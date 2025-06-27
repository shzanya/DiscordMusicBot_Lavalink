import asyncio
import logging
import re
from typing import Dict, List, Optional, Union
import discord
import time
import wavelink
from discord import app_commands
from discord.ext import commands

from commands.music.effects import AudioEffectsManager, EffectType
from core.player import LoopMode, PlayerState
from ui.embeds import create_error_embed
from ui.music_embeds import (
    create_connection_error_embed,
    create_empty_queue_embed,
    create_permission_error_embed,
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
from services import mongo_service

logger = logging.getLogger(__name__)

# Глобальные переменные с типизацией
connection_locks: Dict[int, asyncio.Lock] = {}
_autocomplete_cache = {}
_cache_lock = asyncio.Lock()

async def track_autocomplete(interaction, current: str) -> list[app_commands.Choice[str]]:
    query = (current or "").strip()
    if len(query) < 2:
        return []
    
    query = query[:50]
    
    async with _cache_lock:
        if query in _autocomplete_cache:
            cached_time, cached_choices = _autocomplete_cache[query]
            if time.time() - cached_time < 30:
                return cached_choices
    
    try:
        results = await asyncio.wait_for(
            wavelink.Playable.search(query, source=wavelink.TrackSource.SoundCloud),
            timeout=0.5
        )
        
        if not results:
            return []
        
        choices = []
        for track in results[:15]:
            try:
                title = getattr(track, 'title', 'Unknown') or 'Unknown'
                author = getattr(track, 'author', 'Unknown') or 'Unknown'
                uri = getattr(track, 'uri', '') or getattr(track, 'identifier', '')
                
                if not uri:
                    continue
                
                display = f"{author} – {title}"
                if len(display) > 97:
                    display = display[:94] + "..."
                
                choices.append(app_commands.Choice(name=display, value=uri))
            except Exception:
                continue
        
        async with _cache_lock:
            _autocomplete_cache[query] = (time.time(), choices)
            if len(_autocomplete_cache) > 100:
                oldest_key = min(_autocomplete_cache.keys(),
                                 key=lambda k: _autocomplete_cache[k][0])
                del _autocomplete_cache[oldest_key]
        
        return choices
    
    except (asyncio.TimeoutError, Exception):
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
        self._history: List[wavelink.Playable] = []  # Приватная история
        self.max_history_size: int = 100
        self.view: Optional[discord.ui.View] = None
        self.queue_message: Optional[discord.Message] = None
        self.text_channel: Optional[discord.TextChannel] = None
        self._auto_leave_task: Optional[asyncio.Task] = None
        self._is_destroyed: bool = False
        self.controller_message = None
        self._handling_track_end: bool = False
        self._handling_track_start: bool = False
        self.playlist_mode: bool = False
        self.now_playing_message: Optional[discord.Message] = None
        self.state = PlayerState(
            bass_boost=False, nightcore=False, vaporwave=False,
            loop_mode=LoopMode.NONE, autoplay=False, volume_before_effects=100
        )
    
    @property
    def history(self) -> List[wavelink.Playable]:
        return self._history

    def is_queue_empty(self) -> bool:
        return len(self.playlist) == 0 or self.current_index >= len(self.playlist)

    def get_position(self) -> float:
        if self.paused or not self.start_time_real:
            return self._last_position
        elapsed_real = time.time() - self.start_time_real
        position = self._last_position + elapsed_real * self.speed_override
        return position

    def sync_playback_timing(self, speed: float = 1.0) -> None:
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

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        if paused:
            self.paused_at = self.get_real_position()
        else:
            self.start_time_real = time.time()

    async def set_effects(self, **kwargs) -> None:
        await AudioEffectsManager.set_effects(self, **kwargs)

    async def apply_saved_effects(self) -> None:
        active_effects = {
            effect: getattr(self.state, effect.value, False)
            for effect in EffectType
        }
        await self.set_effects(**active_effects)

    async def destroy(self) -> None:
        self._is_destroyed = True
        await super().disconnect()

    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        if self._handling_track_start:
            return
        self._handling_track_start = True
        try:
            logger.debug(f"Track start event for player {id(self)} in guild {self.guild.id}")
            track = payload.track
            if not track or self._is_destroyed:
                return
            await self.apply_saved_effects()
            self._last_position = 0.0
            self.start_time_real = time.time()
            self.speed_override = getattr(self, 'speed_override', 1.0)
            logger.info(f"Track started: {track.title}")
        except Exception as e:
            logger.error(f"Error in on_wavelink_track_start: {e}")
        finally:
            self._handling_track_start = False

    async def play_track(self, track: wavelink.Playable, *, add_to_history: bool = True, clear_forward: bool = True, **kwargs) -> None:
        try:
            from ui.views import MusicPlayerView
            if self.view and isinstance(self.view, MusicPlayerView):
                self.view.destroy()
            if add_to_history and self._current_track:
                self._add_to_history(self._current_track)
            self._current_track = track
            track.requester = kwargs.pop("requester", None) or (self.text_channel.guild.me if self.text_channel else None)
            self._last_position = 0.0
            self.start_time_real = time.time()
            self.speed_override = getattr(self, 'speed_override', 1.0)
            logger.info(f"play_track starting for: {track.title}")
            await self.play(track, **kwargs)
            logger.info(f"play_track finished for: {track.title}")
            if self.text_channel and not self._is_destroyed:
                try:
                    # Получаем настройки гильдии
                    guild_id = self.text_channel.guild.id if self.text_channel and self.text_channel.guild else None
                    settings = await mongo_service.get_guild_settings(guild_id) if guild_id else {}
                    color = settings.get("color", "default")
                    custom_emojis = settings.get("custom_emojis", None)
                    view = await MusicPlayerView.create(
                        self, None, track.requester,
                        color=color, custom_emojis=custom_emojis
                    )
                    self.now_playing_message = await send_now_playing_message(
                        self.text_channel,
                        track,
                        self,
                        requester=track.requester,
                        view=view,
                        color=color,
                        custom_emojis=custom_emojis
                    )
                    logger.info(f"▶️ Sent now playing message for: {track.title} with MusicPlayerView")
                except Exception as e:
                    import traceback
                    logger.error(f"Failed to send now playing message: {e}\n{traceback.format_exc()}")
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
        await self.play_track(track, requester=track.requester, add_to_history=False, clear_forward=False)
        logger.info(f"🎯 Playing track at index {index}: {track.title}")
        return True

    async def play_previous(self) -> bool:
        if self.current_index <= 0:
            logger.info("⏮ Невозможно вернуться: на первом треке")
            return False
        old_track = self._current_track
        await self._finalize_track_message(old_track)
        self.now_playing_message = None
        now_playing_updater.unregister_message(self.guild.id)
        self.current_index -= 1
        return await self.play_by_index(self.current_index)

    async def play_forward(self) -> bool:
        if self.current_index >= len(self.playlist) - 1:
            logger.info("⏭ Конец плейлиста")
            return False
        return await self.play_by_index(self.current_index + 1)

    async def add_track(self, track: wavelink.Playable) -> bool:
        track_uri = getattr(track, 'uri', getattr(track, 'identifier', ''))
        if track_uri not in {getattr(t, 'uri', getattr(t, 'identifier', '')) for t in self.playlist}:
            track.requester = track.requester or (self.text_channel.guild.me if self.text_channel else None)
            self.playlist.append(track)
            logger.info(f"Added track: {track.title}")
        else:
            logger.info(f"Track already in playlist: {track.title}")
        should_autostart = self._current_track is None or self.current_index == -1
        if should_autostart:
            self.current_index = 0
            logger.info("🚀 Autostarting playback from add_track")
            await self.play_by_index(0)
            return False
        return True

    async def load_playlist(self, tracks: list[wavelink.Playable]) -> None:
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

    async def _start_idle_timer(self, timeout: int = 300) -> None:
        if self._auto_leave_task:
            self._auto_leave_task.cancel()
        async def idle_disconnect():
            await asyncio.sleep(timeout)
            if not self.current and self.is_connected_safely:
                await self.cleanup_disconnect()
                logger.info("[Idle Timer] Disconnected from voice channel due to inactivity.")
        self._auto_leave_task = asyncio.create_task(idle_disconnect())

    async def show_queue(self, interaction: discord.Interaction, page: int = 1) -> None:
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
            view = await QueueView.create(player=self, user=interaction.user, page=page, total_pages=total_pages)
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
            await self._finalize_track_message(old_track)
            self.now_playing_message = None
            await self.play_forward()
        except Exception as e:
            logger.error(f"❌ Skip failed: {e}")

    async def do_next(self) -> None:
        try:
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
            if self.state.loop_mode == LoopMode.TRACK and self._current_track:
                await self.play_track(self._current_track, requester=self._current_track.requester)
                return
            if self.state.loop_mode == LoopMode.QUEUE and self._current_track:
                self.current_index = (self.current_index + 1) % len(self.playlist)
                await self.play_by_index(self.current_index)
                return
            if self.current_index >= len(self.playlist) - 1:
                if self.state.autoplay and self._current_track:
                    recommended = await self._get_autoplay_track()
                    if recommended:
                        await self.add_track(recommended)
                        await self.play_by_index(self.current_index + 1)
                        return
                await self._start_idle_timer()
                return
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

    def _add_to_history(self, track: wavelink.Playable) -> None:
        track_uri = getattr(track, 'uri', getattr(track, 'identifier', ''))
        if track_uri and track_uri not in {getattr(t, 'uri', getattr(t, 'identifier', '')) for t in self._history}:
            self._history.append(track)
            self._history = self._history[-self.max_history_size:]
            logger.debug(f"Added to history: {track.title}")

    async def _finalize_track_message(self, track: Optional[wavelink.Playable], position: Optional[int] = None) -> None:
        if not track or not self.text_channel:
            return
        embed = create_track_finished_embed(track, position=position or getattr(track, 'length', None))
        try:
            if self.now_playing_message:
                await self.now_playing_message.edit(embed=embed, view=None)
                logger.info("✅ Обновлен embed завершенного трека")
            else:
                await self.text_channel.send(embed=embed)
                logger.info("✅ Отправлен новый embed завершенного трека")
        except discord.HTTPException as e:
            logger.warning(f"Не удалось обновить embed: {e}")
            await self.text_channel.send(embed=embed)
            logger.info("✅ Отправлен новый embed завершенного трека после ошибки")

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
                # Показываем embed пустой очереди, а не ошибку подключения
                await self._safe_send_response(
                    interaction,
                    create_empty_queue_embed(),
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
        if interaction.response.is_done():
            return
        
        try:
            voice_state = getattr(interaction.user, 'voice', None)
            if not voice_state or not voice_state.channel:
                await interaction.response.send_message(
                    embed=create_permission_error_embed(),
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            vc_channel = voice_state.channel
            vc = await self._ensure_voice_connection(interaction, vc_channel)
            
            if not vc:
                await interaction.followup.send(
                    embed=create_connection_error_embed(),
                    ephemeral=True
                )
                return
            
            # Determine search source based on query type
            is_uri = query.startswith(("http://", "https://"))
            source = None if is_uri else wavelink.TrackSource.SoundCloud
            
            results = await asyncio.wait_for(
                wavelink.Playable.search(query, source=source), 
                timeout=10.0
            )
            
            if not results:
                await interaction.followup.send(
                    embed=create_search_error_embed(query),
                    ephemeral=True
                )
                return
            
            track = results[0]
            track.requester = interaction.user
            was_added = await vc.add_track(track)
            
            embed = create_track_added_embed(
                track, 
                len(vc.playlist) if was_added else 1
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=create_error_embed("Тайм-аут", "Поиск занял слишком много времени"),
                ephemeral=True
            )
        except wavelink.LavalinkException as e:
            await interaction.followup.send(
                embed=create_error_embed("Ошибка Lavalink", str(e)),
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                embed=create_error_embed("Ошибка", str(e)),
                ephemeral=True
            )

    @commands.Cog.listener()
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
            # --- ГАРАНТИЯ обновления эмбеда now_playing на 'Прослушано' с view=None ---
            if player._current_track and player.text_channel:
                embed = create_track_finished_embed(player._current_track, position=payload.track.length)
                try:
                    if player.now_playing_message:
                        try:
                            await player.now_playing_message.edit(embed=embed, view=None)
                            logger.info("✅ Обновлен embed завершенного трека (гарантировано)")
                        except discord.HTTPException as e:
                            logger.warning(f"Не удалось обновить embed: {e}")
                            await player.text_channel.send(embed=embed)
                            logger.info("✅ Отправлен новый embed завершенного трека после ошибки (гарантировано)")
                    else:
                        await player.text_channel.send(embed=embed)
                        logger.info("✅ Отправлен новый embed завершенного трека (гарантировано)")
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
