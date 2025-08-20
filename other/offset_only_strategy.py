#!/usr/bin/env python3
"""
Offset-only collection strategy (simplest, minimal dedupe):
 - Resolve collection_id by name
 - Fetch listed items using offsets up to 800
 - Deduplicate by id across pages

Usage:
  python data_collection/portals/offset_only_strategy.py "Plush Pepe" "Snoop Dogg"
"""

import os
import asyncio
import logging
import random
from typing import List, Dict, Set, Tuple
from urllib.parse import quote_plus

import aiohttp
from dotenv import load_dotenv

from auth import get_portals_auth_token, get_auth_credentials


load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def _sleep_backoff(attempt: int, retry_after: float | None = None):
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


async def get_collections(limit: int, auth_token: str) -> List[Dict]:
    url = f"{API_URL_PORTALS}/api/collections?limit={limit}"
    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                logger.warning(f"collections(): HTTP {resp.status}")
                return []
            try:
                data = await resp.json()
            except Exception:
                return []
            return data.get("collections", data) or []


async def scan_offsets_simple(collection_id: str, headers: dict, seen_ids: Set[str]) -> List[Dict]:
    """Fetch listed NFTs by offsets up to 800 with limit=50; skip pages that error/empty; dedupe by id."""
    items: List[Dict] = []
    collection_q = quote_plus(collection_id)
    limit = 50
    step = 50
    async with aiohttp.ClientSession() as session:
        for offset in range(0, 800, step):
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={limit}&collection_id={collection_q}&status=listed"
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
    logger.info(f"Offset-only scan collected {len(items)} items")
    return items


async def run_offset_only(collection_name: str, auth_token: str) -> List[Dict]:
    logger.info(f"Offset-only strategy for: {collection_name}")
    cols = await get_collections(500, auth_token)
    name_to_id = {c.get("name"): c.get("id") for c in cols if c.get("name") and c.get("id")}
    coll_id = name_to_id.get(collection_name)
    if not coll_id:
        logger.error(f"Collection id not found for '{collection_name}'")
        return []

    headers = {
        "Authorization": f"tma {auth_token}",
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
    seen_ids: Set[str] = set()
    items = await scan_offsets_simple(coll_id, headers, seen_ids)
    logger.info(f"Final unique: {len(items)} for '{collection_name}'")
    return items


async def main():
    import sys
    names = sys.argv[1:]
    if not names:
        print("Usage: python data_collection/portals/offset_only_strategy.py \"Collection Name\" [more names...]")
        return
    api_id, api_hash = get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)
    for name in names:
        await run_offset_only(name, auth_token)


if __name__ == "__main__":
    asyncio.run(main())


