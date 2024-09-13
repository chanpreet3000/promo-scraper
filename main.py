import asyncio

from dotenv import load_dotenv
import os

import db
from discord_bot import client
from logger import Logger

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')


async def main():
    async with client:
        await db.connect_to_database()

        Logger.info('Starting the Discord Bot')
        await client.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        Logger.critical('An error occurred', e)
