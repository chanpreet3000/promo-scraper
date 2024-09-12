import asyncio
import urllib.parse
from playwright.async_api import async_playwright

import db
from config import DELAY_BETWEEN_SEARCHES, DELAY_BETWEEN_PAGES, TOTAL_PAGES_TO_SCRAPE, DELAY_BETWEEN_LINKS, POST_CODE
from db import get_all_searches
from logger import Logger
from utils import sleep_randomly, get_browser


async def scrape_search(page, search_term):
    all_product_links = []

    for page_num in range(1, TOTAL_PAGES_TO_SCRAPE + 1):
        try:
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

            await sleep_randomly(DELAY_BETWEEN_PAGES)
        except Exception as e:
            Logger.error(f"Error scraping page {page_num} for '{search_term}'", e)

    return all_product_links


async def scrape_all_searches():
    async with async_playwright() as p:
        all_product_links = []
        browser = await get_browser(p)
        page = await browser.new_page()

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

        await browser.close()

        return all_product_links


async def scrape_product_from_links(product_links):
    async with async_playwright() as p:
        promo_codes = set()
        browser = await get_browser(p)
        page = await browser.new_page()
        for link in product_links:
            try:
                await sleep_randomly(DELAY_BETWEEN_LINKS)
                Logger.info(f"Scraping product", link)
                await page.goto(link)

                promo_element = await page.query_selector('.promoPriceBlockMessage > div')
                if promo_element:
                    content_id = await promo_element.get_attribute('data-csa-c-content-id')
                    if content_id and content_id.startswith('/promo/'):
                        promo_code = content_id.split('/promo/')[1]
                        promo_codes.add(promo_code)
                        Logger.info(f"Found promo code: {promo_code}")
            except Exception as e:
                Logger.error(f"Error scraping product {link}", e)

        await browser.close()
        return promo_codes


async def setup_amazon_uk():
    async with async_playwright() as p:
        Logger.info("Setting up Amazon UK")
        browser = await get_browser(p)
        page = await browser.new_page()
        # Navigate to Amazon UK
        await page.goto('https://www.amazon.co.uk')

        # Wait for and accept cookies
        try:
            accept_cookies_button = page.locator('#sp-cc-accept')
            await accept_cookies_button.click(timeout=5000)
            Logger.info("Cookies accepted")
        except Exception as e:
            Logger.error(f"Could not find or click cookie accept button", e)

        # Set UK postcode
        try:
            await page.click('#glow-ingress-block')

            # Wait for the postcode input field to be visible
            postcode_input = page.locator('#GLUXZipUpdateInput')
            await postcode_input.wait_for(state='visible', timeout=5000)

            # Enter the postcode with a retry mechanism
            await postcode_input.fill(POST_CODE)
            await sleep_randomly(3, 0.5)

            # Click the "Apply" button
            await page.click('#GLUXZipUpdate')

            # Wait for the location to update
            await page.wait_for_selector('#glow-ingress-line2')

            Logger.info("Postcode set successfully")
            await sleep_randomly(5, 1)
        except Exception as e:
            raise e

        Logger.info("Amazon UK setup completed")


async def main():
    await db.connect_to_database()

    await setup_amazon_uk()

    product_links = await scrape_all_searches()
    Logger.info(f"Scraping complete. Found {len(product_links)} product links.")

    promo_codes = await scrape_product_from_links(product_links)
    Logger.info(f"Found {len(promo_codes)} promo codes", promo_codes)


if __name__ == "__main__":
    asyncio.run(main())
