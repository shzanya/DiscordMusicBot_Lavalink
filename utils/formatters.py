"""
📊 Утилиты для форматирования данных
"""
import wavelink
from typing import Optional


def format_duration(ms: int) -> str:
    """📊 Форматирование длительности в hh:mm:ss или mm:ss"""
    if ms <= 0:
        return "00:00"

    seconds = ms // 1000
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_track_info(track: wavelink.Playable) -> str:
    """🎵 Форматирование информации о треке"""
    duration = format_duration(track.length if track.length else 0)
    return f"**{track.title}** by **{track.author}** [{duration}]"


def format_track_title(track: wavelink.Playable, max_length: int = 50) -> str:
    """✂️ Обрезка названия трека до указанной длины"""
    title = getattr(track, 'title', 'Неизвестный трек')
    if len(title) > max_length:
        return title[:max_length-3] + "..."
    return title


def format_requester_info(requester: Optional[object]) -> str:
    """👤 Форматирование информации о пользователе"""
    if not requester:
        return "`Неизвестно`"
    
    if hasattr(requester, 'display_name'):
        return f"`{requester.display_name}`"
    elif hasattr(requester, 'name'):
        return f"`{requester.name}`"
    else:
        return "`Неизвестно`"


def format_queue_position(position: int) -> str:
    """📍 Форматирование позиции в очереди"""
    if position == 1:
        return "следующий"
    elif position <= 5:
        return f"{position}-й в очереди"
    else:
        return f"#{position} в очереди"


def truncate_text(text: str, max_length: int = 100) -> str:
    """✂️ Обрезка текста до указанной длины"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def format_file_size(size_bytes: int) -> str:
    """📁 Форматирование размера файла"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"
