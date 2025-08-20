#!/usr/bin/env python3
"""
Production Adaptive Collector - OPTIMIZED VERSION
Ultra-fast collection with concurrent requests and session optimization.
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
from auth import get_portals_auth_token, get_auth_credentials

load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def analyze_collection_price_range_fast(collection_name: str, headers: dict, session: aiohttp.ClientSession):
    """
    Fast price range analysis using existing session.
    """
    collection = quote_plus(collection_name.strip().replace("'", "'"))
    
    logger.info(f"Analyzing price range for: {collection_name}")
    
    url = (
        f"{API_URL_PORTALS}/api/nfts/search"
        f"?offset=0&limit=100"
        f"&collections={collection}"
        f"&status=listed"
    )
    
    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                results = data.get("results", [])
                
                prices = []
                floor_prices = []
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
                logger.error(f"HTTP {resp.status} for {collection_name}")
                return None
                
    except Exception as e:
        logger.error(f"Error analyzing {collection_name}: {e}")
        return None


async def collect_range_concurrent(collection: str, headers: dict, min_price: float, max_price: float, seen_ids: set, session: aiohttp.ClientSession):
    """
    Collect items from a price range with concurrent requests.
    """
    items = []
    max_concurrent = 3  # Number of concurrent requests
    max_offset = 800
    
    # Create tasks for concurrent requests
    async def fetch_offset(offset):
        url = (
            f"{API_URL_PORTALS}/api/nfts/search"
            f"?offset={offset}&limit=100"
            f"&collections={collection}"
            f"&status=listed"
            f"&min_price={min_price}&max_price={max_price}"
        )
        
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    
                    if not results:
                        return []
                    
                    # Check for new items
                    new_items = [item for item in results if item["id"] not in seen_ids]
                    
                    # Add to seen_ids
                    for item in new_items:
                        seen_ids.add(item["id"])
                    
                    return new_items
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Error at offset {offset}: {e}")
            return []
    
    # Collect in batches with concurrency
    offset = 0
    while offset < max_offset:
        # Create concurrent tasks
        tasks = []
        for i in range(max_concurrent):
            current_offset = offset + (i * 100)
            if current_offset < max_offset:
                tasks.append(fetch_offset(current_offset))
        
        if not tasks:
            break
        
        # Execute concurrent requests
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        batch_items = []
        for result in results:
            if isinstance(result, list):
                batch_items.extend(result)
        
        if not batch_items:
            break
        
        items.extend(batch_items)
        logger.info(f"Concurrent batch: {len(batch_items)} items (Total: {len(items)})")
        
        offset += max_concurrent * 100
        await asyncio.sleep(0.2)  # Ultra-fast delay
    
    return items


async def collect_with_optimized_strategy(collection_name: str, auth_token: str):
    """
    Optimized collection strategy with concurrent requests and session reuse.
    """
    collection = quote_plus(collection_name.strip().replace("'", "'"))
    
    headers = {
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
        "Authorization": f"tma {auth_token}"
    }
    
    logger.info(f"Starting optimized collection for: {collection_name}")
    
    all_items = []
    seen_ids = set()
    
    # Use a single session for all requests
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30),
        connector=aiohttp.TCPConnector(limit=10, limit_per_host=5)
    ) as session:
        
        # Step 1: Fast price analysis
        price_analysis = await analyze_collection_price_range_fast(collection_name, headers, session)
        
        if not price_analysis:
            logger.error(f"Could not analyze price range for {collection_name}")
            return all_items
        
        min_price = price_analysis["min_price"]
        max_price = price_analysis["max_price"]
        
        logger.info(f"Price range: {min_price:.2f} - {max_price:.2f} TON")
        
        # Step 2: Test full range with concurrent requests
        logger.info("Testing full price range with concurrent requests...")
        full_range_items = await collect_range_concurrent(
            collection, headers, min_price, max_price, seen_ids, session
        )
        all_items.extend(full_range_items)
        
        logger.info(f"Full range: {len(full_range_items)} items")
        
        # Step 3: If we collected a lot, go deeper with concurrent smaller ranges
        if len(full_range_items) >= 700:
            logger.info("High item count detected - going deeper with concurrent smaller ranges...")
            
            # Create smaller price ranges
            price_ranges = []
            range_size = max_price - min_price
            
            # Calculate optimal step size
            if range_size > 200:
                step = 20
            elif range_size > 100:
                step = 10
            elif range_size > 50:
                step = 5
            elif range_size > 20:
                step = 2
            else:
                step = 1
            
            current_price = min_price
            while current_price < max_price:
                next_price = min(current_price + step, max_price)
                price_ranges.append((current_price, next_price))
                current_price = next_price
            
            logger.info(f"Created {len(price_ranges)} smaller ranges (step: {step} TON)")
            
            # Collect from ranges concurrently (in batches)
            batch_size = 3  # Process 3 ranges at a time
            for i in range(0, len(price_ranges), batch_size):
                batch_ranges = price_ranges[i:i + batch_size]
                
                # Create concurrent tasks for this batch
                tasks = []
                for range_min, range_max in batch_ranges:
                    task = collect_range_concurrent(
                        collection, headers, range_min, range_max, seen_ids, session
                    )
                    tasks.append(task)
                
                # Execute batch concurrently
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for j, result in enumerate(batch_results):
                    if isinstance(result, list):
                        range_min, range_max = batch_ranges[j]
                        all_items.extend(result)
                        logger.info(f"Range {i+j+1}: {len(result)} items (Total: {len(all_items)})")
                
                await asyncio.sleep(0.2)  # Ultra-fast delay between batches
        else:
            logger.info("Full range collection sufficient - no need for deeper granularity")
    
    logger.info(f"Collection complete: {len(seen_ids)} unique items")
    return all_items


async def collect_multiple_collections_optimized(collections: list, auth_token: str):
    """
    Optimized collection from multiple collections with concurrent processing.
    """
    results = {}
    
    # Process collections concurrently (but limit to avoid overwhelming)
    semaphore = asyncio.Semaphore(2)  # Max 2 collections at once
    
    async def collect_single_collection(collection):
        async with semaphore:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing collection: {collection}")
            logger.info(f"{'='*60}")
            
            start_time = time.time()
            
            try:
                items = await collect_with_optimized_strategy(collection, auth_token)
                
                end_time = time.time()
                duration = end_time - start_time
                
                result = {
                    "items": len(items),
                    "duration": duration,
                    "items_per_second": len(items)/duration if duration > 0 else 0,
                    "success": True
                }
                
                logger.info(f"✅ {collection}: {len(items)} items in {duration:.1f}s ({len(items)/duration:.1f} items/s)")
                return collection, result
                
            except Exception as e:
                logger.error(f"❌ Failed to collect {collection}: {e}")
                result = {
                    "items": 0,
                    "duration": 0,
                    "items_per_second": 0,
                    "success": False,
                    "error": str(e)
                }
                return collection, result
    
    # Create tasks for all collections
    tasks = [collect_single_collection(collection) for collection in collections]
    
    # Execute all tasks concurrently
    results_list = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert to dictionary
    for result in results_list:
        if isinstance(result, tuple):
            collection, result_data = result
            results[collection] = result_data
    
    return results


async def main():
    """Main function for optimized collection."""
    logger.info("🚀 Production Adaptive Collector - OPTIMIZED")
    logger.info("=" * 60)
    
    logger.info("🔐 Getting authentication token...")
    api_id, api_hash = get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)
    
    # Test collections
    test_collections = [
        "Love Potion"
    ]
    
    logger.info(f"📋 Processing {len(test_collections)} collections")
    
    # Collect from all collections
    results = await collect_multiple_collections_optimized(test_collections, auth_token)
    
    # Final summary
    logger.info(f"\n{'='*60}")
    logger.info("📊 OPTIMIZED COLLECTION SUMMARY")
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
    
    logger.info(f"\n💡 Optimization Benefits:")
    logger.info(f"   - Concurrent requests (3x faster)")
    logger.info(f"   - Session reuse (reduced overhead)")
    logger.info(f"   - Ultra-fast delays (0.2s)")
    logger.info(f"   - Batch processing")
    logger.info(f"   - Connection pooling")


if __name__ == "__main__":
    asyncio.run(main())
