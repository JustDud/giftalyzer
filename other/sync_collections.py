import asyncio
import aiohttp
import os
from dotenv import load_dotenv
from auth import get_portals_auth_token, get_auth_credentials
from mongo import collections_collection, upsert_and_notify_new_collections

load_dotenv()
API_URL_PORTALS = os.environ.get("API_URL_PORTALS")

async def get_collections(limit: int = 100, auth_token: str = "") -> list:
    url = f"{API_URL_PORTALS}/api/collections?limit={limit}"
    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(
                    f"Error {response.status}: {await response.text()}"
                )
            data = await response.json()
            return data.get("collections", [])

async def sync():
    print("🔐 Getting authentication token...")
    api_id, api_hash = get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)

    print("📦 Fetching collections from API...")
    collections = await get_collections(limit=500, auth_token=auth_token)

    print(f"📋 Retrieved {len(collections)} collections. Syncing to DB...")
    new_items = await upsert_and_notify_new_collections(collections_collection, collections, key="address")

    print(f"✅ Sync complete. {len(new_items)} new collections added.")

if __name__ == "__main__":
    asyncio.run(sync())