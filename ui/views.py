from typing import Optional

import discord
from discord import ui

from config.constants import Emojis
from core.player import HarmonyPlayer
from utils.formatters import format_duration

from .track_select import TrackSelect


class MusicPlayerView(ui.View):
    def __init__(self, player: HarmonyPlayer, message: Optional[discord.Message] = None, requester: Optional[discord.User] = None):
        super().__init__(timeout=None)
        self.player = player
        self.message = message
        self.requester = requester

        # Добавляем селект с треками в View
        self.add_item(TrackSelect(player, requester))

    # Кнопки из твоего MusicControllerView — копируешь сюда все методы с декоратором @ui.button

    @ui.button(emoji=Emojis.NK_RANDOM, style=discord.ButtonStyle.secondary, custom_id="music:shuffle")
    async def shuffle_button(self, interaction: discord.Interaction, button: ui.Button):
        if self.player.queue:
            self.player.queue.shuffle()
            await interaction.response.send_message(f"{Emojis.NK_RANDOM} Очередь перемешана", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Очередь пуста", ephemeral=True)

    @ui.button(emoji=Emojis.NK_BACK, style=discord.ButtonStyle.secondary, custom_id="music:previous")
    async def previous_button(self, interaction: discord.Interaction, button: ui.Button):
        from ui.embed_now_playing import create_now_playing_embed
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

    @ui.button(emoji=Emojis.NK_MUSICPLAY, style=discord.ButtonStyle.secondary, custom_id="music:pause")
    async def pause_button(self, interaction: discord.Interaction, button: ui.Button):
        from ui.embed_now_playing import create_now_playing_embed

        if self.player.paused:
            await self.player.pause(False)
            button.emoji = Emojis.NK_MUSICPLAY
        else:
            await self.player.pause(True)
            button.emoji = Emojis.NK_MUSICPAUSE

        embed = create_now_playing_embed(self.player.current, self.player, interaction.user)
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @ui.button(emoji=Emojis.NK_NEXT, style=discord.ButtonStyle.secondary, custom_id="music:skip")
    async def skip_button(self, interaction: discord.Interaction, button: ui.Button):
        from ui.embed_now_playing import create_now_playing_embed

        await self.player.skip()
        embed = create_now_playing_embed(self.player.current, self.player, interaction.user)
        await self.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @ui.button(emoji=Emojis.NK_POVTOR, style=discord.ButtonStyle.secondary, custom_id="music:loop")
    async def loop_button(self, interaction: discord.Interaction, button: ui.Button):
        self.player.loop = not getattr(self.player, "loop", False)
        button.style = discord.ButtonStyle.success if self.player.loop else discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)

    @ui.button(emoji=Emojis.NK_TIME, style=discord.ButtonStyle.secondary, custom_id="music:seek")
    async def seek_button(self, interaction: discord.Interaction, button: ui.Button):
        pos = format_duration(self.player.position)
        dur = format_duration(self.player.current.length)
        embed = discord.Embed(
            title="📍 Управление позицией",
            description=f"**Текущая позиция:** `{pos}`\n**Длительность трека:** `{dur}`",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(emoji=Emojis.NK_VOLUME, style=discord.ButtonStyle.secondary, custom_id="music:volume")
    async def volume_button(self, interaction: discord.Interaction, button: ui.Button):
        volume = getattr(self.player, "volume", 100)
        embed = discord.Embed(
            title=f"{Emojis.NK_VOLUME} Управление громкостью",
            description=f"**Громкость:** {volume}%",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(emoji=Emojis.NK_LEAVE, style=discord.ButtonStyle.secondary, custom_id="music:stop")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.player.disconnect()
        await interaction.response.edit_message(view=None)

    @ui.button(emoji=Emojis.NK_TEXT, style=discord.ButtonStyle.secondary, custom_id="music:lyrics")
    async def lyrics_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("📄 Текст песни в разработке.", ephemeral=True)

    @ui.button(emoji=Emojis.NK_HEART, style=discord.ButtonStyle.secondary, custom_id="music:like")
    async def like_button(self, interaction: discord.Interaction, button: ui.Button):
        user = interaction.user.mention
        embed = discord.Embed(
            title="—・Понравившиеся",
            description=f"{user}, в каком плейлисте хотите сохранить данный трек?\n\n*Например:* `любимые треки`",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
