"""🔧 Утилитарные команды для HarmonyBot"""

from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class UtilityCategory(commands.Cog):
    """🔧 Категория утилитарных команд"""

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(f"{__name__}.UtilityCategory")

    async def cog_load(self):
        """Событие загрузки категории"""
        self.logger.info("🔧 Категория Utility загружена")

    async def cog_unload(self):
        """Событие выгрузки категории"""
        self.logger.info("🔧 Категория Utility выгружена")


async def setup(bot):
    """Настройка категории Utility"""
    await bot.add_cog(UtilityCategory(bot))
    logger.info("🔧 Категория Utility инициализирована")
