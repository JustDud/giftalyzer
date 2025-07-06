from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
import os
from typing import List, Dict, Any
from pymongo.collection import Collection
import csv


load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client.getgems

gifts_collection = db.gifts
nfts_collection = db.nfts
collections_collection = db.collections
subscriptions_collection = db.subscriptions

# Indexes to ensure uniqueness and efficient lookups
nfts_collection.create_index("nft_id", unique=True)
nfts_collection.create_index("collection_address")
collections_collection.create_index("address", unique=True)
subscriptions_collection.create_index("user_id", unique=True)


def upsert_and_notify_new_collections(collections_collection, collection_summaries):
    existing_addresses = {
        doc["address"] for doc in collections_collection.find({}, {"address": 1})
    }
    new_collections = [col for col in collection_summaries if col["address"] not in existing_addresses]

    upsert_many(collections_collection, collection_summaries, key="address")

    for new_col in new_collections:
        print(f"📢 New collection published: {new_col['name']} ({new_col['address']})")
        # Optionally send a message via Telegram bot, Discord webhook, email, etc.

    return new_collections


def upsert_many(collection: Collection, documents: List[Dict[str, Any]], key: str = "_id") -> None:
    """
    Efficiently upserts many documents based on a unique key.
    """
    operations = []
    for doc in documents:
        if key in doc:
            operations.append(UpdateOne({key: doc[key]}, {"$set": doc}, upsert=True))
    if operations:
        result = collection.bulk_write(operations)
        print(f"Upserted {result.upserted_count} inserted / {result.modified_count} updated documents.")


def remove_missing(collection: Collection, valid_ids: List[Any], match: Dict[str, Any] = None, key: str = "nft_id") -> None:
    """
    Removes documents from the collection where the key is not in valid_ids and match conditions are met.
    """
    if match is None:
        match = {}
    match[key] = {"$nin": valid_ids}
    result = collection.delete_many(match)
    print(f"Removed {result.deleted_count} documents not in the scraped list.")


def export_all_nft_prices_to_csv(estimate_ton_price, convert_ton_to_usd, output_path="nft_price_output.csv"):
    """
    Export all NFTs from the DB with their estimated price to a CSV.
    """
    nfts = list(nfts_collection.find())

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["nft_id", "collection_name", "backdrop", "model", "symbol", "estimated_ton", "usd", "real_price"])

        for nft in nfts:
            nft_id = nft.get("nft_id")
            collection_address = nft.get("collection_address")
            collection_doc = collections_collection.find_one({"address": collection_address})
            collection_name = collection_doc["name"] if collection_doc else ""

            try:
                estimated_price = estimate_ton_price(nft_id)
                usd_price = convert_ton_to_usd(estimated_price)
            except Exception as e:
                print(f"Error estimating price for {nft_id}: {e}")
                estimated_price = None
                usd_price = None

            writer.writerow([
                nft_id,
                collection_name,
                nft.get("backdrop", ""),
                nft.get("model", ""),
                nft.get("symbol", ""),
                estimated_price,
                usd_price,
                nft.get("last_sale") or nft.get("price") or ""
            ])