import aiohttp
import logging
from typing import List
import asyncio
import json
from data_collection.auth import get_auth_credentials, get_portals_auth_token


API_URL_PORTALS = "https://portals-market.com"
logger = logging.getLogger(__name__)


def _normalize_backdrops_payload(data) -> list[str]:
    """
    Extract backdrop names from common shapes:
    - {"floorPrices": {...}}
    - {"data": {"floorPrices": {...}}}
    - {"floor_prices": {...}}
    - {"backdrops": [...]}, {"values": [...]}, {"results": [...]}
    - Dict of {name: {...}}
    - Plain list of strings
    """
    names: list[str] = []
    if data is None:
        return names
    # Direct list
    if isinstance(data, list):
        # Case A: list of strings/ints
        simple = [str(x).strip() for x in data if isinstance(x, (str, int)) and str(x).strip()]
        if simple:
            return simple
        # Case B: list of dicts -> try to pick common fields
        collected: list[str] = []
        for item in data:
            if isinstance(item, dict):
                val = item.get("backdrop") or item.get("name") or item.get("title")
                if isinstance(val, str) and val.strip():
                    collected.append(val.strip())
        if collected:
            return list(dict.fromkeys(collected))
        return []
    if not isinstance(data, dict):
        return names

    # Try nested "data" container first
    container = data.get("data") if isinstance(data.get("data"), (dict, list)) else data

    # Floor prices variations
    for key in ("floorPrices", "floor_prices"):
        fp = container.get(key) if isinstance(container, dict) else None
        if isinstance(fp, dict):
            return list(fp.keys())

    # Lists under known keys
    for key in ("backdrops", "values", "results"):
        val = container.get(key) if isinstance(container, dict) else None
        if isinstance(val, list):
            # strings/ints
            simple = [str(x).strip() for x in val if isinstance(x, (str, int)) and str(x).strip()]
            if simple:
                return simple
            # list of dicts
            collected: list[str] = []
            for item in val:
                if isinstance(item, dict):
                    v = item.get("backdrop") or item.get("name") or item.get("title")
                    if isinstance(v, str) and v.strip():
                        collected.append(v.strip())
            if collected:
                return list(dict.fromkeys(collected))

    # Fallback: dictionary of {name: {...}}
    if isinstance(container, dict):
        try:
            if container and all(isinstance(k, str) for k in container.keys()):
                return list(container.keys())
        except Exception:
            pass
    return names


async def fetch_json(session: aiohttp.ClientSession, url: str, headers: dict) -> tuple[int, dict | None]:
    try:
        async with session.get(url, headers=headers) as resp:
            status = resp.status
            try:
                data = await resp.json()
            except Exception:
                text = await resp.text()
                logger.warning(f"Non-JSON response from {url}: {text[:200]}")
                data = None
            return status, data
    except Exception as e:
        logger.error(f"Request failed {url}: {e}")
        return 0, None


async def fetch_backdrops(tma_token: str, extra_headers: dict | None = None) -> List[str]:
    """
    Fetch global backdrops from Portals Market.
    Requires a valid Telegram Mini App initData token (the long string after 'tma ').
    Returns a list of backdrop names (strings).
    """
    if not isinstance(tma_token, str) or not tma_token.strip():
        raise ValueError("tma_token is required and must be a non-empty string")

    # Accept tokens with or without leading 'tma ' and normalise
    token = tma_token.strip()
    if token.lower().startswith("tma "):
        token = token[4:].strip()

    headers = {
        "Authorization": f"tma {token}",
        "Accept": "application/json",
        "User-Agent": "TelegramBot",
        "Referer": "https://portals-market.com/",
        "Origin": "https://portals-market.com",
        "Accept-Language": "en-GB,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)

    url = f"{API_URL_PORTALS}/api/collections/filters/backdrops"
    async with aiohttp.ClientSession() as session:
        status, data = await fetch_json(session, url, headers)
        logger.info(f"GET {url} -> {status}")
        if status != 200 or not data:
            # Try to show a short body snippet for easier debugging
            try:
                async with session.get(url, headers=headers) as resp:
                    txt = await resp.text()
                    logger.warning(f"Body snippet ({status}): {txt[:300]}")
            except Exception:
                pass
            return []

        names = _normalize_backdrops_payload(data)
        if names:
            return names
        # If we reached here, we failed to parse despite 200. Log the top-level keys to diagnose.
        try:
            keys = list(data.keys()) if isinstance(data, dict) else type(data).__name__
            logger.warning(f"Backdrops response parsed empty; top-level keys: {keys}")
        except Exception:
            logger.warning("Backdrops response parsed empty; unable to list keys")
        try:
            if isinstance(data, list) and data:
                logger.debug(f"First list element type: {type(data[0]).__name__}; sample: {str(data[0])[:200]}")
        except Exception:
            pass
        return []


async def get_all_backdrops():
    api_id, api_hash = await get_auth_credentials()
    auth_token = await get_portals_auth_token(api_id, api_hash)
    bds = await fetch_backdrops(auth_token)
    print(json.dumps(bds, indent=2, ensure_ascii=False))
