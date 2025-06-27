import asyncio
import json
import time
from playwright.async_api import async_playwright
from tonsdk.utils import Address
import os

URL = "https://getgems.io/top-gifts?top-collections-period=all"
OUTPUT_FILE = "collection_addresses_getgems.json"


async def scrape_getgems_collections():
    start_time = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            java_script_enabled=True,
            bypass_csp=True,
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        # Block images, fonts, and styles
        async def block_resource(route, request):
            if request.resource_type in ["image", "stylesheet", "font"]:
                await route.abort()
            else:
                await route.continue_()
        await context.route("**/*", block_resource)

        await page.goto(URL, timeout=60000)
        await page.wait_for_selector("a[href^='/collection/']")

        # Scroll to bottom repeatedly until no new cards are loaded
        prev_count = 0
        while True:
            elements = await page.query_selector_all("a[href^='/collection/']")
            count = len(elements)
            if count == prev_count:
                break
            prev_count = count
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

        # Parse results
        cards = await page.query_selector_all("a[href^='/collection/']")
        seen = set()
        results = []
        for card in cards:
            href = await card.get_attribute("href")
            if not href or "/collection/" not in href:
                continue
            base64_address = href.split("/collection/")[-1].split("/")[0]
            try:
                address = Address(base64_address).to_string(False, True)
            except Exception:
                continue
            text = (await card.inner_text()).strip()
            if not address or not text or address in seen:
                continue
            seen.add(address)
            results.append({
                "name": text,
                "address": address,
                "base64_address": base64_address
            })

        output_dir = os.path.join(os.path.dirname(__file__), "scraped_output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, OUTPUT_FILE)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        await browser.close()
        end_time = time.time()
        print(f"Total collections scraped: {len(results)}")
        print(f"Scraping completed in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    asyncio.run(scrape_getgems_collections())