import discord
import wavelink
from config.constants import emojis
from core.player import HarmonyPlayer
from utils.formatters import format_duration

def create_progress_bar(position: float, duration: float, paused: bool = False, length: int = 10) -> str:
    play_icon = emojis.NK_MUSICPAUSE() if paused else emojis.NK_MUSICPLAY()
    if duration <= 0 or not isinstance(duration, (int, float)):
        return (
            play_icon +
            emojis.NK_MUSICLINESTARTVISIBLE() +
            emojis.NK_MUSICLINEEMPTY() * (length - 1) +
            emojis.NK_MUSICLINEENDVISIBLE()
        )
    position = max(0, position or 0)
    progress = min(length, max(0, int((position / duration) * length)))
    if progress == 0:
        bar = emojis.NK_MUSICLINESTARTVISIBLE()
    else:
        bar = emojis.NK_PB_START_FILL()
        bar += emojis.NK_MUSICLINEFULLVISIBLE() * (progress - 1)
    bar += emojis.NK_MUSICLINEEMPTY() * (length - progress)
    bar += emojis.NK_MUSICLINEENDVISIBLE()
    return play_icon + bar

async def create_now_playing_embed(track: wavelink.Playable, player: HarmonyPlayer, requester: discord.Member) -> discord.Embed:
    if not track:
        return discord.Embed(title="Нет текущего трека", color=0x2B2D31)
    
    artist = getattr(track, 'author', 'Неизвестный исполнитель')
    title = getattr(track, 'title', 'Неизвестный трек')
    uri = getattr(track, 'uri', '') or ''
    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"
    
    try:
        position = player.position if player.position > 0 else 0  # Use position directly, no sleep
    except Exception as e:
        print(f"[DEBUG] Position fetch error: {e}")
        position = 0
    
    duration = getattr(track, 'length', 1) or 1
    try:
        is_paused = getattr(player, 'paused', False)
        progress_bar = create_progress_bar(position, duration, paused=is_paused, length=9)
    except Exception as e:
        print(f"[DEBUG] Progress bar error: {e}")
        progress_bar = "▶️ ▱▱▱▱▱▱▱▱▱"
    
    try:
        current_time = format_duration(int(position))
        total_time = format_duration(int(duration)) if duration > 0 else "∞"
    except Exception:
        current_time = "0:00"
        total_time = "∞"
    
    requester_name = requester.display_name if requester and hasattr(requester, 'display_name') else 'Unknown'
    description = (
        f"{track_link}\n\n"
        f"> Запрос от {requester_name}:\n"
        f"{progress_bar}\n\n"
        f"Играет — `[{current_time}/{total_time}]`"
    )
    
    embed = discord.Embed(title=artist, description=description, color=0x2B2D31)
    try:
        artwork = getattr(track, 'artwork', None) or getattr(track, 'thumbnail', None)
        if artwork:
            embed.set_thumbnail(url=artwork)
    except Exception:
        pass
    
    return embed
