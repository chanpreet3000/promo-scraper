import json
import urllib.parse
import re
from playwright.async_api import async_playwright

from config import DELAY_BETWEEN_SEARCHES, DELAY_BETWEEN_PAGES, MAX_PAGES_TO_SCRAPE, DELAY_BETWEEN_LINKS, POST_CODE, \
    SCRAPER_RETRIES, SCRAPER_RETRIES_DELAY, BATCH_SIZE, BATCH_SIZE_DELAY, DELAY_BETWEEN_STEPS
from db import get_all_searches, connect_to_database, process_products
from logger import Logger
from utils import sleep_randomly, get_browser


async def setup_amazon_uk():
    async with async_playwright() as p:
        Logger.info("Setting up Amazon UK")

        browser, page = await get_browser(p)

        # Navigate to Amazon UK
        await page.goto('https://www.amazon.co.uk')

        # Wait for and accept cookies
        try:
            accept_cookies_button = page.locator('#sp-cc-accept')
            await accept_cookies_button.click(timeout=5000)
            Logger.info("Cookies accepted")
        except Exception as e:
            Logger.error(f"Could not find or click cookie accept button", e)

        await page.click('#glow-ingress-block')

        # Wait for the postcode input field to be visible
        postcode_input = page.locator('#GLUXZipUpdateInput')
        await postcode_input.wait_for(state='visible', timeout=5000)

        # Enter the postcode with a retry mechanism
        await postcode_input.fill(POST_CODE)
        await sleep_randomly(2, 0)

        # Click the "Apply" button
        await page.click('#GLUXZipUpdate')

        # Wait for the location to update
        await page.wait_for_selector('#glow-ingress-line2')

        Logger.info("Postcode set successfully")
        await sleep_randomly(4, 1)
        await browser.close()

        Logger.info("Amazon UK setup completed")


async def scraping_promo_products_from_search(search_term: str) -> list[str]:
    async with async_playwright() as p:
        Logger.info(f"Scraping promo products from Search = {search_term}")
        browser, page = await get_browser(p)

        all_product_links = []
        try:
            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                Logger.info(f"Scraping page {page_num} for Search = '{search_term}'")

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
                Logger.info(
                    f"Scraped page {page_num} for Search = '{search_term}'. Found {len(product_links)} product links")

                try:
                    await page.locator(
                        ".s-pagination-item.s-pagination-next.s-pagination-button.s-pagination-separator").wait_for(
                        timeout=5000)
                except:
                    Logger.info(f"No more pages found for Search = '{search_term}'")
                    break

                await sleep_randomly(DELAY_BETWEEN_PAGES)
        except Exception as e:
            Logger.error(f"Error scraping search term: {search_term}", e)

        await browser.close()

        all_product_links = list(set(all_product_links))

        Logger.info(
            f"Finished scraping promo products from Search = {search_term}. Found {len(all_product_links)} product links")
        return all_product_links


async def scraping_promo_products_from_searches() -> list[str]:
    Logger.info('Started Scraping all promo products from searches')
    all_product_links = []
    search_items = await get_all_searches()

    for search_term in search_items:
        all_product_links.extend(await scraping_promo_products_from_search(search_term))
        await sleep_randomly(DELAY_BETWEEN_SEARCHES)

    all_product_links = list(set(all_product_links))
    Logger.info(f'Finished Scraping all promo products from searches. Found {len(all_product_links)} product links')
    return all_product_links


def check_promo_regex(text):
    patterns = [
        r'^.*Get \d+ for the price of \d+.*$',
        r'^.*Get any.*$',
        r'^.*2 for.*$'
    ]

    # Check each pattern
    for pattern in patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True

    return False


async def scrape_from_product_url(page, link: str) -> list[dict]:
    Logger.info(f"Scraping product details from link: {link}")
    product_details_list = []
    try:
        await page.goto(link)

        promo_codes = []
        promo_elements = await page.query_selector_all('#ppd_newAccordionRow .promoPriceBlockMessage > div')
        for promo_element in promo_elements:
            content_id = await promo_element.get_attribute('data-csa-c-content-id')
            if content_id and content_id.startswith('/promo/'):
                promo_code = content_id.split('/promo/')[1]
                promo_text = await promo_element.inner_text()
                promo_text = promo_text.strip()
                if check_promo_regex(promo_text):
                    promo_codes.append({
                        "code": promo_code,
                        "text": promo_text
                    })
                    Logger.info(f"Found promo code: {promo_code}")

        product_details = await page.evaluate('''
                        () => {
                            const product_title = document.querySelector('#productTitle').innerText;
                            const product_url = window.location.href;
                            const product_img = document.querySelector('#landingImage').src;

                            // Get the ASIN (extracted from the product URL)
                            const asin = product_url ? product_url.match(/\/dp\/(\\w+)/) ? product_url.match(/\/dp\/(\\w+)/)[1] : null : null;

                            // Get the current price
                            const priceElement = document.querySelector('#corePriceDisplay_desktop_feature_div .reinventPricePriceToPayMargin');
                            const current_price = priceElement ? priceElement.textContent.trim() : null;

                            // Get sales in last month
                            const salesElement = document.querySelector('#social-proofing-faceout-title-tk_bought');
                            const sales_last_month_raw = salesElement ? salesElement.textContent.trim() : 'N/A';

                            // Function to convert sales string to number
                            const convertSales = (salesStr) => {
                                const match = salesStr.match(/(\d+)([KM]?)\+/);
                                if (match) {
                                    const number = parseInt(match[1]);
                                    const unit = match[2];
                                    if (unit === 'K') {
                                        return number * 1000;
                                    } else if (unit === 'M') {
                                        return number * 1000000;
                                    } else {
                                        return number;
                                    }
                                }
                                return 0;
                            };

                            // Convert sales_last_month to number
                            const sales_last_month = convertSales(sales_last_month_raw);

                            return {
                                product_img,
                                product_title,
                                product_url,
                                asin,
                                current_price,
                                sales_last_month
                            };
                        }
                    ''')

        for promo_code in promo_codes:
            temp_product_details = product_details.copy()
            temp_product_details['promo_code'] = promo_code['code']
            temp_product_details['promo_text'] = promo_code['text']
            product_details_list.append(temp_product_details)

        Logger.info(f"Finished Scraping product details from link: {link}")
    except Exception as e:
        Logger.error(f"Error scraping product details: {link}", e)

    return product_details_list


async def scrape_promo_product_details(product_links: list[str]) -> list[dict]:
    async with async_playwright() as p:
        browser, page = await get_browser(p)
        product_details_list = []
        for link in product_links:
            product_details_list.extend(await scrape_from_product_url(page, link))
            await sleep_randomly(DELAY_BETWEEN_LINKS)
        return product_details_list


async def scrape_promo_product_details_in_batch(product_links: list[str]) -> list[dict]:
    Logger.info(f"Scraping promo product details in batch")
    all_product_details = []
    total_batches = (len(product_links) - 1) // BATCH_SIZE + 1
    for i in range(0, len(product_links), BATCH_SIZE):
        Logger.info(f"Starting batch {i // BATCH_SIZE + 1} of {total_batches}")
        batch = product_links[i:i + BATCH_SIZE]
        batch_details = await scrape_promo_product_details(batch)
        all_product_details.extend(batch_details)
        Logger.info(f"Completed batch {i // BATCH_SIZE + 1} of {total_batches}")
        await sleep_randomly(BATCH_SIZE_DELAY, 3)

    Logger.info("Finished scraping promo product details in batch")
    return all_product_details


async def startScraper() -> tuple[list[dict], int]:
    Logger.info('Starting the Scraper')

    await connect_to_database()

    for attempt in range(SCRAPER_RETRIES):
        try:
            await setup_amazon_uk()
            await sleep_randomly(DELAY_BETWEEN_STEPS)

            product_links = await scraping_promo_products_from_searches()
            await sleep_randomly(DELAY_BETWEEN_STEPS)

            product_details = await scrape_promo_product_details_in_batch(product_links)

            product_details = list({json.dumps(detail, sort_keys=True) for detail in product_details})
            product_details = [json.loads(detail) for detail in product_details]

            await sleep_randomly(DELAY_BETWEEN_STEPS)

            filtered_products = await process_products(product_details)

            filtered_products.sort(key=lambda x: x.get('promo_code', ''))

            return filtered_products, len(product_details)

        except Exception as e:
            Logger.critical(f"Attempt {attempt + 1} failed", e)

            if attempt == SCRAPER_RETRIES - 1:
                Logger.critical(f"All {SCRAPER_RETRIES} attempts failed. Aborting.")
                raise

            Logger.info(f"Retrying in {SCRAPER_RETRIES_DELAY} seconds...")
            await sleep_randomly(SCRAPER_RETRIES_DELAY, 2)

    Logger.info('Ending the Scraper')
    return [], 0
