from discord.ext import commands
from typing import Callable, Optional
from discord import Guild, Member
from ui.embeds import create_error_embed


def has_dj_role() -> Callable:
    """🔐 Проверка наличия роли DJ"""
    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage("Эта команда доступна только на сервере.")

        guild_data = await ctx.bot.db.get_guild(ctx.guild.id)
        if not guild_data:
            raise commands.CheckFailure("Данные сервера не найдены.")

        if ctx.author.guild_permissions.administrator:
            return True

        if not guild_data.dj_role:
            return True

        if guild_data.dj_role in [r.id for r in ctx.author.roles]:
            return True

        raise commands.CheckFailure("❌ Для использования этой команды требуется роль DJ.")
    
    return commands.check(predicate)


def restrict_command() -> Callable:
    """🔒 Проверка ограничений команды"""
    async def predicate(ctx: commands.Context) -> bool:
        if not ctx.guild:
            raise commands.NoPrivateMessage("Эта команда доступна только на сервере.")

        guild_data = await ctx.bot.db.get_guild(ctx.guild.id)
        if not guild_data:
            raise commands.CheckFailure("Данные сервера не найдены.")

        command_name = ctx.command.name
        restriction = guild_data.restrictions.get(command_name)

        if not restriction:
            return True

        if ctx.author.guild_permissions.administrator:
            return True

        if restriction in [str(role.id) for role in ctx.author.roles]:
            return True

        raise commands.CheckFailure(f"❌ Для использования этой команды требуется роль <@&{restriction}>.")
    
    return commands.check(predicate)
