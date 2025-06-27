import requests
import json


def fetch_nfts_from_tonapi(collection_address: str, limit: int = 600):
    base_url = f"https://tonapi.io/v2/nfts/collections/{collection_address}/items"
    offset = 0
    all_nfts = []

    while True:
        params = {
            "limit": limit,
            "offset": offset,
        }
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        items = data.get("nft_items", [])
        if not items:
            break

        processed_count = len(all_nfts)

        for item in items:
            if len(all_nfts) >= 500:
                break
            nft = {}
            address = item.get("address")
            nft["id"] = address
            nft["name"] = item.get("metadata", {}).get("name") or address
            nft["attributes"] = item.get("metadata", {}).get("attributes", [])
            # Fetch extended NFT info
            try:
                nft_info_url = f"https://tonapi.io/v2/nfts/{address}"
                nft_info_response = requests.get(nft_info_url)
                nft_info_response.raise_for_status()
                nft_info = nft_info_response.json()
                nft["owner"] = nft_info.get("owner", {}).get("address", "unknown")
                nft["verified"] = nft_info.get("verified", False)
                nft["last_sale"] = nft_info.get("last_sale", {})
            except Exception:
                nft["owner"] = "error"
                nft["verified"] = False
                nft["last_sale"] = {}
            all_nfts.append(nft)

        if len(all_nfts) >= 50:
            break

        if len(items) < limit:
            break
        offset += limit

    with open(f"alldata_{collection_address}.json", "w", encoding="utf-8") as f:
        json.dump(all_nfts, f, ensure_ascii=False, indent=2)

    print(f"Total NFTs fetched: {len(all_nfts)}")
    return all_nfts




if __name__ == "__main__":
    collection_slug = "EQBG-g6ahkAUGWpefWbx-D_9sQ8oWbvy6puuq78U2c4NUDFS"
    try:
        listings = fetch_nfts_from_tonapi(collection_slug)
        for nft in listings:
            print(f"Address: {nft['id']}")
            print(f"Name: {nft['name']}")
            print(f"Attributes: {nft['attributes']}")
            print(f"Owner: {nft['owner']}")
            print(f"Verified: {nft['verified']}")
            print(f"Last Sale: {nft['last_sale']}")
            print("-" * 40)
    except Exception as e:
        import traceback
        print("Error fetching listings:")
        traceback.print_exc()




import requests
import json


def fetch_nfts_from_tonapi(collection_address: str, limit: int = 600):
    base_url = f"https://tonapi.io/v2/nfts/collections/{collection_address}/items"
    offset = 0
    all_nfts = []

    while True:
        params = {
            "limit": limit,
            "offset": offset,
        }
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()

        items = data.get("nft_items", [])
        if not items:
            break

        for item in items:
            nft = {}
            address = item.get("address")
            nft["id"] = address
            nft["name"] = item.get("metadata", {}).get("name") or address
            nft["attributes"] = item.get("metadata", {}).get("attributes", [])
            all_nfts.append(nft)

        if len(items) < limit:
            break
        offset += limit

    with open(f"alldata_{collection_address}.json", "w", encoding="utf-8") as f:
        json.dump(all_nfts, f, ensure_ascii=False, indent=2)

    print(f"Total NFTs fetched: {len(all_nfts)}")
    return all_nfts




if __name__ == "__main__":
    collection_slug = "EQBG-g6ahkAUGWpefWbx-D_9sQ8oWbvy6puuq78U2c4NUDFS"
    try:
        listings = fetch_nfts_from_tonapi(collection_slug)
        for nft in listings:
            print(f"Address: {nft['id']}")
            print(f"Name: {nft['name']}")
            print(f"Attributes: {nft['attributes']}")
            print("-" * 40)
    except Exception as e:
        import traceback
        print("Error fetching listings:")
        traceback.print_exc()

