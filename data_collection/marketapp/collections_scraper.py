import requests
from bs4 import BeautifulSoup
import re


def normalize_collection_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip()
    match = re.match(r"^(.*?)[\s#]+(\d+)$", name)
    if match:
        prefix = match.group(1).replace(" ", "")
        number = match.group(2)
        return f"{prefix}-{number}"
    return name.replace(" ", "")


def parse_ton_value(val):
    if val is None:
        return None
    val = val.strip().upper().replace(",", "")
    val_parts = val.split()
    val = val_parts[0] if val_parts else None
    if val is None:
        return None
    if val.endswith("K"):
        return str(int(float(val[:-1]) * 1000))
    if val.endswith("M"):
        return str(int(float(val[:-1]) * 1_000_000))
    return val


def scrape_collections():
    base_url = "https://marketapp.ws"
    collections_url = base_url + "/?tab=fragment"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(collections_url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    collections = []
    rows = soup.select("tr.tm-row-selectable")
    print("DEBUG: status:", res.status_code)
    print("DEBUG: preview:", res.text[:500])
    print("DEBUG: found rows:", len(rows))

    for row in rows:
        name_cell = row.select_one(".tm-value")
        name = name_cell.text.strip() if name_cell else "Unknown"
        name = name.encode("latin1", errors="ignore").decode("utf-8", errors="ignore")
        name = normalize_collection_name(name)

        link_tag = name_cell.find_parent("a")
        href = link_tag["href"] if link_tag and "href" in link_tag.attrs else None
        address = href.split("/collection/")[1].strip("/") if href and "/collection/" in href else None

        # Extract floor value from the correct <td> containing the floor TON value
        floor_td = name_cell.find_parent("td").find_next_sibling("td").find_next_sibling("td")
        floor_value = floor_td.select_one(".tm-value") if floor_td else None
        floor = floor_value.text.strip().split("~")[0] if floor_value else None

        if name in ["AnonymousTelegramNumbers", "TelegramUsernames"]:
            continue

        tds = row.find_all("td")[1:]

        def get_td_text(i, tds):
            return tds[i].get_text(strip=True).split("~")[0] if len(tds) > i else None

        floor = get_td_text(1)
        top_order = get_td_text(2)
        volume = get_td_text(3)
        owners = get_td_text(4)
        supply = get_td_text(5).replace("\n", "").replace("/", "").strip() if get_td_text(5) else None

        floor = parse_ton_value(floor)
        top_order = parse_ton_value(top_order)
        volume = parse_ton_value(volume)
        owners = parse_ton_value(owners)
        supply = parse_ton_value(supply)

        collections.append({
            "name": name,
            "address": address,
            "floor": floor,
            "top_order": top_order,
            "volume": volume,
            "owners": owners,
            "supply": supply
        })

    return collections
