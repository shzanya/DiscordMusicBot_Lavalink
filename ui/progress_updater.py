"""
📊 Система автообновления сообщений с прогрессом воспроизведения
"""
import asyncio
import logging
from typing import Dict, Optional

import discord
import wavelink

logger = logging.getLogger(__name__)


class NowPlayingUpdater:
    """Класс для автообновления сообщений с прогрессом воспроизведения"""
    
    def __init__(self):
        self.active_messages: Dict[int, dict] = {}
        self.update_task: Optional[asyncio.Task] = None
        
    def start_updater(self):
        """Запуск фонового обновления"""
        if self.update_task is None or self.update_task.done():
            self.update_task = asyncio.create_task(self._update_loop())
    
    def stop_updater(self):
        """Остановка фонового обновления"""
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
    
    async def register_message(
        self, 
        guild_id: int, 
        message: discord.Message, 
        player, 
        track: wavelink.Playable, 
        requester: discord.Member,
        color: str = "default",
        custom_emojis: dict = None
    ):
        """Регистрация сообщения для автообновления"""
        if not message or not player:
            return
        self.active_messages[guild_id] = {
            'message': message,
            'player': player,
            'track': track,
            'requester': requester,
            'last_update': 0,
            'color': color,
            'custom_emojis': custom_emojis
        }
        self.start_updater()
    
    def unregister_message(self, guild_id: int):
        """Удаление сообщения из автообновления"""
        if guild_id in self.active_messages:
            del self.active_messages[guild_id]
        
        if not self.active_messages:
            self.stop_updater()
    
    async def _update_loop(self):
        """Основной цикл обновления"""
        try:
            while self.active_messages:
                items = list(self.active_messages.items())
                
                for guild_id, info in items:
                    try:
                        await self._update_message(guild_id, info)
                    except Exception as e:
                        logger.debug(f"Update error for guild {guild_id}: {e}")
                        self.unregister_message(guild_id)
                
                await asyncio.sleep(3)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Critical update loop error: {e}")

    async def _update_message(self, guild_id: int, info: dict):
        """Обновление одного сообщения"""
        try:
            message = info.get('message')
            player = info.get('player')
            color = info.get('color', "default")
            custom_emojis = info.get('custom_emojis', None)
            if not message or not player:
                self.unregister_message(guild_id)
                return
            # Проверяем состояние плеера
            if not hasattr(player, 'playing') or not player.playing or not player.current:
                self.unregister_message(guild_id)
                return
            # Получаем позицию безопасно
            try:
                current_position = int(getattr(player, 'position', 0) or 0)
            except Exception:
                current_position = 0
            current_track = player.current
            # Принудительное обновление при смене трека
            force_update = False
            if info.get('track') != current_track:
                info['track'] = current_track
                force_update = True
            # Проверка времени обновления
            last_update = info.get('last_update', 0)
            if not force_update and abs(current_position - last_update) < 1:
                return
            info['last_update'] = current_position
            # Создаем и отправляем обновленный embed
            from ui.embed_now_playing import create_now_playing_embed
            requester = info.get('requester')
            embed = create_now_playing_embed(
                current_track, player, requester,
                color=color, custom_emojis=custom_emojis
            )
            await message.edit(embed=embed)
        except discord.NotFound:
            self.unregister_message(guild_id)
        except discord.Forbidden:
            self.unregister_message(guild_id)
        except discord.HTTPException as e:
            logger.debug(f"HTTP error for guild {guild_id}: {e}")
        except Exception as e:
            logger.debug(f"Update error for guild {guild_id}: {e}")


# Глобальный экземпляр
now_playing_updater = NowPlayingUpdater()


async def send_now_playing_message(
    channel: discord.TextChannel,
    track: wavelink.Playable,
    player,
    requester: discord.Member,
    view: Optional[discord.ui.View] = None,
    color: str = "default",
    custom_emojis: dict = None
) -> discord.Message:
    from ui.views import MusicPlayerView
    from ui.embed_now_playing import create_now_playing_embed
    embed = create_now_playing_embed(
        track, player, requester,
        color=color, custom_emojis=custom_emojis
    )
    if view is None:
        view = await MusicPlayerView.create(
            player, None, requester,
            color=color, custom_emojis=custom_emojis
        )
    message = await channel.send(embed=embed, view=view)
    view.message = message
    player.view = view
    player.now_playing_message = message
    await now_playing_updater.register_message(
        channel.guild.id,
        message,
        player,
        track,
        requester,
        color=color,
        custom_emojis=custom_emojis
    )
    return message


def cleanup_updater():
    """Очистка ресурсов при завершении работы"""
    now_playing_updater.stop_updater()
