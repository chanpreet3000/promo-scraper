import os
import pytz
import asyncio
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def get_current_time():
    uk_tz = pytz.timezone('Europe/London')
    return datetime.now(uk_tz).strftime('%d %B %Y, %I:%M:%S %p %Z')


async def sleep_randomly(base_sleep: float, randomness: float = 1):
    delay = base_sleep + random.uniform(-randomness, randomness)
    delay = max(delay, 0)
    await asyncio.sleep(delay)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.54 Safari/537.36",
]


async def get_browser(p):
    user_data_dir = os.path.abspath("chrome_user_data")
    os.makedirs(user_data_dir, exist_ok=True)

    # Randomize geolocation within Farnham, UK area
    latitude = 51.2150 + random.uniform(-0.05, 0.05)
    longitude = -0.7986 + random.uniform(-0.05, 0.05)

    # proxy_manager = ProxyManager()
    # proxy = proxy_manager.get_random_proxy()
    # proxy_server = f"http://{proxy[0]}:{proxy[1]}"

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
            '--disable-extensions',
            '--disable-popup-blocking',
            '--disable-infobars',
        ],
        ignore_https_errors=True,
        accept_downloads=True,
        permissions=['geolocation'],
        geolocation={'latitude': latitude, 'longitude': longitude},
        locale='en-GB',
        timezone_id='Europe/London',
    )

    # Randomize browser fingerprint
    page = await browser.new_page()
    await page.evaluate('''
        () => {
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-GB', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        }
    ''')
    await page.close()

    return browser
