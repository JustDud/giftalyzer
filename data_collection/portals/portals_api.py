import asyncio
from urllib.parse import unquote, quote_plus
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName, InputUser
from pyrogram.raw.functions.users import GetUsers
from curl_cffi import requests
import re

# collections_ids = {
#     "Plush Pepe": "8d21b568-63bb-437a-9093-8684c5b63485",
#     "Loot Bag": "db7f4abd-96d9-4968-ba81-7f1a07bc2e9c",
#     "Bow Tie": "216c52eb-447a-4775-921d-a59f9b67082c",
#     "Heroic Helmet": "013a775d-4d7d-457b-9d3d-30a6429ea79f",
#     "Durov's Cap": "fc46d19d-5f25-44c5-8924-5976c2fb790e",
#     "Nail Bracelet": "40311c45-48a8-4863-8abb-7156ae62767b",
#     "Swiss Watch": "f0125f02-2b17-4882-95b4-8715a88678a5",
#     "Bonded Ring": "07484deb-1790-4a21-9d2f-ece02acdcb84",
#     "Precious Peach": "40131849-420d-4775-b616-6d359c17c22f",
#     "Gem Signet": "020c2380-709d-4d09-bbad-814852b32551",
#     "Vintage Cigar": "48204369-2f95-4909-8018-1660b37c2b9d",
#     "Light Sword": "0ebbc5d6-f59f-49f5-9a48-7a1fc1625093",
#     "Toy Bear": "060d4cef-3a21-47e6-98fc-cd338ae0b5e0",
#     "Neko Helmet": "f3e9621f-a32f-49d9-b602-71ecf2515ded",
#     "Lol Pop": "98850266-bb6c-43a6-9559-accedf420a02",
#     "Ion Gem": "47f0cf89-4fc9-4aa2-99b2-7f3cf9a6c16a",
#     "Astral Shard": "207d7011-8359-429c-b86b-df191b3659dd",
#     "Sharp Tongue": "308fc63d-1ebc-4e31-865e-c756018e4dff",
#     "Diamond Ring": "45aa08dd-94e0-492f-bf04-1952aa024951",
#     "Restless Jar": "9537661e-290b-49f3-adaf-d96e8f590288",
#     "Signet Ring": "a1a5ec7e-53b9-45b9-91e5-cad37a15fe5e",
#     "Scared Cat": "a4a90909-9a06-4b78-9d75-4de42280334a",
#     "Easter Egg": "88a37665-6d13-4619-afa9-47de8464adb4",
#     "Genie Lamp": "7693b50e-b9ad-4eed-8791-a7b4bf3ea726",
#     "Electric Skull": "43b4502a-ca8c-49e8-ba5d-03cdf66d8f48",
#     "Perfume Bottle": "e1b2c024-a443-4637-b451-02904a6bc3f6",
#     "Voodoo Doll": "ba7390cc-72d4-45ce-96e4-d243e22a6500",
#     "Kissed Frog": "2c68a297-604a-4710-a32e-d3eac17e15ae",
#     "Hanging Star": "1d7b6d74-5eef-45ee-b25b-632a96b9505a",
#     "Magic Potion": "a17b488a-3942-4eae-89f9-bba2ce342c6b",
#     "Tama Gadget": "beed4df4-cce3-4b21-aefe-0cc5e5196834",
#     "Top Hat": "860ae248-5a63-4ea9-ae6d-defd3c0952b9",
#     "Desk Calendar": "ae8f48a9-e090-44f2-9c61-5928702ab171",
#     "Sleigh Bell": "8519c4e9-ef09-48fd-af9c-9e7412809e7c",
#     "Flying Broom": "73de1866-6b90-45b4-a543-fb5ea9ca1415",
#     "Trapped Heart": "bef99328-29f3-454a-abef-4d2f34b3bf3f",
#     "Love Potion": "7369ac28-ddaf-4100-9a75-a4225b64e1b0",
#     "Eternal Rose": "fa27c78c-6eb9-4653-a619-19544b8255b1",
#     "Mad Pumpkin": "1f281b21-1955-4691-923c-8f58ce00a456",
#     "Eternal Candle": "257ad54a-134c-437c-ab1e-febc4c798243",
#     "Sakura Flower": "1c1616f5-2f39-47dc-9f27-e77fa1b6a569",
#     "Snow Globe": "ffdfcb47-b9c9-4a5c-a59f-d6d236b583cf",
#     "Mini Oscar": "ea3f1a6f-80c8-4abf-8c56-cd41a0e1c89a",
#     "Record Player": "99cb46d0-c724-4e27-8497-ac381e10d97c",
#     "Love Candle": "128c7b37-36db-4b21-a21b-7d858c8dbc1a",
#     "Evil Eye": "f639a421-45df-4848-ac69-a089746828c4",
#     "Witch Hat": "a7253309-ed0e-4d5d-972c-2bc9c0194bea",
#     "Crystal Ball": "ac575eb3-2929-48d6-96d0-1db8f12243de",
#     "Bunny Muffin": "586cd461-0194-49af-86b0-cbc3b55a2a65",
#     "Spy Agaric": "a39d2458-5df0-42ff-98d5-08af484001d6",
#     "Skull Flower": "61a23d97-cf11-4c91-8435-476ba84c81eb",
#     "Homemade Cake": "f7a194d4-d53a-419a-b357-3c794f6cd98b",
#     "Holiday Drink": "6bf906a0-e5b1-4c7f-b741-a70c3f7ed77b",
#     "Jelly Bunny": "1a139fcf-5850-48c3-aee6-924134ad17d8",
#     "Party Sparkler": "53110539-1d3e-4334-9692-a665e0527f69",
#     "Big Year": "8b58d6ea-a8e0-47ef-bdd1-3ade5d5ea0cb",
#     "Ginger Cookie": "b85209cd-4e16-4d1a-985c-d784619fe2d0",
#     "Pet Snake": "563ed415-a63b-49e8-870d-745602fb3de3",
#     "Jack-in-the-Box": "996e7628-28bf-4874-b3ec-2e5f7c1cb684",
#     "Snow Mittens": "0009551d-bdd4-40ee-a276-b6e01fa4d327",
#     "B-Day Candle": "12efb9cd-179f-44c6-af65-a63480691c18",
#     "Berry Box": "b8747d58-90ed-49cf-8e29-b9e2c8b3e7a6",
#     "Xmas Stocking": "acebace7-be16-4a4b-9b02-c274bed4c856",
#     "Jingle Bells": "1501b9b9-83e0-4d05-a3af-d0e2021c6d5e",
#     "Candy Cane": "8b001ea2-5a73-4a61-a3a2-6f01d557fee7",
#     "Santa Hat": "b577efed-76dc-410f-bda9-edae43ab0f4a",
#     "Cookie Heart": "35c106ab-7133-4f10-a502-e2c602b64da9",
#     "Spiced Wine": "9aac072e-34d6-4819-a7f4-70ad25af8196",
#     "Hex Pot": "66e62058-8600-471f-909b-844751f5f103",
#     "Lunar Snake": "a4b271b4-efa3-4854-b53f-9ae6f3ecac59",
#     "Hypno Lollipop": "fe1816f1-a6a9-4770-8921-839a5bfa5a22",
#     "Star Notepad": "a76231dd-a8be-4f06-b7a3-e119b65074da",
#     "Snake Box": "f50f29bb-70b5-4502-a21b-8eadf20518fa",
#     "Jester Hat": "ea32e880-b03c-4791-9385-68d24db9784b",
#     "Winter Wreath": "13bada87-1353-4db5-b77c-d451c95365e0"
#     }


def cap(text) -> str:
    words = re.findall(r"\w+(?:'\w+)?", text)
    for word in words:
        if len(word) > 0:
            cap = word[0].upper() + word[1:]
            text = text.replace(word, cap, 1)
    return text


def listToURL(gifts: list) -> str:
    return '%2C'.join(quote_plus(cap(gift)) for gift in gifts)


def activityListToURL(activity: list) -> str:
    return '%2C'.join(activity)


def toShortName(gift_name):
    return gift_name.replace(" ", "").replace("'", "").replace("’", "").replace("-", "").lower()


async def update_auth(api_id: int | str, api_hash: str) -> str:
    """
    Updates Telegram authData for Portals API using Pyrogram.

    Args:
        api_id (int|str)
        api_hash (str)

    Returns:
        str: new authData
    """
    async with Client("account", api_id=api_id, api_hash=api_hash) as client:
        peer = await client.resolve_peer("portals")
        user_full = await client.invoke(GetUsers(id=[peer]))
        bot_raw = user_full[0]
        bot = InputUser(user_id=bot_raw.id, access_hash=bot_raw.access_hash)
        bot_app = InputBotAppShortName(bot_id=bot, short_name="market")
        web_view = await client.invoke(
            RequestAppWebView(
                peer=peer,
                app=bot_app,
                platform="desktop",
            )
        )
        initData = unquote(web_view.url.split('tgWebAppData=', 1)[1].split('&tgWebAppVersion', 1)[0])
        return f"tma {initData}"


SORTS = {
    "latest": "&sort_by=listed_at+desc",
    "price_asc": "&sort_by=price+asc",
    "price_desc": "&sort_by=price+desc",
    "gift_id_asc": "&sort_by=external_collection_number+asc",
    "gift_id_desc": "&sort_by=external_collection_number+desc",
    "model_rarity_asc": "&sort_by=model_rarity+asc",
    "model_rarity_desc": "&sort_by=model_rarity+desc"
}

API_URL = "https://portals-market.com/api/"

HEADERS = {
    "Authorization": "",
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Origin": "https://portals-market.com",
    "Referer": "https://portals-market.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0"
}


def search(sort: str = "price_asc", offset: int = 0, limit: int = 20, gift_name: str | list = "",
           model: str | list = "", backdrop: str | list = "", symbol: str | list = "", min_price: int = 0,
           max_price: int = 100000, authData: str = "") -> list:
    """
    Search for gifts with various filters and sorting options.

    Args:
        sort (str): The sorting method for the results. Available options:
            "price_asc", "price_desc", "latest", "gift_id_asc", "gift_id_desc",
            "model_rarity_asc", "model_rarity_desc". Defaults to "price_asc".
        offset (int): The pagination offset (limit*page). Defaults to 0.
        limit (int): The maximum number of results to return. Defaults to 20 (probably max is 20).
        gift_name (str | list): The name or list of names of gifts to filter.
        model (str | list): The model or list of models to filter.
        backdrop (str | list): The backdrop or list of backdrops to filter.
        symbol (str | list): The symbol or list of symbols to filter.
        min_price (int): The minimum price of the gifts to filter. Defaults to 0.
        max_price (int): The maximum price of the gifts to filter. Defaults to 100000.
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of dictionaries containing the search results.

    Raises:
        Exception: If min_price or max_price are not integers.
        Exception: If max_price is less than min_price.
        Exception: If authData is not provided.
        Exception: If gift_name, model, backdrop, or symbol are not strings or lists.
        Exception: If the API request fails.
    """

    URL = API_URL + "nfts/" + "search?" + f"offset={offset}" + f"&limit={limit}" + f"{SORTS[sort]}"

    try:
        min_price = int(min_price)
        max_price = int(max_price)
    except:
        raise Exception("portalsmp: search(): Error: min_price and max_price must be integers")

    if max_price < 100000:
        URL += f"&min_price={min_price}&max_price={max_price}"

    if authData == "":
        raise Exception("portalsmp: search(): Error: authData is required")
    if max_price < min_price:
        raise Exception("portalsmp: search(): Error: max_price must be greater than min_price")

    if gift_name:
        if type(gift_name) == str:
            URL += f"&filter_by_collections={quote_plus(cap(gift_name))}"
        elif type(gift_name) == list:
            URL += f"&filter_by_collections={listToURL(gift_name)}"
        else:
            raise Exception("portalsmp: search(): Error: gift_name must be a string or list")
    if model:
        if type(model) == str:
            URL += f"&filter_by_models={quote_plus(cap(model))}"
        elif type(model) == list:
            URL += f"&filter_by_models={listToURL(model)}"
        else:
            raise Exception("portalsmp: search(): Error: model must be a string or list")
    if backdrop:
        if type(backdrop) == str:
            URL += f"&filter_by_backdrops={quote_plus(cap(backdrop))}"
        elif type(backdrop) == list:
            URL += f"&filter_by_backdrops={listToURL(backdrop)}"
        else:
            raise Exception("portalsmp: search(): Error: backdrop must be a string or list")
    if symbol:
        if type(symbol) == str:
            URL += f"&filter_by_symbols={quote_plus(cap(symbol))}"
        elif type(symbol) == list:
            URL += f"&filter_by_symbols={listToURL(symbol)}"
        else:
            raise Exception("portalsmp: search(): Error: symbol must be a string or list")

    URL += "&status=listed"

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: search(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json()["results"] if response.json()["results"] else response.json()


def giftsFloors(authData: str = "") -> dict:
    """
    Retrieves the floor prices for all gift collections (short names only).

    Args:
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the floor prices of collections if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """

    URL = API_URL + "collections/floors"

    if authData == "":
        raise Exception("portalsmp: giftsFloors(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: giftsFloors(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json()['floorPrices'] if response.json()['floorPrices'] else None


def myPortalsGifts(offset: int = 0, limit: int = 20, listed: bool = True, authData: str = "") -> list:
    """
    Retrieves a list of the user's owned Portal gifts.

    Args:
        offset (int): The offset for pagination.
        limit (int): The maximum number of items to return.
        listed (bool): If True, only gifts listed for sale are shown. Defaults to True.
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of the user's owned Portal gifts if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "nfts/" + "owned?" + f"offset={offset}" + f"&limit={limit}"

    if authData == "":
        raise Exception("portalsmp: myPortalsGifts(): Error: authData is required")
    if listed == True:
        URL += "&status=listed"
    else:
        URL += "&status=unlisted"

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: myPortalsGifts(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json()['nfts'] if 'nfts' in response.json() else response.json()


def myPoints(authData: str = "") -> dict:
    """
    Retrieves the user's Portals Points information.

    Args:
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the user's points information if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "points/my-points"

    if authData == "":
        raise Exception("portalsmp: myPoints(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: myPoints(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def myBalances(authData: str = "") -> dict:
    """
    Retrieves the user's balances.

    Args:
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the user's balances if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "users/wallets/"

    if authData == "":
        raise Exception("portalsmp: myBalances(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: myBalances(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def myActivity(offset: int = 0, limit: int = 20, authData: str = "") -> list:
    """
    Retrieves the user's activity on the marketplace.

    Args:
        offset (int): The pagination offset (limit*page). Defaults to 0.
        limit (int): The maximum number of results to return. Defaults to 20.
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of dictionaries containing the user's activity if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "users/actions/" + f"?offset={offset}" + f"&limit={limit}"

    if authData == "":
        raise Exception("portalsmp: myActivity(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: myActivity(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json()['actions'] if response.json()['actions'] else response.json()


def collections(limit: int = 100, authData: str = "") -> list:
    """
    Retrieves a list of collections and their floors, supply, daily volume etc from the marketplace.

    Args:
        limit (int): The maximum number of results to return. Defaults to 100.
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of dictionaries containing information about the collections if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "collections" + f"?limit={limit}"

    if authData == "":
        raise Exception("portalsmp: collections(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: collections(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json()['collections'] if response.json()['collections'] else response.json()


def marketActivity(sort: str = "latest", offset: int = 0, limit: int = 20, activityType: str | list = "",
                   gift_name: str | list = "", model: str | list = "", backdrop: str | list = "",
                   symbol: str | list = "", min_price: int = 0, max_price: int = 100000, authData: str = "") -> list:
    """
    Retrieves market activity with various filters and sorting options.

    Args:
        sort (str): The sorting method for the results. Options include "latest", "price_asc", "price_desc",
            "gift_id_asc", "gift_id_desc", "model_rarity_asc", "model_rarity_desc". Defaults to "latest".
        offset (int): The pagination offset (limit*page). Defaults to 0.
        limit (int): The maximum number of results to return. Defaults to 20.
        activityType (str): The type of activity to filter by. Options are "buy", "listing", "price_update",
            "offer", or an empty string for no filter.
        gift_name (str | list): The name or list of names of gifts to filter.
        model (str | list): The model or list of models to filter.
        backdrop (str | list): The backdrop or list of backdrops to filter.
        symbol (str | list): The symbol or list of symbols to filter.
        min_price (int): The minimum price of the gifts to filter. Defaults to 0.
        max_price (int): The maximum price of the gifts to filter. Defaults to 100000.
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of dictionaries containing the market activity results.

    Raises:
        Exception: If authData is not provided.
        Exception: If max_price is less than min_price.
        Exception: If activityType is not one of the valid options.
        Exception: If gift_name, model, backdrop, or symbol are not strings or lists.
        Exception: If the API request fails.
    """

    URL = API_URL + "market/actions/" + f"?offset={offset}" + f"&limit={limit}" + f"{SORTS[sort]}"

    try:
        min_price = int(min_price)
        max_price = int(max_price)
    except:
        raise Exception("portalsmp: marketActivity(): Error: min_price and max_price must be integers")

    if max_price < 100000:
        URL += f"&min_price={min_price}&max_price={max_price}"

    if authData == "":
        raise Exception("portalsmp: marketActivity(): Error: authData is required")
    if max_price < min_price:
        raise Exception("portalsmp: marketActivity(): Error: max_price must be greater than min_price")
    if type(activityType) == str and activityType.lower() not in ["", "buy", "listing", "price_update", "offer"]:
        raise Exception(
            "portalsmp: marketActivity(): Error: activityType may be empty, buy, listing, offer or price_update only.")
    if type(activityType) == list:
        activityType = activityListToURL(activityType)

    if gift_name:
        if type(gift_name) == str:
            URL += f"&filter_by_collections={quote_plus(cap(gift_name))}"
        elif type(gift_name) == list:
            URL += f"&filter_by_collections={listToURL(gift_name)}"
        else:
            raise Exception("portalsmp: marketActivity(): Error: gift_name must be a string or list")
    if model:
        if type(model) == str:
            URL += f"&filter_by_models={quote_plus(cap(model))}"
        elif type(model) == list:
            URL += f"&filter_by_models={listToURL(model)}"
        else:
            raise Exception("portalsmp: marketActivity(): Error: model must be a string or list")
    if backdrop:
        if type(backdrop) == str:
            URL += f"&filter_by_backdrops={quote_plus(cap(backdrop))}"
        elif type(backdrop) == list:
            URL += f"&filter_by_backdrops={listToURL(backdrop)}"
        else:
            raise Exception("portalsmp: marketActivity(): Error: backdrop must be a string or list")
    if symbol:
        if type(symbol) == str:
            URL += f"&filter_by_symbols={quote_plus(cap(symbol))}"
        elif type(symbol) == list:
            URL += f"&filter_by_symbols={listToURL(symbol)}"
        else:
            raise Exception("portalsmp: marketActivity(): Error: symbol must be a string or list")
    if activityType:
        URL += f"&action_types={activityType}"

    HEADERS["Authorization"] = authData
    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: marketActivity(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json()['actions'] if 'actions' in response.json() else response.json()


def convertForListing(nft_id: str = "", price: float = 0):
    return {"nft_id": nft_id, "price": str(price)}


def convertForBuying(nft_id: str = "", price: float = 0):
    return {"id": nft_id, "price": str(price)}


def bulkList(nfts: list = [], authData: str = "") -> dict:
    """
    Lists multiple NFTs for sale in bulk.

    Args:
        nfts (list): A non-empty list of dictionaries, each containing 'nft_id', and 'price' as keys.
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the response from the API if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If nfts is not a non-empty list.
        Exception: If the API request fails or returns a non-200 status code.
    """

    URL = API_URL + "nfts/bulk-list"

    if authData == "":
        raise Exception("portalsmp: bulkList(): Error: authData is required")
    if type(nfts) != list or len(nfts) == 0:
        raise Exception("portalsmp: bulkList(): Error: nfts must be a non-empty list")

    HEADERS["Authorization"] = authData

    PAYLOAD = {
        "nft_prices": nfts
    }

    response = requests.post(URL, json=PAYLOAD, headers=HEADERS, impersonate="chrome110")
    if response.status_code not in [200, 204]:
        raise Exception(
            f"portalsmp: bulkList(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def sale(nft_id: str = "", price: int | float = 0, authData: str = "") -> dict | None:
    """
    Lists a single NFT for sale.

    Args:
        nft_id (str): The unique identifier of the NFT to be listed.
        price (int|float): The price at which the NFT should be listed for sale.
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the response from the API if the request is successful.
        None: Likely 204 no content response from the API.

    Raises:
        Exception: If authData is not provided.
        Exception: If nft_id is not provided.
        Exception: If price is not provided or not a number.
        Exception: If the API request fails or returns a non-200 status code.
    """

    URL = API_URL + "nfts/bulk-list"

    if authData == "":
        raise Exception("portalsmp: sale(): Error: authData is required")
    if not nft_id:
        raise Exception("portalsmp: sale(): Error: nft_id is required")
    if price == 0 or type(price) not in [int, float]:
        raise Exception("portalsmp: sale(): Error: price error")

    nfts = [{"nft_id": nft_id, "price": str(price)}]

    HEADERS["Authorization"] = authData

    PAYLOAD = {
        "nft_prices": nfts
    }

    response = requests.post(URL, json=PAYLOAD, headers=HEADERS, impersonate="chrome110")
    if response.status_code not in [200, 204]:
        raise Exception(
            f"portalsmp: sale(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def buy(nft_id: str = "", price: int | float = 0, authData: str = "") -> dict | None:
    """
    Buys a gift with the given nft_id at the given price.

    Args:
        nft_id (str): The unique identifier of the NFT to be bought.
        price (int|float): The price at which the NFT should be bought.
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the response from the API if the request is successful.
        None: Likely 204 no content response from the API.

    Raises:
        Exception: If authData is not provided.
        Exception: If nft_id is not provided.
        Exception: If price is not provided or not a number.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "nfts"

    if authData == "":
        raise Exception("portalsmp: buy(): Error: authData is required")
    if not nft_id:
        raise Exception("portalsmp: buy(): Error: nft_id is required")
    if price == 0 or type(price) not in [int, float]:
        raise Exception("portalsmp: buy(): Error: price error")

    HEADERS["Authorization"] = authData

    nfts = [{"id": nft_id, "price": str(price)}]
    '''
    {"nft_details":[{"id":"aaaa8eb4-deac-4ba2-aa5c-ea79c73f0d5b","owner_id":6540727795,"price":"1.85"}]}
    '''

    PAYLOAD = {
        "nft_details": nfts
    }

    response = requests.post(URL, json=PAYLOAD, headers=HEADERS, impersonate="chrome110")
    if response.status_code not in [200, 204]:
        raise Exception(f"portalsmp: buy(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def makeOffer(nft_id: str = "", offer_price: float = 0, expiration_days: int = 7, authData: str = "") -> dict | None:
    """
    Creates an offer for a specified NFT.

    Args:
        nft_id (str): The unique identifier of the NFT for which the offer is being made.
        offer_price (float): The price of the offer.
        expiration_days (int): The number of days until the offer expires. 0 - no expiration, 7 - 7 days.
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the response from the API if the request is successful.
        None: Likely 204 no content response from the API.

    Raises:
        Exception: If nft_id is not provided.
        Exception: If offer_price is not provided.
        Exception: If expiration_days is not 7 or 0.
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """

    URL = API_URL + "offers"

    if not nft_id:
        raise Exception("portalsmp: makeOffer(): Error: nft_id is required")
    if offer_price == 0:
        raise Exception("portalsmp: makeOffer(): Error: offer_price is required")
    if expiration_days not in [7, 0]:
        raise Exception("portalsmp: makeOffer(): Error: expiration_days must be 7 or 0")
    if authData == "":
        raise Exception("portalsmp: makeOffer(): Error: authData is required")

    HEADERS["Authorization"] = authData

    PAYLOAD = {
        "offer": {
            "nft_id": nft_id,
            "offer_price": str(offer_price)
        }
    }

    if expiration_days == 7:
        PAYLOAD["offer"].update({"expiration_days": expiration_days})

    response = requests.post(URL, json=PAYLOAD, headers=HEADERS, impersonate="chrome110")
    if response.status_code not in [200, 204]:
        raise Exception(
            f"portalsmp: makeOffer(): Error: status_code: {response.status_code}, response_text: {response.content}")

    return response.json() if response.status_code == 200 else None


def cancelOffer(offer_id: str = "", authData: str = "") -> dict | None:
    """
    Cancels an offer with the given offer_id.

    Args:
        offer_id (str): The unique identifier of the offer to be canceled.
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the response from the API if the request is successful.
        None: Likely 204 no content response from the API.

    Raises:
        Exception: If offer_id is not provided.
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "offers/" + f"{offer_id}" + "/cancel"

    if not offer_id:
        raise Exception("portalsmp: cancelOffer(): Error: offer_id is required")
    if authData == "":
        raise Exception("portalsmp: cancelOffer(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.post(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code not in [200, 204]:
        raise Exception(
            f"portalsmp: cancelOffer(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def changePrice(nft_id: str = "", price: float = 0, authData: str = "") -> dict | None:
    """
    Updates the price of a specified NFT.

    Args:
        nft_id (str): The unique identifier of the NFT for which the price is being updated.
        price (float): The new price to set for the NFT.
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the response from the API if the request is successful.
        None: Likely 204 no content response from the API.

    Raises:
        Exception: If nft_id is not provided.
        Exception: If price is not provided.
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """

    URL = API_URL + "nfts/" + f"{nft_id}/" + "list"

    if not nft_id:
        raise Exception("portalsmp: changePrice(): Error: nft_id is required")
    if price == 0:
        raise Exception("portalsmp: changePrice(): Error: price is required")
    if authData == "":
        raise Exception("portalsmp: changePrice(): Error: authData is required")

    HEADERS["Authorization"] = authData

    PAYLOAD = {
        "price": str(price)
    }

    response = requests.post(URL, json=PAYLOAD, headers=HEADERS, impersonate="chrome110")
    if response.status_code not in [200, 204]:
        raise Exception(
            f"portalsmp: changePrice(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


class PortalsGift:
    """
    Attributes:
        id (str): Portals ID of the gift
        tg_id (int): Telegram ID of the gift
        collection_id (str): Portals ID of the gift collection
        name (str): Name of the gift
        photo_url (str): Photo URL of the gift (model + bg + symbol preview)
        price (str): Price of the gift
        model (str): Model of the gift
        model_rarity (float): Model rarity of the gift
        symbol (str): Symbol of the gift
        symbol_rarity (float): Symbol rarity of the gift
        backdrop (str): Backdrop of the gift
        backdrop_rarity (float): Backdrop rarity of the gift
        listed_at (str): Time the gift was listed
        status (str): (usually listed)
        animation_url (str): Lottie animation URL of the gift
        emoji_id (str): Telegram custom emoji ID of the gift
        floor_price (str): Floor price of the gift (not the model)
        unlocks_at (str): Time of when the gift will be available to be minted
    """

    def __init__(self, data: dict):
        self.__dict__ = data

    def toDict(self):
        return self.__dict__

    @property
    def id(self):
        return self.__dict__["id"]

    @property
    def tg_id(self):
        return self.__dict__["external_collection_number"]

    @property
    def collection_id(self):
        return self.__dict__["collection_id"]

    @property
    def name(self):
        return self.__dict__["name"]

    @property
    def photo_url(self):
        return self.__dict__["photo_url"]

    @property
    def price(self):
        return float(self.__dict__["price"]) if self.__dict__["price"] else None

    @property
    def model(self):
        for attr in self.__dict__["attributes"]:
            if attr["type"] == "model":
                return attr["value"]
        return None

    @property
    def model_rarity(self):
        for attr in self.__dict__["attributes"]:
            if attr["type"] == "model":
                return attr["rarity_per_mille"]
        return None

    @property
    def symbol(self):
        for attr in self.__dict__["attributes"]:
            if attr["type"] == "symbol":
                return attr["value"]
        return None

    @property
    def symbol_rarity(self):
        for attr in self.__dict__["attributes"]:
            if attr["type"] == "symbol":
                return attr["rarity_per_mille"]
        return None

    @property
    def backdrop(self):
        for attr in self.__dict__["attributes"]:
            if attr["type"] == "backdrop":
                return attr["value"]
        return None

    @property
    def backdrop_rarity(self):
        for attr in self.__dict__["attributes"]:
            if attr["type"] == "backdrop":
                return attr["rarity_per_mille"]
        return None

    @property
    def listed_at(self):
        return self.__dict__["listed_at"]

    @property
    def status(self):
        return self.__dict__["status"]

    @property
    def animation_url(self):
        return self.__dict__["animation_url"]

    @property
    def emoji_id(self):
        return self.__dict__["emoji_id"]

    @property
    def floor_price(self):
        return float(self.__dict__["floor_price"]) if self.__dict__["floor_price"] else None

    @property
    def unlocks_at(self):
        return self.__dict__["unlocks_at"]


def withdrawPortals(amount: float = 0, wallet: str = "", authData: str = "") -> dict:
    """
    Withdraw Portals from the user's wallet to an external address.

    Args:
        amount (float): The amount of Portals to withdraw.
        wallet (str): The external address to withdraw to.
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing ID of the withdrawal.

    Raises:
        Exception: If amount is not provided.
        Exception: If wallet is not provided.
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "users/wallets/withdraw"

    if amount == 0:
        raise Exception("portalsmp: withdrawPortals(): Error: amount is required")
    if not wallet:
        raise Exception("portalsmp: withdrawPortals(): Error: wallet is required")
    if not authData:
        raise Exception("portalsmp: withdrawPortals(): Error: authData is required")

    HEADERS["Authorization"] = authData

    PAYLOAD = {
        "amount": str(amount),
        "external_address": wallet
    }

    response = requests.post(URL, json=PAYLOAD, headers=HEADERS, impersonate="chrome110")
    if response.status_code not in [200, 204]:
        raise Exception(
            f"portalsmp: withdrawPortals(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def collectionOffer(gift_name: str = "", amount: float | int = 0, expiration_days: int = 7, max_nfts: int = 1,
                    authData: str = ""):
    """
    Make an offer for collection.

    Args:
        gift_name (str): A name of the collection
        amount (float | int): Amount of offer
        expiration_days (int: 0 or 7): 7 - the offer will expire after 7 days; 0 - no expiration.
        max_nfts (int): Quantity of NFTs to buy. Default = 1.
        authData (str): authData

    Returns:
        dict: A dictionary containing id, collection_id, status etc. of the collection offer

    Raises:
        Exception: If gift_name is not provided.
        Exception: If gift_name is invalid.
        Exception: If amount is not provided.
        Exception: If max_nfts is not provided.
        Exception: If authData is not provided.
        Exception: If expiration_days is not 0 or 7.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "collection-offers/"

    if not gift_name:
        raise Exception("portalsmp: collectionOffer(): Error: gift_name is required")

    if amount <= 0.0:
        raise Exception("portalsmp: collectionOffer(): Error: amount is required")

    if max_nfts <= 0:
        raise Exception("portalsmp: collectionOffer(): Error: max_nfts is required")

    if not authData:
        raise Exception("portalsmp: collectionOffer(): Error: authData is required")

    if expiration_days not in [0, 7]:
        raise Exception("portalsmp: collectionOffer(): Error: expiration_days must be 0 (no expiration) or 7 (7 days)")

    gift_name = cap(gift_name)

    try:
        ID = collections_ids[gift_name]
    except:
        raise Exception("portalsmp: collectionOffer(): Error: gift_name is invalid")

    HEADERS["Authorization"] = authData

    PAYLOAD = {
        "amount": str(amount),
        "collection_id": ID,
        "expiration_days": expiration_days,
        "max_nfts": max_nfts
    }

    response = requests.post(url=URL, headers=HEADERS, json=PAYLOAD, impersonate="chrome110")

    if response.status_code not in [200, 201, 204]:
        raise Exception(
            f"portalsmp: collectionOffer(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code in [200, 201] else None


def cancelCollectionOffer(offer_id: str = "", authData: str = ""):
    URL = API_URL + "collection-offers/cancel"

    if not offer_id:
        raise Exception("portalsmp: cancelCollectionOffer(): Error: offer_id is required")

    if not authData:
        raise Exception("portalsmp: cancelCollectionOffer(): Error: authData is required")

    HEADERS["Authorization"] = authData

    PAYLOAD = {
        "id": offer_id
    }

    response = requests.post(url=URL, headers=HEADERS, json=PAYLOAD, impersonate="chrome110")

    if response.status_code not in [200, 204]:
        raise Exception(
            f"portalsmp: cancelCollectionOffer(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def allCollectionOffers(gift_name: str = "", authData: str = "") -> list:
    """
    Retrieves all collection offers for a specific gift collection.
    Args:
        gift_name (str): The name of the gift collection.
        authData (str): The authentication data required for the API request.
    Returns:
        list: A list of dictionaries containing all collection offers for the specified gift collection.
    Raises:
        Exception: If gift_name is not provided or is invalid.
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "collection-offers/"

    if not gift_name:
        raise Exception("portalsmp: allCollectionOffers(): Error: gift_name is required")
    gift_name = cap(gift_name)
    try:
        ID = collections_ids[gift_name]
    except:
        raise Exception("portalsmp: allCollectionOffers(): Error: gift_name is invalid")
    if not authData:
        raise Exception("portalsmp: allCollectionOffers(): Error: authData is required")

    URL += f"{ID}/all"
    HEADERS["Authorization"] = authData
    response = requests.get(url=URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: allCollectionOffers(): Error: status_code: {response.status_code}, response_text: {response.text}")
    return response.json() if response.status_code == 200 else None


def filterFloors(gift_name: str = "", authData: str = "") -> dict:
    """
    Retrieves the floor prices of models/backdrops/symbols for a specific gift collection.
    Args:
        gift_name (str): The name of the gift collection.
        authData (str): The authentication data required for the API request.
    Returns:
        dict: A dictionary containing the floor prices of models, backgrounds, and symbols for the specified gift collection. To get models, backgrounds, and symbols floor prices, use the keys "models", "backdrops", and "symbols".
    Raises:
        Exception: If authData is not provided.
        Exception: If gift_name is not provided or is not a string.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "collections/filters"

    if not authData:
        raise Exception("portalsmp: filters(): Error: authData is required")
    if not gift_name:
        raise Exception("portalsmp: filters(): Error: gift_name is required")
    if type(gift_name) == str:
        gift_name = toShortName(gift_name)
    if type(gift_name) != str:
        raise Exception("portalsmp: filters(): Error: gift_name must be a string")

    URL += f"?short_names={gift_name}"
    HEADERS["Authorization"] = authData
    response = requests.get(url=URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: filters(): Error: status_code: {response.status_code}, response_text: {response.text}")
    return response.json()['floor_prices'][gift_name] if response.status_code == 200 else None


def myPlacedOffers(offset: int = 0, limit: int = 20, authData: str = ""):
    """
    Retrieves the offers placed by the user.

    Args:
        offset (int): The pagination offset. Defaults to 0.
        limit (int): The maximum number of results to return. Defaults to 20.
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of placed offers if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + f"offers/placed?offset={offset}&limit={limit}"

    if authData == "":
        raise Exception("portalsmp: myPlacedOffers(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: myPlacedOffers(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json()['offers'] if 'offers' in response.json() else response.json()


def editOffer(offer_id: str = "", new_price: float = 0, authData: str = "") -> None:
    """
    Edit existing offer price.
    Args:
        offer_id (str): The unique identifier of the offer to be edited.
        new_price (int | float): The new price to set for the offer.
        authData (str): The authentication data required for the API request.
    Returns:
        None: If the request is successful and the offer is edited.
    Raises:
        Exception: If offer_id is not provided.
        Exception: If new_price is not provided or is less than 0.5.
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "offers/" + f"{offer_id}"

    if not offer_id:
        raise Exception("portalsmp: editOffer(): Error: offer_id is required")
    if type(new_price) not in [float, int] or new_price < 0.5:
        raise Exception("portalsmp: editOffer(): Error: new_price must be a number >= 0.5")
    if not authData:
        raise Exception("portalsmp: editOffer(): Error: authData is required")

    PAYLOAD = {
        "amount": str(float(new_price))
    }

    HEADERS["Authorization"] = authData
    response = requests.patch(url=URL, json=PAYLOAD, headers=HEADERS, impersonate="chrome110")
    if response.status_code not in [200, 204]:
        raise Exception(
            f"portalsmp: editOffer(): Error: status_code: {response.status_code}, response_text: {response.text}")
    return None if response.status_code == 204 else response.json()


def myReceivedOffers(offset: int = 0, limit: int = 20, authData: str = ""):
    """
    Retrieves the offers received by the user.

    Args:
        offset (int): The pagination offset. Defaults to 0.
        limit (int): The maximum number of results to return. Defaults to 20.
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of received offers if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + f"offers/received?offset={offset}&limit={limit}"

    if authData == "":
        raise Exception("portalsmp: myReceivedOffers(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: myReceivedOffers(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json()['top_offers'] if 'top_offers' in response.json() else response.json()


def myCollectionOffers(authData: str = ""):
    """
    Retrieves the collection offers placed by the user.

    Args:
        authData (str): The authentication data required for the API request.

    Returns:
        list: A list of collection offers if the request is successful.

    Raises:
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """

    URL = API_URL + "collection-offers/"
    if authData == "":
        raise Exception("portalsmp: myCollectionOffers(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL, headers=HEADERS, impersonate="chrome110")
    if response.status_code != 200:
        raise Exception(
            f"portalsmp: myCollectionOffers(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None


def topOffer(gift_name: str = "", authData: str = ""):
    """
    Retrieves the top offer for a specified gift collection.

    Args:
        gift_name (str): The name of the gift collection.
        authData (str): The authentication data required for the API request.

    Returns:
        dict: A dictionary containing the top offer details if the request is successful.

    Raises:
        Exception: If gift_name is not provided.
        Exception: If authData is not provided.
        Exception: If the API request fails or returns a non-200 status code.
    """
    URL = API_URL + "collection-offers/"

    try:
        ID = collections_ids[cap(gift_name)]
    except:
        raise Exception("portalsmp: topOffer(): Error: gift_name is invalid")

    if authData == "":
        raise Exception("portalsmp: topOffer(): Error: authData is required")

    HEADERS["Authorization"] = authData

    response = requests.get(URL + f"{ID}/top", headers=HEADERS, impersonate="chrome110")

    if response.status_code != 200:
        raise Exception(
            f"portalsmp: topOffer(): Error: status_code: {response.status_code}, response_text: {response.text}")

    return response.json() if response.status_code == 200 else None