import discord
import wavelink
from config.constants import Emojis
from utils.formatters import format_duration
from core.player import HarmonyPlayer

def create_progress_bar(position: float, duration: float, paused: bool = False, length: int = 10) -> str:
    play_icon = Emojis.PROGRESS_PAUSE if paused else Emojis.PROGRESS_PLAY

    if duration <= 0:
        return (
            play_icon +
            Emojis.PROGRESS_LINE_START +
            Emojis.PROGRESS_LINE_EMPTY * (length - 1) +
            Emojis.PROGRESS_LINE_END
        )

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
    if not track:
        return discord.Embed(title="Нет текущего трека", color=discord.Color.dark_gray())

    artist = getattr(track, 'author', 'Неизвестный исполнитель')
    title = getattr(track, 'title', 'Неизвестный трек')
    uri = getattr(track, 'uri', '')
    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"

    # ✅ Получаем позицию корректно (некоторые ноды требуют await)
    position = player.position
    duration = track.length or 1

    progress_bar = create_progress_bar(position, duration, paused=player.paused, length=9)
    current_time = format_duration(int(position))
    total_time = format_duration(int(duration)) if duration else "∞"

    description = (
        f"{track_link}\n\n"
        f"> Запрос от {requester.display_name}:\n"
        f"{progress_bar}\n\n"
        f"Играет — `[{current_time}/{total_time}]`"
    )

    embed = discord.Embed(
        title=artist,
        description=description,
        color=discord.Color.green()
    )

    if hasattr(track, 'artwork') and track.artwork:
        embed.set_thumbnail(url=track.artwork)
    elif hasattr(track, 'thumbnail') and track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)

    return embed
