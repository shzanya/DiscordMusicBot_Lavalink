import asyncio
import logging
import re
import traceback
from typing import Dict, List, Optional, Union

import discord
import wavelink
from wavelink import Queue
from cachetools import TTLCache
from discord import app_commands
from discord.ext import commands
from config.constants import Colors, Emojis
from core.player import LoopMode
from types import SimpleNamespace
from ui.embeds import (
    cleanup_updater,
    create_error_embed,
    create_now_playing_embed,
    now_playing_updater,
    send_now_playing_message,
)

logger = logging.getLogger(__name__)

# Глобальные кеши и состояния
autocomplete_cache = TTLCache(maxsize=100, ttl=120)
connection_locks: Dict[int, asyncio.Lock] = {}


autocomplete_cache: dict[str, List[app_commands.Choice[str]]] = {}

async def track_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    query = current.strip().lower()

    if len(query) < 2:
        return []

    if query in autocomplete_cache:
        return autocomplete_cache[query]

    try:
        # Попробуем найти сначала в Spotify
        tracks = await asyncio.wait_for(
            wavelink.Playable.search(query, source="spotify"),
            timeout=1.5
        )

        # Если Spotify не дал результатов — пробуем SoundCloud
        if not tracks:
            tracks = await asyncio.wait_for(
                wavelink.Playable.search(query, source="soundcloud"),
                timeout=1.5
            )

        if not tracks:
            return []

        choices = []
        for track in tracks[:5]:
            name = f"{track.author} – {track.title}"
            if len(name) > 100:
                name = name[:97] + "..."
            choices.append(app_commands.Choice(name=name, value=track.uri))

        autocomplete_cache[query] = choices
        return choices

    except Exception as e:
        logger.warning(f"[Autocomplete Error] {e}")
        return []



class HarmonyPlayer(wavelink.Player):
    """Enhanced Wavelink Player with proper state management and error handling."""
    
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

        # Добавить сюда
        self.state = SimpleNamespace(
            loop_mode=LoopMode.NONE,
            autoplay=False
        )
    @property
    def is_paused(self) -> bool:
        """Safe access to paused state."""
        return getattr(self, 'paused', False)

    @property
    def current_track(self) -> Optional[wavelink.Playable]:
        """Get current track with fallback."""
        return self._current_track or super().current

    @property
    def current(self) -> Optional[wavelink.Playable]:
        """Unified current track property."""
        return self.current_track

    @property
    def is_connected_safely(self) -> bool:
        """Check if player is safely connected."""
        try:
            return (
                self.guild is not None and 
                self.channel is not None and 
                not self._is_destroyed and
                super().connected
            )
        except Exception:
            return False

    async def show_queue(self, interaction: discord.Interaction, limit: int = 10) -> None:
        """Display current queue with enhanced formatting."""
        try:
            if self.queue.is_empty:
                embed = discord.Embed(
                    title="📭 Очередь пуста",
                    description="Добавьте треки с помощью `/play`.",
                    color=Colors.WARNING
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            description_lines = []
            queue_items = list(self.queue)[:limit]
            
            for i, track in enumerate(queue_items, start=1):
                duration = getattr(track, 'length', 0)
                duration_str = f" `[{self._format_duration(duration)}]`" if duration else ""
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
            
            # Добавляем информацию о текущем треке
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
        """Format duration from milliseconds to MM:SS."""
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
                    self.controller_message: Optional[discord.Message] = None
        except Exception as e:
            logger.error(f"[play_track error] {e}")

    def _add_to_history(self, track: wavelink.Playable) -> None:
        """Add track to history with size management."""
        try:
            if track in self.history:
                self.history.remove(track)
            self.history.append(track)
            
            # Manage history size
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

                self._start_idle_timer()
                return

            next_track = self.queue.get()
            await self.play_track(next_track)
        except Exception as e:
            logger.error(f"[do_next error] {e}")

    def _schedule_auto_leave(self) -> None:
        """Schedule auto-disconnect after inactivity."""
        async def leave_after_timeout():
            try:
                await asyncio.sleep(300)  # 5 минут
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
        """Skip the current track and play the next one."""
        if self.queue.is_empty:
            await self.stop()
            return

        next_track = self.queue.get()
        await self.play_track(next_track)

    async def play_previous(self) -> bool:
        """Play previous track if available."""
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
        """Safely disconnect and cleanup resources."""
        try:
            self._is_destroyed = True
            
            # Cancel auto-leave task
            if self._auto_leave_task and not self._auto_leave_task.done():
                self._auto_leave_task.cancel()
                self._auto_leave_task = None
            
            # Clear view reference
            if self.view:
                try:
                    if hasattr(self.view, 'destroy'):
                        self.view.destroy()
                except Exception as e:
                    logger.warning(f"View destroy failed: {e}")
                finally:
                    self.view = None
            
            # Disconnect from voice
            if self.is_connected_safely:
                await self.disconnect()
                
        except Exception as e:
            logger.error(f"Cleanup disconnect failed: {e}")


class Music(commands.Cog):
    """Enhanced Music cog with robust error handling and connection management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_unload(self) -> None:
        """Cleanup when cog is unloaded."""
        try:
            cleanup_updater()
            
            # Disconnect all players
            for guild in self.bot.guilds:
                if guild.voice_client and isinstance(guild.voice_client, HarmonyPlayer):
                    await guild.voice_client.cleanup_disconnect()
                    
        except Exception as e:
            logger.error(f"Cog unload error: {e}")

    async def _get_connection_lock(self, guild_id: int) -> asyncio.Lock:
        """Get or create connection lock for guild."""
        if guild_id not in connection_locks:
            connection_locks[guild_id] = asyncio.Lock()
        return connection_locks[guild_id]
    async def _search_tracks(self, query: str) -> Optional[Union[list[wavelink.Playable], wavelink.Playlist]]:
        """🔍 Улучшенный query треков с обработкой ошибок."""
        try:
            # Проверка — это ссылка или queryовый запрос
            is_url = bool(re.match(r'^https?://', query, re.IGNORECASE))

            # Поиск треков (Lavalink автоматически определит источник по URL)
            results = await asyncio.wait_for(
                wavelink.Playable.search(
                    query,
                    source=wavelink.TrackSource.YouTube if not is_url else None
                ),
                timeout=15.0
            )

            return results

        except asyncio.TimeoutError:
            logger.warning(f"[Timeout] Поиск превысил лимит времени: {query}")
            return None
        except wavelink.LavalinkException as e:
            logger.error(f"[Lavalink Error] {e}")
            return None
        except Exception as e:
            logger.error(f"[Unknown Error] {e}")
            traceback.print_exc()
            return None

    async def _ensure_voice_connection(
        self, 
        interaction: discord.Interaction, 
        voice_channel: discord.VoiceChannel
    ) -> Optional[HarmonyPlayer]:
        """Ensure proper voice connection with locking."""
        guild_id = interaction.guild.id
        lock = await self._get_connection_lock(guild_id)
        
        async with lock:
            try:
                vc = interaction.guild.voice_client
                
                # If already connected and healthy
                if vc and isinstance(vc, HarmonyPlayer) and vc.is_connected_safely:
                    # Move to new channel if needed
                    if vc.channel.id != voice_channel.id:
                        await vc.move_to(voice_channel)
                    return vc
                
                # Clean up existing broken connection
                if vc:
                    try:
                        await vc.cleanup_disconnect()
                    except Exception as e:
                        logger.warning(f"Cleanup of old connection failed: {e}")
                
                # Create new connection
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
        """Display current music queue."""
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

    @app_commands.command(name="play", description="🎵 Искать и воспроизводить музыку")
    @app_commands.describe(query="Название трека, исполнитель или ссылка")
    @app_commands.autocomplete(query=track_autocomplete)
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        """Enhanced play command with robust error handling."""
        # Voice channel validation
        voice_state = getattr(interaction.user, 'voice', None)
        if not voice_state or not voice_state.channel:
            await interaction.response.send_message(
                embed=create_error_embed("Ошибка", "Вы должны находиться в голосовом канале"),
                ephemeral=True
            )
            return

        vc_channel = voice_state.channel
        
        # Defer response early
        await interaction.response.defer(ephemeral=True)

        try:
            # Ensure voice connection
            vc = await self._ensure_voice_connection(interaction, vc_channel)
            if not vc:
                await interaction.followup.send(
                    embed=create_error_embed("Ошибка", "Не удалось подключиться к голосовому каналу"),
                    ephemeral=True
                )
                return

            # Search for tracks
            logger.info(f"Searching for: {query}")
            results = await self._search_tracks(query)
            
            if not results:
                await interaction.followup.send(
                    embed=create_error_embed("query", f"Ничего не найдено по запросу: `{query}`"),
                    ephemeral=True
                )
                return

            # Handle playlist
            if isinstance(results, wavelink.Playlist):
                added_count = 0
                for track in results.tracks:
                    vc.queue.put(track)
                    added_count += 1

                embed = discord.Embed(
                    title=f"{Emojis.ADD} Плейлист добавлен",
                    description=f"**{results.name}** — {added_count} треков добавлено в очередь",
                    color=Colors.SUCCESS
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

                # Start playback if nothing is playing
                if not vc.playing and not vc.paused:
                    await vc.do_next()
                    if vc.current:
                        try:
                            await send_now_playing_message(
                                interaction.channel, vc.current, vc, interaction.user
                            )
                        except Exception as e:
                            logger.warning(f"Failed to send now playing message: {e}")

            # Handle single track
            else:
                track = results[0]
                logger.info(f"Found track: {track.title} by {track.author}")

                # Add to queue if something is playing
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
                    
                # Play immediately if nothing is playing
                else:
                    success = await vc.play_track(track)
                    if success:
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
                    else:
                        await interaction.followup.send(
                            embed=create_error_embed("Ошибка", "Не удалось воспроизвести трек"),
                            ephemeral=True
                        )

        except Exception as e:
            logger.error(f"Play command failed: {e}")
            traceback.print_exc()
            
            try:
                await interaction.followup.send(
                    embed=create_error_embed("Ошибка", "Произошла непредвиденная ошибка"),
                    ephemeral=True
                )
            except Exception:
                pass  # Interaction might be expired

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        """Handle track end events with proper error handling."""
        try:
            player: HarmonyPlayer = payload.player
            
            if not player or not isinstance(player, HarmonyPlayer):
                return

            if player._is_destroyed:
                return

            logger.info(f"Track ended: {payload.track.title if payload.track else 'Unknown'}")
            logger.debug(f"End reason: {payload.reason}")

            # Only proceed to next track for natural endings
            if payload.reason in ("finished", "stopped", "cleanup"):
                await player.do_next()

        except Exception as e:
            logger.error(f"Track end handler failed: {e}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        """Handle track start events."""
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

            # Update now playing embed if exists
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
        """Handle voice state updates for auto-disconnect."""
        try:
            # Only process bot's own voice state changes
            if member.id != self.bot.user.id:
                return

            # Bot was disconnected
            if before.channel and not after.channel:
                guild = before.channel.guild
                vc = guild.voice_client
                
                if vc and isinstance(vc, HarmonyPlayer):
                    logger.info(f"Bot disconnected from voice in {guild.name}")
                    await vc.cleanup_disconnect()

        except Exception as e:
            logger.error(f"Voice state update handler failed: {e}")


async def setup(bot: commands.Bot) -> None:
    """Setup function for the cog."""
    await bot.add_cog(Music(bot))
