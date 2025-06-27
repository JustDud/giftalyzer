from pymongo import MongoClient
from dotenv import load_dotenv
import os

# Bulk upsert utility
from pymongo import UpdateOne

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client.getgems

gifts_collection = db.gifts
nfts_collection = db.nfts
collections_collection = db.collections

# Indexes to ensure uniqueness and efficient lookups
nfts_collection.create_index("nft_id", unique=True)
nfts_collection.create_index("collection_address")
collections_collection.create_index("address", unique=True)


def upsert_many(collection, documents, key="_id"):
    """
    Efficiently upserts many documents based on a unique key.
    """
    operations = []
    for doc in documents:
        if key in doc:
            operations.append(UpdateOne({key: doc[key]}, {"$set": doc}, upsert=True))
    if operations:
        result = collection.bulk_write(operations)
        print(f"✅ Upserted {result.upserted_count} inserted / {result.modified_count} updated documents.")


def remove_missing(collection, valid_ids, match=None, key="nft_id"):
    """
    Removes documents from the collection where the key is not in valid_ids and match conditions are met.
    """
    if match is None:
        match = {}
    match[key] = {"$nin": valid_ids}
    result = collection.delete_many(match)
    print(f"🗑️ Removed {result.deleted_count} documents not in the scraped list.")