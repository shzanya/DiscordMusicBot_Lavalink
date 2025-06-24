from emojis import Emojis as CustomEmojis

class Emojis:
    """🎨 Эмодзи для интерфейса"""
    NK_RANDOM = CustomEmojis.NK_RANDOM
    NK_BACK = CustomEmojis.NK_BACK
    NK_MUSICPLAY = CustomEmojis.NK_MUSICPLAY
    NK_MUSICPAUSE = CustomEmojis.NK_MUSICPAUSE
    NK_NEXT = CustomEmojis.NK_NEXT
    NK_POVTOR = CustomEmojis.NK_POVTOR
    NK_TIME = CustomEmojis.NK_TIME
    NK_VOLUME = CustomEmojis.NK_VOLUME
    NK_LEAVE = CustomEmojis.NK_LEAVE
    NK_TEXT = CustomEmojis.NK_TEXT
    NK_HEART = CustomEmojis.NK_HEART

    # Прогресс-бар
    PROGRESS_PLAY = CustomEmojis.NK_MUSICPLAY
    PROGRESS_PAUSE = CustomEmojis.NK_MUSICPAUSE
    PROGRESS_LINE_START = CustomEmojis.NK_MUSICLINESTARTVISIBLE
    PROGRESS_LINE_START_FULL = CustomEmojis.NK_MUSICLINESTARTFULLVISIBLE
    PROGRESS_LINE_FULL = CustomEmojis.NK_MUSICLINEFULLVISIBLE
    PROGRESS_LINE_EMPTY = CustomEmojis.NK_MUSICLINEEMPTY
    PROGRESS_LINE_END = CustomEmojis.NK_MUSICLINEENDVISIBLE
    # 🎵 Музыка
    PLAY = "▶️"
    PAUSE = "⏸️"
    STOP = "⏹️"
    SKIP = "⏭️"
    PREVIOUS = "⏮️"
    SHUFFLE = "🔀"
    REPEAT = "🔄"
    REPEAT_ONE = "🔂"

    # 🔊 Звук
    VOLUME_LOW = "🔉"
    VOLUME_HIGH = "🔊"
    VOLUME_MUTE = "🔇"

    # 📋 Очередь
    QUEUE = "📋"
    ADD = "➕"
    REMOVE = "➖"
    CLEAR = "🗑️"

    # ❤️ Избранное
    HEART = "❤️"
    HEART_BROKEN = "💔"
    STAR = "⭐"

    # 🎚️ Эффекты
    BASS = "🎛️"
    NIGHTCORE = "🌙"
    VAPORWAVE = "🌊"

    # ✅ Статусы
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"

    # 🔐 Доступ
    LOCK = "🔒"
    UNLOCK = "🔓"
    KEY = "🔑"

class Colors:
    """🎨 Цвета для embed'ов"""
    
    PRIMARY = 0x7289DA      # Discord Blurple
    SUCCESS = 0x43B581      # Зеленый
    WARNING = 0xFAA61A      # Желтый
    ERROR = 0xF04747        # Красный
    INFO = 0x5865F2         # Синий
    MUSIC = 0xFF6B9D        # Розовый
    PREMIUM = 0xFFD700      # Золотой
    SPOTIFY = 0x1DB954      # Spotify зеленый
