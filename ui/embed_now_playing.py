import discord
import wavelink
from config.constants import get_emoji
from core.player import HarmonyPlayer
from utils.formatters import format_duration


def create_progress_bar(
    position: float,
    duration: float,
    paused: bool = False,
    length: int = 10,
    color: str = "default",
    custom_emojis: dict = None,
) -> str:
    play_icon = (
        get_emoji("NK_MUSICPAUSE", color, custom_emojis)
        if paused
        else get_emoji("NK_MUSICPLAY", color, custom_emojis)
    )
    if duration <= 0 or not isinstance(duration, (int, float)):
        return (
            play_icon
            + get_emoji("NK_MUSICLINESTARTVISIBLE", color, custom_emojis)
            + get_emoji("NK_MUSICLINEEMPTY", color, custom_emojis) * (length - 1)
            + get_emoji("NK_MUSICLINEENDVISIBLE", color, custom_emojis)
        )
    position = max(0, position or 0)
    progress = min(length, max(0, int((position / duration) * length)))
    if progress == 0:
        bar = get_emoji("NK_MUSICLINESTARTVISIBLE", color, custom_emojis)
    else:
        bar = get_emoji("NK_PB_START_FILL", color, custom_emojis)
        bar += get_emoji("NK_MUSICLINEFULLVISIBLE", color, custom_emojis) * (
            progress - 1
        )
    bar += get_emoji("NK_MUSICLINEEMPTY", color, custom_emojis) * (length - progress)
    bar += get_emoji("NK_MUSICLINEENDVISIBLE", color, custom_emojis)
    return play_icon + bar


def create_now_playing_embed(
    track: wavelink.Playable,
    player: HarmonyPlayer,
    requester: discord.Member,
    color: str = "default",
    custom_emojis: dict = None,
) -> discord.Embed:
    if not track:
        return discord.Embed(title="Нет текущего трека", color=0x242429)

    artist = getattr(track, "author", "Неизвестный исполнитель")
    title = getattr(track, "title", "Неизвестный трек")
    uri = getattr(track, "uri", "") or ""
    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"

    try:
        raw_position = player.position if player.position > 0 else 0
        speed = getattr(player, "speed_override", 1.0)
        position = raw_position / speed if speed != 0 else raw_position
    except Exception as e:
        print(f"[DEBUG] Position fetch error: {e}")
        position = 0

    duration = getattr(track, "length", 1) or 1
    try:
        is_paused = getattr(player, "paused", False)
        progress_bar = create_progress_bar(
            position,
            duration,
            paused=is_paused,
            length=9,
            color=color,
            custom_emojis=custom_emojis,
        )
    except Exception as e:
        print(f"[DEBUG] Progress bar error: {e}")
        progress_bar = "▶️ ▱▱▱▱▱▱▱▱▱"

    try:
        current_time = format_duration(int(position))
        total_time = format_duration(int(duration)) if duration > 0 else "∞"
    except Exception:
        current_time = "0:00"
        total_time = "∞"

    requester_name = (
        requester.display_name
        if requester and hasattr(requester, "display_name")
        else "Unknown"
    )

    # Additional safety check
    if not isinstance(requester_name, str):
        requester_name = "Unknown"

    # Получаем текущую громкость
    try:
        volume = getattr(player, "volume", 100)
        volume_emoji = "🔇" if volume == 0 else "🔉" if volume < 50 else "🔊"
        volume_info = f" | {volume_emoji} {volume}%"
    except Exception:
        volume_info = ""

    description = (
        f"{track_link}\n\n"
        f"> Запрос от {requester_name}:\n"
        f"{progress_bar}\n\n"
        f"Играет — `[{current_time}/{total_time}]{volume_info}`"
    )

    embed = discord.Embed(title=artist, description=description, color=0x242429)
    try:
        artwork = getattr(track, "artwork", None) or getattr(track, "thumbnail", None)
        if artwork:
            embed.set_thumbnail(url=artwork)
    except Exception:
        pass

    return embed
