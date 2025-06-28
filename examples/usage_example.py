"""
Пример использования новой архитектуры Music Bot.
Демонстрирует основные возможности и паттерны.
"""

import discord
from discord.ext import commands

from core.events import TrackStartEvent, TrackEndEvent
from commands.music.queue_command import QueueCommand
from commands.music.loop_command import LoopCommand
from utils.autocomplete import autocomplete_manager


class ExampleBot(commands.Bot):
    """Пример бота с новой архитектурой."""

    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

        # Инициализация обработчиков событий
        self.track_start_event = TrackStartEvent(self)
        self.track_end_event = TrackEndEvent(self)

        # Инициализация команд
        self.queue_command = QueueCommand(self)
        self.loop_command = LoopCommand(self)

    async def setup_hook(self):
        """Настройка бота при запуске."""
        # Загрузка когов
        await self.load_extension("commands.music.playback")

        # Настройка автокомплита
        await autocomplete_manager.clear_cache()

    async def on_wavelink_track_start(self, payload):
        """Обработка события начала трека."""
        await self.track_start_event.handle(payload)

    async def on_wavelink_track_end(self, payload):
        """Обработка события окончания трека."""
        await self.track_end_event.handle(payload)


# Пример использования команд
async def example_usage():
    """Пример использования команд."""

    # Создание бота
    bot = ExampleBot()

    # Пример обработки команды queue
    async def handle_queue_command(interaction):
        await bot.queue_command.execute(interaction)

    # Пример обработки команды loop
    async def handle_loop_command(interaction, mode="track"):
        await bot.loop_command.execute(interaction, mode)

    # Пример автокомплита
    async def handle_autocomplete(interaction, current):
        return await autocomplete_manager.track_autocomplete(interaction, current)


# Пример создания новой команды
class CustomCommand:
    """Пример создания новой команды по новой архитектуре."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def execute(self, interaction: discord.Interaction) -> None:
        """Выполнение команды."""
        try:
            # Проверка условий
            if not interaction.user.voice:
                await interaction.response.send_message(
                    "❌ Вы должны быть в голосовом канале!", ephemeral=True
                )
                return

            # Получение плеера
            vc = interaction.guild.voice_client
            if not vc:
                await interaction.response.send_message(
                    "❌ Бот не подключен!", ephemeral=True
                )
                return

            # Логика команды
            await interaction.response.send_message(
                "✅ Команда выполнена!", ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)


# Пример создания нового события
class CustomEvent:
    """Пример создания нового события по новой архитектуре."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle(self, payload) -> None:
        """Обработка события."""
        try:
            # Логика обработки события
            print(f"Custom event handled: {payload}")

        except Exception as e:
            print(f"Error handling custom event: {e}")


# Пример интеграции
class IntegratedBot(commands.Bot):
    """Бот с интегрированными компонентами."""

    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

        # Компоненты
        self.events = {
            "track_start": TrackStartEvent(self),
            "track_end": TrackEndEvent(self),
            "custom": CustomEvent(self),
        }

        self.commands = {
            "queue": QueueCommand(self),
            "loop": LoopCommand(self),
            "custom": CustomCommand(self),
        }

    async def handle_event(self, event_name: str, payload):
        """Обработка события по имени."""
        if event_name in self.events:
            await self.events[event_name].handle(payload)

    async def handle_command(self, command_name: str, interaction, **kwargs):
        """Обработка команды по имени."""
        if command_name in self.commands:
            await self.commands[command_name].execute(interaction, **kwargs)


if __name__ == "__main__":
    # Пример запуска
    bot = IntegratedBot()

    # Регистрация обработчиков событий
    @bot.event
    async def on_wavelink_track_start(payload):
        await bot.handle_event("track_start", payload)

    @bot.event
    async def on_wavelink_track_end(payload):
        await bot.handle_event("track_end", payload)

    # Запуск бота
    # bot.run("YOUR_TOKEN")
