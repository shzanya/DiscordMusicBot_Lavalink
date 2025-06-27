import asyncio
import logging
import re
from typing import Dict, List, Optional, Union
import discord
import time
import wavelink
from cachetools import TTLCache
from discord import Interaction, app_commands
from discord.ext import commands

from commands.music.effects import AudioEffectsManager, EffectType
from core.player import LoopMode, PlayerState
from ui.embeds import create_error_embed
from ui.music_embeds import (
    create_connection_error_embed,
    create_empty_queue_embed,
    create_permission_error_embed,
    create_playlist_embed,
    create_queue_embed,
    create_search_error_embed,
    create_track_added_embed,
    create_track_finished_embed,
)
from ui.progress_updater import (
    cleanup_updater,
    now_playing_updater,
    send_now_playing_message,
)
from ui.views import QueueView

logger = logging.getLogger(__name__)

connection_locks: Dict[int, asyncio.Lock] = {}
autocomplete_cache = TTLCache(maxsize=200, ttl=300)
background_cache: dict[str, List[app_commands.Choice[str]]] = {}


async def _autocomplete_internal_logic(query: str) -> List[app_commands.Choice[str]]:
    if not query or len(query.strip()) < 2:
        return []
    
    cache_key = query.lower().strip()
    if cache_key in autocomplete_cache:
        return autocomplete_cache[cache_key]
    
    tracks = []
    sources = [wavelink.TrackSource.SoundCloud]
    
    search_tasks = []
    for source in sources:
        task = asyncio.create_task(
            asyncio.wait_for(
                wavelink.Playable.search(query, source=source),
                timeout=0.8
            )
        )
        search_tasks.append((source, task))
    
    for source, task in search_tasks:
        try:
            result = await task
            if result and len(result) > 0:
                tracks = result
                logger.debug(f"[Autocomplete] Found {len(tracks)} tracks from {source}")
                break
        except asyncio.TimeoutError:
            logger.debug(f"[Autocomplete] Timeout for {source}")
            continue
        except wavelink.LavalinkException as e:
            logger.debug(f"[Autocomplete] {source} error: {e}")
            continue
        except Exception as e:
            logger.debug(f"[Autocomplete] Unexpected error for {source}: {e}")
            continue
    
    for _, task in search_tasks:
        if not task.done():
            task.cancel()
    
    if not tracks:
        autocomplete_cache[cache_key] = []
        return []
    
    choices = []
    for track in tracks[:4]:
        try:
            author = getattr(track, 'author', 'Unknown Artist') or 'Unknown Artist'
            title = getattr(track, 'title', 'Unknown Title') or 'Unknown Title'
            uri = getattr(track, 'uri', '') or getattr(track, 'identifier', '')
            
            if not uri:
                continue
                
            display_name = f"{author} – {title}"
            if len(display_name) > 97:
                display_name = display_name[:94] + "..."
            
            choices.append(app_commands.Choice(name=display_name, value=uri))
            
        except Exception as e:
            logger.debug(f"[Autocomplete] Error processing track: {e}")
            continue
    
    autocomplete_cache[cache_key] = choices
    logger.debug(f"[Autocomplete] Cached {len(choices)} choices for '{query}'")
    
    return choices

async def track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
    try:
        if interaction.response.is_done():
            logger.debug(f"[Autocomplete] Interaction already responded for '{current}'")
            return []
        
        query = current.strip()
        if len(query) < 2:
            return []
        
        if len(query) > 100:
            query = query[:100]
        
        normalized_query = query.lower()
        
        if normalized_query in autocomplete_cache:
            cached_result = autocomplete_cache[normalized_query]
            logger.debug(f"[Autocomplete] Cache hit for '{query}'")
            return cached_result
        
        result = await asyncio.wait_for(
            _autocomplete_internal_logic(normalized_query), 
            timeout=1.2
        )
        
        if interaction.response.is_done():
            logger.debug(f"[Autocomplete] Interaction expired during search for '{current}'")
            return []
        
        logger.debug(f"[Autocomplete] Returning {len(result)} results for '{query}'")
        return result
        
    except asyncio.TimeoutError:
        logger.debug(f"[Autocomplete] Timeout for '{current}'")
        return []
    except asyncio.CancelledError:
        logger.debug(f"[Autocomplete] Cancelled for '{current}'")
        return []
    except (AttributeError, RuntimeError):
        logger.debug(f"[Autocomplete] Interaction error for '{current}'")
        return []
    except Exception as e:
        logger.debug(f"[Autocomplete] Unexpected error for '{current}': {e}")
        return []

async def smart_track_autocomplete(interaction: Interaction, current: str) -> List[app_commands.Choice[str]]:
    try:
        query = current.strip().lower()

        if len(query) < 2:
            return []

        # Защитная проверка
        if not isinstance(background_cache, dict):
            logger.warning("background_cache is not a valid dict")
            return await track_autocomplete(interaction, current)

        for cached_query, cached_results in background_cache.items():
            if not isinstance(cached_query, str):
                continue
            if query in cached_query or cached_query in query:
                logger.debug(f"[Smart Autocomplete] Background cache hit for '{query}'")
                return cached_results[:4]

        return await track_autocomplete(interaction, current)

    except Exception as e:
        logger.debug(f"[Smart Autocomplete] Error: {e}")
        return []

class HarmonyPlayer(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time_real: float = 0.0
        self.speed_override: float = 1.0
        self._last_position: float = 0.0
        self._last_sync: float = 0.0
        self._current_track: Optional[wavelink.Playable] = None
        self.playlist: List[wavelink.Playable] = []
        self.current_index: int = -1
        self.history: List[wavelink.Playable] = []  # Добавляем историю
        self.max_history_size = 100
        self.view: Optional[discord.ui.View] = None
        self.queue_message: Optional[discord.Message] = None
        self.text_channel: Optional[discord.TextChannel] = None
        self._auto_leave_task: Optional[asyncio.Task] = None
        self._is_destroyed = False
        self.controller_message = None
        self._handling_track_end = False
        self._handling_track_start = False
        self.playlist_mode: bool = False
        self.now_playing_message: Optional[discord.Message] = None
        self.state = PlayerState(
            bass_boost=False, nightcore=False, vaporwave=False,
            loop_mode=LoopMode.NONE, autoplay=False, volume_before_effects=100
        )
    
    def is_queue_empty(self) -> bool:
        return len(self.playlist) == 0 or self.current_index >= len(self.playlist)


    def get_position(self) -> float:
        """
        Возвращает скорректированную позицию трека с учётом скорости
        """
        if self.paused or not self.start_time_real:
            return self._last_position

        elapsed_real = time.time() - self.start_time_real
        position = self._last_position + elapsed_real * self.speed_override
        return position

    def sync_playback_timing(self, speed: float = 1.0):
        self.track_speed = speed
        self.start_time_real = time.time()
        self.paused_at = self.position
        self.was_paused = False

    def get_real_position(self) -> float:
        if getattr(self, 'paused', False):
            return self.paused_at
        if not hasattr(self, 'start_time_real'):
            return self.position

        elapsed = time.time() - self.start_time_real
        speed = getattr(self, 'track_speed', 1.0)
        return self.paused_at + (elapsed * speed)

    def set_paused(self, paused: bool):
        self.paused = paused
        if paused:
            self.paused_at = self.get_real_position()
        else:
            self.start_time_real = time.time()

    async def set_effects(self, **kwargs):
        await AudioEffectsManager.set_effects(self, **kwargs)

    async def apply_saved_effects(self):
        active_effects = {
            effect: getattr(self.state, effect.value, False)
            for effect in EffectType
        }
        await self.set_effects(**active_effects)




    async def destroy(self) -> None:
        self._is_destroyed = True
        await super().disconnect()

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        if self._handling_track_start:
            return
        self._handling_track_start = True

        try:
            logger.debug(f"Track start event for player {id(self)} in guild {self.guild.id}")

            track = payload.track
            if not track or self._is_destroyed:
                return

            # 🎛️ Применяем эффекты
            await self.apply_saved_effects()

            # 🕒 Синхронизируем старт
            self._last_position = 0.0
            self.start_time_real = time.time()
            self.speed_override = getattr(self, 'speed_override', 1.0)

            logger.info(f"Track started: {track.title}")

        except Exception as e:
            logger.error(f"Error in on_wavelink_track_start: {e}")
        finally:
            self._handling_track_start = False

    async def play_track(self, track: wavelink.Playable, *, add_to_history=True, clear_forward=True, **kwargs):
            try:
                # Удаляем старый View
                from ui.views import MusicPlayerView
                if self.view and isinstance(self.view, MusicPlayerView):
                    self.view.destroy()

                # Добавляем текущий трек в историю, если нужно
                if add_to_history and self._current_track:
                    track_uri = getattr(self._current_track, 'uri', getattr(self._current_track, 'identifier', ''))
                    if track_uri and track_uri not in {getattr(t, 'uri', getattr(t, 'identifier', '')) for t in self.history}:
                        self.history.append(self._current_track)
                        self.history = self.history[-self.max_history_size:]
                        logger.debug(f"Added to history: {self._current_track.title}")

                # Устанавливаем текущий трек
                self._current_track = track
                track.requester = kwargs.pop("requester", None) or (self.text_channel.guild.me if self.text_channel else None)

                # Сбрасываем таймер
                self._last_position = 0.0
                self.start_time_real = time.time()
                self.speed_override = getattr(self, 'speed_override', 1.0)

                # Запускаем воспроизведение
                await self.play(track, **kwargs)

                # Отправляем now playing сообщение
                if self.text_channel and not self._is_destroyed:
                    try:
                        from ui.views import MusicPlayerView
                        view = MusicPlayerView(self, None, track.requester)
                        self.now_playing_message = await send_now_playing_message(
                            self.text_channel,
                            track,
                            self,
                            requester=track.requester,
                            view=view
                        )
                        logger.info(f"▶️ Sent now playing message for: {track.title} with MusicPlayerView")
                    except Exception as e:
                        logger.error(f"Failed to send now playing message: {e}")
                        # Продолжаем воспроизведение, несмотря на ошибку отправки сообщения

                logger.info(f"Playing: {track.title}")

            except Exception as e:
                logger.error(f"play_track error: {e}")

    async def play_by_index(self, index: int) -> bool:
        if not (0 <= index < len(self.playlist)):
            logger.warning(f"play_by_index: Index {index} out of range")
            return False

        self.current_index = index
        track = self.playlist[index]

        if not hasattr(track, "requester") or not track.requester:
            track.requester = self.text_channel.guild.me if self.text_channel else None

        # Не добавляем в историю — это переход по индексу
        await self.play_track(track, requester=track.requester, add_to_history=False, clear_forward=False)

        logger.info(f"🎯 Playing track at index {index}: {track.title}")
        return True

    async def play_previous(self) -> bool:
            if self.current_index <= 0:
                logger.info("⏮ Невозможно вернуться: на первом треке")
                return False

            old_track = self._current_track
            if old_track and self.now_playing_message and self.text_channel:
                try:
                    embed = create_track_finished_embed(old_track, position=old_track.length)
                    await self.now_playing_message.edit(embed=embed, view=None)
                    logger.info("✅ Обновлен embed завершенного трека (previous)")
                except discord.HTTPException as e:
                    logger.warning(f"Failed to edit finished embed (previous): {e}")

            self.now_playing_message = None
            now_playing_updater.unregister_message(self.guild.id)
            self.current_index -= 1
            return await self.play_by_index(self.current_index)

    async def play_forward(self) -> bool:
        if self.current_index >= len(self.playlist) - 1:
            logger.info("⏭ Конец плейлиста")
            return False
        return await self.play_by_index(self.current_index + 1)

    async def add_track(self, track: wavelink.Playable):
            track_uri = getattr(track, 'uri', getattr(track, 'identifier', ''))
            # Проверяем, нет ли трека уже в плейлисте
            if track_uri not in {getattr(t, 'uri', getattr(t, 'identifier', '')) for t in self.playlist}:
                track.requester = track.requester or (self.text_channel.guild.me if self.text_channel else None)
                self.playlist.append(track)
                logger.info(f"Added track: {track.title}")
                # Добавляем трек в историю при добавлении
                if track_uri and track_uri not in {getattr(t, 'uri', getattr(t, 'identifier', '')) for t in self.history}:
                    self.history.append(track)
                    self.history = self.history[-self.max_history_size:]
                    logger.debug(f"Added to history: {track.title}")
            else:
                logger.info(f"Track already in playlist: {track.title}")

            # Автостарт, если плеер не играет
            if self._current_track is None or self.current_index == -1:
                self.current_index = 0
                await self.play_by_index(0)

    async def load_playlist(self, tracks: list[wavelink.Playable]):
        self.playlist = tracks
        for track in self.playlist:
            track.requester = track.requester or (self.text_channel.guild.me if self.text_channel else None)
        self.current_index = 0
        if tracks:
            await self.play_by_index(self.current_index)


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
                await self.cleanup_disconnect()
                logger.info("[Idle Timer] Disconnected from voice channel due to inactivity.")
        self._auto_leave_task = asyncio.create_task(idle_disconnect())

    async def show_queue(self, interaction: discord.Interaction, page: int = 1):
        try:
            items_per_page = 10
            total_tracks = len(self.playlist)
            total_pages = max((total_tracks - 1) // items_per_page + 1, 1)

            if page > total_pages:
                page = total_pages

            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            visible_queue = self.playlist[start_index:end_index]

            embed = create_queue_embed(
                guild=interaction.guild,
                now_playing=self.current,
                queue=visible_queue,
                page=page,
                total_pages=total_pages,
                user=interaction.user
            )

            view = QueueView(player=self, user=interaction.user, page=page, total_pages=total_pages)
            
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                
        except discord.InteractionResponded:
            logger.warning("Interaction already responded to in show_queue")
        except discord.NotFound:
            logger.warning("Interaction not found (expired) in show_queue")
        except Exception as e:
            logger.error(f"Error in show_queue: {e}")

    async def skip(self) -> None:
            if getattr(self, "_handling_track_end", False):
                logger.debug("⚠️ Skip ignored: track end handling in progress")
                return

            try:
                if not self.playlist or self.current_index >= len(self.playlist) - 1:
                    logger.info("🚫 End of playlist, stopping playback")
                    await self.stop()
                    now_playing_updater.unregister_message(self.guild.id)
                    self.now_playing_message = None
                    self._current_track = None
                    return

                old_track = self._current_track
                if old_track and self.now_playing_message and self.text_channel:
                    try:
                        embed = create_track_finished_embed(old_track, position=old_track.length)
                        await self.now_playing_message.edit(embed=embed, view=None)
                        logger.info("✅ Обновлен embed завершенного трека (skip)")
                    except discord.HTTPException as e:
                        logger.warning(f"Failed to edit finished embed (skip): {e}")

                self.now_playing_message = None
                await self.play_forward()

            except Exception as e:
                logger.error(f"❌ Skip failed: {e}")

    async def do_next(self):
        try:
            # 🛑 Пустая очередь
            if not self.playlist:
                logger.info("📭 Очередь пуста — отключаюсь")
                if self.text_channel:
                    try:
                        from ui.embeds import create_empty_queue_embed
                        await self.text_channel.send(embed=create_empty_queue_embed())
                    except Exception as e:
                        logger.error(f"❌ Не удалось отправить embed пустой очереди: {e}")
                await self.cleanup_disconnect()
                return

            # 🔁 Повтор трека
            if self.state.loop_mode == LoopMode.TRACK and self._current_track:
                await self.play_track(self._current_track, requester=self._current_track.requester)
                return

            # 🔁 Повтор очереди
            if self.state.loop_mode == LoopMode.QUEUE and self._current_track:
                self.current_index = (self.current_index + 1) % len(self.playlist)
                await self.play_by_index(self.current_index)
                return

            # ➕ Автовоспроизведение (если очередь закончилась)
            if self.current_index >= len(self.playlist) - 1:
                if self.state.autoplay and self._current_track:
                    recommended = await self._get_autoplay_track()
                    if recommended:
                        await self.add_track(recommended)
                        await self.play_by_index(self.current_index + 1)
                        return
                await self._start_idle_timer()
                return

            # ▶️ Следующий трек
            await self.play_by_index(self.current_index + 1)

        except Exception as e:
            logger.error(f"❌ do_next error: {e}")

    async def cleanup_disconnect(self) -> None:
        try:
            self._is_destroyed = True
            now_playing_updater.unregister_message(self.guild.id)

            if self._auto_leave_task and not self._auto_leave_task.done():
                self._auto_leave_task.cancel()
                self._auto_leave_task = None

            if super().connected:
                logger.info("Disconnecting from voice channel")
                await self.disconnect()
                logger.info("Successfully disconnected")
            else:
                logger.warning("Player not connected, skipping disconnect")

            self.playlist.clear()
            self.current_index = -1
            self._current_track = None

            if self.now_playing_message:
                try:
                    await self.now_playing_message.delete()
                except discord.HTTPException:
                    pass
                self.now_playing_message = None

        except Exception as e:
            logger.error(f"Cleanup disconnect failed: {e}")

    async def _get_autoplay_track(self) -> Optional[wavelink.Playable]:
        try:
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

    async def _safe_send_response(self, interaction: discord.Interaction, embed: discord.Embed, ephemeral: bool = True):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
            else:
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
        except discord.InteractionResponded:
            logger.warning("Interaction already responded to")
            try:
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            except Exception as e:
                logger.error(f"Failed to send followup: {e}")
        except discord.NotFound:
            logger.warning("Interaction not found (expired)")
        except Exception as e:
            logger.error(f"Error sending response: {e}")

    @app_commands.command(name="queue", description="📄 Показать текущую очередь треков")
    async def queue(self, interaction: discord.Interaction) -> None:
        try:
            vc = interaction.guild.voice_client
            if not vc or not isinstance(vc, HarmonyPlayer):
                await self._safe_send_response(
                    interaction,
                    create_connection_error_embed("Бот не подключен к голосовому каналу"),
                    ephemeral=True
                )
                return
            await vc.show_queue(interaction)
        except Exception as e:
            logger.error(f"Queue command error: {e}")
            await self._safe_send_response(
                interaction,
                create_error_embed("Ошибка", "Не удалось отобразить очередь"),
                ephemeral=True
            )

    @app_commands.command(name="play", description="🎵 Искать и воспроизвести музыку")
    @app_commands.describe(query="Название трека, исполнитель или ссылка")
    @app_commands.autocomplete(query=track_autocomplete)
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        interaction_handled = False
        
        try:
            voice_state = getattr(interaction.user, 'voice', None)
            if not voice_state or not voice_state.channel:
                await interaction.response.send_message(
                    embed=create_permission_error_embed(),
                    ephemeral=True
                )
                interaction_handled = True
                return

            await interaction.response.defer(ephemeral=True)
            interaction_handled = True

            vc_channel = voice_state.channel
            vc = await self._ensure_voice_connection(interaction, vc_channel)
            if not vc:
                await interaction.followup.send(
                    embed=create_connection_error_embed(),
                    ephemeral=True
                )
                return

            logger.info(f"Searching for: {query}")
            results = await self._search_tracks(query)

            if not results:
                await interaction.followup.send(
                    embed=create_search_error_embed(query),
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
                        await vc.add_track(track)
                        added_count += 1
                    except Exception as e:
                        logger.error(f"Failed to add track {track.title} to playlist: {e}")
                        continue

                embed = create_playlist_embed(results.name, added_count)
                await interaction.followup.send(embed=embed, ephemeral=True)

                if not vc.playing and not vc.paused:
                    logger.info("Starting playback for playlist")
                    await vc.load_playlist(results.tracks)

            else:
                track = results[0]
                track.requester = interaction.user
                logger.info(f"Found track: {track.title} by {track.author}")

                await vc.add_track(track)
                if not vc.playing and not vc.paused:
                    embed = create_track_added_embed(track, len(vc.playlist))
                    await interaction.followup.send(embed=embed, ephemeral=True)

        except discord.InteractionResponded:
            logger.warning("Play command: Interaction already responded")
        except discord.NotFound:
            logger.warning("Play command: Interaction not found (expired)")
        except Exception as e:
            logger.error(f"Play command failed: {e}")
            try:
                if not interaction_handled:
                    await interaction.response.send_message(
                        embed=create_error_embed("Ошибка", "Произошла непредвиденная ошибка"),
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        embed=create_error_embed("Ошибка", "Произошла непредвиденная ошибка"),
                        ephemeral=True
                    )
            except (discord.InteractionResponded, discord.NotFound):
                logger.error("Could not send error response - interaction expired or already handled")
            except Exception as send_error:
                logger.error(f"Failed to send error response: {send_error}")

    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
            player: HarmonyPlayer = payload.player

            if not player or getattr(player, "_is_destroyed", False):
                logger.warning("❌ Invalid or destroyed player in track end event")
                return

            if getattr(player, "_handling_track_end", False):
                logger.debug("Track end already handled")
                return

            if payload.reason == "replaced":
                logger.info("🔁 Track replaced manually — skipping handler logic")
                return

            player._handling_track_end = True

            try:
                if player._current_track:
                    track_title = getattr(player._current_track, 'title', 'Unknown Track')
                    logger.info(f"⏹️ Трек завершен: {track_title}")

                    # История уже обновлена в add_track, но проверяем на всякий случай
                    track_uri = getattr(player._current_track, 'uri', getattr(player._current_track, 'identifier', ''))
                    if track_uri and track_uri not in {getattr(t, 'uri', getattr(t, 'identifier', '')) for t in player.history}:
                        player.history.append(player._current_track)
                        player.history = player.history[-player.max_history_size:]
                        logger.debug(f"Added to history: {track_title}")

                    # Отключаем автообновление
                    now_playing_updater.unregister_message(player.guild.id)

                    # Обновляем или отправляем embed "Прослушано"
                    if player.text_channel:
                        embed = create_track_finished_embed(player._current_track, position=payload.track.length)
                        try:
                            if player.now_playing_message:
                                try:
                                    await player.now_playing_message.edit(embed=embed, view=None)
                                    logger.info("✅ Обновлен embed завершенного трека")
                                except discord.HTTPException as e:
                                    logger.warning(f"Не удалось обновить embed: {e}")
                                    await player.text_channel.send(embed=embed)
                                    logger.info("✅ Отправлен новый embed завершенного трека после ошибки")
                            else:
                                await player.text_channel.send(embed=embed)
                                logger.info("✅ Отправлен новый embed завершенного трека")
                        except discord.HTTPException as e:
                            logger.error(f"Не удалось отправить embed: {e}")

                # Очищаем текущее сообщение и трек
                player.now_playing_message = None
                player._current_track = None

                # Проверяем, есть ли следующий трек
                if not player.playlist or player.current_index >= len(player.playlist) - 1:
                    logger.info("🚪 Очередь пуста — отключаюсь")
                    if player.text_channel:
                        try:
                            embed = create_empty_queue_embed()
                            await player.text_channel.send(embed=embed)
                            logger.info("✅ Отправлен embed пустой очереди")
                        except Exception as e:
                            logger.error(f"❌ Ошибка при отправке embed пустой очереди: {e}")
                    await player.cleanup_disconnect()
                    return

                # Переходим к следующему треку
                player.current_index += 1
                await player.play_by_index(player.current_index)

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
