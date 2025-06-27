import os
import json
import requests
import glob
from tqdm import tqdm

import os, json, glob

def extract_all_nft_addresses(collections_dir):
    nft_addresses = []
    print(f"Scanning folder: {collections_dir}")
    for file_path in glob.glob(os.path.join(collections_dir, "*.json")):
        print(f"Reading file: {file_path}")
        with open(file_path, "r") as f:
            try:
                items = json.load(f)
                print(f"   → Found {len(items)} items")
                for item in items:
                    href = item.get("href")
                    if href and href.startswith("/nft/"):
                        address = href.split("/nft/")[1].strip("/")
                        nft_addresses.append(address)
            except Exception as e:
                print(f"Error in {file_path}: {e}")
    print(f"Total NFT addresses extracted: {len(nft_addresses)}")
    return nft_addresses


def query_marketapp_batches(nft_addresses, batch_size=20):
    url = "https://marketapp.ws/user/action/prepare/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://marketapp.ws/",
        "Origin": "https://marketapp.ws",
        "Content-Type": "application/json"
    }


    for i in tqdm(range(0, len(nft_addresses), batch_size), desc="Querying MarketApp"):
        batch = nft_addresses[i:i+batch_size]
        payload = {
            "type": "buy",
            "nft_addresses": batch
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            print(f"Batch {i // batch_size + 1} ➜ Status {response.status_code}")

            if not response.headers.get("Content-Type", "").startswith("application/json"):
                print("   ❌ Non-JSON response:\n", response.text[:300])
                continue  # Skip bad batch

            data = response.json()
            if "h" in data:
                print(f"\n✅ Batch {i//batch_size + 1}: HTML fragment received.")
            if "j" in data:
                print("📦 Contains JavaScript.")
            if "detail" in data:
                print(f"⚠️ Error: {data['detail']}")
        except Exception as e:
            print(f"❌ Error in batch {i//batch_size + 1}: {e}")


if __name__ == "__main__":
    collections_dir = os.path.join(
        os.path.dirname(__file__),
        "../scraped_output/collections"
    )
    collections_dir = os.path.abspath(collections_dir)
    nft_addresses = extract_all_nft_addresses(collections_dir)
    print(f"🔎 Total NFTs to query: {len(nft_addresses)}")
    query_marketapp_batches(nft_addresses)