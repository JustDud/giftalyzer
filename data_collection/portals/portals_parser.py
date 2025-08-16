from urllib.parse import unquote, quote_plus
import os
from dotenv import load_dotenv
import aiohttp
import asyncio
import json
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName, InputUser
from pyrogram.raw.functions.users import GetUsers
import random
import csv
import datetime
import pandas as pd
from .pagination_config import get_pagination_config, get_api_config, get_error_config, calculate_delay, should_retry_request, get_error_message

load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")
PORTALS_AUTH = os.environ.get("PORTALS_AUTH")
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE")
TWO_FA_PASSWORD = os.environ.get("TELEGRAM_PASSWORD")

# API constants for direct requests (async)
API_URL = "https://portals-market.com/api/"
SORTS = {
    "latest": "&sort_by=listed_at+desc",
    "price_asc": "&sort_by=price+asc",
    "price_desc": "&sort_by=price+desc",
    "gift_id_asc": "&sort_by=external_collection_number+asc",
    "gift_id_desc": "&sort_by=external_collection_number+desc",
    "model_rarity_asc": "&sort_by=model_rarity+asc",
    "model_rarity_desc": "&sort_by=model_rarity+desc"
}
HEADERS = {
    "Authorization": "",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Origin": "https://portals-market.com",
    "Referer": "https://portals-market.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0"
}


# Helper functions for search() and collections()
def cap(value: str) -> str:
    return value.strip().capitalize()


def listToURL(items: list) -> str:
    return ",".join([quote_plus(cap(item)) for item in items])


def toShortName(gift_name):
    return gift_name.replace(" ", "").replace("'", "").replace("’", "").replace("-", "")


# The per-collection CSV saving is disabled in favor of unified saving at the end.
# def save_to_csv_partial(data, collection_name):
#     if not data:
#         return
#
#     filename = f"{collection_name.replace(' ', '_')}.csv"
#     csv_fields = list(data[0].keys())
#     write_header = not os.path.exists(filename)
#     with open(filename, mode='a', newline='', encoding='utf-8') as file:
#         writer = csv.DictWriter(file, fieldnames=csv_fields)
#         if write_header:
#             writer.writeheader()
#         writer.writerows(data)


async def get_collections(limit: int = 100, authData: str = "") -> list:
    """
    Retrieves a list of collections and their floors, supply, daily volume etc from the marketplace.

    Args:
        limit (int): The maximum number of results to return. Defaults to 100.
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of dictionaries containing information about the collections if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
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


async def get_portals_auth_token(api_id: int, api_hash: str) -> str:
    async with Client("giftalyzerauth", api_id=api_id, api_hash=api_hash, phone_number=PHONE_NUMBER, password=TWO_FA_PASSWORD) as client:
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
        initData = unquote(web_view.url.split('tgWebAppData=', 1)[1].split('&tgWebAppVersion', 1)[0])
        # print("🔐 WebView URL:", web_view.url)
        # print("📦 InitData:", initData)
        return initData


async def get_gifts_by_collection_name(collection_name: str, auth_token: str) -> list:
    """
    Fetch all gifts for a given collection name with improved pagination handling.

    Args:
        collection_name (str): Name of the collection to fetch gifts from.
        auth_token (str): Telegram Mini App auth token.

    Returns:
        list: A list of dictionaries containing gift data.
    """
    # Get configuration for this collection
    config = get_pagination_config(collection_name)
    api_config = get_api_config()
    error_config = get_error_config()
    
    # Use the actual collection name as seen in the collections list for search
    collection = quote_plus(collection_name.strip().replace("'", "'"))
    offset = 0
    limit = config["limit"]
    all_items = []
    seen_ids = set()
    consecutive_empty_pages = 0
    consecutive_repeated_pages = 0

    headers = {
        **api_config["headers"],
        "Authorization": f"tma {auth_token}"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        while offset < config["max_offset"]:
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={limit}"
                f"&collections={collection}"
                f"&status={api_config['default_status']}"
            )
            print(f"🌐 Requesting URL: {url}")

            # Retry logic for failed requests
            max_retries = config["max_retries"]
            retry_delay = config["retry_delay"]
            
            for attempt in range(max_retries):
                try:
                    timeout = aiohttp.ClientTimeout(total=config["request_timeout"])
                    async with session.get(url, timeout=timeout) as resp:
                        if resp.status == config["rate_limit_status"]:  # Rate limited
                            wait_time = retry_delay * (config["retry_backoff_multiplier"] ** attempt)
                            print(f"⏳ Rate limited, waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                            await asyncio.sleep(wait_time)
                            continue
                        elif resp.status != config["success_status"]:
                            error_msg = get_error_message(resp.status, error_config)
                            print(f"❌ HTTP {resp.status} at offset {offset}: {error_msg}")
                            
                            if should_retry_request(resp.status, error_config) and attempt < max_retries - 1:
                                await asyncio.sleep(retry_delay)
                                continue
                            else:
                                print(f"🛑 Failed after {max_retries} attempts at offset {offset}")
                                break
                        
                        data = await resp.json()
                        items = data.get("results", [])
                        
                        if not items:
                            consecutive_empty_pages += 1
                            if config["verbose_logging"]:
                                print(f"📭 Empty page at offset {offset} (consecutive: {consecutive_empty_pages})")
                            if consecutive_empty_pages >= config["max_consecutive_empty_pages"]:
                                print(f"🛑 Stopping pagination after {config['max_consecutive_empty_pages']} consecutive empty pages")
                                break
                            offset += limit
                            continue
                        else:
                            consecutive_empty_pages = 0  # Reset counter

                        # Check for duplicate IDs within the current batch
                        current_ids = [item["id"] for item in items]
                        if len(current_ids) != len(set(current_ids)) and config["log_duplicate_ids"]:
                            print(f"⚠️ Duplicate IDs in batch at offset {offset}")

                        # Check for repeated IDs from previous pages
                        new_items = [item for item in items if item["id"] not in seen_ids]
                        repeated_count = len(items) - len(new_items)
                        
                        if repeated_count == len(items):  # All items are repeated
                            consecutive_repeated_pages += 1
                            if config["verbose_logging"]:
                                print(f"🔄 All items repeated at offset {offset} (consecutive: {consecutive_repeated_pages})")
                            
                            if consecutive_repeated_pages >= config["max_consecutive_repeated_pages"]:
                                print(f"🛑 Stopping pagination after {config['max_consecutive_repeated_pages']} consecutive repeated pages")
                                break
                        else:
                            consecutive_repeated_pages = 0  # Reset counter
                            
                            if repeated_count > 0 and config["log_repeated_ids"]:
                                repeated_ids = [item["id"] for item in items if item["id"] in seen_ids]
                                print(f"🧪 {repeated_count} repeated IDs at offset {offset}: {repeated_ids[:3]}{'...' if len(repeated_ids) > 3 else ''}")

                        # Add new items to our collection
                        for item in new_items:
                            seen_ids.add(item["id"])
                        all_items.extend(new_items)

                        print(f"📥 Fetched {len(all_items)} total gifts for {collection_name} (new: {len(new_items)})")
                        print(f"🔍 Current offset: {offset}, Items this page: {len(items)}")

                        # Check if we've reached the end of results
                        if len(items) < limit:
                            print(f"✅ Reached end of results at offset {offset} (items < limit)")
                            break

                        offset += limit
                        break  # Success, exit retry loop
                        
                except asyncio.TimeoutError:
                    print(f"⏰ Timeout at offset {offset}, attempt {attempt + 1}/{max_retries}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                    else:
                        print(f"🛑 Timeout after {max_retries} attempts at offset {offset}")
                        break
                except Exception as e:
                    print(f"❌ Error at offset {offset}, attempt {attempt + 1}/{max_retries}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                    else:
                        print(f"🛑 Failed after {max_retries} attempts at offset {offset}")
                        break

            # Calculate adaptive delay
            delay = calculate_delay(config, consecutive_repeated_pages)
            await asyncio.sleep(delay)

    print(f"🎯 Final result: {len(all_items)} unique gifts fetched for {collection_name}")
    return all_items


async def main():
    global PORTALS_AUTH
    api_id = int(os.environ.get("API_ID"))
    api_hash = os.environ.get("API_HASH")
    PORTALS_AUTH = await get_portals_auth_token(api_id, api_hash)
    colls = await get_collections(limit=1000, authData=PORTALS_AUTH)
    print("✅ Retrieved Collections:")
    for col in colls:
        print(col["name"], "-", col.get("floor_price"))

    # Accumulate all gifts here
    all_gifts = []
    for col in colls:
        col_name = col["name"]
        print(f"📦 Fetching gifts for collection: {col_name}")
        detailed_gifts = await get_gifts_by_collection_name(col_name, PORTALS_AUTH)
        print(f"✅ Retrieved {len(detailed_gifts)} gifts for {col_name}")
        all_gifts.extend(detailed_gifts)

    # Save all gifts to a unified CSV file using pandas
    if all_gifts:
        all_gifts_df = pd.DataFrame(all_gifts)
        all_gifts_df.to_csv("all_collections_gifts.csv", index=False)
        print(f"💾 Saved {len(all_gifts)} gifts to all_collections_gifts.csv")

asyncio.run(main())
