import discord
from discord.ext import commands
import logging
from pathlib import Path
from typing import Dict
import hashlib
import aiohttp


class AutoEmojiManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("AutoEmojiManager")
        self.emoji_folder = Path("assets/Emoji")
        self.supported_formats = {'.png', '.jpg', '.jpeg', '.gif'}
        self.emojis: Dict[str, discord.Emoji] = {}

    def _get_file_hash(self, file_path: Path) -> str:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    async def _get_emoji_hash(self, emoji: discord.Emoji) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(emoji.url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        return hashlib.md5(content).hexdigest()
        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки эмодзи {emoji.name} с URL: {e}")
        return "0"

    async def auto_sync_emojis(self):
        if not self.emoji_folder.exists():
            self.emoji_folder.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"📁 Создана папка: {self.emoji_folder}")
            return

        # 🔍 Читаем локальные файлы
        local_files = {
            file.stem: {"path": file, "hash": self._get_file_hash(file)}
            for file in self.emoji_folder.iterdir()
            if file.is_file() and file.suffix.lower() in self.supported_formats
        }

        # 📥 Получаем все эмодзи приложения
        try:
            app_emojis = await self.bot.fetch_application_emojis()
        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки эмодзи приложения: {e}")
            return

        existing_emojis = {emoji.name: emoji for emoji in app_emojis}

        deleted = updated = added = 0

        # ♻️ Обновление и добавление
        for name, info in local_files.items():
            file_path = info["path"]
            file_hash = info["hash"]
            existing = existing_emojis.get(name)

            changed = True

            if existing:
                existing_hash = await self._get_emoji_hash(existing)
                changed = (existing_hash != file_hash)

            if not existing or changed:
                try:
                    with open(file_path, 'rb') as f:
                        image_data = f.read()

                    if existing:
                        await existing.delete()

                    new_emoji = await self.bot.create_application_emoji(name=name, image=image_data)
                    self.emojis[name] = new_emoji

                    if existing:
                        updated += 1
                        self.logger.info(f"🔁 Обновлён: {name}")
                    else:
                        added += 1
                        self.logger.info(f"➕ Добавлен: {name}")
                except Exception as e:
                    self.logger.error(f"❌ Ошибка с {name}: {e}")
            else:
                self.emojis[name] = existing
                self.logger.info(f"✅ Без изменений: {name}")

        await self._generate_emoji_file()

        self.logger.info(
            f"🚀 Синхронизация завершена: ➕ {added}, 🔁 {updated}, 🗑 {deleted}, ✅ {len(self.emojis)} актуально"
        )

    async def _generate_emoji_file(self):
        emoji_file = Path("emojis.py")
        lines = [
            "# ⚠️ Автогенерированный файл с эмодзи",
            "# Не редактируй вручную!",
            "",
            "class Emojis:",
            "    \"\"\"🚀 Класс со всеми application эмодзи\"\"\"",
            ""
        ]

        try:
            app_emojis = await self.bot.fetch_application_emojis()
            for emoji in app_emojis:
                safe_name = emoji.name.replace('-', '_').replace(' ', '_')
                lines.append(f"    {safe_name.upper()} = \"{emoji}\"")
        except Exception as e:
            self.logger.error(f"❌ Ошибка генерации emoji-файла: {e}")

        lines += [
            "",
            "    @classmethod",
            "    def get_all(cls):",
            "        return {k: v for k, v in cls.__dict__.items() if not k.startswith('_') and k != 'get_all'}",
            ""
        ]

        emoji_file.write_text('\n'.join(lines), encoding='utf-8')
        self.logger.info(f"📄 Файл {emoji_file} обновлён")
