"""
MongoDB service for music bot.
Handles database operations for guild settings and queues.
"""

import logging
from typing import Dict, Any, Optional
import motor.motor_asyncio

logger = logging.getLogger(__name__)

# MongoDB connection
client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None


async def init_mongo(connection_string: str, database_name: str = "musicbot"):
    """Initialize MongoDB connection."""
    global client, db
    try:
        client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
        db = client[database_name]
        logger.info("✅ MongoDB connection established")
    except Exception as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        raise


def get_collection(collection_name: str):
    """Get MongoDB collection."""
    if not db:
        raise RuntimeError("MongoDB not initialized")
    return db[collection_name]


async def get_guild_settings(guild_id: int) -> Dict[str, Any]:
    """Get guild settings from database."""
    try:
        collection = get_collection("guild_settings")
        doc = await collection.find_one({"guild_id": str(guild_id)})
        
        if doc:
            # Remove MongoDB _id field
            doc.pop("_id", None)
            return doc
        else:
            # Return default settings
            return {
                "guild_id": str(guild_id),
                "color": "default",
                "custom_emojis": {},
                "volume": 100
            }
            
    except Exception as e:
        logger.error(f"Error getting guild settings for {guild_id}: {e}")
        return {
            "guild_id": str(guild_id),
            "color": "default",
            "custom_emojis": {},
            "volume": 100
        }


async def set_guild_settings(guild_id: int, settings: Dict[str, Any]) -> bool:
    """Set guild settings in database."""
    try:
        collection = get_collection("guild_settings")
        settings["guild_id"] = str(guild_id)
        
        await collection.update_one(
            {"guild_id": str(guild_id)},
            {"$set": settings},
            upsert=True
        )
        
        logger.debug(f"Saved guild settings for {guild_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving guild settings for {guild_id}: {e}")
        return False


async def get_guild_volume(guild_id: int) -> int:
    """Get guild volume from database."""
    try:
        settings = await get_guild_settings(guild_id)
        return settings.get("volume", 100)
    except Exception as e:
        logger.error(f"Error getting guild volume for {guild_id}: {e}")
        return 100


async def set_guild_volume(guild_id: int, volume: int) -> bool:
    """Set guild volume in database."""
    try:
        collection = get_collection("guild_settings")
        
        await collection.update_one(
            {"guild_id": str(guild_id)},
            {"$set": {"volume": volume}},
            upsert=True
        )
        
        logger.debug(f"Saved guild volume for {guild_id}: {volume}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving guild volume for {guild_id}: {e}")
        return False


async def close_mongo():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")
