import discord
from discord.ext import commands
from config.constants import Colors, get_emoji
from ui.embeds import create_error_embed
from services import mongo_service

class SettingsView(discord.ui.View):
    def __init__(self, guild_id: int, current_color: str):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.current_color = current_color
        self.options_per_page = 25
        self.current_page = 0

        from config.constants import Emojis
        self.all_colors = list(Emojis._color_suffixes.keys())
        self.max_page = (len(self.all_colors) - 1) // self.options_per_page

        self.color_select = self.create_select()
        self.add_item(self.color_select)

        if self.max_page > 0:
            self.add_item(PrevButton(self))
            self.add_item(NextButton(self))

    def create_select(self) -> discord.ui.Select:
        start = self.current_page * self.options_per_page
        end = start + self.options_per_page
        options = []
        for color_name in self.all_colors[start:end]:
            options.append(
                discord.SelectOption(
                    label=color_name.capitalize(),
                    value=color_name,
                    default=(color_name == self.current_color)
                )
            )
        select = discord.ui.Select(
            placeholder="Выберите цвет эмодзи для сервера",
            options=options,
            custom_id="color_select"
        )
        select.callback = self.color_callback
        return select

    async def color_callback(self, interaction: discord.Interaction):
        selected_color = self.color_select.values[0]
        await interaction.response.defer(ephemeral=True)
        await mongo_service.set_guild_settings(
            self.guild_id, {"color": selected_color}
        )
        self.current_color = selected_color
        emoji = get_emoji('SUCCESS', selected_color)
        await interaction.followup.send(
            f"{emoji} Цвет эмодзи для сервера изменён на "
            f"**{selected_color.capitalize()}**",
            ephemeral=True
        )

    async def update_select(self, interaction: discord.Interaction):
        self.remove_item(self.color_select)
        self.color_select = self.create_select()
        self.add_item(self.color_select)
        await interaction.response.edit_message(view=self)


class PrevButton(discord.ui.Button):
    def __init__(self, view: SettingsView):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="⬅ Предыдущая",
            row=1
        )
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        view = self.view_ref
        if view.current_page > 0:
            await interaction.response.defer(ephemeral=True)
            view.current_page -= 1
            await view.update_select(interaction)


class NextButton(discord.ui.Button):
    def __init__(self, view: SettingsView):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Следующая ➡",
            row=1
        )
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        view = self.view_ref
        if view.current_page < view.max_page:
            await interaction.response.defer(ephemeral=True)
            view.current_page += 1
            await view.update_select(interaction)


class AdminSettingsCommands(commands.Cog, name="⚙️ Настройки"):
    """⚙️ Команды администрирования настроек сервера"""
    
    def __init__(self, bot):
        self.bot = bot

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

        await mongo_service.set_guild_settings(ctx.guild.id, {"prefix": new_prefix})

        settings = await mongo_service.get_guild_settings(ctx.guild.id) or {}
        color = settings.get("color", "default")
        emoji = get_emoji('SUCCESS', color)
        embed = discord.Embed(
            title=f"{emoji} Префикс изменён",
            description=(
                f"Новый префикс: "
                f"`{new_prefix}`"
            ),
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

        await mongo_service.set_guild_settings(ctx.guild.id, {"dj_role": role.id if role else None})

        settings = await mongo_service.get_guild_settings(ctx.guild.id) or {}
        color = settings.get("color", "default")
        emoji = get_emoji('SUCCESS', color)
        embed = discord.Embed(
            title=f"{emoji} Роль DJ обновлена",
            description=(
                f"Новая роль DJ: "
                f"{role.mention if role else 'Отключена'}"
            ),
            color=Colors.SUCCESS
        )
        await ctx.reply(embed=embed)

    @commands.has_guild_permissions(administrator=True)
    @commands.hybrid_command(
        name="settings",
        description="Настройки цвета и эмодзи для сервера"
    )
    async def settings_command(self, ctx: commands.Context):
        guild_id = ctx.guild.id if ctx.guild else None
        if not guild_id:
            return await ctx.reply(
                embed=create_error_embed(
                    "Команда доступна только на сервере!"
                )
            )
        settings = await mongo_service.get_guild_settings(guild_id) or {}
        color = settings.get("color", "default")
        embed = discord.Embed(
            title="Настройки цвета эмодзи",
            description=(
                "Здесь вы можете выбрать цвет для всех эмодзи этого сервера.\n"
                "Этот цвет будет использоваться для всех музыкальных кнопок и UI."
            ),
            color=0x242429
        )
        embed.add_field(
            name="Текущий цвет",
            value=color
        )
        view = SettingsView(guild_id, color)
        await ctx.defer(
            ephemeral=True
        )
        await ctx.reply(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminSettingsCommands(bot))
