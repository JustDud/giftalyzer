import asyncio
import aiohttp
import os
import logging
from urllib.parse import quote_plus
from dotenv import load_dotenv
from typing import Tuple, List, Dict, Set
import random
import csv

from data_collection.auth import get_portals_auth_token, get_auth_credentials
from mongo import (
    init_indexes,
    upsert_collections_and_build_map,
    upsert_nfts_for_collection,
    reset_market_state_for_collection,
)
from data_collection.portals.backdrops_fetcher import fetch_backdrops as get_all_backdrops


load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
OFFSET_STEP = 50
PAGE_LIMIT = 50

# Rate limit/cooldown configuration and state
COOLDOWN_SECONDS = int(os.environ.get("PORTALS_COOLDOWN_SECONDS", "300"))  # 5 minutes default
RATE_LIMIT_STRIKES_THRESHOLD = int(os.environ.get("PORTALS_RATE_LIMIT_STRIKES", "3"))  # consecutive 429s before cooldown
_rate_limit_strikes = 0



async def _sleep_backoff(attempt: int, retry_after: float | None = None):
    """Sleep with exponential backoff and jitter. Honors Retry-After if provided."""
    if retry_after is not None:
        await asyncio.sleep(float(retry_after))
        return
    delay = 0.2 * (2 ** attempt) + random.random() * 0.1
    await asyncio.sleep(min(delay, 4))


# Global cooldown after too many consecutive 429s
async def _global_cooldown():
    logger.warning(f"🧊 Too many 429s in a row — cooling down for {COOLDOWN_SECONDS}s...")
    await asyncio.sleep(COOLDOWN_SECONDS)


async def fetch_json(session: aiohttp.ClientSession, url: str, headers: dict, *, max_retries: int = 6) -> Tuple[int, dict | None]:
    global _rate_limit_strikes
    last_status = None
    for attempt in range(max_retries + 1):
        try:
            async with session.get(url, headers=headers) as resp:
                last_status = resp.status
                if resp.status == 200:
                    # reset strike counter on success
                    _rate_limit_strikes = 0
                    try:
                        return 200, await resp.json()
                    except Exception:
                        if attempt < max_retries:
                            await _sleep_backoff(attempt)
                            continue
                        return resp.status, None
                if resp.status == 429:
                    # too many requests — honor Retry-After if present, else exponential backoff
                    _rate_limit_strikes += 1
                    retry_after = resp.headers.get("Retry-After")
                    if _rate_limit_strikes >= RATE_LIMIT_STRIKES_THRESHOLD:
                        # enter a longer cool-down to let the API recover
                        await _global_cooldown()
                        _rate_limit_strikes = 0
                        continue
                    await _sleep_backoff(attempt, retry_after=float(retry_after) if retry_after else None)
                    continue
                if resp.status in {500, 502, 503, 504}:
                    # reset strike counter for non-429 server errors
                    _rate_limit_strikes = 0
                    if attempt < max_retries:
                        await _sleep_backoff(attempt)
                        continue
                # reset strike counter for all other non-429 statuses
                _rate_limit_strikes = 0
                return resp.status, None
        except aiohttp.ClientError:
            _rate_limit_strikes = 0
            if attempt < max_retries:
                await _sleep_backoff(attempt)
                continue
            return last_status or 0, None
    return last_status or 0, None


def _nice_step(target_step: float) -> float:
    candidates = [
        0.1, 0.2, 0.5,
        1, 2, 5,
        10, 20, 25, 50,
        100, 200, 250, 500,
        1000, 2000, 5000
    ]
    for cand in candidates:
        if cand >= target_step:
            return cand
    return candidates[-1]


async def analyze_price_range(collection_id: str, headers: dict) -> Tuple[float, float]:
    """Approximate min/max price from the first page (listed)."""
    collection = quote_plus(collection_id)
    url = (
        f"{API_URL_PORTALS}/api/nfts/search?offset=0&limit={PAGE_LIMIT}"
        f"&collection_id={collection}&status=listed"
    )
    async with aiohttp.ClientSession() as session:
        status, data = await fetch_json(session, url, headers)
        if status == 200 and data:
            results = data.get("results", [])
            prices: List[float] = []
            for it in results:
                try:
                    prices.append(float(it.get("price", 0)))
                except Exception:
                    continue
            if prices:
                return min(prices), max(prices)
    # fallback
    return 0.0, 0.0


def _get_attr(it: Dict, keys: List[str]) -> str | None:
    for k in keys:
        v = it.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


async def scan_offsets(collection_id: str, headers: dict, seen_ids: Set[str]) -> List[Dict]:
    """Wide scan: listed by offsets up to 800 (limit=50). Skips empty/error pages without stopping early."""
    items: List[Dict] = []
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        for offset in range(0, 800, OFFSET_STEP):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}&status=listed"
            )
            status, data = await fetch_json(session, url, headers)
            if status != 200 or not data:
                await asyncio.sleep(0.1)
                continue
            results = data.get("results", [])
            if results is None:
                results = []
            if not hasattr(scan_offsets, "_dup_pages"):
                scan_offsets._dup_pages = 0
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            if not new_items and results:
                scan_offsets._dup_pages += 1
                logger.info(f"Duplicate page (all duplicates) at offset {offset} for collection {collection_id} [{scan_offsets._dup_pages} consecutive]")
                if scan_offsets._dup_pages >= 2:
                    logger.info(f"Early stop (2 consecutive duplicate pages) at offset {offset} for collection {collection_id}")
                    break
            else:
                scan_offsets._dup_pages = 0
            for it in new_items:
                seen_ids.add(it["id"])
            items.extend(new_items)
            await asyncio.sleep(0.1)
    logger.info(f"Wide scan collected {len(items)} items")
    return items


async def scan_price_range(collection_id: str, headers: dict, pmin: float, pmax: float, seen_ids: Set[str]) -> List[Dict]:
    """Scan a single price subrange with offsets up to 800 (limit=50). Skips empty/error pages."""
    items: List[Dict] = []
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        for offset in range(0, 800, OFFSET_STEP):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}&status=listed"
                f"&min_price={pmin}&max_price={pmax}"
            )
            status, data = await fetch_json(session, url, headers)
            if status != 200 or not data:
                await asyncio.sleep(0.1)
                continue
            results = data.get("results", [])
            if results is None:
                results = []
            if not hasattr(scan_price_range, "_dup_pages"):
                scan_price_range._dup_pages = 0
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            if not new_items and results:
                scan_price_range._dup_pages += 1
                logger.info(f"Duplicate page (all duplicates) at offset {offset} for collection {collection_id} in price range [{pmin}, {pmax}] [{scan_price_range._dup_pages} consecutive]")
                if scan_price_range._dup_pages >= 2:
                    logger.info(f"Early stop (2 consecutive duplicate pages) at offset {offset} for collection {collection_id} in price range [{pmin}, {pmax}]")
                    break
            else:
                scan_price_range._dup_pages = 0
            for it in new_items:
                seen_ids.add(it["id"])
            items.extend(new_items)
            await asyncio.sleep(0.1)
    return items


async def scan_by_attribute(collection_id: str, headers: dict, param_name: str, values: List[str], seen_ids: Set[str]) -> List[Dict]:
    """Partitioned scans by attribute values (e.g., filter_by_backdrops/symbols) with limit=50 offsets.
    Probes each value at offset=0 first; if empty, skips full scan for that value.
    """
    items: List[Dict] = []
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        for val in values:
            if not val:
                continue
            qval = quote_plus(val)
            # Probe at offset=0 to see if value has any items
            probe_url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset=0&limit={PAGE_LIMIT}&collection_id={collection}&status=listed"
                f"&{param_name}={qval}"
            )
            status, data = await fetch_json(session, probe_url, headers)
            if status != 200 or not data or not data.get("results"):
                continue

            # Full scan across offsets only for values that returned items
            for offset in range(0, 800, OFFSET_STEP):
                url = (
                    f"{API_URL_PORTALS}/api/nfts/search"
                    f"?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}&status=listed"
                    f"&{param_name}={qval}"
                )
                s2, d2 = await fetch_json(session, url, headers)
                if s2 != 200 or not d2:
                    await asyncio.sleep(0.1)
                    continue
                results = d2.get("results", [])
                if results is None:
                    results = []
                if not hasattr(scan_by_attribute, "_dup_pages"):
                    scan_by_attribute._dup_pages = 0
                new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
                if not new_items and results:
                    scan_by_attribute._dup_pages += 1
                    logger.info(f"Duplicate page (all duplicates) at offset {offset} for collection {collection_id} on {param_name}={val} [{scan_by_attribute._dup_pages} consecutive]")
                    if scan_by_attribute._dup_pages >= 2:
                        logger.info(f"Early stop (2 consecutive duplicate pages) at offset {offset} for collection {collection_id} on {param_name}={val}")
                        break
                else:
                    scan_by_attribute._dup_pages = 0
                for it in new_items:
                    seen_ids.add(it["id"])
                items.extend(new_items)
                await asyncio.sleep(0.1)
    return items


async def get_filter_values(session: aiohttp.ClientSession, url: str, headers: dict) -> list[str]:
    status, data = await fetch_json(session, url, headers)
    if status != 200 or not data:
        return []
    # Try common shapes: list, {values: []}, {results: []}, {backdrops: []}, {symbols: []}
    if isinstance(data, list):
        return [str(x) for x in data if isinstance(x, (str, int))]
    for key in ("values", "results", "backdrops", "symbols"):
        val = data.get(key)
        if isinstance(val, list):
            return [str(x) for x in val if isinstance(x, (str, int))]
    return []


async def get_collection_filter_sets(collection_id: str, headers: dict) -> tuple[list[str], list[str]]:
    """Fetch available backdrops and symbols for a collection."""
    collection = quote_plus(collection_id)
    backdrops_url = f"{API_URL_PORTALS}/api/collections/filters/backdrops?collection_id={collection}"
    symbols_url = f"{API_URL_PORTALS}/api/collections/filters/symbols?collection_id={collection}"
    async with aiohttp.ClientSession() as session:
        backdrops = await get_filter_values(session, backdrops_url, headers)
        symbols = await get_filter_values(session, symbols_url, headers)
    return backdrops, symbols


async def get_collections(limit: int, auth_token: str) -> List[Dict]:
    """Fetch collections from the API with retries/backoff."""
    url = f"{API_URL_PORTALS}/api/collections?limit={limit}"
    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        status, data = await fetch_json(session, url, headers)
        if status != 200 or not data:
            logger.warning(f"collections(): HTTP {status}")
            return []
        return data.get("collections", data) or []


def write_collections_csv(collections: List[Dict], filename: str = "collections_output.csv") -> None:
    logger.info(f"📄 Writing {len(collections)} collections to {filename}")
    # Filter out heavy/unused fields if present
    filtered = [
        {k: v for k, v in c.items() if k not in {"short_name", "photo_url", "is_favorite"}}
        for c in collections
    ]
    if not filtered:
        logger.warning("No collections to write")
        return
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=filtered[0].keys())
        writer.writeheader()
        writer.writerows(filtered)


def append_nfts_csv(items: List[Dict], filename: str = "nfts_output.csv") -> None:
    logger.info("💾 Writing all NFT items to nfts_output.csv...")
    # Clean fields, flatten attributes, and dedupe by id within the batch
    cleaned_items = []
    for it in items:
        base = {k: v for k, v in it.items() if k not in {"photo_url", "status", "animation_url", "emoji_id", "has_animation", "attributes"}}

        # Defaults for flattened attributes
        model = ""
        model_rpm = ""
        symbol = ""
        symbol_rpm = ""
        backdrop = ""
        backdrop_rpm = ""

        attrs = it.get("attributes") or []
        if isinstance(attrs, list):
            for a in attrs:
                try:
                    atype = str(a.get("type", "")).lower()
                except Exception:
                    atype = ""
                val = a.get("value", "")
                rpm = a.get("rarity_per_mille", "")
                if atype == "model":
                    model, model_rpm = val, rpm
                elif atype == "symbol":
                    symbol, symbol_rpm = val, rpm
                elif atype == "backdrop":
                    backdrop, backdrop_rpm = val, rpm

        base.update({
            "model": model,
            "model_rarity_per_mille": model_rpm,
            "symbol": symbol,
            "symbol_rarity_per_mille": symbol_rpm,
            "backdrop": backdrop,
            "backdrop_rarity_per_mille": backdrop_rpm,
        })
        cleaned_items.append(base)

    dedup_map: Dict[str, Dict] = {}
    for row in cleaned_items:
        rid = row.get("id")
        if rid is not None:
            dedup_map[str(rid)] = row
    cleaned_items = list(dedup_map.values())

    # Fixed field order for CSV stability
    fieldnames = [
        "id", "name", "collection_id", "external_collection_number", "price",
        "floor_price", "listed_at", "unlocks_at", "tg_id", "is_owned",
        "model", "model_rarity_per_mille", "symbol", "symbol_rarity_per_mille",
        "backdrop", "backdrop_rarity_per_mille"
    ]
    actual_keys = {key for it in cleaned_items for key in it}
    missing = [k for k in fieldnames if k not in actual_keys]
    if missing:
        logger.warning(f"⚠️ Missing fields in data: {missing}")

    file_exists = os.path.exists(filename)
    existing_ids: Set[str] = set()
    if file_exists:
        try:
            with open(filename, "r", newline="", encoding="utf-8") as fr:
                reader = csv.DictReader(fr)
                for row in reader:
                    rid = row.get("id")
                    if rid:
                        existing_ids.add(rid)
        except Exception as e:
            logger.warning(f"⚠️ Could not read existing CSV for dedupe: {e}")
            existing_ids = set()

    new_rows = 0
    need_header = not file_exists or os.path.getsize(filename) == 0
    with open(filename, "a", newline="", encoding="utf-8") as fa:
        writer = csv.DictWriter(fa, fieldnames=fieldnames)
        if need_header:
            writer.writeheader()
        skipped_missing_id = 0
        skipped_duplicates = 0
        for row in cleaned_items:
            rid = row.get("id")
            if not rid:
                skipped_missing_id += 1
                continue
            rid = str(rid)
            if rid in existing_ids:
                skipped_duplicates += 1
                continue
            writer.writerow({k: row.get(k, "") for k in fieldnames})
            existing_ids.add(rid)
            new_rows += 1
    logger.info(
        f"✅ CSV appended with {new_rows} new NFTs. "
        f"Skipped {skipped_duplicates} duplicates, {skipped_missing_id} with missing id. "
        f"Total unique now ~{len(existing_ids)}."
    )


# --- Partitioned scan by backdrops for a collection ---
async def scan_all_backdrops_for_collection(collection_id: str, headers: dict, backdrops: List[str], seen_ids: Set[str]) -> List[Dict]:
    """
    For a given collection, run partitioned scans for each backdrop value using filter_by_backdrops.
    Assumes 'backdrops' is a pre-fetched global list of backdrop names.
    """
    if not backdrops:
        logger.info("No global backdrops provided; falling back to offset scan")
        return await scan_offsets(collection_id, headers, seen_ids)
    items = await scan_by_attribute(collection_id, headers, "filter_by_backdrops", backdrops, seen_ids)
    logger.info(f"Backdrop-partitioned scan collected {len(items)} items for collection {collection_id}")
    return items


# --- Offset-only execution over all collections ---
async def offset_only_all(auth_token: str, limit: int = 500) -> None:
    logger.info("🔐 Fetching collections list for offset-only strategy...")
    cols = await get_collections(limit, auth_token)
    if not cols:
        logger.warning("No collections received; aborting")
        return
    # Ensure collections exist in DB and build id -> uid map for anchor market
    id_to_uid = await upsert_collections_and_build_map(cols, market="portals")
    #write_collections_csv(cols, filename="collections_output.csv")

    names = [c.get("name") for c in cols if c.get("name")]
    logger.info(f"📋 Processing {len(names)} collections (offset-only)")

    seen_ids_global: Set[str] = set()

    # Iterate all collections and gather NFTs using simple offset scan
    for idx, name in enumerate(names, 1):
        logger.info(f"[{idx}/{len(names)}] {name}")
        try:
            # Resolve id again to be safe
            name_to_id = {c.get("name"): c.get("id") for c in cols if c.get("name") and c.get("id")}
            coll_id = name_to_id.get(name)
            if not coll_id:
                logger.warning(f"No id for collection '{name}', skipping")
                continue
            headers = {
                "Authorization": f"tma {auth_token}",
                "User-Agent": "TelegramBot",
                "Accept": "application/json",
            }
            items = await scan_offsets(coll_id, headers, seen_ids_global)
            # Anchor reset for this collection+market before rewriting state
            collection_uid = id_to_uid.get(str(coll_id))
            if collection_uid:
                await reset_market_state_for_collection(collection_uid, market="portals")
                await upsert_nfts_for_collection(items, collection_uid, market="portals")
        except Exception as e:
            logger.warning(f"Failed '{name}': {e}")
        await asyncio.sleep(0.1)
    # Optional: write last run items to CSV is disabled for DB anchor path
    # append_nfts_csv(all_items, filename="nfts_output.csv")


async def smart_partition_all(auth_token: str, limit: int = 500, threshold: int = 700) -> None:
    logger.info("🔐 Fetching collections list for SMART strategy (offset-first, fallback to backdrops if big)...")
    cols = await get_collections(limit, auth_token)
    if not cols:
        logger.warning("No collections received; aborting")
        return
    id_to_uid = await upsert_collections_and_build_map(cols, market="portals")

    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
    # Prefetch global backdrops once
    global_backdrops: List[str] = await get_all_backdrops(auth_token)
    logger.info(f"Global backdrops loaded once (SMART): {len(global_backdrops)}")

    names = [c.get("name") for c in cols if c.get("name")]
    logger.info(f"📋 Processing {len(names)} collections (SMART, reversed)")

    seen_ids_global: Set[str] = set()
    name_to_id = {c.get("name"): c.get("id") for c in cols if c.get("name") and c.get("id")}

    for idx, name in enumerate(reversed(names), 1):
        logger.info(f"[{idx}/{len(names)}] {name}")
        try:
            coll_id = name_to_id.get(name)
            if not coll_id:
                logger.warning(f"No id for collection '{name}', skipping")
                continue

            # 1) Wide offset scan up to cap
            items_offset = await scan_offsets(coll_id, headers, seen_ids_global)
            logger.info(f"Offset scan found {len(items_offset)} items for collection {name}")

            # 2) Decide: if large, switch to backdrop-partition scan
            if len(items_offset) > threshold:
                logger.info(f"➡️  {name}: >{threshold} items from offsets — switching to backdrops partition scan")
                items = await scan_all_backdrops_for_collection(coll_id, headers, global_backdrops, seen_ids_global)
            else:
                logger.info(f"✅ {name}: ≤{threshold} items — keeping offset scan results")
                items = items_offset

            collection_uid = id_to_uid.get(str(coll_id))
            if collection_uid:
                await reset_market_state_for_collection(collection_uid, market="portals")
                await upsert_nfts_for_collection(items, collection_uid, market="portals")
        except Exception as e:
            logger.warning(f"Failed '{name}': {e}")
        await asyncio.sleep(0.1)


# --- Partitioned by backdrops: orchestrator ---
async def backdrops_partition_all(auth_token: str, limit: int = 500) -> None:
    logger.info("🔐 Fetching collections list for backdrop-partition strategy...")
    cols = await get_collections(limit, auth_token)
    if not cols:
        logger.warning("No collections received; aborting")
        return
    id_to_uid = await upsert_collections_and_build_map(cols, market="portals")
    #write_collections_csv(cols, filename="collections_output.csv")

    # Prefetch global backdrops once using the TMA token
    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
    global_backdrops = await get_all_backdrops(auth_token)
    logger.info(f"Global backdrops loaded once: {len(global_backdrops)}")

    names = [c.get("name") for c in cols if c.get("name")]
    logger.info(f"📋 Processing {len(names)} collections (by backdrops)")

    seen_ids_global: Set[str] = set()
    name_to_id = {c.get("name"): c.get("id") for c in cols if c.get("name") and c.get("id")}

    for idx, name in enumerate(names, 1):
        logger.info(f"[{idx}/{len(names)}] {name}")
        try:
            coll_id = name_to_id.get(name)
            if not coll_id:
                logger.warning(f"No id for collection '{name}', skipping")
                continue
            items = await scan_all_backdrops_for_collection(coll_id, headers, global_backdrops, seen_ids_global)
            collection_uid = id_to_uid.get(str(coll_id))
            if collection_uid:
                await reset_market_state_for_collection(collection_uid, market="portals")
                await upsert_nfts_for_collection(items, collection_uid, market="portals")
        except Exception as e:
            logger.warning(f"Failed '{name}': {e}")
        await asyncio.sleep(0.1)


# --- Existing richer logic (commented out for offset-only mode) ---
# NOTE: The following calls are intentionally commented out to keep the strategy offset-only.
# - Attribute partition scans (backdrops/symbols)
# - Granular price range scans
# If needed later, uncomment and reuse:
# backdrops, symbols = await get_collection_filter_sets(coll_id, headers)
# part_b = await scan_by_attribute(coll_id, headers, "filter_by_backdrops", backdrops, seen_ids)
# part_s = await scan_by_attribute(coll_id, headers, "filter_by_symbols", symbols, seen_ids)
# pmin, pmax = await analyze_price_range(coll_id, headers)
# sub = await scan_price_range(coll_id, headers, current, nxt, seen_ids)


async def scrape_collections_by_backdrop(names: List[str], auth_token: str, limit: int = 500, threshold: int = 700) -> None:
    """Targeted scrape for specific collections.
    Strategy: run an offset scan first; if count exceeds `threshold`, run a backdrop-partitioned scan and merge
    results using a shared seen_ids set to avoid duplicates. Accepts collection names or ids. Processes in reverse order.
    """
    logger.info("🔐 Fetching collections list for targeted strategy (offset-first, thresholded backdrops)...")
    cols = await get_collections(limit, auth_token)
    if not cols:
        logger.warning("No collections received; aborting")
        return
    id_to_uid = await upsert_collections_and_build_map(cols, market="portals")

    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }

    # Prefetch global backdrops once
    global_backdrops: List[str] = await get_all_backdrops(auth_token)
    logger.info(f"Global backdrops loaded once (targeted): {len(global_backdrops)}")

    name_to_id = {c.get("name"): c.get("id") for c in cols if c.get("name") and c.get("id")}

    for idx, name in enumerate(reversed(names), 1):
        coll_id = name_to_id.get(name) or name
        if not coll_id:
            logger.warning(f"No id for '{name}', skipping")
            continue

        logger.info(f"[targeted {idx}/{len(names)}] {name} ({coll_id}) — offset-first (threshold={threshold})")
        try:
            # Use a per-collection seen set to dedupe across scans
            seen_ids_per_run: Set[str] = set()

            # 1) Offset scan first
            items_offset = await scan_offsets(coll_id, headers, seen_ids_per_run)
            logger.info(f"[targeted] {name}: offset scan found {len(items_offset)} items")

            items = list(items_offset)  # copy

            # 2) Only if above threshold, run backdrop-partition and merge
            if len(items_offset) > threshold:
                logger.info(f"[targeted] {name}: >{threshold} items — running backdrop-partition to reduce misses")
                part = await scan_all_backdrops_for_collection(coll_id, headers, global_backdrops, seen_ids_per_run)
                if part:
                    items.extend(part)
            else:
                logger.info(f"[targeted] {name}: ≤{threshold} items — skipping backdrop scan to avoid extra requests")

            # Upsert merged results
            collection_uid = id_to_uid.get(str(coll_id))
            if collection_uid:
                await reset_market_state_for_collection(collection_uid, market="portals")
                await upsert_nfts_for_collection(items, collection_uid, market="portals")
        except Exception as e:
            logger.warning(f"Failed '{name}': {e}")
        await asyncio.sleep(0.1)


async def run_portals_scraper():
    import sys
    args = sys.argv[1:]
    # Modes:
    #  - default (no flag): scrape ALL collections (SMART over all)
    #  - --target <names...>: scrape ONLY the provided collections (offset-first, thresholded backdrop)
    if "--target" in args:
        target_mode = True
        args = [a for a in args if a != "--target"]
    else:
        target_mode = False

    names = args
    api_id, api_hash = await get_auth_credentials()
    # Acquire TMA token with gentle retry/backoff to avoid hammering Telegram if session is temporarily unavailable
    auth_token = None  # type: str | None
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
        logger.error("Auth token was not obtained; aborting run_portals_scraper")
        return
    # Initialize DB indexes once
    await init_indexes()
    if target_mode:
        if not names:
            logger.warning("--target mode selected but no collection names/ids were provided; aborting")
            return
        await scrape_collections_by_backdrop(names, auth_token, limit=500, threshold=700)
        return

    # Default: scrape ALL collections regardless of names passed (to keep behaviour predictable)
    await smart_partition_all(auth_token, limit=500, threshold=700)


