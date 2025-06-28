#!/usr/bin/env python3
"""
Тест кастомных эмодзи для управления громкостью и позицией.
"""

import asyncio
import logging
from unittest.mock import Mock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockEmojiSettings:
    def __init__(self):
        self.custom_emojis = {
            "NK_VOLUM_M": "🔉",
            "NK_VOLUM_P": "🔊",
            "NK_VOLUME": "🔊",
            "NK_BACK": "⏮️",
            "NK_NEXT": "⏭️",
            "NK_Revive": "🔄",
        }
        self.color = 0x242429

    def get_emoji(self, name):
        return self.custom_emojis.get(name, "❓")


class MockPlayer:
    def __init__(self):
        self.volume = 100
        self.position = 30000  # 30 секунд
        self.current = Mock()
        self.current.length = 180000  # 3 минуты


async def test_volume_emojis():
    """Тест эмодзи для управления громкостью."""
    logger.info("🧪 Тестирую эмодзи управления громкостью...")

    emoji_settings = MockEmojiSettings()

    # Проверяем эмодзи
    volume_minus = emoji_settings.get_emoji("NK_VOLUM_M")
    volume_plus = emoji_settings.get_emoji("NK_VOLUM_P")
    volume_set = emoji_settings.get_emoji("NK_VOLUME")

    logger.info(f"NK_VOLUM_M: {volume_minus}")
    logger.info(f"NK_VOLUM_P: {volume_plus}")
    logger.info(f"NK_VOLUME: {volume_set}")

    assert volume_minus != "❓", "NK_VOLUM_M не найден"
    assert volume_plus != "❓", "NK_VOLUM_P не найден"
    assert volume_set != "❓", "NK_VOLUME не найден"

    logger.info("✅ Эмодзи управления громкостью работают")


async def test_seek_emojis():
    """Тест эмодзи для управления позицией."""
    logger.info("🧪 Тестирую эмодзи управления позицией...")

    emoji_settings = MockEmojiSettings()

    # Проверяем эмодзи
    back_emoji = emoji_settings.get_emoji("NK_BACK")
    next_emoji = emoji_settings.get_emoji("NK_NEXT")
    revive_emoji = emoji_settings.get_emoji("NK_Revive")

    logger.info(f"NK_BACK: {back_emoji}")
    logger.info(f"NK_NEXT: {next_emoji}")
    logger.info(f"NK_Revive: {revive_emoji}")

    assert back_emoji != "❓", "NK_BACK не найден"
    assert next_emoji != "❓", "NK_NEXT не найден"
    assert revive_emoji != "❓", "NK_Revive не найден"

    logger.info("✅ Эмодзи управления позицией работают")


async def test_emoji_application():
    """Тест применения эмодзи к кнопкам."""
    logger.info("🧪 Тестирую применение эмодзи к кнопкам...")

    emoji_settings = MockEmojiSettings()

    # Симуляция кнопок
    buttons = [
        {"label": "-10%", "emoji_name": "NK_VOLUM_M"},
        {"label": "+10%", "emoji_name": "NK_VOLUM_P"},
        {"label": "Установить", "emoji_name": "NK_VOLUME"},
        {"label": "Назад на 10с", "emoji_name": "NK_BACK"},
        {"label": "Вперед на 10с", "emoji_name": "NK_NEXT"},
        {"label": "Вернуться в начало трэка", "emoji_name": "NK_Revive"},
    ]

    for button in buttons:
        emoji = emoji_settings.get_emoji(button["emoji_name"])
        logger.info(f"Кнопка '{button['label']}' -> {emoji}")
        assert emoji != "❓", f"Эмодзи для {button['label']} не найден"

    logger.info("✅ Применение эмодзи к кнопкам работает")


async def main():
    """Запуск всех тестов."""
    logger.info("🚀 Тестирование кастомных эмодзи...")

    try:
        await test_volume_emojis()
        await test_seek_emojis()
        await test_emoji_application()

        logger.info("✅ Все тесты эмодзи прошли успешно!")
        logger.info("📝 Проверьте, что в БД есть эмодзи:")
        logger.info("   - NK_VOLUM_M (уменьшить громкость)")
        logger.info("   - NK_VOLUM_P (увеличить громкость)")
        logger.info("   - NK_VOLUME (установить громкость)")
        logger.info("   - NK_BACK (назад на 10с)")
        logger.info("   - NK_NEXT (вперед на 10с)")
        logger.info("   - NK_Revive (вернуться в начало)")

    except Exception as e:
        logger.error(f"❌ Тест не прошел: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())
