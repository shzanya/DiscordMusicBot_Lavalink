import discord
from discord.ui import Select
from typing import Optional
from core.player import HarmonyPlayer


class TrackSelect(Select):
    def __init__(self, player: HarmonyPlayer, requester: Optional[discord.User] = None):
        self.player = player
        self.requester = requester

        # Получаем последние 25 треков из истории
        history = getattr(player, 'history', [])[-25:] if hasattr(player, 'history') else []

        options = []
        for i, track in enumerate(reversed(history)):
            author = getattr(track, 'author', 'Unknown Artist')
            title = getattr(track, 'title', 'Unknown Track')
            label = f"{author} - {title}"

            if len(label) > 100:
                label = label[:97] + "..."

            options.append(discord.SelectOption(
                label=label,
                value=str(i),
                description=f"Длительность: {self._format_duration(getattr(track, 'length', 0))}"
            ))

        disabled = not bool(options)  # Если история пуста — отключить выбор

        if not options:
            options = [discord.SelectOption(label="История пуста", value="none")]

        super().__init__(
            placeholder="Выберите трек из истории воспроизведения",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
            custom_id="track_select"
        )

    def _format_duration(self, seconds: int) -> str:
        if seconds <= 0:
            return "N/A"
        return f"{seconds // 60}:{seconds % 60:02d}"

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ История пуста.", ephemeral=True)
            return

        try:
            idx = int(self.values[0])
        except ValueError:
            await interaction.response.send_message("❌ Ошибка выбора трека", ephemeral=True)
            return

        history = getattr(self.player, 'history', [])[-25:]
        if idx >= len(history):
            await interaction.response.send_message("❌ Выбранный трек не найден", ephemeral=True)
            return

        track = history[-(idx + 1)]

        if not self.player or not hasattr(self.player, 'play_track'):
            await interaction.response.send_message("❌ Плеер недоступен", ephemeral=True)
            return

        await self.player.play_track(track)

        # Только текст без embed
        track_info = f"{getattr(track, 'author', 'Unknown')} — {getattr(track, 'title', 'Unknown')}"
        await interaction.response.send_message(
            f"▶️ Воспроизвожу: **{track_info}** из истории",
            ephemeral=True
        )
