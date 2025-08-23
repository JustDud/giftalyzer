import asyncio
from playwright.async_api import async_playwright

TELEGRAM_URL = "https://t.me/mrkt/app?startapp=market"

async def get_init_data():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Go to the Telegram WebApp link
        await page.goto(TELEGRAM_URL)

        # Wait for initData to appear (or timeout after 10s)
        await page.wait_for_function(
            "window.Telegram && Telegram.WebApp && Telegram.WebApp.initData && Telegram.WebApp.initData.length > 0",
            timeout=10000
        )

        # Extract initData
        init_data = await page.evaluate("() => Telegram.WebApp.initData")

        await browser.close()
        return init_data

# Run this as a script
if __name__ == "__main__":
    init_data = asyncio.run(get_init_data())
    print("✅ Fresh initData:", init_data)