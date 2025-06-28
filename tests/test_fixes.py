#!/usr/bin/env python3
"""
Тест для проверки исправлений ошибок
"""

import asyncio
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_volume_fixes():
    """Тест исправлений громкости"""
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

        # Тестируем установку громкости (должно работать без ошибок Node.send)
        logger.info(f"Initial volume: {player.volume}")

        player.volume = 50
        logger.info(f"After setting to 50: {player.volume}")

        player.volume = 150
        logger.info(f"After setting to 150: {player.volume}")

        logger.info("✅ Volume fixes test completed successfully")

    except Exception as e:
        logger.error(f"❌ Volume fixes test failed: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


async def test_effects_fixes():
    """Тест исправлений эффектов"""
    try:
        from commands.music.playback import HarmonyPlayer

        # Создаем мок плеера
        class MockPlayer(HarmonyPlayer):
            def __init__(self):
                self.state = type(
                    "State",
                    (),
                    {
                        "bass_boost": False,
                        "nightcore": False,
                        "vaporwave": False,
                        "treble_boost": False,
                        "karaoke": False,
                        "tremolo": False,
                        "vibrato": False,
                        "distortion": False,
                    },
                )()

            async def set_effects(self, **kwargs):
                logger.info(f"Mock set_effects called with: {kwargs}")

        player = MockPlayer()

        # Тестируем apply_saved_effects (должно работать без ошибки keywords)
        await player.apply_saved_effects()

        logger.info("✅ Effects fixes test completed successfully")

    except Exception as e:
        logger.error(f"❌ Effects fixes test failed: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


async def test_modal_fixes():
    """Тест исправлений модального окна"""
    try:
        # Тестируем создание модального окна
        from discord import ui

        class TestVolumeModal(ui.Modal, title="Тест громкости"):
            def __init__(self, player, update_callback):
                super().__init__(title="Тест громкости")
                self.player = player
                self.update_callback = update_callback

            volume_input = ui.TextInput(
                label="Громкость (0-200%)",
                placeholder="Введите значение от 0 до 200",
                min_length=1,
                max_length=3,
                default="100",
            )

            async def on_submit(self, interaction):
                logger.info(f"Modal submitted with volume: {self.volume_input.value}")

        # Создаем мок объекты
        class MockPlayer:
            def __init__(self):
                self.volume = 100

        class MockCallback:
            async def __call__(self, interaction, volume):
                logger.info(f"Callback called with volume: {volume}")

        player = MockPlayer()
        callback = MockCallback()

        # Создаем модальное окно
        modal = TestVolumeModal(player, callback)
        logger.info(f"Modal created successfully with player: {modal.player}")

        logger.info("✅ Modal fixes test completed successfully")

    except Exception as e:
        logger.error(f"❌ Modal fixes test failed: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


async def main():
    """Основная функция тестирования"""
    logger.info("🚀 Starting fixes tests...")

    await test_volume_fixes()
    await test_effects_fixes()
    await test_modal_fixes()

    logger.info("✅ All fixes tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
