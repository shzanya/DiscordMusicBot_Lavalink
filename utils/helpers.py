import discord
import asyncio
from typing import Optional

async def safe_send(channel: discord.TextChannel, **kwargs) -> Optional[discord.Message]:
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
