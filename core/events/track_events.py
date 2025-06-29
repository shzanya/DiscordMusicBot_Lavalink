"""
Track events handler for music bot.
Handles track start and end events with proper queue management.
"""

import logging
import time
import discord
import wavelink
from discord.ext import commands

from commands.music.playback import HarmonyPlayer
from core.player import LoopMode
from ui.music_embeds import (
    create_track_finished_embed,
)
from utils.builders.embed import build_disconnect_embed

logger = logging.getLogger(__name__)


class TrackStartEvent:
    """Handles track start events with proper message management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle(self, payload: wavelink.TrackStartEventPayload) -> None:
        """Handle track start event."""
        player: HarmonyPlayer = payload.player

        if not player or getattr(player, "_is_destroyed", False):
            logger.warning("❌ Invalid or destroyed player in track start event")
            return

        if getattr(player, "_handling_track_start", False):
            logger.debug("Track start already handled")
            return

        player._handling_track_start = True

        try:
            track = payload.track
            if not track:
                logger.warning("No track in payload")
                return

            logger.info(f"🎵 Track started: {track.title}")

            # Apply saved effects
            await player.apply_saved_effects()

            # Reset timing
            player._last_position = 0.0
            player.start_time_real = int(time.time())
            player.speed_override = getattr(player, "speed_override", 1.0)

            # Note: Now playing message is sent in playback.py play_track method
            # to avoid duplication

        except Exception as e:
            logger.error(f"❌ Track start handler failed: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            player._handling_track_start = False


class TrackEndEvent:
    """Handles track end events with proper queue management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle(self, payload: wavelink.TrackEndEventPayload) -> None:
        """Handle track end event."""
        player: HarmonyPlayer = payload.player

        if not player or getattr(player, "_is_destroyed", False):
            logger.debug("❌ Invalid or destroyed player in track end event - skipping")
            return

        if getattr(player, "_handling_track_end", False):
            logger.debug("Track end already handled")
            return

        if payload.reason == "replaced":
            logger.info("🔁 Track replaced manually — skipping handler logic")
            return

        player._handling_track_end = True

        try:
            # Дополнительная проверка на случай, если плеер был уничтожен во время обработки
            if getattr(player, "_is_destroyed", False):
                logger.debug(
                    "❌ Player was destroyed during track end handling - aborting"
                )
                return

            # Handle track end based on reason
            if payload.reason == "REPLACED":
                await self._handle_replaced_track(player)
            else:
                await self._handle_normal_track_end(player, payload)

        except Exception as e:
            logger.error(f"❌ Track end handler failed: {e}")
        finally:
            player._handling_track_end = False

    async def _handle_replaced_track(self, player: HarmonyPlayer) -> None:
        """Handle track replacement."""
        player.paused = False
        player.paused_at = 0

        # Delete old message
        if player.now_playing_message:
            try:
                await player.now_playing_message.delete()
            except discord.HTTPException:
                pass
            player.now_playing_message = None

    async def _handle_normal_track_end(
        self, player: HarmonyPlayer, payload: wavelink.TrackEndEventPayload
    ) -> None:
        """Handle normal track end."""
        # Сохраняем ссылку на текущий трек перед очисткой
        current_track = player._current_track

        # Update finished track message
        await self._update_finished_track_message(player, payload.track)

        # Clear current track and message
        player.now_playing_message = None
        player._current_track = None

        # Handle queue logic with saved track reference
        await self._handle_queue_logic(player, current_track)

    async def _update_finished_track_message(
        self, player: HarmonyPlayer, track: wavelink.Playable
    ) -> None:
        """Update now playing message to show finished track."""
        if not track or not player.text_channel:
            return

        embed = create_track_finished_embed(track, position=track.length)

        try:
            if player.now_playing_message:
                # Проверяем, что сообщение еще существует и не было заменено
                try:
                    await player.now_playing_message.edit(embed=embed, view=None)
                    logger.info("✅ Updated finished track embed")
                except discord.NotFound:
                    # Сообщение было удалено, отправляем новое
                    await player.text_channel.send(embed=embed)
                    logger.info("✅ Sent new finished track embed (original deleted)")
                except discord.HTTPException as e:
                    if "Cannot edit a message authored by another user" in str(e):
                        # Сообщение было заменено другим, отправляем новое
                        await player.text_channel.send(embed=embed)
                        logger.info("✅ Sent new finished track embed (replaced)")
                    else:
                        raise
            else:
                await player.text_channel.send(embed=embed)
                logger.info("✅ Sent new finished track embed")
        except discord.HTTPException as e:
            logger.warning(f"Failed to update embed: {e}")
            try:
                await player.text_channel.send(embed=embed)
                logger.info("✅ Sent new finished track embed after error")
            except Exception as e2:
                logger.error(f"Failed to send embed: {e2}")

    async def _handle_queue_logic(
        self, player: HarmonyPlayer, finished_track: wavelink.Playable = None
    ) -> None:
        """Handle queue logic after track end."""

        # Handle loop modes first
        if player.state.loop_mode == LoopMode.TRACK and finished_track:
            requester = finished_track.requester
            if not requester:
                requester = (
                    player.text_channel.guild.me if player.text_channel else None
                )
            await player.play_track(finished_track, requester=requester)
            return

        if player.state.loop_mode == LoopMode.QUEUE and finished_track:
            player.current_index = (player.current_index + 1) % len(player.playlist)
            await player.play_by_index(player.current_index)
            return

        # Check if queue is empty (only after handling loop modes)
        if not player.playlist or player.current_index >= len(player.playlist) - 1:
            await self._handle_empty_queue(player)
            return

        # Play next track
        player.current_index += 1
        await player.play_by_index(player.current_index)

    async def _handle_empty_queue(self, player: HarmonyPlayer) -> None:
        """Handle empty queue scenario."""
        logger.info("🚪 Queue is empty — disconnecting")

        if player.text_channel:
            try:
                # Получаем настройки эмодзи из плеера

                if hasattr(player, "emoji_settings"):
                    getattr(player.emoji_settings, "color", "default")
                    getattr(
                        player.emoji_settings, "custom_emojis", None
                    )

                embed = build_disconnect_embed(
                    reason="в очереди не осталось треков", embed_color=0x242429
                )
                await player.text_channel.send(embed=embed)
                logger.info("✅ Sent disconnect embed")
            except Exception as e:
                logger.error(f"❌ Error sending disconnect embed: {e}")

        await player.cleanup_disconnect()
