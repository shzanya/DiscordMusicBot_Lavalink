import logging
from typing import Optional, Union
import discord
from discord import ui
from config.constants import get_button_emoji
from ui.embed_now_playing import create_now_playing_embed
from utils.formatters import format_duration
from core.player import HarmonyPlayer
import asyncio
# from commands.admin.settings import apply_guild_emoji_color  # больше не нужен
from services import mongo_service


from .track_select import TrackSelect

logger = logging.getLogger(__name__)

class MusicPlayerView(ui.View):
    @classmethod
    async def create(
        cls,
        player,
        message: Optional[discord.Message] = None,
        requester: Optional[Union[discord.Member, discord.User]] = None,
        color: str = "default",
        custom_emojis: dict = None
    ):
        self = cls.__new__(cls)
        super(MusicPlayerView, self).__init__(timeout=None)
        self.player = player
        self.message = message
        self.requester = requester
        self._is_destroyed = False
        self.player.view = self
        self._emoji_settings = {"color": color or "default", "custom_emojis": custom_emojis or {}}
        guild_id = getattr(
            getattr(self.player, 'guild', None), 'id', None
        )
        # Если параметры не переданы явно — загружаем из БД
        if (not color or color == "default") or (not custom_emojis):
            if guild_id:
                settings = await mongo_service.get_guild_settings(guild_id) or {}
                self._emoji_settings["color"] = settings.get(
                    "color", color or "default"
                )
                self._emoji_settings["custom_emojis"] = settings.get(
                    "custom_emojis", custom_emojis or {}
                )
        track_select = TrackSelect(self.player, self.requester)
        buttons = [item for item in self.children]
        self.clear_items()
        self.add_item(track_select)
        for button in buttons:
            self.add_item(button)
        logger.info(
            "View initialized with children: "
            f"{[item.custom_id for item in self.children if hasattr(item, 'custom_id')]}"
        )
        self._update_all_emojis()
        return self

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

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:shuffle")
    async def shuffle_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji("NK_RANDOM", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
        if not self.player.queue:
            await self._safe_defer_or_respond(interaction, "❌ Очередь пуста для перемешивания")
            return
        try:
            self.player.queue.shuffle()
            await self._safe_defer_or_respond(interaction, f"{button.emoji} Очередь перемешана")
            await self.refresh_select_menu()
        except Exception as e:
            logger.error(f"Shuffle error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при перемешивании очереди")

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:previous")
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji(
            "NK_BACK",
            self._emoji_settings["color"],
            self._emoji_settings["custom_emojis"]
        )
        try:
            if getattr(self.player, "_handling_track_end", False):
                await self._safe_defer_or_respond(
                    interaction,
                    "⏳ Подождите завершения текущего трека..."
                )
                return

            if self.player.current_index <= 0:
                await self._safe_defer_or_respond(
                    interaction,
                    "📜 Нет предыдущих треков в плейлисте"
                )
                return

            await self._safe_defer_or_respond(interaction)
            success = await self.player.play_previous()

            if not success:
                await interaction.followup.send(
                    "❌ Не удалось воспроизвести предыдущий трек",
                    ephemeral=True
                )
                return

            await self.refresh_select_menu()

        except Exception as e:
            logger.error(f"Previous track error: {e}")
            await self._safe_defer_or_respond(
                interaction,
                "⚠️ Ошибка при переходе к предыдущему треку"
            )

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:pause")
    async def pause_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji(
            "NK_MUSICPLAY",
            self._emoji_settings["color"],
            self._emoji_settings["custom_emojis"]
        )
        try:
            # Use player.now_playing_message if self.message is None
            if not self.message and self.player.now_playing_message:
                self.message = self.player.now_playing_message
                logger.debug(
                    "Updated self.message from player.now_playing_message in pause_button"
                )

            if not self.message:
                logger.warning(
                    "self.message is None during pause_button, attempting to create new message"
                )
                if self.player.current and self.player.text_channel:
                    embed = create_now_playing_embed(
                        self.player.current,
                        self.player,
                        self.requester or interaction.user
                    )

                    self.message = await self.player.text_channel.send(
                        embed=embed, view=self
                    )
                    self.player.now_playing_message = self.message
                    logger.info("Created new now_playing_message in pause_button")
                else:
                    await self._safe_defer_or_respond(
                        interaction,
                        "⚠️ Не удалось обновить интерфейс: нет текущего трека или канала"
                    )
                    return

            is_paused = getattr(self.player, 'paused', False)
            await self.player.pause(not is_paused)
            button.emoji = get_button_emoji(
                "NK_MUSICPAUSE",
                self._emoji_settings["color"],
                self._emoji_settings["custom_emojis"]
            ) if not is_paused else get_button_emoji(
                "NK_MUSICPLAY",
                self._emoji_settings["color"],
                self._emoji_settings["custom_emojis"]
            )
            await self.message.edit(view=self)
            if self.player.current:
                embed = create_now_playing_embed(
                    self.player.current,
                    self.player,
                    self.requester or interaction.user
                )

                await self.message.edit(embed=embed, view=self)
            await self._safe_defer_or_respond(interaction)
        except Exception as e:
            logger.error(f"Pause/resume error: {e}")
            await self._safe_defer_or_respond(
                interaction,
                "⚠️ Ошибка при изменении воспроизведения"
            )

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:skip")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji(
            "NK_NEXT",
            self._emoji_settings["color"],
            self._emoji_settings["custom_emojis"]
        )
        try:
            if getattr(self.player, "_handling_track_end", False):
                await self._safe_defer_or_respond(
                    interaction,
                    "⏳ Подождите завершения текущего трека..."
                )
                return

            if self.player.current_index >= len(self.player.playlist) - 1:
                await self._safe_defer_or_respond(
                    interaction,
                    "📭 В плейлисте нет треков для пропуска"
                )
                return

            await self._safe_defer_or_respond(interaction)
            await self.player.skip()
            await self.refresh_select_menu()

        except Exception as e:
            logger.error(f"Skip error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при пропуске трека")

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:loop")
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji("NK_POVTOR", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
        try:
            current_loop = getattr(self.player, "loop", False)
            self.player.loop = not current_loop

            status = "включен" if self.player.loop else "выключен"
            await self._safe_defer_or_respond(interaction, f"{button.emoji} Повтор {status}")
        except Exception as e:
            logger.error(f"Loop toggle error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при переключении повтора")

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:seek")
    async def seek_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji("NK_TIME", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
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

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:volume")
    async def volume_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji("NK_VOLUME", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
        try:
            volume = getattr(self.player, "volume", 100)
            embed = discord.Embed(
                title=f"{button.emoji} Громкость",
                description=f"**Текущая громкость:** {volume}%",
                color=0x242429
            )
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Volume info error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при получении информации о громкости")

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:stop")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji("NK_LEAVE", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
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

    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:text")
    async def lyrics_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji("NK_TEXT", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
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

                @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary)
                async def prev_button(self, interaction: discord.Interaction, button: ui.Button):
                    if self.page > 0:
                        self.page -= 1
                        await self.update(interaction)

                @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary)
                async def next_button(self, interaction: discord.Interaction, button: ui.Button):
                    if self.page < total_pages - 1:
                        self.page += 1
                        await self.update(interaction)

            view = LyricsPaginator()
            await view.send(interaction)

        except Exception as e:
            logger.error(f"Lyrics error: {e}")
            await self._safe_defer_or_respond(interaction, "⚠️ Ошибка при получении текста песни")


    @ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:like")
    async def like_button(self, interaction: discord.Interaction, button: ui.Button) -> None:
        button.label = None
        button.emoji = get_button_emoji("NK_HEART", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
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

    def _update_all_emojis(self):
        emoji_map = {
            "music:shuffle": "NK_RANDOM",
            "music:previous": "NK_BACK",
            "music:pause": "NK_MUSICPLAY",
            "music:skip": "NK_NEXT",
            "music:loop": "NK_POVTOR",
            "music:seek": "NK_TIME",
            "music:volume": "NK_VOLUME",
            "music:stop": "NK_LEAVE",
            "music:text": "NK_TEXT",
            "music:like": "NK_HEART",
        }
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                emoji_name = emoji_map.get(getattr(item, 'custom_id', None))
                if emoji_name:
                    item.emoji = get_button_emoji(
                        emoji_name,
                        self._emoji_settings["color"],
                        self._emoji_settings["custom_emojis"]
                    )
                    item.label = None

class QueueView(discord.ui.View):
    @classmethod
    async def create(
        cls,
        player: HarmonyPlayer,
        user: discord.User,
        page: int,
        total_pages: int,
        color: str = "default",
        custom_emojis: dict = None
    ):
        self = cls.__new__(cls)
        super(QueueView, self).__init__(timeout=60)
        self.player = player
        self.user = user
        self.page = page
        self.total_pages = total_pages
        self._emoji_settings = {"color": color or "default", "custom_emojis": custom_emojis or {}}
        guild_id = getattr(
            getattr(self.player, 'guild', None), 'id', None
        )
        if (not color or color == "default") or (not custom_emojis):
            if guild_id:
                settings = await mongo_service.get_guild_settings(guild_id) or {}
                self._emoji_settings["color"] = settings.get(
                    "color", color or "default"
                )
                self._emoji_settings["custom_emojis"] = settings.get(
                    "custom_emojis", custom_emojis or {}
                )
        # Состояние кнопок
        self.first_page_button.disabled = page <= 1
        self.prev_page_button.disabled = page <= 1
        self.next_page_button.disabled = page >= total_pages
        self.last_page_button.disabled = page >= total_pages
        return self

    @discord.ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:shuffle")
    async def first_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = None
        button.emoji = get_button_emoji("NK_BACKKK", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
        await self.player.show_queue(interaction, page=1)

    @discord.ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:previous")
    async def prev_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = None
        button.emoji = get_button_emoji("NK_BACKK", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
        await self.player.show_queue(interaction, page=self.page - 1)

    @discord.ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:skip")
    async def clear_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = None
        button.emoji = get_button_emoji("NK_TRASH", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
        if interaction.user != self.user:
            await interaction.response.send_message(
                f"{get_button_emoji('ERROR', self._emoji_settings['color'], self._emoji_settings['custom_emojis'])} Это сообщение доступно только тебе.",
                ephemeral=True
            )
            return
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    @discord.ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:next")
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = None
        button.emoji = get_button_emoji("NK_NEXTT", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
        await self.player.show_queue(interaction, page=self.page + 1)

    @discord.ui.button(emoji=None, label='•', style=discord.ButtonStyle.secondary, custom_id="music:last")
    async def last_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = None
        button.emoji = get_button_emoji("NK_NEXTTT", self._emoji_settings["color"], self._emoji_settings["custom_emojis"])
        await self.player.show_queue(interaction, page=self.total_pages)

    def _update_all_emojis(self):
        emoji_map = {
            "music:shuffle": "NK_BACKKK",
            "music:previous": "NK_BACKK",
            "music:skip": "NK_TRASH",
            "music:next": "NK_NEXTT",
            "music:last": "NK_NEXTTT",
        }
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                emoji_name = emoji_map.get(getattr(item, 'custom_id', None))
                if emoji_name:
                    item.emoji = get_button_emoji(
                        emoji_name,
                        self._emoji_settings["color"],
                        self._emoji_settings["custom_emojis"]
                    )
                    item.label = None
