import asyncio
import hashlib
import io
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Set, Tuple

import aiohttp
from discord.ext import commands
from PIL import Image


class EmojiManager(commands.Cog):
    def __init__(self, bot):
        self.replace_existing = False  # тут TRue если хотите цвета
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.session = None
        self.executor = ThreadPoolExecutor(max_workers=8)

        # Расширенная палитра цветов
        self.color_presets = {
            "red": (255, 85, 85),
            "blue": (85, 170, 255),
            "green": (85, 255, 85),
            "yellow": (255, 255, 85),
            "purple": (170, 85, 255),
            "orange": (255, 170, 85),
            "pink": (255, 85, 170),
            "cyan": (85, 255, 255),
            "white": (255, 255, 255),
            "black": (50, 50, 50),
            "gray": (150, 150, 150),
            "brown": (165, 115, 85),
            "lime": (170, 255, 85),
            "teal": (85, 255, 170),
            "indigo": (85, 85, 255),
            "maroon": (170, 85, 85),
            "navy": (85, 85, 170),
            "olive": (170, 170, 85),
            "aqua": (85, 255, 255),
            "fuchsia": (255, 85, 255),
            "silver": (192, 192, 192),
            "gold": (255, 215, 0),
            "coral": (255, 127, 80),
            "salmon": (250, 128, 114),
            "crimson": (220, 20, 60),
        }

        bot.loop.create_task(self.auto_generate_colored_emojis())

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=50),
            timeout=aiohttp.ClientTimeout(total=30),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        self.executor.shutdown(wait=False)

    def cog_unload(self):
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())
        self.executor.shutdown(wait=False)

    async def auto_generate_colored_emojis(self):
        await self.bot.wait_until_ready()

        async with self:
            # Получаем все эмодзи один раз
            app_emojis = await self.bot.fetch_application_emojis()
            self.existing_emojis_map = {emoji.name: emoji for emoji in app_emojis}
            existing_names = set(self.existing_emojis_map.keys())

            # Фильтруем оригинальные эмодзи (без цветовых суффиксов)
            original_emojis = [
                emoji
                for emoji in app_emojis
                if not any(
                    emoji.name.endswith(f"_{color}") for color in self.color_presets
                )
            ]

            self.logger.info(f"🎨 Найдено {len(original_emojis)} оригинальных эмодзи")

            # Создаем задачи для всех цветов параллельно
            tasks = []
            for color in self.color_presets:
                task = self.create_colored_variants(
                    original_emojis, color, existing_names
                )
                tasks.append(task)

            # Выполняем все задачи параллельно с ограничением
            semaphore = asyncio.Semaphore(5)  # Ограничиваем до 5 одновременных цветов

            async def run_with_semaphore(task):
                async with semaphore:
                    return await task

            results = await asyncio.gather(
                *[run_with_semaphore(task) for task in tasks]
            )

            total_created = sum(results)
            self.logger.info(f"✅ Создано {total_created} новых цветных эмодзи")

            await self.generate_emojis_py()

    async def create_colored_variants(
        self, original_emojis: List, color: str, existing_names: Set[str]
    ) -> int:
        """Создает цветные варианты эмодзи для одного цвета"""
        target_color = self.color_presets[color.lower()]
        created_count = 0

        # Создаем задачи для обработки эмодзи
        tasks = []
        for emoji in original_emojis:
            new_name = self.generate_color_name(emoji.name, color)
            if new_name in existing_names:
                if self.replace_existing:
                    task = self.process_single_emoji(
                        original_emoji=emoji,
                        target_color=target_color,
                        new_name=new_name,
                        old_emoji=self.existing_emojis_map.get(new_name),
                    )
                    tasks.append(task)
            else:
                task = self.process_single_emoji(
                    original_emoji=emoji,
                    target_color=target_color,
                    new_name=new_name,
                    old_emoji=None,
                )
                tasks.append(task)
                task = self.process_single_emoji(emoji, target_color, new_name)
                tasks.append(task)

        if not tasks:
            return 0

        # Выполняем с контролем скорости
        semaphore = asyncio.Semaphore(3)  # Максимум 3 эмодзи одновременно

        async def process_with_semaphore(task):
            async with semaphore:
                result = await task
                if result:
                    await asyncio.sleep(0.1)  # Минимальная задержка для API
                return result

        results = await asyncio.gather(
            *[process_with_semaphore(task) for task in tasks], return_exceptions=True
        )
        created_count = sum(1 for r in results if r is True)

        self.logger.info(f"✅ {color}: создано {created_count} эмодзи")
        return created_count

    async def process_single_emoji(
        self,
        original_emoji,
        target_color: Tuple[int, int, int],
        new_name: str,
        old_emoji=None,
    ) -> bool:
        original_bytes = await self.download_emoji_optimized(original_emoji.url)

        # Перекрашиваем
        loop = asyncio.get_event_loop()
        recolored_bytes = await loop.run_in_executor(
            self.executor, self.recolor_image_optimized, original_bytes, target_color
        )

        # Проверка: изображение идентично старому?
        if old_emoji:
            try:
                old_bytes = await self.download_emoji_optimized(old_emoji.url)
                if self.images_identical(old_bytes, recolored_bytes):
                    return False  # Нет изменений
                await old_emoji.delete()  # Удаляем старый эмодзи
                await asyncio.sleep(0.1)  # Безопасная пауза
            except Exception as e:
                self.logger.warning(f"⚠️ Не удалось удалить {new_name}: {e}")

        # Создаем новый эмодзи
        await self.bot.create_application_emoji(name=new_name, image=recolored_bytes)
        return True

    def generate_color_name(self, base_name: str, color: str) -> str:
        """Генерирует имя для цветного варианта эмодзи"""
        suffix = f"_{color}"
        max_len = 32

        if len(base_name + suffix) > max_len:
            base_name = base_name[: max_len - len(suffix)]

        return base_name + suffix

    async def download_emoji_optimized(self, url: str) -> bytes:
        """Оптимизированная загрузка эмодзи"""
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}")
                return await resp.read()
        except Exception as e:
            self.logger.error(f"❌ Ошибка загрузки {url}: {e}")
            raise

    def recolor_image_optimized(
        self, image_bytes: bytes, target_color: Tuple[int, int, int]
    ) -> bytes:
        """Интенсивная перекраска: тянет цвета к целевому + увеличивает насыщенность"""
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

            try:
                import numpy as np

                img_array = np.array(img, dtype=np.float32)
                alpha = img_array[:, :, 3] > 0

                rgb = img_array[:, :, :3]
                target_rgb = np.array(target_color, dtype=np.float32)

                # Интенсивное смешивание (тянем каждый цвет к целевому)
                blend_ratio = 0.85  # 0.0 — ничего не меняем, 1.0 — полный цвет цели
                recolored_rgb = rgb * (1 - blend_ratio) + target_rgb * blend_ratio

                # Повышаем насыщенность — усиливаем цвета
                recolored_rgb = np.clip(recolored_rgb * 1.3, 0, 255)

                # Применяем только к непрозрачным пикселям
                img_array[:, :, :3] = np.where(alpha[:, :, None], recolored_rgb, rgb)

                img = Image.fromarray(img_array.astype(np.uint8), "RGBA")

            except ImportError:
                # Без NumPy — упрощённое интенсивное перекрашивание
                pixels = img.load()
                for x in range(img.width):
                    for y in range(img.height):
                        r, g, b, a = pixels[x, y]
                        if a == 0:
                            continue

                        blend_ratio = 0.85
                        new_r = int(
                            r * (1 - blend_ratio) + target_color[0] * blend_ratio
                        )
                        new_g = int(
                            g * (1 - blend_ratio) + target_color[1] * blend_ratio
                        )
                        new_b = int(
                            b * (1 - blend_ratio) + target_color[2] * blend_ratio
                        )

                        # Усиление цвета
                        new_r = min(255, int(new_r * 1.3))
                        new_g = min(255, int(new_g * 1.3))
                        new_b = min(255, int(new_b * 1.3))

                        pixels[x, y] = (new_r, new_g, new_b, a)

            output = io.BytesIO()
            img.save(output, format="PNG", optimize=True)
            return output.getvalue()

        except Exception as e:
            self.logger.error(f"❌ Ошибка перекрашивания: {e}")
            raise

    def images_identical(self, img1_bytes: bytes, img2_bytes: bytes) -> bool:
        """Быстрая проверка идентичности изображений"""
        return hashlib.md5(img1_bytes).digest() == hashlib.md5(img2_bytes).digest()

    async def generate_emojis_py(self):
        """Генерирует файл с эмодзи"""
        try:
            emojis = await self.bot.fetch_application_emojis()

            lines = [
                "# ⚠️ Автогенерированный файл с эмодзи",
                "# Не редактируй вручную!",
                "",
                "class Emojis:",
                '    """🚀 Класс со всеми application эмодзи"""',
                "",
            ]

            # Сортируем эмодзи по имени для стабильности
            sorted_emojis = sorted(emojis, key=lambda e: e.name)

            for emoji in sorted_emojis:
                safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", emoji.name).upper()
                lines.append(f'    {safe_name} = "{emoji}"')

            lines.extend(
                [
                    "",
                    "    @classmethod",
                    "    def get_all(cls):",
                    "        return {k: v for k, v in cls.__dict__.items() if not k.startswith('_') and k != 'get_all'}",
                    "",
                    "    @classmethod",
                    "    def get_by_color(cls, color: str):",
                    "        return {k: v for k, v in cls.get_all().items() if k.endswith(f'_{color.upper()}')}",
                ]
            )

            Path("emojis.py").write_text("\n".join(lines), encoding="utf-8")
            self.logger.info("✅ Файл emojis.py обновлен")

        except Exception as e:
            self.logger.error(f"❌ Ошибка генерации emojis.py: {e}")


async def setup(bot):
    await bot.add_cog(EmojiManager(bot))
