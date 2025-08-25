import asyncio
import aiohttp
import os
import logging
from urllib.parse import quote_plus
from dotenv import load_dotenv
from typing import Tuple, List, Dict, Set, Callable, Any, Optional
import random
import csv

from data_collection.auth import get_portals_auth_token, get_auth_credentials
from mongo import (
    init_indexes,
    upsert_collections_and_build_map,
    upsert_nfts_for_collection,
    reset_market_state_for_collection,
    upsert_nfts_for_collection_bulk,
)
from backdrops_fetcher import fetch_backdrops as get_all_backdrops

load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
OFFSET_STEP = 50
PAGE_LIMIT = 50


async def _sleep_backoff(attempt: int, retry_after: float | None = None):
    """Sleep with exponential backoff and jitter. Honors Retry-After if provided."""
    if retry_after is not None:
        await asyncio.sleep(float(retry_after))
        return
    delay = 0.2 * (2 ** attempt) + random.random() * 0.1
    await asyncio.sleep(min(delay, 1))


async def fetch_json(session: aiohttp.ClientSession, url: str, headers: dict, *, max_retries: int = 6) -> Tuple[int, dict | None]:
    last_status = None
    for attempt in range(max_retries + 1):
        try:
            async with session.get(url, headers=headers) as resp:
                last_status = resp.status
                if resp.status == 200:
                    try:
                        return 200, await resp.json()
                    except Exception:
                        if attempt < max_retries:
                            await _sleep_backoff(attempt)
                            continue
                        return resp.status, None
                if resp.status == 429:
                    retry_after = resp.headers.get("Retry-After")
                    await _sleep_backoff(attempt, retry_after=float(retry_after) if retry_after else None)
                    continue
                if resp.status in {500, 502, 503, 504}:
                    if attempt < max_retries:
                        await _sleep_backoff(attempt)
                        continue
                return resp.status, None
        except aiohttp.ClientError:
            if attempt < max_retries:
                await _sleep_backoff(attempt)
                continue
            return last_status or 0, None
    return last_status or 0, None


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
                await asyncio.sleep(0.05)
                continue
            results = data.get("results", [])
            if not results:
                await asyncio.sleep(0.05)
                continue
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            for it in new_items:
                seen_ids.add(it["id"])
            items.extend(new_items)
            await asyncio.sleep(0.05)
    logger.info(f"Wide scan collected {len(items)} items")
    return items


async def scan_offsets_with_backdrops(collection_id: str, headers: dict, backdrops: List[str], seen_ids: Set[str]) -> List[Dict]:
    """
    For a given collection, iterate every backdrop and scan offsets 0..750 (limit=50)
    using the filter_by_backdrops parameter to bypass the 800-items cap per query.
    """
    if not backdrops:
        logger.info("No global backdrops provided; falling back to offset-only scan")
        return await scan_offsets(collection_id, headers, seen_ids)

    items: List[Dict] = []
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        for backdrop in backdrops:
            if not backdrop:
                continue
            q_backdrop = quote_plus(backdrop)
            # Probe first page for this backdrop; if empty, skip heavy loop
            probe_url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset=0&limit={PAGE_LIMIT}&collection_id={collection}&status=listed"
                f"&filter_by_backdrops={q_backdrop}"
            )
            status, data = await fetch_json(session, probe_url, headers)
            if status != 200 or not data or not data.get("results"):
                await asyncio.sleep(0.02)
                continue

            for offset in range(0, 800, OFFSET_STEP):
                url = (
                    f"{API_URL_PORTALS}/api/nfts/search"
                    f"?offset={offset}&limit={PAGE_LIMIT}&collection_id={collection}&status=listed"
                    f"&filter_by_backdrops={q_backdrop}"
                )
                s2, d2 = await fetch_json(session, url, headers)
                if s2 != 200 or not d2:
                    await asyncio.sleep(0.05)
                    continue
                results = d2.get("results", [])
                if not results:
                    await asyncio.sleep(0.05)
                    continue
                new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
                for it in new_items:
                    seen_ids.add(it["id"])
                items.extend(new_items)
                await asyncio.sleep(0.05)
    logger.info(f"Backdrop-partitioned scan collected {len(items)} items for collection {collection_id}")
    return items


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


# --- Offset-only execution over all collections ---
async def offset_only_all(auth_token: str, limit: int = 500, *, fast_db: bool = False, no_reset: bool = False) -> None:
    logger.info("🔐 Fetching collections list for offset-only strategy...")
    cols = await get_collections(limit, auth_token)
    if not cols:
        logger.warning("No collections received; aborting")
        return
    # Ensure collections exist in DB and build id -> uid map for anchor market
    id_to_uid = await upsert_collections_and_build_map(cols, market="portals")
    write_collections_csv(cols, filename="collections_output.csv")

    # Prefetch global backdrops ONCE using the same auth token
    hdrs_global = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
    try:
        global_backdrops = await get_all_backdrops(auth_token)
        logger.info(f"Global backdrops loaded once: {len(global_backdrops)}")
    except Exception as e:
        logger.warning(f"Failed to load global backdrops, will fallback to offset-only: {e}")
        global_backdrops = []

    names = [c.get("name") for c in cols if c.get("name")]

    logger.info(f"📋 Processing {len(names)} collections (offset-only)")

    seen_ids_global: Set[str] = set()

    # Iterate all collections and gather NFTs using backdrop-filtered offset scan
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
            items = await scan_offsets_with_backdrops(coll_id, headers, global_backdrops, seen_ids_global)
            # Anchor reset for this collection+market before rewriting state
            collection_uid = id_to_uid.get(str(coll_id))
            if collection_uid:
                if not no_reset:
                    await reset_market_state_for_collection(collection_uid, market="portals")
                if fast_db:
                    count = await upsert_nfts_for_collection_bulk(items, collection_uid, market="portals", batch_size=750)
                    logger.info(f"⚡ Bulk upserted ~{count} docs for {name}")
                else:
                    await upsert_nfts_for_collection(items, collection_uid, market="portals")
        except Exception as e:
            logger.warning(f"Failed '{name}': {e}")
        await asyncio.sleep(0.05)
    # Optional: write last run items to CSV is disabled for DB anchor path
    # append_nfts_csv(all_items, filename="nfts_output.csv")



# Unified programmatic runner and convenience wrappers
async def run_portals_scraper_with_options(names: Optional[List[str]] = None, *, fast_db: bool = False, no_reset: bool = False):
    """
    Programmatic entrypoint: run the scraper with explicit options.
    - names=None  -> all collections
    - names=list  -> only these collection names
    - fast_db     -> use bulk batched upserts
    - no_reset    -> skip reset
    """
    api_id, api_hash = await get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)
    await init_indexes()

    if names:
        # Names-mode: process only selected collections
        cols = await get_collections(500, auth_token)
        if not cols:
            logger.warning("No collections received; aborting (names mode)")
            return
        id_to_uid = await upsert_collections_and_build_map(cols, market="portals")
        name_to_id = {c.get("name"): c.get("id") for c in cols if c.get("name") and c.get("id")}
        headers = {
            "Authorization": f"tma {auth_token}",
            "User-Agent": "TelegramBot",
            "Accept": "application/json",
        }
        # Prefetch global backdrops once for names-mode
        try:
            global_backdrops = await get_all_backdrops(auth_token)
            logger.info(f"Global backdrops loaded once (names-mode): {len(global_backdrops)}")
        except Exception as e:
            logger.warning(f"Failed to load global backdrops in names-mode: {e}")
            global_backdrops = []

        seen_ids: Set[str] = set()
        def get_save_fn(fast_db: bool = False, no_reset: bool = False):
            async def save(name, collection_uid, items):
                if not no_reset:
                    await reset_market_state_for_collection(collection_uid, market="portals")
                if fast_db:
                    count = await upsert_nfts_for_collection_bulk(items, collection_uid, market="portals", batch_size=750)
                    logger.info(f"⚡ Bulk upserted ~{count} docs for {name}")
                else:
                    await upsert_nfts_for_collection(items, collection_uid, market="portals")
            return save
        save_fn = get_save_fn(fast_db=fast_db, no_reset=no_reset)
        for name in names:
            coll_id = name_to_id.get(name)
            if not coll_id:
                logger.warning(f"No id for '{name}', skipping")
                continue
            items = await scan_offsets_with_backdrops(coll_id, headers, global_backdrops, seen_ids)
            collection_uid = id_to_uid.get(str(coll_id))
            if collection_uid:
                await save_fn(name, collection_uid, items)
            await asyncio.sleep(0.05)
        write_collections_csv(cols, filename="collections_output.csv")
        return

    # All collections mode
    await offset_only_all(auth_token, fast_db=fast_db, no_reset=no_reset)

# Convenience wrappers you can call directly (no CLI flags needed)
async def run_all_standard():
    return await run_portals_scraper_with_options(None, fast_db=False, no_reset=False)

async def run_all_standard_no_reset():
    return await run_portals_scraper_with_options(None, fast_db=False, no_reset=True)

async def run_all_bulk():
    return await run_portals_scraper_with_options(None, fast_db=True, no_reset=False)

async def run_all_bulk_no_reset():
    return await run_portals_scraper_with_options(None, fast_db=True, no_reset=True)

async def run_names_standard(names: List[str]):
    return await run_portals_scraper_with_options(names, fast_db=False, no_reset=False)

async def run_names_standard_no_reset(names: List[str]):
    return await run_portals_scraper_with_options(names, fast_db=False, no_reset=True)

async def run_names_bulk(names: List[str]):
    return await run_portals_scraper_with_options(names, fast_db=True, no_reset=False)

async def run_names_bulk_no_reset(names: List[str]):
    return await run_portals_scraper_with_options(names, fast_db=True, no_reset=True)


async def run_portals_scraper():
    import sys
    args = sys.argv[1:]
    names = [a for a in args if not a.startswith("--")]
    fast_db = ("--fast-db" in args)
    no_reset = ("--no-reset" in args)
    names_or_none: Optional[List[str]] = names if names else None
    await run_portals_scraper_with_options(names_or_none, fast_db=fast_db, no_reset=no_reset)

if __name__ == "__main__":
    asyncio.run(run_all_bulk())
