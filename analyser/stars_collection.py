import numpy as np
import pandas as pd

# === Supply→Price policy (лимиты) ===
supply_price_limits = {
    '500000-200000': 200,    # 500 000 ≥ supply > 200 000
    '200000-100000': 450,    # 200 000 ≥ supply ≥ 100 000
    '50000': 1000,           # ровно 50 000
    '37500': 1800,           # ровно 37 500
    '15000': 3500,           # ровно 15 000
    '10000': 5600,           # ровно 10 000
    '<10000': 20000          # меньше 10 000
}

POLICY_TEXT = "Оценка не учитывает мгновенные OTC-перепродажи и хайп-модели. Торговля в ноль считается неоправданной."
HIDE_CAP_IN_OUTPUT = True      # не показывать потолок пользователю
SAFETY_MARGIN = 1.00           # напр. 0.85 = требуем купить на 15% ниже лимита

def _base_limit_by_supply(supply: int) -> int:
    """Возвращает лимит цены по саплаю согласно правилам (без маржи)."""
    s = int(supply)
    if 200_000 < s <= 500_000:
        return supply_price_limits['500000-200000']
    if 100_000 <= s <= 200_000:
        return supply_price_limits['200000-100000']
    if s == 50_000:
        return supply_price_limits['50000']
    if s == 37_500:
        return supply_price_limits['37500']
    if s == 15_000:
        return supply_price_limits['15000']
    if s == 10_000:
        return supply_price_limits['10000']
    if s < 10_000:
        return supply_price_limits['<10000']
    # Флоор к ближайшему более редкому порогу (монотонно)
    if s < 15_000:
        return supply_price_limits['10000']   # 10k правило
    if s < 37_500:
        return supply_price_limits['15000']   # 15k правило
    if s < 50_000:
        return supply_price_limits['37500']   # 37.5k правило
    if s < 100_000:
        return supply_price_limits['50000']   # 50k правило
    # Между 100k и 200k уже покрыто; безопасный fallback:
    return supply_price_limits['200000-100000']

def evaluate_gift(supply: int, price_stars: int,
                  hide_cap: bool = HIDE_CAP_IN_OUTPUT,
                  safety_margin: float = SAFETY_MARGIN) -> dict:
    """
    verdict по покупке: price < (лимит * маржа) ⇒ ОПРАВДАНО; иначе НЕОПРАВДАНО.
    'В ноль' считается НЕоправданной. Игнорируем мгновенные OTC и хайп-модели.
    """
    base_cap = _base_limit_by_supply(supply)
    final_cap = int(round(base_cap * safety_margin))
    justified = int(price_stars) < final_cap

    if hide_cap:
        reason = ("Цена значительно ниже расчётного уровня для данного саплая."
                  if justified else
                  "Цена близка к расчётному уровню или выше него для данного саплая.")
        return {
            "verdict": "Покупка оправдана ✅" if justified else "Покупка не оправдана ❌",
            "supply": int(supply),
            "price": int(price_stars),
            "explanation": reason,
            "policy": POLICY_TEXT
        }
    else:
        return {
            "verdict": "Покупка оправдана ✅" if justified else "Покупка не оправдана ❌",
            "supply": int(supply),
            "price": int(price_stars),
            "base_cap": base_cap,
            "final_cap": final_cap,
            "explanation": "Price is below margin-adjusted limit." if justified else "Price is not below margin-adjusted limit.",
            "policy": POLICY_TEXT
        }

def evaluate_df(df, supply_col: str = "supply", price_col: str = "price"):
    """
    Пакетная оценка по DataFrame с колонками 'supply' и 'price'.
    Возвращает таблицу с verdictом, explanationм и политикой.
    """
    out = []
    for s, p in df[[supply_col, price_col]].itertuples(index=False, name=None):
        res = evaluate_gift(int(s), int(p))
        out.append({
            "supply": int(s),
            "price": int(p),
            "verdict": res["verdict"],
            "explanation": res["explanation"],
            "policy": res["policy"]
        })

    return pd.DataFrame(out)