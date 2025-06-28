import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from config.settings import Settings
import wavelink
import logging


class SpotifyService:
    """🎵 Сервис интеграции со Spotify через Lavalink"""

    def __init__(self):
        self.logger = logging.getLogger("SpotifyService")
        if not Settings.SPOTIFY_CLIENT_ID or not Settings.SPOTIFY_CLIENT_SECRET:
            self.sp = None
            self.logger.warning("⚠️ Spotify ключи не настроены")
            return

        try:
            self.sp = spotipy.Spotify(
                client_credentials_manager=SpotifyClientCredentials(
                    client_id=Settings.SPOTIFY_CLIENT_ID,
                    client_secret=Settings.SPOTIFY_CLIENT_SECRET,
                )
            )
            # Проверяем ключи
            self.sp.search("test", limit=1)
            self.logger.info("✅ Spotify API инициализирован")
        except Exception as e:
            self.sp = None
            self.logger.error(f"❌ Ошибка инициализации Spotify: {e}")

    async def get_tracks(
        self, url: str
    ) -> wavelink.Playlist | list[wavelink.Playable] | None:
        """🔍 Получение треков из Spotify URL через Lavalink"""
        if not self.sp:
            self.logger.warning("Spotify API не инициализирован")
            return None

        try:
            # Прямой поиск Spotify URL через Lavalink (без указания источника)
            tracks = await wavelink.Playable.search(url)

            if tracks:
                self.logger.info(f"✅ Lavalink нашел {len(tracks)} Spotify треков")
                return tracks
            else:
                self.logger.warning(f"❌ Lavalink не нашел треки для: {url}")
                # Fallback на SoundCloud
                return await self._fallback_search(url)

        except Exception as e:
            self.logger.error(f"❌ Ошибка Lavalink Spotify: {e}")
            # Fallback на SoundCloud
            return await self._fallback_search(url)

    async def _fallback_search(
        self, url: str
    ) -> wavelink.Playlist | list[wavelink.Playable] | None:
        """🔄 Резервный поиск через SoundCloud если Spotify не работает"""
        if not self.sp:
            return None

        try:
            if "track" in url:
                self.logger.info("Fallback: обработка Spotify трека через SoundCloud")
                track = self.sp.track(url)
                query = f"{track['name']} {track['artists'][0]['name']}"

                tracks = await wavelink.Playable.search(
                    query, source=wavelink.TrackSource.SoundCloud
                )
                if tracks:
                    # Добавляем метаданные Spotify к SoundCloud треку
                    tracks[0].spotify_id = track["id"]
                    tracks[0].spotify_url = url
                    return tracks

            elif "playlist" in url:
                self.logger.info(
                    "Fallback: обработка Spotify плейлиста через SoundCloud"
                )
                playlist = self.sp.playlist(url)
                tracks = []

                for item in playlist["tracks"]["items"]:
                    if not item["track"]:
                        continue
                    track = item["track"]
                    query = f"{track['name']} {track['artists'][0]['name']}"
                    results = await wavelink.Playable.search(
                        query, source=wavelink.TrackSource.SoundCloud
                    )
                    if results:
                        # Добавляем Spotify метаданные
                        results[0].spotify_id = track["id"]
                        tracks.append(results[0])

                if tracks:
                    return wavelink.Playlist(name=playlist["name"], tracks=tracks)

            elif "album" in url:
                self.logger.info("Fallback: обработка Spotify альбома через SoundCloud")
                album = self.sp.album(url)
                tracks = []

                for item in album["tracks"]["items"]:
                    query = f"{item['name']} {album['artists'][0]['name']}"
                    results = await wavelink.Playable.search(
                        query, source=wavelink.TrackSource.SoundCloud
                    )
                    if results:
                        results[0].spotify_id = item["id"]
                        tracks.append(results[0])

                if tracks:
                    return wavelink.Playlist(name=album["name"], tracks=tracks)

            return None

        except Exception as e:
            self.logger.error(f"❌ Ошибка fallback поиска: {e}")
            return None

    def is_spotify_url(self, url: str) -> bool:
        """🔍 Проверка является ли URL ссылкой Spotify"""
        return "spotify.com" in url or "open.spotify.com" in url
