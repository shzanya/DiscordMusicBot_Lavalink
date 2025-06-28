#!/usr/bin/env python3
"""
Тест для проверки исправлений кнопок и обработки ошибок
"""

import asyncio
import logging
import sys
import os

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


# Создаем мок объекты для тестирования
class MockInteraction:
    def __init__(self, user_id=123456789):
        self.user = MockUser(user_id)
        self.response = MockResponse()
        self.followup = MockFollowup()
        self.message = None
        self.guild = MockGuild()

    async def response(self):
        return self.response

    async def followup(self):
        return self.followup


class MockUser:
    def __init__(self, user_id):
        self.id = user_id
        self.mention = f"<@{user_id}>"


class MockResponse:
    def __init__(self):
        self.is_done = False

    async def send_message(self, content=None, embed=None, view=None, ephemeral=True):
        logger.info(f"Mock response: {content}")
        self.is_done = True

    async def defer(self, ephemeral=True):
        logger.info("Mock defer")
        self.is_done = True

    async def edit_message(self, embed=None, view=None):
        logger.info("Mock edit_message")


class MockFollowup:
    async def send(self, content=None, embed=None, view=None, ephemeral=True):
        logger.info(f"Mock followup: {content}")


class MockGuild:
    def __init__(self):
        self.id = 987654321


class MockPlayer:
    def __init__(self):
        self.playlist = []
        self.current_index = -1
        self.current = None
        self.paused = False
        self.volume = 100
        self.text_channel = MockTextChannel()
        self.now_playing_message = None
        self._handling_track_end = False
        self.state = MockState()

    async def play_previous(self):
        logger.info("Mock play_previous")
        return True

    async def skip(self):
        logger.info("Mock skip")

    async def pause(self, paused):
        logger.info(f"Mock pause: {paused}")
        self.paused = paused

    async def cleanup_disconnect(self):
        logger.info("Mock cleanup_disconnect")


class MockState:
    def __init__(self):
        self.loop_mode = 0  # NONE


class MockTextChannel:
    def __init__(self):
        self.guild = MockGuild()


class MockTrack:
    def __init__(self, title="Test Track", author="Test Artist"):
        self.title = title
        self.author = author
        self.length = 180000  # 3 minutes
        self.uri = "test://track/123"


async def test_track_select_update():
    """Тест метода update в TrackSelect"""
    logger.info("🧪 Тестируем TrackSelect.update()")

    try:
        from ui.track_select import TrackSelect

        player = MockPlayer()
        player.history = [MockTrack("Track 1"), MockTrack("Track 2")]

        track_select = TrackSelect(player)

        # Тестируем метод update
        await track_select.update()

        logger.info("✅ TrackSelect.update() работает корректно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка в TrackSelect.update(): {e}")
        return False


async def test_view_error_handling():
    """Тест обработки ошибок в views"""
    logger.info("🧪 Тестируем обработку ошибок в views")

    try:
        from ui.views import MusicPlayerView
        from ui.base_view import EmojiSettings

        player = MockPlayer()
        interaction = MockInteraction()

        # Создаем настройки эмодзи
        emoji_settings = EmojiSettings()

        # Создаем view
        view = MusicPlayerView(player=player, emoji_settings=emoji_settings)

        # Тестируем обработку ошибок
        error = Exception("Test error")
        await view.on_error(interaction, error, view.children[0])

        logger.info("✅ Обработка ошибок в views работает корректно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка в обработке ошибок views: {e}")
        return False


async def test_button_callbacks():
    """Тест callback функций кнопок"""
    logger.info("🧪 Тестируем callback функции кнопок")

    try:
        from ui.views import MusicPlayerView
        from ui.base_view import EmojiSettings

        player = MockPlayer()
        player.playlist = [MockTrack("Track 1"), MockTrack("Track 2")]
        player.current = MockTrack("Current Track")
        player.current_index = 0

        interaction = MockInteraction()

        # Создаем настройки эмодзи
        emoji_settings = EmojiSettings()

        # Создаем view
        view = MusicPlayerView(player=player, emoji_settings=emoji_settings)

        # Тестируем различные callback функции
        test_results = []

        # Тест shuffle
        try:
            await view.shuffle_button_callback(interaction)
            test_results.append("✅ shuffle_button_callback")
        except Exception as e:
            test_results.append(f"❌ shuffle_button_callback: {e}")

        # Тест previous
        try:
            await view.previous_button_callback(interaction)
            test_results.append("✅ previous_button_callback")
        except Exception as e:
            test_results.append(f"❌ previous_button_callback: {e}")

        # Тест skip
        try:
            await view.skip_button_callback(interaction)
            test_results.append("✅ skip_button_callback")
        except Exception as e:
            test_results.append(f"❌ skip_button_callback: {e}")

        # Тест loop
        try:
            await view.loop_button_callback(interaction)
            test_results.append("✅ loop_button_callback")
        except Exception as e:
            test_results.append(f"❌ loop_button_callback: {e}")

        # Тест pause
        try:
            await view.pause_button_callback(interaction)
            test_results.append("✅ pause_button_callback")
        except Exception as e:
            test_results.append(f"❌ pause_button_callback: {e}")

        # Тест stop
        try:
            await view.stop_button_callback(interaction)
            test_results.append("✅ stop_button_callback")
        except Exception as e:
            test_results.append(f"❌ stop_button_callback: {e}")

        for result in test_results:
            logger.info(result)

        success_count = sum(1 for r in test_results if r.startswith("✅"))
        total_count = len(test_results)

        logger.info(
            f"📊 Результат: {success_count}/{total_count} тестов прошли успешно"
        )
        return success_count == total_count

    except Exception as e:
        logger.error(f"❌ Ошибка в тестировании callback функций: {e}")
        return False


async def test_safe_defer_or_respond():
    """Тест безопасного ответа на взаимодействия"""
    logger.info("🧪 Тестируем _safe_defer_or_respond")

    try:
        from ui.views import MusicPlayerView
        from ui.base_view import EmojiSettings

        player = MockPlayer()
        interaction = MockInteraction()

        # Создаем настройки эмодзи
        emoji_settings = EmojiSettings()

        # Создаем view
        view = MusicPlayerView(player=player, emoji_settings=emoji_settings)

        # Тестируем с сообщением
        await view._safe_defer_or_respond(interaction, "Test message")

        # Тестируем без сообщения (defer)
        interaction.response.is_done = False
        await view._safe_defer_or_respond(interaction)

        logger.info("✅ _safe_defer_or_respond работает корректно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка в _safe_defer_or_respond: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    logger.info("🚀 Начинаем тестирование исправлений")

    tests = [
        test_track_select_update,
        test_view_error_handling,
        test_button_callbacks,
        test_safe_defer_or_respond,
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            logger.error(f"❌ Ошибка в тесте {test.__name__}: {e}")
            results.append(False)

    success_count = sum(results)
    total_count = len(results)

    logger.info(
        f"\n📊 ИТОГОВЫЙ РЕЗУЛЬТАТ: {success_count}/{total_count} тестов прошли успешно"
    )

    if success_count == total_count:
        logger.info("🎉 Все тесты прошли успешно! Исправления работают корректно.")
    else:
        logger.warning("⚠️ Некоторые тесты не прошли. Проверьте логи выше.")

    return success_count == total_count


if __name__ == "__main__":
    asyncio.run(main())
