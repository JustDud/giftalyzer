import requests

def fetch_nft_history_from_tonviewer(address: str, limit: int = 10):
    url = "https://tonviewer.com/graphql"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    query = """
    query ($address: String!, $limit: Int!) {
      transactions(address: $address, limit: $limit) {
        edges {
          node {
            hash
            timestamp
            account
            balance_delta
            message {
              sender
              recipient
              amount
            }
          }
        }
      }
    }
    """

    payload = {
        "operationName": None,
        "variables": {
            "address": address,
            "limit": limit
        },
        "query": query
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            print(f"[{address}] Non-JSON response received:")
            print(response.text)
            return []

        transactions = data.get("data", {}).get("transactions", {}).get("edges", [])
        return [tx["node"] for tx in transactions]
    except Exception as e:
        print(f"Error fetching transaction history for {address}: {e}")
        return []

if __name__ == "__main__":
    history = fetch_nft_history_from_tonviewer("EQB0DhStvuGvy0R5a4jDL7LotGr7kXiBtOCw2pvgMwW0y1H7", limit=20)
    for tx in history:
        print(tx)
