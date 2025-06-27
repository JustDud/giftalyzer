iimport requests
import os
import time
import re
import requests
from dotenv import load_dotenv
load_dotenv()

TON_API = os.getenv("TON_API")

def is_working_getgems_page(url: str) -> bool:
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200 and "this page does not exist" not in response.text.lower() and "we cannot find this page" not in response.text.lower():
            return True
    except requests.RequestException:
        pass
    return False

def fetch_all_collections(limit=1000):
    url = "https://tonapi.io/v2/nfts/collections"
    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {TON_API}"
    }

    all_collections = []
    offset = 0

    while True:
        params = {
            "limit": limit,
            "offset": offset
        }
        print(f"Params: {params}")

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        items = data.get("nft_collections", [])
        if not items:
            break

        # Filter only Telegram Gift-related collections from getgems
        for item in items:

            metadata = item.get("metadata") or {}
            marketplace = metadata.get("marketplace", "")
            description = (metadata.get("description") or "")

            if "getgems.io" in marketplace and "is an exclusive nft collection by telegram." in description.lower():
                external_url = metadata.get("external_url")
                if external_url and external_url.startswith("https://getgems.io/collection/") and is_working_getgems_page(external_url):
                    collection = {
                        "address": item.get("address"),
                        "name": "".join(c for c in metadata.get("name", "") if c.isalnum() or c.isspace()),
                        "external_url": external_url,
                        "description": metadata.get("description")
                    }
                    all_collections.append(collection)

        time.sleep(1.0)  # increased delay to avoid 429 Too Many Requests

        offset += limit
        if offset > 5000:
            break

    print(f"Total collections fetched: {len(all_collections)}")
    return all_collections


# Пример использования:
if __name__ == "__main__":
    collections = fetch_all_collections()
    for col in collections:
        print(f"{col['name']} → {col['address']}")
    import json
    with open("collection_addresses_getgems.json", "w", encoding="utf-8") as f:
        json.dump(collections, f, ensure_ascii=False, indent=2)

##############
##############
#############
########
#####
##
#
#
#
#
#
#

#
#


# import time
# import json
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from tonsdk.utils import Address
# import logging
# logging.getLogger('selenium').setLevel(logging.WARNING)
# logging.getLogger('urllib3').setLevel(logging.WARNING)
#
#
# def scrape_all_gift_collections():
#     start_time = time.time()
#     url = "https://getgems.io/top-gifts?top-collections-period=all"
#     options = webdriver.ChromeOptions()
#     options.add_argument("--headless")
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     prefs = {
#         "profile.managed_default_content_settings.images": 2,
#         "profile.managed_default_content_settings.stylesheets": 2,
#         "profile.managed_default_content_settings.fonts": 2
#     }
#     options.add_experimental_option("prefs", prefs)
#     options.add_experimental_option("excludeSwitches", ["enable-logging"])
#     driver = webdriver.Chrome(options=options)
#     driver.get(url)
#
#     # Wait until at least one collection card is loaded
#     wait = WebDriverWait(driver, 20)
#     wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='/collection/']")))
#
#     # Scroll to the bottom to load all cards
#     selector = "a[href^='/collection/']"
#     cards = driver.find_elements(By.CSS_SELECTOR, selector)
#     num_cards = len(cards)
#     while True:
#         driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
#         try:
#             WebDriverWait(driver, 10).until(
#                 lambda d: len(d.find_elements(By.CSS_SELECTOR, selector)) > num_cards
#             )
#             cards = driver.find_elements(By.CSS_SELECTOR, selector)
#             num_cards = len(cards)
#         except:
#             break
#
#     # Extract collection addresses and names
#     cards = driver.find_elements(By.CSS_SELECTOR, "a[href^='/collection/']")
#     seen = set()
#     results = []
#     for card in cards:
#         href = card.get_attribute("href")
#         # href should be like https://getgems.io/collection/EQ...
#         if "/collection/" not in href:
#             continue
#         base64_address = href.split("/collection/")[-1].split("/")[0]
#         try:
#             address = Address(base64_address).to_string(False, True)
#         except Exception:
#             continue
#         name = card.text.strip()
#         if not address or not name:
#             continue
#         if address in seen:
#             continue
#         seen.add(address)
#         results.append({"name": name, "address": address})
#
#     # Save to JSON file
#     with open("collection_addresses_getgems.json", "w", encoding="utf-8") as f:
#         json.dump(results, f, ensure_ascii=False, indent=2)
#
#     end_time = time.time()
#     print(f"Total collections scraped: {len(results)}")
#     print(f"Scraping completed in {end_time - start_time:.2f} seconds.")
#     driver.quit()
# if __name__ == "__main__":
#     scrape_all_gift_collections()





import asyncio
import json
import re
import time
from playwright.async_api import async_playwright
from tonsdk.utils import Address



async def scrape_prices(collection_address: str):
    start_time = time.time()
    url = f"https://getgems.io/collection/{collection_address}?filter=%7B%22saleType%22%3A%22fix_price%22%7D"
    nft_list = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # Block images, fonts, and styles
        async def block_resources(route, request):
            if request.resource_type in ["image", "font", "stylesheet"]:
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", block_resources)

        page = await context.new_page()
        await page.goto(url, timeout=60000)
        await page.wait_for_selector("div[data-address]")

        # Dynamically scroll until no new NFTs appear after multiple attempts
        prev_count = 0
        same_count = 0
        max_same = 10

        while same_count < max_same:
            await page.mouse.wheel(0, 1500)
            await asyncio.sleep(1.5)
            await page.evaluate("window.dispatchEvent(new Event('scroll'))")

            cards = await page.query_selector_all("div[data-address]")
            count = len(cards)

            if count == prev_count:
                same_count += 1
            else:
                same_count = 0
                prev_count = count

        print(f"🔍 Found {len(await page.query_selector_all('div[data-address]'))} NFT cards on the page.")

        for card in await page.query_selector_all("div.NftItemContainer[data-address]"):
            try:
                base64_addr = await card.get_attribute("data-address")
                address = await base64_to_hex(base64_addr)

                name_elem = await card.query_selector(".LibraryTypography")
                name = (await name_elem.inner_text()).strip() if name_elem else "N/A"

                price_elem = await card.query_selector(".LibraryCryptoPrice__amount")
                price_text = (await price_elem.inner_text()).strip() if price_elem else ""
                price_clean = re.sub(r"[^\d]", "", price_text)
                price = int(price_clean) if price_clean else None

                attributes = {}
                attr_elems = await card.query_selector_all(".NftProperty")
                for attr_elem in attr_elems:
                    try:
                        key_el = await attr_elem.query_selector(".NftProperty__title")
                        val_el = await attr_elem.query_selector(".NftProperty__subtitle")
                        key = (await key_el.inner_text()).strip() if key_el else ""
                        value = (await val_el.inner_text()).strip() if val_el else ""
                        if key:
                            attributes[key] = value
                    except:
                        continue

                if price is not None:
                    nft_list.append({
                        "id": address,
                        "name": name,
                        "address": address,
                        "price": price,
                        "attributes": attributes
                    })
            except Exception as e:
                print(f"⚠️ Error parsing NFT: {e}")
                continue

        await browser.close()

    if nft_list:
        filename = f"prices_{collection_address}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(nft_list, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved {len(nft_list)} NFTs with prices to {filename}")
    else:
        print("⚠️ No NFTs with prices were found.")

    print(f"⏱ Scraping completed in {time.time() - start_time:.2f} seconds.")


async def base64_to_hex(addr: str) -> str:
    return Address(addr).to_string(False, False)


if __name__ == "__main__":
    # Replace with the address you want to scrape
    collection_address = "EQBG-g6ahkAUGWpefWbx-D_9sQ8oWbvy6puuq78U2c4NUDFS"
    asyncio.run(scrape_prices(collection_address))