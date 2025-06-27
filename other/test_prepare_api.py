import requests
import json

collection_url = "https://marketapp.ws/collection/EQBG2o0lp-6Oy86NGEJm717BeTDAw_F5ELkgaX2l9UsfavWE"

cookies = {
    "session": "eyJsb2NhbGUiOiAiZW4iLCAidG9uX3Byb29mIjogImMxZTQyYzQ0ZDk2Y2YyOWIiLCAiYWRkcmVzcyI6ICIwOjU3YzhlMTUyNTE5NzRjZTIzNDZmNzYyMDFhZmE5MTE3YTZlMjMyMzMyMzhhYTA5MmY1ZGIzMjEwOGVmYjliMDgiLCAicmVmIjogIlY4amhVbEdYVE9JMGIzWWdHdnFSRjZiaU1qTWppcUNTOWRzeUVJNzdtd2c9IiwgImRuc19yZWNvcmQiOiAiIiwgImFwcF9uYW1lIjogInRlbGVncmFtLXdhbGxldCBicm93c2VyIiwgIm1heF9tZXNzYWdlcyI6IDI1NX0=.aFAo4Q.rafdA3SVgBg2a-u7ILUnvL-eaNE"
}
headers = {
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://marketapp.ws",
    "Referer": collection_url,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)..."
}

import os

# Load real rows from collection file
collection_file_path = "../scraped_output/collections/EQBI07PXew94YQz7GwN72nPNGF6htSTOJkuU4Kx_bjTZv32U.json"
with open(collection_file_path, "r") as f:
    nfts = json.load(f)

# Filter to only test the specific NFTs
test_nft_ids = [
    "EQCjaS2j66Z0FEU9PyPKyvFM5qaGLJHdY-OKhckHnBMAj7Xt",
    "EQC3xPlfAtAarYpkIVhHeECKnNLovLvJCmVmeFdh6S7wHiKQ"
]
nfts = [nft for nft in nfts if any(nft_id in nft.get("href", "") for nft_id in test_nft_ids)]

for nft in nfts:
    print(f"--- Processing NFT: {nft['name']} ---")
    # print(json.dumps(nft, indent=2))
    # Extract NFT ID from href
    href = nft.get("href", "")
    nft_id = href.split("/nft/")[-1].rstrip("/") if "/nft/" in href else None
    if not nft_id:
        nft["current_price"] = None
        continue

    # --- PATCH: Use hardcoded default floor price for SwissWatchCollection ---
    # Simulate a collection_floors dict (in real use, would be loaded elsewhere)
    collection_floors = {}
    # Set default for SwissWatchCollection (replace with actual address if needed)
    SWISS_WATCH_COLLECTION_ADDRESS = None  # Replace with actual if available
    # Try to get collection_address from NFT (simulate)
    collection_address = nft.get("collection_address")
    if nft_id == "EQCjaS2j66Z0FEU9PyPKyvFM5qaGLJHdY-OKhckHnBMAj7Xt":
        price = "66.0"
    else:
        price = "57.2"
    price = price.replace(',', '').strip()
    # Check if price is valid number
    if not price or not price.replace('.', '', 1).isdigit():
        print(f"[SKIP] Invalid price for NFT {nft_id}: {price}")
        continue

    # Fallback price attempts: use only the actual floor price
    fallback_prices = [float(price)]
    url = "https://marketapp.ws/nft/buy/"
    amount_result = None
    for attempt_price in fallback_prices:
        try:
            attempt_price = float(attempt_price)
            nanotones = str(int(attempt_price * 1e9))
            # Debug prints
            print(f"[DEBUG] NFT ID: {nft_id}")
            print(f"[DEBUG] Floor price: {price}")
            print(f"[DEBUG] Converted Price (nanotones): {nanotones}")
            print(f"[DEBUG] Preparing transaction for: {nft_id} at {nanotones} nanotones")
            # print(f"[RETURN] Price used for NFT {nft_id}: {price} TON ({nanotones} nanotons)")
            data = {
                "nfts": {
                    nft_id: nanotones
                }
            }
            response = requests.post(url, headers=headers, cookies=cookies, json=data)
            print(f"[DEBUG] Response text: {response.text}")
            if response.status_code == 200:
                json_data = response.json()
                transaction = json_data.get("transaction", {})
                messages = transaction.get("messages", [])
                # Find amount from messages if available
                amount = None
                for msg in messages:
                    amount = msg.get("amount")
                    if amount:
                        break
                amount_result = amount if amount is not None else "[No amount]"
                break  # success
            else:
                amount_result = f"Error: Status {response.status_code}"
        except Exception as e:
            print(f"[ERROR] Attempt with price {attempt_price} failed: {e}")
            amount_result = f"Exception: {str(e)}"
    nft["current_price"] = amount_result
    print(f"Current price result: {nft['current_price']}")
