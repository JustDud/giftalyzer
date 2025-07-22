import time
import asyncio
from data_collection.marketapp.collections_scraper import scrape_collections
from data_collection.marketapp.nft_scraper import scrape_nfts
from mongo import nfts_collection, collections_collection, upsert_many, remove_missing, upsert_and_notify_new_collections


async def scrape_and_update_db():
    total_start = time.time()

    collection_summaries = scrape_collections()

    print("DEBUG: scraped collections:", collection_summaries)
    print(f"✅ Scraped {len(collection_summaries)} collections.\n")

    await upsert_and_notify_new_collections(collections_collection, collection_summaries)

    all_nfts = []

    for idx, collection in enumerate(collection_summaries, 1):
        print(f"Scraping collection ({idx}/{len(collection_summaries)}): {collection['name']} ({collection['address']})")
        nfts = scrape_nfts(collection['address']) or []
        print(f"Debug: Number of NFTs scraped: {len(nfts)}")
        for nft in nfts:
            nft["collection_address"] = collection["address"]
            nft["nft_id"] = nft.get("href", "").split("/")[-2] if "href" in nft else None
        all_nfts.extend(nfts)

    await upsert_many(nfts_collection, all_nfts, key="nft_id")

    scraped_ids_by_collection = {}
    for nft in all_nfts:
        col_addr = nft["collection_address"]
        scraped_ids_by_collection.setdefault(col_addr, []).append(nft["nft_id"])

    remove_tasks = [
        remove_missing(nfts_collection, nft_ids, match={"collection_address": address})
        for address, nft_ids in scraped_ids_by_collection.items()
    ]
    await asyncio.gather(*remove_tasks)

    total_elapsed = round(time.time() - total_start, 2)
    print(f"\nTotal time to scrape all collections: {total_elapsed} seconds")
