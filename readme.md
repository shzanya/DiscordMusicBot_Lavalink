# 🎵 Harmony Music Bot

**Современный Discord музыкальный бот с продвинутыми возможностями, красивым интерфейсом и уникальными функциями**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Discord.py](https://img.shields.io/badge/Discord.py-2.0+-green.svg)](https://discordpy.readthedocs.io)
[![Wavelink](https://img.shields.io/badge/Wavelink-3.0+-purple.svg)](https://wavelink.dev)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-orange.svg)](https://mongodb.com)

## 🌟 Особенности

### 🎛️ **Продвинутое управление музыкой**

- **Интуитивный интерфейс** с кастомными эмодзи и цветами
- **Умная очередь** с историей воспроизведения и автопродолжением
- **Режимы повтора** (трек/очередь/выключено)
- **Перемешивание** и навигация по плейлисту
- **Сохранение очереди** между сессиями

### 🔊 **Аудио эффекты и настройки**

- **8 профессиональных эффектов**: Басбуст, Найткор, Вейпорвейв, Требл буст, Караоке, Тремоло, Вибрато, Дисторшн
- **Индивидуальная громкость** для каждого сервера (0-200%)
- **Быстрые кнопки** +/-10% громкости
- **Автосохранение** настроек в базе данных

### 🎨 **Кастомизация и UI**

- **25+ цветовых схем** для интерфейса
- **Кастомные эмодзи** для каждой кнопки
- **Адаптивные эмбеды** с прогресс-барами
- **Интерактивные кнопки** и селекты
- **Отзывчивый дизайн** для всех устройств

### 🔧 **Административные функции**

- **Роль DJ** для управления музыкой
- **Система разрешений** и модерации
- **Настройки сервера** с изоляцией между гильдиями
- **Логирование** действий и ошибок
- **Автоочистка** неактивных сессий

## 🏗️ Архитектура

### 📁 **Структура проекта**

```
musicBot/
├── 🎵 commands/          # Команды бота
│   ├── admin/           # Админ команды
│   ├── music/           # Музыкальные команды
│   └── playlist/        # Управление плейлистами
├── 🎛️ core/             # Основная логика
│   ├── bot.py           # Главный класс бота
│   ├── player.py        # Кастомный плеер
│   └── events/          # Обработчики событий
├── 🎨 ui/               # Пользовательский интерфейс
│   ├── views.py         # Интерактивные кнопки
│   ├── embeds.py        # Красивые эмбеды
│   └── track_select.py  # Выбор треков
├── 🔧 services/         # Внешние сервисы
│   ├── mongo_service.py # База данных
│   ├── spotify.py       # Spotify интеграция
│   └── youtube.py       # YouTube поиск
├── 🛠️ utils/            # Утилиты и хелперы
└── 📁 assets/           # Эмодзи и ресурсы
```

### 🔄 **Поток данных**

```
Discord Event → Bot Handler → Command → Player → Audio Engine → Discord Response
     ↓              ↓           ↓         ↓          ↓              ↓
   Interaction → Validation → Logic → Wavelink → Lavalink → UI Update
```

### 🗄️ **База данных (MongoDB)**

```javascript
// Коллекция: guild_settings
{
  "guild_id": "123456789",
  "color": "blue",
  "volume": 85,
  "custom_emojis": {
    "NK_VOLUME": "🔊",
    "NK_HEART": "❤️"
  },
  "dj_role": "987654321",
  "prefix": "!"
}

// Коллекция: saved_queues
{
  "guild_id": "123456789",
  "tracks": [...],
  "current_index": 2,
  "timestamp": "2024-01-01T12:00:00Z"
}
```

## 🚀 Установка и настройка

### 📋 **Требования**

- Python 3.8+
- MongoDB Atlas или локальная MongoDB
- Lavalink сервер
- Discord Bot Token

### ⚙️ **Быстрая установка**

1. **Клонируйте репозиторий**

```bash
git clone https://github.com/your-username/harmony-music-bot.git
cd harmony-music-bot
```

2. **Установите зависимости**

```bash
pip install -r requirements.txt
```

3. **Запустите бота**

```bash
python main.py
```



## 🎮 Использование

### 🎵 **Основные команды**

```
/play <запрос>     -Воспроизвести музыку
/queue             - Показать 
```

### 🎛️ **Эффекты**

```
/effects           - эффекты
```

### ⚙️ **Админ команды**

```
/settings          - Настройки сервера
```

## 🎨 Скриншоты
![MAIN](screenshots/main-interface.png)
![alt text](screenshots/Pozition_volume.png)
![alt text](screenshots/queue.png)
![alt text](screenshots/effects-panel2.png)
![alt text](screenshots/effects-panel.png)
![alt text](screenshots/settings.png)
## 🔧 Технические детали

### 🎵 **Аудио движок**

- **Wavelink 3.0** - современная библиотека для Lavalink
- **Lavalink** - высокопроизводительный аудио сервер
- **Поддержка форматов**: MP3, FLAC, OGG, M4A, WAV
- **Качество**: До 320kbps

### 🗄️ **База данных**

- **MongoDB** - NoSQL база данных
- **Изоляция данных** между серверами
- **Автосохранение** настроек и очередей
- **Индексация** для быстрого поиска

### 🎨 **UI/UX**

- **Discord.py Views** - нативные интерактивные элементы
- **Кастомные эмбеды** с прогресс-барами
- **Адаптивный дизайн** для всех устройств
- **25+ цветовых схем** для персонализации

### 🔒 **Безопасность**

- **Валидация входных данных**
- **Система разрешений** Discord
- **Защита от спама** и злоупотреблений
- **Безопасное хранение** токенов

## 🚀 Производительность

### ⚡ **Оптимизации**

- **Асинхронная обработка** всех операций
- **Кэширование** часто используемых данных
- **Ленивая загрузка** ресурсов
- **Эффективные запросы** к базе данных

### 📊 **Метрики**

- **Время отклика**: <100ms для команд
- **Память**: ~50MB на сервер
- **CPU**: Минимальная нагрузка
- **Сеть**: Оптимизированные запросы

## 🤝 Вклад в проект

### 📝 **Как помочь**

1. **Fork** репозиторий
2. **Создайте ветку** для новой функции
3. **Внесите изменения** с тестами
4. **Создайте Pull Request**

### 🐛 **Сообщение об ошибках**

- Используйте **Issues** на GitHub
- Опишите **шаги воспроизведения**
- Приложите **логи ошибок**
- Укажите **версию** бота и Discord.py

## 📄 Лицензия

Этот проект лицензирован под **MIT License** - см. файл [LICENSE](LICENSE) для деталей.

## 🙏 Благодарности

- **Discord.py** команде за отличную библиотеку
- **Wavelink** разработчикам за аудио движок
- **Lavalink** команде за сервер
- **Сообществу** за идеи и поддержку

## 📞 Поддержка

- **Discord**: [Сервер поддержки](https://discord.gg/your-server)
- **GitHub**: [Issues](https://github.com/your-username/harmony-music-bot/issues)
- **Email**: support@harmony-bot.com

---

**⭐ Если вам понравился бот, поставьте звезду на GitHub!**

**🎵 Создано с ❤️ для Discord сообщества**
