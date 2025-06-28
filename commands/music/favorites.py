import discord
from discord.ext import commands
from config.constants import Emojis, Colors
from services.database import DatabaseService
from ui.embeds import create_error_embed, create_track_embed


class FavoritesCommands(commands.Cog, name="❤️ Избранное"):
    """❤️ Команды управления избранными треками"""

    def __init__(self, bot):
        self.bot = bot
        self.db: DatabaseService = bot.db

    @commands.command(name="favorite", aliases=["fav", "addfav"])
    async def favorite_command(self, ctx):
        """❤️ Добавление текущего трека в избранное"""
        player = ctx.voice_client
        if not player or not player.current:
            return await ctx.reply(
                embed=create_error_embed("Сейчас ничего не воспроизводится!")
            )

        track = player.current
        await self.db.add_favorite(ctx.author.id, track.title, track.uri)

        embed = create_track_embed(
            track, f"{Emojis.HEART} Добавлено в избранное", Colors.SUCCESS
        )
        await ctx.reply(embed=embed)

    @commands.command(name="favorites", aliases=["favs"])
    async def favorites_list_command(self, ctx, page: int = 1):
        """📜 Список избранных треков"""
        favorites = await self.db.get_favorites(ctx.author.id)
        if not favorites:
            return await ctx.reply(
                embed=create_error_embed("У вас нет избранных треков!")
            )

        embed = discord.Embed(
            title=f"{Emojis.HEART} Избранные треки {ctx.author.name}",
            color=Colors.MUSIC,
        )

        per_page = 10
        pages = max(1, (len(favorites) + per_page - 1) // per_page)
        page = max(1, min(page, pages))

        start = (page - 1) * per_page
        end = start + per_page

        for i, favorite in enumerate(favorites[start:end], start=start + 1):
            embed.add_field(
                name=f"{i}. {favorite.title}",
                value=f"[Слушать]({favorite.uri})" if favorite.uri else "—",
                inline=False,
            )

        embed.set_footer(text=f"Страница {page}/{pages}")
        await ctx.reply(embed=embed)

    @commands.command(name="removefav", aliases=["unfav"])
    async def remove_favorite_command(self, ctx, index: int):
        """💔 Удаление трека из избранного"""
        favorites = await self.db.get_favorites(ctx.author.id)
        if not favorites or index < 1 or index > len(favorites):
            return await ctx.reply(
                embed=create_error_embed("Недопустимый индекс или избранное пусто!")
            )

        favorite = favorites[index - 1]
        await self.db.remove_favorite(ctx.author.id, favorite.id)

        embed = discord.Embed(
            title=f"{Emojis.HEART_BROKEN} Трек удален из избранного",
            description=f"{favorite.title}",
            color=Colors.WARNING,
        )
        await ctx.reply(embed=embed)


async def setup(bot):
    await bot.add_cog(FavoritesCommands(bot))
