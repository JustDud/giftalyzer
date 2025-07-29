import asyncio
import time
import os
import random
import json
import csv
from playwright.async_api import async_playwright
# from utils import fragment_slug
# from config import API_URL_TONNEL, COLLECTION_NAMES

API_URL_TONNEL   = "https://gifts3.tonnel.network/api/pageGifts"

COLLECTION_NAMES = [
    "Pet Snake", "Plush Pepe", "Precious Peach", "Record Player", "Restless Jar",
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
    "Westside Sign", "Low Rider", "Astral Shard", "B-Day Candle", "Berry Box", "Big Year"
]


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

_tonnel_lock = asyncio.Lock()
_tonnel_last = 0
TONNEL_RATE = 1.5


async def fetch_floor(page, gift_name: str):
    payload = {
        "page": 1,
        "limit": 5,
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
            wait_time = random.uniform(1.2, 2.0)
            wait = wait_time - (time.perf_counter() - _tonnel_last)
            if wait > 0:
                await asyncio.sleep(wait)
            _tonnel_last = time.perf_counter()

        payload["user_auth"] = "user=%7B%22id%22%3A474039722%2C%22first_name%22%3A%22DD%22%2C%22last_name%22%3A%22%22%2C%22username%22%3A%22dimadud%22%2C%22language_code%22%3A%22en%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FBGU567L3Vze7kpeoVSkeUDvHBh-0ZooveO2c_CXyk-Q.svg%22%7D&chat_instance=2616407032313614176&chat_type=sender&auth_date=1753806184&signature=t_GYtEnqYhEEjv5ls7JJiCRVHCeY1SV7y_6EjaPYHQrgf8e7kNnjqdxMtKVnGGlsaPwxJQArBbtnUqZrTU_YDw&hash=35b1c2cc67e5396e9ff3d070a034e5921dfb15b79b0bbefb2b5e8a1a0942edb1"
        all_valid_items = []
        page_num = 1

        while True:
            payload["page"] = page_num
            response = await page.evaluate(
                """async ({url, payload}) => {
                    const res = await fetch(url, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });
                    if (!res.ok) throw new Error("HTTP " + res.status);
                    return await res.json();
                }""",
                {"url": API_URL_TONNEL, "payload": payload},
            )
            # Patch: extract "items" from dict response if present
            if isinstance(response, dict):
                response = response.get("items", [])
            print("🔎 RAW response:", response)

            # New: handle empty or invalid responses gracefully
            if response is None or not isinstance(response, list) or len(response) == 0:
                print(f"❌ {gift_name} (tonnel): нет данных")
                return gift_name, "", None, "", "", "", ""

            valid_items = [
                item for item in response
                if isinstance(item, dict) and item.get("buyer") is None and item.get("export_at")
            ]
            if valid_items:
                all_valid_items.extend(valid_items)
            if not valid_items or len(valid_items) < payload["limit"]:
                break
            page_num += 1

        # Check for empty all_valid_items before accessing [0]
        if not all_valid_items:
            print(f"❌ {gift_name} (tonnel): нет валидных лотов")
            return gift_name, "", None, "", "", "", ""

        item = all_valid_items[0]
        price = float(item["price"]) * 1.10
        gift_num = item.get("gift_num", "")
        real_id = item.get("gift_id", "")
        name_gift = item.get("name", "")
        model = item.get("model", "")
        #gift_slug = fragment_slug(gift_name)
        #image_url = f"https://nft.fragment.com/gift/{gift_slug}-{gift_num}.large.jpg"
        market_url = f"https://marketplace.tonnel.network/?giftDrawerId={real_id}"

        print(f"✅ {gift_name} (tonnel): {name_gift} {model} {price:.2f} TON")
        return gift_name, gift_num, price, market_url, name_gift, model, #image_url

    except Exception as e:
        print(f"❌ {gift_name} (tonnel): ошибка — {e}")
        return gift_name, "", None, "", "", "", ""


async def main():
    start = time.time()
    # getgems_floors = await fetch_getgems_floors(GETGEMS_MAP)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        # fragment_floors = await fetch_fragment_floors(COLLECTION_NAMES)

        page = await context.new_page()
        await page.goto("https://gifts3.tonnel.network", wait_until="load")

        MRKT_AUTH = await get_valid_token()
        if not MRKT_AUTH:
            print("❌ Не удалось получить MRKT токен")
            return

        if not os.path.exists("tonnel_results.csv"):
            with open("tonnel_results.csv", mode="w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Collection Slug", "Gift Name", "Gift Num", "Price (TON)", "Market URL", "Name Gift", "Model"])

        for idx, name in enumerate(COLLECTION_NAMES, 1):
            name_mrkt = name.replace("'", "’")
            t_task = fetch_floor(page, name)
            tonnel_data = await t_task

            # Save each collection result appended into a single CSV file
            with open("tonnel_results.csv", mode="a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([name] + list(tonnel_data))
            print(f"✅ Appended: {name}")
            await asyncio.sleep(0.2)

        await browser.close()
        # The following block is removed/commented: save all results to a single CSV file
        # with open("tonnel_results.csv", mode="w", newline="", encoding="utf-8") as csvfile:
        #     writer = csv.writer(csvfile)
        #     writer.writerow(["Collection Slug", "Gift Name", "Gift Num", "Price (TON)", "Market URL", "Name Gift", "Model"])
        #     for name, data in results:
        #         writer.writerow([name] + list(data))
        # print("✅ Results saved to tonnel_results.csv")
        print(f"⏱ Total time: {time.time() - start:.1f} sec")

if __name__ == "__main__":
    asyncio.run(main())
