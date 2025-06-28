import logging
import asyncio
from typing import Optional
from lyricsgenius import Genius
from config.settings import Settings
import yt_dlp


def get_soundcloud_description(url: str) -> Optional[str]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "force_generic_extractor": False,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("description")
    except Exception as e:
        print(f"Ошибка при получении описания с SoundCloud: {e}")
        return None


class LyricsService:
    """📝 Быстрый сервис получения текстов песен с кешем"""

    _lyrics_cache: dict[str, str] = {}

    def __init__(self):
        self.logger = logging.getLogger("LyricsService")
        token = getattr(Settings, "GENIUS_ACCESS_TOKEN", None)

        if token:
            self.genius = Genius(
                token,
                skip_non_songs=True,
                excluded_terms=["(Remix)", "(Live)"],
                timeout=5,
            )
            self.genius.verbose = False
            self.genius.remove_section_headers = True
        else:
            self.genius = None
            self.logger.warning("⚠️ Genius API не инициализирован: отсутствует токен")

    async def get_lyrics(
        self, title: str, artist: str = "", url: str = ""
    ) -> Optional[str]:
        # 🔁 Проверка кеша
        cache_key = f"{title.lower().strip()}|{artist.lower().strip()}"
        if cache_key in self._lyrics_cache:
            return self._lyrics_cache[cache_key]

        # 🧠 Сначала пробуем Genius
        if self.genius:
            try:
                song = await asyncio.to_thread(
                    self.genius.search_song, title.strip(), artist.strip()
                )
                if song and song.lyrics:
                    lyrics = song.lyrics.strip()
                    self._lyrics_cache[cache_key] = lyrics
                    return lyrics
            except Exception as e:
                self.logger.error(f"❌ Genius ошибка: {e}")

        # 🎧 Если трек с SoundCloud — пробуем описание
        if "soundcloud.com" in url:
            try:
                loop = asyncio.get_event_loop()
                lyrics = await loop.run_in_executor(
                    None, get_soundcloud_description, url
                )
                if lyrics:
                    self._lyrics_cache[cache_key] = lyrics
                    return lyrics
            except Exception as e:
                self.logger.error(f"⚠️ Ошибка SoundCloud lyrics: {e}")

        return None
