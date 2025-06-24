import discord
from discord.ext import commands
from config.constants import Emojis, Colors
from services.database import DatabaseService
from ui.embeds import create_error_embed

class AdminSettingsCommands(commands.Cog, name="⚙️ Настройки"):
    """⚙️ Команды администрирования настроек сервера"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db: DatabaseService = bot.db

    @commands.command(name='prefix')
    @commands.has_permissions(administrator=True)
    async def prefix_command(self, ctx: commands.Context, new_prefix: str):
        """
        ⚙️ Изменение префикса команд
        
        Пример:
        {prefix}prefix !
        """
        if len(new_prefix) > 5:
            return await ctx.reply(embed=create_error_embed(
                "Префикс не должен быть длиннее 5 символов!"
            ))
        
        if not ctx.guild:
            return await ctx.reply(embed=create_error_embed(
                "Команда доступна только на сервере!"
            ))

        await self.db.update_guild_prefix(ctx.guild.id, new_prefix)
        
        embed = discord.Embed(
            title=f"{Emojis.SUCCESS} Префикс изменён",
            description=f"Новый префикс: `{new_prefix}`",
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)

    @commands.command(name='djrole', aliases=['dj'])
    @commands.has_permissions(administrator=True)
    async def dj_role_command(self, ctx: commands.Context, role: discord.Role = None):
        """
        🎧 Установка роли DJ
        
        Пример:
        {prefix}djrole @DJ
        {prefix}djrole off - Отключить роль DJ
        """
        if not ctx.guild:
            return await ctx.reply(embed=create_error_embed(
                "Команда доступна только на сервере!"
            ))

        await self.db.update_guild_dj_role(ctx.guild.id, role.id if role else None)

        embed = discord.Embed(
            title=f"{Emojis.SUCCESS} Роль DJ обновлена",
            description=f"Новая роль DJ: {role.mention if role else 'Отключена'}",
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)
async def setup(bot):
    await bot.add_cog(AdminSettingsCommands(bot))
