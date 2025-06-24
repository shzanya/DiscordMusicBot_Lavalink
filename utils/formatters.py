import wavelink

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
