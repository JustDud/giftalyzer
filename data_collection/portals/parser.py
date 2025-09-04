import os
import asyncio
import logging
import time
import random
from typing import Optional, Tuple, List, Dict, Set

import aiohttp
from urllib.parse import quote_plus
from dotenv import load_dotenv

# ---- Auth helpers import ----
from data_collection.auth import get_portals_auth_token, get_auth_credentials

# Load ENV once
load_dotenv()

# ---- Config copied from existing working scraper ----
API_URL_PORTALS = os.environ.get("API_URL_PORTALS")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OFFSET_STEP = 50
PAGE_LIMIT = 50

# Rate limit/cooldown configuration and state (copied minimal subset)
COOLDOWN_SECONDS = int(os.environ.get("PORTALS_COOLDOWN_SECONDS", "900"))  # default 15m
RATE_LIMIT_STRIKES_THRESHOLD = int(os.environ.get("PORTALS_RATE_LIMIT_STRIKES", "3"))
BASE_DELAY_BETWEEN_REQUESTS = float(os.environ.get("PORTALS_BASE_DELAY_SEC", "0.25"))
JITTER_MIN = float(os.environ.get("PORTALS_JITTER_MIN_SEC", "0.05"))
JITTER_MAX = float(os.environ.get("PORTALS_JITTER_MAX_SEC", "0.15"))
TOKEN_BUCKET_CAPACITY = int(os.environ.get("PORTALS_TOKEN_BUCKET_CAPACITY", "3"))
TOKEN_BUCKET_RPS = float(os.environ.get("PORTALS_TOKEN_BUCKET_RPS", "3.0"))


# ---- Minimal helper to obtain auth token with retry/backoff ----
async def _get_auth_token_with_retry(max_attempts: int = 3) -> str:
    """Obtain a TMA token without minting a new one if avoidable.
    Order: ENV → existing session file → helpers
    """
    # 1) Prefer an env-provided token (server already running same token)
    env_token = (
        os.environ.get("PORTALS_TMA_TOKEN")
        or os.environ.get("PORTALS_AUTH_TOKEN")
        or os.environ.get("TMA_AUTH_TOKEN")
    )
    if env_token and env_token.strip():
        return env_token.strip()

    # 2) Reuse a local Telethon session if available to avoid a fresh login
    try:
        here = os.path.dirname(__file__)
        session_path = os.path.join(here, "giftalyzer.session")
        if os.path.exists(session_path):
            os.environ.setdefault("TELETHON_SESSION", session_path)
            os.environ.setdefault("PORTALS_SESSION_FILE", session_path)
    except Exception:
        pass

    # 3) Fallback: obtain via existing auth helpers (may create/refresh token)
    api_id, api_hash = await get_auth_credentials()
    last_exc = None
    for attempt in range(max_attempts):
        try:
            return await get_portals_auth_token(api_id, api_hash)
        except Exception as e:
            last_exc = e
            if attempt < max_attempts - 1:
                await _sleep_backoff(attempt)
    raise RuntimeError(f"Failed to obtain auth token after {max_attempts} attempts: {last_exc}")

# ---- Token bucket & rate state (copied) ----
class TokenBucket:
    def __init__(self, capacity: int, refill_rate_per_sec: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate_per_sec
        self.last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.refill_rate
                await asyncio.sleep(max(0.0, wait))
                self.tokens = 0
                self.last = time.monotonic()
            else:
                self.tokens -= 1

GLOBAL_BUCKET = TokenBucket(TOKEN_BUCKET_CAPACITY, TOKEN_BUCKET_RPS)


def _jitter() -> float:
    return random.uniform(JITTER_MIN, JITTER_MAX)


class _RateState:
    def __init__(self):
        self.strikes_429: int = 0
        self.cooldown_until: float = 0.0

RATE = _RateState()


async def _sleep_backoff(attempt: int, retry_after: float | None = None):
    """Sleep with exponential backoff and jitter. Honors Retry-After if provided."""
    if retry_after is not None:
        await asyncio.sleep(float(retry_after))
        return
    delay = 0.2 * (2 ** attempt) + random.random() * 0.1
    await asyncio.sleep(min(delay, 4))


async def _global_cooldown():
    now = time.monotonic()
    if now < RATE.cooldown_until:
        remaining = RATE.cooldown_until - now
        logger.warning(f"🧊 Cooldown already active — {remaining:.1f}s remaining...")
        await asyncio.sleep(remaining)
        return
    RATE.cooldown_until = now + COOLDOWN_SECONDS
    logger.warning(f"🧊 Too many 429s — entering {COOLDOWN_SECONDS}s cooldown window...")
    await asyncio.sleep(COOLDOWN_SECONDS)


# ---- HTTP helper (copied) ----
async def fetch_json(session: aiohttp.ClientSession, url: str, headers: dict, *, max_retries: int = 6) -> Tuple[int, dict | None]:
    last_status: Optional[int] = None
    for attempt in range(max_retries + 1):
        now = time.monotonic()
        if now < RATE.cooldown_until:
            await asyncio.sleep(RATE.cooldown_until - now)

        await GLOBAL_BUCKET.acquire()
        await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())

        try:
            async with session.get(url, headers=headers) as resp:
                last_status = resp.status

                if resp.status == 200:
                    if RATE.strikes_429 > 0:
                        RATE.strikes_429 = max(0, RATE.strikes_429 - 1)
                    try:
                        return 200, await resp.json()
                    except Exception:
                        if attempt < max_retries:
                            await _sleep_backoff(attempt)
                            continue
                        return resp.status, None

                if resp.status == 429:
                    RATE.strikes_429 += 1
                    ra = resp.headers.get("Retry-After")
                    if ra:
                        try:
                            wait = float(ra)
                        except ValueError:
                            wait = 5.0
                    else:
                        wait = min(8.0, (1.2 ** RATE.strikes_429)) + random.uniform(0.25, 0.75)

                    if RATE.strikes_429 >= RATE_LIMIT_STRIKES_THRESHOLD:
                        await _global_cooldown()
                        RATE.strikes_429 = max(0, RATE.strikes_429 - 2)
                        continue

                    await asyncio.sleep(wait)
                    continue

                if resp.status in {500, 502, 503, 504}:
                    if attempt < max_retries:
                        await asyncio.sleep(1.5 + random.uniform(0.0, 0.5))
                        continue
                    return resp.status, None

                return resp.status, None

        except aiohttp.ClientError:
            if attempt < max_retries:
                await _sleep_backoff(attempt)
                continue
            return last_status or 0, None

    return last_status or 0, None


# ---- EXACT working threshold logic (collection) reproduced ----
async def scan_offsets(collection_id: str, headers: dict, seen_ids: Set[str]) -> List[Dict]:
    """Offset paging up to 800 (limit=50) and early-stop on two duplicate pages.
    Copied from the working scraper so classification is identical.
    """
    items: List[Dict] = []
    scan_offsets._dup_pages = 0  # type: ignore[attr-defined]
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        for offset in range(0, 800, OFFSET_STEP):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}&status=listed"
            )
            status, data = await fetch_json(session, url, headers)
            if status != 200 or not data:
                await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
                continue
            results = data.get("results", []) or []
            if not hasattr(scan_offsets, "_dup_pages"):
                scan_offsets._dup_pages = 0  # type: ignore[attr-defined]
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            if not new_items and results:
                scan_offsets._dup_pages += 1  # type: ignore[attr-defined]
                logger.info(
                    f"Duplicate page (all duplicates) at offset {offset} for collection {collection_id} "
                    f"[{scan_offsets._dup_pages} consecutive]"
                )
                if scan_offsets._dup_pages >= 2:  # type: ignore[attr-defined]
                    logger.info(
                        f"Early stop (2 consecutive duplicate pages) at offset {offset} for collection {collection_id}"
                    )
                    break
            else:
                scan_offsets._dup_pages = 0  # type: ignore[attr-defined]
            for it in new_items:
                seen_ids.add(it["id"])  # type: ignore[index]
            items.extend(new_items)
            await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
    logger.info(f"Wide scan collected {len(items)} items")
    return items


async def classify_collection_by_threshold(collection_id: str, auth_token: str, threshold: int = 700) -> dict:
    """Step 1: EXACTLY the same decision criterion as the working code.

    Performs an offset scan (no filters) and uses the item count to decide
    whether the collection is considered small (< threshold) or big (>= threshold).

    Returns a dict like:
    {
        'collection_id': <id>,
        'count_seen': <int>,
        'is_small': <bool>,
        'threshold': <int>
    }
    """
    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
    seen_ids: Set[str] = set()
    items = await scan_offsets(collection_id, headers, seen_ids)
    count = len(items)
    is_small = count <= threshold
    logger.info(
        f"classify_collection_by_threshold: collection={collection_id} count={count} threshold={threshold} is_small={is_small}"
    )
    return {
        "collection_id": collection_id,
        "count_seen": count,
        "is_small": is_small,
        "threshold": threshold,
    }


# ---- Step 1 orchestrator with branching (skip first collection) ----
async def process_big_collection(collection: dict, auth_token: str) -> dict:
    """Placeholder for big collections (≥700). Will later run model/backdrop sharding.
    For now, just emit a log and return a draft result structure.
    """
    cid = str(collection.get("id") or (collection.get("raw") or {}).get("id") or (collection.get("raw") or {}).get("collection_id"))
    name = collection.get("name") or (collection.get("raw") or {}).get("name")
    short = collection.get("short_name")
    logger.info(f"[BIG] {name or short or cid}: would run sharded processing here (draft stub)")
    return {"collection_id": cid, "name": name, "short_name": short, "action": "process_big_collection(draft)"}

async def process_small_collection(collection: dict, auth_token: str) -> dict:
    """Placeholder for small collections (<700). Will later persist general scan results.
    For now, just emit a log and return a draft result structure.
    """
    cid = str(collection.get("id") or (collection.get("raw") or {}).get("id") or (collection.get("raw") or {}).get("collection_id"))
    name = collection.get("name") or (collection.get("raw") or {}).get("name")
    short = collection.get("short_name")
    logger.info(f"[SMALL] {name or short or cid}: would save general-scan results to DB here (draft stub)")
    return {"collection_id": cid, "name": name, "short_name": short, "action": "process_small_collection(draft)"}

async def fetch_all_collections(auth_token: str, limit: int = 500) -> list[dict]:
    """Fetch collections from the API with the same behaviour as backdropsfiltered_scraper.get_collections."""
    url = f"{API_URL_PORTALS}/api/collections?limit={limit}"
    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        status, data = await fetch_json(session, url, headers)
        if status != 200 or not data:
            logger.warning(f"fetch_all_collections(): HTTP {status}")
            return []
        return data.get("collections", data) or []

async def classify_all_collections(auth_token: str, threshold: int = 700) -> list[dict]:
    """Classify all collections by threshold. Returns a list of classification dicts."""
    cols = await fetch_all_collections(auth_token)
    results: list[dict] = []
    for c in cols:
        cid = c.get("id") or (c.get("raw") or {}).get("id") or (c.get("raw") or {}).get("collection_id")
        if not cid:
            continue
        try:
            klass = await classify_collection_by_threshold(str(cid), auth_token, threshold=threshold)
            results.append(klass)
        except Exception as e:
            logger.warning(f"classify_all_collections: Failed for collection {cid}: {e}")
        await asyncio.sleep(0.05)
    return results

async def run_step1_branch_over_collections(auth_token: str, threshold: int = 700) -> list[dict]:
    """Fetch all collections, drop the first one, then for each remaining collection
    run the Step‑1 threshold classification. If count >= threshold → process_big_collection();
    else → process_small_collection(). For now both handlers are placeholders.
    """
    cols = await fetch_all_collections(auth_token)
    if not cols:
        logger.warning("No collections fetched; nothing to do")
        return []


    results: list[dict] = []
    for c in cols:
        cid = c.get("id") or (c.get("raw") or {}).get("id") or (c.get("raw") or {}).get("collection_id")
        if not cid:
            logger.warning(f"Skipping collection without id: {c}")
            continue
        try:
            # Step‑1: classify this collection
            klass = await classify_collection_by_threshold(str(cid), auth_token, threshold=threshold)
            count_seen = int(klass.get("count_seen", 0))
            # Branch
            if count_seen >= threshold:
                res = await process_big_collection(c, auth_token)
            else:
                res = await process_small_collection(c, auth_token)
            # attach classification info for visibility
            res.update({"count_seen": count_seen, "threshold": threshold})
            results.append(res)
        except Exception as e:
            logger.warning(f"Branching failed for collection {cid}: {e}")
        await asyncio.sleep(0.05)
    return results


if __name__ == "__main__":
    import sys, json as _json

    async def _main():
        args = sys.argv[1:]
        # Default: no args → classify ALL (Step 1 only)
        if not args:
            print("No args provided — obtaining TMA token and classifying ALL collections (Step 1)…")
            auth = await _get_auth_token_with_retry()
            res = await classify_all_collections(auth, threshold=700)
            print(_json.dumps(res, ensure_ascii=False, indent=2))
            return

        # run-step1-branch: fetch all, skip first, classify each, then branch to stub handlers
        if args[0] == "run-step1-branch":
            if len(args) == 2:
                auth = args[1]
            else:
                print("No AUTH_TOKEN provided — using PORTALS_TMA_TOKEN/PORTALS_AUTH_TOKEN if set, or existing session; otherwise obtaining a TMA token…")
                auth = await _get_auth_token_with_retry()
            res = await run_step1_branch_over_collections(auth, threshold=700)
            print(_json.dumps(res, ensure_ascii=False, indent=2))
            return

        # list-collections mode
        if args[0] == "list-collections":
            if len(args) == 2:
                auth = args[1]
            else:
                print("No AUTH_TOKEN provided — using PORTALS_TMA_TOKEN/PORTALS_AUTH_TOKEN if set, or existing session; otherwise obtaining a TMA token…")
                auth = await _get_auth_token_with_retry()
            cols = await fetch_all_collections(auth)
            print(_json.dumps(cols, ensure_ascii=False, indent=2))
            return

        # Single collection classification modes
        if len(args) == 2:
            auth, coll = args
            res = await classify_collection_by_threshold(coll, auth)
            print(_json.dumps(res, ensure_ascii=False, indent=2))
            return
        elif len(args) == 1:
            coll = args[0]
            print("No AUTH_TOKEN provided — using PORTALS_TMA_TOKEN/PORTALS_AUTH_TOKEN if set, or existing session; otherwise obtaining a TMA token…")
            auth = await _get_auth_token_with_retry()
            res = await classify_collection_by_threshold(coll, auth)
            print(_json.dumps(res, ensure_ascii=False, indent=2))
            return

        print("Usage:\n  python parser.py                               # classify ALL collections (auto token)\n  python parser.py list-collections [AUTH_TOKEN]\n  python parser.py run-step1-branch [AUTH_TOKEN]\n  python parser.py <COLLECTION_ID>\n  python parser.py <AUTH_TOKEN> <COLLECTION_ID>")

    asyncio.run(_main())