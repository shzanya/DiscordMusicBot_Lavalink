from urllib.parse import urlparse
import re
import discord
import logging
from typing import Optional, Union, Any

logger = logging.getLogger(__name__)

def is_valid_url(url: str) -> bool:
    """✅ Проверка валидности URL"""
    pattern = re.compile(
        r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    )
    return bool(pattern.match(url))

def is_spotify_url(url: str) -> bool:
    """🎵 Проверка Spotify URL"""
    parsed = urlparse(url)
    return parsed.netloc in ['open.spotify.com', 'spotify.com'] and \
           any(x in parsed.path for x in ['track', 'playlist', 'album'])

def is_player_owner(player: Any, user: Union[discord.Member, discord.User]) -> bool:
    """
    Проверяет, является ли пользователь владельцем плеера.
    
    Args:
        player: Экземпляр плеера
        user: Пользователь для проверки
        
    Returns:
        bool: True если пользователь является владельцем плеера
    """
    try:
        # Проверяем текущий трек
        current_track = getattr(player, 'current', None)
        if current_track and hasattr(current_track, 'requester'):
            if current_track.requester and current_track.requester.id == user.id:
                return True
        
        # Проверяем первый трек в плейлисте (кто запустил)
        if hasattr(player, 'playlist') and player.playlist:
            first_track = player.playlist[0]
            if hasattr(first_track, 'requester') and first_track.requester:
                if first_track.requester.id == user.id:
                    return True
        
        # Проверяем requester из view
        if hasattr(player, 'view') and player.view:
            view_requester = getattr(player.view, 'requester', None)
            if view_requester and view_requester.id == user.id:
                return True
        
        # Проверяем администраторов сервера
        if hasattr(user, 'guild_permissions') and user.guild_permissions.administrator:
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error checking player ownership: {e}")
        return False

async def check_player_ownership(
    interaction: discord.Interaction, 
    player: Any,
    error_message: str = "❌ Это не Ваш плеер! Только тот, кто запустил музыку, может управлять ею."
) -> bool:
    """
    Проверяет владельца плеера и отправляет сообщение об ошибке если пользователь не владелец.
    
    Args:
        interaction: Discord interaction
        player: Экземпляр плеера
        error_message: Сообщение об ошибке
        
    Returns:
        bool: True если пользователь является владельцем плеера
    """
    if not is_player_owner(player, interaction.user):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(error_message, ephemeral=True)
            else:
                await interaction.followup.send(error_message, ephemeral=True)
        except Exception as e:
            logger.error(f"Error sending ownership error message: {e}")
        return False
    return True
