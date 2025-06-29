"""
Advanced loop command with multiple repeat modes.
Based on TypeScript implementation with Python adaptations.
"""

import logging
import discord
from discord.ext import commands

from core.player import HarmonyPlayer, LoopMode
from ui.embeds import create_success_embed
from utils.builders.embed import build_permission_error_embed
from services import mongo_service

logger = logging.getLogger(__name__)


class LoopCommand:
    """Advanced loop command with multiple repeat modes."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def execute(self, interaction: discord.Interaction, mode: str = None) -> None:
        """Execute loop command with mode selection."""
        try:
            # Check if user is in voice channel
            if not interaction.user.voice or not interaction.user.voice.channel:
                # Получаем настройки гильдии для цвета
                try:
                    guild_id = interaction.guild.id if interaction.guild else None
                    settings = (
                        await mongo_service.get_guild_settings(guild_id)
                        if guild_id
                        else {}
                    )
                    color = settings.get("color", "default")
                    custom_emojis = settings.get("custom_emojis", {})

                    embed = build_permission_error_embed(
                        color=color, custom_emojis=custom_emojis
                    )
                except Exception as e:
                    logger.error(f"Error getting guild settings: {e}")
                    embed = build_permission_error_embed()

                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Get voice client
            vc = interaction.guild.voice_client
            if not vc or not isinstance(vc, HarmonyPlayer):
                await interaction.response.send_message(
                    "❌ Бот не подключен к голосовому каналу!", ephemeral=True
                )
                return

            # If no mode specified, cycle through modes
            if mode is None:
                await self._cycle_loop_mode(interaction, vc)
            else:
                await self._set_loop_mode(interaction, vc, mode)

        except Exception as e:
            logger.error(f"Loop command error: {e}")
            await interaction.response.send_message(
                "❌ Произошла ошибка при изменении режима повтора", ephemeral=True
            )

    async def _cycle_loop_mode(
        self, interaction: discord.Interaction, player: HarmonyPlayer
    ) -> None:
        """Cycle through loop modes."""
        current_mode = player.state.loop_mode

        # Define mode cycle
        mode_cycle = [LoopMode.NONE, LoopMode.TRACK, LoopMode.QUEUE]

        # Find next mode
        try:
            current_index = mode_cycle.index(current_mode)
            next_index = (current_index + 1) % len(mode_cycle)
            new_mode = mode_cycle[next_index]
        except ValueError:
            new_mode = LoopMode.NONE

        await self._set_loop_mode(interaction, player, new_mode.value)

    async def _set_loop_mode(
        self, interaction: discord.Interaction, player: HarmonyPlayer, mode: str
    ) -> None:
        """Set specific loop mode."""
        try:
            # Validate mode
            valid_modes = {
                "none": LoopMode.NONE,
                "track": LoopMode.TRACK,
                "queue": LoopMode.QUEUE,
            }

            mode_lower = mode.lower()
            if mode_lower not in valid_modes:
                await interaction.response.send_message(
                    "❌ Неверный режим повтора! Доступные: none, track, queue",
                    ephemeral=True,
                )
                return

            # Set new mode
            old_mode = player.state.loop_mode
            player.state.loop_mode = valid_modes[mode_lower]

            # Save to database
            await self._save_loop_mode(interaction.guild.id, mode_lower)

            # Create response embed
            embed = self._create_loop_embed(old_mode, player.state.loop_mode)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error setting loop mode: {e}")
            await interaction.response.send_message(
                "❌ Ошибка при установке режима повтора", ephemeral=True
            )

    async def _save_loop_mode(self, guild_id: int, mode: str) -> None:
        """Save loop mode to database."""
        try:
            settings = await mongo_service.get_guild_settings(guild_id)
            settings["loop_mode"] = mode
            await mongo_service.save_guild_settings(guild_id, settings)
        except Exception as e:
            logger.error(f"Failed to save loop mode: {e}")

    def _create_loop_embed(
        self, old_mode: LoopMode, new_mode: LoopMode
    ) -> discord.Embed:
        """Create embed showing loop mode change."""
        mode_names = {
            LoopMode.NONE: "Отключен",
            LoopMode.TRACK: "Трек",
            LoopMode.QUEUE: "Очередь",
        }

        old_name = mode_names.get(old_mode, "Неизвестно")
        new_name = mode_names.get(new_mode, "Неизвестно")

        embed = create_success_embed(
            "🔄 Режим повтора изменен", f"**Было:** {old_name}\n**Стало:** {new_name}"
        )

        # Add mode descriptions
        descriptions = {
            LoopMode.NONE: "Треки не повторяются",
            LoopMode.TRACK: "Текущий трек повторяется бесконечно",
            LoopMode.QUEUE: "Вся очередь повторяется циклически",
        }

        description = descriptions.get(new_mode, "")
        if description:
            embed.add_field(name="Описание", value=description, inline=False)

        return embed

    async def get_current_mode(self, player: HarmonyPlayer) -> str:
        """Get current loop mode as string."""
        mode_names = {
            LoopMode.NONE: "none",
            LoopMode.TRACK: "track",
            LoopMode.QUEUE: "queue",
        }
        return mode_names.get(player.state.loop_mode, "none")


# Convenience function for slash command
async def loop_command(interaction: discord.Interaction, mode: str = None) -> None:
    """Loop command for slash commands."""
    bot = interaction.client
    command = LoopCommand(bot)
    await command.execute(interaction, mode)
