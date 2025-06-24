
# 🎶 HarmonyBot — Музыкальный Discord Бот

> 🧠 Умный. 🎧 Музыкальный. 💎 Стильный.

HarmonyBot — это музыкальный бот нового поколения с поддержкой **SoundCloud**, **Spotify**, умной очередью, кнопками управления и автообновляемым сообщением `Now Playing`.  
Идеально подойдёт для уютных серверов, вечеринок и просто хорошей атмосферы.

🎯 Поддерживает **поиск по названию**, **ссылки на треки и плейлисты**, с интерфейсом, который приятно трогать глазами (смотри скрины 👇).

---

![UI Preview](https://cdn.discordapp.com/attachments/1376500061021802587/1387027769782960179/77615194-8FB0-41AC-86AC-46C4D1B615A0.png?ex=685bd9c6&is=685a8846&hm=cc7c8b43d075993f47fbe2026737974f3a6dbb78c0a306ec58693737d5805552&)

---

## 💡 Возможности

- 🔍 Умный поиск (названия, исполнители, ссылки) — SoundCloud и Spotify  
- 📻 Плейлисты? Конечно!  
- 🎛️ Полный контроллер: пауза, скип, перемешать, громкость и повтор  
- 🖼️ Обновляющееся `Now Playing` сообщение (без магии не обошлось)  
- 💬 Удобные Slash-команды и интерактивные кнопки  
- 🧠 Приятный код и продуманная архитектура  

---

## 🖼️ Интерфейс

> Как это выглядит? Вот так красиво:

![Now Playing](https://cdn.discordapp.com/attachments/1376500061021802587/1387027831728640052/B2927FE3-C676-44C8-B0DE-764D827245A2.png?ex=685bd9d4&is=685a8854&hm=4aacbc8d8756a3a9ed627208b4e1c27c298514ed6561ad67e1933bc3fbc8e73a&)

---

## 🚀 Настройка Lavalink

Для работы музыкального бота требуется запустить собственный Lavalink сервер.

### 1. Создайте папку `Lavalink` в корне проекта.

### 2. В папке `Lavalink` создайте файл `application.yml` со следующим содержимым:

```yaml
server:
  port: 2333
  address: 0.0.0.0
  http2:
    enabled: false

lavalink:
  server:
    password: "123"
    sources:
      youtube: false
      soundcloud: true
      http: true
    bufferDurationMs: 400
    youtubeSearchEnabled: false
    soundcloudSearchEnabled: true
    playerUpdateInterval: 5

plugins:
  lavasrc:
    providers:
      - "scsearch:%QUERY%"
      - "spsearch:%ISRC%"
      - "spotify"
    sources:
      youtube: false
      youtubeMusic: false
      spotify: true
      appleMusic: true
      soundcloud: true
    spotify:
      clientId: "свой"
      clientSecret: "свой"
      countryCode: "свой"
```

### 3. Скачайте `Lavalink.jar` и поместите его в папку `Lavalink`.

### 4. В папку `Lavalink/plugins` добавьте плагины:

- `youtube-plugin-1.13.3.jar`  
- `lavasrc-plugin-4.7.2.jar`  

### 5. Запустите Lavalink сервер из папки `Lavalink` командой:

```bash
java -jar Lavalink.jar
```

---

## ⭐ Поддержка

Если бот вам нравится, не забудьте поставить ⭐ на репозиторий!  
Это мотивирует меня развивать проект и добавлять новые фишки 😊

Спасибо за внимание и приятного прослушивания музыки! 🎶
