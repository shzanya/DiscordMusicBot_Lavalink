# Архитектура Music Bot

## Обзор

Этот проект представляет собой профессиональный Discord музыкальный бот, построенный с использованием современной архитектуры, вдохновленной TypeScript проектами.

## Структура проекта

```
musicBot/
├── core/                    # Основная логика
│   ├── events/             # Обработчики событий
│   │   ├── __init__.py
│   │   └── track_events.py # События треков (TrackStart, TrackEnd)
│   ├── player.py           # Основной плеер
│   └── bot.py              # Основной класс бота
├── commands/               # Команды
│   └── music/
│       ├── playback.py     # Основные команды воспроизведения
│       ├── queue_command.py # Команда очереди с пагинацией
│       ├── loop_command.py # Команда режимов повтора
│       └── effects.py      # Аудио эффекты
├── ui/                     # Пользовательский интерфейс
│   ├── embeds.py           # Эмбеды
│   ├── views.py            # Discord Views
│   └── progress_updater.py # Обновление прогресса
├── utils/                  # Утилиты
│   └── autocomplete.py     # Автокомплит
└── services/               # Сервисы
    └── mongo_service.py    # Работа с базой данных
```

## Ключевые компоненты

### 1. Система событий (Events)

События треков вынесены в отдельные классы по примеру TypeScript:

```python
# core/events/track_events.py
class TrackStartEvent:
    async def handle(self, payload: wavelink.TrackStartEventPayload) -> None:
        # Обработка начала трека

class TrackEndEvent:
    async def handle(self, payload: wavelink.TrackEndEventPayload) -> None:
        # Обработка окончания трека
```

### 2. Автокомплит

Профессиональная система автокомплита с кэшированием:

```python
# utils/autocomplete.py
class AutocompleteManager:
    async def track_autocomplete(self, interaction, current: str) -> List[Choice]:
        # Умный поиск с кэшированием
```

### 3. Команды

Каждая команда вынесена в отдельный класс:

```python
# commands/music/queue_command.py
class QueueCommand:
    async def execute(self, interaction: discord.Interaction) -> None:
        # Логика команды очереди с пагинацией

# commands/music/loop_command.py
class LoopCommand:
    async def execute(self, interaction: discord.Interaction, mode: str) -> None:
        # Логика команды повтора
```

## Особенности архитектуры

### 1. Разделение ответственности

- **Events**: Обработка событий треков
- **Commands**: Логика команд
- **UI**: Пользовательский интерфейс
- **Services**: Работа с внешними сервисами

### 2. Кэширование и производительность

- Автокомплит с TTL кэшем
- Оптимизированные поиски
- Эффективная работа с памятью

### 3. Обработка ошибок

- Централизованная обработка исключений
- Graceful degradation
- Подробное логирование

### 4. Расширяемость

- Модульная архитектура
- Легкое добавление новых команд
- Плагинная система событий

## Использование

### Добавление новой команды

1. Создайте новый файл в `commands/music/`
2. Создайте класс команды
3. Добавьте команду в основной cog

```python
class NewCommand:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def execute(self, interaction: discord.Interaction) -> None:
        # Логика команды
```

### Добавление нового события

1. Создайте новый класс в `core/events/`
2. Реализуйте метод `handle()`
3. Зарегистрируйте в основном cog

```python
class NewEvent:
    async def handle(self, payload) -> None:
        # Обработка события
```

## Преимущества новой архитектуры

1. **Читаемость**: Код разделен на логические модули
2. **Тестируемость**: Каждый компонент можно тестировать отдельно
3. **Масштабируемость**: Легко добавлять новые функции
4. **Производительность**: Оптимизированная работа с ресурсами
5. **Надежность**: Централизованная обработка ошибок

## Миграция с старой архитектуры

1. События треков перенесены в `core/events/`
2. Команды разделены на отдельные классы
3. Автокомплит вынесен в отдельный модуль
4. Улучшена обработка ошибок

Эта архитектура обеспечивает профессиональный уровень разработки и легкость поддержки кода.
