import asyncio
import logging
import re
from typing import Dict, List, Optional, Union

import discord
import wavelink
from cachetools import TTLCache
from discord import Interaction, app_commands
from discord.ext import commands
from wavelink import Queue

from commands.music.effects import AudioEffectsManager, EffectType
from config.constants import Colors
from core.player import LoopMode, PlayerState
from ui.embeds import (
    cleanup_updater,
    create_error_embed,
    create_queue_embed,
)
from ui.views import QueueView

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
        self._current_track: Optional[wavelink.Playable] = None
        self.history: list[wavelink.Playable] = []
        self.forward_stack: list[wavelink.Playable] = []
        self.max_history_size = 100
        self.view: Optional[discord.ui.View] = None
        self.queue_message: Optional[discord.Message] = None
        self.text_channel: Optional[discord.TextChannel] = None
        self._auto_leave_task: Optional[asyncio.Task] = None
        self._update_task: Optional[asyncio.Task] = None
        self._is_destroyed = False
        self.queue = Queue()
        self.controller_message = None
        self._handling_track_end = False
        self._handling_track_start = False
        self._handling_track_start = False
        self.playlist_mode: bool = False
        self.now_playing_message: Optional[discord.Message] = None
        self.state = PlayerState(
            bass_boost=False, nightcore=False, vaporwave=False,
            loop_mode=LoopMode.NONE, autoplay=False, volume_before_effects=100
        )
    def is_queue_empty(self) -> bool:
        return len(self.queue) == 0
    

    async def destroy(self) -> None:
        self._is_destroyed = True
        await super().disconnect()

    async def _update_progress_bar(self):
        """Periodically update now_playing_message with progress bar."""
        while self.is_connected_safely and self._current_track and not self._is_destroyed:
            try:
                if self.now_playing_message:
                    requester = getattr(self._current_track, "requester", None)
                    from ui.embed_now_playing import create_now_playing_embed
                    embed = await create_now_playing_embed(self._current_track, self, requester)
                    await self.now_playing_message.edit(embed=embed, view=self.view)
            except discord.HTTPException as e:
                logger.error(f"Failed to update progress bar: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error in update_progress_bar: {e}")
                break
            await asyncio.sleep(5)  # Update every 5 seconds
 

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        if self._handling_track_start:
            return
        self._handling_track_start = True
        try:
            logger.debug(f"Track start event for player {id(self)} in guild {self.guild.id}")
            await self.apply_saved_effects()
            track = payload.track
            if not track or self._is_destroyed:
                return
            logger.info(f"Track started: {track.title}")
        except Exception as e:
            logger.error(f"Error in on_wavelink_track_start: {e}")
        finally:
            self._handling_track_start = False

    async def _update_now_playing_message(self, track: wavelink.Playable, requester=None):
        for attempt in range(3):
            try:
                from ui.embed_now_playing import create_now_playing_embed
                from ui.views import MusicPlayerView
                embed = await create_now_playing_embed(track, self, requester)

                # Create new view and ensure its message is set
                view = MusicPlayerView(self, self.now_playing_message, requester)
                if self.now_playing_message:
                    await self.now_playing_message.edit(embed=embed, view=view)
                    view.message = self.now_playing_message  # Ensure view.message is updated
                    self.view = view
                    logger.debug("Updated existing now_playing_message")
                else:
                    self.now_playing_message = await self.text_channel.send(embed=embed, view=view)
                    view.message = self.now_playing_message  # Set view.message for new message
                    self.view = view
                    logger.info("Created new now_playing_message")
                return
            except discord.HTTPException as e:
                if e.status == 429 and attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    logger.warning(f"Rate limit hit on attempt {attempt + 1}, retrying after {2 ** attempt}s")
                    continue
                logger.error(f"Failed to update now_playing_message: {e}")
                break


    async def play_track(self, track: wavelink.Playable, add_to_history: bool = True, **kwargs):
        try:
            if add_to_history and self._current_track:
                self.history.append(self._current_track)
                self.history = self.history[-self.max_history_size:]
                logger.debug(f"Added to history: {self._current_track.title}")

            self.forward_stack.clear()
            self._current_track = track

            requester = kwargs.pop("requester", None)
            if requester:
                track.requester = requester

            await self.play(track, **kwargs)
            await self._update_now_playing_message(track, requester)

            if self._update_task:
                self._update_task.cancel()
            self._update_task = asyncio.create_task(self._update_progress_bar())

            logger.info(f"Playing: {track.title}")

        except Exception as e:
            logger.error(f"play_track error: {e}")



    async def apply_saved_effects(self):
            active_effects = {effect: getattr(self.state, effect.value, False) for effect in EffectType}
            await AudioEffectsManager.apply_effects(self, active_effects)

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

    async def _start_idle_timer(self, timeout: int = 300):
            if self._auto_leave_task:
                self._auto_leave_task.cancel()
            async def idle_disconnect():
                await asyncio.sleep(timeout)
                if not self.current and self.is_connected_safely:
                    await self.disconnect()
                    logger.info("[Idle Timer] Disconnected from voice channel due to inactivity.")
            self._auto_leave_task = asyncio.create_task(idle_disconnect())

    async def show_queue(self, interaction: discord.Interaction, page: int = 1):
        items_per_page = 10
        total_tracks = len(self.queue)
        total_pages = max((total_tracks - 1) // items_per_page + 1, 1)

        if page > total_pages:
            page = total_pages

        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        visible_queue = list(self.queue)[start_index:end_index]  # ⬅️ Обрезка очереди

        embed = create_queue_embed(
            guild=interaction.guild,
            now_playing=self.current,
            queue=visible_queue,  # ⬅️ Используем только текущую страницу
            page=page,
            total_pages=total_pages,
            user=interaction.user
        )

        view = QueueView(player=self, user=interaction.user, page=page, total_pages=total_pages)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    def _format_duration(self, milliseconds: int) -> str:
        if not milliseconds:
            return "00:00"
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    async def play_next(self) -> bool:
        try:
            if not self.forward_stack or not self.is_connected_safely:
                logger.debug("No forward stack or not connected")
                return False
            if self._current_track:
                self.history.append(self._current_track)
                self.history = self.history[-self.max_history_size:]
            next_track = self.forward_stack.pop()
            await self.play_track(next_track, requester=getattr(next_track, "requester", None))
            logger.info(f"Playing next: {next_track.title}")
            return True
        except Exception as e:
            logger.error(f"play_next failed: {e}")
            return False

    async def skip(self) -> None:
        if getattr(self, "_handling_track_end", False):
            logger.debug("⚠️ Skip ignored: track end handling in progress")
            return

        try:
            if self.queue.is_empty:
                logger.info("🚫 Queue empty, stopping playback")
                await self.stop()
                return

            if self._current_track:
                self.history.append(self._current_track)
                self.history = self.history[-self.max_history_size:]

            self.forward_stack.clear()
            next_track = self.queue.get()
            self._current_track = next_track

            logger.info(f"⏭️ Skipping to: {next_track.title}")
            await self.play_track(next_track, replace=True, requester=getattr(next_track, 'requester', None))

        except Exception as e:
            logger.error(f"❌ Skip failed: {e}")


    async def do_next(self):
            try:
                if self.state.loop_mode == LoopMode.TRACK and self._current_track:
                    return await self.play_track(self._current_track, requester=self._current_track.requester)
                if self.state.loop_mode == LoopMode.QUEUE and self._current_track:
                    self.queue.put(self._current_track)
                if self.queue.is_empty:
                    if self.state.autoplay and self._current_track:
                        recommended = await self._get_autoplay_track()
                        if recommended:
                            return await self.play_track(recommended, requester=self._current_track.requester)
                    await self._start_idle_timer()
                    return
                if self._current_track:
                    self.history.append(self._current_track)
                    self.history = self.history[-self.max_history_size:]
                    logger.debug(f"Added to history: {self._current_track.title}")
                self.forward_stack.clear()
                next_track = self.queue.get()
                self._current_track = next_track
                await self.play_track(next_track, requester=next_track.requester)
            except Exception as e:
                logger.error(f"do_next error: {e}")

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

    async def play_previous(self) -> bool:
        try:
            logger.debug(f"play_previous called for player {id(self)} in guild {self.guild.id}")

            if not self.history or not self.is_connected_safely:
                logger.debug("No history or not connected")
                return False

            # Сохраняем текущий трек в forward_stack
            if self._current_track:
                self.forward_stack.append(self._current_track)

            previous_track = self.history.pop()
            self._current_track = previous_track
            self._handling_track_end = True

            await self.play_track(previous_track, requester=getattr(previous_track, "requester", None), add_to_history=False)

            logger.info(f"Playing previous: {previous_track.title}")
            return True

        except Exception as e:
            logger.error(f"play_previous failed: {e}")
            return False

        finally:
            self._handling_track_end = False




    async def play_forward(self) -> bool:
        try:
            logger.debug(f"play_forward called for player {id(self)} in guild {self.guild.id}")

            if not self.forward_stack or not self.is_connected_safely:
                logger.debug("No forward stack or not connected")
                return False

            # Сохраняем текущий трек в history
            if self._current_track:
                self.history.append(self._current_track)
                self.history = self.history[-self.max_history_size:]

            next_track = self.forward_stack.pop()
            self._current_track = next_track
            self._handling_track_end = True

            await self.play_track(next_track, requester=getattr(next_track, "requester", None), add_to_history=False)

            logger.info(f"Playing forward: {next_track.title}")
            return True

        except Exception as e:
            logger.error(f"play_forward failed: {e}")
            return False

        finally:
            self._handling_track_end = False

    async def set_effects(self, **kwargs):
            try:
                filters = wavelink.Filters()
                if kwargs.get('bass', False):
                    eq_bands = [
                        {"band": 0, "gain": 0.6}, {"band": 1, "gain": 0.7},
                        {"band": 2, "gain": 0.8}, {"band": 3, "gain": 0.4},
                        {"band": 4, "gain": 0.0}
                    ]
                    filters.equalizer.set(bands=eq_bands)
                if kwargs.get('treble', False):
                    eq_bands = [
                        {"band": 10, "gain": 0.5}, {"band": 11, "gain": 0.6},
                        {"band": 12, "gain": 0.7}, {"band": 13, "gain": 0.8},
                        {"band": 14, "gain": 0.6}
                    ]
                    filters.equalizer.set(bands=eq_bands)
                if kwargs.get('nightcore', False):
                    filters.timescale.set(speed=1.2, pitch=1.2, rate=1.0)
                if kwargs.get('vaporwave', False):
                    filters.timescale.set(speed=0.8, pitch=0.8, rate=1.0)
                    eq_bands = [
                        {"band": 0, "gain": -0.2}, {"band": 1, "gain": -0.2},
                        {"band": 2, "gain": -0.1}
                    ]
                    filters.equalizer.set(bands=eq_bands)
                if kwargs.get('karaoke', False):
                    filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
                if kwargs.get('tremolo', False):
                    filters.tremolo.set(frequency=2.0, depth=0.5)
                if kwargs.get('vibrato', False):
                    filters.vibrato.set(frequency=2.0, depth=0.5)
                if kwargs.get('distortion', False):
                    filters.distortion.set(
                        sin_offset=0.0, sin_scale=1.0, cos_offset=0.0, cos_scale=1.0,
                        tan_offset=0.0, tan_scale=1.0, offset=0.0, scale=1.2
                    )
                await self.set_filters(filters)
                logger.info(f"🎚️ Applied effects: {[k for k, v in kwargs.items() if v]}")
            except Exception as e:
                logger.error(f"❌ Failed to set effects: {e}")
                raise

    async def cleanup_disconnect(self) -> None:
        try:
            self._is_destroyed = True

            if self._auto_leave_task and not self._auto_leave_task.done():
                self._auto_leave_task.cancel()
                self._auto_leave_task = None

            if self._update_task and not self._update_task.done():
                self._update_task.cancel()
                self._update_task = None

            if super().connected:
                logger.info("Disconnecting from voice channel")
                await self.disconnect()
                logger.info("Successfully disconnected")
            else:
                logger.warning("Player not connected, skipping disconnect")

            self.history.clear()
            self.forward_stack.clear()
            self._current_track = None

            if self.now_playing_message:
                try:
                    await self.now_playing_message.delete()
                except discord.HTTPException:
                    pass
                self.now_playing_message = None

            # УДАЛЕНО: await super().destroy()

        except Exception as e:
            logger.error(f"Cleanup disconnect failed: {e}")

    # Add the missing _get_autoplay_track method
    async def _get_autoplay_track(self) -> Optional[wavelink.Playable]:
        """Get a recommended track for autoplay (placeholder implementation)"""
        try:
            # This is a placeholder - you'll need to implement your autoplay logic
            # For example, you could use the current track to find similar tracks
            return None
        except Exception as e:
            logger.error(f"Error getting autoplay track: {e}")
            return None

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
                results = await asyncio.wait_for(wavelink.Playable.search(query), timeout=5.0)
                return results if results else None
            else:
                sources = [(wavelink.TrackSource.SoundCloud, "scsearch:")]
                for source, prefix in sources:
                    try:
                        full_query = prefix + query
                        results = await asyncio.wait_for(wavelink.Playable.search(full_query, source=source), timeout=5.0)
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

    async def _ensure_voice_connection(self, interaction: discord.Interaction, voice_channel: discord.VoiceChannel) -> Optional[HarmonyPlayer]:
        guild_id = interaction.guild.id
        lock = await self._get_connection_lock(guild_id)
        async with lock:
            try:
                vc = interaction.guild.voice_client
                if vc and isinstance(vc, HarmonyPlayer):
                    logger.debug(f"Existing player found for guild {guild_id}, connected: {vc.is_connected_safely}")
                    if vc.is_connected_safely and vc.channel.id == voice_channel.id:
                        return vc
                    await vc.cleanup_disconnect()
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
                vc.playlist_mode = True
                added_count = 0
                logger.info(f"Processing playlist: {results.name}, track count: {len(results.tracks)}")
                for track in results.tracks:
                    try:
                        track.requester = interaction.user
                        vc.queue.put(track)
                        added_count += 1
                        logger.debug(f"Added track to queue: {track.author} - {track.title}")
                    except Exception as e:
                        logger.error(f"Failed to add track {track.title} to queue: {e}")
                        continue
                logger.info(f"Added {added_count} tracks to queue from playlist: {results.name}")
                embed = discord.Embed(
                    description=f'Добавлен плейлист "**{results.name}**" ({added_count} треков)',
                    color=Colors.SUCCESS
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                if not vc.playing and not vc.paused:
                    logger.info("Starting playback for playlist")
                    await vc.do_next()
            else:
                track = results[0]
                track.requester = interaction.user
                logger.info(f"Found track: {track.title} by {track.author}")
                if vc.playing or vc.paused or vc.current:
                    vc.queue.put(track)
                    queue_position = vc.queue.count
                    embed = discord.Embed(
                        description=f"Добавлено в очередь #{queue_position}: {track.author} — {track.title}",
                        color=Colors.SUCCESS
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await vc.play_track(track, requester=interaction.user)
                    embed = discord.Embed(
                        description=f"Воспроизводится: {track.author} — {track.title}",
                        color=Colors.SUCCESS
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Play command failed: {e}")
            try:
                await interaction.followup.send(
                    embed=create_error_embed("Ошибка", "Произошла непредвиденная ошибка"),
                    ephemeral=True
                )
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        player: HarmonyPlayer = payload.player

        if not player or getattr(player, "_is_destroyed", False):
            logger.warning("❌ Invalid or destroyed player in track end event")
            return

        if getattr(player, "_handling_track_end", False):
            logger.debug("Track end already handled")
            return

        player._handling_track_end = True

        try:
            if payload.reason == "replaced":
                logger.info("🔁 Track replaced manually (e.g., skip) — no action needed")
                return

            logger.info(f"⏹️ Track ended: {payload.track.title if payload.track else 'Unknown'}")

            # Обновляем историю треков
            if payload.track and player._current_track:
                track_uri = getattr(payload.track, 'uri', getattr(payload.track, 'identifier', ''))
                if track_uri not in {getattr(t, 'uri', getattr(t, 'identifier', '')) for t in player.history}:
                    player.history.append(payload.track)
                    player.history = player.history[-player.max_history_size:]

            # Отправляем embed об окончании трека (если нужно)
            if payload.track and player.now_playing_message:
                try:
                    await player.now_playing_message.edit(embed=discord.Embed(
                        description=f"**> Статус:** Прослушано — {getattr(payload.track, 'title', 'Без названия')}",
                        color=0x242429,
                        timestamp=discord.utils.utcnow()
                    ), view=None)
                    logger.info("✅ Updated now playing message")
                except discord.HTTPException as e:
                    logger.warning(f"Failed to update now playing message: {e}")

            # Обработка очереди
            if player.queue.is_empty:
                logger.info("🚪 Queue is empty. Disconnecting.")
                if player.text_channel:
                    try:
                        await player.text_channel.send(embed=discord.Embed(
                            description="—・Пустая очередь сервера\nЯ покинула канал, потому что в очереди не осталось треков",
                            color=0x242429,
                            timestamp=discord.utils.utcnow()
                        ))
                    except Exception as e:
                        logger.error(f"❌ Failed to send empty queue message: {e}")
                await player.cleanup_disconnect()
            else:
                await player.do_next()

        except Exception as e:
            logger.error(f"❌ Track end handler failed: {e}")
        finally:
            player._handling_track_end = False


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
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
