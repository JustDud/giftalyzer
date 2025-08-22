import asyncio
from analyser.model_provider import generate_response
import numpy as np
import os, time, re
from typing import Optional, Tuple, Iterable


# ===========================================
# NFT/Gift Forecast Engine — FINAL MODULE
# ===========================================
# Что делает:
# - Формирует краткий прогноз на 30 дней для NFT/«подарков»
# - Единый формат вывода без слов FORECAST и без нумерации
# - Метрики: цена (TON), редкость (%), бэкдроп с подсказкой ликвидности
# - Эмодзи: ✅❌➖ + контекстные (💧 💤 🔄 📉 📈 🐻 🚀 ⚖️)
# - Логика: дифф к оценке, активность, «топ» бэкдропы
# - LLM (опционально, через OpenRouter): эмбеддингов нет — только перефраз «Обзора»
# - Тихий фоллбек: если LLM/ключа нет — чистый шаблон без мусорных сообщений
#
# Как подключить OpenRouter:
#   os.environ["OPENAI_API_KEY"] = "sk-or-ВАШ_КЛЮЧ"
#   (или задайте переменную окружения в вашей среде)
#
# Как использовать в коде:
#   from forecaster import render_forecast, render_many
#   text = render_forecast(item_dict)              # один объект
#   blob = render_many(list_of_item_dicts, sep="\n\n")  # несколько
#
# Формат входного item:
# {
#   "id": "…",                        # опционально
#   "name": "Emerald Dragon",
#   "backdrop": "Onyx Black",
#   "price": 14.2,                    # float (TON)
#   "est_price": 12.8,                # float (TON) — оценка
#   "rarity": "9/32" или "28.1" или "28.1%",
#   "liquidity": 215                  # int
# }


# ====== НАСТРОЙКИ ======
USE_LLM_DEFAULT = True                 # если есть корректный ключ — используем LLM
DISPLAY_DIFF_CAP = 40                  # максимум % для показа (логика считает реальный diff)
IMPORTANT_BACKDROPS = {"Black", "Onyx Black", "Gunmetal"}  # «топ» по ликвидности

FORECAST_EMOJI = {"up": "✅", "down": "❌", "neutral": "➖"}
FORECAST_UPPER = {"up": "UP", "down": "DOWN", "neutral": "NEUTRAL"}


def _fmt_price(v: float) -> str:
    s = f"{float(v):.2f}"
    return s.rstrip("0").rstrip(".")

def _backdrop_hint(backdrop: str) -> str:
    return "в топе по ликвидности 💧" if backdrop in IMPORTANT_BACKDROPS else "нейтрален"

def _rarity_from_rank_text(r: str) -> Tuple[Optional[int], Optional[int]]:
    try:
        if isinstance(r, str) and "/" in r:
            a, b = r.split("/", 1)
            return int(a.strip()), int(b.strip())
    except:
        pass
    return None, None

def _rarity_to_percent(rank: Optional[int], max_rank: Optional[int]) -> Optional[float]:
    try:
        if rank and max_rank:
            return round(((max_rank + 1 - rank) / max_rank) * 100, 1)
    except:
        pass
    return None

def _raw_diff_pct(est_price: float, price: float) -> float:
    try:
        return (est_price - price) / max(abs(price), 1e-9) * 100
    except:
        return 0.0

def _diff_label_and_value(est_price: float, price: float) -> Tuple[str, float, float]:
    """
    Возвращает:
      label: 'дисконт' | 'премия' | 'близко к оценке'
      shown_abs: ABS% для отображения (софт-кеп DISPLAY_DIFF_CAP)
      real_abs:  реальный ABS% (для логики)
    """
    diff_pct = _raw_diff_pct(est_price, price)
    ad = abs(diff_pct)
    if ad < 7:
        return "близко к оценке", round(min(ad, DISPLAY_DIFF_CAP)), ad
    label = "дисконт" if diff_pct >= 0 else "премия"
    return label, round(min(ad, DISPLAY_DIFF_CAP)), ad

def _diff_phrase(word: str, shown_val: float) -> str:
    if word == "близко к оценке":
        return f"близко к оценке (~{shown_val}%)"
    sign = "+" if word == "премия" else "−"
    return f"{word} ({sign}{shown_val}%)"

def _liquidity_tag(liq: Optional[int]) -> str:
    if liq is None: return "активность не указана"
    if liq < 100:   return "активность скромная 💤"
    if liq < 200:   return "активность умеренная 🔄"
    return "активность повышенная 🔁"

def _gain_emoji(diff_word: str) -> str:
    # 💰 — только при «премия/дисконт»
    return " 💰" if diff_word in ("дисконт", "премия") else ""

# ====== ЛОГИКА НАПРАВЛЕНИЯ ======
def _choose_forecast(price: float, est_price: float, liquidity: int, backdrop: str) -> str:
    """
    - diff >= +14.5% → up, diff <= -14.5% → down, иначе neutral/up/down случайно;
    - важный бэкдроп смещает neutral→up при положительном diff;
    - слабая активность (<100) ослабляет up → neutral/down.
    """
    import random
    diff_pct = _raw_diff_pct(est_price, price)
    if diff_pct >= 14.5:
        base = "up"
    elif diff_pct <= -14.5:
        base = "down"
    else:
        base = random.choice(["neutral", "up", "down"])

    if backdrop in IMPORTANT_BACKDROPS and base == "neutral" and diff_pct > 0:
        base = "up"
    if liquidity is not None and liquidity < 100 and base == "up":
        import random as _r
        base = _r.choice(["neutral", "down"])
    return base

# ====== LLM-ПЕРЕФРАЗ «ОБЗОРА» (опционально) ======
async def _llm_rewrite_overview(label: str,
                          backdrop: str,
                          price: float,
                          est_price: float,
                          rarity_pct: Optional[float],
                          liquidity: int,
                          forecast: str,
                          retries: int = 1) -> Optional[str]:
    """1–2 предложения. Начало: «Прогноз на ближайшие 30 дней: цена …»"""

    diff_word, diff_shown, _ = _diff_label_and_value(est_price, price)
    diff_text = _diff_phrase(diff_word, diff_shown)  # без слова «цена»
    act = _liquidity_tag(liquidity)
    top = _backdrop_hint(backdrop)
    mood = {"up": "оптимистичный", "down": "осторожный", "neutral": "нейтральный"}[forecast]

    ask = (
        f"Одно-два предложения для обзора на 30 дней. Начни дословно: "
        f"«Прогноз на ближайшие 30 дней: цена {diff_text}» (дальше — эмодзи и вывод по смыслу). "
        f"Упомяни: {act}, бэкдроп {backdrop} ({top}), редкость ≈ {rarity_pct:.1f}% (если уместно). "
        f"Заверши «DYOR.» Без таблиц и без повторения метрик. Тон — {mood}."
    )

    last_err = None
    for a in range(retries + 1):
        try:
            ai_response = await generate_response(ask)
        except Exception as e:
            last_err = e
            time.sleep(0.6 * (a + 1))
    return None  # тихий фоллбек


# ====== ПУБЛИЧНЫЕ ФУНКЦИИ ======
async def render_forecast(item: dict) -> str:
    """
    Возвращает форматированный прогноз (строка) для одного item.
    См. формат входа в шапке файла.
    """
    label    = (item.get("name") or f"NFT {item.get('id','—')}").strip()
    backdrop = str(item.get("backdrop", "Unknown")).strip()
    price    = float(item.get("price", 0))
    estp     = float(item.get("est_price", price))
    rarity   = item.get("rarity", "—")
    liq      = int(item.get("liquidity", 0))

    # Редкость → %
    r_rank, r_max = _rarity_from_rank_text(rarity)
    if r_rank and r_max:
        rarity_pct = _rarity_to_percent(r_rank, r_max)
    else:
        try:
            rarity_pct = float(str(rarity).replace("%", "").strip())
        except:
            rarity_pct = None

    forecast = _choose_forecast(price, estp, liq, backdrop)
    emoji = FORECAST_EMOJI[forecast]
    fupper = FORECAST_UPPER[forecast]

    price_s = _fmt_price(price)
    rare_s  = f"{rarity_pct:.1f}%" if isinstance(rarity_pct, (int, float)) else str(rarity)
    bd_hint = _backdrop_hint(backdrop)

    diff_word, diff_shown, _ = _diff_label_and_value(estp, price)
    diff_text = _diff_phrase(diff_word, diff_shown)
    act = _liquidity_tag(liq)
    prize = _gain_emoji(diff_word)

    # Fallback-обзор (LLM при наличии ключа может переписать)
    if forecast == "up":
        overview = (
            f"Прогноз на ближайшие 30 дней: цена {diff_text}{prize}, {act}. "
            f"Бэкдроп {backdrop} — {bd_hint}. Вероятен подъём при подогреве спроса 📈🚀. DYOR."
        )
    elif forecast == "down":
        overview = (
            f"Прогноз на ближайшие 30 дней: цена {diff_text} и/или слабые катализаторы; {act}. "
            f"Бэкдроп {backdrop} — {bd_hint}. Риск коррекции сохраняется 🐻📉. DYOR."
        )
    else:
        overview = (
            f"Прогноз на ближайшие 30 дней: цена {diff_text}, {act}. "
            f"Бэкдроп {backdrop} — {bd_hint}. Консолидация/боковик ⚖️. DYOR."
        )

    # Пытаемся «оживить» через LLM
    llm_text = await _llm_rewrite_overview(label, backdrop, price, estp, rarity_pct or 0.0, liq, forecast)
    if llm_text:
        overview = llm_text

    return (
        f"🎁 {label} — {fupper} {emoji}\n"
        f"Метрики: {price_s} TON | редкость {rare_s} | бэкдроп {backdrop} 🎯 ({bd_hint})\n"
        f"Обзор: {overview}"
    )

async def render_many(items: Iterable[dict], sep: str = "\n\n") -> str:
    """
    Рендерит несколько объектов и возвращает одним текстовым блоком.
    """
    return sep.join([await render_forecast(it) for it in items])

