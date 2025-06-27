import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
load_dotenv()  # loads FRAGMENT_CLIENT_ID and FRAGMENT_CLIENT_SECRET from .env

def get_fragment_access_token():
    client_id = os.getenv("FRAGMENT_CLIENT_ID")
    client_secret = os.getenv("FRAGMENT_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("Error: FRAGMENT_CLIENT_ID or FRAGMENT_CLIENT_SECRET not set in environment.")
        return None
    auth_url = "https://auth.eu-west-1.fragment.dev/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.eu-west-1.fragment.dev/*"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(auth_url, auth=HTTPBasicAuth(client_id, client_secret), data=data, headers=headers)
    resp.raise_for_status()
    return resp.json().get("access_token")

def fetch_fragment_gifts(limit=10):
    token = get_fragment_access_token()
    if not token:
        print("No access token; please set your Fragment credentials.")
        return []
    api_url = "https://api.eu-west-1.fragment.dev/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    gql_query = {
        "query": """
            query ($limit: Int!) {
              gifts(limit: $limit) {
                id
                name
                price
                owner { address }
              }
            }
        """,
        "variables": {"limit": limit}
    }
    resp = requests.post(api_url, json=gql_query, headers=headers)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    return data.get("gifts", [])


if __name__ == "__main__":
    for gift in fetch_fragment_gifts(5):
        print(f"{gift['name']} - {gift['price']} - owner: {gift['owner']['address']}")
