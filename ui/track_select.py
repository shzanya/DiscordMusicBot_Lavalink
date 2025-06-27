from discord.ui import Select
from discord import Interaction, SelectOption
from typing import Optional
import discord
from ui.music_embeds import create_track_finished_embed  # убедись, что импорт работает
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
        history = getattr(self.player, 'history', [])
        seen = set()
        unique_history = [t for t in reversed(history[-25:]) if not (t.uri in seen or seen.add(t.uri))]
        self.tracks = unique_history

        options = []
        for i, track in enumerate(self.tracks):
            author = getattr(track, 'author', 'Unknown Artist')
            title = getattr(track, 'title', 'Unknown Track')
            label = f"{author} - {title}"

            if len(label) > 100:
                label = label[:97] + "..."

            options.append(SelectOption(
                label=label,
                value=str(i),
                description=f"Длительность: {format_duration(getattr(track, 'length', 0))}"
            ))

        disabled = not bool(options)

        if not options:
            options = [SelectOption(label="История пуста", value="none")]

        super().__init__(
            placeholder="Выберите трек из истории воспроизведения",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
            custom_id="track_select"
        )

    async def callback(self, interaction: Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ История пуста.", ephemeral=True)
            return

        try:
            idx = int(self.values[0])
            track = self.tracks[idx]
        except (ValueError, IndexError):
            await interaction.response.send_message("❌ Ошибка выбора трека", ephemeral=True)
            return

        if not self.player or not hasattr(self.player, 'play_by_index'):
            await interaction.response.send_message("❌ Плеер недоступен", ephemeral=True)
            return

        if getattr(self.player, "_handling_track_end", False):
            await interaction.response.send_message("⏳ Подождите завершения текущего трека...", ephemeral=True)
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
                    logger.info("✅ Отправлен новый embed завершенного трека (track_select)")
            except discord.HTTPException as e:
                logger.warning(f"Failed to edit/send finished embed (track_select): {e}")

        self.player.now_playing_message = None

        # Добавляем трек в плейлист, если его там нет
        if track not in self.player.playlist:
            if self.requester:
                track.requester = self.requester
            await self.player.add_track(track)

        await interaction.response.defer()
        success = await self.player.play_by_index(self.player.playlist.index(track))

        if success:
            try:
                await interaction.message.edit(view=None)
            except discord.HTTPException:
                pass
        else:
            await interaction.followup.send("❌ Не удалось воспроизвести трек", ephemeral=True)
