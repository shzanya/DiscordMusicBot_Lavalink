import discord
from discord.ext import commands
import wavelink
import logging
import os
from pathlib import Path
from config.settings import Settings
from core.events import EventHandler
from core.assets import AutoEmojiManager

class HarmonyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=Settings.COMMAND_PREFIX,  # убрал _get_prefix
            intents=intents,
            description="🎵 Современный музыкальный бот для Discord",
            case_insensitive=True,
            strip_after_prefix=True
        )

        # self.db = DatabaseService()  <-- Удалено
        self.ready = False
        self.logger = self.get_logger()
        self.synced = False
        self.loaded_cogs = []
          # Список загруженных когов

    async def setup_hook(self):
        """🔧 Настройка бота при запуске"""
        await self.setup_emoji_manager()  # ✅ Вызов

    async def setup_emoji_manager(self):
        """⚙️ Установка и синхронизация эмодзи"""
        manager = AutoEmojiManager(self)
        await manager.auto_sync_emojis()
        # Подключение к Lavalink
        nodes = [
            wavelink.Node(
                identifier="HARMONY_NODE",
                uri=f"{'wss' if Settings.LAVALINK_SECURE else 'ws'}://{Settings.LAVALINK_HOST}:{Settings.LAVALINK_PORT}",
                password=Settings.LAVALINK_PASSWORD,
                heartbeat=30.0,
                retries=3
            )
        ]
        
        await wavelink.Pool.connect(
            nodes=nodes,
            client=self,
            cache_capacity=100
        )
        
        # Загрузка команд из структурированных папок
        await self._load_cogs_from_structure()
        
        # Инициализация обработчиков событий
        await self.add_cog(EventHandler(self))
        
        self.logger.info("🎵 Harmony Bot инициализирован!")

    async def _load_cogs_from_structure(self):
        """📂 Загрузка когов из структурированных папок"""
        # Определяем структуру папок с когами
        cog_structure = {
            'commands/music': [
                'playback',
                'queue',
                'effects',
                # 'favorites',  # ⛔ ModuleNotFoundError: services.database
                # 'lyrics',     # ⛔ файл не найден
                # 'radio'       # ⛔ файл не найден
            ],
            'commands/playlist': [
                # 'management',     # ⛔ ModuleNotFoundError
                # 'sharing',        # ⛔ ModuleNotFoundError
                # 'import_export'   # ⛔ файл не найден
            ],
            'commands/admin': [
                # 'settings',     # ⛔ ModuleNotFoundError
                # 'permissions',  # ⛔ ModuleNotFoundError
                # 'moderation'    # ⛔ файл не найден
            ],
            'commands/utility': [
                # 'help',   # ⛔ файл не найден
                # 'info',   # ⛔ файл не найден
                # 'stats'   # ⛔ файл не найден
            ],
            'commands/Emoji': [
                'EmojiManager'
            ]
        }

        self.logger.info("📂 Начинаю загрузку когов...")
        
        # Очистка существующих когов
        await self._unload_all_cogs()
        
        total_loaded = 0
        
        # Загрузка из каждой категории
        for folder_path, cog_names in cog_structure.items():
            category_name = folder_path.split('/')[-1]
            self.logger.info(f"📁 Загружаю категорию: {category_name.upper()}")
            
            loaded_in_category = 0
            
            for cog_name in cog_names:
                success = await self._load_single_cog(folder_path, cog_name)
                if success:
                    loaded_in_category += 1
                    total_loaded += 1
            
            self.logger.info(f"✅ {category_name.upper()}: {loaded_in_category}/{len(cog_names)} когов загружено")
        
        # Дополнительная загрузка из __init__.py файлов
        await self._load_cogs_from_init_files()
        
        self.logger.info(f"🎯 Всего загружено {total_loaded} когов")

    async def _load_single_cog(self, folder_path: str, cog_name: str) -> bool:
        """📄 Загрузка одного кога"""
        # Попробуем разные варианты путей
        possible_paths = [
            f"{folder_path}/{cog_name}.py",
            f"{folder_path}/{cog_name}/main.py",
            f"{folder_path}/{cog_name}/__init__.py"
        ]
        
        for file_path in possible_paths:
            if os.path.exists(file_path):
                try:
                    # Формируем модульный путь
                    module_path = file_path.replace('/', '.').replace('\\', '.').replace('.py', '')
                    
                    await self.load_extension(module_path)
                    self.loaded_cogs.append(module_path)
                    self.logger.info(f"  ✅ {cog_name}")
                    return True
                    
                except Exception as e:
                    self.logger.error(f"  ❌ {cog_name}: {e}")
                    continue
        
        # Если не найден ни один файл
        self.logger.warning(f"  ⚠️ {cog_name}: файл не найден")
        return False

    async def _load_cogs_from_init_files(self):
        """📋 Загрузка когов из __init__.py файлов"""
        init_files = [
            'commands/music/__init__.py',
            'commands/playlist/__init__.py', 
            'commands/admin/__init__.py',
            'commands/utility/__init__.py'
        ]
        
        for init_file in init_files:
            if os.path.exists(init_file):
                try:
                    module_path = init_file.replace('/', '.').replace('\\', '.').replace('.py', '')
                    await self.load_extension(module_path)
                    self.loaded_cogs.append(module_path)
                    category = init_file.split('/')[1]
                    self.logger.info(f"📋 Загружен __init__ для {category}")
                except Exception as e:
                    self.logger.error(f"❌ Ошибка загрузки {init_file}: {e}")

    async def _discover_and_load_all_cogs(self):
        """🔍 Автоматическое обнаружение и загрузка всех когов"""
        commands_dir = Path('commands')
        
        if not commands_dir.exists():
            self.logger.warning("📁 Папка commands не найдена")
            return
        
        self.logger.info("🔍 Автоматический поиск когов...")
        
        # Рекурсивный поиск всех .py файлов
        for py_file in commands_dir.rglob('*.py'):
            # Пропускаем системные файлы
            if py_file.name.startswith('_') and py_file.name != '__init__.py':
                continue
                
            # Формируем путь модуля
            relative_path = py_file.relative_to(Path('.'))
            module_path = str(relative_path).replace(os.sep, '.').replace('.py', '')
            
            # Пропускаем уже загруженные
            if module_path in self.loaded_cogs:
                continue
            
            try:
                await self.load_extension(module_path)
                self.loaded_cogs.append(module_path)
                self.logger.info(f"🔍 Обнаружен и загружен: {module_path}")
            except Exception as e:
                self.logger.debug(f"🔍 Пропущен {module_path}: {e}")

    async def _unload_all_cogs(self):
        """🗑️ Выгрузка всех когов"""
        extensions_to_unload = list(self.extensions.keys())
        
        for extension in extensions_to_unload:
            try:
                await self.unload_extension(extension)
                self.logger.debug(f"🗑️ Выгружен: {extension}")
            except Exception as e:
                self.logger.error(f"❌ Ошибка выгрузки {extension}: {e}")
        
        self.loaded_cogs.clear()

    async def on_ready(self):
        """🚀 Событие готовности бота"""
        if self.ready:
            return
        self.ready = True
        
        # Синхронизация slash команд
        if not self.synced:
            try:
                synced = await self.tree.sync()
                self.logger.info(f"🔄 Синхронизировано {len(synced)} slash команд")
                self.synced = True
            except Exception as e:
                self.logger.error(f"❌ Ошибка синхронизации команд: {e}")
        
        self.logger.info(f"🎵 {self.user} готов к работе!")
        self.logger.info(f"📊 Подключен к {len(self.guilds)} серверам")
        self.logger.info(f"👥 Обслуживает {len(self.users)} пользователей")
        self.logger.info(f"⚙️ Загружено {len(self.loaded_cogs)} когов")
        
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=f"{Settings.COMMAND_PREFIX}help | 🎵 Музыка для всех"
            )
        )

    async def reload_cogs(self, category: str = None):
        """🔄 Перезагрузка когов"""
        if category:
            self.logger.info(f"🔄 Перезагрузка категории: {category}")
            # Перезагрузка конкретной категории
            cogs_to_reload = [cog for cog in self.loaded_cogs if f'commands.{category}' in cog]
            
            for cog in cogs_to_reload:
                try:
                    await self.reload_extension(cog)
                    self.logger.info(f"🔄 Перезагружен: {cog}")
                except Exception as e:
                    self.logger.error(f"❌ Ошибка перезагрузки {cog}: {e}")
        else:
            self.logger.info("🔄 Полная перезагрузка всех когов...")
            await self._load_cogs_from_structure()
        
        # Повторная синхронизация slash команд
        try:
            synced = await self.tree.sync()
            self.logger.info(f"🔄 Пересинхронизировано {len(synced)} slash команд")
        except Exception as e:
            self.logger.error(f"❌ Ошибка пересинхронизации: {e}")
        
        self.logger.info("✅ Перезагрузка завершена!")

    def get_logger(self):
        """📝 Получение логгера"""
        return logging.getLogger(f'HarmonyBot.{self.__class__.__name__}')

    async def get_cog_info(self):
        """📋 Получение информации о загруженных когах"""
        info = {
            'total_cogs': len(self.loaded_cogs),
            'categories': {},
            'loaded_cogs': self.loaded_cogs
        }
        
        # Группируем по категориям
        for cog in self.loaded_cogs:
            if 'commands.' in cog:
                category = cog.split('.')[1] if len(cog.split('.')) > 1 else 'other'
                if category not in info['categories']:
                    info['categories'][category] = []
                info['categories'][category].append(cog)
        
        return info


    async def on_guild_remove(self, guild):
        """👋 Событие покидания сервера"""
        self.logger.info(f"👋 Покинул сервер: {guild.name} ({guild.id})")

# Функции для разработки
async def setup_dev_commands(bot: HarmonyBot):
    """⚙️ Настройка команд для разработки"""
    
    @bot.tree.command(name="reload", description="🔄 Перезагрузить коги")
    async def reload_command(interaction: discord.Interaction, category: str = None):
        if interaction.user.id != 123456789:  # Замените на свой ID
            await interaction.response.send_message("❌ У вас нет прав!", ephemeral=True)
            return
            
        await interaction.response.defer()
        await bot.reload_cogs(category)
        
        if category:
            await interaction.followup.send(f"✅ Категория {category} перезагружена!")
        else:
            await interaction.followup.send("✅ Все коги перезагружены!")
    
    @bot.tree.command(name="coginfo", description="📋 Информация о загруженных когах")
    async def coginfo_command(interaction: discord.Interaction):
        if interaction.user.id != 123456789:  # Замените на свой ID
            await interaction.response.send_message("❌ У вас нет прав!", ephemeral=True)
            return
        
        info = await bot.get_cog_info()
        
        embed = discord.Embed(
            title="📋 Информация о когах",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Статистика",
            value=f"Всего когов: {info['total_cogs']}",
            inline=False
        )
        
        for category, cogs in info['categories'].items():
            cog_list = '\n'.join([f"• {cog.split('.')[-1]}" for cog in cogs])
            embed.add_field(
                name=f"📁 {category.upper()}",
                value=cog_list or "Нет когов",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)

# Пример использования:
if __name__ == "__main__":
    bot = HarmonyBot()
    
    # Добавляем dev команды (только для разработки)
    # await setup_dev_commands(bot)
    
    # bot.run(Settings.DISCORD_TOKEN)
