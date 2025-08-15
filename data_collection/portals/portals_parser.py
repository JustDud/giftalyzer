from urllib.parse import quote_plus
import os
from dotenv import load_dotenv
import aiohttp
import asyncio
import json
from pyrogram import Client
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw.types import InputBotAppShortName, InputUser
from pyrogram.raw.functions.users import GetUsers

load_dotenv()

API_URL_PORTALS = os.environ.get("API_URL_PORTALS")
PORTALS_AUTH = os.environ.get("PORTALS_AUTH")
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
PHONE_NUMBER = os.environ.get("TELEGRAM_PHONE")
TWO_FA_PASSWORD = os.environ.get("TELEGRAM_PASSWORD")

gift_name = "Pepe"
collections_ids = {
    "Plush Pepe": "8d21b568-63bb-437a-9093-8684c5b63485",
    "Loot Bag": "db7f4abd-96d9-4968-ba81-7f1a07bc2e9c",
    "Bow Tie": "216c52eb-447a-4775-921d-a59f9b67082c",
    "Heroic Helmet": "013a775d-4d7d-457b-9d3d-30a6429ea79f",
    "Durov's Cap": "fc46d19d-5f25-44c5-8924-5976c2fb790e",
    "Nail Bracelet": "40311c45-48a8-4863-8abb-7156ae62767b",
    "Swiss Watch": "f0125f02-2b17-4882-95b4-8715a88678a5",
    "Bonded Ring": "07484deb-1790-4a21-9d2f-ece02acdcb84",
    "Precious Peach": "40131849-420d-4775-b616-6d359c17c22f",
    "Gem Signet": "020c2380-709d-4d09-bbad-814852b32551",
    "Vintage Cigar": "48204369-2f95-4909-8018-1660b37c2b9d",
    "Light Sword": "0ebbc5d6-f59f-49f5-9a48-7a1fc1625093",
    "Toy Bear": "060d4cef-3a21-47e6-98fc-cd338ae0b5e0",
    "Neko Helmet": "f3e9621f-a32f-49d9-b602-71ecf2515ded",
    "Lol Pop": "98850266-bb6c-43a6-9559-accedf420a02",
    "Ion Gem": "47f0cf89-4fc9-4aa2-99b2-7f3cf9a6c16a",
    "Astral Shard": "207d7011-8359-429c-b86b-df191b3659dd",
    "Sharp Tongue": "308fc63d-1ebc-4e31-865e-c756018e4dff",
    "Diamond Ring": "45aa08dd-94e0-492f-bf04-1952aa024951",
    "Restless Jar": "9537661e-290b-49f3-adaf-d96e8f590288",
    "Signet Ring": "a1a5ec7e-53b9-45b9-91e5-cad37a15fe5e",
    "Scared Cat": "a4a90909-9a06-4b78-9d75-4de42280334a",
    "Easter Egg": "88a37665-6d13-4619-afa9-47de8464adb4",
    "Genie Lamp": "7693b50e-b9ad-4eed-8791-a7b4bf3ea726",
    "Electric Skull": "43b4502a-ca8c-49e8-ba5d-03cdf66d8f48",
    "Perfume Bottle": "e1b2c024-a443-4637-b451-02904a6bc3f6",
    "Voodoo Doll": "ba7390cc-72d4-45ce-96e4-d243e22a6500",
    "Kissed Frog": "2c68a297-604a-4710-a32e-d3eac17e15ae",
    "Hanging Star": "1d7b6d74-5eef-45ee-b25b-632a96b9505a",
    "Magic Potion": "a17b488a-3942-4eae-89f9-bba2ce342c6b",
    "Tama Gadget": "beed4df4-cce3-4b21-aefe-0cc5e5196834",
    "Top Hat": "860ae248-5a63-4ea9-ae6d-defd3c0952b9",
    "Desk Calendar": "ae8f48a9-e090-44f2-9c61-5928702ab171",
    "Sleigh Bell": "8519c4e9-ef09-48fd-af9c-9e7412809e7c",
    "Flying Broom": "73de1866-6b90-45b4-a543-fb5ea9ca1415",
    "Trapped Heart": "bef99328-29f3-454a-abef-4d2f34b3bf3f",
    "Love Potion": "7369ac28-ddaf-4100-9a75-a4225b64e1b0",
    "Eternal Rose": "fa27c78c-6eb9-4653-a619-19544b8255b1",
    "Mad Pumpkin": "1f281b21-1955-4691-923c-8f58ce00a456",
    "Eternal Candle": "257ad54a-134c-437c-ab1e-febc4c798243",
    "Sakura Flower": "1c1616f5-2f39-47dc-9f27-e77fa1b6a569",
    "Snow Globe": "ffdfcb47-b9c9-4a5c-a59f-d6d236b583cf",
    "Mini Oscar": "ea3f1a6f-80c8-4abf-8c56-cd41a0e1c89a",
    "Record Player": "99cb46d0-c724-4e27-8497-ac381e10d97c",
    "Love Candle": "128c7b37-36db-4b21-a21b-7d858c8dbc1a",
    "Evil Eye": "f639a421-45df-4848-ac69-a089746828c4",
    "Witch Hat": "a7253309-ed0e-4d5d-972c-2bc9c0194bea",
    "Crystal Ball": "ac575eb3-2929-48d6-96d0-1db8f12243de",
    "Bunny Muffin": "586cd461-0194-49af-86b0-cbc3b55a2a65",
    "Spy Agaric": "a39d2458-5df0-42ff-98d5-08af484001d6",
    "Skull Flower": "61a23d97-cf11-4c91-8435-476ba84c81eb",
    "Homemade Cake": "f7a194d4-d53a-419a-b357-3c794f6cd98b",
    "Holiday Drink": "6bf906a0-e5b1-4c7f-b741-a70c3f7ed77b",
    "Jelly Bunny": "1a139fcf-5850-48c3-aee6-924134ad17d8",
    "Party Sparkler": "53110539-1d3e-4334-9692-a665e0527f69",
    "Big Year": "8b58d6ea-a8e0-47ef-bdd1-3ade5d5ea0cb",
    "Ginger Cookie": "b85209cd-4e16-4d1a-985c-d784619fe2d0",
    "Pet Snake": "563ed415-a63b-49e8-870d-745602fb3de3",
    "Jack-in-the-Box": "996e7628-28bf-4874-b3ec-2e5f7c1cb684",
    "Snow Mittens": "0009551d-bdd4-40ee-a276-b6e01fa4d327",
    "B-Day Candle": "12efb9cd-179f-44c6-af65-a63480691c18",
    "Berry Box": "b8747d58-90ed-49cf-8e29-b9e2c8b3e7a6",
    "Xmas Stocking": "acebace7-be16-4a4b-9b02-c274bed4c856",
    "Jingle Bells": "1501b9b9-83e0-4d05-a3af-d0e2021c6d5e",
    "Candy Cane": "8b001ea2-5a73-4a61-a3a2-6f01d557fee7",
    "Santa Hat": "b577efed-76dc-410f-bda9-edae43ab0f4a",
    "Cookie Heart": "35c106ab-7133-4f10-a502-e2c602b64da9",
    "Spiced Wine": "9aac072e-34d6-4819-a7f4-70ad25af8196",
    "Hex Pot": "66e62058-8600-471f-909b-844751f5f103",
    "Lunar Snake": "a4b271b4-efa3-4854-b53f-9ae6f3ecac59",
    "Hypno Lollipop": "fe1816f1-a6a9-4770-8921-839a5bfa5a22",
    "Star Notepad": "a76231dd-a8be-4f06-b7a3-e119b65074da",
    "Snake Box": "f50f29bb-70b5-4502-a21b-8eadf20518fa",
    "Jester Hat": "ea32e880-b03c-4791-9385-68d24db9784b",
    "Winter Wreath": "13bada87-1353-4db5-b77c-d451c95365e0"
    }


async def get_portals_auth_token(api_id: int, api_hash: str) -> str:
    async with Client(":memory:", api_id=api_id, api_hash=api_hash, phone_number=PHONE_NUMBER, password=TWO_FA_PASSWORD) as app:
        me = await app.get_me()

        web_view = await app.invoke(
            RequestAppWebView(
                peer=await app.resolve_peer("giftalyzer_admin"),
                app=InputUser(user_id=6136187493, access_hash=5521816162305789110),
                platform="android",
                from_bot_menu=False,
                url="https://app.portals-market.com"
            )
        )
        # Extract token from the URL returned
        url = web_view.url
        auth_part = url.split("tma=")[-1]
        return auth_part


async def fetch_all_portals_gifts(collection_name: str):
    collection = quote_plus(collection_name)
    offset = 0
    limit = 50
    all_items = []

    headers = {
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
        "Authorization": f"tma {PORTALS_AUTH}"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            url = (
                f"{API_URL_PORTALS}/api/nfts/search"
                f"?offset={offset}&limit={limit}"
                f"&filter_by_collections={collection}"
                f"&sort_by=price+asc"
                f"&status=listed"
            )

            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"❌ HTTP {resp.status}")
                    break
                data = await resp.json()
                items = data.get("results", [])
                if not items:
                    break

                all_items.extend(items)
                offset += limit

    return all_items


async def main():
    global PORTALS_AUTH
    api_id = int(os.environ.get("API_ID"))
    api_hash = os.environ.get("API_HASH")
    PORTALS_AUTH = await get_portals_auth_token(api_id, api_hash)
    gifts = await fetch_all_portals_gifts("Durov’s Cap")
    for gift in gifts:
        print(gift["name"], "-", gift["price"])

asyncio.run(main())