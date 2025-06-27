import time
import os
import json

from data_collection.marketapp.collections_scraper import scrape_collections
from data_collection.marketapp.nft_scraper import scrape_nfts
from data_collection.mongo import nfts_collection, collections_collection, upsert_many
from data_collection.mongo import remove_missing


def scrape_and_update_db():
    total_start = time.time()

    print("Scraping collections summary from MarketApp...")
    scrape_collections()

    collection_file_path = os.path.join(os.path.dirname(__file__), "..", "scraped_output", "collections_summary.json")
    with open(collection_file_path, "r") as f:
        collection_summaries = json.load(f)
    print(f"✅ Scraped {len(collection_summaries)} collections.\n")

    all_nfts = []

    for idx, collection in enumerate(collection_summaries, 1):
        print(f"Scraping collection ({idx}/{len(collection_summaries)}): {collection['name']} ({collection['address']})")
        nfts = scrape_nfts(collection['address']) or []
        print(f"Debug: Number of NFTs scraped: {len(nfts)}")
        for nft in nfts:
            nft["collection_address"] = collection["address"]
            nft["nft_id"] = nft.get("href", "").split("/")[-2] if "href" in nft else None
        all_nfts.extend(nfts)

    upsert_many(collections_collection, collection_summaries, key="address")
    upsert_many(nfts_collection, all_nfts, key="nft_id")

    scraped_ids_by_collection = {}
    for nft in all_nfts:
        col_addr = nft["collection_address"]
        scraped_ids_by_collection.setdefault(col_addr, []).append(nft["nft_id"])

    for address, nft_ids in scraped_ids_by_collection.items():
        remove_missing(nfts_collection, nft_ids, match={"collection_address": address})

    total_elapsed = round(time.time() - total_start, 2)
    print(f"\nTotal time to scrape all collections: {total_elapsed} seconds")