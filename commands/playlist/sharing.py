import discord
from discord.ext import commands
from config.constants import Emojis, Colors
from config.settings import Settings  # Добавлено предположение, откуда берётся Settings
from services.database import DatabaseService
from ui.embeds import create_error_embed


class PlaylistSharingCommands(commands.Cog, name="🔗 Поделиться"):
    """🔗 Команды для шаринга плейлистов"""

    def __init__(self, bot):
        self.bot = bot
        self.db: DatabaseService = bot.db

    @commands.command(name="shareplaylist", aliases=["plshare"])
    async def share_playlist_command(self, ctx, playlist_name: str):
        """🔗 Поделиться плейлистом"""
        playlist = await self.db.get_playlist(ctx.author.id, playlist_name)
        if not playlist:
            return await ctx.reply(
                embed=create_error_embed(f"Плейлист `{playlist_name}` не найден!")
            )

        share_id = await self.db.create_share_link(playlist.id)

        embed = discord.Embed(
            title=f"{Emojis.LOCK} Плейлист отправлен",
            description=(
                f"Поделитесь плейлистом **{playlist.name}** с помощью команды:\n"
                f"```{Settings.COMMAND_PREFIX}importpl {share_id}```"
            ),
            color=Colors.DEFAULT,  # или Colors.EMBED, если у вас такой цвет определён
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PlaylistSharingCommands(bot))
