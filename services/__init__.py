import motor.motor_asyncio
from typing import Any, Dict, Optional
from config.settings import Settings

MONGODB_URI = Settings.MONGODB_URI


class MongoService:
    def __init__(self, uri: str = MONGODB_URI, db_name: str = "musicbot"):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self.guild_settings = self.db["guild_settings"]
        self.effects = self.db["effects"]
        self.history = self.db["history"]
        self.favorites = self.db["favorites"]
        self.playlists = self.db["playlists"]

    # Пример: получить настройки сервера
    async def get_guild_settings(self, guild_id: int) -> Optional[Dict[str, Any]]:
        # Убеждаемся что guild_id - строка
        guild_id_str = str(guild_id)
        return await self.guild_settings.find_one({"guild_id": guild_id_str})

    async def set_guild_settings(self, guild_id: int, settings: Dict[str, Any]) -> None:
        # Убеждаемся что guild_id - строка
        guild_id_str = str(guild_id)
        await self.guild_settings.update_one(
            {"guild_id": guild_id_str}, {"$set": settings}, upsert=True
        )

    # Пример: сохранить эффекты для сервера
    async def set_effects(self, guild_id: int, effects: Dict[str, Any]) -> None:
        await self.effects.update_one(
            {"guild_id": guild_id}, {"$set": {"effects": effects}}, upsert=True
        )

    async def get_effects(self, guild_id: int) -> Optional[Dict[str, Any]]:
        doc = await self.effects.find_one({"guild_id": guild_id})
        return doc["effects"] if doc else None

    # Пример: история треков
    async def add_history(self, guild_id: int, track: Dict[str, Any]) -> None:
        await self.history.insert_one({"guild_id": guild_id, **track})

    async def get_history(self, guild_id: int, limit: int = 25) -> list:
        cursor = self.history.find({"guild_id": guild_id}).sort("_id", -1).limit(limit)
        return [doc async for doc in cursor]

    # Пример: избранное
    async def add_favorite(self, user_id: int, track: Dict[str, Any]) -> None:
        await self.favorites.insert_one({"user_id": user_id, **track})

    async def get_favorites(self, user_id: int, limit: int = 25) -> list:
        cursor = self.favorites.find({"user_id": user_id}).sort("_id", -1).limit(limit)
        return [doc async for doc in cursor]

    # Пример: плейлисты
    async def save_playlist(self, user_id: int, name: str, tracks: list) -> None:
        await self.playlists.update_one(
            {"user_id": user_id, "name": name},
            {"$set": {"tracks": tracks}},
            upsert=True,
        )

    async def get_playlist(self, user_id: int, name: str) -> Optional[Dict[str, Any]]:
        return await self.playlists.find_one({"user_id": user_id, "name": name})

    async def update_guild_prefix(self, guild_id: int, prefix: str):
        await self.guild_settings.update_one(
            {"guild_id": guild_id}, {"$set": {"prefix": prefix}}, upsert=True
        )

    # DJ Role
    async def update_guild_dj_role(self, guild_id: int, role_id: Optional[int]):
        await self.guild_settings.update_one(
            {"guild_id": guild_id}, {"$set": {"dj_role_id": role_id}}, upsert=True
        )

    def get_collection(self, collection_name: str):
        """Получить коллекцию по имени"""
        return self.db[collection_name]

    # Методы для работы с громкостью сервера
    async def get_guild_volume(self, guild_id: int) -> int:
        """Получить громкость сервера"""
        guild_id_str = str(guild_id)
        doc = await self.guild_settings.find_one({"guild_id": guild_id_str})
        return doc.get("volume", 100) if doc else 100

    async def set_guild_volume(self, guild_id: int, volume: int) -> None:
        """Установить громкость сервера"""
        guild_id_str = str(guild_id)
        await self.guild_settings.update_one(
            {"guild_id": guild_id_str}, {"$set": {"volume": volume}}, upsert=True
        )

    # Методы для работы с режимом повтора сервера
    async def get_guild_loop_mode(self, guild_id: int) -> str:
        """Получить режим повтора сервера"""
        guild_id_str = str(guild_id)
        doc = await self.guild_settings.find_one({"guild_id": guild_id_str})
        return doc.get("loop_mode", "none") if doc else "none"

    async def set_guild_loop_mode(self, guild_id: int, loop_mode: str) -> None:
        """Установить режим повтора сервера"""
        guild_id_str = str(guild_id)
        await self.guild_settings.update_one(
            {"guild_id": guild_id_str}, {"$set": {"loop_mode": loop_mode}}, upsert=True
        )


# Глобальный экземпляр для использования во всем проекте
mongo_service = MongoService()
