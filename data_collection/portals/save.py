def load_existing_csv_ids(filename: str) -> set:
    ids = set()
    if not os.path.exists(filename):
        return ids
    try:
        with open(filename, "r", newline="", encoding="utf-8") as fr:
            reader = csv.DictReader(fr)
            for row in reader:
                rid = row.get("id")
                if rid:
                    ids.add(rid)
    except Exception as e:
        logger.warning(f"⚠️ Could not load existing IDs from {filename}: {e}")
    return ids
#!/usr/bin/env python3
"""
Production Adaptive Collector: Complete solution for maximizing data collection with intelligent granularity.
This is the final, production-ready version that can be integrated into the main collection process.
"""

import asyncio
import aiohttp
import json
import re
from urllib.parse import quote_plus, unquote_plus
import os
from dotenv import load_dotenv
import time
from datetime import datetime, timedelta
import logging
import random
from auth import get_portals_auth_token, get_auth_credentials
from mongo import upsert_many, nfts_collection
import csv

load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Title-Case Helper ---
def cap(text: str) -> str:
    words = re.findall(r"\w+(?:'\w+)?", text)
    for w in words:
        if w:
            text = text.replace(w, w[0].upper() + w[1:], 1)
    return text

# --- Slug/Short Name Helper ---
def to_short_name(text: str) -> str:
    """Create a slug/short name: strip spaces, apostrophes (straight & curly), and hyphens; lowercase."""
    return (
        text.replace(" ", "").replace("'", "").replace("’", "").replace("-", "").lower()
    )

# --- Collection Name Comparison Helper ---
def _names_equal(a: str | None, b: str | None) -> bool:
    """Loose equality for collection names: case-insensitive and slug-equivalent."""
    if not a or not b:
        return False
    a_str = str(a).strip()
    b_str = str(b).strip()
    if a_str.lower() == b_str.lower():
        return True
    return to_short_name(a_str) == to_short_name(b_str)


def _get_item_collection_key(item: dict):
    """Return a machine-friendly collection key from an NFT item (short_name preferred)."""
    coll = item.get("collection") or {}
    return (
        item.get("collection_short_name")
        or coll.get("short_name")
        or item.get("collectionShortName")
        or coll.get("shortName")
        or item.get("collection_id")
        or item.get("collectionId")
    )

# --- Candidate query filters and matchers ---
def _candidate_filters(collection_name: str, collection_short_name: str | None):
    """Return a list of (param_key, param_value, matcher) candidates to try."""
    name_tc = cap(collection_name)
    short = collection_short_name or to_short_name(collection_name)
    cands = [
        ("gift_name", quote_plus(name_tc), ("name", name_tc)),
        ("collections", quote_plus(short), ("short", short.lower())),
        # fallbacks
        ("collections", quote_plus(name_tc), ("name", name_tc)),
        ("gift_name", quote_plus(collection_name), ("name", collection_name)),
    ]
    return cands

def _match_ratio(items: list, matcher: tuple[str, str]):
    """Compute the fraction of items that match the intended collection by name or short key."""
    if not items:
        return 0.0
    kind, target = matcher
    if kind == "short":
        matches = [it for it in items if str(_get_item_collection_key(it)).lower() == str(target).lower()]
    else:  # "name"
        matches = [it for it in items if _names_equal(_get_item_collection_name(it), target)]
    return len(matches) / len(items)

# --- Human Name Extractor ---
def _get_item_collection_name(item: dict):
    coll = item.get("collection") or {}
    return (
        coll.get("name")
        or item.get("collection_name")
        or item.get("collectionName")
    )

# --- Robust fetch helpers for retries and backoff ---
async def _sleep_backoff(attempt: int, retry_after: float | None = None):
    """Sleep with exponential backoff and jitter. Honors Retry-After if provided."""
    if retry_after is not None:
        await asyncio.sleep(float(retry_after))
        return
    # base 0.5s * 2^attempt with jitter [0, 0.25]
    delay = 0.5 * (2 ** attempt) + random.random() * 0.25
    # cap at 10s to avoid excessive waits
    await asyncio.sleep(min(delay, 10))


async def fetch_json(session: aiohttp.ClientSession, url: str, headers: dict, *, max_retries: int = 6):
    """GET a JSON URL with retries on 429/5xx, respecting Retry-After. Returns (status, json_or_none)."""
    last_status = None
    for attempt in range(max_retries + 1):
        try:
            async with session.get(url, headers=headers) as resp:
                last_status = resp.status
                if resp.status == 200:
                    try:
                        return 200, await resp.json()
                    except Exception:
                        # Non-JSON or parse error – treat as retryable once
                        if attempt < max_retries:
                            await _sleep_backoff(attempt)
                            continue
                        return resp.status, None
                # Handle rate limiting – honor Retry-After if present
                if resp.status == 429:
                    retry_after = resp.headers.get("Retry-After")
                    await _sleep_backoff(attempt, retry_after=float(retry_after) if retry_after else None)
                    continue
                # Retry on transient server/network errors
                if resp.status in {500, 502, 503, 504}:
                    if attempt < max_retries:
                        await _sleep_backoff(attempt)
                        continue
                # For other non-200s, don't retry endlessly
                return resp.status, None
        except aiohttp.ClientError:
            if attempt < max_retries:
                await _sleep_backoff(attempt)
                continue
            return last_status or 0, None
    return last_status or 0, None


async def get_collections(limit: int = 100, authData: str = "") -> list:
    URL = API_URL_PORTALS + "/api/collections?limit=" + str(limit)
    if authData == "":
        raise Exception("portalsmp: collections(): Error: authData is required")

    headers = {
        "Authorization": f"tma {authData}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(URL, headers=headers) as response:
            if response.status != 200:
                raise Exception(
                    f"portalsmp: collections(): Error: status_code: {response.status}, response_text: {await response.text()}"
                )

            json_data = await response.json()
            return json_data.get("collections", json_data)


async def analyze_collection_price_range(collection_name: str, headers: dict, collection_short_name: str | None = None):
    """
    Analyze the price range of a collection to find min, max, and distribution.
    Tries several candidate query filters and returns the chosen query key/value and matcher.
    """
    logger.info(f"Analyzing price range for: {collection_name}")
    prices = []
    floor_prices = []

    chosen = None
    items = []
    async with aiohttp.ClientSession() as session:
        # Try multiple parameterizations until the filter clearly takes
        best = (None, None, -1.0, [])  # key, val, ratio, items
        for key, val, matcher in _candidate_filters(collection_name, collection_short_name):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset=0&limit=100&{key}={val}&status=listed"
            )
            status, data = await fetch_json(session, url, headers)
            if status != 200 or not data:
                continue
            results = data.get("results", [])
            ratio = _match_ratio(results, matcher)
            if ratio >= 0.8:
                chosen = (key, val, matcher)
                items = results
                logger.info(f"Using filter {key}={unquote_plus(val)} for '{collection_name}' (match {ratio:.0%})")
                break
            # keep best attempt to potentially use
            if ratio > best[2]:
                best = (key, val, ratio, results)

        if not chosen:
            # Use best attempt if it had any results at all
            key, val, ratio, results = best
            if results:
                logger.warning(
                    f"Filter weak for '{collection_name}' (best ratio {ratio:.0%} via {key}). Proceeding cautiously."
                )
                chosen = (key, val, ("name", cap(collection_name)))
                items = results
                logger.warning(f"Proceeding with best filter {key}={unquote_plus(val)} for '{collection_name}' (match {ratio:.0%})")
            else:
                logger.warning(f"No price data found for {collection_name}")
                return None

        # Extract prices from chosen items
        for item in items:
            try:
                prices.append(float(item.get("price", 0)))
                floor_prices.append(float(item.get("floor_price", 0)))
            except (ValueError, TypeError):
                continue

        if not prices:
            logger.warning(f"No price data found for {collection_name}")
            return None

        min_price = min(prices)
        max_price = max(prices)
        avg_price = sum(prices) / len(prices)
        if floor_prices:
            min_floor = min(floor_prices)
            max_floor = max(floor_prices)
            avg_floor = sum(floor_prices) / len(floor_prices)
        else:
            min_floor = max_floor = avg_floor = 0

        logger.info(f"Price Analysis: {min_price:.2f} - {max_price:.2f} TON (avg: {avg_price:.2f})")
        logger.info(f"Floor Analysis: {min_floor:.2f} - {max_floor:.2f} TON (avg: {avg_floor:.2f})")

        # Return range plus chosen query key/value to reuse later
        return {
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": avg_price,
            "min_floor": min_floor,
            "max_floor": max_floor,
            "avg_floor": avg_floor,
            "price_count": len(prices),
            "query_key": chosen[0],
            "query_val": chosen[1],
            "matcher": chosen[2],
        }


async def collect_items_from_range(query_key: str, query_val: str, headers: dict, min_price: float, max_price: float, seen_ids: set, matcher: tuple[str, str] | None = None):
    """
    Collect all items from a specific price range using offsets.
    'query_key' and 'query_val' param are used for collection filtering.
    """
    items = []
    offset = 0
    consecutive_repeated = 0
    max_consecutive_repeated = 3
    max_offset = 800  # Stop at 800 items per range

    async with aiohttp.ClientSession() as session:
        while offset < max_offset:
            if offset == 0:
                logger.info(f"Collecting with filter {query_key}={unquote_plus(query_val)} | window {min_price}-{max_price}")
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit=100"
                f"&{query_key}={query_val}"
                f"&status=listed"
                f"&min_price={min_price}&max_price={max_price}"
            )

            try:
                status, data = await fetch_json(session, url, headers)
                if status == 200 and data:
                    results = data.get("results", [])

                    # Sanity check: ensure API honored the collection filter for this window
                    if results and matcher:
                        ratio = _match_ratio(results, matcher)
                        logger.debug(f"Window {min_price}-{max_price} match ratio: {ratio:.0%} via {matcher[0] if matcher else 'n/a'}")
                        if ratio < 0.8:
                            logger.warning(
                                f"Collection filter ineffective for window {min_price}-{max_price} (kept {ratio:.0%})."
                            )
                            # keep only matches when possible
                            kind, target = matcher
                            if kind == "short":
                                results = [it for it in results if str(_get_item_collection_key(it)).lower() == target]
                            else:
                                results = [it for it in results if _names_equal(_get_item_collection_name(it), target)]

                    if not results:
                        break

                    # Check for new items
                    new_items = [item for item in results if item.get("id") not in seen_ids]
                    repeated_count = len(results) - len(new_items)

                    for item in new_items:
                        seen_ids.add(item.get("id"))
                    items.extend(new_items)

                    # If mostly repeats, increment guard
                    if repeated_count >= len(results) * 0.8:
                        consecutive_repeated += 1
                        if consecutive_repeated >= max_consecutive_repeated:
                            logger.info(f"Hit limit at offset {offset} for range {min_price}-{max_price}")
                            break
                    else:
                        consecutive_repeated = 0

                    if len(results) < 100:
                        break

                    offset += 100
                    await asyncio.sleep(0.15)  # slightly faster; fetch_json handles backoff on 429

                else:
                    if status == 429:
                        # fetch_json already backed off; try the same offset again
                        logger.warning(f"HTTP 429 at offset {offset} – retrying")
                        continue
                    logger.warning(f"HTTP {status} at offset {offset}")
                    break

            except Exception as e:
                logger.error(f"Error at offset {offset}: {e}")
                break

    return items


async def collect_with_production_strategy(collection_name: str, auth_token: str, initial_seen: set | None = None, collection_short_name: str | None = None):
    """
    Production-ready adaptive collection strategy.
    """
    headers = {
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
        "Authorization": f"tma {auth_token}"
    }

    logger.info(f"Starting production collection for: {collection_name}")

    all_items = []
    seen_ids = set(initial_seen) if initial_seen else set()
    base_seen_count = len(seen_ids)

    # Step 1: Analyze price range
    price_analysis = await analyze_collection_price_range(collection_name, headers, collection_short_name)

    if not price_analysis:
        logger.error(f"Could not analyze price range for {collection_name}")
        return all_items

    min_price = price_analysis["min_price"]
    max_price = price_analysis["max_price"]

    logger.info(f"Price range: {min_price:.2f} - {max_price:.2f} TON")

    # Extract chosen query key/val and matcher
    query_key = price_analysis.get("query_key")
    query_val = price_analysis.get("query_val")
    matcher = price_analysis.get("matcher")
    if not query_key or not query_val:
        logger.error(f"No valid query parameters resolved for {collection_name}")
        return all_items

    # Step 2: Test the full range first
    logger.info("Testing full price range...")
    full_range_items = await collect_items_from_range(
        query_key, query_val, headers, min_price, max_price, seen_ids, matcher
    )
    all_items.extend(full_range_items)

    logger.info(f"Full range: {len(full_range_items)} items")

    # Step 3: If we collected a lot of items, the range might be hitting limits
    # Go deeper with smaller ranges
    if len(full_range_items) >= 700:  # Threshold for going deeper
        logger.info("High item count detected - going deeper with smaller ranges...")

        # Create smaller price ranges
        price_ranges = []
        range_size = max_price - min_price

        # Calculate optimal step size based on range
        if range_size > 200:
            step = 20
        elif range_size > 100:
            step = 10
        elif range_size > 50:
            step = 5
        elif range_size > 20:
            step = 2
        elif range_size > 10:
            step = 1
        else:
            step = 0.5

        current_price = min_price
        while current_price < max_price:
            next_price = min(current_price + step, max_price)
            price_ranges.append((current_price, next_price))
            current_price = next_price

        logger.info(f"Created {len(price_ranges)} smaller ranges (step: {step} TON)")

        # Collect from each smaller range
        for i, (range_min, range_max) in enumerate(price_ranges):
            logger.info(f"Processing range {i+1}/{len(price_ranges)}: {range_min:.2f}-{range_max:.2f} TON")

            range_items = await collect_items_from_range(
                query_key, query_val, headers, range_min, range_max, seen_ids, matcher
            )
            all_items.extend(range_items)

            logger.info(f"Range {i+1}: {len(range_items)} items (Total: {len(all_items)})")

            # If this range also collected a lot, go ultra-granular
            if len(range_items) >= 700 and range_max - range_min > 2:
                logger.info(f"Range {i+1} hit high count - going ultra-granular...")

                # Create ultra-granular ranges
                ultra_step = max(0.1, (range_max - range_min) / 10)
                ultra_current = range_min

                while ultra_current < range_max:
                    ultra_next = min(ultra_current + ultra_step, range_max)

                    ultra_items = await collect_items_from_range(
                        query_key, query_val, headers, ultra_current, ultra_next, seen_ids, matcher
                    )
                    all_items.extend(ultra_items)

                    ultra_current = ultra_next
                    await asyncio.sleep(0.3)  # Ultra-fast delay

                logger.info(f"Ultra-granular complete for range {i+1}")

            await asyncio.sleep(0.25)  # Ultra-fast delay
    else:
        logger.info("Full range collection sufficient - no need for deeper granularity")

    new_count = len(seen_ids) - base_seen_count
    logger.info(f"Collection complete: {new_count} new items (unique vs global index); seen this run total: {len(seen_ids)}")
    return all_items


async def collect_multiple_collections(collections: list, auth_token: str, name_to_short: dict[str, str] | None = None):
    """
    Collect data from multiple collections using the production strategy.
    """
    results = {}

    for collection in collections:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing collection: {collection}")
        logger.info(f"{'='*60}")

        start_time = time.time()

        try:
            short = name_to_short.get(collection) if name_to_short else None
            items = await collect_with_production_strategy(collection, auth_token, collection_short_name=short)

            # Store items into MongoDB after each collection
            await upsert_many(nfts_collection, items, key="id")

            end_time = time.time()
            duration = end_time - start_time

            results[collection] = {
                "items": len(items),
                "duration": duration,
                "items_per_second": len(items)/duration if duration > 0 else 0,
                "success": True
            }

            logger.info(f"✅ {collection}: {len(items)} items in {duration:.1f}s ({len(items)/duration:.1f} items/s)")

        except Exception as e:
            logger.error(f"❌ Failed to collect {collection}: {e}")
            results[collection] = {
                "items": 0,
                "duration": 0,
                "items_per_second": 0,
                "success": False,
                "error": str(e)
            }

        # Add delay between collections
        await asyncio.sleep(0.5)  # Ultra-fast delay between collections

    return results


async def main():
    """Main function for production collection."""
    logger.info("🚀 Production Adaptive Collector")
    logger.info("=" * 60)

    logger.info("🔐 Getting authentication token...")
    api_id, api_hash = get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)

    raw_collections = await get_collections(limit=100, authData=auth_token)
    test_collections = [c["name"] for c in raw_collections if c.get("name")]
    name_to_short = {
        c["name"]: (c.get("short_name") or to_short_name(c["name"]))
        for c in raw_collections if c.get("name")
    }

    logger.info(f"📋 Processing {len(test_collections)} collections")

    # Collect from all collections
    results = await collect_multiple_collections(test_collections, auth_token, name_to_short)

    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info("📊 PRODUCTION COLLECTION SUMMARY")
    logger.info(f"{'='*60}")

    total_items = 0
    total_duration = 0
    successful_collections = 0

    for collection, result in results.items():
        items = result["items"]
        duration = result["duration"]
        success = result["success"]

        if success:
            total_items += items
            total_duration += duration
            successful_collections += 1
            logger.info(f"   ✅ {collection}: {items} items ({duration:.1f}s)")
        else:
            logger.info(f"   ❌ {collection}: Failed - {result.get('error', 'Unknown error')}")

    if total_duration > 0:
        logger.info(f"\n🏆 Total: {total_items} items in {total_duration:.1f} seconds")
        logger.info(f"📈 Average: {total_items/total_duration:.1f} items/second")
        logger.info(f"✅ Success rate: {successful_collections}/{len(test_collections)} collections")

    logger.info(f"\n💡 Production Strategy Benefits:")
    logger.info(f"   - Intelligent granularity based on collection size")
    logger.info(f"   - Only goes deeper when hitting limits")
    logger.info(f"   - Complete price range coverage")
    logger.info(f"   - Production-ready with proper error handling")
    logger.info(f"   - Efficient resource usage")


async def parse_and_update_all_collections():
    """
    Authenticate, fetch collections, collect data, and upsert all NFT items into MongoDB.
    """
    logger.info("🔐 Getting authentication token for parse_and_update_all_collections...")
    api_id, api_hash = get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)

    raw_collections = await get_collections(limit=100, authData=auth_token)
    collections = [c["name"] for c in raw_collections if c.get("name")]
    name_to_short = {
        c["name"]: (c.get("short_name") or to_short_name(c["name"]))
        for c in raw_collections if c.get("name")
    }

    logger.info(f"📋 Starting collection and update for {len(collections)} collections")

    await collect_multiple_collections(collections, auth_token, name_to_short)

    logger.info("✅ All collections parsed and updated into MongoDB.")


async def parse_and_save_to_csv():
    """
    Authenticate, fetch collections, collect data, and save all items to CSV instead of DB.
    """
    logger.info("🔐 Getting authentication token for parse_and_save_to_csv...")
    api_id, api_hash = get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)

    raw_collections = await get_collections(limit=500, authData=auth_token)
    collections = [c["name"] for c in raw_collections if c.get("name")]
    name_to_short = {
        c["name"]: (c.get("short_name") or to_short_name(c["name"]))
        for c in raw_collections if c.get("name")
    }

    logger.info(f"📋 Saving {len(collections)} collections to CSV")
    # Filter out unwanted fields from collections before writing to CSV
    filtered_collections = [
        {k: v for k, v in collection.items() if k not in {"photo_url", "is_favorite"}}
        for collection in raw_collections
    ]
    with open("collections_output.csv", "w", newline="", encoding="utf-8") as f:
        if filtered_collections:
            writer = csv.DictWriter(f, fieldnames=filtered_collections[0].keys())
            writer.writeheader()
            writer.writerows(filtered_collections)
        else:
            logger.warning("⚠️ No collections to write to CSV.")

    logger.info(f"📦 Collecting items for all collections")
    nfts_csv = "nfts_output.csv"
    global_existing_ids = load_existing_csv_ids(nfts_csv)
    if global_existing_ids:
        logger.info(f"📚 Preloaded {len(global_existing_ids)} existing IDs from CSV for incremental collection")
    all_items = []
    for collection_name in collections:
        logger.info(f"📥 Collecting from: {collection_name}")
        short = name_to_short.get(collection_name)
        items = await collect_with_production_strategy(collection_name, auth_token, initial_seen=global_existing_ids, collection_short_name=short)

        if not items:
            logger.warning(f"⚠️ No items found for {collection_name}")
            continue

        all_items.extend(items)

        if all_items:
            logger.info("💾 Writing all NFT items to nfts_output.csv...")
            # Filter out unwanted fields from each NFT dictionary before writing
            cleaned_items = [
                {k: v for k, v in item.items() if k not in {"photo_url", "status", "animation_url", "emoji_id", "has_animation"}}
                for item in all_items
            ]
            # De-duplicate by NFT id to avoid repeats from overlapping ranges/retries
            dedup_map = {}
            for row in cleaned_items:
                rid = row.get("id")
                if rid is not None:
                    dedup_map[rid] = row  # last write wins
            cleaned_items = list(dedup_map.values())
            # Use a fixed field order for NFTs to ensure consistent CSV columns
            fieldnames = [
                "id", "name", "collection_id", "external_collection_number", "price",
                "floor_price", "listed_at", "unlocks_at", "tg_id", "is_owned"
            ]

            # Log missing keys before writing
            actual_keys = {key for item in cleaned_items for key in item}
            missing_keys = [k for k in fieldnames if k not in actual_keys]
            if missing_keys:
                logger.warning(f"⚠️ Missing fields in data: {missing_keys}")

            try:
                fn = "nfts_output.csv"
                file_exists = os.path.exists(fn)
                existing_ids = set()
                # If the file exists, load existing IDs to avoid cross-run duplicates
                if file_exists:
                    try:
                        with open(fn, "r", newline="", encoding="utf-8") as fr:
                            reader = csv.DictReader(fr)
                            # Only read the id column; ignore others for speed
                            for row in reader:
                                rid = row.get("id")
                                if rid is not None and rid != "":
                                    existing_ids.add(rid)
                    except Exception as read_err:
                        logger.warning(f"⚠️ Could not read existing CSV for dedupe: {read_err}")
                        existing_ids = set()

                # Append new rows only
                new_rows = 0
                # Determine if we need to write header
                need_header = not file_exists or os.path.getsize(fn) == 0
                with open(fn, "a", newline="", encoding="utf-8") as fa:
                    writer = csv.DictWriter(fa, fieldnames=fieldnames)
                    if need_header:
                        writer.writeheader()
                    for row in cleaned_items:
                        rid = row.get("id")
                        if rid is None or rid == "":
                            continue
                        if rid in existing_ids:
                            continue
                        writer.writerow({k: row.get(k, "") for k in fieldnames})
                        existing_ids.add(rid)
                        new_rows += 1

                logger.info(f"✅ CSV appended with {new_rows} new NFTs. Total unique now ~{len(existing_ids)}.")
            except Exception as e:
                logger.error(f"❌ Failed to append to CSV: {e}")
            # Refresh global ID index after appending so subsequent collections skip sooner
            global_existing_ids = load_existing_csv_ids(fn)
        else:
            logger.warning("⚠️ No items to write to CSV.")

    logger.info("✅ All data saved to CSV.")


if __name__ == "__main__":
    #asyncio.run(parse_and_update_all_collections())
    asyncio.run(parse_and_save_to_csv())

