
import discord
from discord.ext import commands

from config.constants import Colors, Emojis
from ui.embeds import create_error_embed, create_queue_embed


class QueueCommands(commands.Cog, name="📋 Очередь"):
    """📋 Команды управления очередью воспроизведения"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='queue', aliases=['q'])
    async def queue_command(self, ctx, page: int = 1):
        """
        📋 Просмотр очереди воспроизведения

        Пример:
        {prefix}queue 2 - Показать вторую страницу очереди
        """
        player = ctx.voice_client
        if not player or not player.queue:
            return await ctx.reply(embed=create_error_embed(
                "Очередь пуста!"
            ))

        embed = create_queue_embed(player.queue, page, player.current)
        await ctx.reply(embed=embed)

    @commands.command(name='clear')
    async def clear_command(self, ctx):
        """🗑️ Очистка очереди"""
        player = ctx.voice_client
        if not player:
            return await ctx.reply(embed=create_error_embed(
                "Бот не подключен к голосовому каналу!"
            ))

        player.queue.clear()
        embed = discord.Embed(
            title=f"{Emojis.CLEAR} Очередь очищена",
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)

    @commands.command(name='remove', aliases=['rm'])
    async def remove_command(self, ctx, index: int):
        """
        ➖ Удаление трека из очереди по индексу

        Пример:
        {prefix}remove 3
        """
        player = ctx.voice_client
        if not player or not player.queue:
            return await ctx.reply(embed=create_error_embed(
                "Очередь пуста!"
            ))

        if index < 1 or index > len(player.queue):
            return await ctx.reply(embed=create_error_embed(
                f"Недопустимый индекс! Выберите от 1 до {len(player.queue)}"
            ))

        removed_track = player.queue.pop(index - 1)
        embed = discord.Embed(
            title=f"{Emojis.REMOVE} Трек удален",
            description=f"{removed_track.title}",
            color=Colors.WARNING
        )
        await ctx.reply(embed=embed)

    @commands.command(name='shuffle')
    async def shuffle_command(self, ctx):
        """🔀 Перемешивание очереди"""
        player = ctx.voice_client
        if not player or not player.queue:
            return await ctx.reply(embed=create_error_embed(
                "Очередь пуста!"
            ))

        player.queue.shuffle()
        embed = discord.Embed(
            title=f"{Emojis.SHUFFLE} Очередь перемешана",
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)
async def setup(bot):
    await bot.add_cog(QueueCommands(bot))
