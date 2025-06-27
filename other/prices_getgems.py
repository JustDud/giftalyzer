import requests
import time
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import re
from selenium.webdriver.support.ui import WebDriverWait
import csv

from tonsdk.utils import Address

load_dotenv()
API_KEY = os.getenv("TON_API")
COLLECTION_ADDRESS = "EQBG-g6ahkAUGWpefWbx-D_9sQ8oWbvy6puuq78U2c4NUDFS"

headers = {
    "Authorization": f"Bearer {API_KEY}"
}


def scrape_prices_from_collection_page(collection_address):
    start_time = time.time()
    output_dir = os.path.join("data_collection", "scraped_output")
    os.makedirs(output_dir, exist_ok=True)
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    url = f"https://getgems.io/collection/{collection_address}?filter=%7B%22saleType%22%3A%22fix_price%22%7D"
    driver.get(url)

    # Scrolls to load all NFTs
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # Waits up to 25s for at least one NFT card
    try:
        WebDriverWait(driver, 25).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "div[data-address]")) > 0
        )
    except Exception as e:
        print(f"Timeout or error while waiting for NFT cards: {e}")
        with open("debug_output_after_timeout.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.save_screenshot("screenshot_after_timeout.png")
        driver.quit()
        return

    cards = driver.find_elements(By.CSS_SELECTOR, "div.NftItemContainer[data-address]")
    print(f"Found {len(cards)} NFT cards on the page.")

    nft_list = []
    retry_cards = []
    for card in cards:
        try:
            base64_address = card.get_attribute("data-address")
            address = base64_to_hex(base64_address)
            name_elem = card.find_element(By.CSS_SELECTOR, ".LibraryTypography")
            name = name_elem.text.strip()

            price_elem = card.find_element(By.CSS_SELECTOR, ".LibraryCryptoPrice__amount")
            price_text = price_elem.text.strip()
            price_clean = re.sub(r"[^\d]", "", price_text)
            price = int(price_clean)

            attributes_elements = card.find_elements(By.CSS_SELECTOR, ".NftProperty")
            attributes = {}
            for attr_elem in attributes_elements:
                try:
                    key_elem = attr_elem.find_element(By.CSS_SELECTOR, ".NftProperty__title")
                    value_elem = attr_elem.find_element(By.CSS_SELECTOR, ".NftProperty__subtitle")
                    key = key_elem.text.strip()
                    value = value_elem.text.strip()
                    if key:
                        attributes[key] = value
                except Exception:
                    continue

            nft_list.append({
                "id": address,
                # "name": name,
                # "address": address,
                "price": price,
            })
        except Exception as e:
            print(f"Skipped card due to error: {e}")
            name_text = "N/A"
            address_text = "N/A"
            try:
                name_text = card.find_element(By.CSS_SELECTOR, ".LibraryTypography").text.strip()
            except:
                pass
            try:
                base64_address = card.get_attribute("data-address")
                address_text = base64_to_hex(base64_address)
            except:
                pass
            print(f"↪Name: {name_text} | Address: {address_text}")
            retry_cards.append(card)
            continue

    if retry_cards:
        print(f"Retrying {len(retry_cards)} skipped cards...")
        for card in retry_cards:
            try:
                base64_address = card.get_attribute("data-address")
                address = base64_to_hex(base64_address)
                name_elem = card.find_element(By.CSS_SELECTOR, ".LibraryTypography")
                name = name_elem.text.strip()

                price_elem = card.find_element(By.CSS_SELECTOR, ".LibraryCryptoPrice__amount")
                price_text = price_elem.text.strip()
                price_clean = re.sub(r"[^\d]", "", price_text)
                price = int(price_clean)

                nft_list.append({
                    "id": address,
                    "name": name,
                    "address": address,
                    "price": price,
                })
                print(f"Retried: {name} | {address}")
            except Exception as e:
                print(f"Retry failed for {address}")
                continue

    if not nft_list:
        print("No NFTs with visible prices found.")
        with open("debug_output.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Saved page HTML to debug_output.html")
    else:
        # json_path = os.path.join(output_dir, f"prices_{collection_address}.json")
        # with open(json_path, "w") as f:
        #     json.dump(nft_list, f, indent=2)
        # print(f"Saved {len(nft_list)} NFTs with prices to {json_path}")
        csv_filename = os.path.join(output_dir, f"prices_{collection_address}.csv")
        with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=["id", "price"])
            writer.writeheader()
            for nft in nft_list:
                writer.writerow({
                    "id": nft["id"],
                    "price": nft["price"]
                })
        print(f"Saved CSV to {csv_filename}")

    end_time = time.time()
    print(f"Scraping completed in {end_time - start_time:.2f} seconds.")
    driver.quit()
    return  nft_list


def base64_to_hex(addr: str) -> str:
    return Address(addr).to_string(False, False)

if __name__ == "__main__":
    scrape_prices_from_collection_page(COLLECTION_ADDRESS)