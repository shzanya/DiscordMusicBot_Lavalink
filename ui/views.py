from typing import Optional, Union
import discord
from discord import ui
from config.constants import get_button_emoji
from ui.embed_now_playing import create_now_playing_embed
from ui.base_view import BaseEmojiView, EmojiSettings
from utils.formatters import format_duration
from utils.validators import check_player_ownership
from core.player import HarmonyPlayer, LoopMode
from services import mongo_service
from services.lyrics import LyricsService
import logging
# from commands.admin.settings import apply_guild_emoji_color  # больше не нужен


from .track_select import TrackSelect

logger = logging.getLogger(__name__)


class MusicPlayerView(BaseEmojiView):
    def __init__(
        self,
        player,
        message: Optional[discord.Message] = None,
        requester: Optional[Union[discord.Member, discord.User]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.player = player
        self.message = message
        self.requester = requester
        self._is_destroyed = False
        self.player.view = self

        # Сначала добавляем TrackSelect (будет отображаться выше кнопок)
        track_select = TrackSelect(self.player, self.requester)
        self.add_item(track_select)

        # Затем создаем все кнопки в правильном порядке
        # 1. Shuffle (перемешать треки)
        shuffle_button = ui.Button(
            emoji=self.get_emoji("NK_RANDOM"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:shuffle",
        )
        shuffle_button.callback = self.shuffle_button_callback
        self.add_item(shuffle_button)

        # 2. Previous
        previous_button = ui.Button(
            emoji=self.get_emoji("NK_BACK"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:previous",
        )
        previous_button.callback = self.previous_button_callback
        self.add_item(previous_button)

        # 3. Pause (центральная кнопка)
        is_paused = getattr(self.player, "paused", False)
        initial_emoji_name = "NK_MUSICPAUSE" if is_paused else "NK_MUSICPLAY"
        pause_button = ui.Button(
            emoji=self.get_emoji(initial_emoji_name),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:pause",
        )
        pause_button.callback = self.pause_button_callback
        self.add_item(pause_button)

        # 4. Skip
        skip_button = ui.Button(
            emoji=self.get_emoji("NK_NEXT"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:skip",
        )
        skip_button.callback = self.skip_button_callback
        self.add_item(skip_button)

        # 5. Loop (цикл трека/очереди)
        loop_button = ui.Button(
            emoji=self.get_emoji("NK_POVTOR"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:loop",
        )
        loop_button.callback = self.loop_button_callback
        self.add_item(loop_button)

        # 6. Seek (текущее место + 3 подкнопки)
        seek_button = ui.Button(
            emoji=self.get_emoji("NK_TIME"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:seek",
        )
        seek_button.callback = self.seek_button_callback
        self.add_item(seek_button)

        # 7. Volume (громкость + 2 подкнопки)
        volume_button = ui.Button(
            emoji=self.get_emoji("NK_VOLUME"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:volume",
        )
        volume_button.callback = self.volume_button_callback
        self.add_item(volume_button)

        # 8. Stop
        stop_button = ui.Button(
            emoji=self.get_emoji("NK_LEAVE"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:stop",
        )
        stop_button.callback = self.stop_button_callback
        self.add_item(stop_button)

        # 9. Text
        text_button = ui.Button(
            emoji=self.get_emoji("NK_TEXT"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:text",
        )
        text_button.callback = self.text_button_callback
        self.add_item(text_button)

        # 10. Like
        like_button = ui.Button(
            emoji=self.get_emoji("NK_HEART"),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:like",
        )
        like_button.callback = self.like_button_callback
        self.add_item(like_button)

        logger.info(
            "View initialized with children: "
            f"{[item.custom_id for item in self.children if hasattr(item, 'custom_id')]}"
        )

    def _setup_emoji_mapping(self):
        """Настройка маппинга эмодзи для MusicPlayerView"""
        self._emoji_map = {
            "music:shuffle": "NK_RANDOM",
            "music:previous": "NK_BACK",
            "music:skip": "NK_NEXT",
            "music:loop": "NK_POVTOR",
            "music:seek": "NK_TIME",
            "music:volume": "NK_VOLUME",
            "music:stop": "NK_LEAVE",
            "music:text": "NK_TEXT",
            "music:like": "NK_HEART",
        }

    @classmethod
    async def create(
        cls,
        player,
        message: Optional[discord.Message] = None,
        requester: Optional[Union[discord.Member, discord.User]] = None,
        color: str = "default",
        custom_emojis: dict = None,
        **kwargs,
    ):
        # Создаем настройки эмодзи
        emoji_settings = EmojiSettings(color=color, custom_emojis=custom_emojis)

        # Если параметры не переданы явно — загружаем из БД
        if (not color or color == "default") or (not custom_emojis):
            guild_id = getattr(getattr(player, "guild", None), "id", None)
            if guild_id:
                emoji_settings = await EmojiSettings.from_guild(guild_id)

        # Создаем экземпляр с настройками эмодзи
        instance = cls(
            player=player,
            message=message,
            requester=requester,
            emoji_settings=emoji_settings,
            **kwargs,
        )

        # Инициализируем эмодзи
        await instance._initialize_emojis()

        return instance

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
        self, interaction: discord.Interaction, error: Exception, item: ui.Item
    ) -> None:
        logger.debug(f"View error in {item.custom_id}: {error}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Произошла ошибка при выполнении действия", ephemeral=True
                )
        except Exception as e:
            logger.debug(f"Error handling view error: {e}")

    def destroy(self) -> None:
        """Уничтожает view и отключает все кнопки."""
        self._is_destroyed = True
        for item in self.children:
            item.disabled = True
        if self.player:
            self.player.view = None

    async def refresh_select_menu(self) -> None:
        """Обновляет меню выбора треков."""
        try:
            for item in self.children:
                if isinstance(item, TrackSelect):
                    await item.update()
                    break
        except Exception as e:
            logger.debug(f"Error refreshing select menu: {e}")

    async def update_track_select(self) -> None:
        """Обновляет меню выбора треков с новыми данными."""
        try:
            for item in self.children:
                if isinstance(item, TrackSelect):
                    await item.update()
                    break
        except Exception as e:
            logger.debug(f"Error updating track select: {e}")

    async def _safe_defer_or_respond(
        self,
        interaction: discord.Interaction,
        message: str = None,
        ephemeral: bool = True,
    ) -> None:
        try:
            if message:
                await interaction.response.send_message(message, ephemeral=ephemeral)
            else:
                await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            pass
        except Exception as e:
            logger.debug(f"Error in interaction response: {e}")

    async def shuffle_button_callback(self, interaction: discord.Interaction) -> None:
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

            if len(self.player.playlist) < 2:
                await self._safe_defer_or_respond(
                    interaction, "❌ Недостаточно треков для перемешивания"
                )
                return

            import random

            # Перемешиваем плейлист, исключая текущий трек
            current_track = self.player.current
            other_tracks = [t for t in self.player.playlist if t != current_track]
            random.shuffle(other_tracks)

            # Восстанавливаем порядок: текущий трек + перемешанные остальные
            self.player.playlist = (
                [current_track] + other_tracks if current_track else other_tracks
            )

            await self._safe_defer_or_respond(
                interaction, "🔀 Все треки были успешно перемешаны"
            )
            await self.update_track_select()
        except Exception as e:
            logger.debug(f"Shuffle error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при перемешивании очереди"
            )

    async def previous_button_callback(self, interaction: discord.Interaction) -> None:
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

            if getattr(self.player, "_handling_track_end", False):
                await self._safe_defer_or_respond(
                    interaction, "⏳ Подождите завершения текущего трека..."
                )
                return

            if self.player.current_index <= 0:
                await self._safe_defer_or_respond(
                    interaction, "📜 Нет предыдущих треков в плейлисте"
                )
                return

            await self._safe_defer_or_respond(interaction)
            success = await self.player.play_previous()

            if not success:
                await interaction.followup.send(
                    "❌ Не удалось воспроизвести предыдущий трек", ephemeral=True
                )
                return

            await self.update_track_select()

        except Exception as e:
            logger.debug(f"Previous track error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при переходе к предыдущему треку"
            )

    async def skip_button_callback(self, interaction: discord.Interaction) -> None:
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

            if getattr(self.player, "_handling_track_end", False):
                await self._safe_defer_or_respond(
                    interaction, "⏳ Подождите завершения текущего трека..."
                )
                return

            if self.player.current_index >= len(self.player.playlist) - 1:
                await self._safe_defer_or_respond(
                    interaction, "📭 В плейлисте нет треков для пропуска"
                )
                return

            await self._safe_defer_or_respond(interaction)
            await self.player.skip()
            await self.update_track_select()

        except Exception as e:
            logger.debug(f"Skip error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при пропуске трека"
            )

    async def loop_button_callback(self, interaction: discord.Interaction) -> None:
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

            # Переключаем режим цикла
            if self.player.state.loop_mode == LoopMode.NONE:
                self.player.state.loop_mode = LoopMode.TRACK
                message = "🔁 Вы включили повтор данного трека"
            elif self.player.state.loop_mode == LoopMode.TRACK:
                self.player.state.loop_mode = LoopMode.QUEUE
                message = "🔁 Вы включили повтор очереди треков"
            else:  # LoopMode.QUEUE
                self.player.state.loop_mode = LoopMode.NONE
                message = "🔁 Вы отключили повтор треков"

            await self._safe_defer_or_respond(interaction, message)
        except Exception as e:
            logger.debug(f"Loop toggle error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при переключении повтора"
            )

    async def seek_button_callback(self, interaction: discord.Interaction) -> None:
        # Проверяем владельца плеера
        if not await check_player_ownership(interaction, self.player):
            return

        try:
            if not self.player.current:
                await self._safe_defer_or_respond(
                    interaction, "❌ Нет воспроизводимого трека"
                )
                return

            position = getattr(self.player, "position", 0)
            duration = getattr(self.player.current, "length", 0)
            dur_formatted = format_duration(duration)

            def create_embed(pos, parent_view):
                pos_formatted = format_duration(pos)
                # Получаем цвет из настроек
                color = 0x242429  # дефолтный цвет
                if (
                    hasattr(parent_view.emoji_settings, "color")
                    and parent_view.emoji_settings.color
                ):
                    try:
                        if not isinstance(parent_view.emoji_settings.color, str):
                            color = parent_view.emoji_settings.color
                    except Exception:
                        color = 0x242429

                return discord.Embed(
                    title="Управление позицией",
                    description=f"**Текущая позиция:**\n{pos_formatted}\n**Длительность трека:**\n{dur_formatted}",
                    color=color,
                )

            # Создаем view с подкнопками
            class SeekView(ui.View):
                def __init__(self, player, original_interaction, parent_view):
                    super().__init__(timeout=60)
                    self.player = player
                    self.original_interaction = original_interaction
                    self.parent_view = parent_view
                    self.seek_message = None  # Сохраняем ссылку на локальное сообщение

                async def update_embed(self):
                    """Обновляет только локальный эмбед управления позицией"""
                    if not self.seek_message:
                        return

                    try:
                        current_pos = getattr(self.player, "position", 0)
                        updated_embed = create_embed(current_pos, self.parent_view)
                        await self.seek_message.edit(embed=updated_embed, view=self)
                    except Exception as e:
                        logger.error(f"Error updating seek embed: {e}")

                @ui.button(
                    label="Назад на 10с", style=discord.ButtonStyle.secondary, row=0
                )
                async def rewind_10(
                    self, interaction: discord.Interaction, button: ui.Button
                ):
                    if not await check_player_ownership(interaction, self.player):
                        return

                    try:
                        current_pos = getattr(self.player, "position", 0)
                        new_pos = max(0, current_pos - 10000)  # 10 секунд назад
                        await self.player.seek(new_pos)

                        await interaction.response.defer()
                        await self.update_embed()

                    except Exception as e:
                        logger.error(f"Rewind error: {e}")
                        await interaction.response.send_message(
                            "⚠️ Ошибка при перемотке", ephemeral=True
                        )

                @ui.button(
                    label="Вперед на 10с", style=discord.ButtonStyle.secondary, row=0
                )
                async def forward_10(
                    self, interaction: discord.Interaction, button: ui.Button
                ):
                    if not await check_player_ownership(interaction, self.player):
                        return

                    try:
                        current_pos = getattr(self.player, "position", 0)
                        duration = getattr(self.player.current, "length", 0)
                        new_pos = min(duration, current_pos + 10000)  # 10 секунд вперед
                        await self.player.seek(new_pos)

                        await interaction.response.defer()
                        await self.update_embed()

                    except Exception as e:
                        logger.error(f"Forward error: {e}")
                        await interaction.response.send_message(
                            "⚠️ Ошибка при перемотке", ephemeral=True
                        )

                @ui.button(
                    label="Вернуться в начало трэка",
                    style=discord.ButtonStyle.secondary,
                    row=1,
                )
                async def restart(
                    self, interaction: discord.Interaction, button: ui.Button
                ):
                    if not await check_player_ownership(interaction, self.player):
                        return

                    try:
                        await self.player.seek(0)

                        await interaction.response.defer()
                        await self.update_embed()

                    except Exception as e:
                        logger.error(f"Restart error: {e}")
                        await interaction.response.send_message(
                            "⚠️ Ошибка при перезапуске", ephemeral=True
                        )

            embed = create_embed(position, self)
            view = SeekView(self.player, interaction, self)

            # Устанавливаем кастомные эмодзи для кнопок
            for item in view.children:
                if isinstance(item, discord.ui.Button):
                    if item.label == "Назад на 10с":
                        emoji = self.get_emoji("NK_BACK")
                        if emoji and emoji != "❓":
                            item.emoji = emoji
                    elif item.label == "Вперед на 10с":
                        emoji = self.get_emoji("NK_NEXT")
                        if emoji and emoji != "❓":
                            item.emoji = emoji
                    elif item.label == "Вернуться в начало трэка":
                        emoji = self.get_emoji("NK_REVIVE")
                        if emoji and emoji != "❓":
                            item.emoji = emoji

            await self._safe_defer_or_respond(interaction)
            # Сохраняем ссылку на локальное сообщение
            view.seek_message = await interaction.followup.send(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"Seek info error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при получении информации о позиции"
            )

    def _create_progress_bar(
        self, position: int, duration: int, length: int = 20
    ) -> str:
        if duration <= 0:
            return "▬" * length
        progress = min(position / duration, 1.0)
        filled = int(progress * length)
        bar = "▰" * filled + "▱" * (length - filled)
        return f"`{bar}`"

    async def volume_button_callback(self, interaction: discord.Interaction) -> None:
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

            # Загружаем текущую громкость из БД
            if self.player.text_channel and self.player.text_channel.guild:
                guild_id = self.player.text_channel.guild.id
                current_volume = await mongo_service.get_guild_volume(guild_id)
            else:
                current_volume = getattr(self.player, "volume", 100)

            embed = discord.Embed(
                title="🔊 Управление громкостью",
                description=f"**Текущая громкость:** {current_volume}%",
                color=0x242429,
            )

            # Создаем view с подкнопками
            class VolumeView(ui.View):
                def __init__(self, player, parent_view):
                    super().__init__(timeout=60)
                    self.player = player
                    self.parent_view = parent_view
                    self.volume_message = (
                        None  # Сохраняем ссылку на локальное сообщение
                    )

                async def update_volume_embed(self, new_volume: int):
                    """Обновляет локальный эмбед управления громкостью"""
                    if not self.volume_message:
                        return

                    try:
                        # Получаем цвет из настроек
                        color = 0x242429  # дефолтный цвет
                        if (
                            hasattr(self.parent_view.emoji_settings, "color")
                            and self.parent_view.emoji_settings.color
                        ):
                            try:
                                if not isinstance(
                                    self.parent_view.emoji_settings.color, str
                                ):
                                    color = self.parent_view.emoji_settings.color
                            except Exception:
                                color = 0x242429

                        embed = discord.Embed(
                            title="🔊 Управление громкостью",
                            description=f"**Текущая громкость:** {new_volume}%",
                            color=color,
                        )
                        await self.volume_message.edit(embed=embed, view=self)
                    except Exception as e:
                        logger.debug(f"Error updating volume embed: {e}")

                @ui.button(
                    label="-10%", style=discord.ButtonStyle.secondary, emoji="🔉"
                )
                async def decrease_volume(
                    self, interaction: discord.Interaction, button: ui.Button
                ):
                    try:
                        if not await check_player_ownership(interaction, self.player):
                            return
                        current_volume = getattr(self.player, "volume", 100)
                        new_volume = max(0, current_volume - 10)
                        self.player.volume = new_volume
                        await interaction.response.defer()
                        await self.update_volume_embed(new_volume)
                    except Exception as e:
                        logger.debug(f"Volume decrease error: {e}")
                        await interaction.response.send_message(
                            "⚠️ Ошибка при изменении громкости", ephemeral=True
                        )

                @ui.button(
                    label="+10%", style=discord.ButtonStyle.secondary, emoji="🔊"
                )
                async def increase_volume(
                    self, interaction: discord.Interaction, button: ui.Button
                ):
                    try:
                        if not await check_player_ownership(interaction, self.player):
                            return
                        current_volume = getattr(self.player, "volume", 100)
                        new_volume = min(200, current_volume + 10)
                        self.player.volume = new_volume
                        await interaction.response.defer()
                        await self.update_volume_embed(new_volume)
                    except Exception as e:
                        logger.debug(f"Volume increase error: {e}")
                        await interaction.response.send_message(
                            "⚠️ Ошибка при изменении громкости", ephemeral=True
                        )

                @ui.button(
                    label="Установить", style=discord.ButtonStyle.secondary, emoji="⚙️"
                )
                async def set_volume(
                    self, interaction: discord.Interaction, button: ui.Button
                ):
                    try:
                        if not await check_player_ownership(interaction, self.player):
                            return

                        class VolumeModal(ui.Modal, title="Установить громкость"):
                            def __init__(self, player, volume_view):
                                super().__init__(title="Установить громкость")
                                self.player = player
                                self.volume_view = volume_view

                            volume_input = ui.TextInput(
                                label="Громкость (0-200%)",
                                placeholder="Введите значение от 0 до 200",
                                min_length=1,
                                max_length=3,
                                default="100",
                            )

                            async def on_submit(
                                self, modal_interaction: discord.Interaction
                            ):
                                try:
                                    volume = int(self.volume_input.value)
                                    if volume < 0 or volume > 200:
                                        await modal_interaction.response.send_message(
                                            "❌ Громкость должна быть от 0 до 200%",
                                            ephemeral=True,
                                        )
                                        return
                                    self.player.volume = volume
                                    await self.volume_view.update_volume_embed(volume)
                                    await modal_interaction.response.send_message(
                                        f"🔊 Громкость установлена на {volume}%",
                                        ephemeral=True,
                                    )
                                except ValueError:
                                    await modal_interaction.response.send_message(
                                        "❌ Введите корректное число", ephemeral=True
                                    )

                        await interaction.response.send_modal(
                            VolumeModal(self.player, self)
                        )
                    except Exception as e:
                        logger.debug(f"Volume modal error: {e}")
                        await interaction.response.send_message(
                            "⚠️ Ошибка при установке громкости", ephemeral=True
                        )

            # Применяем кастомные эмодзи к кнопкам
            view = VolumeView(self.player, self)

            # Устанавливаем кастомные эмодзи для кнопок
            for item in view.children:
                if isinstance(item, discord.ui.Button):
                    if item.label == "-10%":
                        emoji = self.get_emoji("NK_VOLUM_M")
                        if emoji and emoji != "❓":
                            item.emoji = emoji
                    elif item.label == "+10%":
                        emoji = self.get_emoji("NK_VOLUM_P")
                        if emoji and emoji != "❓":
                            item.emoji = emoji
                    elif item.label == "Установить":
                        emoji = self.get_emoji("NK_VOLUME")
                        if emoji and emoji != "❓":
                            item.emoji = emoji

            await self._safe_defer_or_respond(interaction)
            # Сохраняем ссылку на локальное сообщение
            view.volume_message = await interaction.followup.send(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.debug(f"Volume info error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при получении информации о громкости"
            )

    async def stop_button_callback(self, interaction: discord.Interaction) -> None:
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

            await self._safe_defer_or_respond(interaction)
            await self.player.cleanup_disconnect()
            await interaction.followup.send(
                "⏹️ Воспроизведение остановлено", ephemeral=True
            )
        except Exception as e:
            logger.debug(f"Stop error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при остановке воспроизведения"
            )

    async def text_button_callback(self, interaction: discord.Interaction) -> None:
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

            if not self.player.current:
                await self._safe_defer_or_respond(
                    interaction, "❌ Нет воспроизводимого трека"
                )
                return
            track = self.player.current
            title = track.title
            artist = getattr(track, "author", "")
            await interaction.response.defer(ephemeral=True)
            lyrics_service = LyricsService()
            lyrics = await lyrics_service.get_lyrics(title, artist, url=track.uri)
            if not lyrics:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title=f"{self.get_emoji('NK_TEXT')} ❌ Текст не найден",
                        description=f"Не удалось найти текст для **{title}**.",
                        color=0x242429,
                    ),
                    ephemeral=True,
                )
                return
            chunks = [lyrics[i : i + 1000] for i in range(0, len(lyrics), 1000)]
            total_pages = len(chunks)
            emoji = self.get_emoji("NK_TEXT")
            # Конвертируем цвет в число
            color = 0x242429  # дефолтный цвет
            if hasattr(self.emoji_settings, "color") and self.emoji_settings.color:
                try:
                    if isinstance(self.emoji_settings.color, str):
                        # Если цвет - строка, используем дефолтный
                        color = 0x242429
                    else:
                        color = self.emoji_settings.color
                except Exception:
                    color = 0x242429

            # Получаем кастомные эмодзи для кнопок
            prev_emoji = self.get_emoji("NK_BACKK")
            next_emoji = self.get_emoji("NK_NEXTT")

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
                        title=f"{emoji} Текст: {title}",
                        description=chunks[self.page],
                        color=color,
                    )
                    embed.set_footer(text=f"Страница {self.page + 1}/{total_pages}")
                    return embed

                async def send(self, interaction: discord.Interaction):
                    self.update_buttons()
                    embed = self.create_embed()
                    self.message = await interaction.followup.send(
                        embed=embed, view=self, ephemeral=True
                    )

                async def update(self, interaction: discord.Interaction):
                    self.update_buttons()
                    embed = self.create_embed()
                    await interaction.response.edit_message(embed=embed, view=self)

                @ui.button(emoji=prev_emoji, style=discord.ButtonStyle.secondary)
                async def prev_button(
                    self, interaction: discord.Interaction, button: ui.Button
                ):
                    if self.page > 0:
                        self.page -= 1
                        await self.update(interaction)

                @ui.button(emoji=next_emoji, style=discord.ButtonStyle.secondary)
                async def next_button(
                    self, interaction: discord.Interaction, button: ui.Button
                ):
                    if self.page < total_pages - 1:
                        self.page += 1
                        await self.update(interaction)

            view = LyricsPaginator()
            await view.send(interaction)
        except Exception as e:
            logger.debug(f"Lyrics error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при получении текста песни"
            )

    async def like_button_callback(self, interaction: discord.Interaction) -> None:
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

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
                color=0x242429,
            )
            embed.add_field(
                name="Популярные плейлисты",
                value="• `Любимые треки`\n• `Избранное`\n• `Мой плейлист`",
                inline=False,
            )
            await self._safe_defer_or_respond(interaction)
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.debug(f"Like button error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при добавлении трека в плейлист"
            )

    async def pause_button_callback(self, interaction: discord.Interaction) -> None:
        """Callback для кнопки pause"""
        try:
            # Проверяем владельца плеера
            if not await check_player_ownership(interaction, self.player):
                return

            # Use player.now_playing_message if self.message is None
            if not self.message and self.player.now_playing_message:
                self.message = self.player.now_playing_message
                logger.debug(
                    "Updated self.message from player.now_playing_message in pause_button"
                )

            if not self.message:
                logger.debug(
                    "self.message is None during pause_button, attempting to create new message"
                )
                if self.player.current and self.player.text_channel:
                    # Безопасно получаем цвет
                    color = 0x242429  # дефолтный цвет
                    if (
                        hasattr(self.emoji_settings, "color")
                        and self.emoji_settings.color
                    ):
                        try:
                            if isinstance(self.emoji_settings.color, str):
                                color = 0x242429
                            else:
                                color = self.emoji_settings.color
                        except Exception:
                            color = 0x242429

                    embed = create_now_playing_embed(
                        self.player.current,
                        self.player,
                        self.requester or interaction.user,
                        color=color,
                        custom_emojis=self.emoji_settings.custom_emojis,
                    )

                    self.message = await self.player.text_channel.send(
                        embed=embed, view=self
                    )
                    self.player.now_playing_message = self.message
                    logger.info("Created new now_playing_message in pause_button")
                else:
                    await self._safe_defer_or_respond(
                        interaction,
                        "⚠️ Не удалось обновить интерфейс: нет текущего трека или канала",
                    )
                    return

            is_paused = getattr(self.player, "paused", False)
            await self.player.pause(not is_paused)

            # Обновляем эмодзи кнопки pause
            new_emoji_name = "NK_MUSICPAUSE" if not is_paused else "NK_MUSICPLAY"
            self.update_emoji("music:pause", new_emoji_name)

            await self.message.edit(view=self)
            if self.player.current:
                # Безопасно получаем цвет
                color = 0x242429  # дефолтный цвет
                if hasattr(self.emoji_settings, "color") and self.emoji_settings.color:
                    try:
                        if isinstance(self.emoji_settings.color, str):
                            color = 0x242429
                        else:
                            color = self.emoji_settings.color
                    except Exception:
                        color = 0x242429

                embed = create_now_playing_embed(
                    self.player.current,
                    self.player,
                    self.requester or interaction.user,
                    color=color,
                    custom_emojis=self.emoji_settings.custom_emojis,
                )
                await self.message.edit(embed=embed, view=self)

            await self._safe_defer_or_respond(
                interaction,
                "⏸️ Воспроизведение приостановлено"
                if not is_paused
                else "▶️ Воспроизведение возобновлено",
            )
        except Exception as e:
            logger.debug(f"Pause button error: {e}")
            await self._safe_defer_or_respond(
                interaction, "⚠️ Ошибка при управлении воспроизведением"
            )


class QueueView(BaseEmojiView):
    def __init__(
        self,
        player: HarmonyPlayer,
        user: discord.User,
        page: int,
        total_pages: int,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.player = player
        self.user = user
        self.page = page
        self.total_pages = total_pages
        self.update_page_buttons()
        # Обновляем эмодзи после инициализации
        if hasattr(self, "_emoji_map"):
            self.update_queue_emojis()

    def update_page_buttons(self):
        """Отключает кнопки страниц, если нельзя перейти"""
        for item in self.children:
            if hasattr(item, "custom_id"):
                if item.custom_id == "music:shuffle":
                    item.disabled = self.page == 1
                elif item.custom_id == "music:previous":
                    item.disabled = self.page == 1
                elif item.custom_id == "music:next":
                    item.disabled = self.page == self.total_pages
                elif item.custom_id == "music:last":
                    item.disabled = self.page == self.total_pages

    def update_queue_emojis(self):
        """Обновляет эмодзи кнопок на кастомные"""
        for item in self.children:
            if hasattr(item, "custom_id"):
                if item.custom_id == "music:shuffle":
                    item.emoji = self.get_emoji("NK_BACKKK")
                elif item.custom_id == "music:previous":
                    item.emoji = self.get_emoji("NK_BACKK")
                elif item.custom_id == "music:skip":
                    item.emoji = self.get_emoji("NK_TRASH")
                elif item.custom_id == "music:next":
                    item.emoji = self.get_emoji("NK_NEXTT")
                elif item.custom_id == "music:last":
                    item.emoji = self.get_emoji("NK_NEXTTT")

    def _setup_emoji_mapping(self):
        """Настройка маппинга эмодзи для QueueView"""
        self._emoji_map = {
            "music:shuffle": "NK_BACKKK",
            "music:previous": "NK_BACKK",
            "music:skip": "NK_TRASH",
            "music:next": "NK_NEXTT",
            "music:last": "NK_NEXTTT",
        }

    @classmethod
    async def create(
        cls,
        player: HarmonyPlayer,
        user: discord.User,
        page: int,
        total_pages: int,
        color: str = "default",
        custom_emojis: dict = None,
        **kwargs,
    ):
        emoji_settings = EmojiSettings(color=color, custom_emojis=custom_emojis)
        if (not color or color == "default") or (not custom_emojis):
            guild_id = getattr(getattr(player, "guild", None), "id", None)
            if guild_id:
                emoji_settings = await EmojiSettings.from_guild(guild_id)
        instance = cls(
            player=player,
            user=user,
            page=page,
            total_pages=total_pages,
            emoji_settings=emoji_settings,
            **kwargs,
        )
        await instance._initialize_emojis()
        instance.update_page_buttons()
        instance.update_queue_emojis()
        return instance

    @discord.ui.button(
        emoji="⏮️",
        label=None,
        style=discord.ButtonStyle.secondary,
        custom_id="music:shuffle",
    )
    async def first_page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not await check_player_ownership(interaction, self.player):
            return
        self.page = 1
        self.update_page_buttons()
        await self.player.show_queue(interaction, page=1, edit=True, view=self)

    @discord.ui.button(
        emoji="◀️",
        label=None,
        style=discord.ButtonStyle.secondary,
        custom_id="music:previous",
    )
    async def prev_page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not await check_player_ownership(interaction, self.player):
            return
        if self.page > 1:
            self.page -= 1
        self.update_page_buttons()
        await self.player.show_queue(interaction, page=self.page, edit=True, view=self)

    @discord.ui.button(
        emoji="🗑️",
        label=None,
        style=discord.ButtonStyle.secondary,
        custom_id="music:skip",
    )
    async def clear_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not await check_player_ownership(interaction, self.player):
            return
        if interaction.user != self.user:
            # Безопасно получаем цвет как строку
            color = "default"
            if hasattr(self.emoji_settings, "color") and self.emoji_settings.color:
                if isinstance(self.emoji_settings.color, str):
                    color = self.emoji_settings.color
                else:
                    color = "default"

            await interaction.response.send_message(
                f"{get_button_emoji('ERROR', color, self.emoji_settings.custom_emojis)} Это сообщение доступно только тебе.",
                ephemeral=True,
            )
            return
        try:
            await interaction.response.defer()
            await interaction.delete_original_response()
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    @discord.ui.button(
        emoji="▶️",
        label=None,
        style=discord.ButtonStyle.secondary,
        custom_id="music:next",
    )
    async def next_page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not await check_player_ownership(interaction, self.player):
            return
        if self.page < self.total_pages:
            self.page += 1
        self.update_page_buttons()
        await self.player.show_queue(interaction, page=self.page, edit=True, view=self)

    @discord.ui.button(
        emoji="⏭️",
        label=None,
        style=discord.ButtonStyle.secondary,
        custom_id="music:last",
    )
    async def last_page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not await check_player_ownership(interaction, self.player):
            return
        if interaction.user != self.user:
            # Безопасно получаем цвет как строку
            color = "default"
            if hasattr(self.emoji_settings, "color") and self.emoji_settings.color:
                if isinstance(self.emoji_settings.color, str):
                    color = self.emoji_settings.color
                else:
                    color = "default"

            await interaction.response.send_message(
                f"{get_button_emoji('ERROR', color, self.emoji_settings.custom_emojis)} Это сообщение доступно только тебе.",
                ephemeral=True,
            )
            return
        self.page = self.total_pages
        self.update_page_buttons()
        await self.player.show_queue(interaction, page=self.page, edit=True, view=self)

    async def _handle_page_change(
        self, interaction: discord.Interaction, new_page: int
    ):
        if new_page < 1 or new_page > self.total_pages:
            return
        self.page = new_page
        self.update_page_buttons()
        await self.player.show_queue(interaction, self.page, edit=True, view=self)
