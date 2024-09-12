import asyncio
import os
import random
from config import USER_AGENTS

from dotenv import load_dotenv

load_dotenv()


async def sleep_randomly(base_sleep: float, randomness: float = 1):
    delay = base_sleep + random.uniform(-randomness, randomness)
    delay = max(delay, 0)
    await asyncio.sleep(delay)


async def get_browser(p):
    user_data_dir = os.path.abspath("chrome_user_data")

    # Ensure the directory exists
    os.makedirs(user_data_dir, exist_ok=True)

    # Farnham, UK coordinates (approximate)
    latitude = 51.2150
    longitude = -0.7986

    return await p.chromium.launch_persistent_context(
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
        ignore_https_errors=True,
        accept_downloads=True,
        permissions=['geolocation'],
        geolocation={'latitude': latitude, 'longitude': longitude},
    )
