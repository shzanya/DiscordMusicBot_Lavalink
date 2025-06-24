"""📝 Команды плейлистов для HarmonyBot"""

from discord.ext import commands
import logging

logger = logging.getLogger(__name__)

class PlaylistCategory(commands.Cog):
    """📝 Категория команд плейлистов"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(f'{__name__}.PlaylistCategory')
    
    async def cog_load(self):
        """Событие загрузки категории"""
        self.logger.info("📝 Категория Playlist загружена")
    
    async def cog_unload(self):
        """Событие выгрузки категории"""
        self.logger.info("📝 Категория Playlist выгружена")

async def setup(bot):
    """Настройка категории Playlist"""
    await bot.add_cog(PlaylistCategory(bot))
    logger.info("📝 Категория Playlist инициализирована")
