import logging
from typing import Optional, Union
import discord
from discord import ui
from config.constants import emojis
from ui.embed_now_playing import create_now_playing_embed
from utils.formatters import format_duration
from core.player import HarmonyPlayer
import asyncio


from .track_select import TrackSelect

logger = logging.getLogger(__name__)

class MusicPlayerView(ui.View):
    def __init__(self, player, message: Optional[discord.Message] = None, requester: Optional[Union[discord.Member, discord.User]] = None):
        super().__init__(timeout=None)
        self.player = player
        self.message = message
        self.requester = requester
        self._is_destroyed = False
        self.player.view = self
        track_select = TrackSelect(self.player, self.requester)
        buttons = [item for item in self.children]
        self.clear_items()
        self.add_item(track_select)
        for button in buttons:
            self.add_item(button)
        logger.info(f"View initialized with children: {[item.custom_id for item in self.children if hasattr(item, 'custom_id')]}")

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

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        logger.error(f"View error in {item.custom_id}: {error}")
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message("⚠️ Произошла ошибка при выполнении команды.", ephemeral=True)
            except discord.HTTPException:
                pass

    def destroy(self) -> None:
        self._is_destroyed = True
        self.stop()

        if hasattr(self.player, 'view') and self.player.view is self:
            self.player.view = None

        # Попробовать удалить view из сообщения
        if self.message:
            try:
                asyncio.create_task(self.message.edit(view=None))
            except Exception as e:
                logger.warning(f"Не удалось удалить view из сообщения при destroy(): {e}")


    async def refresh_select_menu(self) -> None:
        if self._is_destroyed:
            return
        try:
            for item in self.children.copy():
                if isinstance(item, TrackSelect):
                    self.remove_item(item)
                    break
            self.add_item(TrackSelect(self.player, self.requester))
            if self.message:
                await self.message.edit(view=self)
        except discord.HTTPException as e:
            logger.warning(f"Failed to refresh select menu: {e}")
        except Exception as e:
            logger.error(f"Unexpected error refreshing select menu: {e}")

    async def _safe_defer_or_respond(self, interaction: discord.Interaction, message: str = None, ephemeral: bool = True) -> None:
        try:
            if message:
                await interaction.response.send_message(message, ephemeral=ephemeral)
            else:
                await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass
        except Exception as e:
            logger.error(f"Error in interaction response: {e}")

    @ui.button(emoji=emojis.NK_RANDOM(), style=discord.ButtonStyle.secondary, custom_id="music:shuffle")
    async def shuffle_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        if not self.player.queue:
            await self._safe_defer_or_respond(interaction, "❌ Очередь пуста для перемешивания")
            return
        try:
            self.player.queue.shuffle()
            await self._safe_defer_or_respond(interaction, f"{emojis.NK_RANDOM()} Очередь перемешана")
            await self.refresh_select_menu()
        except Exception as e:
            logger.error(f"Shuffle error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при перемешивании очереди")

    @ui.button(emoji=emojis.NK_BACK(), style=discord.ButtonStyle.secondary, custom_id="music:previous")
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            if getattr(self.player, "_handling_track_end", False):
                await self._safe_defer_or_respond(interaction, "⏳ Подождите завершения текущего трека...")
                return

            if self.player.current_index <= 0:
                await self._safe_defer_or_respond(interaction, "📜 Нет предыдущих треков в плейлисте")
                return

            await self._safe_defer_or_respond(interaction)
            success = await self.player.play_previous()

            if not success:
                await interaction.followup.send("❌ Не удалось воспроизвести предыдущий трек", ephemeral=True)
                return

            await self.refresh_select_menu()

        except Exception as e:
            logger.error(f"Previous track error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при переходе к предыдущему треку")


    @ui.button(emoji=emojis.NK_MUSICPLAY(), style=discord.ButtonStyle.secondary, custom_id="music:pause")
    async def pause_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            # Use player.now_playing_message if self.message is None
            if not self.message and self.player.now_playing_message:
                self.message = self.player.now_playing_message
                logger.debug("Updated self.message from player.now_playing_message in pause_button")

            if not self.message:
                logger.warning("self.message is None during pause_button, attempting to create new message")
                if self.player.current and self.player.text_channel:
                    embed = create_now_playing_embed(self.player.current, self.player, self.requester or interaction.user)

                    self.message = await self.player.text_channel.send(embed=embed, view=self)
                    self.player.now_playing_message = self.message
                    logger.info("Created new now_playing_message in pause_button")
                else:
                    await self._safe_defer_or_respond(interaction, "⚠️ Не удалось обновить интерфейс: нет текущего трека или канала")
                    return

            is_paused = getattr(self.player, 'paused', False)
            await self.player.pause(not is_paused)
            button.emoji = emojis.NK_MUSICPAUSE() if not is_paused else emojis.NK_MUSICPLAY()
            await self.message.edit(view=self)
            if self.player.current:
                embed = create_now_playing_embed(self.player.current, self.player, self.requester or interaction.user)

                await self.message.edit(embed=embed, view=self)
            await self._safe_defer_or_respond(interaction)
        except Exception as e:
            logger.error(f"Pause/resume error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при изменении воспроизведения")


    @ui.button(emoji=emojis.NK_NEXT(), style=discord.ButtonStyle.secondary, custom_id="music:skip")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            if getattr(self.player, "_handling_track_end", False):
                await self._safe_defer_or_respond(interaction, "⏳ Подождите завершения текущего трека...")
                return

            if self.player.current_index >= len(self.player.playlist) - 1:
                await self._safe_defer_or_respond(interaction, "📭 В плейлисте нет треков для пропуска")
                return

            await self._safe_defer_or_respond(interaction)
            await self.player.skip()
            await self.refresh_select_menu()

        except Exception as e:
            logger.error(f"Skip error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при пропуске трека")

    @ui.button(emoji=emojis.NK_POVTOR(), style=discord.ButtonStyle.secondary, custom_id="music:loop")
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            current_loop = getattr(self.player, "loop", False)
            self.player.loop = not current_loop

            status = "включен" if self.player.loop else "выключен"
            await self._safe_defer_or_respond(interaction, f"{emojis.NK_POVTOR()} Повтор {status}")
        except Exception as e:
            logger.error(f"Loop toggle error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при переключении повтора")

    @ui.button(emoji=emojis.NK_TIME(), style=discord.ButtonStyle.secondary, custom_id="music:seek")
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
                color=0x242429
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

    @ui.button(emoji=emojis.NK_VOLUME(), style=discord.ButtonStyle.secondary, custom_id="music:volume")
    async def volume_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            volume = getattr(self.player, "volume", 100)
            embed = discord.Embed(
                title=f"{emojis.NK_VOLUME()} Громкость",
                description=f"**Текущая громкость:** {volume}%",
                color=0x242429
            )
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Volume info error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при получении информации о громкости")

    @ui.button(emoji=emojis.NK_LEAVE(), style=discord.ButtonStyle.secondary, custom_id="music:stop")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            await self.player.disconnect()
            embed = discord.Embed(
                title="⏹️ Воспроизведение остановлено",
                description="Плеер отключен от голосового канала",
                color=0x242429
            )
            await interaction.response.edit_message(embed=embed, view=None)
            self.destroy()
        except Exception as e:
            logger.error(f"Stop error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при остановке воспроизведения")

    @ui.button(emoji=emojis.NK_TEXT(), style=discord.ButtonStyle.secondary, custom_id="music:lyrics")
    async def lyrics_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        try:
            if not self.player.current:
                await self._safe_defer_or_respond(interaction, "❌ Нет воспроизводимого трека")
                return

            track = self.player.current
            title = track.title
            artist = getattr(track, "author", "")

            await interaction.response.defer(ephemeral=True)

            from services.lyrics import LyricsService
            lyrics_service = LyricsService()
            lyrics = await lyrics_service.get_lyrics(title, artist, url=track.uri)

            if not lyrics:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Текст не найден",
                        description=f"Не удалось найти текст для **{title}**.",
                        color=0x242429
                    ),
                    ephemeral=True
                )
                return

            chunks = [lyrics[i:i + 1000] for i in range(0, len(lyrics), 1000)]
            total_pages = len(chunks)

            class LyricsPaginator(ui.View):
                def __init__(self):
                    super().__init__(timeout=300)
                    self.page = 0
                    self.message = None

                def update_buttons(self):
                    self.prev_button.disabled = self.page == 0
                    self.next_button.disabled = self.page >= total_pages - 1

                def create_embed(self):
                    embed = discord.Embed(
                        title=f"📄 Текст: {title}",
                        description=chunks[self.page],
                        color=0x242429
                    )
                    embed.set_footer(text=f"Страница {self.page + 1}/{total_pages}")
                    return embed

                async def send(self, interaction: discord.Interaction):
                    self.update_buttons()
                    embed = self.create_embed()
                    self.message = await interaction.followup.send(embed=embed, view=self, ephemeral=True)

                async def update(self, interaction: discord.Interaction):
                    self.update_buttons()
                    embed = self.create_embed()
                    await interaction.response.edit_message(embed=embed, view=self)

                @ui.button(emoji=emojis.NK_BACK(), style=discord.ButtonStyle.secondary)
                async def prev_button(self, interaction: discord.Interaction, button: ui.Button):
                    if self.page > 0:
                        self.page -= 1
                        await self.update(interaction)

                @ui.button(emoji=emojis.NK_NEXT(), style=discord.ButtonStyle.secondary)
                async def next_button(self, interaction: discord.Interaction, button: ui.Button):
                    if self.page < total_pages - 1:
                        self.page += 1
                        await self.update(interaction)

            view = LyricsPaginator()
            await view.send(interaction)

        except Exception as e:
            logger.error(f"Lyrics error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при получении текста песни")


    @ui.button(emoji=emojis.NK_HEART(), style=discord.ButtonStyle.secondary, custom_id="music:like")
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
                color=0x242429
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

class QueueView(discord.ui.View):
    def __init__(self, player: HarmonyPlayer, user: discord.User, page: int, total_pages: int):
        super().__init__(timeout=60)
        self.player = player
        self.user = user
        self.page = page
        self.total_pages = total_pages

        # Состояние кнопок
        self.first_page_button.disabled = page <= 1
        self.prev_page_button.disabled = page <= 1
        self.next_page_button.disabled = page >= total_pages
        self.last_page_button.disabled = page >= total_pages

    @discord.ui.button(emoji=emojis.NK_BACKKK(), style=discord.ButtonStyle.secondary, row=0)
    async def first_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.show_queue(interaction, page=1)

    @discord.ui.button(emoji=emojis.NK_BACKK(), style=discord.ButtonStyle.secondary, row=0)
    async def prev_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.show_queue(interaction, page=self.page - 1)

    @discord.ui.button(emoji=emojis.NK_TRASH(), style=discord.ButtonStyle.secondary, row=0)
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            await interaction.response.send_message(
                f"{emojis.ERROR()} Это сообщение доступно только тебе.",
                ephemeral=True
            )
            return
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    @discord.ui.button(emoji=emojis.NK_NEXTT(), style=discord.ButtonStyle.secondary, row=0)
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.show_queue(interaction, page=self.page + 1)

    @discord.ui.button(emoji=emojis.NK_NEXTTT(), style=discord.ButtonStyle.secondary, row=0)
    async def last_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.show_queue(interaction, page=self.total_pages)
