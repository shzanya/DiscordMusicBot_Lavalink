import discord
from discord.ext import commands
from typing import Optional
from config.constants import Emojis, Colors
from core.player import HarmonyPlayer
from ui.embeds import create_error_embed

class EffectsCommands(commands.Cog, name="🎚️ Эффекты"):
    """🎚️ Команды управления звуковыми эффектами"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='bassboost', aliases=['bass'])
    async def bass_boost_command(self, ctx, state: Optional[bool] = None):
        """
        🎛️ Включение/выключение басбуста

        Примеры:
        {prefix}bassboost - Переключение
        {prefix}bassboost on - Включить
        {prefix}bassboost off - Выключить
        """
        player: HarmonyPlayer = ctx.voice_client
        if not player:
            return await ctx.reply(embed=create_error_embed(
                "Бот не подключен к голосовому каналу!"
            ))

        new_state = not player.state.bass_boost if state is None else state
        await player.set_effects(bass=new_state)

        embed = discord.Embed(
            title=f"{Emojis.BASS} Басбуст {'включен' if new_state else 'выключен'}",
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)

    @commands.command(name='nightcore')
    async def nightcore_command(self, ctx, state: Optional[bool] = None):
        """🌙 Включение/выключение найткор эффекта"""
        player: HarmonyPlayer = ctx.voice_client
        if not player:
            return await ctx.reply(embed=create_error_embed(
                "Бот не подключен к голосовому каналу!"
            ))

        new_state = not player.state.nightcore if state is None else state
        await player.set_effects(nightcore=new_state)

        embed = discord.Embed(
            title=f"{Emojis.NIGHTCORE} Найткор {'включен' if new_state else 'выключен'}",
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)

    @commands.command(name='vaporwave')
    async def vaporwave_command(self, ctx, state: Optional[bool] = None):
        """🌊 Включение/выключение вейпорвейв эффекта"""
        player: HarmonyPlayer = ctx.voice_client
        if not player:
            return await ctx.reply(embed=create_error_embed(
                "Бот не подключен к голосовому каналу!"
            ))

        new_state = not player.state.vaporwave if state is None else state
        await player.set_effects(vaporwave=new_state)

        embed = discord.Embed(
            title=f"{Emojis.VAPORWAVE} Вейпорвейв {'включен' if new_state else 'выключен'}",
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)
async def setup(bot):
    await bot.add_cog(EffectsCommands(bot))
