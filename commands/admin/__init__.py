"""⚙️ Административные команды для HarmonyBot"""

from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class AdminCategory(commands.Cog):
    """⚙️ Категория административных команд"""

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(f"{__name__}.AdminCategory")

    async def cog_load(self):
        """Событие загрузки категории"""
        self.logger.info("⚙️ Категория Admin загружена")

    async def cog_unload(self):
        """Событие выгрузки категории"""
        self.logger.info("⚙️ Категория Admin выгружена")


async def setup(bot):
    """Настройка категории Admin"""
    await bot.add_cog(AdminCategory(bot))
    logger.info("⚙️ Категория Admin инициализирована")
