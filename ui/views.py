
import discord
from discord import ui

from config.constants import Emojis
from ui.embed_now_playing import create_now_playing_embed
from utils.formatters import format_duration

from .track_select import TrackSelect


class MusicPlayerView(ui.View):
    def __init__(self, player, message=None, requester=None):
        super().__init__(timeout=None)

        self.player = player
        self.message = message
        self.requester = requester

        self.player.view = self  # ✅ Теперь self.player уже существует
        # 1. Добавляем селект первым
        self.add_item(TrackSelect(player, requester))

        # 2. Добавляем кнопки вручную, в нужном порядке
        self.add_item(self._make_button("music:shuffle", Emojis.NK_RANDOM, self.shuffle_button))
        self.add_item(self._make_button("music:previous", Emojis.NK_BACK, self.previous_button))
        self.add_item(self._make_button("music:pause", Emojis.NK_MUSICPLAY, self.pause_button))
        self.add_item(self._make_button("music:skip", Emojis.NK_NEXT, self.skip_button))
        self.add_item(self._make_button("music:loop", Emojis.NK_POVTOR, self.loop_button))
        self.add_item(self._make_button("music:seek", Emojis.NK_TIME, self.seek_button))
        self.add_item(self._make_button("music:volume", Emojis.NK_VOLUME, self.volume_button))
        self.add_item(self._make_button("music:stop", Emojis.NK_LEAVE, self.stop_button))
        self.add_item(self._make_button("music:lyrics", Emojis.NK_TEXT, self.lyrics_button))
        self.add_item(self._make_button("music:like", Emojis.NK_HEART, self.like_button))

    def _make_button(self, custom_id, emoji, callback, style=discord.ButtonStyle.secondary):
        button = ui.Button(emoji=emoji, style=style, custom_id=custom_id)
        button.callback = callback
        return button

    # Обработчики кнопок
    async def refresh_select_menu(self):
        """Обновляет селект треков в интерфейсе"""
        # Удалим старый TrackSelect
        for item in self.children:
            if isinstance(item, TrackSelect):
                self.remove_item(item)
                break

        # Добавим новый TrackSelect с актуальной историей
        self.add_item(TrackSelect(self.player, self.requester))

        # Обновим сообщение
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass  # Сообщение удалено или изменено

    async def shuffle_button(self, interaction: discord.Interaction):
        if self.player.queue:
            self.player.queue.shuffle()
            await interaction.response.send_message(f"{Emojis.NK_RANDOM} Очередь перемешана", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Очередь пуста", ephemeral=True)

    async def previous_button(self, interaction: discord.Interaction):
        if hasattr(self.player, "play_previous"):
            success = await self.player.play_previous()
            if success:
                embed = create_now_playing_embed(self.player.current, self.player, interaction.user)
                await self.message.edit(embed=embed, view=self)
                await interaction.response.defer()
            else:
                await interaction.response.send_message("❌ Предыдущий трек не найден", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Плеер не поддерживает `play_previous()`", ephemeral=True)

    async def pause_button(self, interaction: discord.Interaction):
        if self.player.paused:
            await self.player.pause(False)
        else:
            await self.player.pause(True)

        embed = create_now_playing_embed(self.player.current, self.player, interaction.user)
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    async def skip_button(self, interaction: discord.Interaction):
        await self.player.skip()
        embed = create_now_playing_embed(self.player.current, self.player, interaction.user)
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    async def loop_button(self, interaction: discord.Interaction):
        self.player.loop = not getattr(self.player, "loop", False)
        await interaction.response.edit_message(view=self)

    async def seek_button(self, interaction: discord.Interaction):
        pos = format_duration(self.player.position)
        dur = format_duration(self.player.current.length)
        embed = discord.Embed(
            title="📍 Управление позицией",
            description=f"**Текущая позиция:** `{pos}`\n**Длительность трека:** `{dur}`",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def volume_button(self, interaction: discord.Interaction):
        volume = getattr(self.player, "volume", 100)
        embed = discord.Embed(
            title=f"{Emojis.NK_VOLUME} Управление громкостью",
            description=f"**Громкость:** {volume}%",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def stop_button(self, interaction: discord.Interaction):
        await self.player.disconnect()
        await interaction.response.edit_message(view=None)

    async def lyrics_button(self, interaction: discord.Interaction):
        await interaction.response.send_message("📄 Текст песни в разработке.", ephemeral=True)

    async def like_button(self, interaction: discord.Interaction):
        user = interaction.user.mention
        embed = discord.Embed(
            title="—・Понравившиеся",
            description=f"{user}, в каком плейлисте хотите сохранить данный трек?\n\n*Например:* `любимые треки`",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
