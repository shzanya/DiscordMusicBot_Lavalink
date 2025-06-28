# 🏗️ Архитектура Harmony Music Bot

## 📋 Обзор системы

Harmony Music Bot - это модульная, масштабируемая система для воспроизведения музыки в Discord. Архитектура построена на принципах **разделения ответственности**, **модульности** и **расширяемости**.

## 🎯 Основные принципы

### 🔧 **Модульность**

- Каждый компонент имеет четко определенную ответственность
- Минимальная связанность между модулями
- Возможность замены компонентов без влияния на другие

### 🚀 **Масштабируемость**

- Поддержка множественных серверов
- Изоляция данных между гильдиями
- Эффективное использование ресурсов

### 🛡️ **Надежность**

- Обработка ошибок на всех уровнях
- Автоматическое восстановление соединений
- Валидация входных данных

### 🎨 **Расширяемость**

- Плагинная архитектура для эффектов
- Конфигурируемый UI
- Поддержка новых источников музыки

## 🏛️ Архитектурные слои

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                       │
│  Discord UI, Embeds, Views, Interactive Components         │
├─────────────────────────────────────────────────────────────┤
│                    APPLICATION LAYER                        │
│  Commands, Event Handlers, Business Logic                  │
├─────────────────────────────────────────────────────────────┤
│                     DOMAIN LAYER                            │
│  Player, Queue, Effects, Audio Processing                   │
├─────────────────────────────────────────────────────────────┤
│                   INFRASTRUCTURE LAYER                      │
│  Database, External APIs, Audio Engine                      │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Структура проекта

### 🎵 **commands/** - Команды и обработчики

```
commands/
├── admin/              # Административные команды
│   ├── permissions.py  # Система разрешений
│   └── settings.py     # Настройки сервера
├── music/              # Музыкальные команды
│   ├── playback.py     # Основные команды воспроизведения
│   ├── effects.py      # Аудио эффекты
│   ├── queue.py        # Управление очередью
│   └── favorites.py    # Избранные треки
└── playlist/           # Управление плейлистами
    ├── management.py   # Создание/редактирование
    └── sharing.py      # Поделиться плейлистами
```

### 🎛️ **core/** - Основная логика

```
core/
├── bot.py              # Главный класс бота
├── player.py           # Кастомный аудио плеер
├── events/             # Обработчики событий
│   └── track_events.py # События треков
└── assets.py           # Управление ресурсами
```

### 🎨 **ui/** - Пользовательский интерфейс

```
ui/
├── views.py            # Интерактивные кнопки
├── embeds.py           # Красивые эмбеды
├── track_select.py     # Выбор треков
├── base_view.py        # Базовые классы UI
├── modals.py           # Модальные окна
└── progress_updater.py # Обновление прогресса
```

### 🔧 **services/** - Внешние сервисы

```
services/
├── mongo_service.py    # База данных MongoDB
├── spotify.py          # Spotify API интеграция
├── youtube.py          # YouTube поиск
├── lyrics.py           # Сервис текстов песен
├── queue_service.py    # Управление очередями
└── recommendations.py  # Рекомендации
```

### 🛠️ **utils/** - Утилиты и хелперы

```
utils/
├── formatters.py       # Форматирование данных
├── validators.py       # Валидация входных данных
├── helpers.py          # Общие хелперы
├── decorators.py       # Декораторы
└── autocomplete.py     # Автодополнение команд
```

### 📁 **assets/** - Ресурсы

```
assets/
└── Emoji/              # Кастомные эмодзи
    ├── NK_VOLUME.png
    ├── NK_PLAY.png
    └── ...
```

## 🔄 Потоки данных

### 🎵 **Воспроизведение музыки**

```
User Command → Discord API → Bot Handler → Player → Wavelink → Lavalink → Audio Output
     ↓              ↓            ↓          ↓         ↓          ↓           ↓
   /play         Interaction  Validation  Queue    Filters   Streaming   Discord
```

### 🗄️ **Сохранение данных**

```
Player State → Database Service → MongoDB → Persistence
     ↓              ↓              ↓           ↓
   Volume        Validation     Storage    Retrieval
   Queue         Serialization  Indexing   Caching
   Settings      Encryption     Backup     Replication
```

### 🎨 **Обновление UI**

```
Audio Progress → Progress Updater → Embed Generator → Discord API → UI Update
      ↓              ↓                ↓              ↓           ↓
   Position       Timer Loop      Format Data    Edit Message  Visual Update
   Duration       Force Update    Add Fields     Rate Limit    User Feedback
   Metadata       Error Handle    Color Scheme   Permissions   Responsive
```

## 🗄️ Модели данных

### 📊 **Guild Settings**

```javascript
{
  "_id": ObjectId,
  "guild_id": "123456789",
  "color": "blue",
  "volume": 85,
  "custom_emojis": {
    "NK_VOLUME": "🔊",
    "NK_HEART": "❤️"
  },
  "dj_role": "987654321",
  "prefix": "!",
  "autoplay": true,
  "default_volume": 100,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 🎵 **Saved Queue**

```javascript
{
  "_id": ObjectId,
  "guild_id": "123456789",
  "tracks": [
    {
      "title": "Song Title",
      "author": "Artist",
      "uri": "https://...",
      "length": 180000,
      "requester": "456789123"
    }
  ],
  "current_index": 2,
  "loop_mode": "NONE",
  "volume": 85,
  "effects": {
    "bass_boost": false,
    "nightcore": true
  },
  "created_at": ISODate,
  "last_played": ISODate
}
```

### 👤 **User Favorites**

```javascript
{
  "_id": ObjectId,
  "user_id": "456789123",
  "guild_id": "123456789",
  "favorites": [
    {
      "title": "Favorite Song",
      "author": "Artist",
      "uri": "https://...",
      "added_at": ISODate
    }
  ],
  "playlists": [
    {
      "name": "My Playlist",
      "tracks": [...],
      "created_at": ISODate
    }
  ]
}
```

## 🔧 Ключевые компоненты

### 🎛️ **HarmonyPlayer**

Основной класс для управления аудио воспроизведением.

**Ответственности:**

- Управление состоянием воспроизведения
- Обработка аудио эффектов
- Синхронизация с базой данных
- Управление очередью треков

**Ключевые методы:**

```python
class HarmonyPlayer(wavelink.Player):
    async def play_track(self, track, **kwargs)
    async def set_effects(self, **kwargs)
    async def save_queue(self) -> bool
    async def load_saved_queue(self) -> bool
    @property
    def volume(self) -> int
```

### 🎨 **MusicPlayerView**

Интерактивный интерфейс для управления музыкой.

**Ответственности:**

- Отображение кнопок управления
- Обработка пользовательских взаимодействий
- Обновление UI в реальном времени
- Кастомизация внешнего вида

**Ключевые компоненты:**

```python
class MusicPlayerView(BaseEmojiView):
    async def shuffle_button_callback(self, interaction)
    async def volume_button_callback(self, interaction)
    async def effects_button_callback(self, interaction)
    async def update_track_select(self)
```

### 🗄️ **MongoService**

Слой доступа к данным.

**Ответственности:**

- CRUD операции с базой данных
- Кэширование часто используемых данных
- Валидация данных
- Обработка ошибок подключения

**Ключевые методы:**

```python
class MongoService:
    async def get_guild_settings(guild_id: int) -> Dict
    async def set_guild_settings(guild_id: int, settings: Dict) -> bool
    async def get_guild_volume(guild_id: int) -> int
    async def save_queue(guild_id: int, queue_data: Dict) -> bool
```

### 🎛️ **AudioEffectsManager**

Управление аудио эффектами.

**Ответственности:**

- Применение аудио фильтров
- Проверка совместимости эффектов
- Конфигурация эффектов
- Управление состоянием эффектов

**Поддерживаемые эффекты:**

```python
class EffectType(Enum):
    BASS_BOOST = "bass_boost"
    NIGHTCORE = "nightcore"
    VAPORWAVE = "vaporwave"
    TREBLE_BOOST = "treble_boost"
    KARAOKE = "karaoke"
    TREMOLO = "tremolo"
    VIBRATO = "vibrato"
    DISTORTION = "distortion"
```

## 🔄 Паттерны проектирования

### 🏭 **Factory Pattern**

Используется для создания плееров и UI компонентов.

```python
@classmethod
async def create(cls, player, message=None, requester=None, **kwargs):
    # Создание экземпляра с настройками
    instance = cls(player=player, message=message, requester=requester, **kwargs)
    await instance._initialize_emojis()
    return instance
```

### 🎯 **Observer Pattern**

Для обновления UI при изменении состояния плеера.

```python
class NowPlayingUpdater:
    def register_message(self, guild_id, message, player, track, requester):
        # Регистрация сообщения для автообновления
        self.active_messages[guild_id] = {...}
```

### 🛡️ **Decorator Pattern**

Для валидации и проверки разрешений.

```python
def check_player_ownership(func):
    async def wrapper(interaction, player, *args, **kwargs):
        # Проверка владельца плеера
        if not await validate_ownership(interaction, player):
            return
        return await func(interaction, player, *args, **kwargs)
    return wrapper
```

### 🗄️ **Repository Pattern**

Для абстракции доступа к данным.

```python
class MongoService:
    @staticmethod
    async def get_guild_settings(guild_id: int) -> Dict:
        # Абстракция доступа к MongoDB
        collection = get_collection("guild_settings")
        return await collection.find_one({"guild_id": str(guild_id)})
```

## 🔒 Безопасность

### 🛡️ **Валидация данных**

- Проверка входных параметров
- Санитизация пользовательского ввода
- Валидация URL и ссылок

### 🔐 **Разрешения**

- Система ролей Discord
- Проверка владельца плеера
- Ограничение доступа к командам

### 🗄️ **Защита данных**

- Шифрование чувствительных данных
- Безопасное хранение токенов
- Изоляция данных между серверами

## 📊 Производительность

### ⚡ **Оптимизации**

- Асинхронная обработка всех операций
- Кэширование часто используемых данных
- Ленивая загрузка ресурсов
- Эффективные запросы к базе данных

### 📈 **Метрики**

- Время отклика команд: <100ms
- Использование памяти: ~50MB на сервер
- CPU нагрузка: минимальная
- Сетевая эффективность: оптимизированные запросы

### 🔄 **Масштабирование**

- Поддержка множественных Lavalink серверов
- Горизонтальное масштабирование
- Балансировка нагрузки
- Репликация базы данных

## 🧪 Тестирование

### 📋 **Стратегия тестирования**

- **Unit тесты** для отдельных компонентов
- **Integration тесты** для взаимодействия модулей
- **End-to-end тесты** для полных сценариев
- **Performance тесты** для нагрузочного тестирования

### 🛠️ **Инструменты тестирования**

- **pytest** - основной фреймворк тестирования
- **pytest-asyncio** - для асинхронных тестов
- **pytest-mock** - для мокирования
- **pytest-cov** - для покрытия кода

## 🔮 Будущие улучшения

### 🚀 **Планируемые функции**

- **Микросервисная архитектура**
- **GraphQL API**
- **WebSocket для real-time обновлений**
- **Машинное обучение для рекомендаций**
- **Поддержка видео потоков**

### 🔧 **Технические улучшения**

- **Docker контейнеризация**
- **Kubernetes оркестрация**
- **Redis для кэширования**
- **Elasticsearch для поиска**
- **Prometheus метрики**

---

**🎵 Архитектура Harmony Music Bot спроектирована для максимальной производительности, надежности и расширяемости!**
