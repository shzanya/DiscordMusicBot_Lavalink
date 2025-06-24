import asyncio
import logging
from pathlib import Path

from core.bot import HarmonyBot

from config.settings import Settings

async def main():
    """🚀 Главная функция запуска бота"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=[
            logging.FileHandler('harmony.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger('HarmonyBot')
    logger.info("🎵 Запуск Harmony Music Bot...")
    
    # Инициализация бота
    bot = HarmonyBot()
    
    try:
        await bot.start(Settings.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("🔄 Остановка бота...")
        await bot.close()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
