import numpy as np
import pandas as pd
from mongo import collections_collection, nfts_collection
import os
import requests
import math
import asyncio

# csv_path = os.path.join(os.path.dirname(__file__), 'Backdrop_Price_Multipliers.csv')
# df = pd.read_csv(csv_path)


async def convert_ton_to_usd(ton):
    if asyncio.iscoroutine(ton):
        ton = await ton
    url = "https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        rate = float(data["price"])
        return round(ton * rate, 2)
    except Exception as e:
        print(f"[ERROR] Binance API failed, using fallback: {e}")
        return round(ton * 2.0, 2)


async def get_data(nft_id):
    nft = await nfts_collection.find_one({
        "$or": [
            {"_id": nft_id},
            {"external_ids.portals.id": nft_id}
        ]
    })
    if not nft:
        raise ValueError("NFT not found in the database.")

    collection_uid = nft.get("collection_uid")
    if not collection_uid:
        raise ValueError("Collection UID not found in NFT data.")

    collection = await collections_collection.find_one({"_id": collection_uid})
    if not collection:
        raise ValueError("Collection not found in the database.")

    market_data = collection.get("markets", {}).get("portals", {})
    if 'floor_price' not in market_data:
        raise KeyError(f"'floor_price' key not found in collection: {collection}")

    traits = {t["type"]: t["value"] for t in nft.get("traits", [])}

    return {
        "name": nft.get("name", "Unknown"),
        "symbol": traits.get("symbol", "Unknown"),
        "model": traits.get("model", "Unknown"),
        "backdrop": traits.get("backdrop", "Unknown"),
        "market": "portals",
        "price": float(nft.get("markets", {}).get("portals", {}).get("price", {}).get("amount", 0)),
        "last_sale": float(nft.get("markets", {}).get("portals", {}).get("floor_price", {}).get("amount", 0)),
        "rarity": int(traits.get("rarity_per_mille", 9999)),
        "max_rarity": int(market_data.get("supply", 2800) * 0.9),
        "floor": float(market_data.get("floor_price", {}).get("amount", 0)),
        "top_order": float(market_data.get("floor_price", {}).get("amount", 0)),
        "volume": float(market_data.get("volume", {}).get("amount", 0)),
        "owners": int(market_data.get("owners", 1)),
        "supply": int(market_data.get("supply", 2800)),
        "collection_address": collection_uid,
    }


async def estimate_ton_price(nft_id):
    data = await get_data(nft_id)

    floor = data["floor"]
    top_order = data["top_order"]
    volume = data["volume"]
    rarity = data["rarity"]
    price = data["price"]
    backdrop = data["backdrop"]
    last_sale = data["last_sale"]
    owners = data["owners"]
    supply = data["supply"]
    max_rarity = data["max_rarity"]

    estimated_price = calculate_nft_price(
        price=price,
        backdrop=backdrop,
        last_sale=last_sale,
        rarity=rarity,
        max_rarity=max_rarity,
        floor=floor,
        top_order=top_order,
        volume=volume,
        owners=owners,
        supply=supply
    )

    return round(estimated_price, 2)


def calculate_nft_price(price, backdrop, last_sale, rarity, max_rarity, floor, top_order, volume, owners, supply):
    # Provided backdrop multipliers
    backdrop_multipliers = {
        'Amber': 1.00, 'Aquamarine': 1.07, 'Azure Blue': 1.02, 'Battleship Grey': 1.04,
        'Black': 1.10, 'Burgundy': 1.03, 'Burnt Sienna': 1.04, 'Camo Green': 1.02,
        'Cappuccino': 1.07, 'Caramel': 0.97, 'Carmine': 1.00, 'Carrot Juice': 1.04,
        'Celtic Blue': 1.02, 'Chestnut': 1.07, 'Chocolate': 0.97, 'Cobalt Blue': 1.04,
        'Copper': 1.02, 'Coral Red': 1.07, 'Cyberpunk': 0.97, 'Dark Green': 1.04,
        'Dark Lilac': 1.02, 'Deep Cyan': 1.07, 'Desert Sand': 0.97, 'Electric Indigo': 1.04,
        'Electric Purple': 1.02, 'Emerald': 1.07, 'English Violet': 0.97, 'Fandango': 1.04,
        'Feldgrau': 1.02, 'Fire Engine': 1.07, 'French Blue': 0.97, 'French Violet': 1.04,
        'Grape': 1.02, 'Gunmetal': 1.07, 'Gunship Green': 0.97, 'Hunter Green': 1.04,
        'Indigo Dye': 1.02, 'Ivory White': 1.07, 'Jade Green': 0.97, 'Khaki Green': 1.04,
        'Lavender': 1.02, 'Lemongrass': 1.07, 'Light Olive': 0.97, 'Malachite': 1.04,
        'Marine Blue': 1.02, 'Mexican Pink': 1.07, 'Midnight Blue': 0.97, 'Mint Green': 1.04,
        'Moonstone': 1.02, 'Mustard': 1.07, 'Mystic Pearl': 0.97, 'Navy Blue': 1.04,
        'Neon Blue': 1.02, 'Old Gold': 1.07, 'Onyx Black': 0.97, 'Orange': 1.04,
        'Pacific Cyan': 1.02, 'Pacific Green': 1.07, 'Persimmon': 0.97, 'Pine Green': 1.04,
        'Pistachio': 1.02, 'Platinum': 1.07, 'Pure Gold': 0.97, 'Purple': 1.04,
        'Ranger Green': 1.02, 'Raspberry': 1.07, 'Rifle Green': 0.97, 'Roman Silver': 1.04,
        'Rosewood': 1.02, 'Sapphire': 1.07, 'Satin Gold': 0.97, 'Seal Brown': 1.04,
        'Shamrock Green': 1.02, 'Silver Blue': 1.07, 'Sky Blue': 0.97, 'Steel Grey': 1.04,
        'Strawberry': 1.02, 'Tactical Pine': 1.07, 'Tomato': 0.97, 'Turquoise': 1.04
    }

    """
        Финальная формула оценки цены NFT:
        - Использует rarity, volume, supply и backdrop multipliers
        - last_sale и owners не участвуют
        - Динамический шум теперь ±20% для симметричного разброса
        """


    # Фактор редкости
    rarity_factor = min(max(1.5 / max(rarity / max_rarity, 0.001), 1.2), 2.0)
    # Фактор рынка (без owners)
    market_factor = min((volume / max(supply, 1)) * 0.01 + 0.7, 0.9)
    # Фактор бекдропа
    backdrop_factor = backdrop_multipliers.get(backdrop, 1.0)

    # Базовая цена
    estimated_price = price * rarity_factor * market_factor * backdrop_factor

    # Динамический шум ±20%
    noise = np.random.uniform(-0.2, 0.2)
    return round(estimated_price * (1 + noise), 2)

