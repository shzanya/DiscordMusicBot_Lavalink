import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from config.settings import Settings
import wavelink
import logging

class SpotifyService:
    """🎵 Сервис интеграции со Spotify"""
   
    def __init__(self):
        self.logger = logging.getLogger('SpotifyService')
        if not Settings.SPOTIFY_CLIENT_ID or not Settings.SPOTIFY_CLIENT_SECRET:
            self.sp = None
            self.logger.warning("⚠️ Spotify ключи не настроены")
            return
           
        try:
            self.sp = spotipy.Spotify(
                client_credentials_manager=SpotifyClientCredentials(
                    client_id=Settings.SPOTIFY_CLIENT_ID,
                    client_secret=Settings.SPOTIFY_CLIENT_SECRET
                )
            )
            # Проверяем ключи
            self.sp.search("test", limit=1)
            self.logger.info("✅ Spotify API инициализирован")
        except Exception as e:
            self.sp = None
            self.logger.error(f"❌ Ошибка инициализации Spotify: {e}")
   
    async def get_tracks(self, url: str) -> wavelink.Playlist | list[wavelink.Playable] | None:
        """🔍 Получение треков из Spotify URL"""
        if not self.sp:
            self.logger.warning("Spotify API не инициализирован")
            return None
       
        try:
            if 'track' in url:
                self.logger.info(f"Обработка Spotify трека: {url}")
                track = self.sp.track(url)
                query = f"{track['name']} {track['artists'][0]['name']}"
                self.logger.info(f"Поиск в YouTube: {query}")
                
                tracks = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
                if tracks:
                    self.logger.info(f"Найдено {len(tracks)} треков")
                    return tracks
                else:
                    self.logger.warning(f"Треки не найдены для запроса: {query}")
                    return None
               
            elif 'playlist' in url:
                self.logger.info(f"Обработка Spotify плейлиста: {url}")
                playlist = self.sp.playlist(url)
                tracks = []
                
                for item in playlist['tracks']['items']:
                    if not item['track']:
                        continue
                    track = item['track']
                    query = f"{track['name']} {track['artists'][0]['name']}"
                    results = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
                    if results:
                        tracks.append(results[0])
               
                if tracks:
                    return wavelink.Playlist(
                        name=playlist['name'],
                        tracks=tracks
                    )
                return None
               
            elif 'album' in url:
                self.logger.info(f"Обработка Spotify альбома: {url}")
                album = self.sp.album(url)
                tracks = []
                
                for item in album['tracks']['items']:
                    query = f"{item['name']} {album['artists'][0]['name']}"
                    results = await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
                    if results:
                        tracks.append(results[0])
               
                if tracks:
                    return wavelink.Playlist(
                        name=album['name'],
                        tracks=tracks
                    )
                return None
                
            else:
                self.logger.warning(f"Неподдерживаемый тип Spotify URL: {url}")
                return None
               
        except Exception as e:
            self.logger.error(f"❌ Ошибка Spotify: {e}")
            return None
