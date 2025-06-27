"""
📊 Система автообновления сообщений с прогрессом воспроизведения
"""
import asyncio
import logging
from typing import Dict, Optional

import discord
import wavelink

from utils.formatters import format_duration, format_track_title, format_requester_info

logger = logging.getLogger(__name__)


class NowPlayingUpdater:
    """Класс для автообновления сообщений с прогрессом воспроизведения"""
    
    def __init__(self):
        self.active_messages: Dict[int, dict] = {}
        self.update_task: Optional[asyncio.Task] = None
        self.update_interval = 3  # Секунды между обновлениями
        
    def start_updater(self):
        """Запуск фонового обновления"""
        if self.update_task is None or self.update_task.done():
            self.update_task = asyncio.create_task(self._update_loop())
            logger.debug("Progress updater started")
    
    def stop_updater(self):
        """Остановка фонового обновления"""
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
            logger.debug("Progress updater stopped")
    
    async def register_message(
        self, 
        guild_id: int, 
        message: discord.Message, 
        player, 
        track: wavelink.Playable, 
        requester: discord.Member
    ):
        """Регистрация сообщения для автообновления"""
        if not message or not player:
            logger.warning(f"Cannot register message for guild {guild_id}: invalid message or player")
            return
            
        self.active_messages[guild_id] = {
            'message': message,
            'player': player,
            'track': track,
            'requester': requester,
            'last_update': 0,
            'last_position': 0,
            'error_count': 0
        }
        
        logger.debug(f"Registered message for guild {guild_id}")
        self.start_updater()
    
    def unregister_message(self, guild_id: int):
        """Удаление сообщения из автообновления"""
        if guild_id in self.active_messages:
            del self.active_messages[guild_id]
            logger.debug(f"Unregistered message for guild {guild_id}")
        
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
                        
                        # Увеличиваем счетчик ошибок
                        info['error_count'] = info.get('error_count', 0) + 1
                        
                        # Если слишком много ошибок, отключаем обновление
                        if info['error_count'] > 5:
                            logger.warning(f"Too many errors for guild {guild_id}, unregistering")
                            self.unregister_message(guild_id)
                
                await asyncio.sleep(self.update_interval)
                
        except asyncio.CancelledError:
            logger.debug("Update loop cancelled")
        except Exception as e:
            logger.error(f"Critical update loop error: {e}")

    async def _update_message(self, guild_id: int, info: dict):
        """Обновление одного сообщения"""
        try:
            message = info.get('message')
            player = info.get('player')

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
            except (ValueError, TypeError):
                current_position = 0

            current_track = player.current

            # Принудительное обновление при смене трека
            force_update = False
            if info.get('track') != current_track:
                info['track'] = current_track
                force_update = True
                logger.debug(f"Track changed for guild {guild_id}, forcing update")

            # Проверка времени обновления (обновляем каждые 5 секунд позиции)
            last_position = info.get('last_position', 0)
            if not force_update and abs(current_position - last_position) < 5000:  # 5 секунд в миллисекундах
                return

            info['last_position'] = current_position

            # Создаем и отправляем обновленный embed
            embed = self._create_progress_embed(current_track, player, info.get('requester'))
            
            # Получаем view если есть
            view = getattr(player, 'view', None)
            
            await message.edit(embed=embed, view=view)
            
            # Сбрасываем счетчик ошибок при успешном обновлении
            info['error_count'] = 0
            
        except discord.NotFound:
            logger.debug(f"Message not found for guild {guild_id}")
            self.unregister_message(guild_id)
        except discord.Forbidden:
            logger.warning(f"No permission to edit message for guild {guild_id}")
            self.unregister_message(guild_id)
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limit
                logger.warning(f"Rate limited for guild {guild_id}")
                await asyncio.sleep(2)
            else:
                logger.debug(f"HTTP error for guild {guild_id}: {e}")
                raise
        except Exception as e:
            logger.debug(f"Update error for guild {guild_id}: {e}")
            raise

    def _create_progress_embed(self, track: wavelink.Playable, player, requester) -> discord.Embed:
        """Создание embed с прогрессом воспроизведения"""
        from config.constants import Colors
        
        # Информация о треке
        track_title = format_track_title(track, max_length=50)
        author = getattr(track, 'author', 'Неизвестный исполнитель')
        requester_info = format_requester_info(requester)
        
        # Прогресс воспроизведения
        current_pos = int(getattr(player, 'position', 0) or 0)
        total_duration = track.length or 0
        
        # Создаем прогресс-бар
        progress_bar = self._create_progress_bar(current_pos, total_duration)
        
        # Форматируем время
        current_time = format_duration(current_pos)
        total_time = format_duration(total_duration)
        
        # Создаем embed
        embed = discord.Embed(
            title="🎵 Сейчас играет",
            description=f"**[{track_title}]({getattr(track, 'uri', '')})**\n{author}",
            color=Colors.MUSIC
        )
        
        # Добавляем прогресс
        embed.add_field(
            name="Прогресс",
            value=f"{progress_bar}\n`{current_time}` / `{total_time}`",
            inline=False
        )
        
        # Добавляем информацию о заказчике
        embed.add_field(
            name="Заказал",
            value=requester_info,
            inline=True
        )
        
        # Добавляем статус плеера
        status = "⏸️ Пауза" if getattr(player, 'paused', False) else "▶️ Играет"
        embed.add_field(
            name="Статус",
            value=status,
            inline=True
        )
        
        # Добавляем громкость
        volume = getattr(player, 'volume', 100)
        embed.add_field(
            name="Громкость",
            value=f"{volume}%",
            inline=True
        )
        
        # Добавляем обложку
        artwork = getattr(track, 'artwork', None) or getattr(track, 'thumbnail', None)
        if artwork:
            embed.set_thumbnail(url=artwork)
        
        # Добавляем timestamp
        embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    def _create_progress_bar(self, current: int, total: int, length: int = 20) -> str:
        """Создание визуального прогресс-бара"""
        if total <= 0:
            return "▬" * length
        
        progress = min(current / total, 1.0)
        filled_length = int(length * progress)
        
        if filled_length == 0:
            return "🔘" + "▬" * (length - 1)
        elif filled_length >= length:
            return "▬" * (length - 1) + "🔘"
        else:
            return "▬" * filled_length + "🔘" + "▬" * (length - filled_length - 1)


# Глобальный экземпляр
now_playing_updater = NowPlayingUpdater()


async def send_now_playing_message(
    channel, 
    track: wavelink.Playable, 
    player, 
    requester: discord.Member
) -> discord.Message:
    """Отправка сообщения с автообновлением и кнопками управления"""
    from ui.views import MusicPlayerView
    
    # Создаем начальный embed
    embed = now_playing_updater._create_progress_embed(track, player, requester)
    
    # Создаем view с кнопками управления
    view = MusicPlayerView(player, None, requester)
    
    # Отправляем сообщение
    message = await channel.send(embed=embed, view=view)
    
    # Привязываем message к view и player
    view.message = message
    player.view = view
    player.now_playing_message = message
    
    # Регистрируем автообновление
    await now_playing_updater.register_message(
        channel.guild.id,
        message,
        player,
        track,
        requester
    )
    
    logger.info(f"Now playing message sent for guild {channel.guild.id}")
    return message


async def update_now_playing_message(
    player,
    track: wavelink.Playable,
    requester: discord.Member = None
) -> bool:
    """Обновление существующего сообщения с треком"""
    try:
        if not hasattr(player, 'now_playing_message') or not player.now_playing_message:
            return False
        
        embed = now_playing_updater._create_progress_embed(track, player, requester)
        view = getattr(player, 'view', None)
        
        await player.now_playing_message.edit(embed=embed, view=view)
        
        # Обновляем информацию в updater
        guild_id = player.guild.id
        if guild_id in now_playing_updater.active_messages:
            now_playing_updater.active_messages[guild_id]['track'] = track
            if requester:
                now_playing_updater.active_messages[guild_id]['requester'] = requester
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to update now playing message: {e}")
        return False


def cleanup_updater():
    """Очистка ресурсов при завершении работы"""
    now_playing_updater.stop_updater()
    logger.info("Progress updater cleaned up")


def get_active_messages_count() -> int:
    """Получение количества активных сообщений для мониторинга"""
    return len(now_playing_updater.active_messages)


async def force_update_all():
    """Принудительное обновление всех активных сообщений"""
    for guild_id, info in list(now_playing_updater.active_messages.items()):
        try:
            await now_playing_updater._update_message(guild_id, info)
        except Exception as e:
            logger.error(f"Force update failed for guild {guild_id}: {e}")


# Utility functions for external use
def is_message_being_updated(guild_id: int) -> bool:
    """Проверка, обновляется ли сообщение для данной гильдии"""
    return guild_id in now_playing_updater.active_messages


def get_message_info(guild_id: int) -> Optional[dict]:
    """Получение информации о сообщении для данной гильдии"""
    return now_playing_updater.active_messages.get(guild_id)
