IMPORTANT_BACKDROPS = {"Black", "Onyx Black", "Gunmetal"}
FORECAST_EMOJI = {"up": "✅", "down": "❌", "neutral": "➖"}
FORECAST_UPPER = {"up": "UP", "down": "DOWN", "neutral": "NEUTRAL"}

def _fmt_price(v: float) -> str:
    s = f"{float(v):.2f}"
    return s.rstrip("0").rstrip(".")

def _backdrop_hint(name: str) -> str:
    return "в топе по ликвидности 💧" if name in IMPORTANT_BACKDROPS else "нейтрален"

def _diff_phrase(est: float, real: float) -> str:
    try:
        diff = (est - real) / max(abs(real), 1e-9) * 100
        adiff = abs(diff)
        if adiff < 7:
            return f"близко к оценке (~{round(adiff)}%)", "➖", "нейтрально"
        elif diff > 0:
            return f"дисконт (−{round(adiff)}%)", "💰", "рост"
        else:
            return f"премия (+{round(adiff)}%)", "💰", "снижение"
    except:
        return "неизвестно", "", ""

def _liquidity_tag(volume: int) -> str:
    if volume < 100: return "активность скромная 💤"
    if volume < 200: return "активность умеренная 🔄"
    return "активность повышенная 🔁"

def render_forecast(nft: dict) -> str:
    name = nft.get("nft_id", "NFT")
    backdrop = nft.get("backdrop", "")
    price = float(nft.get("real_price", 0))
    est = float(nft.get("estimated_ton", 0))
    rarity = nft.get("rarity", "-")
    volume = int(nft.get("volume_of_sales", 0))
    forecast = nft.get("forecast", "neutral")

    diff_text, prize, _ = _diff_phrase(est, price)
    bd_hint = _backdrop_hint(backdrop)
    act = _liquidity_tag(volume)

    emoji = FORECAST_EMOJI.get(forecast, "➖")
    fupper = FORECAST_UPPER.get(forecast, "NEUTRAL")
    price_s = _fmt_price(price)

    overview = (
        f"Прогноз на ближайшие 30 дней: цена {diff_text} {prize}, {act}. "
        f"Бэкдроп {backdrop} — {bd_hint}. DYOR."
    )

    return (
        f"🎁 {name} — {fupper} {emoji}\n"
        f"Метрики: {price_s} TON | редкость {rarity} | бэкдроп {backdrop} 🎯 ({bd_hint})\n"
        f"Обзор: {overview}"
    )

def render_many(items: list, sep: str = "\n\n") -> str:
    return sep.join(render_forecast(it) for it in items)

def render_response(nft_list: list, question: str) -> str:
    if question == "🔍 Проанализируй NFT":
        if len(nft_list) == 1:
            return render_forecast(nft_list[0])
        elif len(nft_list) == 2:
            return "\n\n".join(render_forecast(n) for n in nft_list) + "\n\n⚖️ Сравнение: Анализ выше основан на различиях в редкости, цене и активности."
        else:
            return render_many(nft_list)

    if question == "📈 Покажи недооцененные":
        undervalued = [n for n in nft_list if n.get("forecast") == "up"]
        return render_many(undervalued) or "❌ Не найдено недооценённых NFT."

    if question == "⬆ Только с прогнозом 'up'":
        only_up = [n for n in nft_list if n.get("forecast") == "up"]
        return render_many(only_up) or "❌ Нет NFT с прогнозом 'up'."

    return render_many(nft_list)


def calculate_forecast(nft_details: list) -> list:
    popular_attributes = {"Neon Blue", "Caramel", "Cotton Candy", "Indigo Dye", "Navy Blue"}

    def calculate_score(nft):
        score = 0
        rarity = nft.get("rarity", 0)
        price = nft.get("real_price", 0)
        est = nft.get("estimated_ton", 1)
        backdrop = nft.get("backdrop", "")
        symbol = nft.get("symbol", "")
        model = nft.get("model", "")
        volume = nft.get("volume_of_sales", 0)

        if rarity < 50000:
            score += 1
        elif rarity > 75000:
            score -= 1

        if price < est * 0.95:
            score += 1
        elif price > est * 1.05:
            score -= 1

        if backdrop in popular_attributes or symbol in popular_attributes or model in popular_attributes:
            score += 1

        if volume > 100:
            score += 1

        return score

    for nft in nft_details:
        nft["score"] = score = calculate_score(nft)
        if score >= 2:
            nft["forecast"] = "up"
        elif score <= -2:
            nft["forecast"] = "down"
        else:
            nft["forecast"] = "neutral"

    return nft_details
