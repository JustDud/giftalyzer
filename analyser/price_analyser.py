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




import numpy as np
import pandas as pd
import re
from typing import Optional, Dict, Any
from typing import Tuple

# ---------- ПАРАМЕТРЫ U-shape ----------
SMILE = dict(
    SPREAD=0.20,        # полу-размах премии: ±20%
    CENTER_POWER=0.60,  # <1 усиливает хвосты (U-shape), >1 делает «колокол»
    SCALE_Q=0.95,       # квантили для нормирования масштаба
    USE_LOG=True        # True: log(F_adj), False: F_adj-1
)

# Управление доп. множителями и шумом
USE_RARITY_MARKET = True   # включить фактор редкости/рынка в финальной оценке
USE_NOISE = False          # добавить шум ±20% на конце (для детерминизма держим False)
NOISE_SEED: Optional[int] = 42  # сид шума (None → каждый раз новый)

# Кандидаты имён колонок (auto-detect)
PRICE_CANDIDATES      = ["salePrice","saleprice","price_ton","price","current_price","amount_price",
                         "last_sale_price","executed_price","execution_price"]
COLLECTION_CANDIDATES = ["collection_uid","collection","modelName","modelname","CollectionId",
                         "collectionUid","collectionid","model","series","set"]
BACKDROP_CANDIDATES   = ["backdropName","backdrop_name","background","bg","backdrop","backdropname","bg_name"]

# ---------- FIXED BACKDROP MULTIPLIERS (K_b) ----------
BACKDROP_MULTIPLIERS: Dict[str, float] = {
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




# Assumes in scope:
# from price_analyser import get_data, compute_estimates
async def estimate_u_shape_by_id(nft_id: str) -> float:
    """
    Fetches NFT data via get_data(nft_id), maps to the columns expected by the U-shape estimator,
    runs compute_estimates, and returns (estimate_in_ton, full_output_df).
    Uses ALL inputs the estimator supports: price, collection_uid, backdrop, rarity, maxRarity, volume, supply.
    """
    data = await get_data(nft_id)

    # Hard requirements
    price = float(data.get("price", 0) or 0.0)
    collection_uid = data.get("collection_address")
    if not collection_uid:
        raise ValueError("collection_address is missing in get_data(...) result.")

    # Optional enhancers (coerced with safe defaults)
    row = {
        "price": price,
        "collection_uid": str(collection_uid),                   # REQUIRED
        "backdrop": data.get("backdrop"),                        # optional
        "rarity": float(data.get("rarity", 1000) or 1000),       # optional
        "maxRarity": float(data.get("max_rarity", 1000) or 1000),# NOTE: camelCase expected by model
        "volume": float(data.get("volume", 1000) or 1000),       # optional
        "supply": float(data.get("supply", 1000) or 1000),       # optional
    }

    df = pd.DataFrame([row])

    out = compute_estimates(
        df,
        price_col="price",
        collection_col="collection_uid",
        backdrop_col="backdrop",
        add_columns=True,
    )

    # Prefer final deterministic estimate if rarity/market factors are enabled
    est = float(
        out.loc[0, "est_price_final_det"]
        if "est_price_final_det" in out.columns
        else out.loc[0, "est_price_smile"]
    )
    return round(est, 2)


# ===================== ВНУТРЕННИЕ УТИЛИТЫ =====================
def _safe_scale(arr: pd.Series, q: float) -> float:
    s = float(np.nanquantile(np.abs(arr.astype(float)), q)) if arr.size else 1.0
    if not np.isfinite(s) or s <= 0:
        s = float(np.nanmedian(np.abs(arr.astype(float)))) or 1.0
    return s

def _prem_with_known_scale(F_adj: float, scale: float,
                           spread: float, center_power: float, use_log: bool) -> float:
    if not np.isfinite(F_adj) or F_adj <= 0:
        return 0.0
    z = np.log(max(F_adj, 1e-12)) if use_log else (F_adj - 1.0)
    x = z / (scale if (scale and scale > 0) else 1.0)
    out = np.sign(x) * (abs(x) ** center_power)
    prem = float(np.clip(spread * out, -spread, spread))
    return prem if np.isfinite(prem) else 0.0

def _norm_name(s: Any) -> str:
    if s is None or (isinstance(s, float) and np.isnan(s)): return ""
    s = str(s).strip().lower()
    return re.sub(r"[^a-z0-9]+","", s)

def _pick_col(df: pd.DataFrame, candidates) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None

def _pick_price_col(df: pd.DataFrame) -> Optional[str]:
    for c in PRICE_CANDIDATES:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            if s.gt(0).any():
                return c
    return None

# ===================== КОНТЕКСТ ДЛЯ ROW-ФУНКЦИИ =====================
_CTX: Optional[Dict[str, Any]] = None

def init_smile_context(df: pd.DataFrame,
                       price_col: Optional[str] = None,
                       collection_col: Optional[str] = None,
                       backdrop_col: Optional[str] = None,
                       use_noise: bool = USE_NOISE,
                       noise_seed: Optional[int] = NOISE_SEED) -> Dict[str, Any]:
    """
    Готовит всё для calculate_estimated_price(row):
      - auto-detect колонок (если не заданы)
      - считает F_raw (если нет), K_c по коллекции, K_b по бэкдропу
      - считает общий scale по F_adj для U-shape
    """
    global _CTX
    df = df.copy()

    price_col      = price_col or _pick_price_col(df)
    collection_col = collection_col or _pick_col(df, COLLECTION_CANDIDATES)
    backdrop_col   = backdrop_col or _pick_col(df, BACKDROP_CANDIDATES)

    if price_col is None:
        raise RuntimeError("Не нашёл ценовую колонку с >0 значений.")
    if collection_col is None:
        raise KeyError("Не нашёл колонку коллекции среди: " + ", ".join(COLLECTION_CANDIDATES))

    price = pd.to_numeric(df[price_col], errors="coerce")
    df    = df.loc[price.gt(0)].copy()
    if df.empty:
        raise RuntimeError("Нет положительных цен — нечего оценивать.")

    # F_raw
    if "F_raw" in df.columns:
        F_raw = pd.to_numeric(df["F_raw"], errors="coerce")
    else:
        med_by_col = df.groupby(collection_col)[price_col].median()
        F_raw = price.loc[df.index] / df[collection_col].map(med_by_col)

    # K_c
    if "K_c" in df.columns:
        Kc_ser = pd.to_numeric(df["K_c"], errors="coerce")
        Kc_map = (df[[collection_col]]
                  .assign(K_c=Kc_ser)
                  .dropna()
                  .drop_duplicates(subset=[collection_col])
                  .set_index(collection_col)["K_c"]
                  .to_dict())
    else:
        Kc_map = ((F_raw.groupby(df[collection_col]).median()).replace(0, np.nan) ** -1.0).to_dict()
        Kc_ser = df[collection_col].map(Kc_map).fillna(1.0)

    # K_b
    bd_lookup = { _norm_name(k): v for k, v in BACKDROP_MULTIPLIERS.items() }
    if backdrop_col:
        Kb_ser = df[backdrop_col].map(lambda x: bd_lookup.get(_norm_name(x), 1.0))
    else:
        Kb_ser = pd.Series(1.0, index=df.index)

    # Масштаб для U-shape на всём датасете
    F_adj_all = pd.to_numeric(F_raw, errors="coerce") \
               * pd.to_numeric(Kc_ser, errors="coerce") \
               * pd.to_numeric(Kb_ser, errors="coerce")
    z = np.log(F_adj_all.clip(lower=1e-12)) if SMILE["USE_LOG"] else (F_adj_all - 1.0)
    scale = _safe_scale(z, SMILE["SCALE_Q"])

    rng = np.random.default_rng(noise_seed) if (use_noise and noise_seed is not None) else np.random.default_rng()

    _CTX = dict(
        price_col=price_col,
        collection_col=collection_col,
        backdrop_col=backdrop_col,  # может быть None
        med_by_col= df.groupby(collection_col)[price_col].median().to_dict(),
        Kc_map=Kc_map,
        bd_lookup=bd_lookup,
        scale=scale,
        use_noise=use_noise,
        rng=rng
    )
    return _CTX

# ===================== ТВОЯ ROW-ФУНКЦИЯ =====================
def calculate_estimated_price(row: pd.Series) -> float:
    """
    Финальная оценка:
      1) U-shape премия по F_adj = F_raw * K_c * K_b (масштаб из init_smile_context)
      2) (опц.) rarity/market множители
      3) (опц.) шум ±20%
    """
    global _CTX
    if _CTX is None:
        raise RuntimeError("Сначала вызови init_smile_context(df, ...).")

    price = row.get(_CTX["price_col"], np.nan)
    if price is None or not np.isfinite(price) or price <= 0:
        return np.nan

    col = row.get(_CTX["collection_col"], None)
    bd  = row.get(_CTX["backdrop_col"], None) if _CTX["backdrop_col"] else None

    # F_raw
    if "F_raw" in row and np.isfinite(row["F_raw"]):
        F_raw = float(row["F_raw"])
    else:
        med = _CTX["med_by_col"].get(col, price)
        F_raw = float(price) / float(med if (med and med > 0) else price)

    # K_c
    K_c = float(row["K_c"]) if ("K_c" in row and np.isfinite(row["K_c"])) else float(_CTX["Kc_map"].get(col, 1.0))

    # K_b
    K_b = float(_CTX["bd_lookup"].get(_norm_name(bd), 1.0)) if bd is not None else 1.0

    # U-shape премия
    F_adj = F_raw * K_c * K_b
    prem = _prem_with_known_scale(
        F_adj, _CTX["scale"],
        spread=SMILE["SPREAD"],
        center_power=SMILE["CENTER_POWER"],
        use_log=SMILE["USE_LOG"]
    )
    est = float(price) * (1.0 + prem)

    # rarity / market
    if USE_RARITY_MARKET:
        def _val(name: str, default: float) -> float:
            v = row.get(name, default)
            try:
                return float(v)
            except Exception:
                return float(default)

        rarity     = _val('rarity',    1000.0)
        max_rarity = max(_val('maxRarity', 1000.0), 1e-9)
        volume     = _val('volume',    1000.0)
        supply     = max(_val('supply',    1000.0), 1.0)

        rratio = max(rarity / max_rarity, 1e-3)
        rarity_factor  = np.clip(1.5 / rratio, 1.2, 2.0)
        market_factor  = min((volume / supply) * 0.01 + 0.7, 0.9)
        est *= float(rarity_factor * market_factor)

    # шум ±20%
    if _CTX["use_noise"]:
        noise = _CTX["rng"].uniform(-0.2, 0.2)
        est *= (1.0 + float(noise))

    return round(est, 2)

# ===================== БАТЧ-ХЕЛПЕР (опционально) =====================
def compute_estimates(df: pd.DataFrame,
                      price_col: Optional[str] = None,
                      collection_col: Optional[str] = None,
                      backdrop_col: Optional[str] = None,
                      add_columns: bool = True) -> pd.DataFrame:
    """
    Пакетный расчёт поверх DataFrame (дет. U-shape + опц. rarity/market).
    Возвращает DataFrame с:
      prem_frac, premium_pct, est_price_smile,
      est_price_final_det (если USE_RARITY_MARKET=True),
      F_raw, K_c, K_b.
    """
    ctx = init_smile_context(df, price_col=price_col, collection_col=collection_col, backdrop_col=backdrop_col,
                             use_noise=False, noise_seed=NOISE_SEED)

    out = df.copy()

    # F_raw / K_c / K_b если отсутствуют
    price = pd.to_numeric(out[ctx["price_col"]], errors="coerce")
    med_by_col = pd.Series(ctx["med_by_col"])
    if "F_raw" not in out.columns:
        out["F_raw"] = price / out[ctx["collection_col"]].map(med_by_col)
    if "K_c" not in out.columns:
        out["K_c"] = out[ctx["collection_col"]].map(ctx["Kc_map"]).fillna(1.0)
    if "K_b" not in out.columns:
        if ctx["backdrop_col"]:
            out["K_b"] = out[ctx["backdrop_col"]].map(lambda x: ctx["bd_lookup"].get(_norm_name(x), 1.0)).fillna(1.0)
        else:
            out["K_b"] = 1.0

    # Премия и цены (векторно)
    F_adj = (pd.to_numeric(out["F_raw"], errors="coerce") *
             pd.to_numeric(out["K_c"], errors="coerce") *
             pd.to_numeric(out["K_b"], errors="coerce")).clip(lower=1e-12)
    z = np.log(F_adj) if SMILE["USE_LOG"] else (F_adj - 1.0)
    x = (z / (ctx["scale"] if ctx["scale"] > 0 else 1.0)).astype(float)
    prem_frac = (SMILE["SPREAD"] * np.sign(x) * (np.abs(x) ** SMILE["CENTER_POWER"])).clip(-SMILE["SPREAD"], SMILE["SPREAD"])
    out["prem_frac"] = prem_frac.fillna(0.0)
    out["premium_pct"] = (out["prem_frac"] * 100).round(2)
    out["est_price_smile"] = (pd.to_numeric(out[ctx["price_col"]], errors="coerce") * (1.0 + out["prem_frac"])).round(2)

    if USE_RARITY_MARKET:
        def col_or_default(df_local, name, default_val):
            if name in df_local.columns:
                return pd.to_numeric(df_local[name], errors="coerce").fillna(default_val).astype(float)
            else:
                return pd.Series(float(default_val), index=df_local.index)
        rarity = col_or_default(out, "rarity",    1000.0)
        maxr = col_or_default(out, "maxRarity", 1000.0)
        volume = col_or_default(out, "volume",    1000.0)
        supply = col_or_default(out, "supply",    1000.0)
        rratio = np.maximum(rarity / np.maximum(maxr, 1e-9), 1e-3)
        rarity_factor = np.clip(1.5 / rratio, 1.2, 2.0)
        market_factor = np.minimum((volume / np.maximum(supply, 1.0)) * 0.01 + 0.7, 0.9)
        mult = (rarity_factor * market_factor).astype(float)
        out["est_price_final_det"] = (out["est_price_smile"] * mult).round(2)

    return out if add_columns else out[["est_price_smile"] + (["est_price_final_det"] if USE_RARITY_MARKET else [])]