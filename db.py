from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

from data_manager import DataManager
from logger import Logger

load_dotenv()

client = None
db = None
collection = None
products_collection = None
data_manager = DataManager()


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


async def upsert_product(product_data):
    current_time = datetime.utcnow()
    product_id = f"{product_data['asin']}/{product_data['promo_code']}"

    update_data = {
        "last_updated": current_time,
        "product_img": product_data['product_img'],
        "product_title": product_data['product_title'],
        "product_url": product_data['product_url'],
        "asin": product_data['asin'],
        "current_price": product_data['current_price'],
        "sales_last_month": product_data['sales_last_month'],
        "promo_code": product_data['promo_code'],
        "promo_text": product_data['promo_text']
    }

    result = await products_collection.update_one(
        {"_id": product_id},
        {"$set": update_data},
        upsert=True
    )

    Logger.info(f"Upserted product: {product_id}")
    return result.upserted_id is not None


async def process_products(product_list, days=7):
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    cutoff_sales = data_manager.get_monthly_sales_cutoff()

    processed_products = {
        "upserted": [],
        "up_to_date": []
    }

    for product in product_list:
        product_id = f"{product['asin']}/{product['promo_code']}"
        doc = await products_collection.find_one(
            {
                "_id": product_id,
                "last_updated": {"$gte": cutoff_date}
            }
        )

        if doc is None and product['sales_last_month'] >= cutoff_sales:
            upserted = await upsert_product(product)
            if upserted:
                processed_products["upserted"].append(product)
            else:
                Logger.warn(f"Failed to upsert product: {product_id}")
        else:
            processed_products["up_to_date"].append(product)

    Logger.info(f"Upserted {len(processed_products['upserted'])} products")
    Logger.info(f"Found {len(processed_products['up_to_date'])} up-to-date products")
    return processed_products["upserted"]
