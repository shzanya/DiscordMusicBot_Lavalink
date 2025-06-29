"""
🎵 Embed'ы для музыкальных функций с использованием форматтеров
"""

import discord
import wavelink
from typing import List, Optional

from config.constants import Colors
from ui.embed_now_playing import create_progress_bar
from utils.builders.embed import build_volume_embed
from utils.formatters import (
    format_duration,
    format_track_info,
    format_track_title,
    format_requester_info,
    format_queue_position,
    truncate_text,
)


def create_queue_embed(
    guild: discord.Guild,
    now_playing: wavelink.Playable,
    queue: List[wavelink.Playable],
    page: int,
    total_pages: int,
    user: discord.User,
) -> discord.Embed:
    """📄 Создание embed для очереди треков"""
    if not queue and not now_playing:
        embed = discord.Embed(
            title="—・Пустая очередь сервера",
            description="Я покинула канал, потому что в очереди не осталось треков",
            color=Colors.MUSIC,
        )
        return embed
    embed = discord.Embed(title=f"—・Очередь сервера {guild.name}", color=Colors.MUSIC)

    # Сейчас играет
    if now_playing:
        duration = format_duration(now_playing.length or 0)
        requester_info = format_requester_info(getattr(now_playing, "requester", None))
        track_title = format_track_title(now_playing, max_length=45)

        embed.description = (
            f"**Сейчас играет:** [{track_title}]({now_playing.uri}) "
            f"| {duration} | {requester_info}\n"
        )
    else:
        embed.description = "**Ничего не играет**\n"

    # Треки в очереди
    if queue:
        queue_lines = []
        for i, track in enumerate(queue, start=1):
            duration = format_duration(track.length or 0)
            requester_info = format_requester_info(getattr(track, "requester", None))
            track_title = format_track_title(track, max_length=40)

            line = (
                f"**{i})** [{track_title}]({track.uri}) | {duration} | {requester_info}"
            )

            # Проверяем лимит Discord (4096 символов)
            current_description = (
                embed.description + "\n".join(queue_lines) + "\n" + line
            )
            if len(current_description) > 3900:  # Оставляем запас
                queue_lines.append("...и другие треки.")
                break

            queue_lines.append(line)

        embed.description += "\n" + "\n".join(queue_lines)
    else:
        embed.description += "\n*Очередь пуста*"

    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"Страница: {page}/{total_pages}")
    return embed


def create_track_embed(
    track: wavelink.Playable, requester: discord.Member, position: int, duration: int
) -> discord.Embed:
    """🎵 Создание embed в стиле Spotify"""

    artist = getattr(track, "author", "Неизвестный исполнитель")
    title = getattr(track, "title", "Неизвестный трек")
    uri = getattr(track, "uri", "")

    # Ссылка на трек
    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"

    # Прогресс-бар
    progress_bar = create_progress_bar(position, duration, 9)

    # Время
    current_time = format_duration(int(position))
    total_time = format_duration(int(duration)) if duration else "∞"

    # Описание
    description = f"{track_link}\n\n"
    description += f"> Запрос от {requester.display_name}:\n"
    description += f"{progress_bar}\n\n"
    description += f"Играет — `[{current_time}/{total_time}]`"

    embed = discord.Embed(title=artist, description=description, color=Colors.SPOTIFY)

    # Обложка
    artwork = getattr(track, "artwork", None)
    if artwork:
        embed.set_thumbnail(url=artwork)

    return embed


def create_playlist_embed(playlist_name: str, track_count: int) -> discord.Embed:
    """📋 Создание embed для плейлиста"""
    playlist_display = truncate_text(playlist_name, 80)
    return discord.Embed(
        description=f'Добавлен плейлист "**{playlist_display}**" ({track_count} треков)',
        color=Colors.SUCCESS,
    )


def create_track_added_embed(track: wavelink.Playable, position: int) -> discord.Embed:
    """➕ Создание embed для добавленного трека"""
    track_info = format_track_info(track)
    position_text = format_queue_position(position)

    return discord.Embed(
        description=f"Добавлено в очередь ({position_text}): {track_info}",
        color=Colors.SUCCESS,
    )


def create_now_playing_embed(
    track: wavelink.Playable, player, requester: Optional[discord.Member] = None
) -> discord.Embed:
    """▶️ Создание embed для воспроизводимого трека в Spotify-стиле"""
    artist = getattr(track, "author", "Неизвестный исполнитель")
    title = getattr(track, "title", "Неизвестный трек")
    uri = getattr(track, "uri", "")
    artwork = getattr(track, "artwork", None)
    position = int(getattr(player, "position", 0) or 0)
    duration = getattr(track, "length", 0)

    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"
    progress = f"{format_duration(position)}/{format_duration(duration)}"

    embed = discord.Embed(
        title=artist,
        description=f"{track_link}\n\n**Играет — [{progress}]**",
        color=Colors.SUCCESS,
        timestamp=discord.utils.utcnow(),
    )

    if artwork:
        embed.set_thumbnail(url=artwork)
    if requester:
        embed.set_footer(text=f"Запросил: {requester.display_name}")

    return embed


def create_empty_queue_embed() -> discord.Embed:
    """🚪 Создание embed для пустой очереди"""
    return discord.Embed(
        description=(
            "—・Пустая очередь сервера\n"
            "Я покинула канал, потому что в очереди не осталось треков"
        ),
        color=Colors.PRIMARY,
        timestamp=discord.utils.utcnow(),
    )


def create_track_finished_embed(
    track: wavelink.Playable, position: int
) -> discord.Embed:
    """⏹️ Создание embed для завершенного трека в Spotify-стиле"""

    artist = getattr(track, "author", "Неизвестный исполнитель")
    title = getattr(track, "title", "Неизвестный трек")
    uri = getattr(track, "uri", "")
    artwork = getattr(track, "artwork", None)

    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"

    # Время воспроизведения (позиция)
    listened_time = format_duration(int(position))

    embed = discord.Embed(
        title=artist,
        description=f"{track_link}\n\n**> Статус:** Прослушано ({listened_time})",
        color=Colors.PRIMARY,
        timestamp=discord.utils.utcnow(),
    )

    if artwork:
        embed.set_thumbnail(url=artwork)

    return embed


def create_search_error_embed(query: str) -> discord.Embed:
    """❌ Создание embed для ошибки поиска"""
    safe_query = truncate_text(query, 100)
    return discord.Embed(
        title="Ошибка поиска",
        description=f"Ничего не найдено по запросу: `{safe_query}`",
        color=Colors.ERROR,
    )


def create_connection_error_embed(
    message: str = "Не удалось подключиться к голосовому каналу",
) -> discord.Embed:
    """🔌 Создание embed для ошибки подключения"""
    return discord.Embed(
        title="Ошибка подключения", description=message, color=Colors.ERROR
    )


def create_permission_error_embed(
    message: str = "Вы должны находиться в голосовом канале",
) -> discord.Embed:
    """🚫 Создание embed для ошибки прав доступа"""
    return discord.Embed(
        title="Ошибка доступа", description=message, color=Colors.ERROR
    )


def create_music_status_embed(
    guild_name: str,
    current_track: Optional[wavelink.Playable] = None,
    queue_count: int = 0,
    is_paused: bool = False,
    loop_mode: str = "Выключен",
    volume: int = 100,
) -> discord.Embed:
    """📊 Создание embed со статусом музыкального плеера"""
    embed = discord.Embed(
        title=f"🎵 Статус плеера — {truncate_text(guild_name, 30)}", color=Colors.MUSIC
    )

    # Текущий трек
    if current_track:
        track_info = format_track_info(current_track)
        status = "⏸️ Пауза" if is_paused else "▶️ Играет"
        embed.add_field(
            name="Сейчас играет", value=f"{status} {track_info}", inline=False
        )
    else:
        embed.add_field(name="Сейчас играет", value="❌ Ничего не играет", inline=False)

    # Информация о плеере
    embed.add_field(name="Треков в очереди", value=str(queue_count), inline=True)
    embed.add_field(name="Повтор", value=loop_mode, inline=True)
    embed.add_field(name="Громкость", value=f"{volume}%", inline=True)

    return embed


def create_volume_embed(
    volume: int,
    color: str = "default",
    custom_emojis: dict = None,
) -> discord.Embed:
    """🔊 Создание embed для изменения громкости с кастомными эмодзи"""
    return build_volume_embed(
        volume=volume,
        color=color,
        custom_emojis=custom_emojis,
        embed_color=Colors.SUCCESS,
    )


def create_skip_embed(track: wavelink.Playable) -> discord.Embed:
    """⏭️ Создание embed для пропуска трека"""
    track_info = format_track_info(track)
    return discord.Embed(
        description=f"⏭️ Пропущен трек: {track_info}", color=Colors.SUCCESS
    )


def create_pause_embed() -> discord.Embed:
    """⏸️ Создание embed для паузы"""
    return discord.Embed(
        description="⏸️ Воспроизведение приостановлено", color=Colors.WARNING
    )


def create_resume_embed() -> discord.Embed:
    """▶️ Создание embed для возобновления"""
    return discord.Embed(
        description="▶️ Воспроизведение возобновлено", color=Colors.SUCCESS
    )


def create_stop_embed() -> discord.Embed:
    """⏹️ Создание embed для остановки"""
    return discord.Embed(
        description="⏹️ Воспроизведение остановлено и очередь очищена",
        color=Colors.WARNING,
    )


def create_shuffle_embed(queue_size: int) -> discord.Embed:
    """🔀 Создание embed для перемешивания очереди"""
    return discord.Embed(
        description=f"🔀 Очередь перемешана ({queue_size} треков)", color=Colors.SUCCESS
    )


def create_loop_embed(mode: str) -> discord.Embed:
    """🔁 Создание embed для изменения режима повтора"""
    mode_emoji = {"none": "❌", "track": "🔂", "queue": "🔁"}.get(mode.lower(), "❓")

    mode_text = {
        "none": "Повтор выключен",
        "track": "Повтор трека",
        "queue": "Повтор очереди",
    }.get(mode.lower(), "Неизвестный режим")

    return discord.Embed(description=f"{mode_emoji} {mode_text}", color=Colors.SUCCESS)
