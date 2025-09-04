# -- stdlib
import asyncio
import time
import os
import random
import json
import csv
# -- 3rd party
from playwright.async_api import async_playwright
USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.196 Mobile Safari/537.36"
]
# from utils import fragment_slug
# from config import API_URL_TONNEL, COLLECTION_NAMES
from dotenv import load_dotenv
load_dotenv()

USER_AUTH = os.environ.get("USER_AUTH")
API_URL_TONNEL = os.environ.get("API_URL_TONNEL")
TONNEL_PRICE_MULTIPLIER = 1.06

TONNEL_RATE = 1.5


COLLECTION_NAMES = [
    "Astral Shard", "Pet Snake", "Plush Pepe", "Precious Peach", "Record Player", "Restless Jar",
    "Sakura Flower", "Santa Hat", "Scared Cat", "Sharp Tongue", "Signet Ring",
    "Skull Flower", "Sleigh Bell", "Snake Box", "Snow Globe", "Snow Mittens",
    "Spiced Wine", "Spy Agaric", "Star Notepad", "Swiss Watch", "Tama Gadget",
    "Top Hat", "Toy Bear", "Trapped Heart", "Valentine Box", "Vintage Cigar",
    "Voodoo Doll", "Whip Cupcake", "Winter Wreath", "Witch Hat", "Xmas Stocking",
    "Loot Bag", "Love Candle", "Love Potion", "Lunar Snake", "Lush Bouquet",
    "Mad Pumpkin", "Magic Potion", "Mini Oscar", "Nail Bracelet", "Neko Helmet",
    "Party Sparkler", "Electric Skull", "Eternal Candle", "Eternal Rose", "Evil Eye",
    "Gem Signet", "Genie Lamp", "Ginger Cookie", "Hanging Star", "Heart Locket",
    "Heroic Helmet", "Hex Pot", "Holiday Drink", "Homemade Cake", "Hypno Lollipop",
    "Ion Gem", "Jack-in-the-Box", "Jelly Bunny", "Jester Hat", "Jingle Bells",
    "Joyful Bundle", "Kissed Frog", "Light Sword", "Lol Pop", "Bonded Ring",
    "Bow Tie", "Bunny Muffin", "Candy Cane", "Cookie Heart", "Crystal Ball",
    "Cupid Charm", "Desk Calendar", "Diamond Ring", "Durov's Cap", "Easter Egg",
    "Perfume Bottle", "Flying Broom", "Snoop Dogg", "Swag Bag", "Snoop Cigar",
    "Westside Sign", "Low Rider", "B-Day Candle", "Berry Box", "Big Year"
]

_tonnel_lock = asyncio.Lock()
_tonnel_last = 0

def manual_slugify(name):
    return name.lower().replace("’", "").replace("'", "").replace("’", "").replace("’", "").replace(" ", "-")

SLUG_COLLECTION_NAMES = [manual_slugify(name) for name in COLLECTION_NAMES]


async def get_valid_token():
    return {
        "id": 474039722,
        "first_name": "DD",
        "last_name": "",
        "username": "dimadud",
        "language_code": "en",
        "allows_write_to_pm": True,
        "photo_url": "https://t.me/i/userpic/320/BGU567L3Vze7kpeoVSkeUDvHBh-0ZooveO2c_CXyk-Q.svg"
    }
# from mrkt import fetch_mrkt_floor, fetch_mrkt_model_floor
# from portals import fetch_portals_floor
# from fragment import fetch_fragment_floors
# from getgems import fetch_getgems_floors, GETGEMS_MAP




async def fetch_floor(page, gift_name: str):
    payload = {
        "page": 1,
        "limit": 30,
        "sort": "{\"price\":1,\"gift_id\":-1}",
        "filter": f"""{{
            "gift_name": "{gift_name}",
            "price": {{"$exists": true}},
            "refunded": {{"$ne": true}},
            "buyer": {{"$exists": false}},
            "export_at": {{"$exists": true}},
            "asset": "TON"
        }}""",
        "ref": 0,
        "price_range": None,
        # user_auth will be overwritten below
        "user_auth": None,
    }

    try:
        global _tonnel_last
        async with _tonnel_lock:
            wait = TONNEL_RATE - (time.perf_counter() - _tonnel_last)
            print(f"Wait Delay: {wait}")
            if wait > 0:
                await asyncio.sleep(wait)
            _tonnel_last = time.perf_counter()

        payload["user_auth"] = USER_AUTH
        all_valid_items = []
        page_num = 1

        while True:
            payload["page"] = page_num
            delay = random.uniform(1.2, 1.4)
            print(f"⏳ Вариативная задержка перед запросом: {delay:.2f} сек")
            await asyncio.sleep(delay)
            print(f"📄 {gift_name} — страница {page_num}")
            retries = 3
            for attempt in range(retries):
                # --- Patch: set random User-Agent
                headers = {"Content-Type": "application/json"}
                headers["User-Agent"] = random.choice(USER_AGENTS)
                try:
                    data = await page.evaluate(
                        """async ({url, payload, headers}) => {
                            const res = await fetch(url, {
                                method: "POST",
                                headers,
                                body: JSON.stringify(payload)
                            });
                            if (!res.ok) throw new Error("HTTP " + res.status);
                            return await res.json();
                        }""",
                        {"url": API_URL_TONNEL, "payload": payload, "headers": headers},
                    )
                    break  # success, exit retry loop
                except Exception as e:
                    print(f"⚠️ Попытка {attempt+1} не удалась: {e}")
                    # Patch: wait 20s before last attempt
                    if attempt == retries - 2:
                        print("⏳ Последняя попытка, ждём 25 секунд перед повтором...")
                        await asyncio.sleep(25)
                    if attempt < retries - 1:
                        await asyncio.sleep(15)
                    else:
                        raise  # re-raise the final exception after retries exhausted
            # Patch: extract "items" from dict response if present
            response = data
            if isinstance(response, dict):
                response = response.get("items", [])
            #print("🔎 RAW response:", response)

            # New: handle empty or invalid responses gracefully
            if response is None or not isinstance(response, list) or len(response) == 0:
                print(f"❌ {gift_name} (tonnel): нет данных")
                return gift_name, []

            valid_items = [
                item for item in response
                if isinstance(item, dict) and item.get("buyer") is None and item.get("export_at")
            ]
            if valid_items:
                all_valid_items.extend(valid_items)
            if not valid_items or len(valid_items) < payload["limit"]:
                break
            page_num += 1

        # Check for empty all_valid_items before accessing
        if not all_valid_items:
            print(f"❌ {gift_name} (tonnel): нет валидных лотов")
            return gift_name, []

        # Extract required fields for each valid item
        extracted_items = []
        for item in all_valid_items:
            gift_id = item.get("gift_id", "")
            gift_num = item.get("gift_num", "")
            name_gift = item.get("name", "")
            model = item.get("model", "")
            symbol = item.get("symbol", "")
            backdrop = item.get("backdrop", "")
            price = float(item.get("price", 0)) * TONNEL_PRICE_MULTIPLIER if item.get("price") is not None else None
            status = item.get("status", "")
            extracted_items.append((
                gift_name,
                gift_id,
                gift_num,
                name_gift,
                model,
                symbol,
                backdrop,
                price,
                status
            ))

        print(f"✅ {gift_name} (tonnel): extracted {len(extracted_items)} items")
        return gift_name, extracted_items

    except Exception as e:
        print(f"❌ {gift_name} (tonnel): ошибка — {e}")
        return gift_name, []


async def main():
    start = time.time()
    # getgems_floors = await fetch_getgems_floors(GETGEMS_MAP)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        )

        # fragment_floors = await fetch_fragment_floors(COLLECTION_NAMES)

        page = await context.new_page()
        await page.goto("https://gifts3.tonnel.network", wait_until="load")

        MRKT_AUTH = await get_valid_token()
        if not MRKT_AUTH:
            print("❌ Не удалось получить MRKT токен")
            return

        # Always overwrite the CSV file and write the correct header at the start
        with open("tonnel_results.csv", mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Collection Slug", "Gift ID", "Gift Num", "Gift Name", "Model", "Symbol", "Backdrop", "Price (TON)", "Status"])

        for idx, name in enumerate(COLLECTION_NAMES, 1):
            collection_start = time.time()
            name_mrkt = name.replace("'", "’")
            t_task = fetch_floor(page, name)
            gift_name, items = await t_task

            print(f"📦 Проверка перед записью: {gift_name}, items count: {len(items)}")
            # Append each valid item as a separate row (append mode not needed since we wrote header above, but keep append below for clarity)
            with open("tonnel_results.csv", mode="a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                if items:
                    for item in items:
                        writer.writerow(item)
                    print(f"✅ Записано: {gift_name} — {len(items)} items")
                else:
                    print(f"⚠️ Пропущено: {gift_name}, некорректные или пустые данные")
            await asyncio.sleep(random.uniform(0.9, 1.4))
            print(f"⏱ Time for {gift_name}: {time.time() - collection_start:.1f} sec")

        await browser.close()

        print(f"⏱ Total time: {time.time() - start:.1f} sec")

if __name__ == "__main__":
    asyncio.run(main())
