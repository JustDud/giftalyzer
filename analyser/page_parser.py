

import aiohttp
from bs4 import BeautifulSoup
from mongo import get_nfts_by_params


async def parse_telegram_gift_page(gift_name: str) -> dict | None:
    """
    Парсит Telegram NFT страницу и достает параметры: модель, символ, фон.
    """
    url = f"https://t.me/nft/{gift_name}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
    except Exception:
        return None

    soup = BeautifulSoup(html, "html.parser")

    try:
        import re

        def clean_cell_text(text: str) -> str:
            # Удалить всё после цифр или процентов
            return re.split(r'[\d%]+', text)[0].strip()

        table = soup.find("table", class_="tgme_gift_table")
        if not table:
            return None

        data = {}
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            header = row.find("th").get_text(strip=True).lower()

            if header == "model":
                data["model"] = clean_cell_text(cells[0].get_text(strip=True))
            elif header == "symbol":
                data["symbol"] = clean_cell_text(cells[0].get_text(strip=True))
            elif header == "backdrop":
                data["backdrop"] = clean_cell_text(cells[0].get_text(strip=True))

        if not all(key in data for key in ("model", "symbol", "backdrop")):
            return None

        return data

    except Exception:
        return None


async def find_similar_in_db(model: str, symbol: str, backdrop: str) -> list[dict]:
    return await get_nfts_by_params(model, symbol, backdrop)
