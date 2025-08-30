import asyncio
from data_collection.portals import backdropsfiltered_scraper
from mongo import cleanup_empty_market_nfts, db


async def update_db():
    while True:
        try:
            await backdropsfiltered_scraper.run_portals_scraper()
        except Exception as e:
            print(f"[db_updater] error: {e!r}")
            await asyncio.sleep(100)
        await asyncio.sleep(0.5)


if __name__ == "__main__":
    asyncio.run(update_db())