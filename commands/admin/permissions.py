import discord
from discord.ext import commands
from config.constants import Emojis, Colors
from services.database import DatabaseService
from ui.embeds import create_error_embed


class PermissionsCommands(commands.Cog, name="🔐 Права"):
    """🔐 Команды управления правами доступа"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db: DatabaseService = bot.db

    @commands.command(name="restrict", aliases=["restrictcmd"])
    @commands.has_permissions(administrator=True)
    async def restrict_command(
        self, ctx: commands.Context, command: str, role: discord.Role = None
    ):
        """
        🔒 Ограничение доступа к команде

        Примеры:
        {prefix}restrict play @DJ
        {prefix}restrict skip off
        """
        if not ctx.guild:
            return await ctx.reply(
                embed=create_error_embed("Команда доступна только на сервере!")
            )

        found_command = self.bot.get_command(command)
        if not found_command:
            return await ctx.reply(
                embed=create_error_embed(f"Команда `{command}` не найдена!")
            )

        await self.db.set_command_restriction(
            ctx.guild.id, command, role.id if role else None
        )

        embed = discord.Embed(
            title=f"{Emojis.LOCK} Ограничение обновлено",
            description=f"Команда `{command}` теперь доступна: {role.mention if role else 'всем'}",
            color=Colors.SUCCESS,
        )
        await ctx.reply(embed=embed)

    async def cog_check(self, ctx: commands.Context) -> bool:
        """🔍 Проверка прав доступа для команд"""
        if not ctx.guild:
            return False

        if ctx.author.guild_permissions.administrator:
            return True

        guild_data = await self.db.get_guild(ctx.guild.id)
        if (
            guild_data
            and guild_data.dj_role
            and guild_data.dj_role in [r.id for r in ctx.author.roles]
        ):
            return True

        return False


async def setup(bot):
    await bot.add_cog(PermissionsCommands(bot))
