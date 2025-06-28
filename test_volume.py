#!/usr/bin/env python3
"""
Тест для проверки работы громкости
"""

import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_volume_setter():
    """Тест установки громкости"""
    try:
        from commands.music.playback import HarmonyPlayer
        
        # Создаем мок плеера для тестирования
        class MockPlayer(HarmonyPlayer):
            def __init__(self):
                self._volume = 100
                self.text_channel = None
                self.guild = None
                self._node = None
            
            async def set_filters(self, filters):
                logger.info(f"Mock set_filters called with volume: {getattr(filters, 'volume', 'N/A')}")
        
        player = MockPlayer()
        
        # Тестируем установку громкости
        logger.info(f"Initial volume: {player.volume}")
        
        player.volume = 50
        logger.info(f"After setting to 50: {player.volume}")
        
        player.volume = 150
        logger.info(f"After setting to 150: {player.volume}")
        
        player.volume = 0
        logger.info(f"After setting to 0: {player.volume}")
        
        player.volume = 250  # Должно быть ограничено до 200
        logger.info(f"After setting to 250 (should be 200): {player.volume}")
        
        logger.info("✅ Volume setter test completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Volume setter test failed: {e}")

async def test_mongo_service():
    """Тест MongoDB сервиса"""
    try:
        from services import mongo_service
        
        # Тестируем функции громкости
        test_guild_id = 123456789
        
        # Тест установки громкости
        success = await mongo_service.set_guild_volume(test_guild_id, 75)
        logger.info(f"Set volume result: {success}")
        
        # Тест получения громкости
        volume = await mongo_service.get_guild_volume(test_guild_id)
        logger.info(f"Retrieved volume: {volume}")
        
        logger.info("✅ MongoDB service test completed successfully")
        
    except Exception as e:
        logger.error(f"❌ MongoDB service test failed: {e}")

async def main():
    """Основная функция тестирования"""
    logger.info("🚀 Starting volume tests...")
    
    await test_volume_setter()
    await test_mongo_service()
    
    logger.info("✅ All tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 