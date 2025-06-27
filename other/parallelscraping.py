# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.common.by import By
# import time
# import json
#
# COLLECTION_ADDRESS = "EQBG-g6ahkAUGWpefWbx-D_9sQ8oWbvy6puuq78U2c4NUDFS"
# COLLECTION_URL = f"https://getgems.io/collection/{COLLECTION_ADDRESS}?filter=%7B%22saleType%22%3A%22fix_price%22%7D"
#
# def scrape_nfts_from_collection(url):
#     options = Options()
#     options.add_argument("--headless=new")
#     options.add_argument("--disable-gpu")
#     options.add_argument("--no-sandbox")
#     driver = webdriver.Chrome(options=options)
#
#     try:
#         driver.get(url)
#         time.sleep(5)
#         script = driver.find_element(By.ID, '__NEXT_DATA__').get_attribute('innerHTML')
#         data = json.loads(script)
#
#         items = data.get("props", {}).get("pageProps", {}).get("nfts", [])
#         results = []
#
#         for nft in items:
#             results.append({
#                 'name': nft.get('name'),
#                 'symbol': nft.get('symbol'),
#                 'attributes': nft.get('attributes', []),
#                 'model': nft.get('model'),
#                 'background': nft.get('background'),
#                 'price': nft.get('price'),
#                 'address': nft.get('address')
#             })
#
#         return results
#
#     except Exception as e:
#         print(f"❌ Error: {e}")
#         return []
#
#     finally:
#         driver.quit()


import requests
import json

import requests
import json

def fetch_nft_names(collection_address):
    url = "https://api.getgems.io/graphql"
    query = """
    query GetNFTs($input: FilterInput!, $first: Int!) {
      nftItems(filter: $input, first: $first) {
        items {
          name
          address
        }
      }
    }
    """
    variables = {
        "input": {"collectionAddress": collection_address},
        "first": 10
    }

    response = requests.post(
        url,
        json={"query": query, "variables": variables},
        headers={"Content-Type": "application/json"}
    )

    data = response.json()
    print(json.dumps(data, indent=2))

fetch_nft_names("EQBG-g6ahkAUGWpefWbx-D_9sQ8oWbvy6puuq78U2c4NUDFS")

def main():
    result = fetch_nft_attributes("EQBG-g6ahkAUGWpefWbx-D_9sQ8oWbvy6puuq78U2c4NUDFS")
    if result:
        print(f"✅ Found {len(result)} NFTs")
        for nft in result:
            print(f"🔹 {nft.get('name', 'Unnamed NFT')}")


