import os
import pytz
import asyncio
import random
import inspect

from datetime import datetime
from dotenv import load_dotenv
from itertools import cycle
from logger import Logger

load_dotenv()


def get_current_time():
    uk_tz = pytz.timezone('Europe/London')
    return datetime.now(uk_tz).strftime('%d %B %Y, %I:%M:%S %p %Z')


async def sleep_randomly(base_sleep: float, randomness: float = 1, message: str = None):
    delay = base_sleep + random.uniform(-randomness, randomness)
    delay = max(delay, 0)
    current_frame = inspect.currentframe()
    caller_frame = current_frame.f_back
    file_name = caller_frame.f_code.co_filename
    line_number = caller_frame.f_lineno
    project_root = Logger.get_project_root()
    relative_file_name = os.path.relpath(file_name, project_root)
    relative_file_name = f"./{relative_file_name.replace(os.sep, '/')}"
    if message == None:
        Logger.debug(f'Sleeping for {delay:.2f} seconds - {relative_file_name}:{line_number})')
    else:
        Logger.debug(f'Sleeping for {delay:.2f} seconds - {message} - {relative_file_name}:{line_number})')
    await asyncio.sleep(delay)

    del current_frame, caller_frame


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.61 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.54 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36"
]

user_agent_cycle = cycle(USER_AGENTS)


async def get_browser(p):
    user_data_dir = os.path.abspath("chrome_user_data")
    os.makedirs(user_data_dir, exist_ok=True)

    # Randomize geolocation within Farnham, UK area
    latitude = 51.2150 + random.uniform(-0.1, 0.1)
    longitude = -0.7986 + random.uniform(-0.1, 0.1)

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
            f'--user-agent={next(user_agent_cycle)}',
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
    pages = browser.pages
    if pages:
        page = pages[0]
    else:
        page = await browser.new_page()
    return browser, page
