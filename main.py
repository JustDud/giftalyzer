import asyncio
from bot_manager.bot import run_bot


async def main():
    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())
