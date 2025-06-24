import discord
import wavelink
import math
import asyncio
from typing import Optional, Dict
from config.constants import Colors, Emojis
from core.player import HarmonyPlayer
from utils.formatters import format_duration
from ui.views import MusicControllerView





class NowPlayingUpdater:
    """Класс для автоматического обновления embed с информацией о воспроизведении"""
    
    def __init__(self):
        self.active_messages: Dict[int, dict] = {}  # guild_id -> message_info
        self.update_task = None
        
    def start_updater(self):
        """Запуск фоновой задачи обновления"""
        if self.update_task is None or self.update_task.done():
            self.update_task = asyncio.create_task(self._update_loop())
    
    def stop_updater(self):
        """Остановка фоновой задачи"""
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
    
    async def register_message(self, guild_id: int, message: discord.Message, player: HarmonyPlayer, track: wavelink.Playable, requester: discord.Member):
        """Регистрация сообщения для автообновления"""
        self.active_messages[guild_id] = {
            'message': message,
            'player': player,
            'track': track,
            'requester': requester,
            'last_update': 0
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
                for guild_id, info in list(self.active_messages.items()):
                    try:
                        await self._update_message(guild_id, info)
                    except Exception as e:
                        print(f"[DEBUG] Update error for guild {guild_id}: {e}")
                        # Удаляем проблемное сообщение
                        self.unregister_message(guild_id)
                
                await asyncio.sleep(10)  # Обновляем каждые 10 секунд
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[DEBUG] Update loop error: {e}")
 
    
    async def _update_message(self, guild_id: int, info: dict):
        message = info['message']
        player = info['player']

        if not player.playing or not player.current:
            self.unregister_message(guild_id)
            return

        current_position = int(player.position)
        current_track = player.current

        force_update = False
        if info['track'] != current_track:
            info['track'] = current_track
            force_update = True

        if not force_update and abs(current_position - info['last_update']) < 5:
            return

        info['last_update'] = current_position

        requester = info['requester']
        embed = create_now_playing_embed(current_track, player, requester)

        try:
            # Оптимизация: сравнение с прошлым embed
            old_embed = message.embeds[0] if message.embeds else None
            if not old_embed or old_embed.description != embed.description:
                await message.edit(embed=embed)
        except discord.NotFound:
            self.unregister_message(guild_id)
        except discord.Forbidden:
            self.unregister_message(guild_id)


# Глобальный экземпляр updater
now_playing_updater = NowPlayingUpdater()


def create_now_playing_embed(track: wavelink.Playable, player: HarmonyPlayer, requester: discord.Member) -> discord.Embed:
    """🎵 Создание embed для текущего трека в точном стиле примера"""
   
    # Получаем информацию о треке
    artist = getattr(track, 'author', 'Неизвестный исполнитель')
    title = getattr(track, 'title', 'Неизвестный трек')
    uri = getattr(track, 'uri', '')
   
    # Создаем ссылку на трек (если есть)
    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"
   
    # Формируем прогресс-бар (точно как в примере - 9 сегментов)
    position = player.position
    duration = track.length
    progress_bar = create_progress_bar(position, duration, paused=player.paused, length=9)
   
    # Форматируем время
    current_time = format_duration(int(position))
    total_time = format_duration(int(duration)) if duration else "∞"
   
    # Описание точно как в примере
    description = f"{track_link}\n\n"
    description += f"> Запрос от {requester.display_name}:\n"
    description += f"{progress_bar}\n\n"
    description += f"Играет — `[{current_time}/{total_time}]`"
   
    # Создаем embed без цвета (как в примере)
    embed = discord.Embed(
        title=artist,
        description=description,
        color=None
    )
   
    # Добавляем обложку трека
    if hasattr(track, 'artwork') and track.artwork:
        embed.set_thumbnail(url=track.artwork)
    elif hasattr(track, 'thumbnail') and track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
   
    return embed


def create_progress_bar(position: float, duration: float, paused: bool = False, length: int = 10) -> str:
    """🎛️ Создание прогресс-бара с кастомными эмодзи и иконкой в начале"""

    # Плей или пауза эмодзи в начале строки
    play_icon = Emojis.PROGRESS_PAUSE if paused else Emojis.PROGRESS_PLAY

    # Если длительность неизвестна
    if duration <= 0:
        return (
            play_icon +
            Emojis.PROGRESS_LINE_START +
            Emojis.PROGRESS_LINE_EMPTY * (length - 1) +
            Emojis.PROGRESS_LINE_END
        )

    # Считаем прогресс
    progress = min(length, max(0, int((position / duration) * length)))

    # Начало: пустое или заполненное
    if progress == 0:
        bar = Emojis.PROGRESS_LINE_START
    else:
        bar = Emojis.PROGRESS_LINE_START_FULL
        bar += Emojis.PROGRESS_LINE_FULL * (progress - 1)

    # Добавляем пустые сегменты
    empty_segments = length - progress
    bar += Emojis.PROGRESS_LINE_EMPTY * empty_segments

    # Завершение
    bar += Emojis.PROGRESS_LINE_END

    # Возвращаем бар с иконкой плей/пауза в начале
    return play_icon + bar


async def send_now_playing_message(channel, track: wavelink.Playable, player: HarmonyPlayer, requester: discord.Member) -> discord.Message:
    """Отправка сообщения с автообновлением и кнопками управления"""

    embed = create_now_playing_embed(track, player, requester)

    # Временно создаём view без message
    view = MusicControllerView(player, None)

    # Отправляем сообщение
    message = await channel.send(embed=embed, view=view)

    # Привязываем сообщение к view (после отправки)
    view.message = message

    # Обновляем view (т.к. теперь у неё есть message)
    await message.edit(view=view)

    # Регистрируем сообщение для автообновления
    await now_playing_updater.register_message(
        channel.guild.id,
        message,
        player,
        track,
        requester
    )

    return message


def create_track_embed_spotify_style(track: wavelink.Playable, player: HarmonyPlayer, requester: discord.Member) -> discord.Embed:
    """🎵 Создание embed в стиле Spotify"""
   
    artist = getattr(track, 'author', 'Неизвестный исполнитель')
    title = getattr(track, 'title', 'Неизвестный трек')
    uri = getattr(track, 'uri', '')
   
    # Создаем ссылку на трек
    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"
   
    # Прогресс-бар
    position = player.position
    duration = track.length
    progress_bar = create_progress_bar(position, duration, 9)  # 9 сегментов как в примере
   
    # Время
    current_time = format_duration(int(position))
    total_time = format_duration(int(duration)) if duration else "∞"
   
    # Описание
    description = f"{track_link}\n\n"
    description += f"> Запрос от {requester.display_name}:\n"
    description += f"{progress_bar}\n\n"
    description += f"Играет — `[{current_time}/{total_time}]`"
   
    embed = discord.Embed(
        title=artist,
        description=description,
        color=Colors.SPOTIFY
    )
   
    # Обложка
    if hasattr(track, 'artwork') and track.artwork:
        embed.set_thumbnail(url=track.artwork)
   
    return embed


def create_queue_embed_advanced(queue: wavelink.Queue, page: int, current: Optional[wavelink.Playable], player: HarmonyPlayer) -> discord.Embed:
    """📋 Расширенный embed для очереди"""
   
    embed = discord.Embed(
        title=f"{Emojis.QUEUE} Очередь воспроизведения",
        color=Colors.SPOTIFY
    )
   
    per_page = 10
    total_tracks = len(queue)
    total_pages = max(1, math.ceil(total_tracks / per_page))
    page = max(1, min(page, total_pages))
   
    start = (page - 1) * per_page
    end = start + per_page
   
    # Текущий трек
    if current:
        position = player.position
        duration = current.length
        progress = int((position / duration) * 10) if duration else 0
        progress_bar = "▰" * progress + "▱" * (10 - progress)
       
        current_info = f"**[{current.title}]({getattr(current, 'uri', '')})**\n"
        current_info += f"*{getattr(current, 'author', 'Неизвестно')}*\n"
        current_time = format_duration(int(position))
        total_time = format_duration(int(duration)) if duration else "∞"
        current_info += f"`{current_time}` {progress_bar} `{total_time}`"
       
        embed.add_field(
            name="🎵 Сейчас играет",
            value=current_info,
            inline=False
        )
   
    # Треки в очереди
    if queue:
        queue_text = ""
        for i, track in enumerate(queue[start:end], start=start + 1):
            duration_str = format_duration(int(track.length)) if hasattr(track, 'length') and track.length else "N/A"
            queue_text += f"`{i}.` **{track.title}**\n"
            queue_text += f"    *{getattr(track, 'author', 'Неизвестно')}* • `{duration_str}`\n\n"
       
        embed.add_field(
            name="📋 Следующие треки",
            value=queue_text or "Очередь пуста",
            inline=False
        )
    else:
        embed.add_field(
            name="📋 Очередь",
            value="Пусто",
            inline=False
        )
   
    # Информация о странице
    if total_pages > 1:
        embed.set_footer(text=f"Страница {page}/{total_pages} • {total_tracks} треков")
    else:
        embed.set_footer(text=f"{total_tracks} треков в очереди")
   
    return embed


def create_error_embed(title: str, description: str) -> discord.Embed:
    """❌ Создание embed для ошибок"""
    return discord.Embed(
        title=f"{Emojis.ERROR} {title}",
        description=description,
        color=Colors.ERROR
    )


def create_success_embed(title: str, description: str) -> discord.Embed:
    """✅ Создание embed для успешных операций"""
    return discord.Embed(
        title=f"{Emojis.SUCCESS} {title}",
        description=description,
        color=Colors.SUCCESS
    )


def create_warning_embed(title: str, description: str) -> discord.Embed:
    """⚠️ Создание embed для предупреждений"""
    return discord.Embed(
        title=f"{Emojis.WARNING} {title}",
        description=description,
        color=Colors.WARNING
    )


def create_info_embed(title: str, description: str) -> discord.Embed:
    """ℹ️ Создание embed для информации"""
    return discord.Embed(
        title=f"{Emojis.INFO} {title}",
        description=description,
        color=Colors.INFO
    )


def create_track_embed(track: wavelink.Playable, title: str = None, color = None, player: HarmonyPlayer = None, requester: discord.Member = None) -> discord.Embed:
    """🎵 Универсальная функция для создания embed трека"""
    
    # Если переданы player и requester, используем create_now_playing_embed
    if player and requester and hasattr(player, 'position'):
        return create_now_playing_embed(track, player, requester)
    
    # Иначе создаем простой embed без прогресс-бара
    artist = getattr(track, 'author', 'Неизвестный исполнитель')
    track_title = getattr(track, 'title', 'Неизвестный трек')
    uri = getattr(track, 'uri', '')
    
    # Создаем ссылку на трек
    track_link = f"**[{track_title}]({uri})**" if uri else f"**{track_title}**"
    
    # Используем переданный title или стандартный
    embed_title = title if title else artist
    embed_color = color if color else Colors.SUCCESS
    
    embed = discord.Embed(
        title=embed_title,
        description=track_link,
        color=embed_color
    )
    
    # Добавляем обложку трека
    if hasattr(track, 'artwork') and track.artwork:
        embed.set_thumbnail(url=track.artwork)
    elif hasattr(track, 'thumbnail') and track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    
    return embed


def create_queue_embed(queue: wavelink.Queue, page: int = 1, current: Optional[wavelink.Playable] = None, player: HarmonyPlayer = None) -> discord.Embed:
    """📋 Alias для create_queue_embed_advanced для обратной совместимости"""
    return create_queue_embed_advanced(queue, page, current, player)


# Очистка при завершении работы бота
def cleanup_updater():
    """Очистка ресурсов при завершении работы"""
    now_playing_updater.stop_updater()
