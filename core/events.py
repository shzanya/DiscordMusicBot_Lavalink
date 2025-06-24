import discord
from discord.ext import commands
import wavelink
import logging
from config.settings import Settings
from config.constants import Colors

class EventHandler(commands.Cog):
    """🎧 Обработчик событий бота"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('HarmonyBot.EventHandler')

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """🔗 Подключение к Lavalink"""
        self.logger.info(f"🎵 Lavalink узел `{payload.node.identifier}` готов")
        self.logger.info(f"📊 Сессия: {payload.session_id}")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """▶️ Начало воспроизведения трека"""
        player = payload.player
        track = payload.track

        # Отмена таймера бездействия
        if hasattr(player, 'idle_task') and player.idle_task:
            player.idle_task.cancel()
            player.idle_task = None

        self.logger.info(f"▶️ Воспроизведение: {track.title} на сервере {player.guild.name}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """⏹️ Окончание трека"""
        player = payload.player

        if payload.reason == "finished":
            await player.do_next()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """🔊 Обновление голосового состояния"""
        if member == self.bot.user and before.channel and not after.channel:
            # Бот покинул голосовой канал
            player = before.channel.guild.voice_client
            if player and hasattr(player, 'controller_message'):
                player.controller_message = None

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """🎉 Присоединение к серверу"""
        await self.bot.db.create_guild(guild.id, guild.name)
        self.logger.info(f"🎉 Присоединился к серверу: {guild.name} ({guild.id})")

        # Приветственное сообщение
        if guild.system_channel:
            embed = discord.Embed(
                title="🎵 Привет! Я Harmony Bot",
                description=(
                    f"Спасибо за добавление меня на сервер!\n\n"
                    f"🎵 Используйте `{Settings.COMMAND_PREFIX}help` для списка команд\n"
                    f"▶️ Используйте `{Settings.COMMAND_PREFIX}play` для начала воспроизведения музыки"
                ),
                color=Colors.PRIMARY
            )
            try:
                await guild.system_channel.send(embed=embed)
            except discord.Forbidden:
                self.logger.warning(f"⛔ Нет прав на отправку сообщений в {guild.system_channel.name}")
