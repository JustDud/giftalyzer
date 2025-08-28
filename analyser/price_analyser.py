from mongo import collections_collection, nfts_collection
import requests
import asyncio
import numpy as np
import math

# csv_path = os.path.join(os.path.dirname(__file__), 'Backdrop_Price_Multipliers.csv')
# df = pd.read_csv(csv_path)


# ====== Настройки U-shape (можно подправить под свои цели) ======
SMILE_SPREAD = 0.20  # полу-размах премии (±20%)
SMILE_CENTER_POWER = 0.65  # <1 усиливает хвосты (U-образность)
SMILE_SCALE_Z = math.log1p(0.15)  # масштаб по |log(F)|; 15% dev ~ 20% премия

# Мягкие (и центрированные на 1.0) факторы редкости/рынка
GAMMA_RARITY = 0.40  # амплитуда влияния редкости: итоговый K_r ∈ [0.8; 1.2]
GAMMA_MARKET = 0.30  # амплитуда влияния рынка:   итоговый K_m ∈ [0.85; 1.15]

# 🔹 Умеренные мультипликаторы бекдропов (0.97–1.10)
_backdrop_multipliers_raw = {
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
# Рецентр к медиане = 1.0
_bd_vals   = np.array(list(_backdrop_multipliers_raw.values()), dtype=float)
_bd_med    = float(np.median(_bd_vals)) if np.isfinite(_bd_vals).all() else 1.0
backdrop_multipliers = {k: (v / (_bd_med if _bd_med>0 else 1.0)) for k, v in _backdrop_multipliers_raw.items()}


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


async def estimate_u_shape_by_id(nft_id: str) -> float:
    """
    Returns a TON estimate using the deterministic U-shape model.
    Relies only on primitives (no DataFrames needed).
    """
    data = await get_data(nft_id)

    # Extract inputs with safe defaults
    price = float(data.get("price", 0) or 0.0)
    last_sale = float(data.get("last_sale", 0) or 0.0)
    rarity = float(data.get("rarity", 0) or 0.0)
    max_rarity = float(data.get("max_rarity", 1) or 1.0)
    floor = float(data.get("floor", 0) or 0.0)
    top_order = float(data.get("top_order", 0) or 0.0)
    volume = float(data.get("volume", 0) or 0.0)
    supply = float(data.get("supply", 1) or 1.0)
    backdrop = data.get("backdrop")

    est = calculate_nft_price_final_optimized(
        price=price,
        last_sale=last_sale,
        rarity=rarity,
        max_rarity=max_rarity,
        floor=floor,
        top_order=top_order,
        volume=volume,
        supply=supply,
        backdrop=backdrop,
    )
    return float(est)


def _safe(v, default):
    try:
        x = float(v)
        return x if np.isfinite(x) else float(default)
    except Exception:
        return float(default)

def _choose_ref(price, last_sale, floor, top_order):
    """Референтная цена для F_raw (приоритет: last_sale → floor → top_order → price)."""
    for x in (last_sale, floor, top_order, price):
        x = _safe(x, np.nan)
        if x > 0:
            return x
    return _safe(price, 1.0)

def _k_backdrop(backdrop: str) -> float:
    if not backdrop:
        return 1.0
    return float(backdrop_multipliers.get(str(backdrop), 1.0))

def _k_rarity(rarity, max_rarity) -> float:
    """
    Центрированный на 1.0 коэффициент редкости:
    r_norm = 1 - rarity/max_rarity  (в интервале [0,1], больше — редче)
    K_r = 1 + GAMMA_RARITY * (r_norm - 0.5)*2  ∈ [1-G, 1+G]
    """
    r  = _safe(rarity, 0.0)
    mr = max(_safe(max_rarity, 1.0), 1.0)
    r_norm = 1.0 - min(max(r / mr, 0.0), 1.0)   # 1.0 -> самый редкий
    return float(1.0 + GAMMA_RARITY * (r_norm - 0.5) * 2.0)

def _k_market(volume, supply) -> float:
    """
    Мягкий рыночный коэффициент, центрированный на 1.0.
    Берём оборот на штуку t = volume/supply, затем
    p = log1p(t) / log1p(5000) ∈ [0,1] (нормализация),
    K_m = 1 + GAMMA_MARKET * (p - 0.5)*2 ∈ [1-G, 1+G].
    """
    vol = max(_safe(volume, 0.0), 0.0)
    sup = max(_safe(supply, 1.0), 1.0)
    t = vol / sup
    p = np.log1p(t) / np.log1p(5000.0)
    p = float(min(max(p, 0.0), 1.0))
    return float(1.0 + GAMMA_MARKET * (p - 0.5) * 2.0)

def _u_shape_premium_frac(F_adj: float) -> float:
    """
    Премия в долях (±SMILE_SPREAD) от приведённого мультипликатора F_adj.
    x = log(F_adj)/SMILE_SCALE_Z; prem = SPREAD * sign(x)*|x|^CENTER_POWER, затем clip.
    """
    F = max(float(F_adj), 1e-12)
    x = math.log(F) / (SMILE_SCALE_Z if SMILE_SCALE_Z > 0 else 1.0)
    val = math.copysign(abs(x) ** SMILE_CENTER_POWER, x)
    prem = SMILE_SPREAD * val
    return float(np.clip(prem, -SMILE_SPREAD, SMILE_SPREAD))

def calculate_nft_price_final_optimized(price, last_sale, rarity, max_rarity,
                                        floor, top_order, volume, supply, backdrop):
    """
    Финальная оценочная цена (TON), детерминированно и с жёстким капом ±20% от текущей price.

    Внутри:
      • референтная цена: last_sale → floor → top_order → price
      • F_raw = price / ref
      • K_b (бекдроп, рецентр к медиане = 1.0)
      • K_r (редкость, центрирован на 1.0, мягко: ±40%)
      • K_m (рынок, центрирован на 1.0, мягко: ±30%)
      • F_adj = F_raw * K_b * K_r * K_m
      • премия U-shape (±20%) → итог всегда в [-20%; +20%] от price
    """

    P = _safe(price, 0.0)
    if P <= 0:
        return 0.0

    ref = _choose_ref(P, last_sale, floor, top_order)

    F_raw = P / max(ref, 1e-9)
    K_b = _k_backdrop(backdrop)
    K_r = _k_rarity(rarity, max_rarity)
    K_m = _k_market(volume, supply)

    F_adj = F_raw * K_b * K_r * K_m
    prem_frac = _u_shape_premium_frac(F_adj)  # в долях от price
    est = P * (1.0 + prem_frac)

    # На всякий случай жёсткий кап (избыточно, но безопасно)
    lo, hi = P * (1.0 - SMILE_SPREAD), P * (1.0 + SMILE_SPREAD)
    est = float(min(max(est, lo), hi))
    return round(est, 2)