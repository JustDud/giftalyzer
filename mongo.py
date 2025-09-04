from typing import Optional
import re
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from dotenv import load_dotenv
import os
from typing import List, Dict, Any
import csv
from datetime import datetime, UTC
from typing import Set
from pymongo import UpdateOne
import re as _re

def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime (PEP 495/PEP 615 safe)."""
    return datetime.now(UTC)


def utc_ts() -> int:
    """Return current UTC timestamp as an integer (seconds)."""
    return int(utc_now().timestamp())


load_dotenv()


# NOTE: DB name is now "giftalyzer_db". Schema supports multi-market canonical IDs
# for collections/nfts while remaining backward compatible with existing data loaders.
client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client.giftalyzer_db

gifts_collection: AsyncIOMotorCollection = db.gifts
nfts_collection: AsyncIOMotorCollection = db.nfts
collections_collection: AsyncIOMotorCollection = db.collections
subscriptions_collection: AsyncIOMotorCollection = db.subscriptions
support_collection: AsyncIOMotorCollection = db.support_tickets
promo_codes_collection: AsyncIOMotorCollection = db.promo_codes
promo_usage_collection: AsyncIOMotorCollection = db.promo_usage

users_collection: AsyncIOMotorCollection = db.users

# --- Price existence helpers (DB-level guarantee) ---
KNOWN_MARKETS = ["portals", "getgems", "tonnel", "fragment"]

def _price_exists_filter(market: str | None, require_listed: bool) -> Dict[str, Any]:
    """Return a Mongo filter that ensures at least one price exists.
    - If require_listed is False → returns {} (no constraint)
    - If market is a specific name → require markets.<market>.price.amount exists
    - If market is None / "any" / "*" → require price in ANY known market via $or
    """
    if not require_listed:
        return {}
    if market and market not in ("any", "*"):
        return {f"markets.{market}.price.amount": {"$exists": True}}
    return {"$or": [{f"markets.{m}.price.amount": {"$exists": True}} for m in KNOWN_MARKETS]}

def _min_any_market_price_in_doc(nft: Dict[str, Any]) -> float:
    best = float("inf")
    for m in (nft.get("markets", {}) or {}).values():
        try:
            amt = float(m.get("price", {}).get("amount"))
            if amt < best:
                best = amt
        except Exception:
            continue
    return best

def _enrich_market_view(nft: Dict[str, Any], preferred_market: str | None = "portals") -> None:
    """Populate convenience fields price/url/is_listed.
    Prefers preferred_market; falls back to the cheapest among all markets.
    """
    markets = nft.get("markets", {}) or {}
    price = None
    url = ""
    if preferred_market and preferred_market in markets:
        try:
            price = float(markets[preferred_market].get("price", {}).get("amount"))
        except Exception:
            price = None
        url = markets[preferred_market].get("url", "")
    if price is None:
        best = float("inf"); best_url = ""
        for mk, data in markets.items():
            try:
                amt = float(data.get("price", {}).get("amount"))
                if amt < best:
                    best = amt
                    best_url = data.get("url", "")
            except Exception:
                continue
        if best != float("inf"):
            price = best
            url = best_url
    if price is not None:
        nft["price"] = price
        nft["is_listed"] = True
        nft["url"] = url or nft.get("url", "")
    else:
        nft["price"] = 0.0
        nft["is_listed"] = False
        nft["url"] = url or nft.get("url", "")


async def init_indexes():
    # --- collections ---
    # Canonical uniqueness by (chain, namespace, slug)
    await collections_collection.create_index(
        [("chain", 1), ("namespace", 1), ("slug", 1)], unique=True
    )
    # Text search on names/slugs
    await collections_collection.create_index([("name", "text"), ("slug", "text")])
    # Example sparse market floor index (per-market path, adjust as needed)
    for m in ["portals", "tonnel", "tgmrkt"]:
        # Collections: market floor index
        await collections_collection.create_index(
            [(f"markets.{m}.floor_price.amount", 1)], sparse=True
        )

    # --- nfts ---
    # Canonical uniqueness by (collection_uid, token_id)
    await nfts_collection.create_index(
        [("collection_uid", 1), ("token_id", 1)], unique=True
    )
    # Fast floor scans per market (sparse)
    for m in ["portals", "tonnel", "tgmrkt"]:
        await nfts_collection.create_index(
            [(f"markets.{m}.is_listed", 1), (f"markets.{m}.price.amount", 1)], sparse=True
        )
    # Trait filters
    await nfts_collection.create_index([("traits.type", 1), ("traits.value", 1)])
    # Text search
    await nfts_collection.create_index([("name", "text")])

    # --- subscriptions ---
    # Do not make user_id unique; users can have many periods. Index by user+start.
    await subscriptions_collection.create_index([("user_id", 1), ("period_start", -1)])
    await subscriptions_collection.create_index([("status", 1), ("period_end", -1)])
    # Optional reconciliation index
    await subscriptions_collection.create_index([("charge_id", 1)], sparse=True)

    # --- promo codes / usage ---
    await promo_codes_collection.create_index([("code", 1)], unique=True)
    await promo_codes_collection.create_index([("valid_from", 1), ("valid_to", 1)])
    await promo_usage_collection.create_index([("promo_code", 1), ("applied_at", -1)])
    await promo_usage_collection.create_index([("user_id", 1), ("applied_at", -1)])

    # --- support tickets ---
    await support_collection.create_index([("status", 1), ("updated_at", -1)])
    await support_collection.create_index([("user_id", 1), ("created_at", -1)])


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


def normalize_slug(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    # replace spaces/underscores with hyphens, drop non-alnum-hyphen
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def build_collection_uid(chain: str, namespace: str, slug: str) -> str:
    return f"{chain}|{namespace}|{slug}"


def build_nft_uid(collection_uid: str, token_id: str) -> str:
    return f"{collection_uid}#{token_id}"


def normalize_token_id(token: str | int) -> str:
    return str(token).strip()


async def upsert_collection_market_snapshot(collection_uid: str, market: str, snapshot: Dict[str, Any]):
    """Update collections.markets[market] with latest snapshot (floor, listed_count, url, last_seen)."""
    now = utc_ts()
    to_set = {f"markets.{market}": {**snapshot, "last_seen": snapshot.get("last_seen", now)}, "updated_at": now}
    await collections_collection.update_one(
        {"_id": collection_uid},
        {"$set": to_set},
        upsert=True,
    )


async def upsert_nft_market_state(collection_uid: str, token_id: str, name: str | None, traits: List[Dict[str, Any]] | None,
                                  media: Dict[str, Any] | None, market: str, market_state: Dict[str, Any],
                                  external_item_ids: Dict[str, Any] | None = None,
                                  intrinsic_fields: Dict[str, Any] | None = None):
    """Create/update NFT document and set markets.<market> latest state."""
    now = utc_ts()
    nft_uid = build_nft_uid(collection_uid, normalize_token_id(token_id))

    # $setOnInsert for static bits
    set_on_insert: Dict[str, Any] = {
        "_id": nft_uid,
        "collection_uid": collection_uid,
        "token_id": normalize_token_id(token_id),
        "traits": traits or [],
        "media": media or {},
        "created_at": now,
    }

    update: Dict[str, Any] = {
        "$setOnInsert": set_on_insert,
        "$set": {
            f"markets.{market}": {**(market_state or {}), "last_seen": now},
            "updated_at": now,
        },
    }
    if intrinsic_fields:
        update["$set"].update(intrinsic_fields)
    if name:
        update["$set"]["name"] = name
    if external_item_ids:
        update["$set"] = {**update["$set"], f"external_ids.{market}": external_item_ids}

    await nfts_collection.update_one({"_id": nft_uid}, update, upsert=True)


async def upsert_collections_and_build_map(cols: List[Dict], market: str = "portals") -> Dict[str, str]:
    """Ensure base collection docs exist and attach per‑market mapping.
    Returns: { <API collection id> -> <collection_uid> }"""
    id_to_uid: Dict[str, str] = {}
    now = utc_ts()
    for c in cols:
        name = c.get("name") or ""
        api_coll_id = c.get("id")
        if not api_coll_id:
            continue
        slug = normalize_slug(name or str(api_coll_id))
        collection_uid = build_collection_uid("TON", "gifts", slug)
        id_to_uid[str(api_coll_id)] = collection_uid

        # Ensure base collection exists + external_ids
        await collections_collection.update_one(
            {"_id": collection_uid},
            {
                "$setOnInsert": {
                    "_id": collection_uid,
                    "chain": "TON",
                    "namespace": "gifts",
                    "slug": slug,
                    "name": name,
                    "created_at": now,
                },
                "$set": {
                    f"external_ids.{market}": {"collection_id": api_coll_id},
                    "updated_at": now,
                },
            },
            upsert=True,
        )

        # Build per-market snapshot with required fields
        def _num(x):
            try:
                return float(x)
            except Exception:
                return None

        def _int(x):
            try:
                return int(float(x))
            except Exception:
                return None

        snapshot: Dict[str, Any] = {}

        # floor_price -> price object
        fp = c.get("floor_price") or c.get("floor")
        if _num(fp) is not None:
            snapshot["floor_price"] = {"amount": str(_num(fp)), "currency": "TON"}

        # day_volume and total volume (TON amounts)
        dv = c.get("day_volume") or c.get("volume_24h") or c.get("volume24h")
        if _num(dv) is not None:
            snapshot["day_volume"] = {"amount": str(_num(dv)), "currency": "TON"}

        tv = c.get("volume") or c.get("total_volume")
        if _num(tv) is not None:
            snapshot["volume"] = {"amount": str(_num(tv)), "currency": "TON"}

        # supply (integer)
        sup = c.get("supply") or c.get("total_supply")
        si = _int(sup)
        if si is not None:
            snapshot["supply"] = si

        # is_premarket (boolean-ish)
        ip = c.get("is_premarket")
        if isinstance(ip, bool):
            snapshot["is_premarket"] = ip
        elif isinstance(ip, str):
            snapshot["is_premarket"] = ip.strip().lower() in {"1", "true", "yes", "y"}
        elif isinstance(ip, (int, float)):
            snapshot["is_premarket"] = bool(int(ip))

        await upsert_collection_market_snapshot(collection_uid, market, snapshot)
    return id_to_uid


async def upsert_nfts_for_collection(items: List[Dict], collection_uid: str, market: str = "portals"):
    """Upsert a batch of NFT items for a single collection into Mongo."""
    for it in items:
        token_id = it.get("external_collection_number") or it.get("id")
        if token_id is None:
            continue
        name = it.get("name")
        traits = it.get("attributes") or []
        media = {"image_url": it.get("photo_url")} if it.get("photo_url") else {}

        # Build intrinsic NFT fields
        intrinsic_fields: Dict[str, Any] = {}
        if it.get("model") is not None:
            intrinsic_fields["model"] = it.get("model")
        if it.get("model_rarity_per_mille") is not None:
            intrinsic_fields["model_rarity_per_mille"] = float(it.get("model_rarity_per_mille"))
        if it.get("symbol") is not None:
            intrinsic_fields["symbol"] = it.get("symbol")
        if it.get("symbol_rarity_per_mille") is not None:
            intrinsic_fields["symbol_rarity_per_mille"] = float(it.get("symbol_rarity_per_mille"))
        if it.get("backdrop") is not None:
            intrinsic_fields["backdrop"] = it.get("backdrop")
        if it.get("backdrop_rarity_per_mille") is not None:
            intrinsic_fields["backdrop_rarity_per_mille"] = float(it.get("backdrop_rarity_per_mille"))

        market_state: Dict[str, Any] = {"is_listed": True}

        # price (TON)
        price_val = it.get("price")
        if price_val is not None:
            pv = None
            try:
                pv = float(price_val)
            except Exception:
                pass
            if pv is not None:
                market_state["price"] = {"amount": str(pv), "currency": "TON"}

        # floor_price (TON) as provided by market for this item
        nft_fp = it.get("floor_price")
        if nft_fp is not None:
            fpv = None
            try:
                fpv = float(nft_fp)
            except Exception:
                pass
            if fpv is not None:
                market_state["floor_price"] = {"amount": str(fpv), "currency": "TON"}

        # listed/unlocks timestamps
        if it.get("listed_at"):
            market_state["listed_at"] = it.get("listed_at")
        if it.get("unlocks_at"):
            market_state["unlocks_at"] = it.get("unlocks_at")

        # tg identity / ownership flags if present
        if it.get("tg_id") is not None:
            market_state["tg_id"] = it.get("tg_id")
        if it.get("is_owned") is not None:
            market_state["is_owned"] = bool(it.get("is_owned"))

        share_url = it.get("share_url") or it.get("url")
        if share_url:
            market_state["url"] = share_url

        external_ids = {"id": it.get("id")}

        await upsert_nft_market_state(
            collection_uid=collection_uid,
            token_id=normalize_token_id(token_id),
            name=name,
            traits=traits,
            media=media,
            market=market,
            market_state=market_state,
            external_item_ids=external_ids,
            intrinsic_fields=intrinsic_fields,
        )


async def upsert_nfts_for_collection_bulk(
    items: List[Dict],
    collection_uid: str,
    market: str = "portals",
    batch_size: int = 750
) -> int:
    """
    Faster path: build UpdateOne ops and execute via bulk_write in batches (ordered=False).
    Avoids high client-side concurrency while significantly reducing round-trips.
    Returns total count of operations applied (approximate).
    """
    if not items:
        return 0

    def _to_safe_float(x):
        try:
            return float(x)
        except Exception:
            return None

    ops: List[UpdateOne] = []
    total = 0
    now = utc_ts()

    total_upserted = 0
    total_modified = 0
    total_matched = 0

    for it in items:
        token_id = it.get("external_collection_number") or it.get("id")
        if token_id is None:
            continue
        token_id_s = normalize_token_id(token_id)
        nft_uid = build_nft_uid(collection_uid, token_id_s)

        name = it.get("name")
        traits = it.get("attributes") or []
        media = {"image_url": it.get("photo_url")} if it.get("photo_url") else {}

        # Intrinsic fields (flattened)
        intrinsic_fields: Dict[str, Any] = {}
        if it.get("model") is not None:
            intrinsic_fields["model"] = it.get("model")
        if it.get("model_rarity_per_mille") is not None:
            val = _to_safe_float(it.get("model_rarity_per_mille"))
            if val is not None:
                intrinsic_fields["model_rarity_per_mille"] = val
        if it.get("symbol") is not None:
            intrinsic_fields["symbol"] = it.get("symbol")
        if it.get("symbol_rarity_per_mille") is not None:
            val = _to_safe_float(it.get("symbol_rarity_per_mille"))
            if val is not None:
                intrinsic_fields["symbol_rarity_per_mille"] = val
        if it.get("backdrop") is not None:
            intrinsic_fields["backdrop"] = it.get("backdrop")
        if it.get("backdrop_rarity_per_mille") is not None:
            val = _to_safe_float(it.get("backdrop_rarity_per_mille"))
            if val is not None:
                intrinsic_fields["backdrop_rarity_per_mille"] = val

        # Market state
        market_state: Dict[str, Any] = {"is_listed": True, "last_seen": now}
        pv = _to_safe_float(it.get("price"))
        if pv is not None:
            market_state["price"] = {"amount": str(pv), "currency": "TON"}
        fpv = _to_safe_float(it.get("floor_price"))
        if fpv is not None:
            market_state["floor_price"] = {"amount": str(fpv), "currency": "TON"}
        if it.get("listed_at"):
            market_state["listed_at"] = it.get("listed_at")
        if it.get("unlocks_at"):
            market_state["unlocks_at"] = it.get("unlocks_at")
        if it.get("tg_id") is not None:
            market_state["tg_id"] = it.get("tg_id")
        if it.get("is_owned") is not None:
            market_state["is_owned"] = bool(it.get("is_owned"))
        share_url = it.get("share_url") or it.get("url")
        if share_url:
            market_state["url"] = share_url

        set_on_insert: Dict[str, Any] = {
            "_id": nft_uid,
            "collection_uid": collection_uid,
            "token_id": token_id_s,
            "traits": traits or [],
            "media": media or {},
            "created_at": now,
        }

        update_set: Dict[str, Any] = {
            f"markets.{market}": market_state,
            "updated_at": now,
        }
        if intrinsic_fields:
            update_set.update(intrinsic_fields)
        if name:
            update_set["name"] = name
        external_ids = {"id": it.get("id")}
        if external_ids:
            update_set[f"external_ids.{market}"] = external_ids

        ops.append(
            UpdateOne(
                {"_id": nft_uid},
                {"$setOnInsert": set_on_insert, "$set": update_set},
                upsert=True,
            )
        )

        # Flush in batches
        if len(ops) >= batch_size:
            res = await nfts_collection.bulk_write(ops, ordered=False)
            total += (res.upserted_count or 0) + (res.modified_count or 0) + (res.matched_count or 0)
            ops = []

    if ops:
        res = await nfts_collection.bulk_write(ops, ordered=False)
        total_upserted += res.upserted_count or 0
        total_modified += res.modified_count or 0
        total_matched += res.matched_count or 0
        total += (res.upserted_count or 0) + (res.modified_count or 0) + (res.matched_count or 0)

    return {
        "upserted": total_upserted,
        "modified": total_modified,
        "matched": total_matched,
    }


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


async def reconcile_delist_for_collection(collection_uid: str, market: str, seen_token_ids: Set[str]) -> dict:
    """
    Flip markets.<market>.is_listed to False for NFTs in a collection that were NOT seen in the latest crawl.
    seen_token_ids must contain the token_id values used to build nft_uid (external_collection_number or id fallback).
    Returns basic stats {matched, modified}.
    """
    if not seen_token_ids:
        # Nothing seen => do not mass-delist; caller should decide a safer policy
        return {"matched": 0, "modified": 0}

    seen_list = [str(tid).strip() for tid in seen_token_ids if tid is not None]
    now = utc_ts()
    filt = {
        "collection_uid": collection_uid,
        f"markets.{market}.is_listed": True,
        "token_id": {"$nin": seen_list},
    }
    update = {"$set": {f"markets.{market}.is_listed": False, f"markets.{market}.delisted_at": now, "updated_at": now}}
    res = await nfts_collection.update_many(filt, update)
    return {"matched": res.matched_count, "modified": res.modified_count}


async def reset_market_state_for_collection(collection_uid: str, market: str) -> dict:
    """
    Remove/clear markets.<market> state for all NFTs in a collection.
    Use before a full rewrite from the first parser to avoid slow delisting.
    Returns basic stats {matched, modified}.
    """
    now = utc_ts()
    filt = {"collection_uid": collection_uid, f"markets.{market}": {"$exists": True}}
    update = {"$unset": {f"markets.{market}": ""}, "$set": {"updated_at": now}}
    res = await nfts_collection.update_many(filt, update)
    return {"matched": res.matched_count, "modified": res.modified_count}


# --- Model-scoped reset for a specific model in a collection ---
async def reset_market_state_for_model(collection_uid: str, model: str, market: str = "portals") -> dict:
    """
    Remove/clear markets.<market> state for all NFTs in a *specific model* of a collection.
    Use right before writing a fresh set for that model (only if you have >0 new items).
    Returns basic stats {matched, modified}.
    """
    now = utc_ts()
    # Match NFTs by collection + market-present + model. Prefer flattened `model`,
    # but also support legacy traits[] fallback.
    filt = {
        "collection_uid": collection_uid,
        f"markets.{market}": {"$exists": True},
        "$or": [
            {"model": model},
            {"traits": {"$elemMatch": {"type": "model", "value": model}}},
        ],
    }
    update = {"$unset": {f"markets.{market}": ""}, "$set": {"updated_at": now}}
    res = await nfts_collection.update_many(filt, update)
    return {"matched": res.matched_count, "modified": res.modified_count}


# --- Optional: index helpers for model-scoped operations ---
async def ensure_model_scoped_indexes():
    """Create helpful indexes for model-scoped resets/lookups (idempotent)."""
    # Speeds up queries on collection+model
    await nfts_collection.create_index(
        [("collection_uid", 1), ("model", 1)],
        name="nfts_collection_model_flat",
        background=True,
    )
    # If you frequently fall back to traits[] for model matching, this helps too
    await nfts_collection.create_index(
        [("collection_uid", 1), ("traits.type", 1), ("traits.value", 1)],
        name="nfts_collection_traits_kv",
        background=True,
    )


async def get_nft_by_id_or_name(gift_id: str):
    nft = await nfts_collection.find_one({"nft_id": gift_id})
    if nft:
        return nft
    if "-" in gift_id and not gift_id.startswith("EQ"):
        nft = await nfts_collection.find_one({"name": gift_id})
        if nft:
            return nft
    return await nfts_collection.find_one({"collection_address": gift_id})




async def get_all_subscriptions():
    return [doc async for doc in subscriptions_collection.find()]





# Updated NFT lookup helpers for new multi-market schema:

async def get_nfts_strict_match(model: str, symbol: str, backdrop: str, collection_name: str = None, market: str = "portals") -> list[dict]:
    collection_uid = None
    if collection_name:
        collection = await collections_collection.find_one({"name": {"$regex": f"^{collection_name}", "$options": "i"}})
        if not collection:
            return []
        collection_uid = collection["_id"]

    query = {
        "model": model,
        "symbol": symbol,
        "backdrop": backdrop,
        f"markets.{market}.price.amount": {"$exists": True}
    }
    if collection_uid:
        query["collection_uid"] = collection_uid

    cursor = nfts_collection.find(query)
    results = []
    async for nft in cursor:
        m = nft.get("markets", {}).get(market, {})
        nft["price"] = float(m.get("price", {}).get("amount", 0))
        nft["is_listed"] = m.get("is_listed", False)
        nft["url"] = m.get("url", "")
        results.append(nft)
    return results

async def get_nfts_loose_match(model: str, backdrop: str, collection_name: str = None, market: str = "portals") -> list[dict]:
    collection_uid = None
    if collection_name:
        collection = await collections_collection.find_one({"name": {"$regex": f"^{collection_name}", "$options": "i"}})
        if not collection:
            return []
        collection_uid = collection["_id"]

    query = {
        "model": model,
        "backdrop": backdrop,
        f"markets.{market}.price.amount": {"$exists": True}
    }
    if collection_uid:
        query["collection_uid"] = collection_uid

    cursor = nfts_collection.find(query)
    results = []
    async for nft in cursor:
        m = nft.get("markets", {}).get(market, {})
        nft["price"] = float(m.get("price", {}).get("amount", 0))
        nft["is_listed"] = m.get("is_listed", False)
        nft["url"] = m.get("url", "")
        results.append(nft)
    return results

async def get_nfts_by_params(model: str, symbol: str | None, backdrop: str, collection_name: str = None, market: str = "portals") -> list[dict]:
    collection_uid = None
    if collection_name:
        collection = await collections_collection.find_one({"name": {"$regex": f"^{collection_name}", "$options": "i"}})
        if not collection:
            return []
        collection_uid = collection["_id"]

    query = {
        "model": model,
        "backdrop": backdrop,
        f"markets.{market}.price.amount": {"$exists": True}
    }
    if symbol:
        query["symbol"] = symbol
    if collection_uid:
        query["collection_uid"] = collection_uid

    cursor = nfts_collection.find(query)
    results = []
    async for nft in cursor:
        m = nft.get("markets", {}).get(market, {})
        nft["price"] = float(m.get("price", {}).get("amount", 0))
        nft["is_listed"] = m.get("is_listed", False)
        nft["url"] = m.get("url", "")
        results.append(nft)
    return results



async def get_nfts_model_only(model: str, collection_name: str = None, market: str = "portals") -> list[dict]:
    # Fetch collection UID by name if provided
    collection_uid = None
    if collection_name:
        collection = await collections_collection.find_one({"name": {"$regex": f"^{collection_name}", "$options": "i"}})
        if not collection:
            return []
        collection_uid = collection["_id"]

    # Build query
    query = {
        "model": model,
        f"markets.{market}.price.amount": {"$exists": True}
    }
    if collection_uid:
        query["collection_uid"] = collection_uid

    cursor = nfts_collection.find(query)
    results = []
    async for nft in cursor:
        m = nft.get("markets", {}).get(market, {})
        nft["price"] = float(m.get("price", {}).get("amount", 0))
        nft["is_listed"] = m.get("is_listed", False)
        nft["url"] = m.get("url", "")
        results.append(nft)
    return results



# --- New flexible model-only NFT search helper ---
async def find_nfts_by_model(
    model: str,
    collection_slug: str | None = None,
    collection_uid: str | None = None,
    market: str = "portals",
    require_listed: bool = True,
) -> list[dict]:
    """Search NFTs by *model only* (case-insensitive), optionally scoped to a collection.
    DB-level guarantee: only NFTs with price in at least one market are returned if require_listed.
    """
    # Resolve collection_uid from slug, if needed
    if not collection_uid and collection_slug:
        coll = await collections_collection.find_one({"slug": collection_slug})
        if not coll:
            return []
        collection_uid = coll["_id"]

    # Build a tolerant listing filter: presence of price amount in at least one known market
    listing_filter = _price_exists_filter(market, require_listed)

    # Model-only filter supports both flattened and traits[] forms
    model_regex = {"$regex": f"^{re.escape(model)}$", "$options": "i"}
    model_filter = {
        "$or": [
            {"model": model_regex},
            {
                "traits": {
                    "$elemMatch": {
                        "type": "model",
                        "value": model_regex,
                    }
                }
            },
        ]
    }

    base_query = {**model_filter, **listing_filter}
    if collection_uid:
        base_query["collection_uid"] = collection_uid

    cursor = nfts_collection.find(base_query)

    results: list[dict] = []
    async for nft in cursor:
        _enrich_market_view(nft, market if market not in (None, "any", "*") else None)
        results.append(nft)
    results.sort(key=_min_any_market_price_in_doc)
    return results


# --- New: find_exact_then_symbolless ---
async def find_exact_then_symbolless(
    model: str,
    backdrop: str,
    symbol: str | None = None,
    collection_slug: str | None = None,
    collection_uid: str | None = None,
    market: str = "portals",
    require_listed: bool = True,
) -> list[dict]:
    """Return NFTs matching (in priority order):
    1) exact: model + backdrop + symbol
    2) symbolless: model + backdrop with an empty/missing symbol
    DB-level guarantee: only NFTs with price in at least one market are returned if require_listed.
    """
    # Resolve collection_uid from slug, if needed
    if not collection_uid and collection_slug:
        coll = await collections_collection.find_one({"slug": collection_slug})
        if not coll:
            return []
        collection_uid = coll["_id"]

    listing_filter = _price_exists_filter(market, require_listed)

    rx = lambda v: {"$regex": f"^{re.escape(v)}$", "$options": "i"}

    # --- Build EXACT filter (model + backdrop + symbol) ---
    exact_symbol = symbol if symbol is not None else ""

    exact_or = [
        {"$and": [
            {"model": rx(model)},
            {"backdrop": rx(backdrop)},
            {"symbol": rx(exact_symbol)},
        ]},
        {"traits": {"$all": [
            {"$elemMatch": {"type": "model", "value": rx(model)}},
            {"$elemMatch": {"type": "backdrop", "value": rx(backdrop)}},
            {"$elemMatch": {"type": "symbol", "value": rx(exact_symbol)}},
        ]}},
    ]

    exact_query = {"$or": exact_or}
    if collection_uid:
        exact_query["collection_uid"] = collection_uid
    if listing_filter:
        exact_query.update(listing_filter)

    exact_cursor = nfts_collection.find(exact_query)
    exact_results: list[dict] = []
    async for nft in exact_cursor:
        _enrich_market_view(nft, market if market not in (None, "any", "*") else None)
        exact_results.append(nft)
    exact_results.sort(key=_min_any_market_price_in_doc)

    if exact_results:
        return exact_results

    # --- Build SYMBOLLESS fallback (model + backdrop, empty/missing symbol) ---
    blank_vals = [None, "", "-", "—"]

    symbolless_or = [
        # flattened: symbol in blank values
        {"$and": [
            {"model": rx(model)},
            {"backdrop": rx(backdrop)},
            {"symbol": {"$in": blank_vals}},
        ]},
        # traits: model/backdrop match, and either no symbol trait or only blank-valued symbol trait
        {"$and": [
            {"traits": {"$all": [
                {"$elemMatch": {"type": "model", "value": rx(model)}},
                {"$elemMatch": {"type": "backdrop", "value": rx(backdrop)}},
            ]}},
            {"$or": [
                {"traits": {"$not": {"$elemMatch": {"type": "symbol"}}}},
                {"traits": {"$elemMatch": {"type": "symbol", "value": {"$in": blank_vals}}}},
            ]},
        ]},
    ]

    symbolless_query = {"$or": symbolless_or}
    if collection_uid:
        symbolless_query["collection_uid"] = collection_uid
    if listing_filter:
        symbolless_query.update(listing_filter)

    sl_cursor = nfts_collection.find(symbolless_query)
    symbolless_results: list[dict] = []
    async for nft in sl_cursor:
        _enrich_market_view(nft, market if market not in (None, "any", "*") else None)
        symbolless_results.append(nft)
    symbolless_results.sort(key=_min_any_market_price_in_doc)

    return symbolless_results


async def get_nfts_compatible(
        collection_address: str,
        model: str | None = None,
        backdrop: str | None = None,
        symbol: str | None = None,
        market: str = "portals",
        inject_legacy_fields: bool = True
) -> list[dict]:
    # Get collection UID
    collection = await collections_collection.find_one({"address": collection_address})
    if not collection:
        return []

    collection_uid = collection["_id"]

    query = {
        "collection_uid": collection_uid,
        f"markets.{market}.price.amount": {"$exists": True}
    }
    if model:
        query["model"] = model
    if backdrop:
        query["backdrop"] = backdrop
    if symbol:
        query["symbol"] = symbol

    # Query NFTs
    results = [n async for n in nfts_collection.find(query)]

    if inject_legacy_fields:
        for n in results:
            # Find the cheapest listing across all markets
            n["real_price"] = min(
                float(m.get("price", {}).get("amount", float("inf")))
                for m in n.get("markets", {}).values()
                if m.get("is_listed")
            )
            m = n.get("markets", {}).get(market, {})
            n["price"] = float(m.get("price", {}).get("amount", 0))
            n["is_listed"] = m.get("is_listed", False)
            n["url"] = m.get("url", "")

    return results


# Helper function: Find NFT _id by traits in a collection
async def find_nft_id_by_traits(
    collection_slug: str,
    model: str,
    backdrop: Optional[str] = None,
    symbol: Optional[str] = None
) -> Optional[str]:
    """
    Search for an NFT by collection_slug and traits (model, backdrop, symbol) and return its _id.
    """
    query = {
        "collection_uid": {"$regex": f"{collection_slug}$"},
        "traits": {
            "$all": [
                {"$elemMatch": {"type": "model", "value": model}}
            ]
        }
    }
    if backdrop:
        query["traits"]["$all"].append({"$elemMatch": {"type": "backdrop", "value": backdrop}})
    if symbol:
        query["traits"]["$all"].append({"$elemMatch": {"type": "symbol", "value": symbol}})

    doc = await nfts_collection.find_one(query, {"_id": 1})
    return doc["_id"] if doc else None


# Flexible NFT lookup by traits (progressive fallback, case-insensitive, $elemMatch, fallback logic)
async def find_nft_id_by_traits_flexible(
    model: str,
    backdrop: str = None,
    symbol: str = None,
    collection_uid: str = None,
    collection_slug: str = None
) -> list[dict]:
    """
    Flexible trait-based NFT search with fallback levels:
      1. model+backdrop+symbol
      2. model+backdrop
      3. model only
    Model matching is case-insensitive using regex; backdrop and symbol logic unchanged.
    """
    # If collection_uid is not provided but collection_slug is, resolve it
    if not collection_uid and collection_slug:
        collection_doc = await collections_collection.find_one({"slug": collection_slug})
        if not collection_doc:
            return []
        collection_uid = collection_doc["_id"]

    # Use the original model value for regex (not lowercased)
    model_value = model if model else None
    backdrop_value = backdrop if backdrop else None
    symbol_value = symbol if symbol else None

    # Build filter levels
    filters = []
    # Level 1: model+backdrop+symbol
    if model_value and backdrop_value and symbol_value:
        filters.append({
            "$all": [
                {
                    "$elemMatch": {
                        "type": "model",
                        "value": {"$regex": f"^{_re.escape(model_value)}$", "$options": "i"}
                    }
                },
                {"$elemMatch": {"type": "backdrop", "value": backdrop_value}},
                {"$elemMatch": {"type": "symbol", "value": symbol_value}}
            ]
        })
    # Level 2: model+backdrop
    if model_value and backdrop_value:
        filters.append({
            "$all": [
                {
                    "$elemMatch": {
                        "type": "model",
                        "value": {"$regex": f"^{_re.escape(model_value)}$", "$options": "i"}
                    }
                },
                {"$elemMatch": {"type": "backdrop", "value": backdrop_value}}
            ]
        })
    # Level 3: model only
    if model_value:
        filters.append({
            "$all": [
                {
                    "$elemMatch": {
                        "type": "model",
                        "value": {"$regex": f"^{_re.escape(model_value)}$", "$options": "i"}
                    }
                }
            ]
        })

    # Try each filter level and return the first non-empty result
    for traits_filter in filters:
        query = {
            "collection_uid": collection_uid,
            "traits": traits_filter
        }
        cursor = nfts_collection.find(query)
        results = []
        async for doc in cursor:
            results.append(doc)
        if results:
            return results
    return []


async def cleanup_empty_market_nfts(nfts_collection: AsyncIOMotorCollection):
    """
    Remove all NFTs from the collection that have no market data.
    i.e., where `markets` is missing, null, or an empty dict {}.
    """
    query = {
        "$or": [
            {"markets": {"$exists": False}},
            {"markets": None},
            {"markets": {}}
        ]
    }
    result = await nfts_collection.delete_many(query)
    print(f"[CLEANUP] Removed {result.deleted_count} NFTs with empty market data.")
    return result.deleted_count