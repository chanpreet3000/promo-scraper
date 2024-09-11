from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

from logger import Logger

load_dotenv()

client = None
db = None
collection = None


async def connect_to_database():
    global client, db, collection
    try:
        Logger.info('Connecting to the database')
        client = AsyncIOMotorClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=10000)
        await client.server_info()
        db = client['PromoBot']
        collection = db['Searches']
        Logger.info("Successfully connected to the database")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to the database: {str(e)}")


async def add_search(search_text):
    Logger.info(f"Adding search term: {search_text}")
    await collection.insert_one({"text": search_text})
    Logger.info(f"Added search term: {search_text}")


async def remove_search(search_text):
    Logger.info(f"Removing search term: {search_text}")
    result = await collection.delete_one({"text": search_text})
    is_deleted = result.deleted_count > 0
    if is_deleted:
        Logger.info(f"Removed search term: {search_text}")
    else:
        Logger.info(f"Search term not found: {search_text}")
    return is_deleted


async def get_all_searches():
    cursor = collection.find()
    searches = [doc['text'] async for doc in cursor]
    Logger.info(f"Found {len(searches)} search terms")
    return searches
