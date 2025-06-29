import discord
from typing import Optional
import logging


async def safe_send(
    channel: discord.TextChannel, **kwargs
) -> Optional[discord.Message]:
    """🔐 Безопасная отправка сообщения"""
    try:
        return await channel.send(**kwargs)
    except discord.Forbidden:
        return None
    except discord.HTTPException:
        return None  # Можно добавить логирование, если нужно


async def safe_edit(message: discord.Message, **kwargs) -> Optional[discord.Message]:
    """🔐 Безопасное редактирование сообщения"""
    try:
        return await message.edit(**kwargs)
    except discord.Forbidden:
        return None
    except discord.HTTPException:
        return None  # Можно добавить логирование, если нужно


async def safe_interaction_send(interaction, embed, ephemeral=True):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        else:
            await interaction.followup.send(embed=embed, ephemeral=ephemeral)
    except Exception as e:
        logging.getLogger(__name__).error(f"❌ Error sending embed: {e}")
