import discord
from discord.ext import commands
from typing import Type
from config.constants import Emojis, Colors
from services.database import DatabaseService
from ui.embeds import create_error_embed

class PlaylistManagementCommands(commands.Cog, name="📁 Плейлисты"):
    """📁 Команды управления плейлистами"""

    def __init__(self, bot):
        """Инициализация ког с ботом и сервисом базы данных"""
        self.bot = bot
        self.db: Type[DatabaseService] = bot.db

    @commands.command(name='createplaylist', aliases=['newpl'])
    async def create_playlist_command(self, ctx: commands.Context, name: str):
        """📁 Создание нового плейлиста

        Args:
            ctx: Контекст команды
            name: Имя нового плейлиста
        """
        if len(name) > 50:
            return await ctx.reply(embed=create_error_embed(
                "Имя плейлиста не должно превышать 50 символов!"
            ))

        playlist = await self.db.create_playlist(ctx.author.id, name)

        embed = discord.Embed(
            title=f"{Emojis.ADD} Плейлист создан",
            description=discord.utils.escape_markdown(name),  # Экранируем пользовательский ввод
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)

    @commands.command(name='addtoplaylist', aliases=['pladd'])
    async def add_to_playlist_command(self, ctx: commands.Context, playlist_name: str):
        """➕ Добавление текущего трека в плейлист

        Args:
            ctx: Контекст команды
            playlist_name: Имя плейлиста
        """
        player = ctx.voice_client
        if not player or not player.current:
            return await ctx.reply(embed=create_error_embed(
                "Сейчас ничего не воспроизводится!"
            ))

        playlist = await self.db.get_playlist(ctx.author.id, playlist_name)
        if not playlist:
            return await ctx.reply(embed=create_error_embed(
                f"Плейлист '{discord.utils.escape_markdown(playlist_name)}' не найден!"
            ))

        track = player.current
        await self.db.add_to_playlist(playlist.id, track.title, track.uri)

        embed = discord.Embed(
            title=f"{Emojis.ADD} Добавлено в плейлист",
            description=(
                f"{discord.utils.escape_markdown(track.title)} → "
                f"{discord.utils.escape_markdown(playlist_name)}"
            ),
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)

    @commands.command(name='playlists', aliases=['pls'])
    async def playlists_command(self, ctx: commands.Context, page: int = 1):
        """📜 Список плейлистов пользователя

        Args:
            ctx: Контекст команды
            page: Номер страницы (по умолчанию 1)
        """
        playlists = await self.db.get_user_playlists(ctx.author.id)
        if not playlists:
            return await ctx.reply(embed=create_error_embed(
                "У вас нет плейлистов!"
            ))

        embed = discord.Embed(
            title=f"{Emojis.QUEUE} Ваши плейлисты",
            color=Colors.MUSIC
        )

        per_page = 10
        pages = (len(playlists) + per_page - 1) // per_page
        page = max(1, min(page, pages))

        start = (page - 1) * per_page
        end = start + per_page

        for i, playlist in enumerate(playlists[start:end], start=start + 1):
            embed.add_field(
                name=f"{i}. {discord.utils.escape_markdown(playlist.name)}",
                value=f"{len(playlist.tracks)} треков",
                inline=False
            )

        embed.set_footer(text=f"Страница {page}/{pages}")
        await ctx.reply(embed=embed)
async def setup(bot):
    await bot.add_cog(PlaylistManagementCommands(bot))
