"""🎵 Музыкальные команды для HarmonyBot"""

from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class MusicCategory(commands.Cog):
    """🎵 Категория музыкальных команд"""

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(f"{__name__}.MusicCategory")

    async def cog_load(self):
        """Событие загрузки категории"""
        self.logger.info("🎵 Категория Music загружена")

    async def cog_unload(self):
        """Событие выгрузки категории"""
        self.logger.info("🎵 Категория Music выгружена")


async def setup(bot):
    """Настройка категории Music"""
    await bot.add_cog(MusicCategory(bot))
    logger.info("🎵 Категория Music инициализирована")
