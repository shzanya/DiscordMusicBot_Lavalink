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
            "crimson": (220, 20, 60)
        }
        
        bot.loop.create_task(self.auto_generate_colored_emojis())

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=50),
            timeout=aiohttp.ClientTimeout(total=30)
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
            existing_names = {emoji.name for emoji in app_emojis}
            
            # Фильтруем оригинальные эмодзи (без цветовых суффиксов)
            original_emojis = [
                emoji for emoji in app_emojis 
                if not any(emoji.name.endswith(f"_{color}") for color in self.color_presets)
            ]
            
            self.logger.info(f"🎨 Найдено {len(original_emojis)} оригинальных эмодзи")
            
            # Создаем задачи для всех цветов параллельно
            tasks = []
            for color in self.color_presets:
                task = self.create_colored_variants(original_emojis, color, existing_names)
                tasks.append(task)
            
            # Выполняем все задачи параллельно с ограничением
            semaphore = asyncio.Semaphore(5)  # Ограничиваем до 5 одновременных цветов
            
            async def run_with_semaphore(task):
                async with semaphore:
                    return await task
            
            results = await asyncio.gather(*[run_with_semaphore(task) for task in tasks])
            
            total_created = sum(results)
            self.logger.info(f"✅ Создано {total_created} новых цветных эмодзи")
            
            await self.generate_emojis_py()

    async def create_colored_variants(self, original_emojis: List, color: str, existing_names: Set[str]) -> int:
        """Создает цветные варианты эмодзи для одного цвета"""
        target_color = self.color_presets[color.lower()]
        created_count = 0
        
        # Создаем задачи для обработки эмодзи
        tasks = []
        for emoji in original_emojis:
            new_name = self.generate_color_name(emoji.name, color)
            if new_name not in existing_names:
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
        
        results = await asyncio.gather(*[process_with_semaphore(task) for task in tasks], return_exceptions=True)
        created_count = sum(1 for r in results if r is True)
        
        self.logger.info(f"✅ {color}: создано {created_count} эмодзи")
        return created_count

    async def process_single_emoji(self, emoji, target_color: Tuple[int, int, int], new_name: str) -> bool:
        """Обрабатывает одно эмодзи"""
        try:
            # Скачиваем изображение
            original_bytes = await self.download_emoji_optimized(emoji.url)
            
            # Перекрашиваем в отдельном потоке
            loop = asyncio.get_event_loop()
            recolored_bytes = await loop.run_in_executor(
                self.executor, 
                self.recolor_image_optimized, 
                original_bytes, 
                target_color
            )
            
            # Проверяем, изменилось ли изображение
            if self.images_identical(original_bytes, recolored_bytes):
                return False
            
            # Создаем новое эмодзи
            await self.bot.create_application_emoji(name=new_name, image=recolored_bytes)
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка при обработке {emoji.name} -> {new_name}: {e}")
            return False

    def generate_color_name(self, base_name: str, color: str) -> str:
        """Генерирует имя для цветного варианта эмодзи"""
        suffix = f"_{color}"
        max_len = 32
        
        if len(base_name + suffix) > max_len:
            base_name = base_name[:max_len - len(suffix)]
        
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

    def recolor_image_optimized(self, image_bytes: bytes, target_color: Tuple[int, int, int]) -> bytes:
        """Оптимизированное перекрашивание с сохранением яркости (как Hue в Photoshop)"""
        try:
            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            
            # Используем numpy для ускорения если доступен
            try:
                import numpy as np
                
                img_array = np.array(img, dtype=np.float32)
                alpha_mask = img_array[:, :, 3] > 0
                
                if np.any(alpha_mask):
                    # Конвертируем RGB в HSV для изменения только оттенка
                    rgb = img_array[:, :, :3] / 255.0
                    
                    # Рассчитываем HSV
                    max_val = np.max(rgb, axis=2)
                    min_val = np.min(rgb, axis=2)
                    diff = max_val - min_val
                    
                    # Value (яркость) - остается неизменной
                    v = max_val
                    
                    # Saturation - остается неизменной
                    s = np.where(max_val == 0, 0, diff / max_val)
                    
                    # Новый Hue из целевого цвета
                    target_rgb = np.array(target_color) / 255.0
                    target_max = np.max(target_rgb)
                    target_min = np.min(target_rgb)
                    target_diff = target_max - target_min
                    
                    if target_diff == 0:
                        new_h = 0
                    else:
                        if target_max == target_rgb[0]:  # Red
                            new_h = ((target_rgb[1] - target_rgb[2]) / target_diff) % 6
                        elif target_max == target_rgb[1]:  # Green
                            new_h = (target_rgb[2] - target_rgb[0]) / target_diff + 2
                        else:  # Blue
                            new_h = (target_rgb[0] - target_rgb[1]) / target_diff + 4
                        new_h = new_h / 6
                    
                    # Конвертируем HSV обратно в RGB с новым оттенком
                    h = np.full_like(v, new_h)
                    
                    # Формула HSV -> RGB
                    c = v * s
                    x = c * (1 - np.abs((h * 6) % 2 - 1))
                    m = v - c
                    
                    h_i = (h * 6).astype(int) % 6
                    
                    new_rgb = np.zeros_like(rgb)
                    
                    # HSV to RGB conversion
                    mask0 = (h_i == 0)
                    mask1 = (h_i == 1)
                    mask2 = (h_i == 2)
                    mask3 = (h_i == 3)
                    mask4 = (h_i == 4)
                    
                    new_rgb[:, :, 0] = np.where(mask0, c + m, 
                                      np.where(mask1, x + m,
                                      np.where(mask2, m,
                                      np.where(mask3, m,
                                      np.where(mask4, x + m, c + m)))))
                    
                    new_rgb[:, :, 1] = np.where(mask0, x + m,
                                      np.where(mask1, c + m,
                                      np.where(mask2, c + m,
                                      np.where(mask3, x + m,
                                      np.where(mask4, m, m)))))
                    
                    new_rgb[:, :, 2] = np.where(mask0, m,
                                      np.where(mask1, m,
                                      np.where(mask2, x + m,
                                      np.where(mask3, c + m,
                                      np.where(mask4, c + m, x + m)))))
                    
                    # Применяем к непрозрачным пикселям и увеличиваем насыщенность
                    saturation_boost = 1.3  # Делаем цвета ярче
                    new_rgb = np.clip(new_rgb * saturation_boost, 0, 1)
                    
                    img_array[:, :, :3] = np.where(alpha_mask[:, :, np.newaxis], 
                                                 new_rgb * 255, 
                                                 img_array[:, :, :3])
                
                img = Image.fromarray(img_array.astype(np.uint8), 'RGBA')
                
            except ImportError:
                # Fallback на PIL с упрощенным алгоритмом
                pixels = img.load()
                for x in range(img.width):
                    for y in range(img.height):
                        r, g, b, a = pixels[x, y]
                        if a == 0:
                            continue
                        
                        # Сохраняем яркость, меняем оттенок
                        brightness = max(r, g, b) / 255.0
                        saturation = (max(r, g, b) - min(r, g, b)) / max(r, g, b) if max(r, g, b) > 0 else 0
                        
                        # Применяем новый цвет с сохранением яркости и насыщенности
                        new_r = int(target_color[0] * brightness * (1 + saturation * 0.3))
                        new_g = int(target_color[1] * brightness * (1 + saturation * 0.3))
                        new_b = int(target_color[2] * brightness * (1 + saturation * 0.3))
                        
                        pixels[x, y] = (min(255, new_r), min(255, new_g), min(255, new_b), a)
            
            output = io.BytesIO()
            img.save(output, format='PNG', optimize=True)
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
                "    \"\"\"🚀 Класс со всеми application эмодзи\"\"\"",
                ""
            ]
            
            # Сортируем эмодзи по имени для стабильности
            sorted_emojis = sorted(emojis, key=lambda e: e.name)
            
            for emoji in sorted_emojis:
                safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', emoji.name).upper()
                lines.append(f"    {safe_name} = \"{emoji}\"")

            lines.extend([
                "",
                "    @classmethod",
                "    def get_all(cls):",
                "        return {k: v for k, v in cls.__dict__.items() if not k.startswith('_') and k != 'get_all'}",
                "",
                "    @classmethod", 
                "    def get_by_color(cls, color: str):",
                "        return {k: v for k, v in cls.get_all().items() if k.endswith(f'_{color.upper()}')}"
            ])

            Path("emojis.py").write_text('\n'.join(lines), encoding='utf-8')
            self.logger.info("✅ Файл emojis.py обновлен")
            
        except Exception as e:
            self.logger.error(f"❌ Ошибка генерации emojis.py: {e}")

async def setup(bot):
    await bot.add_cog(EmojiManager(bot))
