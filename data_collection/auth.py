#!/usr/bin/env python3
"""
Authentication module for Portals API.
Handles Telegram authentication and token generation.
"""

import os
from urllib.parse import unquote
from dotenv import load_dotenv
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName, InputUser
from pyrogram.raw.functions.users import GetUsers

load_dotenv()

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE")
TWO_FA_PASSWORD = os.environ.get("TELEGRAM_PASSWORD")


async def get_portals_auth_token(api_id: int, api_hash: str) -> str:
    """
    Get authentication token for Portals API.
    
    Args:
        api_id (int): Telegram API ID
        api_hash (str): Telegram API Hash
        
    Returns:
        str: Authentication token for Portals API
        
    Raises:
        Exception: If authentication fails
    """
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
        initData = unquote(web_view.url.split('tgWebAppData=', 1)[1].split('&tgWebAppVersion', 1)[0])
        return initData


async def get_tgmrkt_init_data(api_id: int, api_hash: str) -> str:
    """
    Get Telegram WebApp initData for TGMRKT bot.

    Args:
        api_id (int): Telegram API ID
        api_hash (str): Telegram API Hash

    Returns:
        str: Telegram WebApp initData string
    """
    async with Client("tgmrktauth", api_id=api_id, api_hash=api_hash,
                      phone_number=PHONE_NUMBER, password=TWO_FA_PASSWORD) as client:
        peer = await client.resolve_peer("tgmrktbot")
        user_full = await client.invoke(GetUsers(id=[peer]))
        bot_raw = user_full[0]
        bot = InputUser(user_id=bot_raw.id, access_hash=bot_raw.access_hash)
        bot_app = InputBotAppShortName(bot_id=bot, short_name="gifts")
        web_view = await client.invoke(
            RequestAppWebView(
                peer=peer,
                app=bot_app,
                platform="desktop",
            )
        )
        initData = unquote(web_view.url.split('tgWebAppData=', 1)[1].split('&tgWebAppVersion', 1)[0])
        return initData


async def get_auth_credentials():
    """
    Get authentication credentials from environment variables.

    Returns:
        tuple: (api_id, api_hash) as (int, str)
    """
    api_id = int(os.environ.get("API_ID"))
    api_hash = os.environ.get("API_HASH")
    return api_id, api_hash


