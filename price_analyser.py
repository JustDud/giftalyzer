import pandas as pd
from data_collection.mongo import collections_collection, nfts_collection

# Load the CSV file
df = pd.read_csv('Backdrop_Price_Multipliers.csv')


def estimate_ton_price(nft_id, collection_address):
    nft = nfts_collection.find_one({"nft_id": nft_id, "collection_address": collection_address})
    collection = collections_collection.find_one({"address": collection_address})

    if not nft or not collection:
        raise ValueError("NFT or Collection not found in the database.")

    if 'floor' not in collection:
        raise KeyError(f"'floor' key not found in collection: {collection}")
    # DIVISION
    floor = float(collection["floor"]) / 1000 # Приводим к TON
    top_order_raw = collection.get("top_order")
    top_order = float(top_order_raw) if top_order_raw is not None else 0.0
    volume = float(collection["volume"])
    rarity = int(nft["rarity"])
    price = float(nft["price"])
    if 'backdrop' not in nft:
        raise KeyError(f"'backdrop' key not found in NFT: {nft}")
    backdrop = nft["backdrop"]

    print("FLOOR VALUE:", floor)
    print("COLLECTION:", collection)
    print("NFT:", nft)

    # 1. Мультипликатор фона
    row = df[df['backdrop'] == backdrop]
    backdrop_multiplier = float(row['price_multiplier'].values[0]) if not row.empty else 1.0

    # 2. Буст редкости (например, если rarity < 10% всех — добавим 10%)
    rarity_boost = 0.1 if rarity < 200000 else 0.0

    # 3. Буст ликвидности (если volume > 50k)
    liquidity_boost = 0.05 if volume > 50000 else 0.0

    # 4. Пенальти за оверпрайс
    # DIVISION
    overpricing_penalty = 0.1 if price > top_order / 1000 else 0.0

    # Финальная оценка
    estimated_price = floor * backdrop_multiplier * (1 + rarity_boost + liquidity_boost - overpricing_penalty)
    return round(estimated_price, 2)
