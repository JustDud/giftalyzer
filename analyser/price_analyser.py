import pandas as pd
from mongo import collections_collection, nfts_collection
import os
import requests
import math

# csv_path = os.path.join(os.path.dirname(__file__), 'Backdrop_Price_Multipliers.csv')
# df = pd.read_csv(csv_path)


def convert_ton_to_usd(ton):
    url = "https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        rate = float(data["price"])
        return round(ton * rate, 2)
    except Exception as e:
        print(f"[ERROR] Binance API failed, using fallback: {e}")
        return round(ton * 2.0, 2)


def get_data(nft_id):
    nft = nfts_collection.find_one({"nft_id": nft_id})
    if not nft:
        raise ValueError("NFT not found in the database.")

    collection_address = nft.get("collection_address")
    if not collection_address:
        raise ValueError("Collection address not found in NFT data.")

    collection = collections_collection.find_one({"address": collection_address})
    if not collection:
        raise ValueError("Collection not found in the database.")

    if 'floor' not in collection:
        raise KeyError(f"'floor' key not found in collection: {collection}")

    top_order_raw = collection.get("top_order")
    floor_raw = collection.get("floor")

    if top_order_raw is None and floor_raw is None:
        raise ValueError("Neither top_order nor floor is available in collection.")

    top_order = float(top_order_raw if top_order_raw is not None else floor_raw)
    floor = float(collection["floor"])
    return {
        "name": nft.get("name", "Unknown"),
        "symbol": nft.get("symbol", "Unknown"),
        "model": nft.get("model", "Unknown"),
        "backdrop": nft.get("backdrop", "Unknown"),
        "market": nft.get("market", "Unknown"),
        "price": float(str(nft.get("price", "0")).replace(",", "") or 0),
        "last_sale": float(str(nft.get("last_sale", nft.get("price", "0"))).replace(",", "") or 0),
        "rarity": int(str(nft.get("rarity", "9999")).replace(",", "") or 9999),
        "max_rarity": int(collection.get("max_rarity", int(collection.get("supply", 2800)) * 0.9)),
        "floor": floor,
        "top_order": top_order,
        "volume": float(collection.get("volume", 0)),
        "owners": int(collection.get("owners", 1)),
        "supply": int(collection.get("supply", 2800)),
        "collection_address": collection_address
    }


def estimate_ton_price(nft_id):
    """
    Оценивает цену NFT в TON на основе упрощённой формулы.

    Параметры:
    - nft_id: Идентификатор NFT

    Возвращает:
    - Оценочная цена (TON), округлённая до 2 знаков
    """
    data = get_data(nft_id)

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

    # Расчет оценочной цены
    estimated_price = calculate_nft_price_final_optimized(
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


def calculate_nft_price_final_optimized(price, backdrop, last_sale, rarity, max_rarity, floor, top_order, volume, owners, supply):
    # Provided backdrop multipliers
    backdrop_multipliers = {
        'Onyx Black': 4.79,  # low confidence (4 NFTs)
        'Satin Gold': 4.28,
        'Orange': 3.23,
        'Burgundy': 2.76,
        'French Violet': 1.12,  # low confidence (3 NFTs)
        'Mexican Pink': 1.30,  # low confidence (2 NFTs)
        'Coral Red': 1.72,
        'Azure Blue': 1.11,
        'Rifle Green': 1.68,
        'Seal Brown': 1.27,
        'Chocolate': 0.95,
        'Cappuccino': 0.92,
        'Gunship Green': 0.89,
        'Desert Sand': 0.84,
        'Battleship Grey': 0.82,
        'Jade Green': 0.75,
        'Silver Blue': 0.73,
        'Roman Silver': 0.73,
        'Turquoise': 0.73,
        'Midnight Blue': 0.73,
        'Malachite': 0.69,
        'Persimmon': 0.69,
        'Platinum': 0.57,
        'Mystic Pearl': 0.57,
        'Khaki Green': 0.41,
        'Indigo Dye': 0.42,
        'Lavender': 0.40,
        'Rosewood': 0.32,
        'Pine Green': 0.28,
        'Mustard': 0.16,
        'Raspberry': 0.49,
        'Mint Green': 0.10,
        'Grape': 0.09,
        'Pacific Cyan': 0.10,
        'Dark Lilac': 0.10,
        'Pistachio': 0.10,
        'Carrot Juice': 0.07,
        'Hunter Green': 0.06,
        'Dark Green': 0.06,
        'Electric Indigo': 0.07,
        'English Violet': 0.05,
        'Cobalt Blue': 0.05,
        'French Blue': 0.05,
        'Emerald': 0.05,
        'Navy Blue': 0.12,
        'Shamrock Green': 0.09,
        'Fandango': 0.09,
        'Chestnut': 0.10,
        'Light Olive': 0.06,
        'Ivory White': 0.04,
        'Cyberpunk': 0.19,
        'Tactical Pine': 0.09,
        'Purple': 0.03,
        'Strawberry': 0.03,
        'Sky Blue': 0.00,
        'Steel Grey': 0.00,
        'Neon Blue': 0.00,
        'Pure Gold': 0.00,
        'Electric Purple': 0.08,
        'Burnt Sienna': 0.02,
        'Celtic Blue': 0.02,
        'Fire Engine': 0.02,
        'Tomato': 0.01,
        'Deep Cyan': 0.00,  # low confidence (4 NFTs)
        'Feldgrau': 0.00,  # low confidence (4 NFTs)
        'Gunmetal': 0.08,  # low confidence (2 NFTs)
        'Pacific Green': 0.00,
        'Lemongrass': 0.00,
        'Marine Blue': 0.00,  # low confidence (5 NFTs)
        'Copper': 0.00,
        'Camo Green': 0.00,
        'Black': 0.00,  # отсутствует в данных
        'Carmine': 0.00,  # отсутствует в данных
        'Ranger Green': 0.00  # отсутствует в данных
    }

    # BasePrice: уменьшенное влияние разрыва
    price_gap = min(0.2 * abs(price - last_sale) / (price + last_sale), 0.05)
    base_price = max(price, last_sale) * (1 + floor / (supply * max(15, supply / 1000)) + price_gap)

    # RarityFactor: усиленный, чтобы компенсировать отсутствие AttributeFactor
    rarity_factor = min(max(1.5 / (rarity / max_rarity), 1.2), 2.0)

    # MarketLiquidityFactor: сбалансированный
    market_liquidity_factor = min((volume / (owners * max(floor, top_order))) * 0.02 + 0.7, 0.9)

    # Расчет оценочной цены
    estimated_price = base_price * rarity_factor * market_liquidity_factor

    # Ограничения
    lower_bound = (price + last_sale) / 2 * 0.98
    upper_bound = price * 1.2

    if backdrop in backdrop_multipliers and backdrop_multipliers[backdrop] > 0.0:
        multiplier = backdrop_multipliers[backdrop]
        print(f"Applying backdrop multiplier for {backdrop}: {multiplier}")
        estimated_price *= multiplier
    else:
        print(f"No valid multiplier for backdrop {backdrop}, using original formula")

    # Корректировка для аномалий
    if abs(price - last_sale) / (price + last_sale) > 0.1:
        estimated_price = min(estimated_price, (price + last_sale) / 2 * 1.15)
    print(f"Actual Price: {price}")
    #print(f"Estimated Price: {estimated_price}")

    return min(max(estimated_price, lower_bound), upper_bound)
