#!/usr/bin/env python3
"""
Production Adaptive Collector: Complete solution for maximizing data collection with intelligent granularity.
This is the final, production-ready version that can be integrated into the main collection process.
"""

import asyncio
import aiohttp
import json
from urllib.parse import quote_plus
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


async def analyze_collection_price_range(collection_name: str, headers: dict, collection_id: str | None = None):
    """
    Analyze the price range of a collection to find min, max, and distribution.
    """
    collection = quote_plus(collection_id) if collection_id else quote_plus(collection_name.strip().replace("'", "'"))

    logger.info(f"Analyzing price range for: {collection_name}")

    # Start with a broad range to find the price distribution
    url = (
        f"{API_URL_PORTALS}/api/nfts/search"
        f"?offset=0&limit=100"
        f"&collection_id={collection}"
        f"&status=listed"
    )

    prices = []
    floor_prices = []

    async with aiohttp.ClientSession() as session:
        try:
            status, data = await fetch_json(session, url, headers)
            if status == 200 and data:
                results = data.get("results", [])

                for item in results:
                    try:
                        price = float(item.get("price", 0))
                        floor_price = float(item.get("floor_price", 0))
                        prices.append(price)
                        floor_prices.append(floor_price)
                    except (ValueError, TypeError):
                        continue

                if prices:
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

                    return {
                        "min_price": min_price,
                        "max_price": max_price,
                        "avg_price": avg_price,
                        "min_floor": min_floor,
                        "max_floor": max_floor,
                        "avg_floor": avg_floor,
                        "price_count": len(prices)
                    }
                else:
                    logger.warning(f"No price data found for {collection_name}")
                    return None
            else:
                logger.error(f"HTTP {status} for {collection_name}")
                return None
        except Exception as e:
            logger.error(f"Error analyzing {collection_name}: {e}")
            return None


async def collect_items_from_range(collection: str, headers: dict, min_price: float, max_price: float, seen_ids: set, force_full_scan: bool = False):
    """
    Collect all items from a specific price range using offsets.
    Returns (items, meta) where meta contains diagnostic info about the fetch.
    """
    items = []
    offset = 0
    consecutive_repeated = 0
    max_consecutive_repeated = 5  # Increased from 3 to be more thorough
    max_offset = 800  # Keep at 800 since API sends duplicates after this point
    empty_results_count = 0
    max_empty_results = 1  # Stop after first empty page to avoid wasting calls
    duplicate_threshold = 0.95  # If 95% are duplicates, stop this range

    pages_fetched = 0
    total_results_returned = 0
    stopped_reason = "unknown"

    async with aiohttp.ClientSession() as session:
        while offset < max_offset:
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit=100"
                f"&collection_id={collection}"
                f"&status=listed"
                f"&min_price={min_price}&max_price={max_price}"
            )

            try:
                status, data = await fetch_json(session, url, headers)
                if status == 200 and data:
                    results = data.get("results", [])

                    if not results:
                        # When forcing a full scan, keep advancing offsets up to cap
                        if force_full_scan:
                            offset += 100
                            await asyncio.sleep(0.15)
                            continue
                        empty_results_count += 1
                        if empty_results_count >= max_empty_results:
                            stopped_reason = "empty_results"
                            logger.info(f"No more results after {max_empty_results} empty responses at offset {offset}")
                            break
                        # Try next offset even if current one is empty
                        offset += 100
                        await asyncio.sleep(0.15)
                        continue

                    # Reset empty results counter when we get results
                    empty_results_count = 0

                    pages_fetched += 1
                    total_results_returned += len(results)

                    # Check for new items
                    new_items = [item for item in results if item.get("id") not in seen_ids]
                    repeated_count = len(results) - len(new_items)

                    for item in new_items:
                        seen_ids.add(item.get("id"))
                    items.extend(new_items)

                    # If almost all are repeats, this range is exhausted
                    if repeated_count >= len(results) * duplicate_threshold:
                        consecutive_repeated += 1
                        if consecutive_repeated >= max_consecutive_repeated:
                            stopped_reason = "duplicates_exhausted"
                            logger.info(f"Range exhausted at offset {offset} for range {min_price}-{max_price} (duplicates: {repeated_count}/{len(results)})")
                            break
                    else:
                        consecutive_repeated = 0

                    # Only break if we get significantly fewer results than expected
                    # This allows for collections that might have gaps in the middle
                    if not force_full_scan and len(results) < 50:  # Skip this check when forcing scan
                        # Check if we've been getting consistently low results
                        if offset > 200:  # Reduced from 500 to 200 to stop earlier
                            stopped_reason = "low_results_break"
                            logger.info(f"Consistently low results ({len(results)}) at offset {offset}, stopping")
                            break
                        # Otherwise continue to see if it's just a temporary gap

                    offset += 100
                    await asyncio.sleep(0.15)  # slightly faster; fetch_json handles backoff on 429

                else:
                    if status == 429:
                        # fetch_json already backed off; try the same offset again
                        logger.warning(f"HTTP 429 at offset {offset} – retrying")
                        continue
                    stopped_reason = f"http_{status}"
                    logger.warning(f"HTTP {status} at offset {offset}")
                    break

            except Exception as e:
                stopped_reason = "exception"
                logger.error(f"Error at offset {offset}: {e}")
                break

    avg_page_size = (total_results_returned / pages_fetched) if pages_fetched > 0 else 0
    if stopped_reason == "unknown" and offset >= max_offset:
        stopped_reason = "offset_cap"
    meta = {
        "last_offset": offset,
        "pages_fetched": pages_fetched,
        "avg_page_size": avg_page_size,
        "stopped_reason": stopped_reason,
    }

    logger.info(f"Collected {len(items)} items from range {min_price}-{max_price} TON (offset reached: {offset}, pages: {pages_fetched}, avg_page: {avg_page_size:.1f}, reason: {stopped_reason})")
    return items, meta


async def scan_offsets_listed(collection_id: str, headers: dict, seen_ids: set) -> list:
    """Wide scan for listed items by offsets up to 800 without price filters."""
    items: list = []
    collection = quote_plus(collection_id)
    async with aiohttp.ClientSession() as session:
        for offset in range(0, 800, 100):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit=100&collection_id={collection}&status=listed"
            )
            status, data = await fetch_json(session, url, headers)
            if status != 200 or not data:
                break
            results = data.get("results", [])
            if not results:
                break
            new_items = [it for it in results if (it_id := it.get("id")) and it_id not in seen_ids]
            for it in new_items:
                seen_ids.add(it["id"])
            items.extend(new_items)
            if len(results) < 100:
                break
    logger.info(f"Wide scan collected {len(items)} items")
    return items


async def collect_with_production_strategy(collection_name: str, auth_token: str):
    """
    Production-ready adaptive collection strategy.
    """
    logger.info(f"Starting production collection for: {collection_name}")

    # Resolve collection UUID (id) for the given name
    raw_cols = await get_collections(limit=500, authData=auth_token)
    name_to_id = {c.get("name"): c.get("id") for c in raw_cols if c.get("name") and c.get("id")}
    coll_id = name_to_id.get(collection_name)
    all_items = []
    if not coll_id:
        logger.error(f"No collection_id (UUID) found for '{collection_name}' — skipping.")
        return all_items
    collection = quote_plus(coll_id)
    logger.info(f"Using collection_id={coll_id} for '{collection_name}'")

    headers = {
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
        "Authorization": f"tma {auth_token}"
    }

    seen_ids = set()

    # Step 1: Analyze price range
    price_analysis = await analyze_collection_price_range(collection_name, headers, collection_id=coll_id)

    if not price_analysis:
        logger.error(f"Could not analyze price range for {collection_name}")
        return all_items

    min_price = price_analysis["min_price"]
    max_price = price_analysis["max_price"]

    logger.info(f"Price range: {min_price:.2f} - {max_price:.2f} TON")

    # Simple two-phase strategy
    # Phase 1: Wide scan by offsets without price filters
    logger.info("Phase 1: Wide scan (listed only)...")
    wide_items = await scan_offsets_listed(coll_id, headers, seen_ids)
    all_items.extend(wide_items)

    # Phase 2: Proportional granular ranges (~40)
    logger.info("Phase 2: Proportional granular ranges...")
    price_ranges = []
    range_size = max_price - min_price
    target_ranges = 40
    base_step = max(range_size / target_ranges, 0.1)
    step = _nice_step(base_step)

    current_price = min_price
    while current_price < max_price:
        next_price = min(current_price + step, max_price)
        price_ranges.append((current_price, next_price))
        current_price = next_price

    logger.info(f"Created {len(price_ranges)} ranges (step: {step} TON)")

    for i, (range_min, range_max) in enumerate(price_ranges):
        logger.info(f"Processing range {i+1}/{len(price_ranges)}: {range_min:.2f}-{range_max:.2f} TON")
        range_items, _ = await collect_items_from_range(
            collection, headers, range_min, range_max, seen_ids, force_full_scan=False
        )
        all_items.extend(range_items)
        logger.info(f"Range {i+1}: {len(range_items)} items (Total: {len(all_items)})")
        await asyncio.sleep(0.15)

    logger.info(f"Collection strategies complete: {len(all_items)} total items found")
    
    # Final deduplication to ensure we have unique items
    unique_items = []
    seen_final = set()
    for item in all_items:
        item_id = item.get("id")
        if item_id and item_id not in seen_final:
            seen_final.add(item_id)
            unique_items.append(item)
    
    logger.info(f"Collection complete: {len(unique_items)} unique items (raw total: {len(all_items)})")
    
    # Step 4: Try alternative collection approaches to find more items
    if len(unique_items) < 500:  # If we didn't get many items, try alternative approaches
        logger.info("Low item count - trying alternative collection approaches...")
        additional_items = await collect_items_with_different_approaches(collection, headers, seen_final)
        
        # Final deduplication including additional items
        final_items = []
        final_seen = set()
        
        for item in unique_items + additional_items:
            item_id = item.get("id")
            if item_id and item_id not in final_seen:
                final_seen.add(item_id)
                final_items.append(item)
        
        logger.info(f"Final collection with alternative approaches: {len(final_items)} unique items")
        return final_items
    
    return unique_items


async def collect_items_with_different_approaches(collection: str, headers: dict, seen_ids: set):
    """
    Try different collection approaches to find items that might be missed by price-based collection.
    """
    additional_items = []
    
    # Approach 1: Try without price filters to get all listed items
    logger.info("Trying collection without price filters...")
    try:
        url = (
            f"{API_URL_PORTALS}/api/nfts/search"
            f"?offset=0&limit=100"
            f"&collection_id={collection}"
            f"&status=listed"
        )
        
        async with aiohttp.ClientSession() as session:
            status, data = await fetch_json(session, url, headers)
            if status == 200 and data:
                results = data.get("results", [])
                new_items = [item for item in results if item.get("id") not in seen_ids]
                
                for item in new_items:
                    seen_ids.add(item.get("id"))
                additional_items.extend(new_items)
                
                logger.info(f"Found {len(new_items)} additional items without price filters")
                
                # If we found items, try to get more with offsets
                if new_items:
                    offset = 100
                    while offset < 800:  # Stay within the 800 limit
                        url = (
                            f"{API_URL_PORTALS}/api/nfts/search"
                            f"?offset={offset}&limit=100"
                            f"&collection_id={collection}"
                            f"&status=listed"
                        )
                        
                        status, data = await fetch_json(session, url, headers)
                        if status == 200 and data:
                            results = data.get("results", [])
                            if not results:
                                break
                                
                            new_items = [item for item in results if item.get("id") not in seen_ids]
                            
                            # If mostly duplicates, stop
                            if len(new_items) < len(results) * 0.1:  # Less than 10% new items
                                logger.info(f"Stopping at offset {offset} due to high duplicates")
                                break
                                
                            for item in new_items:
                                seen_ids.add(item.get("id"))
                            additional_items.extend(new_items)
                            
                            offset += 100
                            await asyncio.sleep(0.15)
                        else:
                            break
    except Exception as e:
        logger.warning(f"Error in price-filter-free collection: {e}")
    
    logger.info(f"Total additional items found with different approaches: {len(additional_items)}")
    return additional_items





async def collect_multiple_collections(collections: list, auth_token: str):
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
            items = await collect_with_production_strategy(collection, auth_token)

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
    test_collections = [c["name"] for c in raw_collections if "name" in c]

    logger.info(f"📋 Processing {len(test_collections)} collections")

    # Collect from all collections
    results = await collect_multiple_collections(test_collections, auth_token)

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
    collections = [c["name"] for c in raw_collections if "name" in c]

    logger.info(f"📋 Starting collection and update for {len(collections)} collections")

    await collect_multiple_collections(collections, auth_token)

    logger.info("✅ All collections parsed and updated into MongoDB.")


async def parse_and_save_to_csv():
    """
    Authenticate, fetch collections, collect data, and save all items to CSV instead of DB.
    """
    logger.info("🔐 Getting authentication token for parse_and_save_to_csv...")
    api_id, api_hash = get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)

    raw_collections = await get_collections(limit=500, authData=auth_token)
    collections = [c["name"] for c in raw_collections if "name" in c]

    logger.info(f"📋 Saving {len(collections)} collections to CSV")
    # Filter out unwanted fields from collections before writing to CSV
    filtered_collections = [
        {k: v for k, v in collection.items() if k not in {"short_name", "photo_url", "is_favorite"}}
        for collection in raw_collections
    ]
    with open("../data_collection/portals/collections_output.csv", "w", newline="", encoding="utf-8") as f:
        if filtered_collections:
            writer = csv.DictWriter(f, fieldnames=filtered_collections[0].keys())
            writer.writeheader()
            writer.writerows(filtered_collections)
        else:
            logger.warning("⚠️ No collections to write to CSV.")

    logger.info(f"📦 Collecting items for all collections")
    all_items = []
    for collection_name in collections:
        logger.info(f"📥 Collecting from: {collection_name}")
        items = await collect_with_production_strategy(collection_name, auth_token)

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
                    skipped_missing_id = 0
                    skipped_duplicates = 0
                    for row in cleaned_items:
                        rid = row.get("id")
                        if rid is None or rid == "":
                            skipped_missing_id += 1
                            continue
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
            except Exception as e:
                logger.error(f"❌ Failed to append to CSV: {e}")
        else:
            logger.warning("⚠️ No items to write to CSV.")

    logger.info("✅ All data saved to CSV.")


# Helper to choose a "nice" step close to a target value
def _nice_step(target_step: float) -> float:
    """Return a human-friendly step size >= target_step."""
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


if __name__ == "__main__":
    #asyncio.run(parse_and_update_all_collections())
    asyncio.run(parse_and_save_to_csv())

