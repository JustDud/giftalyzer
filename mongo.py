from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
import os
from typing import List, Dict, Any
from pymongo.collection import Collection

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
