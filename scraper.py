import asyncio
import urllib.parse
from playwright.async_api import async_playwright

import db
from config import DELAY_BETWEEN_SEARCHES, DELAY_BETWEEN_PAGES, TOTAL_PAGES_TO_SCRAPE, DELAY_BETWEEN_LINKS, POST_CODE, \
    DELAY_BETWEEN_PROMO_SEARCHES, DELAY_BETWEEN_PROMO
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

            # Extract product links only for products with promotions
            product_links = await page.eval_on_selector_all(
                '.s-result-item:has(.s-coupon-unclipped) a.a-link-normal.s-no-outline',
                "elements => elements.map(el => el.href)"
            )
            all_product_links.extend(product_links)
            await sleep_randomly(DELAY_BETWEEN_PAGES)
        except Exception as e:
            Logger.error(f"Error scraping page {page_num} for '{search_term}'", e)
    return list(set(all_product_links))


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

        return list(set(all_product_links))


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
        finally:
            await browser.close()

        Logger.info("Amazon UK setup completed")


async def scrape_from_promo_code(promo_code: str) -> dict:
    async with async_playwright() as p:
        Logger.info(f"Scraping promo code: {promo_code}")
        browser = await get_browser(p)
        page = await browser.new_page()

        url = f'https://www.amazon.co.uk/promotion/psp/{promo_code}'
        await page.goto(url)

        # Find the promotion title
        try:
            title_element = await page.wait_for_selector('#promotionTitle', timeout=5000)
            promotion_title = await title_element.inner_text()
        except Exception as e:
            Logger.warn(f"Could not find promotion title:", e)
            promotion_title = "Unknown Promotion"

        all_products = []
        search_list = await get_all_searches()

        for search in search_list:
            try:
                await sleep_randomly(DELAY_BETWEEN_PROMO_SEARCHES)
                Logger.info(f"Searching for '{search}' with promo code: {promo_code}")
                # Input search term
                await page.fill('#keywordSearchInputText', search)
                await sleep_randomly(3, 0.5)
                await page.click('#keywordSearchBtn')

                # Wait for the search results to load
                await page.wait_for_load_state('networkidle')
                await sleep_randomly(7, 0.5)

                product_details = await page.evaluate('''
                    () => {
                        // Select all product cards within the div
                        const productCards = Array.from(document.querySelectorAll('#productInfoList > li.productGrid'));

                        return productCards.map(card => {
                            // Get the product image URL
                            const imgElement = card.querySelector('div.productImageBox img');
                            const product_img = imgElement ? imgElement.src : null;

                            // Get the product title
                            const titleElement = card.querySelector('div.productTitleBox a');
                            const product_title = titleElement ? titleElement.textContent.trim() : null;

                            // Get the product URL
                            const product_url = titleElement ? titleElement.href : null;

                            return {
                                product_img,
                                product_title,
                                product_url,
                            };
                        });
                    }
                ''')

                all_products.extend(product_details)

                Logger.info(f'Fetched all products for search term: {search} and promo code: {promo_code}')
            except Exception as e:
                Logger.error(f"Error scraping search term: {search}", e)

        await browser.close()
        Logger.info(f"Scraping Finished for promo code: {promo_code}")

        result = {
            "title": promotion_title,
            "promotion_url": url,
            "products": all_products
        }

        return result


async def scrape_from_promo_codes(promo_codes) -> dict:
    Logger.info('Scraping from promo codes')
    promo_and_product_dict = dict()
    for promo_code in promo_codes:
        data = await scrape_from_promo_code(promo_code)
        promo_and_product_dict[promo_code] = data
        await sleep_randomly(DELAY_BETWEEN_PROMO)

    Logger.info('Finished Scraping from promo codes')
    return promo_and_product_dict


async def main():
    await db.connect_to_database()

    await setup_amazon_uk()

    Logger.info("Starting scraping for all products from searches")
    product_links = await scrape_all_searches()
    Logger.info(f"Scraping complete. Found {len(product_links)} product links.")

    Logger.info("Starting scraping for promo codes")
    promo_codes = await scrape_product_from_links(product_links)
    Logger.info(f"Found {len(promo_codes)} promo codes", promo_codes)

    promo_and_product_dict = await scrape_from_promo_codes(promo_codes)
    Logger.info('Scraping complete', promo_and_product_dict)


# Test Promo codes
# {'A237B13EQ96M7B',
#  'A2P1ZTFRNJUUMV',
#  'A2PGR4VI4CPO26',
#  'A2S8TQ1DMNONDY',
#  'A71VQZ3KSA8IY',
#  'A98ZJPT0I731L'}
if __name__ == "__main__":
    asyncio.run(main())
