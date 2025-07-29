import time
import requests
from bs4 import BeautifulSoup
import html
import re


# Helper to normalize NFT names to format "MadPumpkin-1218"
def normalize_nft_name(name: str) -> str:
    if not name:
        return ""
    name = name.strip()
    match = re.match(r"^(.*?)[\s#]+(\d+)$", name)
    if match:
        prefix = match.group(1).replace(" ", "")
        number = match.group(2)
        return f"{prefix}-{number}"
    return name.replace(" ", "")


def get_human_readable_date_from_text(text: str) -> str:
    text = text.lower()
    now = time.localtime()
    if "hour" in text or "minute" in text:
        return time.strftime("%d-%m-%Y", now)
    elif "day" in text:
        yesterday = time.localtime(time.time() - 86400)
        return time.strftime("%d-%m-%Y", yesterday)
    return None


def scrape_nfts(address):
    base_url = "https://marketapp.ws"
    collection_path = f"/collection/{address}/"
    params = {
        "tab": "nfts",
        "sort_by": "next_bid_asc",
        "filter_by": "any",
        "page": 1
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    all_rows = []
    page = 1
    start_time = time.time()
    nft_count = 0

    res = requests.get(base_url + collection_path, headers=headers)
    try:
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("tr.tm-row-selectable")
        for row in rows:
            name_elem = row.select_one(".tm-value")
            name = name_elem.text.strip() if name_elem else "Unknown"
            name = normalize_nft_name(name)
            link = row.select_one("a")
            href = link['href'] if link else None
            nft_id = href.strip("/").split("/")[-1] if href else None
            if not nft_id:
                continue  # or assign a fallback ID
            status = row.select_one(".tm-status-avail")
            status = status.text.strip() if status else "Not listed"
            market = row.select_one(".tm-status-market")
            market = market.text.strip() if market else "Unknown"
            rarity_td = row.select_one("td:nth-of-type(2)")
            if rarity_td:
                rarity_text = rarity_td.get_text(strip=True)
                rarity_value = ''.join(filter(str.isdigit, rarity_text))
                rarity = rarity_value if rarity_value else None
            else:
                rarity = None
            price = row.select_one(".tm-price")
            price = price.text.strip().replace(",", "") if price else None
            if not price:
                price_td = row.select("td")
                if len(price_td) >= 3:
                    alt_price = price_td[2].select_one(".tm-value")
                    if alt_price:
                        price = alt_price.text.strip().replace(",", "")
            last_sale = last_sale_date = None
            last_sale_td = row.select_one("td:nth-of-type(4)")
            if last_sale_td:
                last_sale = last_sale_td.text.strip()
                time_tag = last_sale_td.select_one("time[timestamp]")
                if time_tag and time_tag.has_attr("timestamp"):
                    try:
                        last_sale_date = time.strftime("%d-%m-%Y", time.localtime(int(time_tag["timestamp"])))
                    except ValueError:
                        if "ago" in time_tag.text:
                            last_sale_date = get_human_readable_date_from_text(time_tag.text)
                        else:
                            last_sale_date = None
            owner = row.select_one("td:nth-of-type(5) a")
            owner = owner.text.strip() if owner else None
            attr_tooltip = row.select_one("span[data-bs-title]")
            model = backdrop = symbol = None
            if attr_tooltip:
                tooltip_html = html.unescape(attr_tooltip["data-bs-title"])
                tooltip_soup = BeautifulSoup(tooltip_html, "html.parser")
                for item in tooltip_soup.select("dl.tm-list-item"):
                    key = item.select_one("dt.tm-list-item-title")
                    value_wrapper = item.select_one("dd.tm-list-item-value > span.accent-color")
                    if key and value_wrapper:
                        label = key.text.strip().lower()
                        value_texts = [t for t in value_wrapper.stripped_strings]
                        if value_texts:
                            text = value_texts[0]
                            if "model" in label:
                                model = text
                            elif "backdrop" in label:
                                backdrop = text
                            elif "symbol" in label:
                                symbol = text
            if name != "Unknown" and status != "Not listed":
                nft_count += 1
                all_rows.append({
                    "nft_id": nft_id,
                    "name": name,
                    "status": status,
                    "market": market,
                    "href": href,
                    "price": price,
                    "last_sale": last_sale,
                    "last_sale_date": last_sale_date,
                    "rarity": rarity,
                    "owner": owner,
                    "model": model,
                    "backdrop": backdrop,
                    "symbol": symbol
                })
    except Exception as e:
        print("Failed to parse initial HTML:", e)

    while True:
        # print(f"Scraping page {page}...")
        params["page"] = page
        res = requests.get(base_url + collection_path, params=params, headers=headers)
        try:
            if page == 1 and res.headers.get("Content-Type", "").startswith("text/html"):
                soup = BeautifulSoup(res.text, "html.parser")
            else:
                json_data = res.json()
                html_fragment = json_data.get("h", "")
                soup = BeautifulSoup(html_fragment, "html.parser")
        except Exception as e:
            print(f"Failed to parse page {page}: {e}")
            break

        rows = soup.select("tr.tm-row-selectable")
        if not rows:
            # print("No more rows found. Stopping.")
            break

        for row in rows:
            name_elem = row.select_one(".tm-value")
            name = name_elem.text.strip() if name_elem else "Unknown"
            name = normalize_nft_name(name)
            link = row.select_one("a")
            href = link['href'] if link else None
            nft_id = href.strip("/").split("/")[-1] if href else None
            status = row.select_one(".tm-status-avail")
            status = status.text.strip() if status else "Not listed"
            market = row.select_one(".tm-status-market")
            market = market.text.strip() if market else "Unknown"
            rarity_td = row.select_one("td:nth-of-type(2)")
            if rarity_td:
                rarity_text = rarity_td.get_text(strip=True)
                rarity_value = ''.join(filter(str.isdigit, rarity_text))
                rarity = rarity_value if rarity_value else None
            else:
                rarity = None
            price = row.select_one(".tm-price")
            price = price.text.strip().replace(",", "") if price else None
            if not price:
                price_td = row.select("td")
                if len(price_td) >= 3:
                    alt_price = price_td[2].select_one(".tm-value")
                    if alt_price:
                        price = alt_price.text.strip().replace(",", "")
            last_sale = last_sale_date = None
            last_sale_td = row.select_one("td:nth-of-type(4)")
            if last_sale_td:
                last_sale = last_sale_td.text.strip()
                time_tag = last_sale_td.select_one("time[timestamp]")
                if time_tag and time_tag.has_attr("timestamp"):
                    try:
                        last_sale_date = time.strftime("%d-%m-%Y", time.localtime(int(time_tag["timestamp"])))
                    except ValueError:
                        if "ago" in time_tag.text:
                            last_sale_date = get_human_readable_date_from_text(time_tag.text)
                        else:
                            last_sale_date = None
            owner = row.select_one("td:nth-of-type(5) a")
            owner = owner.text.strip() if owner else None
            attr_tooltip = row.select_one("span[data-bs-title]")
            model = backdrop = symbol = None
            if attr_tooltip:
                tooltip_html = html.unescape(attr_tooltip["data-bs-title"])
                tooltip_soup = BeautifulSoup(tooltip_html, "html.parser")
                for item in tooltip_soup.select("dl.tm-list-item"):
                    key = item.select_one("dt.tm-list-item-title")
                    value_wrapper = item.select_one("dd.tm-list-item-value > span.accent-color")
                    if key and value_wrapper:
                        label = key.text.strip().lower()
                        value_texts = [t for t in value_wrapper.stripped_strings]
                        if value_texts:
                            text = value_texts[0]
                            if "model" in label:
                                model = text
                            elif "backdrop" in label:
                                backdrop = text
                            elif "symbol" in label:
                                symbol = text
            if name != "Unknown" and status != "Not listed":
                nft_count += 1
                all_rows.append({
                    "nft_id": nft_id,
                    "name": name,
                    "status": status,
                    "market": market,
                    "href": href,
                    "price": price,
                    "last_sale": last_sale,
                    "last_sale_date": last_sale_date,
                    "rarity": rarity,
                    "owner": owner,
                    "model": model,
                    "backdrop": backdrop,
                    "symbol": symbol
                })
        page += 1

    return all_rows
