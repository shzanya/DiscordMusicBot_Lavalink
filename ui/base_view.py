"""
🎨 Базовый класс для UI View с системой управления эмодзи
Обеспечивает корректную инициализацию кастомных эмодзи для кнопок Discord UI
"""

import logging
from typing import Optional, Dict
import discord
from discord import ui
from config.constants import get_button_emoji
from services import mongo_service

logger = logging.getLogger(__name__)


class EmojiSettings:
    """Настройки эмодзи для гильдии"""

    def __init__(
        self, color: str = "default", custom_emojis: Optional[Dict[str, str]] = None
    ):
        self.color = color or "default"
        self.custom_emojis = custom_emojis or {}

    @classmethod
    async def from_guild(cls, guild_id: Optional[int]) -> "EmojiSettings":
        """Создание настроек эмодзи из настроек гильдии"""
        if not guild_id:
            logger.debug("No guild_id provided, using default settings")
            return cls()

        try:
            logger.debug(f"Loading emoji settings for guild {guild_id}")
            settings = await mongo_service.get_guild_settings(guild_id) or {}
            logger.debug(f"Loaded settings: {settings}")

            color = settings.get("color", "default")
            custom_emojis = settings.get("custom_emojis", {})

            logger.debug(f"Using color: {color}, custom_emojis: {custom_emojis}")

            return cls(color=color, custom_emojis=custom_emojis)
        except Exception as e:
            logger.warning(f"Failed to load emoji settings for guild {guild_id}: {e}")
            return cls()

    def get_emoji(self, emoji_name: str) -> str:
        """Получение эмодзи с учетом настроек гильдии"""
        return get_button_emoji(emoji_name, self.color, self.custom_emojis)


class BaseEmojiView(ui.View):
    """Базовый класс для View с поддержкой кастомных эмодзи"""

    def __init__(self, emoji_settings: Optional[EmojiSettings] = None, **kwargs):
        super().__init__(**kwargs)
        self._emoji_settings = emoji_settings or EmojiSettings()
        self._emoji_map: Dict[str, str] = {}
        self._initialized = False

    @classmethod
    async def create(
        cls,
        guild_id: Optional[int] = None,
        emoji_settings: Optional[EmojiSettings] = None,
        **kwargs,
    ) -> "BaseEmojiView":
        """Создание View с автоматической загрузкой настроек эмодзи"""
        if not emoji_settings and guild_id:
            emoji_settings = await EmojiSettings.from_guild(guild_id)

        instance = cls(emoji_settings=emoji_settings, **kwargs)
        await instance._initialize_emojis()
        return instance

    async def _initialize_emojis(self):
        """Инициализация эмодзи для всех кнопок"""
        if self._initialized:
            return

        # Определяем маппинг эмодзи для конкретного View
        self._setup_emoji_mapping()

        # Применяем эмодзи к кнопкам
        self._apply_emojis_to_buttons()

        self._initialized = True
        logger.debug(f"Initialized emojis for {self.__class__.__name__}")

    def _setup_emoji_mapping(self):
        """Настройка маппинга эмодзи - переопределяется в наследниках"""
        pass

    def _apply_emojis_to_buttons(self):
        """Применение эмодзи к кнопкам"""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                custom_id = getattr(item, "custom_id", None)
                if custom_id and custom_id in self._emoji_map:
                    emoji_name = self._emoji_map[custom_id]

                    # Специальная обработка для кнопки pause
                    if custom_id == "music:pause" and hasattr(self, "player"):
                        is_paused = getattr(self.player, "paused", False)
                        emoji_name = "NK_MUSICPAUSE" if is_paused else "NK_MUSICPLAY"

                    emoji = self._emoji_settings.get_emoji(emoji_name)

                    # Применяем эмодзи только если он валидный
                    if emoji and emoji != "❓":
                        item.emoji = emoji
                        item.label = None  # Убираем временную метку
                    else:
                        # Если эмодзи недоступен, устанавливаем дефолтную метку
                        item.label = "•"

    def update_emoji(self, custom_id: str, emoji_name: str):
        """Обновление эмодзи для конкретной кнопки"""
        for item in self.children:
            if (
                isinstance(item, discord.ui.Button)
                and getattr(item, "custom_id", None) == custom_id
            ):
                emoji = self._emoji_settings.get_emoji(emoji_name)
                if emoji and emoji != "❓":
                    item.emoji = emoji
                    item.label = None
                else:
                    item.label = "•"
                break

    def get_emoji(self, emoji_name: str) -> str:
        """Получение эмодзи с учетом настроек"""
        return self._emoji_settings.get_emoji(emoji_name)

    @property
    def emoji_settings(self) -> EmojiSettings:
        """Доступ к настройкам эмодзи"""
        return self._emoji_settings


class EmojiButton(ui.Button):
    """Кнопка с поддержкой кастомных эмодзи"""

    def __init__(self, emoji_name: str, emoji_settings: EmojiSettings, **kwargs):
        # Получаем эмодзи сразу при создании
        emoji = emoji_settings.get_emoji(emoji_name)

        # Если эмодзи недоступен, используем временную метку
        if not emoji or emoji == "❓":
            kwargs["label"] = kwargs.get("label", "•")
            kwargs["emoji"] = None
        else:
            kwargs["emoji"] = emoji
            kwargs["label"] = None

        super().__init__(**kwargs)
        self._emoji_name = emoji_name
        self._emoji_settings = emoji_settings

    def update_emoji(self, emoji_name: str):
        """Обновление эмодзи кнопки"""
        emoji = self._emoji_settings.get_emoji(emoji_name)
        if emoji and emoji != "❓":
            self.emoji = emoji
            self.label = None
        else:
            self.emoji = None
            self.label = "•"
