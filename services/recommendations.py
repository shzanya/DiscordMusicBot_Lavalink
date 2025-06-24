import wavelink
import random
import logging
from typing import Optional, List

from services.spotify import SpotifyService


class RecommendationService:
    """🎯 Сервис рекомендаций"""
    
    def __init__(self, bot):
        self.bot = bot
        self.spotify = SpotifyService()
        self.logger = logging.getLogger('RecommendationService')
    
    async def get_recommendations(self, track: wavelink.Playable, limit: int = 5) -> List[wavelink.Playable]:
        """🎯 Получение рекомендованных треков"""
        try:
            if self.spotify.sp:
                # Используем Spotify API для рекомендаций
                track_info = await self.spotify.get_tracks(track.uri)
                if track_info:
                    recommendations = self.spotify.sp.recommendations(
                        seed_tracks=[track_info.id],
                        limit=limit
                    )
                    tracks = []
                    for rec in recommendations.get('tracks', []):
                        query = f"{rec['name']} {rec['artists'][0]['name']}"
                        results = await wavelink.Playable.search(query)
                        if results and isinstance(results, list):
                            tracks.append(results[0])
                        elif hasattr(results, 'tracks') and results.tracks:
                            tracks.append(results.tracks[0])
                    return tracks
            
            # Fallback: похожие песни по названию исполнителя
            query = f"{track.author} similar songs"
            results = await wavelink.Playable.search(query, limit=limit)
            if not results:
                return []
            if isinstance(results, list):
                return random.sample(results, min(len(results), limit))
            if hasattr(results, 'tracks') and results.tracks:
                return random.sample(results.tracks, min(len(results.tracks), limit))
            return []
        
        except Exception as e:
            self.logger.error(f"❌ Ошибка рекомендаций: {e}")
            return []
