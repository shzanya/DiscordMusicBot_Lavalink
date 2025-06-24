from urllib.parse import urlparse
import re

def is_valid_url(url: str) -> bool:
    """✅ Проверка валидности URL"""
    pattern = re.compile(
        r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    )
    return bool(pattern.match(url))

def is_spotify_url(url: str) -> bool:
    """🎵 Проверка Spotify URL"""
    parsed = urlparse(url)
    return parsed.netloc in ['open.spotify.com', 'spotify.com'] and \
           any(x in parsed.path for x in ['track', 'playlist', 'album'])
