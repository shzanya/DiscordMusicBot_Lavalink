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
    def __init__(
        self, 
        player, 
        message: Optional[discord.Message] = None, 
        requester: Optional[Union[discord.Member, discord.User]] = None
    ):
        super().__init__(timeout=300)
        self.player = player
        self.message = message
        self.requester = requester
        self._is_destroyed = False
        self.player.view = self

        # Сохраняем ссылку на TrackSelect
        self._select = TrackSelect(self.player, self.requester)

    async def on_timeout(self) -> None:
        if self._is_destroyed or not self.message:
            return
        try:
            for item in self.children:
                item.disabled = True
            await self.message.edit(view=self)
        except discord.NotFound:
            pass
        except Exception as e:
            logger.error(f"Error handling timeout: {e}")

    async def on_error(
        self, 
        interaction: discord.Interaction, 
        error: Exception, 
        item: ui.Item
    ) -> None:
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
        self._is_destroyed = True
        self.stop()
        if hasattr(self.player, 'view') and self.player.view is self:
            self.player.view = None

    async def refresh_select_menu(self) -> None:
        if self._is_destroyed:
            return
        try:
            for item in self.children.copy():
                if isinstance(item, TrackSelect):
                    self.remove_item(item)
                    break
            # Re-add TrackSelect at the start to maintain position above buttons
            self.add_item(TrackSelect(self.player, self.requester))
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
        try:
            if message:
                await interaction.response.send_message(message, ephemeral=ephemeral)
            else:
                await interaction.response.defer()
        except discord.InteractionResponded:
            pass
        except Exception as e:
            logger.error(f"Error in interaction response: {e}")

    @ui.button(emoji=Emojis.NK_RANDOM, style=discord.ButtonStyle.secondary, custom_id="music:shuffle")
    async def shuffle_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if not self.player.queue:
            await self._safe_defer_or_respond(interaction, "❌ Очередь пуста для перемешивания")
            return
        try:
            self.player.queue.shuffle()
            await self._safe_defer_or_respond(interaction, f"{Emojis.NK_RANDOM} Очередь перемешана")
            await self.refresh_select_menu()
        except Exception as e:
            logger.error(f"Shuffle error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при перемешивании очереди")

    @ui.button(emoji=Emojis.NK_BACK, style=discord.ButtonStyle.secondary, custom_id="music:previous")
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if not hasattr(self.player, "play_previous"):
            await self._safe_defer_or_respond(interaction, "⚠️ Плеер не поддерживает переход к предыдущему треку")
            return
        try:
            success = await self.player.play_previous()
            if success and self.player.current:
                embed = create_now_playing_embed(self.player.current, self.player, interaction.user)
                await self.message.edit(embed=embed, view=self)
                await self._safe_defer_or_respond(interaction)
            else:
                await self._safe_defer_or_respond(interaction, "❌ Предыдущий трек недоступен")
        except Exception as e:
            logger.error(f"Previous track error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при переходе к предыдущему треку")

    @ui.button(emoji=Emojis.NK_MUSICPLAY, style=discord.ButtonStyle.secondary, custom_id="music:pause")
    async def pause_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            is_paused = getattr(self.player, 'paused', False)
            await self.player.pause(not is_paused)
            if self.player.current and self.message:
                embed = create_now_playing_embed(self.player.current, self.player, interaction.user)
                await self.message.edit(embed=embed, view=self)
            await self._safe_defer_or_respond(interaction)
        except Exception as e:
            logger.error(f"Pause/resume error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при изменении воспроизведения")

    @ui.button(emoji=Emojis.NK_NEXT, style=discord.ButtonStyle.secondary, custom_id="music:skip")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            await self.player.skip()
            if self.player.current and self.message:
                embed = create_now_playing_embed(self.player.current, self.player, interaction.user)
                await self.message.edit(embed=embed, view=self)
            await self._safe_defer_or_respond(interaction)
            await self.refresh_select_menu()
        except Exception as e:
            logger.error(f"Skip error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при пропуске трека")

    @ui.button(emoji=Emojis.NK_POVTOR, style=discord.ButtonStyle.secondary, custom_id="music:loop")
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            current_loop = getattr(self.player, "loop", False)
            self.player.loop = not current_loop
            status = "включен" if self.player.loop else "выключен"
            await interaction.response.edit_message(view=self)
            try:
                await interaction.followup.send(f"{Emojis.NK_POVTOR} Повтор {status}", ephemeral=True)
            except discord.HTTPException:
                pass
        except discord.InteractionResponded:
            pass
        except Exception as e:
            logger.error(f"Loop toggle error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при переключении повтора")

    @ui.button(emoji=Emojis.NK_TIME, style=discord.ButtonStyle.secondary, custom_id="music:seek")
    async def seek_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            if not self.player.current:
                await self._safe_defer_or_respond(interaction, "❌ Нет воспроизводимого трека")
                return
            position = getattr(self.player, 'position', 0)
            duration = getattr(self.player.current, 'length', 0)
            pos_formatted = format_duration(position)
            dur_formatted = format_duration(duration)
            progress_bar = self._create_progress_bar(position, duration)
            embed = discord.Embed(
                title="📍 Позиция воспроизведения",
                description=f"**Позиция:** `{pos_formatted}` / `{dur_formatted}`\n{progress_bar}",
                color=0x2B2D31
            )
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Seek info error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при получении информации о позиции")

    def _create_progress_bar(self, position: int, duration: int, length: int = 20) -> str:
        if duration <= 0:
            return "▬" * length
        progress = min(position / duration, 1.0)
        filled = int(progress * length)
        bar = "▰" * filled + "▱" * (length - filled)
        return f"`{bar}`"

    @ui.button(emoji=Emojis.NK_VOLUME, style=discord.ButtonStyle.secondary, custom_id="music:volume")
    async def volume_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            volume = getattr(self.player, "volume", 100)
            embed = discord.Embed(
                title=f"{Emojis.NK_VOLUME} Громкость",
                description=f"**Текущая громкость:** {volume}%",
                color=0x2B2D31
            )
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Volume info error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при получении информации о громкости")

    @ui.button(emoji=Emojis.NK_LEAVE, style=discord.ButtonStyle.secondary, custom_id="music:stop")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            await self.player.disconnect()
            embed = discord.Embed(
                title="⏹️ Воспроизведение остановлено",
                description="Плеер отключен от голосового канала",
                color=0x2B2D31
            )
            await interaction.response.edit_message(embed=embed, view=None)
            self.destroy()
        except Exception as e:
            logger.error(f"Stop error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при остановке воспроизведения")

    @ui.button(emoji=Emojis.NK_TEXT, style=discord.ButtonStyle.secondary, custom_id="music:lyrics")
    async def lyrics_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            if not self.player.current:
                await self._safe_defer_or_respond(interaction, "❌ Нет воспроизводимого трека")
                return
            embed = discord.Embed(
                title="📄 Текст песни",
                description=f"Функция поиска текста для трека **{self.player.current.title}** в разработке.",
                color=0x2B2D31
            )
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Lyrics error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при получении текста песни")

    @ui.button(emoji=Emojis.NK_HEART, style=discord.ButtonStyle.secondary, custom_id="music:like")
    async def like_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            if not self.player.current:
                await self._safe_defer_or_respond(interaction, "❌ Нет трека для добавления в избранное")
                return
            user_mention = interaction.user.mention
            track_title = self.player.current.title
            embed = discord.Embed(
                title="❤️ Добавить в плейлист",
                description=(
                    f"{user_mention}, в какой плейлист добавить трек "
                    f"**{track_title}**?\n\n*Напишите название плейлиста или выберите:*"
                ),
                color=0x2B2D31
            )
            embed.add_field(
                name="Популярные плейлисты", 
                value="• `Любимые треки`\n• `Избранное`\n• `Мой плейлист`", 
                inline=False
            )
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Like button error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при добавлении трека в плейлист")
