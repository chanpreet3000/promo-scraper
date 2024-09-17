import time
import urllib.parse
import re
from playwright.async_api import async_playwright

from config import DELAY_BETWEEN_SEARCHES, DELAY_BETWEEN_PAGES, MAX_PAGES_TO_SCRAPE, DELAY_BETWEEN_LINKS, POST_CODE, \
    SCRAPER_RETRIES, SCRAPER_RETRIES_DELAY, SCRAPING_URL_BATCH_SIZE, BATCH_SIZE_DELAY, DELAY_BETWEEN_STEPS, \
    MAX_SHOW_MORE_CLICKS, LIMITING_RESULTS, CAPTCHA_DETECTED_DELAY
from db import get_all_searches, connect_to_database, process_products
from logger import Logger
from models import ProductDetails, Promotion, ProcessedProductDetails
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
        except:
            Logger.warn(f"Could not find or click cookie accept button")

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
                    'div.s-result-item div.a-section a.a-link-normal.s-no-outline',
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
            raise e

        all_product_links = list(set(all_product_links))
        all_product_links = all_product_links[:LIMITING_RESULTS]

        Logger.info(
            f"Finished scraping promo products from Search = {search_term}. Found {len(all_product_links)} product links")
        return all_product_links


async def scraping_promo_products_from_searches() -> list[str]:
    Logger.info('Started Scraping all promo products from searches')
    all_product_links = []
    search_items = await get_all_searches()

    for search_term in search_items:
        try:
            all_product_links.extend(await scraping_promo_products_from_search(search_term))
            await sleep_randomly(DELAY_BETWEEN_SEARCHES)
        except:
            await sleep_randomly(CAPTCHA_DETECTED_DELAY, 5)

    all_product_links = list(set(all_product_links))
    Logger.info(f'Finished Scraping all promo products from searches. Found {len(all_product_links)} product links')
    return all_product_links


def check_promo_regex(text):
    patterns = [
        r'^.*Get \d+ for the price of \d+.*$',
        r'^.*Get any.*$',
        r'^.*2 for.*$',
    ]

    # Check each pattern
    for pattern in patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True

    return False


async def scrape_promo_codes_from_product_url(page, link: str) -> set[str]:
    Logger.info(f"Scraping promo codes from link: {link}")
    try:
        await page.goto(link)
        promo_codes = set()
        promo_elements = await page.query_selector_all('a[href^="/promotion/psp/"]')
        for promo_element in promo_elements:
            try:
                href = await promo_element.get_attribute('href')
                promo_code = href.split('/promotion/psp/')[1].split('?')[0]
                promo_codes.add(promo_code)
                Logger.info(f"Found promo code: {promo_code}")
            except Exception as e:
                Logger.error(f"Error scraping promo code", e)

        Logger.info(f"Finished Scraping promo codes from link: {link}")
        return promo_codes
    except Exception as e:
        Logger.error(f"Error scraping product details: {link}", e)

    return set()


async def scrape_promo_codes_from_urls_in_batch(product_links: list[str]) -> set[str]:
    Logger.info(f"Scraping promo codes from urls in batch")
    promo_codes = set()
    total_batches = (len(product_links) - 1) // SCRAPING_URL_BATCH_SIZE + 1
    for i in range(0, len(product_links), SCRAPING_URL_BATCH_SIZE):
        Logger.info(f"Starting batch {i // SCRAPING_URL_BATCH_SIZE + 1} of {total_batches}")
        batch = product_links[i:i + SCRAPING_URL_BATCH_SIZE]

        async with async_playwright() as p:
            browser, page = await get_browser(p)
            for link in batch:
                promo_codes.update(await scrape_promo_codes_from_product_url(page, link))
                await sleep_randomly(DELAY_BETWEEN_LINKS)

        Logger.info(f"Completed batch {i // SCRAPING_URL_BATCH_SIZE + 1} of {total_batches}")
        await sleep_randomly(BATCH_SIZE_DELAY, 3)

    Logger.info(f"Finished scraping promo codes from urls in batch. Found {len(promo_codes)} promo codes", promo_codes)
    return promo_codes


async def scrape_links_from_promo_code(promo_code: str) -> list[Promotion]:
    async with async_playwright() as p:
        Logger.info(f"Scraping product urls from promo code: {promo_code}")
        browser, page = await get_browser(p)

        url = f'https://www.amazon.co.uk/promotion/psp/{promo_code}'
        await page.goto(url)

        all_promotion_products: list[Promotion] = []

        try:
            page_title = await page.title()
            if page_title.startswith("Amazon.co.uk: ") and page_title.endswith(" promotion"):
                promotion_title = page_title[len("Amazon.co.uk: "):-len(" promotion")]
            else:
                promotion_title = "Unknown Promotion"
        except Exception as e:
            Logger.warn(f"Could not find or process page title:", e)
            promotion_title = "Unknown Promotion"

        if check_promo_regex(promotion_title):
            Logger.info(f"Promotion title: {promotion_title} matches the regex")
        else:
            Logger.warn(f"Promotion title: {promotion_title} does not match the regex. Skipping...")
            await sleep_randomly(DELAY_BETWEEN_PAGES)
            return all_promotion_products

        await sleep_randomly(5, 0.5)

        search_list = await get_all_searches()

        for search in search_list:
            try:
                Logger.info(f"Searching = '{search}' with promo code: {promo_code}")

                # Input search term
                await page.fill('#keywordSearchInputText', search)
                await page.click('#keywordSearchBtn', timeout=60000)
                await sleep_randomly(7, 1)
                for index in range(MAX_SHOW_MORE_CLICKS):
                    try:
                        show_more_button = await page.query_selector('#showMore.showMoreBtn')
                        if show_more_button:
                            await show_more_button.scroll_into_view_if_needed(timeout=10000)
                            await show_more_button.click(timeout=10000)
                            Logger.info('Clicked "Show More" button')
                            await sleep_randomly(7, 1)
                        else:
                            raise Exception("Show More button not found")
                    except:
                        Logger.error(f"Error clicking 'Show More' button")
                        break

                product_urls = await page.evaluate('''
                       () => {
                           const productCards = Array.from(document.querySelectorAll('#productInfoList > li.productGrid'));
                           return productCards.map(card => {
                               const titleElement = card.querySelector('div.productTitleBox a');
                               return titleElement ? titleElement.href : null;
                           });
                       }
                   ''')

                for product_url in product_urls:
                    all_promotion_products.append(Promotion(promo_code, promotion_title, url, product_url))

                Logger.info(
                    f'Fetched {len(all_promotion_products)} products for search term: {search} and promo code: {promo_code}')
            except Exception as e:
                raise e
            finally:
                await sleep_randomly(DELAY_BETWEEN_SEARCHES)

        Logger.info(
            f"Finished Scraping product urls for promo code: {promo_code}. Found {len(all_promotion_products)} products")

        await sleep_randomly(DELAY_BETWEEN_SEARCHES)
        return all_promotion_products


async def scrape_links_from_promo_codes(promo_codes: set[str]) -> list[Promotion]:
    Logger.info('scraping product links from all promo codes')

    promotions_list: list[Promotion] = []
    for coupon_index, promo_code in enumerate(promo_codes):
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                Logger.info(
                    f"Attempting coupon {coupon_index + 1}/{len(promo_codes)}, attempt {attempt + 1}/{max_attempts}")
                promo_results = await scrape_links_from_promo_code(promo_code)
                promotions_list.extend(promo_results)
                break
            except Exception as e:
                Logger.error(
                    f"Error scraping promo code {promo_code} (coupon {coupon_index + 1}/{len(promo_codes)}) on attempt {attempt + 1}",
                    e)
                if attempt == max_attempts - 1:
                    Logger.error(
                        f"Max attempts reached for promo code {promo_code} (coupon {coupon_index + 1}/{len(promo_codes)}). Moving to next promo code.")
                else:
                    Logger.info(
                        f"Retrying coupon {coupon_index + 1}/{len(promo_codes)}, attempt {attempt + 2}/{max_attempts} for promo code {promo_code}...")
                    await sleep_randomly(2 * DELAY_BETWEEN_LINKS, 5)
    Logger.info(
        f'finished scraping product links from all promo codes. found {len(promotions_list)} items with promotions',
        promotions_list)
    return promotions_list


async def scrape_product_details_from_url(page, promotion_link: Promotion) -> ProductDetails:
    product_link = promotion_link.product_url
    try:
        Logger.info(f"Scraping product details : {product_link}")
        await page.goto(product_link)

        product = await page.evaluate('''
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

        return ProductDetails(
            promotion_code=promotion_link.promotion_code,
            promotion_title=promotion_link.promotion_title,
            promotion_url=promotion_link.promotion_url,
            product_url=promotion_link.product_url,
            product_title=product['product_title'],
            product_image_url=product['product_img'],
            product_price=product['current_price'],
            product_sales=product['sales_last_month'],
            product_asin=product['asin'],
        )
    except Exception as e:
        Logger.error(f"Error scraping product - {product_link}, Most Likely Captcha is detected!", e)
        raise e
    finally:
        Logger.info(f"Finished scraping product details : {product_link}")


async def scrape_product_details_from_urls_in_batch(product_links: list[Promotion]) -> list[ProductDetails]:
    Logger.info(f"Scraping product details from urls in batch")
    product_details_list: list[ProductDetails] = []

    total_batches = (len(product_links) - 1) // SCRAPING_URL_BATCH_SIZE + 1
    for i in range(0, len(product_links), SCRAPING_URL_BATCH_SIZE):
        Logger.info(f"Starting batch {i // SCRAPING_URL_BATCH_SIZE + 1} of {total_batches}")
        batch = product_links[i:i + SCRAPING_URL_BATCH_SIZE]

        async with async_playwright() as p:
            browser, page = await get_browser(p)
            for link in batch:
                try:
                    product_details_list.append(await scrape_product_details_from_url(page, link))
                    await sleep_randomly(DELAY_BETWEEN_LINKS)
                except:
                    await sleep_randomly(CAPTCHA_DETECTED_DELAY, 3)
                    pass

        Logger.info(f"Completed batch {i // SCRAPING_URL_BATCH_SIZE + 1} of {total_batches}")
        await sleep_randomly(BATCH_SIZE_DELAY, 3)

    Logger.info(f"Finished Scraping product details from urls in batch. Found {len(product_details_list)} promo codes",
                product_details_list)
    return product_details_list


async def startScraper() -> ProcessedProductDetails:
    Logger.info('Starting the Scraper')
    start_time = time.time()

    await connect_to_database()

    for attempt in range(SCRAPER_RETRIES):
        try:
            await setup_amazon_uk()
            await sleep_randomly(DELAY_BETWEEN_STEPS)

            product_links = await scraping_promo_products_from_searches()
            await sleep_randomly(DELAY_BETWEEN_STEPS)

            promo_codes = await scrape_promo_codes_from_urls_in_batch(product_links)
            await sleep_randomly(DELAY_BETWEEN_STEPS)

            promotions_list = await scrape_links_from_promo_codes(promo_codes)
            await sleep_randomly(DELAY_BETWEEN_STEPS)

            product_details_list = await scrape_product_details_from_urls_in_batch(promotions_list)

            filtered_products = await process_products(product_details_list)

            return filtered_products
        except Exception as e:
            Logger.critical(f"Attempt {attempt + 1} failed", e)

            if attempt == SCRAPER_RETRIES - 1:
                Logger.critical(f"All {SCRAPER_RETRIES} attempts failed. Aborting.")
                raise

            Logger.info(f"Retrying in {SCRAPER_RETRIES_DELAY} seconds...")
            await sleep_randomly(SCRAPER_RETRIES_DELAY, 2)

    end_time = time.time()
    total_time = end_time - start_time
    hours, remainder = divmod(total_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    Logger.info(f"Scraper finished execution in {int(hours)} hours, {int(minutes)} minutes, and {int(seconds)} seconds")

    Logger.info('Ending the Scraper')
    return ProcessedProductDetails()
