import asyncio
import aiohttp
import os
import logging
from urllib.parse import quote_plus
from dotenv import load_dotenv
from typing import Tuple, List, Dict, Set
import random
import csv

from auth import get_portals_auth_token, get_auth_credentials


load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def _sleep_backoff(attempt: int, retry_after: float | None = None):
    """Sleep with exponential backoff and jitter. Honors Retry-After if provided."""
    if retry_after is not None:
        await asyncio.sleep(float(retry_after))
        return
    delay = 0.5 * (2 ** attempt) + random.random() * 0.25
    await asyncio.sleep(min(delay, 8))


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


OFFSET_STEP = 50
PAGE_LIMIT = 50


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
                await asyncio.sleep(0.15)
                continue
            results = data.get("results", [])
            if not results:
                await asyncio.sleep(0.15)
                continue
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            for it in new_items:
                seen_ids.add(it["id"])
            items.extend(new_items)
            await asyncio.sleep(0.15)
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
                await asyncio.sleep(0.15)
                continue
            results = data.get("results", [])
            if not results:
                await asyncio.sleep(0.15)
                continue
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            for it in new_items:
                seen_ids.add(it["id"])
            items.extend(new_items)
            await asyncio.sleep(0.15)
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
                    await asyncio.sleep(0.15)
                    continue
                results = d2.get("results", [])
                if not results:
                    await asyncio.sleep(0.15)
                    continue
                new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
                for it in new_items:
                    seen_ids.add(it["id"])
                items.extend(new_items)
                await asyncio.sleep(0.15)
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


# --- Offset-only execution over all collections ---
async def offset_only_all(auth_token: str, limit: int = 500) -> None:
    logger.info("🔐 Fetching collections list for offset-only strategy...")
    cols = await get_collections(limit, auth_token)
    if not cols:
        logger.warning("No collections received; aborting")
        return
    write_collections_csv(cols, filename="collections_output.csv")

    names = [c.get("name") for c in cols if c.get("name")]
    logger.info(f"📋 Processing {len(names)} collections (offset-only)")

    seen_ids_global: Set[str] = set()
    all_items: List[Dict] = []

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
            all_items.extend(items)
        except Exception as e:
            logger.warning(f"Failed '{name}': {e}")
        await asyncio.sleep(0.15)

    # Write all collected NFTs to CSV
    append_nfts_csv(all_items, filename="nfts_output.csv")


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


async def main():
    import sys
    names = sys.argv[1:]
    api_id, api_hash = get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)
    if names:
        # If names provided, run offset-only for those
        cols = await get_collections(500, auth_token)
        name_to_id = {c.get("name"): c.get("id") for c in cols if c.get("name") and c.get("id")}
        headers = {
            "Authorization": f"tma {auth_token}",
            "User-Agent": "TelegramBot",
            "Accept": "application/json",
        }
        seen_ids: Set[str] = set()
        all_items: List[Dict] = []
        for name in names:
            coll_id = name_to_id.get(name)
            if not coll_id:
                logger.warning(f"No id for '{name}', skipping")
                continue
            items = await scan_offsets(coll_id, headers, seen_ids)
            all_items.extend(items)
        # Write outputs
        write_collections_csv(cols, filename="collections_output.csv")
        append_nfts_csv(all_items, filename="nfts_output.csv")
    else:
        # Process all collections
        await offset_only_all(auth_token)


if __name__ == "__main__":
    asyncio.run(main())


