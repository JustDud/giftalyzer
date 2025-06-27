import requests
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


def fetch_getgems_for_sale(collection_slug: str, limit: int = 10):
    """
    Render the GetGems collection page with Selenium and scrape NFTs listed for sale.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    url = f"https://getgems.io/collection/{collection_slug}/items"
    driver.get(url)
    # Click the "For Sale" tab to trigger client-side filtering
    try:
        for_sale_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '//div[contains(text(), "For Sale")]/ancestor::div[contains(@class, "LibraryHoverContainer")]'))
        )
        driver.execute_script("arguments[0].click();", for_sale_button)
        time.sleep(2)
    except Exception as e:
        print("⚠️ Couldn't click 'For Sale' tab:", e)
    # Initial wait for content to begin loading, handle slow or missing loads gracefully
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.NftItemContainer[data-address]"))
        )
    except:
        print("⚠️ Timeout waiting for NFT cards. Proceeding anyway...")

    # Scroll to load all content
    last_height = driver.execute_script("return document.body.scrollHeight")
    same_count = 0
    max_attempts = 10  # prevent infinite loops
    while same_count < max_attempts:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            same_count += 1
        else:
            same_count = 0
        last_height = new_height
    print(f"ℹ️ Page URL: {driver.current_url}")
    cards = driver.find_elements(By.CSS_SELECTOR, "div.NftItemContainer[data-address]")
    print(f"🔍 Found {len(cards)} NFT cards on the page.")
    results = []
    for card in cards:
        address = card.get_attribute("data-address")
        # extract image URL
        try:
            image = card.find_element(By.CSS_SELECTOR, "img").get_attribute("src")
        except:
            image = None
        # extract price
        try:
            price = card.find_element(By.CSS_SELECTOR, ".LibraryCryptoPrice__amount").text
            price = re.sub(r"[^\d]", "", price)
        except:
            # skip if no price
            continue
        # extract name (if available) from the NFT card
        try:
            # the span with class 'NftItemNameContent__name' holds the actual name
            name_elem = card.find_element(By.CSS_SELECTOR, "span.NftItemNameContent__name")
            # use the title attribute if present, otherwise the visible text
            name = name_elem.get_attribute("title") or name_elem.text.strip()
        except:
            # fallback to address if name not found
            name = address
        results.append({
            "name":    name,
            "address": address,
            "price":   price,
        })

    driver.quit()
    import json
    unique_results = {entry['address']: entry for entry in results}.values()
    with open("plush_pepes_listings.json", "w", encoding="utf-8") as f:
        json.dump(list(unique_results), f, ensure_ascii=False, indent=2)
    print(f"✅ Total NFTs listed for sale: {len(results)}")
    return results


if __name__ == "__main__":
    # ← Replace with the slug from your GetGems URL (between /collection/ and any ?)
    slug = "EQBG-g6ahkAUGWpefWbx-D_9sQ8oWbvy6puuq78U2c4NUDFS"

    try:
        listings = fetch_getgems_for_sale(slug)
        if not listings:
            print("No items currently listed for sale in this collection.")
        else:
            for nft in listings:
                # Print all available fields for each NFT
                for key, value in nft.items():
                    print(f"{key.capitalize()}: {value}")
                print("-" * 40)
    except Exception as e:
        import traceback

        print("❌ Error fetching listings:")
        traceback.print_exc()





#
# import requests
# import json
#
#
# url = "https://marketapp.ws/nft/buy/"
# cookies = {
#     "session": "eyJsb2NhbGUiOiAiZW4iLCAidG9uX3Byb29mIjogImMxZTQyYzQ0ZDk2Y2YyOWIiLCAiYWRkcmVzcyI6ICIwOjU3YzhlMTUyNTE5NzRjZTIzNDZmNzYyMDFhZmE5MTE3YTZlMjMyMzMyMzhhYTA5MmY1ZGIzMjEwOGVmYjliMDgiLCAicmVmIjogIlY4amhVbEdYVE9JMGIzWWdHdnFSRjZiaU1qTWppcUNTOWRzeUVJNzdtd2c9IiwgImRuc19yZWNvcmQiOiAiIiwgImFwcF9uYW1lIjogInRlbGVncmFtLXdhbGxldCBicm93c2VyIiwgIm1heF9tZXNzYWdlcyI6IDI1NX0=.aFAo4Q.rafdA3SVgBg2a-u7ILUnvL-eaNE"
# }
# headers = {
#     "Accept": "*/*",
#     "Content-Type": "application/json",
#     "Origin": "https://marketapp.ws",
#     "Referer": "https://marketapp.ws/nft/EQDihO_7507EtNhDYxAXPwjZY5on4Vp19n6-ss3ovVWi3scN/",
#     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)..."
# }
# data = {
#     "nfts": {
#         "EQDihO_7507EtNhDYxAXPwjZY5on4Vp19n6-ss3ovVWi3scN": "18000000000"
#     }
# }
#
# response = requests.post(url, headers=headers, cookies=cookies, json=data)
#
# print("Status:", response.status_code)
# print("Text:", response.text or "[Empty]")
#
# try:
#     json_data = response.json()
#     transaction = json_data.get("transaction", {})
#     messages = transaction.get("messages", [])
#     for msg in messages:
#         print("\n--- Transaction Message ---")
#         print("To Address:", msg.get("address"))
#         print("Amount (nanoTON):", msg.get("amount"))
#         print("Payload (base64):", msg.get("payload"))
#         try:
#             import base64
#             decoded_payload = base64.b64decode(msg.get("payload")).decode('utf-8', errors='ignore')
#             print("Decoded Payload (utf-8):", decoded_payload)
#         except Exception as decode_error:
#             print("Error decoding payload:", str(decode_error))
#
# # Note: Metadata such as rarity, model, backdrop, symbol, or sales history may not be present
# # in the transaction payload. To obtain such information, you may need to use a separate API call
# # or endpoint that provides NFT metadata.
# except Exception as e:
#     print("Error decoding JSON or extracting attributes:", str(e))
