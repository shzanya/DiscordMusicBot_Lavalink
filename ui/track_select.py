from discord.ui import Select
from discord import Interaction, SelectOption
from typing import Optional
import discord
from ui.music_embeds import create_track_finished_embed  # убедись, что импорт работает
from utils.validators import check_player_ownership
import logging

from utils.formatters import (
    format_duration,
)

logger = logging.getLogger(__name__)


class TrackSelect(Select):
    def __init__(self, player, requester: Optional[discord.User] = None):
        self.player = player
        self.requester = requester

        # Получаем историю (последние 25 треков, от новых к старым, без дубликатов)
        history = getattr(self.player, "history", [])
        seen = set()
        unique_history = []

        # Обрабатываем историю в обратном порядке (новые треки первыми)
        for track in reversed(history[-25:]):
            track_uri = getattr(track, "uri", getattr(track, "identifier", ""))
            if track_uri and track_uri not in seen:
                seen.add(track_uri)
                unique_history.append(track)

        self.tracks = unique_history

        options = []
        if self.tracks:
            for i, track in enumerate(self.tracks):
                author = getattr(track, "author", "Unknown Artist")
                title = getattr(track, "title", "Unknown Track")
                label = f"{author} - {title}"

                if len(label) > 100:
                    label = label[:97] + "..."

                duration = getattr(track, "length", 0)
                duration_str = format_duration(duration) if duration > 0 else "Unknown"

                options.append(
                    SelectOption(
                        label=label,
                        value=str(i),
                        description=f"Длительность: {duration_str}",
                    )
                )
        else:
            options = [
                SelectOption(
                    label="История пуста",
                    value="none",
                    description="Нет прослушанных треков",
                )
            ]

        super().__init__(
            placeholder="Выберите трек из истории воспроизведения",
            min_values=1,
            max_values=1,
            options=options,
            disabled=not bool(self.tracks),
            custom_id="track_select",
        )

    async def callback(self, interaction: Interaction):
        # Проверяем владельца плеера
        if not await check_player_ownership(interaction, self.player):
            return

        if self.values[0] == "none":
            await interaction.response.send_message("❌ История пуста.", ephemeral=True)
            return

        try:
            idx = int(self.values[0])
            track = self.tracks[idx]
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "❌ Ошибка выбора трека", ephemeral=True
            )
            return

        if not self.player or not hasattr(self.player, "play_by_index"):
            await interaction.response.send_message(
                "❌ Плеер недоступен", ephemeral=True
            )
            return

        if getattr(self.player, "_handling_track_end", False):
            await interaction.response.send_message(
                "⏳ Подождите завершения текущего трека...", ephemeral=True
            )
            return

        # Сохраняем текущий трек для embed "Прослушано"
        old_track = self.player.current
        if old_track and self.player.text_channel:
            embed = create_track_finished_embed(old_track, position=old_track.length)
            try:
                if self.player.now_playing_message:
                    await self.player.now_playing_message.edit(embed=embed, view=None)
                    logger.info("✅ Обновлен embed завершенного трека (track_select)")
                else:
                    await self.player.text_channel.send(embed=embed)
                    logger.info(
                        "✅ Отправлен новый embed завершенного трека (track_select)"
                    )
            except discord.HTTPException as e:
                logger.warning(
                    f"Failed to edit/send finished embed (track_select): {e}"
                )

        self.player.now_playing_message = None

        # Добавляем трек в плейлист, если его там нет
        track_uri = getattr(track, "uri", getattr(track, "identifier", ""))
        track_in_playlist = any(
            getattr(t, "uri", getattr(t, "identifier", "")) == track_uri
            for t in self.player.playlist
        )

        if not track_in_playlist:
            if self.requester:
                track.requester = self.requester
            await self.player.add_track(track)
            await interaction.response.defer()
            success = await self.player.play_by_index(len(self.player.playlist) - 1)
        else:
            # Если трек уже в плейлисте, находим его индекс
            playlist_index = next(
                i
                for i, t in enumerate(self.player.playlist)
                if getattr(t, "uri", getattr(t, "identifier", "")) == track_uri
            )
            await interaction.response.defer()
            success = await self.player.play_by_index(playlist_index)

        if success:
            try:
                await interaction.message.edit(view=None)
            except discord.HTTPException:
                pass
        else:
            await interaction.followup.send(
                "❌ Не удалось воспроизвести трек", ephemeral=True
            )
