# 🎨 Система управления эмодзи для Discord UI кнопок

## Цель

Обеспечить корректную инициализацию кастомных эмодзи для кнопок Discord UI сразу при создании, избегая отображения временных символов (точек).

## Архитектурное решение

### 1. Базовый класс для UI View

#### `BaseEmojiView` (`ui/base_view.py`)

Базовый класс для всех View с поддержкой кастомных эмодзи.

**Основные возможности:**

- Автоматическая загрузка настроек эмодзи из БД
- Инициализация эмодзи при создании View
- Обновление эмодзи для конкретных кнопок
- Специальная обработка для кнопки pause

**Ключевые методы:**

```python
@classmethod
async def create(cls, guild_id=None, emoji_settings=None, **kwargs)
# Создание View с автоматической загрузкой настроек эмодзи

async def _initialize_emojis()
# Инициализация эмодзи для всех кнопок

def _setup_emoji_mapping()
# Настройка маппинга эмодзи - переопределяется в наследниках

def update_emoji(custom_id, emoji_name)
# Обновление эмодзи для конкретной кнопки
```

#### `EmojiSettings` (`ui/base_view.py`)

Класс для управления настройками эмодзи гильдии.

**Основные возможности:**

- Хранение цвета и кастомных эмодзи
- Загрузка настроек из БД
- Получение эмодзи с учетом настроек

**Ключевые методы:**

```python
@classmethod
async def from_guild(cls, guild_id)
# Создание настроек эмодзи из настроек гильдии

def get_emoji(emoji_name)
# Получение эмодзи с учетом настроек гильдии
```

### 2. Использование в наследниках

#### `MusicPlayerView`

```python
class MusicPlayerView(BaseEmojiView):
    def __init__(self, player, message=None, requester=None, **kwargs):
        super().__init__(**kwargs)
        self.player = player
        self.message = message
        self.requester = requester

        # Устанавливаем начальный эмодзи для кнопки pause
        is_paused = getattr(self.player, 'paused', False)
        initial_emoji_name = "NK_MUSICPAUSE" if is_paused else "NK_MUSICPLAY"

        # Создаем кнопку pause с правильным эмодзи
        pause_button = ui.Button(
            emoji=self.get_emoji(initial_emoji_name),
            label=None,
            style=discord.ButtonStyle.secondary,
            custom_id="music:pause"
        )
        pause_button.callback = self.pause_button_callback
        self.add_item(pause_button)

    def _setup_emoji_mapping(self):
        """Настройка маппинга эмодзи для MusicPlayerView"""
        self._emoji_map = {
            "music:shuffle": "NK_RANDOM",
            "music:previous": "NK_BACK",
            "music:skip": "NK_NEXT",
            "music:loop": "NK_POVTOR",
            "music:seek": "NK_TIME",
            "music:volume": "NK_VOLUME",
            "music:stop": "NK_LEAVE",
            "music:text": "NK_TEXT",
            "music:like": "NK_HEART",
        }
```

#### `QueueView`

```python
class QueueView(BaseEmojiView):
    def _setup_emoji_mapping(self):
        """Настройка маппинга эмодзи для QueueView"""
        self._emoji_map = {
            "music:shuffle": "NK_BACKKK",
            "music:previous": "NK_BACKK",
            "music:skip": "NK_TRASH",
            "music:next": "NK_NEXTT",
            "music:last": "NK_NEXTTT",
        }
```

### 3. Программное создание кнопки pause

Кнопка pause создается программно в `__init__` с правильным эмодзи сразу при инициализации:

```python
def __init__(self, player, message=None, requester=None, **kwargs):
    super().__init__(**kwargs)
    # ... другая инициализация

    # Устанавливаем начальный эмодзи для кнопки pause
    is_paused = getattr(self.player, 'paused', False)
    initial_emoji_name = "NK_MUSICPAUSE" if is_paused else "NK_MUSICPLAY"

    # Создаем кнопку pause с правильным эмодзи
    pause_button = ui.Button(
        emoji=self.get_emoji(initial_emoji_name),
        label=None,
        style=discord.ButtonStyle.secondary,
        custom_id="music:pause"
    )
    pause_button.callback = self.pause_button_callback
    self.add_item(pause_button)
```

### 4. Обновление эмодзи в runtime

```python
async def pause_button_callback(self, interaction: discord.Interaction) -> None:
    # ... логика обработки

    is_paused = getattr(self.player, 'paused', False)
    await self.player.pause(not is_paused)

    # Обновляем эмодзи кнопки pause
    new_emoji_name = "NK_MUSICPAUSE" if not is_paused else "NK_MUSICPLAY"
    self.update_emoji("music:pause", new_emoji_name)
```

## Преимущества новой системы

1. **Немедленная инициализация** - эмодзи устанавливаются сразу при создании View
2. **Отсутствие временных символов** - нет отображения точек при загрузке
3. **Централизованное управление** - все настройки эмодзи в одном месте
4. **Легкое расширение** - простое добавление новых View с эмодзи
5. **Автоматическая загрузка** - настройки загружаются из БД автоматически
6. **Специальная обработка** - поддержка динамических эмодзи (pause)
7. **Программное создание** - кнопка pause создается с правильным эмодзи сразу

## Пример использования

```python
# Создание MusicPlayerView с автоматической загрузкой настроек
view = await MusicPlayerView.create(
    player=player,
    requester=requester,
    guild_id=guild.id  # Автоматически загрузит настройки
)

# Создание с явными настройками
emoji_settings = EmojiSettings(color="red", custom_emojis={...})
view = await MusicPlayerView.create(
    player=player,
    requester=requester,
    emoji_settings=emoji_settings
)
```

## Миграция существующих View

1. Наследовать от `BaseEmojiView` вместо `ui.View`
2. Реализовать метод `_setup_emoji_mapping()`
3. Обновить метод `create()` для использования новой системы
4. Убрать старые методы обновления эмодзи
5. Использовать `self.update_emoji()` для динамических обновлений
6. Для кнопки pause - создать программно в `__init__` с правильным эмодзи
