import pandas as pd
from mongo import collections_collection, nfts_collection
import os
import requests
import math

csv_path = os.path.join(os.path.dirname(__file__), 'Backdrop_Price_Multipliers.csv')
df = pd.read_csv(csv_path)


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

    return {
        "name": nft.get("name", "Unknown"),
        "symbol": nft.get("symbol", "Unknown"),
        "model": nft.get("model", "Unknown"),
        "background": nft.get("backdrop", "Unknown"),
        "market": nft.get("market", "Unknown"),
        "price": float(nft.get("price", 0)),
        "last_sale": float(nft.get("last_sale", 0)) if nft.get("last_sale") is not None else float(nft.get("price", 0)),
        "rarity": int(nft.get("rarity", 9999)),
        "max_rarity": int(collection.get("max_rarity", int(collection.get("supply", 2800)) * 0.9)),
        "floor": float(collection["floor"]),
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
    last_sale = data["last_sale"]
    owners = data["owners"]
    supply = data["supply"]
    max_rarity = data["max_rarity"]

    # Расчет оценочной цены
    estimated_price = calculate_nft_price_final_optimized(
        price=price,
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


def calculate_nft_price_final_optimized(price, last_sale, rarity, max_rarity, floor, top_order, volume, owners, supply):
    """
    Упрощённая формула оценки цены NFT без мультипликаторов атрибутов.

    Параметры:
    - price: Текущая цена (TON)
    - last_sale: Последняя продажа (TON)
    - rarity: Ранг редкости NFT
    - max_rarity: Максимальный ранг редкости в коллекции
    - floor: Минимальная цена коллекции (TON)
    - top_order: Максимальный ордер (TON)
    - volume: Объем торгов за 7 дней (TON)
    - owners: Количество владельцев
    - supply: Общее количество NFT в коллекции

    Возвращает:
    - Оценочная цена (TON)
    """
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

    # Корректировка для аномалий
    if abs(price - last_sale) / (price + last_sale) > 0.1:
        estimated_price = min(estimated_price, (price + last_sale) / 2 * 1.15)
    print(estimated_price)
    return min(max(estimated_price, lower_bound), upper_bound)
