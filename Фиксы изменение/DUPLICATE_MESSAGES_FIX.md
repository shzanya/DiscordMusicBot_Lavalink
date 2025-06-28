# Исправление дублирования "Now Playing" сообщений

## Проблема

В логах наблюдалось дублирование сообщений "now playing":

```
18:42:32,056 | INFO | commands.music.playback | ▶️ Sent now playing message for: Тп на аме with MussicPlayerView
18:42:32,135 | INFO | core.events.track_events | ✅ Sent now playing message for: Тп на аме
```

Сообщение отправлялось дважды:

1. В `playback.py` в методе `play_track`
2. В `track_events.py` в обработчике события начала трека

## Причина

Дублирование происходило из-за того, что:

- При вызове `play_track()` в `playback.py` отправлялось сообщение "now playing"
- Затем срабатывало событие `TrackStartEvent` в `track_events.py`, которое также отправляло сообщение

## Решение

Убрал отправку сообщения из `track_events.py`, оставив только в `playback.py`:

### Изменения в `core/events/track_events.py`:

1. **Удален метод `_send_now_playing_message()`** - больше не отправляет сообщения
2. **Упрощен обработчик `handle()`** - теперь только:
   - Применяет сохраненные эффекты
   - Сбрасывает тайминг
   - Логирует начало трека

### Код после исправления:

```python
async def handle(self, payload: wavelink.TrackStartEventPayload) -> None:
    """Handle track start event."""
    player: HarmonyPlayer = payload.player

    if not player or getattr(player, "_is_destroyed", False):
        logger.warning("❌ Invalid or destroyed player in track start event")
        return

    if getattr(player, "_handling_track_start", False):
        logger.debug("Track start already handled")
        return

    player._handling_track_start = True

    try:
        track = payload.track
        if not track:
            logger.warning("No track in payload")
            return

        logger.info(f"🎵 Track started: {track.title}")

        # Apply saved effects
        await player.apply_saved_effects()

        # Reset timing
        player._last_position = 0.0
        player.start_time_real = int(time.time())
        player.speed_override = getattr(player, 'speed_override', 1.0)

        # Note: Now playing message is sent in playback.py play_track method
        # to avoid duplication

    except Exception as e:
        logger.error(f"❌ Track start handler failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        player._handling_track_start = False
```

## Результат

- ✅ Устранено дублирование сообщений "now playing"
- ✅ Сообщения отправляются только один раз в `playback.py`
- ✅ Сохранена вся функциональность (эффекты, тайминг)
- ✅ Логи стали чище

## Тестирование

Создан тест `test_duplicate_messages.py` для проверки:

- Track start event больше не отправляет сообщения
- Playback play_track метод отправляет сообщения
- Дублирование устранено

```bash
python test_duplicate_messages.py
```

## Логи после исправления

Теперь в логах будет только одно сообщение:

```
18:42:32,056 | INFO | commands.music.playback | ▶️ Sent now playing message for: Тп на аме with MussicPlayerView
```

Вместо двух дублирующих сообщений.
