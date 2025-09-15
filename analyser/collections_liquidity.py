import numpy as np
import math
from datetime import datetime, timezone

# ====== Настройки для Liquidity Score ======
FRESH_HOURS       = 48     # "свежесть" листинга
NEAR_FLOOR_DELTA  = 0.05   # порог "возле пола" = 5%

# ====== Вспомогательные ======
def _safe(x, default=np.nan):
    try:
        v = float(x)
        return v if np.isfinite(v) else default
    except Exception:
        return default

def _norm_log(x, ref):
    x = max(_safe(x,0.0), 0.0)
    ref = max(_safe(ref,1.0), 1e-9)
    return float(np.clip(np.log1p(x)/np.log1p(ref), 0, 1))

# ====== Метрики по коллекции ======
def aggregate_collection(prices, floors=None, ages=None):
    """
    prices: list[float] — цены всех активных листингов
    floors: list[float] — floor_price (если None → берём цены)
    ages: list[float] — возраст каждого листинга (часы)
    return: dict с агрегатами
    """
    if not prices:
        return dict(n_listed=0)

    arr = np.array(prices, float)
    floor_val = float(np.nanmin(floors)) if floors else float(np.nanmin(arr))
    ask_med = float(np.nanmedian(arr))
    ask_p10 = float(np.nanpercentile(arr,10))
    ask_p90 = float(np.nanpercentile(arr,90))
    spread_proxy = (ask_p90 - ask_p10)/max(ask_med,1e-9)

    near_thr = floor_val*(1.0+NEAR_FLOOR_DELTA)
    near_floor_share = float(np.mean(arr <= near_thr))

    rec_m = np.nan
    fresh_share = 0.0
    if ages:
        a = np.array(ages, float)
        rec_m = float(np.nanmedian(a))
        fresh_share = float(np.mean(a <= FRESH_HOURS))

    return dict(
        n_listed=len(arr),
        floor=floor_val,
        ask_median=ask_med,
        spread_proxy=spread_proxy,
        near_floor_share=near_floor_share,
        fresh_share=fresh_share,
        recency_hours_median=rec_m
    )

# ====== Расчёт Liquidity Score ======
def compute_liquidity_score(stats,
                            S_ref=0.5, T_ref=72, n_ref=10,
                            turnover_ref=None, trades_ref=None,
                            volume_24h=None, trades_24h=None, supply=None):
    """
    stats: dict из aggregate_collection
    *_ref: рыночные референсы (можно передавать глобальные значения по рынку)
    volume_24h, trades_24h, supply: опциональные данные с рынка
    return: float L ∈ [0,100]
    """
    if stats.get('n_listed',0) < 3:
        return 0.0

    # нормированные прокси
    p_tight = 1.0 - np.clip(_safe(stats['spread_proxy'],S_ref)/max(S_ref,1e-9), 0, 1)
    p_floor = np.clip(_safe(stats['near_floor_share'],0.0)/0.5, 0, 1)
    p_fresh = np.clip(_safe(stats['fresh_share'],0.0)/0.5, 0, 1)
    p_age   = 1.0 - _norm_log(stats.get('recency_hours_median',T_ref), T_ref)

    # рынок
    p_turn, p_trd = 0.0, 0.0
    if turnover_ref is not None and volume_24h is not None and supply:
        tpi = _safe(volume_24h,0.0)/max(_safe(supply,1.0),1.0)
        p_turn = _norm_log(tpi, turnover_ref)
    if trades_ref is not None and trades_24h is not None:
        p_trd = _norm_log(_safe(trades_24h,0.0), trades_ref)

    # веса
    w_t,w_f,w_fr,w_a = 0.30,0.22,0.22,0.11
    w_turn = 0.10 if turnover_ref is not None else 0.0
    w_trd  = 0.05 if trades_ref   is not None else 0.0
    ws = w_t+w_f+w_fr+w_a+w_turn+w_trd
    w_t,w_f,w_fr,w_a,w_turn,w_trd = [w/ws for w in (w_t,w_f,w_fr,w_a,w_turn,w_trd)]

    base = (w_t*p_tight + w_f*p_floor + w_fr*p_fresh + w_a*p_age +
            w_turn*p_turn + w_trd*p_trd)

    # бонус за витрину
    bonus = 0.0
    if stats['n_listed']>0:
        bonus = min(5.0, 5.0*math.log1p(stats['n_listed'])/math.log1p(max(n_ref,1.0)))

    return float(np.clip(100.0*base + bonus, 0, 100))