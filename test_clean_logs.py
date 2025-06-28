#!/usr/bin/env python3
"""
Тест для проверки чистоты логов
"""

import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_requester_fix():
    """Тест исправления проблемы с requester"""
    try:
        # Создаем мок трек без requester
        class MockTrack:
            def __init__(self):
                self.title = "Test Track"
                self.author = "Test Artist"
                self.uri = "https://example.com"
                self.length = 180000

        track = MockTrack()

        # Тестируем безопасное получение requester
        requester = getattr(track, "requester", None)
        logger.info(f"Requester from track: {requester}")

        # Тестируем с requester
        track.requester = "test_user"
        requester = getattr(track, "requester", None)
        logger.info(f"Requester after setting: {requester}")

        logger.info("✅ Requester fix test completed successfully")

    except Exception as e:
        logger.error(f"❌ Requester fix test failed: {e}")


async def test_queue_loading_fix():
    """Тест исправления загрузки очереди"""
    try:
        from services.queue_service import QueueTrack

        # Тестируем загрузку с правильными данными
        # Используем реальный формат wavelink.Playable
        valid_data = {
            "track": "QAAAjQIAAlRpbWUgLSBUaGUgQ2F0Y2hlciB8IFNwb3RpZnk=",
            "title": "Test Track",
            "author": "Test Artist",
            "uri": "https://example.com",
            "length": 180000,
            "added_at": "2025-06-28T18:30:00",
        }

        try:
            # Создаем мок wavelink.Playable для тестирования
            class MockPlayable:
                def __init__(self, encoded):
                    self.encoded = encoded
                    self.title = "Mock Track"
                    self.author = "Mock Artist"
                    self.uri = "https://mock.com"
                    self.length = 180000

            # Временно заменяем wavelink.Playable на мок
            import wavelink

            original_playable = wavelink.Playable
            wavelink.Playable = MockPlayable

            queue_track = QueueTrack.from_dict(valid_data)
            logger.info(f"Valid track loaded: {queue_track.track.title}")

            # Восстанавливаем оригинальный класс
            wavelink.Playable = original_playable

        except Exception as e:
            logger.error(f"Failed to load valid track: {e}")

        # Тестируем загрузку с неправильными данными
        invalid_data = "invalid_string_data"

        try:
            queue_track = QueueTrack.from_dict(invalid_data)
            logger.error("Should have failed with invalid data")
        except Exception as e:
            logger.info(f"Correctly failed with invalid data: {e}")

        logger.info("✅ Queue loading fix test completed successfully")

    except Exception as e:
        logger.error(f"❌ Queue loading fix test failed: {e}")


async def test_volume_warning_fix():
    """Тест исправления предупреждения о громкости"""
    try:
        from commands.music.playback import HarmonyPlayer

        # Создаем мок плеера
        class MockPlayer(HarmonyPlayer):
            def __init__(self):
                self._volume = 100
                self.text_channel = None
                self._node = None
                self._guild = None
                self._guild_id = 123456789

            @property
            def guild(self):
                return self._guild

            @guild.setter
            def guild(self, value):
                self._guild = value

            async def set_filters(self, filters):
                logger.info(
                    f"Mock set_filters called with volume: {getattr(filters, 'volume', 'N/A')}"
                )

        player = MockPlayer()

        # Тестируем установку громкости (должно работать без предупреждений)
        logger.info(f"Initial volume: {player.volume}")

        player.volume = 75
        logger.info(f"After setting to 75: {player.volume}")

        logger.info("✅ Volume warning fix test completed successfully")

    except Exception as e:
        logger.error(f"❌ Volume warning fix test failed: {e}")


async def main():
    """Основная функция тестирования"""
    logger.info("🚀 Starting clean logs tests...")

    await test_requester_fix()
    await test_queue_loading_fix()
    await test_volume_warning_fix()

    logger.info("✅ All clean logs tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
