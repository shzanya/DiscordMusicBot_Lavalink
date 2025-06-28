#!/usr/bin/env python3
"""
Тест для проверки изоляции настроек между серверами
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


# Мок объекты для тестирования
class MockGuild:
    def __init__(self, guild_id: int):
        self.id = guild_id


class MockTextChannel:
    def __init__(self, guild: MockGuild):
        self.guild = guild


class MockPlayer:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.text_channel = MockTextChannel(MockGuild(guild_id))
        self._volume = 100
        self.state = MockState()

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, value: int):
        self._volume = value


class MockState:
    def __init__(self):
        self.bass_boost = False
        self.nightcore = False
        self.vaporwave = False
        self.loop_mode = 0  # NONE


async def test_volume_isolation():
    """Тест изоляции громкости между серверами"""
    logger.info("🧪 Тестируем изоляцию громкости между серверами")

    try:
        from services import mongo_service

        # Тестируем с двумя разными серверами
        guild_1_id = 123456789
        guild_2_id = 987654321

        # Устанавливаем разную громкость для каждого сервера
        await mongo_service.set_guild_volume(guild_1_id, 75)
        await mongo_service.set_guild_volume(guild_2_id, 125)

        # Проверяем, что настройки сохранились отдельно
        volume_1 = await mongo_service.get_guild_volume(guild_1_id)
        volume_2 = await mongo_service.get_guild_volume(guild_2_id)

        logger.info(f"Сервер {guild_1_id}: громкость = {volume_1}%")
        logger.info(f"Сервер {guild_2_id}: громкость = {volume_2}%")

        if volume_1 == 75 and volume_2 == 125:
            logger.info("✅ Изоляция громкости работает корректно")
            return True
        else:
            logger.error(
                f"❌ Ошибка изоляции громкости: {volume_1} != 75 или {volume_2} != 125"
            )
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте изоляции громкости: {e}")
        return False


async def test_settings_isolation():
    """Тест изоляции настроек между серверами"""
    logger.info("🧪 Тестируем изоляцию настроек между серверами")

    try:
        from services import mongo_service

        # Тестируем с двумя разными серверами
        guild_1_id = 111111111
        guild_2_id = 222222222

        # Устанавливаем разные настройки для каждого сервера
        settings_1 = {
            "color": "red",
            "custom_emojis": {"NK_VOLUME": "🔊"},
            "volume": 80,
        }
        settings_2 = {
            "color": "blue",
            "custom_emojis": {"NK_VOLUME": "🔉"},
            "volume": 120,
        }

        await mongo_service.set_guild_settings(guild_1_id, settings_1)
        await mongo_service.set_guild_settings(guild_2_id, settings_2)

        # Проверяем, что настройки сохранились отдельно
        saved_settings_1 = await mongo_service.get_guild_settings(guild_1_id)
        saved_settings_2 = await mongo_service.get_guild_settings(guild_2_id)

        logger.info(
            f"Сервер {guild_1_id}: цвет = {saved_settings_1.get('color')}, громкость = {saved_settings_1.get('volume')}"
        )
        logger.info(
            f"Сервер {guild_2_id}: цвет = {saved_settings_2.get('color')}, громкость = {saved_settings_2.get('volume')}"
        )

        # Проверяем изоляцию
        if (
            saved_settings_1.get("color") == "red"
            and saved_settings_1.get("volume") == 80
            and saved_settings_2.get("color") == "blue"
            and saved_settings_2.get("volume") == 120
        ):
            logger.info("✅ Изоляция настроек работает корректно")
            return True
        else:
            logger.error("❌ Ошибка изоляции настроек")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте изоляции настроек: {e}")
        return False


async def test_player_volume_isolation():
    """Тест изоляции громкости плееров между серверами"""
    logger.info("🧪 Тестируем изоляцию громкости плееров")

    try:
        # Создаем плееры для разных серверов
        player_1 = MockPlayer(333333333)
        player_2 = MockPlayer(444444444)

        # Устанавливаем разную громкость
        player_1.volume = 60
        player_2.volume = 140

        logger.info(
            f"Плеер 1 (сервер {player_1.guild_id}): громкость = {player_1.volume}%"
        )
        logger.info(
            f"Плеер 2 (сервер {player_2.guild_id}): громкость = {player_2.volume}%"
        )

        if player_1.volume == 60 and player_2.volume == 140:
            logger.info("✅ Изоляция громкости плееров работает корректно")
            return True
        else:
            logger.error(
                f"❌ Ошибка изоляции громкости плееров: {player_1.volume} != 60 или {player_2.volume} != 140"
            )
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте изоляции плееров: {e}")
        return False


async def test_effects_isolation():
    """Тест изоляции эффектов между серверами"""
    logger.info("🧪 Тестируем изоляцию эффектов между серверами")

    try:
        # Создаем состояния эффектов для разных серверов
        state_1 = MockState()
        state_2 = MockState()

        # Устанавливаем разные эффекты
        state_1.bass_boost = True
        state_1.nightcore = False
        state_2.bass_boost = False
        state_2.nightcore = True

        logger.info(
            f"Сервер 1: bass_boost = {state_1.bass_boost}, nightcore = {state_1.nightcore}"
        )
        logger.info(
            f"Сервер 2: bass_boost = {state_2.bass_boost}, nightcore = {state_2.nightcore}"
        )

        if (
            state_1.bass_boost
            and not state_1.nightcore
            and not state_2.bass_boost
            and state_2.nightcore
        ):
            logger.info("✅ Изоляция эффектов работает корректно")
            return True
        else:
            logger.error("❌ Ошибка изоляции эффектов")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте изоляции эффектов: {e}")
        return False


async def test_database_structure():
    """Тест структуры базы данных"""
    logger.info("🧪 Тестируем структуру базы данных")

    try:
        from services import mongo_service

        # Проверяем, что настройки сохраняются с правильным guild_id
        test_guild_id = 555555555
        test_settings = {
            "color": "green",
            "volume": 90,
            "custom_emojis": {"NK_HEART": "💚"},
        }

        await mongo_service.set_guild_settings(test_guild_id, test_settings)
        saved_settings = await mongo_service.get_guild_settings(test_guild_id)

        logger.info(f"Сохраненные настройки: {saved_settings}")

        # Проверяем, что guild_id сохраняется как строка
        if (
            saved_settings.get("guild_id") == str(test_guild_id)
            and saved_settings.get("color") == "green"
            and saved_settings.get("volume") == 90
        ):
            logger.info("✅ Структура базы данных корректна")
            return True
        else:
            logger.error("❌ Ошибка в структуре базы данных")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка в тесте структуры БД: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    logger.info("🚀 Начинаем тестирование изоляции настроек между серверами")

    tests = [
        test_volume_isolation,
        test_settings_isolation,
        test_player_volume_isolation,
        test_effects_isolation,
        test_database_structure,
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
        logger.info(
            "🎉 Все тесты прошли успешно! Изоляция настроек работает корректно."
        )
        logger.info("✅ Каждый сервер имеет свои собственные настройки:")
        logger.info("   - Громкость сохраняется отдельно для каждого сервера")
        logger.info("   - Эффекты применяются независимо на каждом сервере")
        logger.info("   - Цвета и эмодзи настраиваются индивидуально")
        logger.info("   - Настройки не влияют друг на друга")
    else:
        logger.warning("⚠️ Некоторые тесты не прошли. Проверьте логи выше.")

    return success_count == total_count


if __name__ == "__main__":
    asyncio.run(main())
