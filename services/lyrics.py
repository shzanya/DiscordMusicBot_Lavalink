import logging
import asyncio
from typing import Optional
from lyricsgenius import Genius
from config.settings import Settings

class LyricsService:
    """📝 Сервис получения текстов песен"""
    
    def __init__(self):
        self.logger = logging.getLogger('LyricsService')
        if Settings.GENIUS_ACCESS_TOKEN:
            self.genius = Genius(Settings.GENIUS_ACCESS_TOKEN)
            self.genius.verbose = False
        else:
            self.genius = None
            self.logger.warning("⚠️ Genius API не инициализирован: отсутствует токен")
    
    async def get_lyrics(self, title: str, artist: str = "") -> Optional[str]:
        """📝 Получение текста песни"""
        if not self.genius:
            return None

        try:
            song = await asyncio.to_thread(self.genius.search_song, title, artist)
            if song:
                return song.lyrics
            return None
        except Exception as e:
            self.logger.error(f"❌ Ошибка получения текста: {e}")
            return None
