#!/usr/bin/env python3
"""
Тестовый файл для проверки системы владельца плеера
"""

import asyncio
from utils.validators import is_player_owner


class MockPlayer:
    """Мок плеера для тестирования"""

    def __init__(self):
        self.current = None
        self.playlist = []
        self.view = None


class MockTrack:
    """Мок трека для тестирования"""

    def __init__(self, requester_id):
        self.requester = MockUser(requester_id)
        self.title = "Test Track"
        self.uri = "test://track"


class MockUser:
    """Мок пользователя для тестирования"""

    def __init__(self, user_id):
        self.id = user_id
        self.display_name = f"User {user_id}"


class MockInteraction:
    """Мок взаимодействия для тестирования"""

    def __init__(self, user_id):
        self.user = MockUser(user_id)
        self.response = MockResponse()


class MockResponse:
    """Мок ответа для тестирования"""

    def __init__(self):
        self.done = False

    def is_done(self):
        return self.done


async def test_ownership_system():
    """Тестирует систему владельца плеера"""
    print("🧪 Тестирование системы владельца плеера...")

    # Создаем тестовые данные
    owner_id = 123456789
    other_user_id = 987654321

    player = MockPlayer()
    owner = MockUser(owner_id)
    other_user = MockUser(other_user_id)

    # Тест 1: Плеер без треков
    print("\n📋 Тест 1: Плеер без треков")
    result = is_player_owner(player, owner)
    print(f"Владелец без треков: {result} (ожидается: False)")

    # Тест 2: Плеер с треком от владельца
    print("\n📋 Тест 2: Плеер с треком от владельца")
    track = MockTrack(owner_id)
    player.current = track
    result = is_player_owner(player, owner)
    print(f"Владелец с треком: {result} (ожидается: True)")

    # Тест 3: Другой пользователь с треком от владельца
    print("\n📋 Тест 3: Другой пользователь с треком от владельца")
    result = is_player_owner(player, other_user)
    print(f"Другой пользователь: {result} (ожидается: False)")

    # Тест 4: Плеер с плейлистом от владельца
    print("\n📋 Тест 4: Плеер с плейлистом от владельца")
    player.current = None
    player.playlist = [MockTrack(owner_id)]
    result = is_player_owner(player, owner)
    print(f"Владелец с плейлистом: {result} (ожидается: True)")

    # Тест 5: Другой пользователь с плейлистом от владельца
    print("\n📋 Тест 5: Другой пользователь с плейлистом от владельца")
    result = is_player_owner(player, other_user)
    print(f"Другой пользователь с плейлистом: {result} (ожидается: False)")

    print("\n✅ Тестирование завершено!")


if __name__ == "__main__":
    asyncio.run(test_ownership_system())
