import discord
from discord.ext import commands
import wavelink
import logging
from config.constants import Colors


class EventHandler(commands.Cog):
    """🎧 Обработчик событий бота"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("HarmonyBot.EventHandler")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        """🔗 Подключение к Lavalink"""
        self.logger.info(f"🎵 Lavalink узел `{payload.node.identifier}` готов")
        self.logger.info(f"📊 Сессия: {payload.session_id}")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """▶️ Начало воспроизведения трека"""
        try:
            player = payload.player
            track = payload.track

            if not player or not player.guild or not track:
                return

            # Отмена таймера бездействия
            if hasattr(player, "idle_task") and player.idle_task:
                player.idle_task.cancel()
                player.idle_task = None

            self.logger.info(
                f"▶️ Воспроизведение: {track.title} на сервере {player.guild.name}"
            )

        except Exception as e:
            self.logger.error(f"❌ Ошибка в on_track_start: {e}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """⏹️ Окончание трека"""
        try:
            player = payload.player

            if not player or not player.guild:
                return

            self.logger.info(f"⏹️ Трек завершен: {payload.reason}")

            # НЕ вызываем do_next здесь, это делается в playback.py
            # Это предотвращает двойной вызов и конфликты

        except Exception as e:
            self.logger.error(f"❌ Ошибка в on_track_end: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """🔊 Обновление голосового состояния"""
        try:
            if member == self.bot.user and before.channel and not after.channel:
                # Бот покинул голосовой канал
                if before.channel.guild.voice_client:
                    player = before.channel.guild.voice_client
                    if hasattr(player, "controller_message"):
                        player.controller_message = None
                    # Очищаем очередь при отключении
                    if hasattr(player, "queue"):
                        player.queue.clear()

        except Exception as e:
            self.logger.error(f"❌ Ошибка в voice_state_update: {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """🎉 Присоединение к серверу"""
        try:
            # Только если есть функция создания гильдии в БД
            if hasattr(self.bot, "db") and hasattr(self.bot.db, "create_guild"):
                await self.bot.db.create_guild(guild.id, guild.name)

            self.logger.info(f"🎉 Присоединился к серверу: {guild.name} ({guild.id})")

            # Приветственное сообщение
            if guild.system_channel:
                embed = discord.Embed(
                    title="🎵 Привет! Я Harmony Bot",
                    description=(
                        "Спасибо за добавление меня на сервер!\n\n"
                        "🎵 Используйте `/play` для воспроизведения музыки\n"
                        "📋 Используйте `/queue` для просмотра очереди"
                    ),
                    color=Colors.PRIMARY,
                )
                try:
                    await guild.system_channel.send(embed=embed)
                except discord.Forbidden:
                    self.logger.warning(
                        f"⛔ Нет прав на отправку сообщений в {guild.system_channel.name}"
                    )

        except Exception as e:
            self.logger.error(f"❌ Ошибка при присоединении к серверу: {e}")

    @commands.Cog.listener()
    async def on_wavelink_track_exception(
        self, payload: wavelink.TrackExceptionEventPayload
    ):
        """🚫 Обработка ошибок воспроизведения"""
        try:
            player = payload.player
            track = payload.track
            exception = payload.exception

            self.logger.error(f"🚫 Ошибка воспроизведения {track.title}: {exception}")

            if player and player.guild:
                # Пытаемся перейти к следующему треку при ошибке
                if hasattr(player, "do_next"):
                    await player.do_next()

        except Exception as e:
            self.logger.error(f"❌ Ошибка в track_exception: {e}")

    @commands.Cog.listener()
    async def on_wavelink_player_update(
        self, payload: wavelink.PlayerUpdateEventPayload
    ):
        """📊 Обновление состояния плеера"""
        # Этот listener может помочь с отладкой, но не обязателен
        pass
