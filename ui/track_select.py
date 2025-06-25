from discord.ui import Select
from discord import Interaction, SelectOption
from typing import Optional
from core.player import HarmonyPlayer
import discord


class TrackSelect(Select):
    def __init__(self, player: HarmonyPlayer, requester: Optional[discord.User] = None):
        self.player = player
        self.requester = requester

        # Получаем уникальную историю (последние 25 треков, от новых к старым, без дубликатов)
        history = getattr(player, 'history', [])
        # Удаляем дубликаты, сохраняя порядок
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
                description=f"Длительность: {self._format_duration(getattr(track, 'length', 0))}"
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

    def _format_duration(self, milliseconds: int) -> str:
        if milliseconds <= 0:
            return "N/A"
        seconds = milliseconds // 1000  # Конвертируем миллисекунды в секунды
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

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

        if not self.player or not hasattr(self.player, 'play_track'):
            await interaction.response.send_message("❌ Плеер недоступен", ephemeral=True)
            return

        # Устанавливаем requester
        if self.requester:
            track.requester = self.requester

        await interaction.response.defer()
        await self.player.play_track(track)

        try:
            await interaction.message.edit(view=None)
        except discord.HTTPException:
            pass
