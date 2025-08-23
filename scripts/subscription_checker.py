import asyncio
from datetime import datetime, timezone
from subscription.manager import remove_expired_subscriptions


async def main():
    while True:
        print(f"[{datetime.now(timezone.utc)}] Running daily subscription check...")
        await remove_expired_subscriptions()
        print(f"[{datetime.now(timezone.utc)}] Check complete.")
        await asyncio.sleep(86400)  # Sleep for 24 hours

if __name__ == "__main__":
    asyncio.run(main())