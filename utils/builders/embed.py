import discord
from config.constants import Colors, get_emoji
import wavelink


def buildEmbed(
    inter: discord.Interaction,
    title: str,
    description: str,
    include_avatar: bool = True,
) -> discord.Embed:
    embed = discord.Embed(
        title=title, description=description, color=Colors.INFO
    ).set_image(url=Colors.line)

    if include_avatar:
        embed.set_thumbnail(url=inter.user.display_avatar)

    return embed


def get_volume_emoji(
    volume: int, color: str = "default", custom_emojis: dict = None
) -> str:
    """Получение кастомного эмодзи громкости в зависимости от уровня"""
    if volume == 0:
        return get_emoji("NK_VOLUM_M", color, custom_emojis)
    elif volume < 50:
        return get_emoji("NK_VOLUM_M", color, custom_emojis)
    elif volume < 100:
        return get_emoji("NK_VOLUME", color, custom_emojis)
    else:
        return get_emoji("NK_VOLUM_P", color, custom_emojis)


def build_volume_embed(
    volume: int,
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.SUCCESS,
) -> discord.Embed:
    """Создание эмбеда для изменения громкости с кастомными эмодзи"""
    volume_emoji = get_volume_emoji(volume, color, custom_emojis)
    return discord.Embed(
        description=f"{volume_emoji} Громкость установлена на **{volume}%**",
        color=embed_color,
    )


def build_volume_control_embed(
    volume: int,
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.INFO,
) -> discord.Embed:
    """Создание эмбеда для управления громкостью с кастомными эмодзи"""
    return discord.Embed(
        title="Управление громкостью",
        description=f"**Текущая громкость:** {volume}%",
        color=embed_color,
    )


def build_music_status_embed(
    guild_name: str,
    current_track=None,
    queue_count: int = 0,
    is_paused: bool = False,
    loop_mode: str = "Выключен",
    volume: int = 100,
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.MUSIC,
) -> discord.Embed:
    """Создание эмбеда со статусом музыкального плеера с кастомными эмодзи"""
    embed = discord.Embed(
        title=f"🎵 Статус плеера — {guild_name[:30]}", color=embed_color
    )

    # Текущий трек
    if current_track:
        track_info = f"**{current_track.title}** — {current_track.author}"
        status_emoji = (
            get_emoji("NK_MUSICPAUSE", color, custom_emojis)
            if is_paused
            else get_emoji("NK_MUSICPLAY", color, custom_emojis)
        )
        status = f"{status_emoji} Пауза" if is_paused else f"{status_emoji} Играет"
        embed.add_field(
            name="Сейчас играет", value=f"{status} {track_info}", inline=False
        )
    else:
        embed.add_field(name="Сейчас играет", value="❌ Ничего не играет", inline=False)

    # Информация о плеере
    embed.add_field(name="Треков в очереди", value=str(queue_count), inline=True)
    embed.add_field(name="Повтор", value=loop_mode, inline=True)

    # Громкость с кастомным эмодзи
    volume_emoji = get_volume_emoji(volume, color, custom_emojis)
    embed.add_field(name="Громкость", value=f"{volume_emoji} {volume}%", inline=True)

    return embed


def build_skip_embed(
    track,
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.SUCCESS,
) -> discord.Embed:
    """Создание эмбеда для пропуска трека с кастомными эмодзи"""
    skip_emoji = get_emoji("NK_NEXT", color, custom_emojis)
    track_info = f"**{track.title}** — {track.author}"
    return discord.Embed(
        description=f"{skip_emoji} Пропущен трек: {track_info}",
        color=embed_color,
    )


def build_pause_embed(
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.WARNING,
) -> discord.Embed:
    """Создание эмбеда для паузы с кастомными эмодзи"""
    pause_emoji = get_emoji("NK_MUSICPAUSE", color, custom_emojis)
    return discord.Embed(
        description=f"{pause_emoji} Воспроизведение приостановлено",
        color=embed_color,
    )


def build_resume_embed(
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.SUCCESS,
) -> discord.Embed:
    """Создание эмбеда для возобновления с кастомными эмодзи"""
    play_emoji = get_emoji("NK_MUSICPLAY", color, custom_emojis)
    return discord.Embed(
        description=f"{play_emoji} Воспроизведение возобновлено",
        color=embed_color,
    )


def build_stop_embed(
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.WARNING,
) -> discord.Embed:
    """Создание эмбеда для остановки с кастомными эмодзи"""
    stop_emoji = get_emoji("NK_LEAVE", color, custom_emojis)
    return discord.Embed(
        description=f"{stop_emoji} Воспроизведение остановлено и очередь очищена",
        color=embed_color,
    )


def build_shuffle_embed(
    queue_size: int,
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.SUCCESS,
) -> discord.Embed:
    """Создание эмбеда для перемешивания очереди с кастомными эмодзи"""
    shuffle_emoji = get_emoji("NK_RANDOM", color, custom_emojis)
    return discord.Embed(
        description=f"{shuffle_emoji} Очередь перемешана ({queue_size} треков)",
        color=embed_color,
    )


def build_loop_embed(
    mode: str,
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.SUCCESS,
) -> discord.Embed:
    """Создание эмбеда для изменения режима повтора с кастомными эмодзи"""
    loop_emoji = get_emoji("NK_POVTOR", color, custom_emojis)

    mode_text = {
        "none": "Повтор выключен",
        "track": "Повтор трека",
        "queue": "Повтор очереди",
    }.get(mode.lower(), "Неизвестный режим")

    return discord.Embed(
        description=f"{loop_emoji} {mode_text}",
        color=embed_color,
    )


def build_track_added_embed(
    track,
    position: int,
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.SUCCESS,
) -> discord.Embed:
    """Создание эмбеда для добавленного трека с кастомными эмодзи"""
    add_emoji = get_emoji("NK_HEART", color, custom_emojis)
    track_info = f"**{track.title}** — {track.author}"
    position_text = f"позиция {position}" if position > 0 else "следующий"

    return discord.Embed(
        description=f"{add_emoji} Добавлено в очередь ({position_text}): {track_info}",
        color=embed_color,
    )


def build_connection_error_embed(
    message: str = "Не удалось подключиться к голосовому каналу",
    embed_color: int = Colors.ERROR,
) -> discord.Embed:
    """Создание эмбеда для ошибки подключения"""
    return discord.Embed(
        title="Ошибка подключения", description=message, color=embed_color
    )


def build_permission_error_embed(
    message: str = "Вы должны находиться в голосовом канале",
    embed_color: int = Colors.ERROR,
) -> discord.Embed:
    """Создание эмбеда для ошибки прав доступа"""
    return discord.Embed(title="Ошибка доступа", description=message, color=embed_color)


def build_search_error_embed(
    query: str,
    embed_color: int = Colors.ERROR,
) -> discord.Embed:
    """Создание эмбеда для ошибки поиска"""
    safe_query = query[:100] if len(query) > 100 else query
    return discord.Embed(
        title="Ошибка поиска",
        description=f"Ничего не найдено по запросу: `{safe_query}`",
        color=embed_color,
    )


def build_disconnect_embed(
    reason: str = "все вышли",
    embed_color: int = Colors.WARNING,
) -> discord.Embed:
    """Создание эмбеда для отключения от голосового канала"""
    return discord.Embed(
        description=f"—・Выход из голосового канала\nЯ покинула канал, потому что {reason} чтобы не нагружать сервер бота если никого нету в канале",
        color=embed_color,
    )


def build_no_next_track_embed(
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.WARNING,
) -> discord.Embed:
    """Создание эмбеда для отсутствия следующего трека с кастомными эмодзи"""
    next_emoji = get_emoji("NK_NEXT", color, custom_emojis)
    return discord.Embed(
        description=f"{next_emoji} Нет следующего трека в очереди",
        color=embed_color,
    )


def build_no_previous_track_embed(
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.WARNING,
) -> discord.Embed:
    """Создание эмбеда для отсутствия предыдущего трека с кастомными эмодзи"""
    back_emoji = get_emoji("NK_BACK", color, custom_emojis)
    return discord.Embed(
        description=f"{back_emoji} Нет предыдущего трека в очереди",
        color=embed_color,
    )


def build_navigation_error_embed(
    direction: str = "навигация",
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = Colors.WARNING,
) -> discord.Embed:
    """Создание эмбеда для ошибки навигации с кастомными эмодзи"""
    if direction == "next":
        emoji = get_emoji("NK_NEXT", color, custom_emojis)
        text = "Нет следующего трека"
    elif direction == "previous":
        emoji = get_emoji("NK_BACK", color, custom_emojis)
        text = "Нет предыдущего трека"
    else:
        emoji = "❌"
        text = "Ошибка навигации"

    return discord.Embed(
        description=f"{emoji} {text}",
        color=embed_color,
    )


def build_track_finished_embed(
    track: wavelink.Playable,
    position: int,
    color: str = "default",
    custom_emojis: dict = None,
    embed_color: int = None,
) -> discord.Embed:
    """⏹️ Создание embed для завершенного трека с кастомными эмодзи"""
    from config.constants import get_emoji, Colors

    artist = getattr(track, "author", "Неизвестный исполнитель")
    title = getattr(track, "title", "Неизвестный трек")
    uri = getattr(track, "uri", "")
    artwork = getattr(track, "artwork", None)

    track_link = f"**[{title}]({uri})**" if uri else f"**{title}**"

    # Время воспроизведения (позиция)
    from ui.music_embeds import format_duration

    listened_time = format_duration(int(position))

    # Получаем эмодзи
    status_emoji = get_emoji("NK_MusicPlay", color, custom_emojis)

    # Определяем цвет эмбеда
    if embed_color is None:
        try:
            guild_id = getattr(track, "guild_id", None)
            if guild_id:
                # Используем синхронный способ получения цвета
                embed_color = Colors.PRIMARY
            else:
                embed_color = Colors.PRIMARY
        except Exception:
            embed_color = Colors.PRIMARY

    embed = discord.Embed(
        title=artist,
        description=f"{track_link}\n\n**{status_emoji} Статус:** Прослушано ({listened_time})",
        color=embed_color,
        timestamp=discord.utils.utcnow(),
    )

    if artwork:
        embed.set_thumbnail(url=artwork)

    return embed
