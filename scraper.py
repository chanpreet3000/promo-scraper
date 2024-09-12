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
                await sleep_randomly(DELAY_BETWEEN_SEARCHES)
                Logger.info(f"Searching for '{search}' with promo code: {promo_code}")
                # Input search term
                await page.fill('#keywordSearchInputText', search)
                await sleep_randomly(3, 0.5)
                await page.click('#keywordSearchBtn')

                # Wait for the search results to load
                await page.wait_for_load_state('networkidle')
                await sleep_randomly(7, 1)

                product_url = await page.evaluate('''
                    () => {
                        // Select all product cards within the div
                        const productCards = Array.from(document.querySelectorAll('#productInfoList > li.productGrid'));

                        return productCards.map(card => {
                            const titleElement = card.querySelector('div.productTitleBox a');
                            const product_url = titleElement ? titleElement.href : null;
                            return product_url;
                        });
                    }
                ''')

                all_products.extend(product_url)

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
        await sleep_randomly(DELAY_BETWEEN_SEARCHES)

    Logger.info('Finished Scraping from promo codes')
    return promo_and_product_dict


async def scrape_promo_products(promo_products_dict: dict) -> dict:
    async with async_playwright() as p:
        Logger.info('Scraping promo products')
        promo_products_details_map = promo_products_dict.copy()

        browser = await get_browser(p)
        page = await browser.new_page()

        for promo_code, value in promo_products_dict.items():
            products = []
            for product_link in value['products']:
                try:
                    await sleep_randomly(DELAY_BETWEEN_LINKS)
                    Logger.info(f"Scraping product {product_link}")
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
                    products.append(product)
                except Exception as e:
                    Logger.error(f"Error scraping product {product_link}", e)

            promo_products_details_map[promo_code]['products'] = products

        await browser.close()
        Logger.info('Finished scraping promo products')

        return promo_products_details_map


async def startBot():
    await db.connect_to_database()

    retry_count = 3
    delay = 30

    for attempt in range(retry_count):
        try:
            # Attempt to execute the scraping process
            promo_products_dict = await scrape_from_promo_codes({'A237B13EQ96M7B'})
            Logger.info('Products Links Fetched from All Promo Codes', promo_products_dict)

            promo_products_details_dict = await scrape_promo_products(promo_products_dict)
            Logger.info('Promo Products Details Fetched', promo_products_details_dict)

            # Return the result if successful
            return promo_products_details_dict

        except Exception as e:
            Logger.error(f"Attempt {attempt + 1} failed: {str(e)}")

            # If this was the last attempt, raise the exception
            if attempt == retry_count - 1:
                Logger.error(f"All {retry_count} attempts failed. Aborting.")
                raise

            # Otherwise, wait for 30 seconds before retrying
            Logger.info(f"Retrying in {delay} seconds...")
            await sleep_randomly(delay, 2)

    return None
