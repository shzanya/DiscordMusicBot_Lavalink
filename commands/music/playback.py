import asyncio
import logging
import re
import traceback
from typing import Dict, List, Optional, Union

import discord
import wavelink
from cachetools import TTLCache
from discord import Interaction, app_commands
from discord.ext import commands
from wavelink import Queue

from config.constants import Colors, Emojis
from core.player import LoopMode, PlayerState
from ui.embeds import (
    cleanup_updater,
    create_error_embed,
    create_now_playing_embed,
    now_playing_updater,
    send_now_playing_message,
)
from utils.formatters import format_duration

logger = logging.getLogger(__name__)

connection_locks: Dict[int, asyncio.Lock] = {}
autocomplete_cache = TTLCache(maxsize=100, ttl=120)

async def track_autocomplete(
    interaction: Interaction,
    current: str
) -> List[app_commands.Choice[str]]:
    query = current.strip().lower()
    if len(query) < 2:
        return []

    if query in autocomplete_cache:
        return autocomplete_cache[query]

    try:
        tracks = []
        sources = [
            wavelink.TrackSource.SoundCloud
        ]
        for source in sources:
            try:
                tracks = await asyncio.wait_for(
                    wavelink.Playable.search(query, source=source),
                    timeout=2.0
                )
                if tracks:
                    break
            except asyncio.TimeoutError:
                logger.warning(f"[Autocomplete Timeout] {source} for query '{query}'")
                continue
            except wavelink.LavalinkException as e:
                logger.warning(f"[Autocomplete {source} Error] {e}")
                continue

        if not tracks:
            return []

        choices = []
        for track in tracks[:5]:
            title = f"{track.author} – {track.title}"
            if len(title) > 100:
                title = title[:97] + "..."
            choices.append(app_commands.Choice(name=title, value=track.uri))

        autocomplete_cache[query] = choices
        return choices

    except Exception as e:
        logger.warning(f"[Autocomplete Error] {type(e).__name__}: {e}")
        return []

class HarmonyPlayer(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous: Optional[wavelink.Playable] = None
        self._current_track: Optional[wavelink.Playable] = None
        self.history: list[wavelink.Playable] = []
        self.max_history_size = 25
        self.view: Optional[discord.ui.View] = None
        self.queue_message: Optional[discord.Message] = None
        self.text_channel: Optional[discord.TextChannel] = None
        self._auto_leave_task: Optional[asyncio.Task] = None
        self._is_destroyed = False
        self.queue = Queue()
        self.history = Queue()
        self.controller_message = None
        self._handling_track_end = False
        self._handling_track_start = False

        # ✅ Правильная инициализация state
        self.state = PlayerState(
            bass_boost=False,
            nightcore=False,
            vaporwave=False,
            loop_mode=LoopMode.NONE,
            autoplay=False,
            volume_before_effects=100
        )
 
    @property
    def is_paused(self) -> bool:
        return getattr(self, 'paused', False)

    @property
    def current_track(self) -> Optional[wavelink.Playable]:
        return self._current_track or super().current

    @property
    def current(self) -> Optional[wavelink.Playable]:
        return self.current_track

    @property
    def is_connected_safely(self) -> bool:
        try:
            return (
                self.guild is not None and 
                self.channel is not None and 
                not self._is_destroyed and
                super().connected
            )
        except Exception:
            return False

    async def set_effects(self, bass: bool = None, nightcore: bool = None, vaporwave: bool = None):
        filters = wavelink.Filters()

        # Обновляем состояние эффектов
        if bass is not None:
            self.state.bass_boost = bass
        if nightcore is not None:
            self.state.nightcore = nightcore
        if vaporwave is not None:
            self.state.vaporwave = vaporwave

        # Бассбуст (настройка частотных полос вручную)
        if self.state.bass_boost:
            filters.equalizer = wavelink.Equalizer.from_levels(
                0.6, 0.7, 0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            )

        # Найткор
        if self.state.nightcore:
            filters.timescale = wavelink.Timescale(speed=1.2, pitch=1.2)

        # Вейпорвейв
        if self.state.vaporwave:
            filters.timescale = wavelink.Timescale(speed=0.8, pitch=0.8)
            filters.equalizer = wavelink.Equalizer.from_levels(
                -0.2, -0.2, -0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
            )

        await self.set_filters(filters)

    async def _start_idle_timer(self, timeout: int = 300):  # 300 секунд = 5 минут
        if self._auto_leave_task:
            self._auto_leave_task.cancel()

        async def idle_disconnect():
            await asyncio.sleep(timeout)
            if not self.current and self.is_connected_safely:
                await self.disconnect()
                logger.info("[Idle Timer] Disconnected from voice channel due to inactivity.")

        self._auto_leave_task = asyncio.create_task(idle_disconnect())

    async def show_queue(self, interaction: discord.Interaction, limit: int = 10) -> None:
        try:
            if self.queue.is_empty:
                embed = discord.Embed(
                    title="📭 Очередь пуста",
                    description="Добавьте треки с помощью /play.",
                    color=Colors.WARNING
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            description_lines = []
            queue_items = list(self.queue)[:limit]
            for i, track in enumerate(queue_items, start=1):
                duration = getattr(track, 'length', 0)
                duration_str = f" [{self._format_duration(duration)}]" if duration else ""
                description_lines.append(
                    f"**{i}.** {track.author} — {track.title}{duration_str}"
                )

            remaining = self.queue.count - limit
            if remaining > 0:
                description_lines.append(f"\n*И ещё **{remaining}** трек(ов)...*")

            embed = discord.Embed(
                title="🎶 Очередь воспроизведения",
                description="\n".join(description_lines),
                color=Colors.PRIMARY
            )
            if self.current:
                embed.add_field(
                    name="🎵 Сейчас играет",
                    value=f"{self.current.author} — {self.current.title}",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error showing queue: {e}")
            await interaction.response.send_message(
                embed=create_error_embed("Ошибка", "Не удалось отобразить очередь"),
                ephemeral=True
            )

    def _format_duration(self, milliseconds: int) -> str:
        if not milliseconds:
            return "00:00"
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    async def play_track(self, track: wavelink.Playable, **kwargs):
        try:
            if self.current:
                self.history.put(self.current)
            await self.play(track, **kwargs)
            if self.controller_message:
                from ui.embeds import create_now_playing_embed
                from ui.views import MusicPlayerView
                embed = create_now_playing_embed(track, self)
                view = MusicPlayerView(self)
                try:
                    await self.controller_message.edit(embed=embed, view=view)
                except discord.NotFound:
                    self.controller_message = None
        except Exception as e:
            logger.error(f"[play_track error] {e}")

    def _add_to_history(self, track: wavelink.Playable) -> None:
        try:
            if track in self.history:
                self.history.remove(track)
            self.history.append(track)
            while len(self.history) > self.max_history_size:
                self.history.pop(0)
        except Exception as e:
            logger.error(f"Error adding track to history: {e}")

    async def do_next(self):
        try:
            if self.state.loop_mode == LoopMode.TRACK and self.current:
                return await self.play_track(self.current)

            if self.state.loop_mode == LoopMode.QUEUE and self.current:
                self.queue.put(self.current)

            if self.queue.is_empty:
                if self.state.autoplay and self.current:
                    recommended = await self._get_autoplay_track()
                    if recommended:
                        return await self.play_track(recommended)

                await self._start_idle_timer()  # 🔧 Добавлен await
                return

            next_track = self.queue.get()
            await self.play_track(next_track)

        except Exception as e:
            logger.error(f"[do_next error] {e}")

    def _schedule_auto_leave(self) -> None:
        async def leave_after_timeout():
            try:
                await asyncio.sleep(300)
                if (not self.playing and not self.paused and 
                    self.queue.is_empty and self.is_connected_safely):
                    logger.info("Auto-disconnecting due to inactivity")
                    await self.cleanup_disconnect()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Auto-disconnect failed: {e}")
        self._auto_leave_task = asyncio.create_task(leave_after_timeout())

    async def skip(self) -> None:
        if self.queue.is_empty:
            await self.stop()
            return
        next_track = self.queue.get()
        await self.play_track(next_track)

    async def play_previous(self) -> bool:
        try:
            if not self.previous or not self.is_connected_safely:
                return False
            current = self._current_track
            success = await self.play_track(self.previous)
            if success:
                self.previous = current
                return True
            return False
        except Exception as e:
            logger.error(f"Play previous failed: {e}")
            return False

    async def cleanup_disconnect(self) -> None:
        try:
            self._is_destroyed = True
            if self._auto_leave_task and not self._auto_leave_task.done():
                self._auto_leave_task.cancel()
                self._auto_leave_task = None
            if self.is_connected_safely:
                await self.disconnect()
        except Exception as e:
            logger.error(f"Cleanup disconnect failed: {e}")

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_unload(self) -> None:
        try:
            cleanup_updater()
            for guild in self.bot.guilds:
                if guild.voice_client and isinstance(guild.voice_client, HarmonyPlayer):
                    await guild.voice_client.cleanup_disconnect()
        except Exception as e:
            logger.error(f"Cog unload error: {e}")

    async def _get_connection_lock(self, guild_id: int) -> asyncio.Lock:
        if guild_id not in connection_locks:
            connection_locks[guild_id] = asyncio.Lock()
        return connection_locks[guild_id]

    async def _search_tracks(self, query: str) -> Optional[Union[list[wavelink.Playable], wavelink.Playlist]]:
        try:
            is_url = bool(re.match(r'^https?://', query, re.IGNORECASE))
            if is_url:
                results = await asyncio.wait_for(
                    wavelink.Playable.search(query),
                    timeout=5.0
                )
                return results if results else None
            else:
                sources = [
                    (wavelink.TrackSource.SoundCloud, "scsearch:")
                ]
                for source, prefix in sources:
                    try:
                        full_query = prefix + query
                        results = await asyncio.wait_for(
                            wavelink.Playable.search(full_query, source=source),
                            timeout=5.0
                        )
                        if results:
                            return results
                    except asyncio.TimeoutError:
                        logger.warning(f"Search timeout for {full_query}")
                        continue
                    except wavelink.LavalinkException as e:
                        logger.warning(f"Search failed for {full_query}: {e}")
                        continue
                return None
        except Exception as e:
            logger.error(f"Search error: {e}")
            return None

    async def _ensure_voice_connection(
        self, 
        interaction: discord.Interaction, 
        voice_channel: discord.VoiceChannel
    ) -> Optional[HarmonyPlayer]:
        guild_id = interaction.guild.id
        lock = await self._get_connection_lock(guild_id)
        async with lock:
            try:
                vc = interaction.guild.voice_client
                if vc and isinstance(vc, HarmonyPlayer) and vc.is_connected_safely:
                    if vc.channel.id != voice_channel.id:
                        await vc.move_to(voice_channel)
                    return vc
                if vc:
                    try:
                        await vc.cleanup_disconnect()
                    except Exception as e:
                        logger.warning(f"Cleanup of old connection failed: {e}")
                vc = await voice_channel.connect(cls=HarmonyPlayer, timeout=10.0)
                vc.text_channel = interaction.channel
                logger.info(f"Connected to voice channel: {voice_channel.name}")
                return vc
            except asyncio.TimeoutError:
                logger.error("Voice connection timeout")
                return None
            except Exception as e:
                logger.error(f"Failed to connect to voice: {e}")
                return None

    @app_commands.command(name="queue", description="📄 Показать текущую очередь треков")
    async def queue(self, interaction: discord.Interaction) -> None:
        try:
            vc = interaction.guild.voice_client
            if not vc or not isinstance(vc, HarmonyPlayer):
                await interaction.response.send_message(
                    embed=create_error_embed("Ошибка", "Бот не подключен к голосовому каналу"),
                    ephemeral=True
                )
                return
            await vc.show_queue(interaction)
        except Exception as e:
            logger.error(f"Queue command error: {e}")
            await interaction.response.send_message(
                embed=create_error_embed("Ошибка", "Не удалось отобразить очередь"),
                ephemeral=True
            )

    @app_commands.command(name="play", description="🎵 Искать и воспроизвести музыку")
    @app_commands.describe(query="Название трека, исполнитель или ссылка")
    @app_commands.autocomplete(query=track_autocomplete)
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        voice_state = getattr(interaction.user, 'voice', None)
        if not voice_state or not voice_state.channel:
            await interaction.response.send_message(
                embed=create_error_embed("Ошибка", "Вы должны находиться в голосовом канале"),
                ephemeral=True
            )
            return
        vc_channel = voice_state.channel
        await interaction.response.defer(ephemeral=True)
        try:
            vc = await self._ensure_voice_connection(interaction, vc_channel)
            if not vc:
                await interaction.followup.send(
                    embed=create_error_embed("Ошибка", "Не удалось подключиться к голосовому каналу"),
                    ephemeral=True
                )
                return
            logger.info(f"Searching for: {query}")
            results = await self._search_tracks(query)
            if not results:
                await interaction.followup.send(
                    embed=create_error_embed("Ошибка", f"Ничего не найдено по запросу: {query}"),
                    ephemeral=True
                )
                return
            if isinstance(results, wavelink.Playlist):
                added_count = 0
                for track in results.tracks:
                    track.requester = interaction.user  # Set requester
                    vc.queue.put(track)
                    added_count += 1
                embed = discord.Embed(
                    title=f"{Emojis.ADD} Плейлист добавлен",
                    description=f"**{results.name}** — {added_count} треков добавлено в очередь",
                    color=Colors.SUCCESS
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                if not vc.playing and not vc.paused:
                    await vc.do_next()
                    if vc.current:
                        try:
                            await send_now_playing_message(
                                interaction.channel, vc.current, vc, interaction.user
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send now playing message: {e}")
            else:
                track = results[0]
                track.requester = interaction.user  # Set requester
                logger.info(f"Found track: {track.title} by {track.author}")
                if vc.playing or vc.paused or vc.current:
                    vc.queue.put(track)
                    queue_position = vc.queue.count
                    embed = discord.Embed(
                        description=(
                            f"**Добавлено в очередь #{queue_position}:**\n"
                            f"{track.author} — {track.title}"
                        ),
                        color=Colors.SUCCESS
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await vc.play_track(track)
                    try:
                        await send_now_playing_message(
                            interaction.channel, vc.current, vc, interaction.user
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send now playing message: {e}")
                    embed = discord.Embed(
                        description=f"**Воспроизводится:** {track.author} — {track.title}",
                        color=Colors.SUCCESS
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Play command failed: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send(
                    embed=create_error_embed("Ошибка", "Произошла непредвиденная ошибка"),
                    ephemeral=True
                )
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        try:
            player: HarmonyPlayer = payload.player
            if not player or not isinstance(player, HarmonyPlayer):
                logger.warning("No valid player in track end event")
                return
            if player._is_destroyed:
                logger.info("Player is destroyed, skipping track end handling")
                return

            logger.info(f"Track ended: {payload.track.title if payload.track else 'Unknown'}")
            logger.debug(f"End reason: {payload.reason}")

            # 🎯 Обновить эмбед для завершенного трека
            if payload.track and hasattr(player, "now_playing_message") and player.now_playing_message:
                track = payload.track
                requester = getattr(track, "requester", None)
                duration = format_duration(track.length)

                artist = getattr(track, 'author', 'Неизвестный исполнитель')
                title = getattr(track, 'title', 'Неизвестный трек')
                uri = getattr(track, 'uri', '')  # Получить URL трека
                thumbnail = getattr(track, 'artwork', None) or getattr(track, 'thumbnail', None)
                requester_name = requester.display_name if requester else 'shane4kaa'

                # Создать эмбед с названием трека как гиперссылкой
                embed = discord.Embed(
                    title=artist,
                    description=f"**[{title}]({uri})**\n\n**> Статус:\n** Прослушано ({duration}) — {requester_name}" if uri else f"**{title}**\n\n**> Статус:\n** Прослушано ({duration}) — {requester_name}",
                    color=0x2B2D31
                )
                if thumbnail:
                    embed.set_thumbnail(url=thumbnail)

                try:
                    logger.info(f"Updating now_playing_message for {title} in guild {player.guild.id}")
                    # Сохранять view, если очередь не пуста, иначе убрать
                    view = player.view if not player.queue.is_empty else None
                    await player.now_playing_message.edit(embed=embed, view=view)
                except Exception as e:
                    logger.warning(f"Could not edit finished track embed: {e}")

            # ▶️ Обработать следующий трек или пустую очередь
            if payload.reason in ("finished", "stopped", "cleanup"):
                if not player.queue.is_empty:
                    next_track = await player.queue.get_wait()
                    await player.play(next_track)
                    return

                # ❌ Очередь пуста — отправить отдельный эмбед
                if player.text_channel:
                    empty_queue_embed = discord.Embed(
                        description="—・Пустая очередь сервера\nЯ покинула канал, потому что в очереди не осталось треков",
                        color=0x2B2D31
                    )
                    try:
                        logger.info(f"Sending empty queue embed in guild {player.guild.id}")
                        await player.text_channel.send(embed=empty_queue_embed)
                    except Exception as e:
                        logger.warning(f"Could not send empty queue embed: {e}")

                logger.info("Queue empty, keeping updated embed")
                await player._start_idle_timer()  # Запустить таймер бездействия

        except Exception as e:
            logger.error(f"Track end handler failed: {e}")
            traceback.print_exc()


    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        if payload.player._handling_track_start:
            return
        payload.player._handling_track_start = True
        try:
            player: HarmonyPlayer = payload.player
            track = payload.track
            if not player or not isinstance(player, HarmonyPlayer) or not track:
                return
            if player._is_destroyed:
                return
            logger.info(f"Track started: {track.title}")
            guild_id = player.guild.id
            if guild_id in now_playing_updater.active_messages:
                info = now_playing_updater.active_messages[guild_id]
                message = info['message']
                requester = info['requester']
                try:
                    embed = create_now_playing_embed(track, player, requester)
                    await message.edit(embed=embed)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                    logger.debug(f"Failed to update now playing message: {e}")
                    now_playing_updater.unregister_message(guild_id)
        except Exception as e:
            logger.error(f"Track start handler failed: {e}")
            traceback.print_exc()
        finally:
            payload.player._handling_track_start = False

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, 
        member: discord.Member, 
        before: discord.VoiceState, 
        after: discord.VoiceState
    ) -> None:
        try:
            if member.id != self.bot.user.id:
                return
            if before.channel and not after.channel:
                guild = before.channel.guild
                vc = guild.voice_client
                if vc and isinstance(vc, HarmonyPlayer):
                    logger.info(f"Bot disconnected from voice in {guild.name}")
                    await vc.cleanup_disconnect()
        except Exception as e:
            logger.error(f"Voice state update handler failed: {e}")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
