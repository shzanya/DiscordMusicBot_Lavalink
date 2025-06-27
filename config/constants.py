from emojis import Emojis as CustomEmojis

class Emojis:
    _color = "default"

    _color_suffixes = {
        "default": "",
        "red": "red",
        "blue": "blue",
        "green": "green",
        "yellow": "yellow",
        "purple": "purple",
        "orange": "orange",
        "pink": "pink",
        "cyan": "cyan",
        "white": "white",
        "black": "black",
        "gray": "gray",
        "brown": "brown",
        "lime": "lime",
        "teal": "teal",
        "indigo": "indigo",
        "maroon": "maroon",
        "navy": "navy",
        "olive": "olive",
        "aqua": "aqua",
        "fuchsia": "fuchsia",
        "silver": "silver",
        "gold": "gold",
        "coral": "coral",
        "salmon": "salmon",
        "crimson": "crimson"
    }

    @classmethod
    def set_color(cls, color_name: str):
        if color_name.lower() in cls._color_suffixes:
            cls._color = color_name.lower()
        else:
            cls._color = "default"



    @staticmethod
    def ERROR():
        return "❌"


    @classmethod
    def _get_emoji(cls, base_name: str):
        suffix = cls._color_suffixes.get(cls._color, "")
        attr_name = f"{base_name}_{suffix.upper()}" if suffix else base_name
        if hasattr(CustomEmojis, attr_name):
            return getattr(CustomEmojis, attr_name)
        elif hasattr(CustomEmojis, base_name):
            return getattr(CustomEmojis, base_name)
        else:
            return "❓"

    @classmethod
    def NK_BACK(cls): return cls._get_emoji("NK_BACK")
    @classmethod
    def NK_BACKK(cls): return cls._get_emoji("NK_BACKK")
    @classmethod
    def NK_BACKKK(cls): return cls._get_emoji("NK_BACKKK")
    @classmethod
    def NK_HEART(cls): return cls._get_emoji("NK_HEART")
    @classmethod
    def NK_LEAVE(cls): return cls._get_emoji("NK_LEAVE")
    @classmethod
    def NK_MUSICLINEEMPTY(cls): return cls._get_emoji("NK_MUSICLINEEMPTY")
    @classmethod
    def NK_MUSICLINEENDVISIBLE(cls): return cls._get_emoji("NK_MUSICLINEENDVISIBLE")
    @classmethod
    def NK_MUSICLINEFULLVISIBLE(cls): return cls._get_emoji("NK_MUSICLINEFULLVISIBLE")
    @classmethod
    def NK_PB_START_FILL(cls): return cls._get_emoji("NK_PB_START_FILL")
    @classmethod
    def NK_MUSICLINESTARTVISIBLE(cls): return cls._get_emoji("NK_MUSICLINESTARTVISIBLE")
    @classmethod
    def NK_MUSICPAUSE(cls): return cls._get_emoji("NK_MUSICPAUSE")
    @classmethod
    def NK_MUSICPLAY(cls): return cls._get_emoji("NK_MUSICPLAY")
    @classmethod
    def NK_NEXT(cls): return cls._get_emoji("NK_NEXT")
    @classmethod
    def NK_NEXTT(cls): return cls._get_emoji("NK_NEXTT")
    @classmethod
    def NK_NEXTTT(cls): return cls._get_emoji("NK_NEXTTT")
    @classmethod
    def NK_POVTOR(cls): return cls._get_emoji("NK_POVTOR")
    @classmethod
    def NK_RANDOM(cls): return cls._get_emoji("NK_RANDOM")
    @classmethod
    def NK_TEXT(cls): return cls._get_emoji("NK_TEXT")
    @classmethod
    def NK_TIME(cls): return cls._get_emoji("NK_TIME")
    @classmethod
    def NK_TRASH(cls): return cls._get_emoji("NK_TRASH")
    @classmethod
    def NK_VOLUME(cls): return cls._get_emoji("NK_VOLUME")

class Colors:
    PRIMARY = 0x242429
    SUCCESS = 0x242429
    WARNING = 0x242429
    ERROR = 0xEA5455
    INFO = 0x242429
    MUSIC = 0x242429
    PREMIUM = 0x242429
    SPOTIFY = 0x242429

Emojis.set_color("red")
emojis = Emojis
