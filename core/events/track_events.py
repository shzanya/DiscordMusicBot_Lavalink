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
    create_empty_queue_embed,
    create_track_finished_embed,
)
from ui.views import MusicPlayerView
from services import mongo_service

logger = logging.getLogger(__name__)


class TrackStartEvent:
    """Handles track start events with proper message management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def handle(self, payload: wavelink.TrackStartEventPayload) -> None:
        """Handle track start event."""
        player: HarmonyPlayer = payload.player
        
        if not player or getattr(player, "_is_destroyed", False):
            logger.warning(
                "❌ Invalid or destroyed player in track start event"
            )
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
            player.speed_override = getattr(player, 'speed_override', 1.0)
            
            # Send now playing message
            await self._send_now_playing_message(player, track)
            
        except Exception as e:
            logger.error(f"❌ Track start handler failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            player._handling_track_start = False
    
    async def _send_now_playing_message(
        self, player: HarmonyPlayer, track: wavelink.Playable
    ) -> None:
        """Send now playing message with player view."""
        if not player.text_channel or player._is_destroyed:
            return
        
        try:
            # Get guild settings
            guild_id = player.text_channel.guild.id  # Keep as int
            logger.debug(f"Getting guild settings for guild_id: {guild_id} (type: {type(guild_id)})")
            settings = await mongo_service.get_guild_settings(guild_id)
            logger.debug(f"Settings result: {settings} (type: {type(settings)})")
            
            # Debug logging
            logger.debug(f"Guild settings for {guild_id}: {settings}")
            
            # Ensure settings is a dict and extract values safely
            if not isinstance(settings, dict):
                settings = {}
            
            color = settings.get("color", "default")
            custom_emojis = settings.get("custom_emojis", {})
            
            # Debug logging
            logger.debug(f"Color: {color}, Custom emojis: {custom_emojis}")
            
            # Ensure custom_emojis is a dict
            if not isinstance(custom_emojis, dict):
                custom_emojis = {}
            
            # Дополнительная проверка - убеждаемся что все ключи и значения строки
            if custom_emojis:
                try:
                    # Проверяем что все ключи и значения - строки
                    validated_emojis = {}
                    for key, value in custom_emojis.items():
                        if isinstance(key, str) and isinstance(value, str):
                            validated_emojis[key] = value
                        else:
                            logger.warning(f"Invalid emoji key/value: {key} -> {value}")
                    custom_emojis = validated_emojis
                except Exception as e:
                    logger.warning(f"Error validating custom_emojis: {e}")
                    custom_emojis = {}
            
            # Ensure requester is valid
            requester = track.requester
            logger.debug(f"Track requester type: {type(requester)}, value: {requester}")
            
            # Check if requester is a valid Discord member/user object
            if (not requester or 
                not hasattr(requester, 'display_name') or 
                not hasattr(requester, 'id') or
                not isinstance(requester, (discord.Member, discord.User))):
                logger.warning(f"Invalid requester {requester}, using guild.me")
                requester = player.text_channel.guild.me
                logger.debug(f"Using guild.me as requester: {type(requester)}")
            
            # Additional safety check
            if not hasattr(requester, 'display_name'):
                logger.error(f"Requester {requester} still has no display_name after validation")
                requester = player.text_channel.guild.me
            
            # Create player view
            view = await MusicPlayerView.create(
                player, None, requester,
                color=color, custom_emojis=custom_emojis
            )
            
            # Delete old message if exists
            if player.now_playing_message:
                try:
                    await player.now_playing_message.delete()
                except discord.HTTPException:
                    pass
            
            # Send new message
            from ui.progress_updater import send_now_playing_message
            player.now_playing_message = await send_now_playing_message(
                player.text_channel,
                track,
                player,
                requester=requester,
                view=view,
                color=color,
                custom_emojis=custom_emojis
            )
            
            logger.info(f"✅ Sent now playing message for: {track.title}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send now playing message: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")


class TrackEndEvent:
    """Handles track end events with proper queue management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    async def handle(self, payload: wavelink.TrackEndEventPayload) -> None:
        """Handle track end event."""
        player: HarmonyPlayer = payload.player
        
        if not player or getattr(player, "_is_destroyed", False):
            logger.warning(
                "❌ Invalid or destroyed player in track end event"
            )
            return
        
        if getattr(player, "_handling_track_end", False):
            logger.debug("Track end already handled")
            return
        
        if payload.reason == "replaced":
            logger.info("🔁 Track replaced manually — skipping handler logic")
            return
        
        player._handling_track_end = True
        
        try:
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
        # Update finished track message
        await self._update_finished_track_message(player, payload.track)
        
        # Clear current track and message
        player.now_playing_message = None
        player._current_track = None
        
        # Handle queue logic
        await self._handle_queue_logic(player)
    
    async def _update_finished_track_message(
        self, player: HarmonyPlayer, track: wavelink.Playable
    ) -> None:
        """Update now playing message to show finished track."""
        if not track or not player.text_channel:
            return
        
        embed = create_track_finished_embed(track, position=track.length)
        
        try:
            if player.now_playing_message:
                await player.now_playing_message.edit(embed=embed, view=None)
                logger.info("✅ Updated finished track embed")
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
    
    async def _handle_queue_logic(self, player: HarmonyPlayer) -> None:
        """Handle queue logic after track end."""
        # Check if queue is empty
        if not player.playlist or player.current_index >= len(player.playlist) - 1:
            await self._handle_empty_queue(player)
            return
        
        # Handle loop modes
        if (player.state.loop_mode == LoopMode.TRACK and
                player._current_track):
            requester = player._current_track.requester
            if not requester:
                requester = player.text_channel.guild.me if player.text_channel else None
            await player.play_track(
                player._current_track,
                requester=requester
            )
            return
        
        if (player.state.loop_mode == LoopMode.QUEUE and
                player._current_track):
            player.current_index = (
                player.current_index + 1
            ) % len(player.playlist)
            await player.play_by_index(player.current_index)
            return
        
        # Play next track
        player.current_index += 1
        await player.play_by_index(player.current_index)
    
    async def _handle_empty_queue(self, player: HarmonyPlayer) -> None:
        """Handle empty queue scenario."""
        logger.info("🚪 Queue is empty — disconnecting")
        
        if player.text_channel:
            try:
                embed = create_empty_queue_embed()
                await player.text_channel.send(embed=embed)
                logger.info("✅ Sent empty queue embed")
            except Exception as e:
                logger.error(f"❌ Error sending empty queue embed: {e}")
        
        await player.cleanup_disconnect() 
