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
from pathlib import Path

load_dotenv()


API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE")
TWO_FA_PASSWORD = os.environ.get("TELEGRAM_PASSWORD")

# Absolute path to the Pyrogram session file (mounted in Docker)
SESSION_PATH = os.environ.get("TG_SESSION_PATH", "/app/data_collection/portals/giftalyzerauth.session")


def _resolve_session_path(name: str | None = None) -> str:
    """
    Ensure we always use an absolute path that ends with .session.
    If a relative path is provided, make it absolute relative to this file's directory.
    """
    p = name or SESSION_PATH or "giftalyzerauth.session"
    # Ensure .session suffix
    if not p.endswith(".session"):
        p += ".session"
    # If not absolute, resolve relative to project root (this file's directory two levels up if needed)
    if not os.path.isabs(p):
        base_dir = os.path.abspath(os.path.dirname(__file__))
        p = os.path.abspath(os.path.join(base_dir, p))
    # Make sure the parent directory exists to avoid runtime errors
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _resolve_session_parts(name: str | None = None) -> tuple[str, str]:
    """
    Return (workdir, session_name) suitable for Pyrogram's Client, avoiding
    the double '.session' suffix. Pyrogram appends '.session' automatically.
    """
    p = _resolve_session_path(name)
    path = Path(p)
    # Pyrogram wants the base name without the '.session' suffix
    session_name = path.stem if path.suffix == ".session" else path.name
    workdir = str(path.parent)
    # Ensure directory exists
    os.makedirs(workdir, exist_ok=True)
    return workdir, session_name


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
    workdir, session_name = _resolve_session_parts()
    async with Client(
        session_name,
        api_id=api_id,
        api_hash=api_hash,
        phone_number=PHONE_NUMBER,
        password=TWO_FA_PASSWORD,
        no_updates=True,
        workdir=workdir,
    ) as client:
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


async def get_tgmrkt_init_data(api_id: int, api_hash: str, bot_username="mrkt", short_name="market", session_name: str | None = None) -> str:
    """
    Get Telegram WebApp initData for TGMRKT bot.

    Args:
        api_id (int): Telegram API ID
        api_hash (str): Telegram API Hash

    Returns:
        str: Telegram WebApp initData string
    """
    workdir, resolved_name = _resolve_session_parts(session_name)
    async with Client(
        resolved_name,
        api_id=api_id,
        api_hash=api_hash,
        phone_number=PHONE_NUMBER,
        password=TWO_FA_PASSWORD,
        no_updates=True,
        workdir=workdir,
    ) as client:
        peer = await client.resolve_peer(bot_username)
        user_full = await client.invoke(GetUsers(id=[peer]))
        bot_raw = user_full[0]
        bot = InputUser(user_id=bot_raw.id, access_hash=bot_raw.access_hash)
        bot_app = InputBotAppShortName(bot_id=bot, short_name=short_name)
        web_view = await client.invoke(
            RequestAppWebView(
                peer=peer,
                app=bot_app,
                platform="android",
                theme_params=None,
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
