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
        client = AsyncIOMotorClient(os.getenv('MONGO_URI'), serverSelectionTimeoutMS=5000)
        await client.server_info()
        db = client['PromoBot']
        collection = db['Searches']
        Logger.info("Successfully connected to the database")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to the database: {str(e)}")


async def add_search(search_text):
    await collection.insert_one({"text": search_text})


async def remove_search(search_text):
    result = await collection.delete_one({"text": search_text})
    return result.deleted_count > 0


async def get_all_searches():
    cursor = collection.find()
    return [doc['text'] async for doc in cursor]
