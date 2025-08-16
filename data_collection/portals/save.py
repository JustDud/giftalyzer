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
    Fetch all gifts for a given collection name.

    Args:
        collection_name (str): Name of the collection to fetch gifts from.
        auth_token (str): Telegram Mini App auth token.

    Returns:
        list: A list of dictionaries containing gift data.
    """
    # Use the actual collection name as seen in the collections list for search
    collection = quote_plus(collection_name.strip().replace("’", "'"))
    offset = 0
    limit = 100
    all_items = []
    seen_ids = set()

    headers = {
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
        "Authorization": f"tma {auth_token}"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={limit}"
                f"&collections={collection}"
                f"&status=listed{SORTS['gift_id_asc']}"
            )

            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"❌ HTTP {resp.status}")
                    break
                data = await resp.json()
                items = data.get("results", [])
                if not items:
                    break

                if not any(item["id"] not in seen_ids for item in items):
                    repeated_ids = [item["id"] for item in items if item["id"] in seen_ids]
                    print(f"🧪 Repeated IDs at offset {offset}: {repeated_ids[:5]}{'...' if len(repeated_ids) > 5 else ''}")
                    print(f"🛑 Pagination stopped early due to repeated data at offset {offset}")
                    break

                new_items = [item for item in items if item["id"] not in seen_ids]
                for item in new_items:
                    seen_ids.add(item["id"])
                all_items.extend(new_items)

                print(f"📥 Fetched {len(all_items)} gifts for {collection_name}")

                print(f"🔍 Current offset: {offset}, Items this page: {len(items)}")

                if len(items) < limit:
                    break  # No more results

                offset += limit

            await asyncio.sleep(random.uniform(0.4, 0.5))

    # No per-collection CSV writing here.
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
