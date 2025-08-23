import asyncio
from data_collection.portals import portals_scraper


async def main():
    while True:
        await portals_scraper.run_portals_scraper()
        await asyncio.sleep(14400)  # 4 hours

if __name__ == "__main__":
    asyncio.run(main())