import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict
import discord
import time
from discord.ext import commands
import wavelink

from config.constants import Colors
from core.player import HarmonyPlayer
from ui.embeds import create_error_embed

logger = logging.getLogger(__name__)

class EffectType(Enum):
    BASS_BOOST = "bass_boost"
    NIGHTCORE = "nightcore"
    VAPORWAVE = "vaporwave"
    TREBLE_BOOST = "treble_boost"  # ← ДОБАВИТЬ ЭТУ СТРОКУ
    KARAOKE = "karaoke"
    TREMOLO = "tremolo"
    VIBRATO = "vibrato"
    DISTORTION = "distortion"

@dataclass
class EffectConfig:
    name: str
    emoji: str
    description: str
    filters: Dict[str, Any]
    incompatible_with: list = None

    def __post_init__(self):
        if self.incompatible_with is None:
            self.incompatible_with = []

class AudioEffectsManager:
    """🎛️ Менеджер аудиоэффектов"""
    
    EFFECT_CONFIGS = {
        EffectType.BASS_BOOST: EffectConfig(
            name="Басбуст",
            emoji="🔊",
            description="Усиление низких частот",
            filters={
                "equalizer": {
                    "bands": [
                        {"band": 0, "gain": 0.6},
                        {"band": 1, "gain": 0.7},
                        {"band": 2, "gain": 0.8},
                        {"band": 3, "gain": 0.4},
                        {"band": 4, "gain": 0.0},
                    ]
                }
            }
        ),
        
        EffectType.NIGHTCORE: EffectConfig(
            name="Найткор",
            emoji="🌙",
            description="Ускорение и повышение тона",
            filters={
                "timescale": {"speed": 1.2, "pitch": 1.2, "rate": 1.0}
            },
            incompatible_with=[EffectType.VAPORWAVE]
        ),
        
        EffectType.VAPORWAVE: EffectConfig(
            name="Вейпорвейв",
            emoji="🌊",
            description="Замедление и понижение тона",
            filters={
                "timescale": {"speed": 0.8, "pitch": 0.8, "rate": 1.0},
                "equalizer": {
                    "bands": [
                        {"band": 0, "gain": -0.2},
                        {"band": 1, "gain": -0.2},
                        {"band": 2, "gain": -0.1},
                    ]
                }
            },
            incompatible_with=[EffectType.NIGHTCORE]
        ),
        
        EffectType.TREBLE_BOOST: EffectConfig(
            name="Требл буст",
            emoji="🔆",
            description="Усиление высоких частот",
            filters={
                "equalizer": {
                    "bands": [
                        {"band": 10, "gain": 0.5},
                        {"band": 11, "gain": 0.6},
                        {"band": 12, "gain": 0.7},
                        {"band": 13, "gain": 0.8},
                        {"band": 14, "gain": 0.6},
                    ]
                }
            }
        ),
        
        EffectType.KARAOKE: EffectConfig(
            name="Караоке",
            emoji="🎤",
            description="Подавление центрального канала (вокал)",
            filters={
                "karaoke": {
                    "level": 1.0,
                    "monoLevel": 1.0,
                    "filterBand": 220.0,
                    "filterWidth": 100.0
                }
            }
        ),
        
        EffectType.TREMOLO: EffectConfig(
            name="Тремоло",
            emoji="〰️",
            description="Модуляция амплитуды",
            filters={
                "tremolo": {"frequency": 2.0, "depth": 0.5}
            }
        ),
        
        EffectType.VIBRATO: EffectConfig(
            name="Вибрато",
            emoji="🎵",
            description="Модуляция частоты",
            filters={
                "vibrato": {"frequency": 2.0, "depth": 0.5}
            }
        ),
        
        EffectType.DISTORTION: EffectConfig(
            name="Дисторшн",
            emoji="⚡",
            description="Искажение звука",
            filters={
                "distortion": {
                    "sinOffset": 0.0,
                    "sinScale": 1.0,
                    "cosOffset": 0.0,
                    "cosScale": 1.0,
                    "tanOffset": 0.0,
                    "tanScale": 1.0,
                    "offset": 0.0,
                    "scale": 1.2
                }
            }
        )
    }

    @classmethod
    async def set_effects(cls, player: HarmonyPlayer, **kwargs):
        try:
            filters = wavelink.Filters()

            if kwargs.get('bass', False):
                filters.equalizer.set(bands=[
                    {"band": 0, "gain": 0.6},
                    {"band": 1, "gain": 0.7},
                    {"band": 2, "gain": 0.8},
                    {"band": 3, "gain": 0.4},
                    {"band": 4, "gain": 0.0},
                ])
            if kwargs.get('treble', False):
                filters.equalizer.set(bands=[
                    {"band": 10, "gain": 0.5},
                    {"band": 11, "gain": 0.6},
                    {"band": 12, "gain": 0.7},
                    {"band": 13, "gain": 0.8},
                    {"band": 14, "gain": 0.6},
                ])
            if kwargs.get('nightcore', False):
                filters.timescale.set(speed=1.2, pitch=1.2, rate=1.0)
            if kwargs.get('vaporwave', False):
                filters.timescale.set(speed=0.8, pitch=0.8, rate=1.0)
                filters.equalizer.set(bands=[
                    {"band": 0, "gain": -0.2},
                    {"band": 1, "gain": -0.2},
                    {"band": 2, "gain": -0.1},
                ])
            if kwargs.get('karaoke', False):
                filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
            if kwargs.get('tremolo', False):
                filters.tremolo.set(frequency=2.0, depth=0.5)
            if kwargs.get('vibrato', False):
                filters.vibrato.set(frequency=2.0, depth=0.5)
            if kwargs.get('distortion', False):
                filters.distortion.set(
                    sin_offset=0.0, sin_scale=1.0,
                    cos_offset=0.0, cos_scale=1.0,
                    tan_offset=0.0, tan_scale=1.0,
                    offset=0.0, scale=1.2
                )

            await player.set_filters(filters)
            logger.info(f"🎚️ [AudioEffectsManager] Applied filters: {kwargs}")
        except Exception as e:
            logger.error(f"❌ Failed to set effects via AudioEffectsManager: {e}")
            raise

        player.speed_override = 1.0
        if kwargs.get('nightcore'):
            player.speed_override = 1.2
        elif kwargs.get('vaporwave'):
            player.speed_override = 0.8

        player.start_time_real = time.time()

    @classmethod
    def get_effect_config(cls, effect_type: EffectType) -> EffectConfig:
        return cls.EFFECT_CONFIGS.get(effect_type)

    @classmethod
    def check_compatibility(cls, active_effects: list, new_effect: EffectType) -> tuple[bool, str]:
        """Проверка совместимости эффектов"""
        config = cls.get_effect_config(new_effect)
        if not config:
            return False, "Неизвестный эффект"
            
        for active_effect in active_effects:
            if active_effect in config.incompatible_with:
                active_config = cls.get_effect_config(active_effect)
                return False, f"Несовместим с {active_config.name if active_config else active_effect.value}"
                
        return True, ""

    @classmethod
    async def apply_effects(cls, player: HarmonyPlayer, effects: Dict[EffectType, bool]) -> bool:
        try:
            kwargs = {
                "bass": False,
                "treble": False,
                "nightcore": False,
                "vaporwave": False,
                "karaoke": False,
                "tremolo": False,
                "vibrato": False,
                "distortion": False,
            }

            active = [e for e, on in effects.items() if on]

            for effect in active:
                if effect == EffectType.BASS_BOOST:
                    kwargs["bass"] = True
                elif effect.name == "TREBLE_BOOST":
                    kwargs["treble"] = True
                elif effect == EffectType.NIGHTCORE:
                    kwargs["nightcore"] = True
                elif effect == EffectType.VAPORWAVE:
                    kwargs["vaporwave"] = True
                elif effect == EffectType.KARAOKE:
                    kwargs["karaoke"] = True
                elif effect == EffectType.TREMOLO:
                    kwargs["tremolo"] = True
                elif effect == EffectType.VIBRATO:
                    kwargs["vibrato"] = True
                elif effect == EffectType.DISTORTION:
                    kwargs["distortion"] = True

            # Применяем эффекты
            await player.set_effects(**kwargs)

            # Обновляем состояние
            for eff, enabled in effects.items():
                setattr(player.state, eff.value, enabled)

            logger.info(f"🎚️ Applied effects: {[e.value for e in active]}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed apply_effects: {e}")
            return False


class EffectsView(discord.ui.View):
    """Интерфейс управления эффектами"""
    
    def __init__(self, player: HarmonyPlayer):
        super().__init__(timeout=300)
        self.player = player
        self.effects_manager = AudioEffectsManager()
        
        # Добавляем селект меню
        self.add_item(EffectsSelect(player))
        
        # Добавляем кнопки управления
        self.add_item(ClearEffectsButton())
        self.add_item(RefreshButton())

class EffectsSelect(discord.ui.Select):
    """Селект меню для выбора эффектов"""
    
    def __init__(self, player: HarmonyPlayer):
        self.player = player
        self.effects_manager = AudioEffectsManager()
        
        options = []
        for effect_type in EffectType:
            config = self.effects_manager.get_effect_config(effect_type)
            is_active = getattr(player.state, effect_type.value, False)
            
            options.append(discord.SelectOption(
                label=config.name,
                value=effect_type.value,
                description=config.description,
                emoji=config.emoji,
                default=is_active
            ))
        
        super().__init__(
            placeholder="🎚️ Выберите эффекты для применения...",
            min_values=0,
            max_values=len(options),
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Получаем выбранные эффекты
        selected_effects = {
            EffectType(value): True for value in self.values
        }
        
        # Добавляем неактивные эффекты
        all_effects = {}
        for effect_type in EffectType:
            all_effects[effect_type] = effect_type in selected_effects
        
        # Проверяем совместимость
        active_effects = [e for e, enabled in all_effects.items() if enabled]
        for effect in active_effects:
            other_effects = [e for e in active_effects if e != effect]
            compatible, reason = self.effects_manager.check_compatibility(other_effects, effect)
            if not compatible:
                await interaction.response.send_message(
                    embed=create_error_embed("Ошибка совместимости", f"Эффект несовместим: {reason}"),
                    ephemeral=True
                )
                return
        
        # Применяем эффекты
        success = await self.effects_manager.apply_effects(self.player, all_effects)
        if not success:
            await interaction.response.send_message(
                embed=create_error_embed("Ошибка применения", "Не удалось применить эффекты!"),
                ephemeral=True
            )
            return
        
        # Обновляем интерфейс
        embed = self._create_status_embed(all_effects)
        view = EffectsView(self.player)
        await interaction.response.edit_message(embed=embed, view=view)
    
    def _create_status_embed(self, effects: Dict[EffectType, bool]) -> discord.Embed:
        """Создает embed с текущим статусом эффектов"""
        embed = discord.Embed(
            title="🎚️ Панель управления эффектами",
            description="Используйте меню ниже для управления звуковыми эффектами",
            color=Colors.PRIMARY
        )
        
        active_effects = []
        for effect_type, enabled in effects.items():
            if enabled:
                config = self.effects_manager.get_effect_config(effect_type)
                active_effects.append(f"{config.emoji} {config.name}")
        
        if active_effects:
            embed.add_field(
                name="🟢 Активные эффекты",
                value="\n".join(active_effects),
                inline=False
            )
        else:
            embed.add_field(
                name="⚪ Активные эффекты",
                value="Нет активных эффектов",
                inline=False
            )
        
        embed.set_footer(text="💡 Некоторые эффекты несовместимы друг с другом")
        return embed

class ClearEffectsButton(discord.ui.Button):
    """Кнопка очистки всех эффектов"""
    
    def __init__(self):
        super().__init__(
            label="Очистить все",
            style=discord.ButtonStyle.secondary,
            emoji="🧹"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: EffectsView = self.view
        
        # Отключаем все эффекты
        all_effects = {effect: False for effect in EffectType}
        success = await view.effects_manager.apply_effects(view.player, all_effects)
        
        if not success:
            await interaction.response.send_message(
                embed=create_error_embed("Ошибка очистки", "Не удалось очистить эффекты!"),
                ephemeral=True
            )
            return
        
        # Обновляем интерфейс
        embed = discord.Embed(
            title="🎚️ Панель управления эффектами",
            description="Используйте меню ниже для управления звуковыми эффектами",
            color=Colors.PRIMARY
        )
        embed.add_field(
            name="⚪ Активные эффекты",
            value="Нет активных эффектов",
            inline=False
        )
        embed.set_footer(text="💡 Некоторые эффекты несовместимы друг с другом")
        
        new_view = EffectsView(view.player)
        await interaction.response.edit_message(embed=embed, view=new_view)



class RefreshButton(discord.ui.Button):
    """Кнопка обновления интерфейса"""
    
    def __init__(self):
        super().__init__(
            label="Обновить",
            style=discord.ButtonStyle.primary,
            emoji="🔄"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: EffectsView = self.view
        
        # Получаем текущие эффекты
        current_effects = {}
        for effect_type in EffectType:
            current_effects[effect_type] = getattr(view.player.state, effect_type.value, False)
        
        # Создаем новый интерфейс
        embed = discord.Embed(
            title="🎚️ Панель управления эффектами",
            description="Используйте меню ниже для управления звуковыми эффектами",
            color=Colors.PRIMARY
        )
        
        active_effects = []
        for effect_type, enabled in current_effects.items():
            if enabled:
                config = view.effects_manager.get_effect_config(effect_type)
                active_effects.append(f"{config.emoji} {config.name}")
        
        if active_effects:
            embed.add_field(
                name="🟢 Активные эффекты",
                value="\n".join(active_effects),
                inline=False
            )
        else:
            embed.add_field(
                name="⚪ Активные эффекты",
                value="Нет активных эффектов",
                inline=False
            )
        
        embed.set_footer(text="💡 Некоторые эффекты несовместимы друг с другом")
        
        new_view = EffectsView(view.player)
        await interaction.response.edit_message(embed=embed, view=new_view)


class EffectsCommands(commands.Cog, name="🎚️ Эффекты"):
    """🎚️ Управление звуковыми эффектами"""

    def __init__(self, bot):
        self.bot = bot
        self.effects_manager = AudioEffectsManager()

    @discord.app_commands.command(name="effects", description="🎚️ Открыть панель управления эффектами")
    async def effects_panel(self, interaction: discord.Interaction):
        """🎚️ Открыть панель управления эффектами"""
        player: HarmonyPlayer = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(
                embed=create_error_embed("Ошибка", "Бот не подключен к голосовому каналу!"),
                ephemeral=True
            )

        # Получаем текущие эффекты
        current_effects = {}
        for effect_type in EffectType:
            current_effects[effect_type] = getattr(player.state, effect_type.value, False)

        # Создаем embed
        embed = discord.Embed(
            title="🎚️ Панель управления эффектами",
            description="Используйте меню ниже для управления звуковыми эффектами",
            color=Colors.PRIMARY
        )
        
        active_effects = []
        for effect_type, enabled in current_effects.items():
            if enabled:
                config = self.effects_manager.get_effect_config(effect_type)
                active_effects.append(f"{config.emoji} {config.name}")
        
        if active_effects:
            embed.add_field(
                name="🟢 Активные эффекты",
                value="\n".join(active_effects),
                inline=False
            )
        else:
            embed.add_field(
                name="⚪ Активные эффекты",
                value="Нет активных эффектов",
                inline=False
            )
        
        embed.set_footer(text="💡 Некоторые эффекты несовместимы друг с другом")

        # Создаем интерфейс
        view = EffectsView(player)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



async def setup(bot):
    await bot.add_cog(EffectsCommands(bot))
