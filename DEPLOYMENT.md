# 🚀 Руководство по развертыванию Harmony Music Bot

## 📋 Предварительные требования

### 🔧 **Системные требования**

- **Python 3.8+** (рекомендуется 3.11+)
- **Java 17+** (для Lavalink)
- **MongoDB 4.4+** или MongoDB Atlas
- **Минимум 2GB RAM**
- **Стабильное интернет-соединение**

### 🎵 **Аудио требования**

- **Lavalink сервер** (локальный или удаленный)
- **Поддержка Opus кодек**
- **Достаточная пропускная способность** для аудио

## 🏗️ Пошаговое развертывание

### 1. 📥 **Подготовка проекта**

```bash
# Клонируйте репозиторий
git clone https://github.com/your-username/harmony-music-bot.git
cd harmony-music-bot

# Создайте виртуальное окружение
python -m venv venv

# Активируйте виртуальное окружение
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Установите зависимости
pip install -r requirements.txt
```

### 2. 🎵 **Настройка Lavalink**

#### **Вариант A: Локальный Lavalink**

1. **Создайте папку Lavalink**

```bash
mkdir Lavink
cd Lavink
```

2. **Скачайте Lavalink.jar**

```bash
# Скачайте последнюю версию с GitHub
wget https://github.com/lavalink-devs/Lavalink/releases/latest/download/Lavalink.jar
```

3. **Создайте application.yml**

```yaml
server:
  port: 2333
  address: 0.0.0.0
  http2:
    enabled: false

lavalink:
  server:
    password: 'youshallnotpass'
    sources:
      youtube: true
      soundcloud: true
      http: true
    bufferDurationMs: 400
    youtubeSearchEnabled: true
    soundcloudSearchEnabled: true
    playerUpdateInterval: 5

plugins:
  lavasrc:
    providers:
      - 'ytsearch:%QUERY%'
      - 'scsearch:%QUERY%'
      - 'spsearch:%ISRC%'
      - 'spotify'
    sources:
      youtube: true
      youtubeMusic: true
      spotify: true
      appleMusic: true
      soundcloud: true
    spotify:
      clientId: 'your-spotify-client-id'
      clientSecret: 'your-spotify-client-secret'
      countryCode: 'US'
```

4. **Запустите Lavalink**

```bash
java -jar Lavalink.jar
```

#### **Вариант B: Удаленный Lavalink**

Используйте готовый Lavalink сервер:

- **Lavalink.gg** (бесплатный)
- **Lavalink.dev** (платный)
- **Собственный VPS** с Lavalink

### 3. 🗄️ **Настройка MongoDB**

#### **Вариант A: MongoDB Atlas (рекомендуется)**

1. **Создайте аккаунт** на [MongoDB Atlas](https://mongodb.com/atlas)
2. **Создайте кластер** (бесплатный tier подходит)
3. **Настройте сетевой доступ** (0.0.0.0/0 для всех IP)
4. **Создайте пользователя** базы данных
5. **Получите connection string**

#### **Вариант B: Локальная MongoDB**

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install mongodb

# macOS
brew install mongodb-community

# Windows
# Скачайте с официального сайта MongoDB
```

### 4. 🤖 **Создание Discord бота**

1. **Перейдите** на [Discord Developer Portal](https://discord.com/developers/applications)
2. **Создайте новое приложение**
3. **Перейдите в раздел "Bot"**
4. **Создайте бота** и скопируйте токен
5. **Включите необходимые интенты:**
   - Message Content Intent
   - Server Members Intent
   - Presence Intent
6. **Настройте разрешения:**
   - Send Messages
   - Use Slash Commands
   - Connect
   - Speak
   - Use Voice Activity
   - Embed Links
   - Attach Files
   - Read Message History

### 5. ⚙️ **Конфигурация бота**

1. **Создайте файл .env**

```env
# Discord Bot
DISCORD_TOKEN=your-bot-token-here
OWNER_ID=your-discord-id

# Database
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/musicbot

# Lavalink
LAVALINK_HOST=localhost
LAVALINK_PORT=2333
LAVALINK_PASSWORD=youshallnotpass

# Optional Services
SPOTIFY_CLIENT_ID=your-spotify-client-id
SPOTIFY_CLIENT_SECRET=your-spotify-client-secret
GENIUS_ACCESS_TOKEN=your-genius-token
```

2. **Или скопируйте config.example.py**

```bash
cp config.example.py config.py
# Отредактируйте config.py с вашими настройками
```

### 6. 🚀 **Запуск бота**

```bash
# Активируйте виртуальное окружение
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Запустите бота
python main.py
```

## 🌐 **Развертывание на хостинге**

### **Heroku**

1. **Создайте Procfile**

```
worker: python main.py
```

2. **Создайте runtime.txt**

```
python-3.11.0
```

3. **Добавьте переменные окружения** в Heroku Dashboard

4. **Деплойте**

```bash
heroku create your-bot-name
git push heroku main
```

### **Railway**

1. **Подключите GitHub репозиторий**
2. **Настройте переменные окружения**
3. **Деплойте автоматически**

### **DigitalOcean/AWS/VPS**

1. **Создайте сервер** с Ubuntu 20.04+
2. **Установите зависимости**

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git screen
```

3. **Клонируйте и настройте проект**

```bash
git clone https://github.com/your-username/harmony-music-bot.git
cd harmony-music-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. **Запустите в screen**

```bash
screen -S musicbot
python main.py
# Ctrl+A, D для отключения
```

## 🔧 **Настройка автозапуска**

### **Systemd (Linux)**

1. **Создайте сервис файл**

```bash
sudo nano /etc/systemd/system/harmony-bot.service
```

2. **Добавьте конфигурацию**

```ini
[Unit]
Description=Harmony Music Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/harmony-music-bot
Environment=PATH=/path/to/harmony-music-bot/venv/bin
ExecStart=/path/to/harmony-music-bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. **Включите автозапуск**

```bash
sudo systemctl enable harmony-bot
sudo systemctl start harmony-bot
```

### **PM2 (Node.js)**

```bash
npm install -g pm2
pm2 start main.py --name "harmony-bot" --interpreter python
pm2 startup
pm2 save
```

## 🔍 **Проверка работоспособности**

### **Тесты подключения**

1. **Проверьте Discord бота**

```bash
# Бот должен появиться онлайн в Discord
```

2. **Проверьте Lavalink**

```bash
# В логах должно быть: "Connected to Lavalink"
```

3. **Проверьте MongoDB**

```bash
# В логах должно быть: "MongoDB connection established"
```

### **Тестовые команды**

```
/play test
/queue
/volume 50
/effects
```

## 🛠️ **Устранение неполадок**

### **Частые проблемы**

1. **Бот не подключается к голосовому каналу**

   - Проверьте разрешения бота
   - Убедитесь, что Lavalink запущен

2. **Ошибки MongoDB**

   - Проверьте connection string
   - Убедитесь, что IP добавлен в whitelist

3. **Аудио не воспроизводится**

   - Проверьте Lavalink логи
   - Убедитесь, что Java 17+ установлен

4. **Команды не работают**
   - Проверьте токен бота
   - Убедитесь, что интенты включены

### **Логи и отладка**

```bash
# Включите DEBUG режим в config.py
LOG_LEVEL = "DEBUG"

# Проверьте логи
tail -f logs/bot.log
```

## 🔒 **Безопасность**

### **Рекомендации**

1. **Никогда не публикуйте токены**
2. **Используйте переменные окружения**
3. **Ограничьте доступ к MongoDB**
4. **Регулярно обновляйте зависимости**
5. **Используйте HTTPS для API**

### **Firewall настройки**

```bash
# Откройте только необходимые порты
sudo ufw allow 22    # SSH
sudo ufw allow 2333  # Lavalink (если локальный)
sudo ufw enable
```

## 📊 **Мониторинг**

### **Метрики для отслеживания**

- **Время работы бота**
- **Количество активных серверов**
- **Использование памяти и CPU**
- **Количество воспроизведенных треков**
- **Ошибки и исключения**

### **Инструменты мониторинга**

- **Uptime Robot** - проверка доступности
- **Grafana** - метрики и графики
- **Sentry** - отслеживание ошибок
- **Discord Webhooks** - уведомления

## 🎯 **Оптимизация производительности**

### **Настройки для высоких нагрузок**

```python
# config.py
MAX_LAVALINK_CONNECTIONS = 10
DB_POOL_SIZE = 20
AUDIO_BUFFER_SIZE = 200
PROGRESS_UPDATE_INTERVAL = 5
```

### **Рекомендации по серверу**

- **CPU**: 2+ ядра
- **RAM**: 4GB+
- **Диск**: SSD
- **Сеть**: 100Mbps+

## 🎉 **Готово!**

Ваш Harmony Music Bot успешно развернут и готов к использованию!

**Следующие шаги:**

1. Пригласите бота на сервер
2. Настройте роль DJ
3. Выберите цветовую схему
4. Наслаждайтесь музыкой! 🎵
