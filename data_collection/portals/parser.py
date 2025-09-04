import os
import asyncio
import logging
import time
import random
from typing import Optional, Tuple, List, Dict, Set
import sys, json as _json
import aiohttp
from urllib.parse import quote_plus
from dotenv import load_dotenv

# ---- Auth helpers import ----
from data_collection.auth import get_portals_auth_token, get_auth_credentials

# Load ENV once
load_dotenv()

# ---- Mongo helpers import ----
from mongo import (
    init_indexes,
    upsert_collections_and_build_map,
    upsert_nfts_for_collection,
    reset_market_state_for_collection,
)

# Optional model-level reset (if available in your mongo helpers)
try:
    from mongo import reset_market_state_for_model  # type: ignore
except Exception:
    reset_market_state_for_model = None  # type: ignore

# ---- Config copied from existing working scraper ----
API_URL_PORTALS = os.environ.get("API_URL_PORTALS") or "https://portals-market.com"

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

ZERO_RESULTS_FREEZE_SECONDS = int(os.environ.get("PORTALS_ZERO_RESULTS_FREEZE_SEC", "300"))  # default 5 minutes

# New global limits/thresholds
MAX_OFFSET = int(os.environ.get("PORTALS_MAX_OFFSET", "600"))  # maximum offset value to request (inclusive)
BIG_THRESHOLD = int(os.environ.get("PORTALS_BIG_THRESHOLD", "500"))  # >500 ⇒ big
DISCOVERY_LIMIT = int(os.environ.get("PORTALS_DISCOVERY_LIMIT", str(MAX_OFFSET)))  # single-request discovery limit


# ---- Minimal helper to obtain auth token with retry/backoff ----
async def _get_auth_token_with_retry(max_attempts: int = 3) -> str:
    """Obtain a TMA token using the same protocol as backdropsfiltered_scraper.
    Uses get_auth_credentials() and get_portals_auth_token(...) with gentle retry/backoff.
    """
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
async def scan_offsets(collection_id: str, headers: dict, seen_ids: Set[str], collection_name: str | None = None) -> List[Dict]:
    """Offset paging up to MAX_OFFSET (limit=50) and early-stop on two duplicate pages.
    Copied from the working scraper so classification is identical.
    """
    items: List[Dict] = []
    scan_offsets._dup_pages = 0  # type: ignore[attr-defined]
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        for offset in range(0, MAX_OFFSET + OFFSET_STEP, OFFSET_STEP):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}&status=listed&sort_by=price+asc"
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
                    f"Duplicate page (all duplicates) at offset {offset} for collection {collection_id}"
                    + (f" ({collection_name})" if collection_name else "")
                    + f" [{scan_offsets._dup_pages} consecutive]"
                )
                if scan_offsets._dup_pages >= 2:  # type: ignore[attr-defined]
                    logger.info(
                        f"Early stop (2 consecutive duplicate pages) at offset {offset} for collection {collection_id}"
                        + (f" ({collection_name})" if collection_name else "")
                    )
                    break
            else:
                scan_offsets._dup_pages = 0  # type: ignore[attr-defined]
            for it in new_items:
                seen_ids.add(it["id"])  # type: ignore[index]
            items.extend(new_items)
            await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
    logger.info(
        f"Wide scan collected {len(items)} items for collection {collection_id}"
        + (f" ({collection_name})" if collection_name else "")
    )
    return items


async def classify_collection_by_threshold(collection_id: str, auth_token: str, threshold: int = BIG_THRESHOLD, collection_name: str | None = None) -> dict:
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
    items = await scan_offsets(collection_id, headers, seen_ids, collection_name)
    count = len(items)
    is_small = count < threshold
    logger.info(
        f"classify: collection={collection_id}"
        + (f" ({collection_name})" if collection_name else "")
        + f" count={count} threshold={threshold} is_small={is_small}"
    )
    return {
        "collection_id": collection_id,
        "count_seen": count,
        "is_small": is_small,
        "threshold": threshold,
        "items": items,
    }


# ---- Variant 2 helpers: per-model processing with model-level backdrop discovery ----
async def _fetch_models_for_collection(short_name: str, auth_token: str) -> list[str]:
    """Return a list of model names for a collection via /api/collections/filters?short_names=..."""
    url = f"{API_URL_PORTALS}/api/collections/filters?short_names={quote_plus(short_name)}"
    headers = {"Authorization": f"tma {auth_token}", "User-Agent": "TelegramBot", "Accept": "application/json"}
    async with aiohttp.ClientSession() as session:
        status, data = await fetch_json(session, url, headers)
        if status != 200 or not data:
            logger.warning(f"_fetch_models_for_collection: HTTP {status} for {short_name}")
            return []
        try:
            col = (data.get("collections") or {}).get(short_name) or {}
            models = col.get("models") or []
            names = [m.get("name") for m in models if isinstance(m, dict) and m.get("name")]
            return [str(n) for n in names]
        except Exception as e:
            logger.warning(f"_fetch_models_for_collection parse failed for {short_name}: {e}")
            return []

async def _discover_active_backdrops_for_model(collection_id: str, model: str, auth_token: str, *, limit: int = DISCOVERY_LIMIT) -> set[str]:
    """Discover active backdrops for a model via a single request with a high limit (no asc/desc paging).
    Pulls up to `limit` items (default DISCOVERY_LIMIT) sorted by price asc and extracts all distinct backdrops from attributes.
    """
    headers = {"Authorization": f"tma {auth_token}", "User-Agent": "TelegramBot", "Accept": "application/json"}
    collection = quote_plus(collection_id)
    backdrops: set[str] = set()

    url = (
        f"{API_URL_PORTALS}/api/nfts/search?offset=0&limit={int(limit)}&collection_id={collection}"
        f"&status=listed&filter_by_models={quote_plus(model)}&sort_by=price+asc"
    )
    async with aiohttp.ClientSession() as session:
        status, data = await fetch_json(session, url, headers)
        if status != 200 or not data:
            logger.warning(f"_discover_active_backdrops_for_model: HTTP {status} for model={model} in collection={collection_id}")
            return backdrops
        results = data.get("results") or []
        for it in results:
            attrs = it.get("attributes") or []
            if isinstance(attrs, list):
                for a in attrs:
                    t = str(a.get("type", "")).lower()
                    if t == "backdrop":
                        val = a.get("value")
                        if isinstance(val, str) and val:
                            backdrops.add(val)
    return backdrops

async def _scan_offsets_for_model(collection_id: str, model: str, auth_token: str, *, cap: int = MAX_OFFSET) -> list[dict]:
    """Offset pagination for a single model (no backdrop sharding), up to cap (MAX_OFFSET)."""
    headers = {"Authorization": f"tma {auth_token}", "User-Agent": "TelegramBot", "Accept": "application/json"}
    items: list[dict] = []
    seen_ids: set[str] = set()
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        dup_pages = 0
        for offset in range(0, MAX_OFFSET + OFFSET_STEP, OFFSET_STEP):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}"
                f"&status=listed&filter_by_models={quote_plus(model)}&sort_by=price+asc"
            )
            status, data = await fetch_json(session, url, headers)
            if status != 200 or not data:
                await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
                continue
            results = data.get("results") or []
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            if not new_items and results:
                dup_pages += 1
                if dup_pages >= 2:
                    break
            else:
                dup_pages = 0
            for it in new_items:
                seen_ids.add(it.get("id"))
            items.extend(new_items)
            await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
    return items

async def _probe_model_size(collection_id: str, model: str, auth_token: str, *, threshold: int = BIG_THRESHOLD) -> tuple[int, bool, list[dict]]:
    """Probe whether a model has < threshold items by paging up to the threshold. If we reach threshold, it's big. Otherwise, it's small and returns all items."""
    headers = {"Authorization": f"tma {auth_token}", "User-Agent": "TelegramBot", "Accept": "application/json"}
    items: list[dict] = []
    seen_ids: set[str] = set()
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        dup_pages = 0
        count = 0
        # Scan up to the threshold boundary (threshold). If we reach it => big model.
        for offset in range(0, MAX_OFFSET + OFFSET_STEP, OFFSET_STEP):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}"
                f"&status=listed&filter_by_models={quote_plus(model)}&sort_by=price+asc"
            )
            status, data = await fetch_json(session, url, headers)
            if status != 200 or not data:
                await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
                continue
            results = data.get("results") or []
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            if not new_items and results:
                dup_pages += 1
                if dup_pages >= 2:
                    break
            else:
                dup_pages = 0
            for it in new_items:
                seen_ids.add(it.get("id"))
            items.extend(new_items)
            count = len(items)
            if count >= threshold:
                # Big model: hit or crossed the threshold boundary
                return count, False, []
            await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
    # We scanned up to the threshold and didn't reach it => small model; return all collected items
    return count, True, items

async def _fetch_pairs_for_model_backdrops(collection_id: str, model: str, backdrops: set[str], auth_token: str, *, floor_only: bool = True, pages_per_bd: int = 1) -> list[dict]:
    """Fetch items for (model, backdrop) pairs. If floor_only=True, returns at most 1 item per backdrop."""
    headers = {"Authorization": f"tma {auth_token}", "User-Agent": "TelegramBot", "Accept": "application/json"}
    items: list[dict] = []
    seen_ids: set[str] = set()
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        for bd in sorted(backdrops):
            if not bd:
                continue
            bdq = quote_plus(bd)
            if floor_only:
                url = (
                    f"{API_URL_PORTALS}/api/nfts/search?offset=0&limit=50&collection_id={collection}"
                    f"&status=listed&filter_by_models={quote_plus(model)}&filter_by_backdrops={bdq}&sort_by=price+asc"
                )
                status, data = await fetch_json(session, url, headers)
                if status == 200 and data:
                    res = data.get("results") or []
                    for it in res:
                        it_id = it.get("id")
                        if it_id and it_id not in seen_ids:
                            seen_ids.add(it_id)
                            items.append(it)
                await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
            else:
                # small pagination per backdrop
                dup_pages = 0
                for offset in range(0, min(800, pages_per_bd * PAGE_LIMIT), OFFSET_STEP):
                    url = (
                        f"{API_URL_PORTALS}/api/nfts/search?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}"
                        f"&status=listed&filter_by_models={quote_plus(model)}&filter_by_backdrops={bdq}&sort_by=price+asc"
                    )
                    status, data = await fetch_json(session, url, headers)
                    if status != 200 or not data:
                        await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
                        continue
                    res = data.get("results") or []
                    new_items = [it for it in res if (it_id := it.get("id")) and it_id not in seen_ids]
                    if not new_items and res:
                        dup_pages += 1
                        if dup_pages >= 2:
                            break
                    else:
                        dup_pages = 0
                    for it in new_items:
                        seen_ids.add(it.get("id"))
                    items.extend(new_items)
                    await asyncio.sleep(BASE_DELAY_BETWEEN_REQUESTS + _jitter())
    return items


# ---- Step 1 orchestrator with branching ----
async def process_big_collection(collection: dict, auth_token: str) -> dict:
    """Big collection (≥700 total): per-model processing, model-probe then shard by active backdrops if needed.
    Saves data incrementally (no full reset). If a particular fetch yields zero items, it preserves existing DB state.
    """
    cid = str(collection.get("id") or (collection.get("raw") or {}).get("id") or (collection.get("raw") or {}).get("collection_id"))
    name = collection.get("name") or (collection.get("raw") or {}).get("name") or ""
    short = collection.get("short_name") or (collection.get("raw") or {}).get("short_name") or ""

    # Ensure collection meta exists and get uid
    try:
        id_to_uid = await upsert_collections_and_build_map([collection], market="portals")
    except Exception as e:
        logger.warning(f"[BIG] {name or short or cid}: failed to upsert collection meta: {e}")
        id_to_uid = {}
    collection_uid = id_to_uid.get(str(cid))

    # Fetch model list via filters
    models = await _fetch_models_for_collection(short or name, auth_token)
    logger.info(f"[BIG] Starting processing for collection {name or short or cid} with {len(models)} models")
    if not models:
        logger.warning(f"[BIG] {name or short or cid}: no models discovered via filters; skipping")
        return {"collection_id": cid, "name": name, "short_name": short, "action": "no_models"}

    total_saved = 0
    per_model_stats: list[dict] = []

    for model in models:
        try:
            logger.info(f"[BIG] Probing model {model} in {name or short or cid}")
            count, is_small, items_if_small = await _probe_model_size(cid, model, auth_token, threshold=BIG_THRESHOLD)
            logger.info(f"[BIG] Model {model}: count={count}, is_small={is_small}")
            if is_small:
                # Save full model scan (incremental upserts; do NOT reset whole collection)
                if not items_if_small:
                    logger.info(f"[BIG][SMALL-MODEL] {name}/{model}: ZERO_RESULTS — preserving DB")
                    per_model_stats.append({"model": model, "count": 0, "saved": 0, "mode": "model-scan"})
                else:
                    if collection_uid:
                        try:
                            # Model-scoped reset (only if helper exists) and only when we have >0 items
                            logger.info(f"[BIG][SMALL-MODEL] {name}/{model}: resetting and upserting {len(items_if_small)} items")
                            if reset_market_state_for_model is not None:
                                try:
                                    await reset_market_state_for_model(collection_uid, model, market="portals")
                                except Exception as re:
                                    logger.warning(f"[BIG][SMALL-MODEL] {name}/{model}: model reset failed: {re}")
                            await upsert_nfts_for_collection(items_if_small, collection_uid, market="portals")
                            total_saved += len(items_if_small)
                            per_model_stats.append({"model": model, "count": len(items_if_small), "saved": len(items_if_small), "mode": "model-scan"})
                        except Exception as e:
                            logger.warning(f"[BIG][SMALL-MODEL] {name}/{model}: upsert failed: {e}")
                            per_model_stats.append({"model": model, "count": len(items_if_small), "saved": 0, "mode": "model-scan-error"})
                    else:
                        per_model_stats.append({"model": model, "count": len(items_if_small), "saved": 0, "mode": "missing-collection-uid"})
                continue

            # Big model: discover active backdrops then fetch per pair (floors-only by default)
            active_bds = await _discover_active_backdrops_for_model(cid, model, auth_token)
            logger.info(f"[BIG][LARGE-MODEL] {name}/{model}: discovered {len(active_bds)} active backdrops")
            if not active_bds:
                logger.info(f"[BIG][LARGE-MODEL] {name}/{model}: no active backdrops discovered; skipping pairs")
                per_model_stats.append({"model": model, "count": count, "saved": 0, "mode": "no-active-backdrops"})
                continue

            items_pairs = await _fetch_pairs_for_model_backdrops(cid, model, active_bds, auth_token, floor_only=True)
            if not items_pairs:
                logger.info(f"[BIG][LARGE-MODEL] {name}/{model}: pairs fetch returned ZERO_RESULTS — preserving DB")
                per_model_stats.append({"model": model, "count": count, "saved": 0, "mode": "pairs-zero"})
                continue

            if collection_uid:
                try:
                    # Model-scoped reset (only if helper exists) and only when we have >0 items
                    logger.info(f"[BIG][LARGE-MODEL] {name}/{model}: resetting and upserting {len(items_pairs)} items from pairs")
                    if reset_market_state_for_model is not None:
                        try:
                            await reset_market_state_for_model(collection_uid, model, market="portals")
                        except Exception as re:
                            logger.warning(f"[BIG][LARGE-MODEL] {name}/{model}: model reset failed: {re}")
                    await upsert_nfts_for_collection(items_pairs, collection_uid, market="portals")
                    total_saved += len(items_pairs)
                    per_model_stats.append({"model": model, "count": len(items_pairs), "saved": len(items_pairs), "mode": "pairs-floor"})
                except Exception as e:
                    logger.warning(f"[BIG][LARGE-MODEL] {name}/{model}: upsert pairs failed: {e}")
                    per_model_stats.append({"model": model, "count": len(items_pairs), "saved": 0, "mode": "pairs-error"})
            else:
                per_model_stats.append({"model": model, "count": len(items_pairs), "saved": 0, "mode": "missing-collection-uid"})

        except Exception as e:
            logger.warning(f"[BIG] {name}/{model}: processing failed: {e}")
            per_model_stats.append({"model": model, "count": 0, "saved": 0, "mode": "exception"})
        await asyncio.sleep(0.05)

    try:
        # Ensure collection meta is up-to-date at the end of the run
        await upsert_collections_and_build_map([collection], market="portals")
    except Exception as e:
        logger.warning(f"[BIG] {name or short or cid}: final collection meta upsert failed: {e}")
    logger.info(f"[BIG] Finished processing {name or short or cid}: total_saved={total_saved}, models={len(models)})")
    return {"collection_id": cid, "name": name, "short_name": short, "action": "process_big_collection(models)", "saved_total": total_saved, "models": per_model_stats}

async def process_small_collection(collection: dict, auth_token: str, items_precollected: List[dict] | None = None) -> dict:
    """For collections with <700 items: run a general offset scan and persist results.
    IMPORTANT: If gathered items == 0, do NOT reset existing DB state for this collection.
    """
    cid = str(collection.get("id") or (collection.get("raw") or {}).get("id") or (collection.get("raw") or {}).get("collection_id"))
    name = collection.get("name") or (collection.get("raw") or {}).get("name") or ""
    short = collection.get("short_name")

    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }

    # 1) Use precollected items from classification when provided; otherwise do a one-time scan
    if items_precollected is not None:
        items = items_precollected
    else:
        seen_ids: Set[str] = set()
        items = await scan_offsets(cid, headers, seen_ids)
    count = len(items)
    logger.info(f"[SMALL] {name or short or cid}: offset scan collected {count} items")

    # 2) Ensure collection exists in DB and get its UID mapping
    try:
        id_to_uid = await upsert_collections_and_build_map([collection], market="portals")
    except Exception as e:
        logger.warning(f"[SMALL] {name or short or cid}: failed to upsert collection meta: {e}")
        id_to_uid = {}
    collection_uid = id_to_uid.get(str(cid))

    # 3) Persist according to the rule: if zero items → do NOT reset existing DB
    saved = 0
    if count == 0:
        logger.warning(f"[SMALL] {name or short or cid}: ZERO_RESULTS — preserving existing DB state (no reset)")
        logger.warning(f"[SMALL] {name or short or cid}: FREEZE for {ZERO_RESULTS_FREEZE_SECONDS}s due to ZERO_RESULTS")
        await asyncio.sleep(ZERO_RESULTS_FREEZE_SECONDS)
        action = "preserved_existing_no_reset"
    else:
        try:
            if collection_uid:
                logger.info(f"[SMALL] {name or short or cid}: resetting and upserting {count} items")
                # Reset market state before writing fresh set (same behaviour as working scraper)
                await reset_market_state_for_collection(collection_uid, market="portals")
                await upsert_nfts_for_collection(items, collection_uid, market="portals")
                saved = count
                action = "saved_offset_scan"
            else:
                logger.warning(f"[SMALL] {name or short or cid}: no collection UID mapping; skipping DB write")
                action = "missing_collection_uid"
        except Exception as e:
            logger.warning(f"[SMALL] {name or short or cid}: DB write failed: {e}")
            action = "db_write_failed"

    logger.info(f"[SMALL] Finished processing {name or short or cid}: action={action}, saved={saved}")
    return {
        "collection_id": cid,
        "name": name,
        "short_name": short,
        "action": action,
        "count": count,
        "saved": saved,
    }

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

async def classify_all_collections(auth_token: str, threshold: int = BIG_THRESHOLD) -> list[dict]:
    """Classify all collections by threshold. Returns a list of classification dicts."""
    cols = await fetch_all_collections(auth_token)
    results: list[dict] = []
    for c in cols:
        cid = c.get("id") or (c.get("raw") or {}).get("id") or (c.get("raw") or {}).get("collection_id")
        if not cid:
            continue
        try:
            name = c.get("name") or (c.get("raw") or {}).get("name")
            klass = await classify_collection_by_threshold(str(cid), auth_token, threshold=threshold, collection_name=name)
            results.append(klass)
        except Exception as e:
            logger.warning(f"classify_all_collections: Failed for collection {cid}: {e}")
        await asyncio.sleep(0.05)
    return results

async def run_step1_branch_over_collections(auth_token: str, threshold: int = BIG_THRESHOLD) -> list[dict]:
    """Fetch all collections, then for each collection
    run the Step‑1 threshold classification. If count >= threshold → process_big_collection();
    else → process_small_collection().
    """
    cols = await fetch_all_collections(auth_token)
    logger.info(f"Starting run_step1_branch_over_collections for {len(cols)} collections")
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
            name = c.get("name") or (c.get("raw") or {}).get("name")
            # Step‑1: classify this collection
            klass = await classify_collection_by_threshold(str(cid), auth_token, threshold=threshold, collection_name=name)
            count_seen = int(klass.get("count_seen", 0))
            # Branch
            if count_seen >= threshold:
                res = await process_big_collection(c, auth_token)
            else:
                res = await process_small_collection(c, auth_token, klass.get("items"))
            # attach classification info for visibility
            res.update({"count_seen": count_seen, "threshold": threshold})
            results.append(res)
            logger.info(
                f"Finished collection {cid}"
                + (f" ({name})" if name else "")
                + f": action={res.get('action')}, count_seen={count_seen}, saved={res.get('saved', 0)}"
            )
        except Exception as e:
            logger.warning(f"Branching failed for collection {cid}: {e}")
        await asyncio.sleep(0.05)
    return results




async def run_parser():
        args = sys.argv[1:]
        # Default: no args → classify ALL (Step 1 only)
        if not args:
            print("No args provided — obtaining TMA token and classifying ALL collections (Step 1)…")
            api_id, api_hash = await get_auth_credentials()
            auth_token = None
            for attempt in range(3):
                try:
                    auth_token = await get_portals_auth_token(api_id, api_hash)
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.error(f"Failed to obtain auth token after {attempt+1} attempts: {e}")
                        raise
                    await _sleep_backoff(attempt)
            if auth_token is None:
                logger.error("Auth token was not obtained; aborting run")
                return
            auth = auth_token
            res = await classify_all_collections(auth, threshold=BIG_THRESHOLD)
            print(_json.dumps(res, ensure_ascii=False, indent=2))
            logger.info("Parser run complete")
            return

        # run-step1-branch: fetch all, skip first, classify each, then branch to stub handlers
        if args[0] == "run-step1-branch":
            if len(args) == 2:
                auth = args[1]
            else:
                print("No AUTH_TOKEN provided — using PORTALS_TMA_TOKEN/PORTALS_AUTH_TOKEN if set, or existing session; otherwise obtaining a TMA token…")
                api_id, api_hash = await get_auth_credentials()
                auth_token = None
                for attempt in range(3):
                    try:
                        auth_token = await get_portals_auth_token(api_id, api_hash)
                        break
                    except Exception as e:
                        if attempt == 2:
                            logger.error(f"Failed to obtain auth token after {attempt+1} attempts: {e}")
                            raise
                        await _sleep_backoff(attempt)
                if auth_token is None:
                    logger.error("Auth token was not obtained; aborting run")
                    return
                auth = auth_token
            res = await run_step1_branch_over_collections(auth, threshold=BIG_THRESHOLD)
            print(_json.dumps(res, ensure_ascii=False, indent=2))
            return

        # list-collections mode
        if args[0] == "list-collections":
            if len(args) == 2:
                auth = args[1]
            else:
                print("No AUTH_TOKEN provided — using PORTALS_TMA_TOKEN/PORTALS_AUTH_TOKEN if set, or existing session; otherwise obtaining a TMA token…")
                api_id, api_hash = await get_auth_credentials()
                auth_token = None
                for attempt in range(3):
                    try:
                        auth_token = await get_portals_auth_token(api_id, api_hash)
                        break
                    except Exception as e:
                        if attempt == 2:
                            logger.error(f"Failed to obtain auth token after {attempt+1} attempts: {e}")
                            raise
                        await _sleep_backoff(attempt)
                if auth_token is None:
                    logger.error("Auth token was not obtained; aborting run")
                    return
                auth = auth_token
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
            api_id, api_hash = await get_auth_credentials()
            auth_token = None
            for attempt in range(3):
                try:
                    auth_token = await get_portals_auth_token(api_id, api_hash)
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.error(f"Failed to obtain auth token after {attempt+1} attempts: {e}")
                        raise
                    await _sleep_backoff(attempt)
            if auth_token is None:
                logger.error("Auth token was not obtained; aborting run")
                return
            auth = auth_token
            res = await classify_collection_by_threshold(coll, auth)
            print(_json.dumps(res, ensure_ascii=False, indent=2))
            return



if __name__ == "__main__":
    asyncio.run(run_parser())