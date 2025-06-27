import asyncio

from typing import Dict

import discord
import wavelink

from config.constants import Colors, emojis
from core.player import HarmonyPlayer
from ui.embed_now_playing import create_now_playing_embed, create_progress_bar
from utils.formatters import format_duration
from ui.views import MusicPlayerView


class NowPlayingUpdater:
    """Fixed updater class with proper error handling"""
    
    def __init__(self):
        self.active_messages: Dict[int, dict] = {}
        self.update_task = None
        
    def start_updater(self):
        """Start background update task"""
        if self.update_task is None or self.update_task.done():
            self.update_task = asyncio.create_task(self._update_loop())
    
    def stop_updater(self):
        """Stop background update task"""
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
    
    async def register_message(self, guild_id: int, message: discord.Message, player: HarmonyPlayer, track: wavelink.Playable, requester: discord.Member):
        """Register message for auto-updating"""
        if not message or not player:
            return
            
        self.active_messages[guild_id] = {
            'message': message,
            'player': player,
            'track': track,
            'requester': requester,
            'last_update': 0
        }
        self.start_updater()
    
    def unregister_message(self, guild_id: int):
        """Remove message from auto-updating"""
        if guild_id in self.active_messages:
            del self.active_messages[guild_id]
        
        if not self.active_messages:
            self.stop_updater()
    
    async def _update_loop(self):
        """Main update loop with comprehensive error handling"""
        try:
            while self.active_messages:
                items = list(self.active_messages.items())
                
                for guild_id, info in items:
                    try:
                        await self._update_message(guild_id, info)
                    except Exception as e:
                        print(f"[DEBUG] Update error for guild {guild_id}: {e}")
                        self.unregister_message(guild_id)
                
                await asyncio.sleep(3)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[DEBUG] Critical update loop error: {e}")

    async def _update_message(self, guild_id: int, info: dict):
        """Update single message with safety checks"""
        try:
            message = info.get('message')
            player = info.get('player')

            if not message or not player:
                self.unregister_message(guild_id)
                return

            # Check if player is valid and playing
            if not hasattr(player, 'playing') or not player.playing or not hasattr(player, 'current') or not player.current:
                self.unregister_message(guild_id)
                return

            # Get position safely
            try:
                current_position = int(getattr(player, 'position', 0) or 0)
            except Exception:
                current_position = 0

            current_track = player.current

            # Force update if track changed
            force_update = False
            if info.get('track') != current_track:
                info['track'] = current_track
                force_update = True

            # Update timing check
            last_update = info.get('last_update', 0)
            if not force_update and abs(current_position - last_update) < 1:
                return

            info['last_update'] = current_position

            # Create and send updated embed
            requester = info.get('requester')
            embed = create_now_playing_embed(current_track, player, requester)
            await message.edit(embed=embed)
            
        except discord.NotFound:
            self.unregister_message(guild_id)
        except discord.Forbidden:
            self.unregister_message(guild_id)
        except discord.HTTPException as e:
            print(f"[DEBUG] HTTP error for guild {guild_id}: {e}")
        except Exception as e:
            print(f"[DEBUG] Update error for guild {guild_id}: {e}")

# Глобальный экземпляр
now_playing_updater = NowPlayingUpdater()


def create_queue_embed(
    guild: discord.Guild,
    now_playing: wavelink.Playable,
    queue: list,
    page: int,
    total_pages: int,
    user: discord.User
) -> discord.Embed:
    embed = discord.Embed(
        title=f"—・Очередь сервера {guild.name}",
        description="",
        color=Colors.MUSIC
    )

    # Сейчас играет
    duration = now_playing.length // 1000
    minutes = duration // 60
    seconds = duration % 60
    requester = getattr(now_playing, "requester", None)
    requester_name = f"`{requester.display_name}`" if requester else "`Неизвестно`"

    embed.description += f"**Сейчас играет:** [{now_playing.title}]({now_playing.uri}) | `{minutes:02}:{seconds:02}` | {requester_name}\n"

    # Треки на текущей странице
    items_per_page = 10
    start = (page - 1) * items_per_page
    end = start + items_per_page
    tracks = queue[start:end]

    for i, track in enumerate(tracks, start=start + 1):
        duration = track.length // 1000
        minutes = duration // 60
        seconds = duration % 60
        requester = getattr(track, "requester", None)
        requester_name = f"`{requester.display_name}`" if requester else "`Неизвестно`"

        line = f"\n**{i})** [{track.title}]({track.uri}) | `{minutes:02}:{seconds:02}` | {requester_name}"
        # Убедимся, что не превышаем лимит Discord
        if len(embed.description) + len(line) > 4096:
            embed.description += "\n...и другие треки."
            break
        embed.description += line

    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"Страница: {page}/{total_pages}")
    return embed



async def send_now_playing_message(channel, track: wavelink.Playable, player: HarmonyPlayer, requester: discord.Member) -> discord.Message:
    """Отправка сообщения с автообновлением и кнопками управления"""
    embed = create_now_playing_embed(track, player, requester)

    # Создаем view без message
    view = await MusicPlayerView.create(player, None, requester)

    # Отправляем embed с view
    message = await channel.send(embed=embed, view=view)

    # Привязываем message к view
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



def create_error_embed(title: str, description: str) -> discord.Embed:
    """❌ Создание embed для ошибок"""
    return discord.Embed(
        title=f"{emojis.ERROR()} {title}",
        description=description,
        color=Colors.ERROR
    )


def create_success_embed(title: str, description: str) -> discord.Embed:
    """✅ Создание embed для успешных операций"""
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=Colors.SUCCESS
    )


def create_warning_embed(title: str, description: str) -> discord.Embed:
    """⚠️ Создание embed для предупреждений"""
    return discord.Embed(
        title=f"⚠️ {title}",
        description=description,
        color=Colors.WARNING
    )


def create_info_embed(title: str, description: str) -> discord.Embed:
    """ℹ️ Создание embed для информации"""
    return discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=Colors.INFO
    )


# Очистка при завершении работы бота
def cleanup_updater():
    """Очистка ресурсов при завершении работы"""
    now_playing_updater.stop_updater()
