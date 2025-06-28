"""
Advanced queue command with pagination and interaction handling.
Based on TypeScript implementation with Python adaptations.
"""

import logging
import discord
from discord.ext import commands

from core.player import HarmonyPlayer
from ui.music_embeds import create_empty_queue_embed
from ui.views import QueueView

logger = logging.getLogger(__name__)


class QueueCommand:
    """Advanced queue command with pagination support."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def execute(self, interaction: discord.Interaction) -> None:
        """Execute queue command with proper error handling."""
        try:
            # Check if user is in voice channel
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.response.send_message(
                    "❌ Вы должны быть в голосовом канале!", ephemeral=True
                )
                return

            # Get voice client
            vc = interaction.guild.voice_client
            if not vc or not isinstance(vc, HarmonyPlayer):
                await interaction.response.send_message(
                    embed=create_empty_queue_embed(), ephemeral=True
                )
                return

            # Defer response for better UX
            await interaction.response.defer(ephemeral=True)

            # Show queue with pagination
            await self._show_queue_page(interaction, vc, page=1)

        except Exception as e:
            logger.error(f"Queue command error: {e}")
            try:
                await interaction.followup.send(
                    "❌ Произошла ошибка при отображении очереди", ephemeral=True
                )
            except Exception as inner_e:
                logger.warning(f"Followup send failed: {inner_e}")

    async def _show_queue_page(
        self, interaction: discord.Interaction, player: HarmonyPlayer, page: int = 1
    ) -> None:
        """Show specific page of the queue."""
        try:
            items_per_page = 10
            total_tracks = len(player.playlist)

            if total_tracks == 0:
                await interaction.followup.send(
                    embed=create_empty_queue_embed(), ephemeral=True
                )
                return

            # Calculate pagination
            total_pages = max((total_tracks - 1) // items_per_page + 1, 1)
            if page > total_pages:
                page = total_pages
            elif page < 1:
                page = 1

            # Get tracks for current page
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            visible_queue = player.playlist[start_index:end_index]

            # Create embed
            from ui.music_embeds import create_queue_embed

            embed = create_queue_embed(
                guild=interaction.guild,
                now_playing=player.current,
                queue=visible_queue,
                page=page,
                total_pages=total_pages,
                user=interaction.user,
            )

            # Create pagination view
            view = await QueueView.create(
                player=player, user=interaction.user, page=page, total_pages=total_pages
            )

            # Send response
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error(f"Error showing queue page: {e}")
            await interaction.followup.send(
                "❌ Ошибка при отображении страницы очереди", ephemeral=True
            )

    async def handle_pagination_interaction(
        self, interaction: discord.Interaction, action: str
    ) -> None:
        """Handle pagination button interactions."""
        try:
            # Get current page from embed footer
            embed = interaction.message.embeds[0]
            footer_text = embed.footer.text if embed.footer else ""

            # Parse current page
            try:
                current_page = int(footer_text.split(" ")[1].split("/")[0])
            except (IndexError, ValueError):
                current_page = 1

            # Calculate new page
            if action == "left":
                new_page = max(current_page - 1, 1)
            elif action == "right":
                new_page = current_page + 1
            else:
                return

            # Get player
            vc = interaction.guild.voice_client
            if not vc or not isinstance(vc, HarmonyPlayer):
                await interaction.response.send_message(
                    "❌ Плеер не найден", ephemeral=True
                )
                return

            # Show new page
            await self._show_queue_page(interaction, vc, new_page)

        except Exception as e:
            logger.error(f"Pagination interaction error: {e}")
            await interaction.response.send_message(
                "❌ Ошибка при переключении страницы", ephemeral=True
            )


# Convenience function for slash command
async def queue_command(interaction: discord.Interaction) -> None:
    """Queue command for slash commands."""
    bot = interaction.client
    command = QueueCommand(bot)
    await command.execute(interaction)
