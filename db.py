from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

from logger import Logger

load_dotenv()

client = None
db = None
collection = None
products_collection = None


async def connect_to_database():
    global client, db, collection, products_collection
    try:
        Logger.info('Connecting to the database')
        client = AsyncIOMotorClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=10000)
        await client.server_info()
        db = client['PromoBot']
        collection = db['Searches']
        products_collection = db['Products']
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


async def upsert_product(asin, promo_code):
    current_time = datetime.utcnow()
    result = await products_collection.update_one(
        {"asin": asin},
        {"$set": {"last_updated": current_time, "promo_code": promo_code}},
        upsert=True
    )
    Logger.info(f"Upserted product: {asin}")
    return result.upserted_id is not None


async def get_recent_products(days=7):
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    cursor = products_collection.find({"last_updated": {"$gte": cutoff_date}})
    recent_products = [doc['asin'] async for doc in cursor]
    Logger.info(f"Found {len(recent_products)} recent products")
    return recent_products
