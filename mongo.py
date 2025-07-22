import re
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from dotenv import load_dotenv
import os
from typing import List, Dict, Any
import csv
from datetime import datetime

load_dotenv()

client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client.getgems

gifts_collection: AsyncIOMotorCollection = db.gifts
nfts_collection: AsyncIOMotorCollection = db.nfts
collections_collection: AsyncIOMotorCollection = db.collections
subscriptions_collection: AsyncIOMotorCollection = db.subscriptions
support_collection: AsyncIOMotorCollection = db.support_tickets
promo_codes_collection: AsyncIOMotorCollection = db.promo_codes
promo_usage_collection: AsyncIOMotorCollection = db.promo_usage

# Indexes to ensure uniqueness and efficient lookups
async def init_indexes():
    await nfts_collection.create_index("nft_id", unique=True)
    await nfts_collection.create_index("collection_address")
    await collections_collection.create_index("address", unique=True)
    await subscriptions_collection.create_index("user_id", unique=True)
    await promo_codes_collection.create_index("code", unique=True)
    await promo_usage_collection.create_index("promo_code")


def normalize_nft_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip()
    import re
    match = re.match(r"^(.*?)[\s#]+(\d+)$", name)
    if match:
        prefix = match.group(1).replace(" ", "")
        number = match.group(2)
        return f"{prefix}-{number}"
    return name.replace(" ", "")


async def upsert_and_notify_new_collections(
    collection: AsyncIOMotorCollection,
    collection_summaries: List[Dict],
    key: str = "address"
):
    existing_keys = {
        doc[key]
        async for doc in collection.find({}, {key: 1})
    }

    new_items = [
        col for col in collection_summaries if col[key] not in existing_keys
    ]

    await upsert_many(collection, collection_summaries, key=key)

    for new in new_items:
        print(f"📢 New item published: {new.get('name', '')} ({new.get(key)})")

    return new_items


async def upsert_many(collection: AsyncIOMotorCollection, documents: List[Dict[str, Any]], key: str = "_id"):
    operations = []
    for doc in documents:
        if key in doc:
            operations.append(
                {
                    "filter": {key: doc[key]},
                    "update": {"$set": doc},
                    "upsert": True
                }
            )
    if operations:
        requests = [
            collection.update_one(op["filter"], op["update"], upsert=op["upsert"])
            for op in operations
        ]
        await asyncio.gather(*requests)
        print(f"Upserted {len(operations)} documents.")


async def remove_missing(collection: AsyncIOMotorCollection, valid_ids: List[Any], match: Dict[str, Any] = None, key: str = "nft_id"):
    if match is None:
        match = {}
    match[key] = {"$nin": valid_ids}
    result = await collection.delete_many(match)
    print(f"Removed {result.deleted_count} documents not in the scraped list.")


async def export_all_nft_prices_to_csv(estimate_ton_price, convert_ton_to_usd, output_path="nft_price_output.csv"):
    nfts = [n async for n in nfts_collection.find()]

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "nft_id", "collection_name", "backdrop", "model", "symbol",
            "floor_price", "rarity", "real_price", "estimated_ton", "usd", "last_sale_date"
        ])

        for nft in nfts:
            nft_id = nft.get("nft_id")
            collection_address = nft.get("collection_address")
            collection_doc = await collections_collection.find_one({"address": collection_address})
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
                nft.get("floor_price", ""),
                nft.get("rarity", ""),
                nft.get("last_sale") or nft.get("price") or "",
                estimated_price,
                usd_price,
                nft.get("last_sale_date", "")
            ])


async def get_nft_by_id_or_name(gift_id: str):
    nft = await nfts_collection.find_one({"nft_id": gift_id})
    if nft:
        return nft
    if "-" in gift_id and not gift_id.startswith("EQ"):
        nft = await nfts_collection.find_one({"name": gift_id})
        if nft:
            return nft
    return await nfts_collection.find_one({"collection_address": gift_id})


async def get_nfts_by_params(model: str, symbol: str | None, backdrop: str) -> list[dict]:
    query = {
        "model": model,
        "backdrop": backdrop,
        "price": {"$ne": None}
    }
    if symbol:
        query["symbol"] = symbol

    return [n async for n in nfts_collection.find(query)]


async def get_all_subscriptions():
    return [doc async for doc in subscriptions_collection.find()]


async def get_nfts_strict_match(model: str, symbol: str, backdrop: str, collection_name: str = None) -> list[dict]:
    query = {
        "model": model,
        "symbol": symbol,
        "backdrop": backdrop,
        "price": {"$ne": None}
    }
    if collection_name:
        query["name"] = {"$regex": f"^{collection_name}", "$options": "i"}

    return [n async for n in nfts_collection.find(query)]


async def get_nfts_loose_match(model: str, backdrop: str, collection_name: str = None) -> list[dict]:
    query = {
        "model": model,
        "backdrop": backdrop,
        "price": {"$ne": None}
    }
    if collection_name:
        query["name"] = {"$regex": f"^{collection_name}", "$options": "i"}

    return [n async for n in nfts_collection.find(query)]


async def get_nfts_model_only(model: str, collection_name: str = None) -> list[dict]:
    query = {
        "model": model,
        "price": {"$ne": None}
    }
    if collection_name:
        query["name"] = {"$regex": f"^{collection_name}", "$options": "i"}

    return [n async for n in nfts_collection.find(query)]

