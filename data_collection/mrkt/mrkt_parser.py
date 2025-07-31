import csv
import aiohttp
import time
import random
import asyncio
import requests


def fetch_all_collections(token):
    url = "https://api.tgmrkt.io/api/v1/gifts/collections"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "application/json",
        "Origin": "https://cdn.tgmrkt.io",
        "Referer": "https://cdn.tgmrkt.io/"
    }

    try:
        response = requests.get(url, headers=headers)
        print("📡 Status collections:", response.status_code)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Получено коллекций: {len(data)}")
            # Save to CSV
            if data and isinstance(data, list) and len(data) > 0:
                with open("collections_mrkt.csv", mode="w", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(file, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
                print("📁 Данные коллекций сохранены в collections_mrkt.csv")

                # Extract unique collection names and fetch saling data for each, appending to a single CSV file
                collection_names = {item["name"] for item in data if "name" in item}
                print(f"🔁 Обработка {len(collection_names)} коллекций для получения saling...")

                for name in collection_names:
                    try:
                        saling_data = fetch_saling_by_collection(name, token)
                        if saling_data:
                            with open("nftdata_mrkt.csv", mode="a", newline="", encoding="utf-8") as file:
                                writer = csv.DictWriter(file, fieldnames=saling_data[0].keys())
                                if file.tell() == 0:
                                    writer.writeheader()
                                writer.writerows(saling_data)
                            print(f"✅ Добавлено saling для {name}")
                    except Exception as e:
                        print(f"⚠️ Ошибка при обработке {name}: {e}")
                    time.sleep(random.uniform(0.2, 0.4))

            return data
        else:
            print("⚠️ Ошибка:", response.text)
    except Exception as e:
        print("❌ Ошибка при запросе коллекций:", e)
def fetch_saling_by_collection(collection_name, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Origin": "https://cdn.tgmrkt.io",
        "Referer": "https://cdn.tgmrkt.io/"
    }

    all_gifts = []
    cursor = ""

    while True:
        print(f"🔄 Запрос коллекции {collection_name} с курсором: {cursor}")
        payload = {
            "count": 20,
            "cursor": cursor,
            "collectionNames": [collection_name],
            "modelNames": [],
            "backdropNames": [],
            "symbolNames": [],
            "minPrice": None,
            "maxPrice": None,
            "mintable": None,
            "number": None,
            "isNew": None,
            "isPremarket": None,
            "ordering": "Price",
            "lowToHigh": True,
            "query": None
        }

        response = requests.post("https://api.tgmrkt.io/api/v1/gifts/saling", headers=headers, json=payload)
        print(f"Status code: {response.status_code} for {collection_name}")

        try:
            data = response.json()
            gifts = data.get("gifts", [])
            if not gifts:
                print("⚠️ Нет новых подарков. Завершаем цикл.")
                break

            all_gifts.extend(gifts)

            cursor = data.get("cursor")
            if not cursor:
                print("ℹ️ Курсор не найден или пустой — конец пагинации.")
                break
            time.sleep(random.uniform(0.6, 0.9))  # Delay between paginated requests
        except requests.exceptions.JSONDecodeError:
            print("❌ Ошибка декодирования JSON. Ответ:")
            print(response.text)
            break
        except Exception as e:
            print(f"❌ Ошибка при обработке {collection_name}: {e}")
            break

    print(f"📦 Получено {len(all_gifts)} подарков из коллекции {collection_name}")
    return all_gifts


async def fetch_mrkt_token() -> str:
    url = "https://api.tgmrkt.io/api/v1/auth"

    payload = {
        "data": "query_id=AAGirOBUAwAAAKKs4FQjt0TZ&user=%7B%22id%22%3A7866461346%2C%22first_name%22%3A%22David%22%2C%22last_name%22%3A%22Rubenstein%22%2C%22username%22%3A%22davidrubenstein1%22%2C%22language_code%22%3A%22en%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FIvRaHaB6hcKqa9fYq8i12fItl_gsR452TOPLcfJ9gSzjr_lGC-_IcdRJsb4XSfuh.svg%22%7D&auth_date=1753886793&signature=c9SHhFiwvk527sFPRYEUEj5ywvIWWt0SFVkxDrkbqC_8x3ZOZmE3kbR6Rd-a9znf9BZccvrkomzMpj5BVhQcBA&hash=fd4377449929b2ad88194d585043ad2858ac4ef516b54856804595575868536d",
        "photo": "https://t.me/i/userpic/320/IvRaHaB6hcKqa9fYq8i12fItl_gsR452TOPLcfJ9gSzjr_lGC-_IcdRJsb4XSfuh.svg",
        "appId": None
    }

    headers = {
        "Content-Type": "application/json",
        "Origin": "https://cdn.tgmrkt.io",
        "Referer": "https://cdn.tgmrkt.io/",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "*/*"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                print(f"📡 Статус ответа token: {resp.status}")
                text = await resp.text()
                #print(f"📨 Тело ответа: {text}")

                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("token")
                    if token:
                        print(f"✅ Новый MRKT токен: {token}")
                        return token
                    else:
                        print("⚠️ Токен не найден в ответе JSON.")
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
    return None


async def get_valid_token() -> str:
    return await fetch_mrkt_token()


async def main():

    token = await get_valid_token()
    # token = "fdfeac2f-18f1-4b81-8e5b-d8da8cc8c436"
    if token:
        fetch_all_collections(token)  # ← сначала получить все коллекции (без токена)

        # fetch_saling_by_collection("B-Day Candle", token)

asyncio.run(main())
