import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    """⚙️ Настройки приложения"""
    
    # 🤖 Discord
    DISCORD_TOKEN: str = os.getenv('DISCORD_TOKEN')
    COMMAND_PREFIX: str = os.getenv('COMMAND_PREFIX', '♪')
    OWNER_ID: int = int(os.getenv('OWNER_ID', '0'))
    
    # 🎵 Lavalink
    LAVALINK_HOST: str = os.getenv('LAVALINK_HOST', 'localhost')
    LAVALINK_PORT: int = int(os.getenv('LAVALINK_PORT', '2333'))
    LAVALINK_PASSWORD: str = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')
    LAVALINK_SECURE: bool = os.getenv('LAVALINK_SECURE', 'false').lower() == 'true'
    
    # 💾 База данных
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'sqlite+aiosqlite:///harmony.db')
    
    # 🎵 Spotify
    SPOTIFY_CLIENT_ID: Optional[str] = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_CLIENT_SECRET: Optional[str] = os.getenv('SPOTIFY_CLIENT_SECRET')
    
    # 📺 YouTube
    YOUTUBE_API_KEY: Optional[str] = os.getenv('YOUTUBE_API_KEY')
    
    # 📝 Genius (для текстов)
    GENIUS_ACCESS_TOKEN: Optional[str] = os.getenv('GENIUS_ACCESS_TOKEN')
    
    # 🎛️ Настройки по умолчанию
    DEFAULT_VOLUME: int = 100
    MAX_QUEUE_SIZE: int = 1000
    AUTO_DISCONNECT_TIMEOUT: int = 300  # 5 минут
    
    # MongoDB connection string (default: localhost)
    MONGODB_URI = "mongodb+srv://shanya:Qazedc123@discord-bot-yt.fdfytur.mongodb.net/?retryWrites=true&w=majority&appName=discord-Bot-yt"
    
    @classmethod
    def validate(cls) -> bool:
        """✅ Валидация настроек"""
        if not cls.DISCORD_TOKEN:
            raise ValueError("❌ DISCORD_TOKEN не установлен!")
        return True
