#!/usr/bin/env python3
"""
Test script to diagnose and test Portals API pagination issues.
This script helps identify where pagination stops and why.
"""

import asyncio
import aiohttp
import json
from urllib.parse import quote_plus
import os
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName, InputUser
from pyrogram.raw.functions.users import GetUsers

load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE")
TWO_FA_PASSWORD = os.environ.get("TELEGRAM_PASSWORD")


async def get_portals_auth_token(api_id: int, api_hash: str) -> str:
    """Get authentication token for Portals API."""
    async with Client("giftalyzerauth", api_id=api_id, api_hash=api_hash, 
                     phone_number=PHONE_NUMBER, password=TWO_FA_PASSWORD) as client:
        peer = await client.resolve_peer("portals")
        user_full = await client.invoke(GetUsers(id=[peer]))
        bot_raw = user_full[0]
        bot = InputUser(user_id=bot_raw.id, access_hash=bot_raw.access_hash)
        bot_app = InputBotAppShortName(bot_id=bot, short_name="market")
        web_view = await client.invoke(
            RequestAppWebView(
                peer=peer,
                app=bot_app,
                platform="desktop",
            )
        )
        initData = web_view.url.split('tgWebAppData=', 1)[1].split('&tgWebAppVersion', 1)[0]
        return initData


async def test_pagination_for_collection(collection_name: str, auth_token: str, max_offset: int = 2000):
    """
    Test pagination for a specific collection to identify where it stops.
    
    Args:
        collection_name (str): Name of the collection to test
        auth_token (str): Authentication token
        max_offset (int): Maximum offset to test up to
    """
    collection = quote_plus(collection_name.strip().replace("'", "'"))
    limit = 100
    
    headers = {
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
        "Authorization": f"tma {auth_token}"
    }
    
    results = []
    seen_ids = set()
    consecutive_empty = 0
    consecutive_repeated = 0
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for offset in range(0, max_offset, limit):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={limit}"
                f"&collections={collection}"
                f"&status=listed"
            )
            
            print(f"\n🔍 Testing offset {offset}...")
            
            try:
                async with session.get(url) as resp:
                    print(f"   Status: {resp.status}")
                    
                    if resp.status != 200:
                        print(f"   ❌ Failed with status {resp.status}")
                        break
                    
                    data = await resp.json()
                    items = data.get("results", [])
                    
                    if not items:
                        consecutive_empty += 1
                        print(f"   📭 Empty page (consecutive: {consecutive_empty})")
                        if consecutive_empty >= 3:
                            print(f"   🛑 Stopping after 3 consecutive empty pages")
                            break
                        continue
                    else:
                        consecutive_empty = 0
                    
                    # Check for new items
                    new_items = [item for item in items if item["id"] not in seen_ids]
                    repeated_count = len(items) - len(new_items)
                    
                    if repeated_count == len(items):
                        consecutive_repeated += 1
                        print(f"   🔄 All items repeated (consecutive: {consecutive_repeated})")
                        if consecutive_repeated >= 5:
                            print(f"   🛑 Stopping after 5 consecutive repeated pages")
                            break
                    else:
                        consecutive_repeated = 0
                    
                    # Add new items
                    for item in new_items:
                        seen_ids.add(item["id"])
                    results.extend(new_items)
                    
                    print(f"   ✅ Page items: {len(items)}, New items: {len(new_items)}, Total: {len(results)}")
                    
                    # Check if we've reached the end
                    if len(items) < limit:
                        print(f"   🎯 Reached end of results (items < limit)")
                        break
                    
                    # Add delay to avoid rate limiting
                    await asyncio.sleep(1.0)
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
                break
    
    print(f"\n📊 Final Results for {collection_name}:")
    print(f"   Total unique items: {len(results)}")
    print(f"   Last offset tested: {offset}")
    print(f"   Stopped due to: {'empty pages' if consecutive_empty >= 3 else 'repeated pages' if consecutive_repeated >= 5 else 'end of results' if len(items) < limit else 'error'}")
    
    return results


async def test_multiple_collections():
    """Test pagination for multiple collections to identify patterns."""
    print("🔐 Getting authentication token...")
    api_id = int(os.environ.get("API_ID"))
    api_hash = os.environ.get("API_HASH")
    auth_token = await get_portals_auth_token(api_id, api_hash)
    
    # Test with a few different collections
    test_collections = [
        "Plush Pepes",
        "Telegram Stickers",
        "Telegram Premium"
    ]
    
    results_summary = {}
    
    for collection in test_collections:
        print(f"\n{'='*60}")
        print(f"Testing collection: {collection}")
        print(f"{'='*60}")
        
        try:
            items = await test_pagination_for_collection(collection, auth_token)
            results_summary[collection] = {
                "total_items": len(items),
                "success": True
            }
        except Exception as e:
            print(f"❌ Failed to test {collection}: {e}")
            results_summary[collection] = {
                "total_items": 0,
                "success": False,
                "error": str(e)
            }
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for collection, result in results_summary.items():
        if result["success"]:
            print(f"✅ {collection}: {result['total_items']} items")
        else:
            print(f"❌ {collection}: Failed - {result.get('error', 'Unknown error')}")


async def test_specific_offset_range(collection_name: str, auth_token: str, start_offset: int = 700, end_offset: int = 900):
    """
    Test a specific range of offsets to identify the exact point where pagination fails.
    
    Args:
        collection_name (str): Name of the collection to test
        auth_token (str): Authentication token
        start_offset (int): Starting offset to test
        end_offset (int): Ending offset to test
    """
    collection = quote_plus(collection_name.strip().replace("'", "'"))
    limit = 100
    
    headers = {
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
        "Authorization": f"tma {auth_token}"
    }
    
    print(f"\n🔍 Testing offset range {start_offset}-{end_offset} for {collection_name}")
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for offset in range(start_offset, end_offset + limit, limit):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={limit}"
                f"&collections={collection}"
                f"&status=listed"
            )
            
            print(f"\nTesting offset {offset}...")
            
            try:
                async with session.get(url) as resp:
                    print(f"   Status: {resp.status}")
                    print(f"   URL: {url}")
                    
                    if resp.status != 200:
                        print(f"   ❌ Failed with status {resp.status}")
                        response_text = await resp.text()
                        print(f"   Response: {response_text[:200]}...")
                        break
                    
                    data = await resp.json()
                    items = data.get("results", [])
                    
                    print(f"   Items returned: {len(items)}")
                    if items:
                        print(f"   First item ID: {items[0].get('id', 'N/A')}")
                        print(f"   Last item ID: {items[-1].get('id', 'N/A')}")
                    
                    await asyncio.sleep(1.0)
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
                break


if __name__ == "__main__":
    print("🚀 Starting Portals API pagination test...")
    asyncio.run(test_multiple_collections())
