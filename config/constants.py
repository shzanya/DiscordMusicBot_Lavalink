from emojis import Emojis as CustomEmojis
import re

class Emojis:
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

    @staticmethod
    def ERROR():
        return "❌"


def get_emoji(base_name: str, color: str = "default", custom_emojis: dict = None) -> str:
    suffix = Emojis._color_suffixes.get(color, "")
    attr_name = f"{base_name}_{suffix.upper()}" if suffix else base_name
    if custom_emojis and base_name in custom_emojis:
        return custom_emojis[base_name]
    if hasattr(CustomEmojis, attr_name):
        return getattr(CustomEmojis, attr_name)
    elif hasattr(CustomEmojis, base_name):
        return getattr(CustomEmojis, base_name)
    else:
        return "❓"


class Colors:
    PRIMARY = 0x242429
    SUCCESS = 0x242429
    WARNING = 0x242429
    ERROR = 0xEA5455
    INFO = 0x242429
    MUSIC = 0x242429
    PREMIUM = 0x242429
    SPOTIFY = 0x242429

emojis = Emojis


def get_button_emoji(
    base_name: str,
    color: str = "default",
    custom_emojis: dict = None
):
    """
    Возвращает PartialEmoji для кастомных emoji Discord или unicode-символ для обычных.
    Используется для discord.ui.Button/discord.PartialEmoji.
    """
    emoji_str = get_emoji(base_name, color, custom_emojis)
    # Если это кастомный emoji вида <a:name:id> или <:name:id>
    match = re.match(
        r'<a?:(\w+):(\d+)>',
        emoji_str
    )
    if match:
        import discord
        name, id_ = match.group(1), int(match.group(2))
        return discord.PartialEmoji(
            name=name,
            id=id_
        )
    # Если это unicode
    return emoji_str
