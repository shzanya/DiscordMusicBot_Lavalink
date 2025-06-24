import asyncio
import re
import traceback

import discord
import wavelink
from discord import Interaction, app_commands
from discord.ext import commands
from typing import Optional
from cachetools import TTLCache
from config.constants import Colors, Emojis
from ui.embeds import (
    cleanup_updater,
    create_error_embed,
    create_now_playing_embed,
    now_playing_updater,
    send_now_playing_message,
)


class HarmonyPlayer(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous = None
        self._current_track = None
        self.history = []
        self.max_history_size = 25
        self.view: Optional[discord.ui.View] = None
        self.queue_message: Optional[discord.Message] = None  # для отображения очереди
        self.channel: Optional[discord.TextChannel] = None  # канал для embed'ов

    @property
    def is_paused(self):
        return getattr(self, '_paused', False)

    @property
    def current_track(self):
        return self._current_track

    @property
    def current(self):
        return self._current_track

    async def on_voice_state_update(self, data):
        try:
            await super().on_voice_state_update(data)
        except AssertionError:
            print(f"[Wavelink] Игнорируем destroy без guild: {self}")

    async def _destroy(self):
        if not getattr(self, "guild", None):
            print("[DEBUG] Пропущен _destroy — self.guild is None")
            return
        await super()._destroy()

    async def show_queue(self, interaction: discord.Interaction, limit: int = 10):
        if self.queue.is_empty:
            return await interaction.response.send_message(
                embed=discord.Embed(
                    title="Очередь пуста",
                    description="Добавьте треки с помощью `/play`.",
                    color=Colors.WARNING
                ),
                ephemeral=True
            )

        description = ""
        for i, track in enumerate(list(self.queue)[:limit], start=1):
            description += f"**{i}.** {track.author} — {track.title}\n"

        remaining = self.queue.count - limit
        if remaining > 0:
            description += f"\nИ ещё **{remaining}** трек(ов)..."

        embed = discord.Embed(
            title="🎶 Очередь воспроизведения",
            description=description,
            color=Colors.PRIMARY
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def play_track(self, track):
        self._add_to_history(track)
        self._current_track = track
        if not self.guild:
            print("[ERROR] Невозможно воспроизвести: self.guild is None")
            return
        try:
            await self.play(track)
        except AssertionError:
            print("[ERROR] Ошибка воспроизведения — self.guild отсутствует.")
            return

        if self.view and hasattr(self.view, 'refresh_select_menu'):
            try:
                await self.view.refresh_select_menu()
            except Exception as e:
                print(f"[ERROR] View refresh failed: {e}")

        await self._update_now_playing(track)
        await self._update_queue_embed()

    def _add_to_history(self, track):
        if track in self.history:
            self.history.remove(track)
        self.history.append(track)
        if len(self.history) > self.max_history_size:
            self.history.pop(0)

    async def do_next(self):
        if not self.queue.is_empty:
            next_track = self.queue.get()
            await self.play_track(next_track)
        else:
            self._current_track = None
            await self._update_now_playing(None)
            await self._update_queue_embed()

            # Авто-лив через 5 минут
            async def leave_later():
                await asyncio.sleep(300)
                if not self.playing and not self.queue and self.guild.voice_client:
                    await self.guild.voice_client.disconnect()

            asyncio.create_task(leave_later())

    async def skip(self):
        await self.do_next()

    async def play_previous(self):
        if self.previous:
            current = self._current_track
            await self.play_track(self.previous)
            self.previous = current
            return True
        return False

    async def _update_now_playing(self, track):
        if not self.guild:
            return
        if self.guild.id in now_playing_updater.active_messages:
            info = now_playing_updater.active_messages[self.guild.id]
            message = info['message']
            requester = info['requester']

            if track:
                embed = create_now_playing_embed(track, self, requester)
            else:
                embed = discord.Embed(title="⏹️ Воспроизведение остановлено", color=Colors.MAIN)

            try:
                await message.edit(embed=embed)
            except Exception:
                now_playing_updater.unregister_message(self.guild.id)

    async def _update_queue_embed(self):
        if not self.channel:
            return

        queue = list(self.queue)
        if not queue:
            desc = "*Очередь пуста*"
        else:
            desc = "\n".join(
                [f"`{i+1}.` **{t.title}** — *{t.author}*" for i, t in enumerate(queue[:10])]
            )
            if len(queue) > 10:
                desc += f"\n...и еще **{len(queue)-10}** треков."

        embed = discord.Embed(
            title="📜 Очередь треков",
            description=desc,
            color=Colors.MAIN
        )

        try:
            if self.queue_message:
                await self.queue_message.edit(embed=embed)
            else:
                self.queue_message = await self.channel.send(embed=embed)
        except Exception as e:
            print(f"[Queue Embed Error] {e}")



autocomplete_cache = TTLCache(maxsize=100, ttl=120)

async def track_autocomplete(interaction: Interaction, current: str):
    query = current.strip().lower()
    if len(query) < 3:
        return []

    # Кеш
    if query in autocomplete_cache:
        return autocomplete_cache[query]

    try:
        # Ограничиваем до 2 сек, чтобы не словить таймаут Discord
        tracks = await asyncio.wait_for(
            wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube),
            timeout=2.0
        )

        choices = [
            app_commands.Choice(
                name=f"{t.author} – {t.title}"[:100],
                value=t.uri
            )
            for t in tracks[:5]
        ]

        autocomplete_cache[query] = choices
        return choices

    except asyncio.TimeoutError:
        print("[autocomplete] Превышен таймаут поиска треков")
        return []

    except Exception as e:
        print(f"[autocomplete] Ошибка: {e}")
        return []



class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_unload(self):
        cleanup_updater()

    async def _search_tracks(self, query: str):
        try:
            is_url = re.match(r'^https?://', query, re.IGNORECASE)
            source = wavelink.TrackSource.YouTube if is_url else wavelink.TrackSource.SoundCloud

            results = await asyncio.wait_for(
                wavelink.Playable.search(query, source=source),
                timeout=5.0
            )

            if not results and not is_url:
                results = await asyncio.wait_for(
                    wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube),
                    timeout=5.0
                )

            return results
        except asyncio.TimeoutError:
            print(f"[Wavelink] Timeout on query: {query}")
            return None
        except Exception:
            traceback.print_exc()
            return None

    @app_commands.command(name="queue", description="📄 Показать текущую очередь треков")
    async def queue(self, interaction: discord.Interaction):
        vc: HarmonyPlayer = interaction.guild.voice_client
        if not vc or not isinstance(vc, HarmonyPlayer):
            return await interaction.response.send_message(
                embed=create_error_embed("Ошибка", "Бот не в голосовом канале"),
                ephemeral=True
            )

        await vc.show_queue(interaction)


    @app_commands.command(name="play", description="🎵 Искать и воспроизводить музыку")
    @app_commands.describe(поиск="Название, исполнитель или URL")
    @app_commands.autocomplete(поиск=track_autocomplete)
    async def play(self, interaction: discord.Interaction, поиск: str):
        # Проверка подключения к голосовому
        vc_channel = getattr(interaction.user.voice, "channel", None)
        if not vc_channel:
            return await interaction.response.send_message(
                embed=create_error_embed("Ошибка", "Вы не в голосовом канале"),
                ephemeral=True
            )

        # Отложить ответ (обязательно ДО любого запроса в сеть)
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        except discord.HTTPException as e:
            print(f"[DEBUG] interaction.defer() error: {e}")
            return  # завершить, т.к. интеракция уже недействительна

        # Подключение
        if not (vc := interaction.guild.voice_client):
            try:
                vc = await vc_channel.connect(cls=HarmonyPlayer)
            except Exception:
                return await interaction.followup.send(
                    embed=create_error_embed("Ошибка", "Не удалось подключиться к голосовому каналу"),
                    ephemeral=True
                )

        # Безопасный defer
        if not interaction.response.is_done():
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except discord.InteractionResponded:
                pass

        results = await self._search_tracks(поиск)
        if not results:
            return await interaction.followup.send(
                embed=create_error_embed("Поиск", f"Ничего не найдено по запросу: `{поиск}`"),
                ephemeral=True
            )

        if isinstance(results, wavelink.Playlist):
            for track in results.tracks:
                vc.queue.put(track)

            embed = discord.Embed(
                title=f"{Emojis.ADD} Плейлист добавлен",
                description=f"**{results.name}** — {len(results.tracks)} треков",
                color=Colors.SUCCESS
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            if not vc.playing and not vc.paused:
                await vc.do_next()
                await send_now_playing_message(interaction.channel, vc.current, vc, interaction.user)

        else:
            track = results[0]
            if vc.playing or vc.paused or vc.current:
                vc.queue.put(track)
                await interaction.followup.send(
                    embed=discord.Embed(
                        description=f"Добавлено в очередь: **{track.author} — {track.title}**",
                        color=Colors.SUCCESS
                    ),
                    ephemeral=True
                )
            else:
                await vc.play_track(track)
                await send_now_playing_message(interaction.channel, vc.current, vc, interaction.user)

                await interaction.followup.send(
                    embed=discord.Embed(
                        description=f"Воспроизводится: **{track.author} — {track.title}**",
                        color=Colors.SUCCESS
                    ),
                    ephemeral=True
                )

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: HarmonyPlayer = payload.player
        try:
            if player is not None and getattr(player, 'guild', None):
                await player.do_next()
        except AssertionError:
            print("[track_end] player.guild not available (destroyed)")

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        if payload.player.guild and payload.player.current:
            guild_id = payload.player.guild.id
            if guild_id in now_playing_updater.active_messages:
                info = now_playing_updater.active_messages[guild_id]
                message = info['message']
                requester = info['requester']
                embed = create_now_playing_embed(payload.player.current, payload.player, requester)
                try:
                    await message.edit(embed=embed)
                except (discord.NotFound, discord.Forbidden):
                    now_playing_updater.unregister_message(guild_id)
                    await self._create_new_message(payload, guild_id)
            else:
                await self._create_new_message(payload, guild_id)

    async def _create_new_message(self, payload: wavelink.TrackStartEventPayload, guild_id: int):
        try:
            channel = payload.player.guild.system_channel
            if not channel:
                for ch in payload.player.guild.text_channels:
                    if ch.permissions_for(payload.player.guild.me).send_messages:
                        channel = ch
                        break

            if channel:
                await send_now_playing_message(channel, payload.player.current, payload.player, payload.player.guild.me)

        except Exception as e:
            print(f"[DEBUG] Error creating now playing message: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
