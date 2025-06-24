import logging
from typing import Optional, Union

import discord
from discord import ui

from config.constants import Emojis
from ui.embed_now_playing import create_now_playing_embed
from utils.formatters import format_duration

from .track_select import TrackSelect

logger = logging.getLogger(__name__)


class MusicPlayerView(ui.View):
    """
    A comprehensive Discord UI view for music player controls.
    
    Provides buttons for shuffle, previous, pause/play, skip, loop,
    seek, volume, stop, lyrics, and like functionality.
    """
    
    def __init__(
        self, 
        player, 
        message: Optional[discord.Message] = None, 
        requester: Optional[Union[discord.Member, discord.User]] = None
    ):
        super().__init__(timeout=300)  # 5 minute timeout instead of None
        
        self.player = player
        self.message = message
        self.requester = requester
        self._is_destroyed = False
        
        # Set up bidirectional reference
        self.player.view = self
        
        # Initialize UI components
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Initialize all UI components in the correct order."""
        try:
            # Add track selector first
            self.add_item(TrackSelect(self.player, self.requester))
            
            # Add control buttons in logical order
            self._add_control_buttons()
            
        except Exception as e:
            logger.error(f"Failed to setup UI: {e}")
            raise
    
    def _add_control_buttons(self) -> None:
        """Add all control buttons to the view."""
        buttons = [
            ("music:shuffle", Emojis.NK_RANDOM, self.shuffle_button),
            ("music:previous", Emojis.NK_BACK, self.previous_button),
            ("music:pause", Emojis.NK_MUSICPLAY, self.pause_button),
            ("music:skip", Emojis.NK_NEXT, self.skip_button),
            ("music:loop", Emojis.NK_POVTOR, self.loop_button),
            ("music:seek", Emojis.NK_TIME, self.seek_button),
            ("music:volume", Emojis.NK_VOLUME, self.volume_button),
            ("music:stop", Emojis.NK_LEAVE, self.stop_button),
            ("music:lyrics", Emojis.NK_TEXT, self.lyrics_button),
            ("music:like", Emojis.NK_HEART, self.like_button),
        ]
        
        for button_data in buttons:
            custom_id, emoji, callback = button_data[:3]
            style = button_data[3] if len(button_data) > 3 else discord.ButtonStyle.secondary
            self.add_item(self._create_button(custom_id, emoji, callback, style))
    
    def _create_button(
        self, 
        custom_id: str, 
        emoji: str, 
        callback, 
        style: discord.ButtonStyle = discord.ButtonStyle.secondary
    ) -> ui.Button:
        """Create a button with the specified parameters."""
        button = ui.Button(emoji=emoji, style=style, custom_id=custom_id)
        button.callback = callback
        return button
    
    async def on_timeout(self) -> None:
        """Handle view timeout by disabling all components."""
        if self._is_destroyed or not self.message:
            return
            
        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
        except discord.NotFound:
            pass  # Message was deleted
        except Exception as e:
            logger.error(f"Error handling timeout: {e}")
    
    async def on_error(
        self, 
        interaction: discord.Interaction, 
        error: Exception, 
        item: ui.Item
    ) -> None:
        """Handle errors in button interactions."""
        logger.error(f"View error in {item.custom_id}: {error}")
        
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message(
                    "⚠️ Произошла ошибка при выполнении команды.", 
                    ephemeral=True
                )
            except discord.HTTPException:
                pass
    
    def destroy(self) -> None:
        """Clean up the view and its resources."""
        self._is_destroyed = True
        self.stop()
        if hasattr(self.player, 'view') and self.player.view is self:
            self.player.view = None
    
    async def refresh_select_menu(self) -> None:
        """Update the track selection menu with current queue state."""
        if self._is_destroyed:
            return
            
        try:
            # Remove existing TrackSelect
            for item in self.children.copy():
                if isinstance(item, TrackSelect):
                    self.remove_item(item)
                    break
            
            # Add updated TrackSelect
            self.add_item(TrackSelect(self.player, self.requester))
            
            # Update message if available
            if self.message:
                await self.message.edit(view=self)
                
        except discord.HTTPException as e:
            logger.warning(f"Failed to refresh select menu: {e}")
        except Exception as e:
            logger.error(f"Unexpected error refreshing select menu: {e}")
    
    async def _safe_defer_or_respond(
        self, 
        interaction: discord.Interaction, 
        message: str = None, 
        ephemeral: bool = True
    ) -> None:
        """Safely defer or respond to an interaction."""
        try:
            if message:
                await interaction.response.send_message(message, ephemeral=ephemeral)
            else:
                await interaction.response.defer()
        except discord.InteractionResponded:
            pass  # Already responded
        except Exception as e:
            logger.error(f"Error in interaction response: {e}")
    
    # ============ Button Handlers ============
    
    async def shuffle_button(self, interaction: discord.Interaction) -> None:
        """Handle shuffle button click."""
        if not self.player.queue:
            await self._safe_defer_or_respond(
                interaction, "❌ Очередь пуста для перемешивания"
            )
            return
        
        try:
            self.player.queue.shuffle()
            await self._safe_defer_or_respond(
                interaction, f"{Emojis.NK_RANDOM} Очередь перемешана"
            )
            await self.refresh_select_menu()
        except Exception as e:
            logger.error(f"Shuffle error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при перемешивании очереди"
            )
    
    async def previous_button(self, interaction: discord.Interaction) -> None:
        """Handle previous track button click."""
        if not hasattr(self.player, "play_previous"):
            await self._safe_defer_or_respond(
                interaction, "⚠️ Плеер не поддерживает переход к предыдущему треку"
            )
            return
        
        try:
            success = await self.player.play_previous()
            if success and self.player.current:
                embed = create_now_playing_embed(
                    self.player.current, self.player, interaction.user
                )
                await self.message.edit(embed=embed, view=self)
                await self._safe_defer_or_respond(interaction)
            else:
                await self._safe_defer_or_respond(
                    interaction, "❌ Предыдущий трек недоступен"
                )
        except Exception as e:
            logger.error(f"Previous track error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при переходе к предыдущему треку"
            )
    
    async def pause_button(self, interaction: discord.Interaction) -> None:
        """Handle pause/resume button click."""
        try:
            is_paused = getattr(self.player, 'paused', False)
            await self.player.pause(not is_paused)
            
            if self.player.current and self.message:
                embed = create_now_playing_embed(
                    self.player.current, self.player, interaction.user
                )
                await self.message.edit(embed=embed, view=self)
            
            await self._safe_defer_or_respond(interaction)
            
        except Exception as e:
            logger.error(f"Pause/resume error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при изменении воспроизведения"
            )
    
    async def skip_button(self, interaction: discord.Interaction) -> None:
        """Handle skip track button click."""
        try:
            await self.player.skip()
            
            if self.player.current and self.message:
                embed = create_now_playing_embed(
                    self.player.current, self.player, interaction.user
                )
                await self.message.edit(embed=embed, view=self)
            
            await self._safe_defer_or_respond(interaction)
            await self.refresh_select_menu()
            
        except Exception as e:
            logger.error(f"Skip error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при пропуске трека"
            )
    
    async def loop_button(self, interaction: discord.Interaction) -> None:
        """Handle loop toggle button click."""
        try:
            current_loop = getattr(self.player, "loop", False)
            self.player.loop = not current_loop
            
            status = "включен" if self.player.loop else "выключен"
            await interaction.response.edit_message(view=self)
            
            # Optionally send a follow-up message
            try:
                await interaction.followup.send(
                    f"{Emojis.NK_POVTOR} Повтор {status}", 
                    ephemeral=True
                )
            except discord.HTTPException:
                pass
                
        except discord.InteractionResponded:
            pass
        except Exception as e:
            logger.error(f"Loop toggle error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при переключении повтора"
            )
    
    async def seek_button(self, interaction: discord.Interaction) -> None:
        """Handle seek button click - show current position."""
        try:
            if not self.player.current:
                await self._safe_defer_or_respond(
                    interaction, "❌ Нет воспроизводимого трека"
                )
                return
            
            position = getattr(self.player, 'position', 0)
            duration = getattr(self.player.current, 'length', 0)
            
            pos_formatted = format_duration(position)
            dur_formatted = format_duration(duration)
            
            progress_bar = self._create_progress_bar(position, duration)
            
            embed = discord.Embed(
                title="📍 Позиция воспроизведения",
                description=f"**Позиция:** `{pos_formatted}` / `{dur_formatted}`\n{progress_bar}",
                color=discord.Color.blurple()
            )
            
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Seek info error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при получении информации о позиции"
            )
    
    def _create_progress_bar(self, position: int, duration: int, length: int = 20) -> str:
        """Create a visual progress bar."""
        if duration <= 0:
            return "▬" * length
        
        progress = min(position / duration, 1.0)
        filled = int(progress * length)
        bar = "▰" * filled + "▱" * (length - filled)
        return f"`{bar}`"
    
    async def volume_button(self, interaction: discord.Interaction) -> None:
        """Handle volume button click - show current volume."""
        try:
            volume = getattr(self.player, "volume", 100)
            
            embed = discord.Embed(
                title=f"{Emojis.NK_VOLUME} Громкость",
                description=f"**Текущая громкость:** {volume}%",
                color=discord.Color.blurple()
            )
            
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Volume info error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при получении информации о громкости"
            )
    
    async def stop_button(self, interaction: discord.Interaction) -> None:
        """Handle stop button click - disconnect player."""
        try:
            await self.player.disconnect()
            
            embed = discord.Embed(
                title="⏹️ Воспроизведение остановлено",
                description="Плеер отключен от голосового канала",
                color=discord.Color.red()
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            self.destroy()
            
        except Exception as e:
            logger.error(f"Stop error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при остановке воспроизведения"
            )
    
    async def lyrics_button(self, interaction: discord.Interaction) -> None:
        """Handle lyrics button click."""
        try:
            if not self.player.current:
                await self._safe_defer_or_respond(
                    interaction, "❌ Нет воспроизводимого трека"
                )
                return
            
            # TODO: Implement actual lyrics fetching
            embed = discord.Embed(
                title="📄 Текст песни",
                description=f"Функция поиска текста для трека **{self.player.current.title}** в разработке.",
                color=discord.Color.blue()
            )
            
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Lyrics error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при получении текста песни"
            )
    
    async def like_button(self, interaction: discord.Interaction) -> None:
        """Handle like button click - add to playlist."""
        try:
            if not self.player.current:
                await self._safe_defer_or_respond(
                    interaction, "❌ Нет трека для добавления в избранное"
                )
                return
            
            user_mention = interaction.user.mention
            track_title = self.player.current.title
            
            embed = discord.Embed(
                title="❤️ Добавить в плейлист",
                description=(
                    f"{user_mention}, в какой плейлист добавить трек "
                    f"**{track_title}**?\n\n*Напишите название плейлиста или выберите:*"
                ),
                color=discord.Color.red()
            )
            
            # TODO: Add playlist selection dropdown
            embed.add_field(
                name="Популярные плейлисты", 
                value="• `Любимые треки`\n• `Избранное`\n• `Мой плейлист`", 
                inline=False
            )
            
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Like button error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при добавлении трека в плейлист"
            )
