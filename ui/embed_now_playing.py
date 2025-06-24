import discord
import wavelink

from config.constants import Emojis
from core.player import HarmonyPlayer
from utils.formatters import format_duration


def create_progress_bar(position: float, duration: float, paused: bool = False, length: int = 10) -> str:
    """Create progress bar with safe duration handling"""
    play_icon = Emojis.PROGRESS_PAUSE if paused else Emojis.PROGRESS_PLAY

    if duration <= 0 or not isinstance(duration, (int, float)):
        return (
            play_icon +
            Emojis.PROGRESS_LINE_START +
            Emojis.PROGRESS_LINE_EMPTY * (length - 1) +
            Emojis.PROGRESS_LINE_END
        )

    position = max(0, position or 0)
    progress = min(length, max(0, int((position / duration) * length)))

    if progress == 0:
        bar = Emojis.PROGRESS_LINE_START
    else:
        bar = Emojis.PROGRESS_LINE_START_FULL
        bar += Emojis.PROGRESS_LINE_FULL * (progress - 1)

    bar += Emojis.PROGRESS_LINE_EMPTY * (length - progress)
    bar += Emojis.PROGRESS_LINE_END

    return play_icon + bar


def create_now_playing_embed(track: wavelink.Playable, player: HarmonyPlayer, requester: discord.Member) -> discord.Embed:
    """Create now playing embed with comprehensive error handling"""
    if not track:
        return discord.Embed(title="Нет текущего трека", color=0x2B2D31())

    # Safely get track attributes
    artist = getattr(track, 'author', None) or 'Неизвестный исполнитель'
    title = getattr(track, 'title', None) or 'Неизвестный трек'
    uri = getattr(track, 'uri', '') or ''
    
    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"

    # Safely get player position
    try:
        position = getattr(player, 'position', 0) or 0
        if hasattr(position, '__await__'):
            position = 0  # Fallback for async position
    except Exception:
        position = 0

    duration = getattr(track, 'length', None) or 0
    if duration <= 0:
        duration = 1

    # Create progress bar safely
    try:
        is_paused = getattr(player, 'paused', False)
        progress_bar = create_progress_bar(position, duration, paused=is_paused, length=9)
    except Exception as e:
        print(f"[DEBUG] Progress bar error: {e}")
        progress_bar = "▶️ ▱▱▱▱▱▱▱▱▱"

    # Format time safely
    try:
        current_time = format_duration(int(position))
        total_time = format_duration(int(duration)) if duration > 0 else "∞"
    except Exception:
        current_time = "0:00"
        total_time = "∞"

    requester_name = getattr(requester, 'display_name', 'Unknown') if requester else 'Unknown'
    description = (
        f"{track_link}\n\n"
        f"> Запрос от {requester_name}:\n"
        f"{progress_bar}\n\n"
        f"Играет — `[{current_time}/{total_time}]`"
    )

    embed = discord.Embed(
        title=artist,
        description=description,
        color=0x2B2D31
    )

    # Add thumbnail safely
    try:
        artwork = getattr(track, 'artwork', None) or getattr(track, 'thumbnail', None)
        if artwork:
            embed.set_thumbnail(url=artwork)
    except Exception:
        pass

    return embed
