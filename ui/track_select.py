import discord
from discord.ui import Select
from typing import Optional
from core.player import HarmonyPlayer
from ui.embeds import create_now_playing_embed


class TrackSelect(Select):
    def __init__(self, player: HarmonyPlayer, requester: Optional[discord.User] = None):
        self.player = player
        self.requester = requester
        
        options = []
        history = getattr(player, 'history', [])[-25:] if hasattr(player, 'history') else []
        
        for i, track in enumerate(reversed(history)):
            # Безопасное получение атрибутов трека
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
        
        if not options:
            options = [discord.SelectOption(label="История пуста", value="none")]
            disabled = True
        else:
            disabled = False
        
        super().__init__(
            placeholder="Выберите трек из истории воспроизведения",
            min_values=1,
            max_values=1,
            options=options,
            disabled=disabled,
            custom_id="track_select"
        )
    
    def _format_duration(self, seconds: int) -> str:
        """Форматирование длительности трека"""
        if seconds <= 0:
            return "N/A"
        
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # Проверка на пустую историю
            if self.values[0] == "none":
                await interaction.response.send_message(
                    "❌ История воспроизведения пуста", 
                    ephemeral=True
                )
                return
            
            # Получение индекса выбранного трека
            try:
                idx = int(self.values[0])
            except ValueError:
                await interaction.response.send_message(
                    "❌ Ошибка выбора трека", 
                    ephemeral=True
                )
                return
            
            # Проверка наличия истории
            history = getattr(self.player, 'history', [])[-25:]
            if not history or idx >= len(history):
                await interaction.response.send_message(
                    "❌ Выбранный трек недоступен", 
                    ephemeral=True
                )
                return
            
            # Получение трека из истории (в обратном порядке)
            track = history[-(idx + 1)]
            
            # Проверка состояния плеера
            if not self.player or not hasattr(self.player, 'play_track'):
                await interaction.response.send_message(
                    "❌ Плеер недоступен", 
                    ephemeral=True
                )
                return
            
            # Воспроизведение трека
            await self.player.play_track(track)
            
            # Обновление embed
            embed = create_now_playing_embed(track, self.player, self.requester or interaction.user)
            
            # Обновление сообщения
            if interaction.message and self.view:
                try:
                    await interaction.message.edit(embed=embed, view=self.view)
                except discord.HTTPException:
                    pass  # Сообщение может быть удалено
            
            # Ответ пользователю
            track_info = f"{getattr(track, 'author', 'Unknown')} - {getattr(track, 'title', 'Unknown')}"
            await interaction.response.send_message(
                f"▶️ Воспроизвожу: **{track_info}**", 
                ephemeral=True
            )
            
        except Exception as e:
            print(f"[ERROR] TrackSelect callback error: {e}")
            try:
                await interaction.response.send_message(
                    "❌ Произошла ошибка при воспроизведении трека", 
                    ephemeral=True
                )
            except discord.InteractionResponded:
                pass
