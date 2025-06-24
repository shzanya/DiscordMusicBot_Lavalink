# ⚠️ Автогенерированный файл с эмодзи
# Не редактируй вручную!

class Emojis:
    """🚀 Класс со всеми application эмодзи"""

    NK_MUSICLINEEMPTY = "<:NK_MusicLineEmpty:1386993479078510732>"
    NK_MUSICLINEENDVISIBLE = "<:NK_MusicLineEndVisible:1386993480500514886>"
    NK_MUSICLINEFULLVISIBLE = "<:NK_MusicLineFullVisible:1386993482710913045>"
    NK_MUSICLINESTARTFULLVISIBLE = "<:NK_MusicLineStartFullVisible:1386993484292161604>"
    NK_MUSICLINESTARTVISIBLE = "<:NK_MusicLineStartVisible:1386993485894254682>"
    NK_MUSICPLAY = "<:NK_MusicPlay:1386993487529902101>"
    NK_MUSICPAUSE = "<:NK_MusicPause:1386995536111861761>"
    NK_BACK = "<:NK_BACK:1387010220651446293>"
    NK_HEART = "<:NK_HEART:1387010222165459095>"
    NK_LEAVE = "<:NK_LEAVE:1387010224077930630>"
    NK_NEXT = "<:NK_NEXT:1387010233607651329>"
    NK_POVTOR = "<:NK_POVTOR:1387010234978926693>"
    NK_RANDOM = "<:NK_RANDOM:1387010237814276136>"
    NK_TEXT = "<:NK_TEXT:1387010238921572463>"
    NK_TIME = "<:NK_TIME:1387010240670728274>"
    NK_VOLUME = "<:NK_VOLUME:1387010242872737813>"

    @classmethod
    def get_all(cls):
        return {k: v for k, v in cls.__dict__.items() if not k.startswith('_') and k != 'get_all'}
