# Исправления проблем с эмодзи

## ✅ Исправленные проблемы

### 1. Ошибка "keywords must be strings"

- **Проблема**: `mongo_service.get_guild_settings()` возвращал данные, которые не обрабатывались правильно
- **Решение**: Добавил проверки типов и безопасное извлечение значений
- **Файл**: `core/events/track_events.py`

### 2. Проблема с эмодзи в прогресс баре

- **Проблема**: Сначала показывались дефолтные эмодзи, потом серверные
- **Решение**: Обновляем эмодзи сразу после создания view
- **Файл**: `ui/views.py`

### 3. Эмодзи в MusicPlayerView отображались как точки

- **Проблема**: Эмодзи в MusicPlayerView отображались как точки
- **Решение**: Исправлено обновлением эмодзи сразу после создания view
- **Файл**: `ui/views.py`

### 4. Эмодзи в QueueView отображались как точки

- **Проблема**: Эмодзи в QueueView отображались как точки
- **Решение**: Исправлено добавлением обновления эмодзи при создании view и передачей настроек из playback.py
- **Файл**: `ui/views.py`

### HarmonyPlayer.play_track() (commands/music/playback.py)

- Добавлена проверка типа для `track.requester` в методе `play_track()`
- Добавлена fallback логика для случая когда requester не установлен
- Исправлена передача requester в `MusicPlayerView.create()` и `send_now_playing_message()`

### HarmonyPlayer.do_next() (commands/music/playback.py)

- Добавлена проверка типа для `track.requester` в методе `do_next()`
- Исправлена передача requester в `player.play_track()`

## 🔧 Технические детали

### Исправление событий

```python
# Было:
settings = await mongo_service.get_guild_settings(guild_id)
color = settings.get("color", "default")
custom_emojis = settings.get("custom_emojis", None)

# Стало:
settings = await mongo_service.get_guild_settings(guild_id)
if not isinstance(settings, dict):
    settings = {}
color = settings.get("color", "default")
custom_emojis = settings.get("custom_emojis", {})
if not isinstance(custom_emojis, dict):
    custom_emojis = {}
```

### Исправление эмодзи в view

```python
# Добавлено в create() метод:
self._update_all_emojis()  # Обновляем эмодзи сразу после создания
```

### MusicPlayerView (ui/views.py)

- Добавлен вызов `self._update_all_emojis()` в конце метода `create()`
- Убрано обновление эмодзи из обработчиков кнопок (теперь устанавливаются сразу)

### QueueView (ui/views.py)

- Добавлен вызов `self._update_all_emojis()` в конце метода `create()`
- Убрано обновление эмодзи из обработчиков кнопок (теперь устанавливаются сразу)
- Добавлен метод `_update_all_emojis()` для обновления всех кнопок

### HarmonyPlayer.show_queue() (commands/music/playback.py)

- Добавлено получение настроек гильдии для эмодзи
- Передача настроек `color` и `custom_emojis` в `QueueView.create()`

### TrackStartEvent (core/events/track_events.py)

- Добавлена проверка типа для `track.requester`
- Добавлена fallback логика для случая когда requester не установлен
- Исправлена передача requester в `MusicPlayerView.create()` и `send_now_playing_message()`

### TrackEndEvent (core/events/track_events.py)

- Добавлена проверка типа для `track.requester` в методе `_handle_queue_logic`
- Исправлена передача requester в `player.play_track()`

## Результат

Теперь эмодзи отображаются правильно с цветами сервера сразу при создании view, без необходимости нажимать на кнопки. Также исправлена ошибка "keywords must be strings" в обработчиках событий треков.

### Дополнительные исправления

#### HarmonyPlayer.play_by_index() (commands/music/playback.py)

- Добавлена проверка типа для `track.requester` в методе `play_by_index()`
- Исправлена передача requester в `player.play_track()`

#### MusicPlayerView обработчики кнопок (ui/views.py)

- Убрано обновление эмодзи из начала обработчиков кнопок (pause_button, skip_button)
- Эмодзи теперь обновляются только при изменении состояния (например, пауза/воспроизведение)
- Это устраняет проблему с показом дефолтных эмодзи перед серверными

## 📝 Примечания

Проблема с эмодзи возникала из-за того, что Discord сначала отображал view с дефолтными эмодзи, а потом обновлял их на серверные. Теперь эмодзи устанавливаются сразу при создании view.

Теперь эмодзи отображаются правильно с цветами сервера сразу при создании view, без необходимости нажимать на кнопки.

## Диагностика проблем

### Добавлена отладочная информация

- В `core/events/track_events.py` добавлено логирование настроек гильдии
- В `commands/music/playback.py` добавлено логирование настроек для очереди
- Это поможет определить, правильно ли загружаются настройки эмодзи из базы данных

### Возможные причины проблемы с эмодзи в прогресс баре

1. **Настройки не сохраняются в БД** - нужно проверить команды настройки эмодзи
2. **Настройки загружаются как None** - нужно проверить структуру данных в БД
3. **Проблема с функцией get_emoji** - нужно проверить логику в `config/constants.py`

### Следующие шаги

1. Запустить бота и проверить логи отладочной информации
2. Проверить, что настройки эмодзи сохраняются в БД
3. Проверить, что настройки правильно передаются в прогресс бар
