import asyncio
import os
import random
import urllib.parse
from dotenv import load_dotenv
from playwright.async_api import async_playwright

import db
from config import DELAY_BETWEEN_SEARCHES, DELAY_BETWEEN_PAGES, TOTAL_PAGES_TO_SCRAPE
from db import get_all_searches
from logger import Logger
from utils import sleep_randomly

load_dotenv()

# Load proxy credentials
PROXY_IP = os.getenv("PROXY_IP")
PROXY_PORT = os.getenv("PROXY_PORT")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

# User agents list
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
]


async def scrape_search(page, search_term):
    all_product_links = []

    for page_num in range(1, TOTAL_PAGES_TO_SCRAPE):
        try:
            await sleep_randomly(DELAY_BETWEEN_PAGES)

            Logger.info(f"Scraping page {page_num} for '{search_term}'")

            encoded_search_term = urllib.parse.quote(search_term)
            await page.goto(f"https://www.amazon.co.uk/s?k={encoded_search_term}&page={page_num}")

            # Wait for the results to load
            await page.wait_for_selector('.s-main-slot')

            # Extract product links from the current page
            product_links = await page.eval_on_selector_all(
                'a.a-link-normal.s-no-outline',
                "elements => elements.map(el => el.href)"
            )
            all_product_links.extend(product_links)
        except Exception as e:
            Logger.error(f"Error scraping page {page_num} for '{search_term}'", e)

    return all_product_links


async def scrape_all_searches():
    async with async_playwright() as p:
        user_data_dir = os.path.abspath("chrome_user_data")

        # Ensure the directory exists
        os.makedirs(user_data_dir, exist_ok=True)

        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-setuid-sandbox',
                '--no-sandbox',
                '--ignore-certificate-errors',
                '--enable-features=NetworkService,NetworkServiceInProcess',
                f'--user-agent={random.choice(USER_AGENTS)}',
            ],
            viewport={'width': 1920, 'height': 1080},
            # proxy={
            #     "server": f"http://{PROXY_IP}:{PROXY_PORT}",
            #     "username": PROXY_USERNAME,
            #     "password": PROXY_PASSWORD
            # },
            ignore_https_errors=True,
            accept_downloads=True,
            permissions=['geolocation'],
        )

        page = await browser.new_page()

        # Array to store all product links
        all_product_links = []

        # Loop through search terms
        search_items = await get_all_searches()
        for search_term in search_items:
            try:
                Logger.info(f"Searching for: {search_term}")
                all_product_links.extend(await scrape_search(page, search_term))
                await sleep_randomly(DELAY_BETWEEN_SEARCHES)
                Logger.info(f"Completed scraping for: {search_term}")
            except Exception as e:
                Logger.error(f"Error scraping search term: {search_term}", e)

        Logger.info(f"Scraping complete. Found {len(all_product_links)} product links.", all_product_links)
        await browser.close()

        return all_product_links


async def main():
    await db.connect_to_database()
    product_links = await scrape_all_searches()
    Logger.info(f"Product links: {product_links}")


if __name__ == "__main__":
    asyncio.run(main())
