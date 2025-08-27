import asyncio
from datetime import datetime, timezone
from subscription.subscription_manager import remove_expired_subscriptions

async def run_once():
    await remove_expired_subscriptions()
