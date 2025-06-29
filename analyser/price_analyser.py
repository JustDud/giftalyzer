import pandas as pd
from mongo import collections_collection, nfts_collection
import os
import math

csv_path = os.path.join(os.path.dirname(__file__), 'Backdrop_Price_Multipliers.csv')
df = pd.read_csv(csv_path)


def estimate_ton_price(nft_id):
    nft = nfts_collection.find_one({"nft_id": nft_id})
    if not nft:
        raise ValueError("NFT not found.")
    collection_address = nft.get("collection_address")
    if not collection_address:
        raise ValueError("Collection address missing.")
    collection = collections_collection.find_one({"address": collection_address})
    if not collection:
        raise ValueError("Collection not found.")

    print(f"[DEBUG] NFT data: {nft}")
    print(f"[DEBUG] Collection data: {collection}")

    floor_raw = collection.get("floor")
    top_order_raw = collection.get("top_order")
    volume_raw = collection.get("volume")
    price_raw = nft.get("price")
    last_sale_raw = nft.get("last_sale")

    print(f"[DEBUG] Raw values - floor: {floor_raw}, top_order: {top_order_raw}, volume: {volume_raw}, price: {price_raw}, last_sale: {last_sale_raw}")

    floor = float(floor_raw or 0)
    top_order = float(top_order_raw or 0)
    volume = float(volume_raw or 0)
    rarity = int(nft["rarity"])
    price = float(price_raw or 0)
    last_sale = float(last_sale_raw or 0)
    backdrop = nft.get("backdrop", "Unknown")

    # 1. Ограниченный floor (не выше 110% от top_order)
    if top_order > 0:
        floor = min(floor, top_order * 1.1)

    # 2. Мультипликатор фона
    row = df[df['backdrop'] == backdrop]
    backdrop_multiplier = float(row['price_multiplier'].values[0]) if not row.empty else 1.0

    # 3. Boost редкости: чем меньше значение rarity, тем выше буст
    rarity_score = max(0.0, 1 - rarity / 2800000)
    rarity_boost = rarity_score * 0.2

    # 4. Boost ликвидности (логарифмически, ограничен 5%)
    liquidity_boost = min(math.log10(volume + 1) / 100, 0.05)

    # 5. Boost за наличие предыдущей продажи
    last_sale_boost = 0.05 if last_sale > 0 else 0.0

    # 6. Penalty за оверпрайс
    overpricing_penalty = 0.07 if top_order > 0 and price > top_order * 1.1 else 0.0

    # Финальная формула
    estimated_price = floor * backdrop_multiplier * (1 + rarity_boost + liquidity_boost + last_sale_boost - overpricing_penalty)
    return round(estimated_price, 2)