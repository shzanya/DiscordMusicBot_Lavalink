import discord
import wavelink
from discord import app_commands , Interaction
from discord.ext import commands
from config.constants import Colors, Emojis
import traceback
from ui.embeds import (
    cleanup_updater,
    create_error_embed,
    create_now_playing_embed,
    now_playing_updater,
    send_now_playing_message,
)
from ui.views import MusicPlayerView


class HarmonyPlayer(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous = None
        self._current_track = None
        self.history = []
    @property
    def current_track(self):
        return self._current_track
    @property  
    def current(self):
        return self._current_track
    
    async def play_track(self, track: wavelink.Playable):
        if self._current_track:
            self.history.append(self._current_track)
        self._current_track = track
        await self.play(track)

    async def skip(self):
        if not self.queue.is_empty:
            next_track = self.queue.get()
            await self.play_track(next_track)
            if self.guild and self.guild.id in now_playing_updater.active_messages:
                info = now_playing_updater.active_messages[self.guild.id]
                message = info['message']
                requester = info['requester']
                embed = create_now_playing_embed(next_track, self, requester)
                try:
                    await message.edit(embed=embed)
                except Exception:
                    now_playing_updater.unregister_message(self.guild.id)
        else:
            self.previous = self._current_track
            self._current_track = None
            await self.stop()
            if self.guild:
                now_playing_updater.unregister_message(self.guild.id)

    async def play_previous(self):
        if self.previous:
            current = self._current_track
            await self.play_track(self.previous)
            self.previous = current
            if self.guild and self.guild.id in now_playing_updater.active_messages:
                info = now_playing_updater.active_messages[self.guild.id]
                message = info['message']
                requester = info['requester']
                embed = create_now_playing_embed(self._current_track, self, requester)
                try:
                    await message.edit(embed=embed)
                except Exception:
                    now_playing_updater.unregister_message(self.guild.id)
            return True
        return False

    async def do_next(self):
        if not self.queue.is_empty:
            next_track = self.queue.get()
            await self.play_track(next_track)
        else:
            await self.stop()

async def track_autocomplete(interaction: Interaction, current: str):
    if len(current) < 3:
        await interaction.response.autocomplete([])
        return

    try:
        tracks = await wavelink.Playable.search(current, source=wavelink.TrackSource.YouTube)
        choices = [
            app_commands.Choice(
                name=f"{t.author} – {t.title}"[:100],
                value=f"{current}#{i}"
            )
            for i, t in enumerate(tracks[:5])
        ]
        await interaction.response.autocomplete(choices)
    except Exception as e:
        print(f"[autocomplete error] {e}")
        await interaction.response.autocomplete([])

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_unload(self):
        cleanup_updater()

    async def _search_tracks(self, query: str):
        try:
            res = await wavelink.Playable.search(query, source=wavelink.TrackSource.SoundCloud)
            return res or await wavelink.Playable.search(query, source=wavelink.TrackSource.YouTube)
        except wavelink.WavelinkException as e:
            print(f"[Wavelink] Search error: {e}")
            return None
        except Exception:
            print("[DEBUG] Unexpected error during track search:")
            traceback.print_exc()
            return None

    @app_commands.command(name="play", description="🎵 Искать и воспроизводить музыку")
    @app_commands.describe(поиск="Название, исполнитель или URL")
    @app_commands.autocomplete(поиск=track_autocomplete)
    async def play(
        self,
        interaction: discord.Interaction,
        поиск: str
    ):
        # ——————— Проверка канала ———————
        if not (vc_channel := interaction.user.voice and interaction.user.voice.channel):
            return await interaction.response.send_message(
                embed=create_error_embed("Ошибка", "Вы не в голосовом канале"),
                ephemeral=True
            )

        # ——————— Подключаемся к лава-ноде ———————
        if not (vc := interaction.guild.voice_client):
            try:
                vc = await vc_channel.connect(cls=HarmonyPlayer)
            except Exception:
                return await interaction.response.send_message(
                    embed=create_error_embed("Ошибка", "Не удалось подключиться"),
                    ephemeral=True
                )

        # ——————— Один defer и только один ———————
        await interaction.response.defer(ephemeral=True)

        # ——————— Поиск треков ———————
        results = await self._search_tracks(поиск)
        if not results:
            return await interaction.followup.send(
                embed=create_error_embed("Поиск", f"Ничего не найдено: `{поиск}`"),
                ephemeral=True
            )

        # ——————— Обработка плейлиста ———————
        if isinstance(results, wavelink.Playlist):
            for t in results.tracks:
                vc.queue.put(t)
            await interaction.followup.send(
                embed=discord.Embed(
                    title=f"{Emojis.ADD} Плейлист добавлен",
                    description=f"**{results.name}** — {len(results.tracks)} треков",
                    color=Colors.SUCCESS
                ),
                ephemeral=True
            )
            if not vc.playing:
                await vc.do_next()
                await self._start_now_playing_update(interaction.channel, vc, interaction.user)

        # ——————— Одиночный трек ———————
        else:
            track = results[0]
            if vc.playing:
                vc.queue.put(track)
            else:
                await vc.play_track(track)
                await self._start_now_playing_update(interaction.channel, vc, interaction.user)

            await interaction.followup.send(
                embed=discord.Embed(
                    description=f"Добавлено в очередь: **{track.author} — {track.title}**",
                    color=Colors.SUCCESS
                ),
                ephemeral=True
            )

    async def _start_now_playing_update(self, channel, vc, user):
        embed = create_now_playing_embed(vc.current, vc, user)
        view = MusicPlayerView(player=vc, requester=user)
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
        await now_playing_updater.register_message(
            vc.guild.id, msg, vc, vc.current, user
        )
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        if payload.player.guild and not payload.player.queue:
            now_playing_updater.unregister_message(payload.player.guild.id)

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
                message = await send_now_playing_message(channel, payload.player.current, payload.player, payload.player.guild.me)
                if message:
                    await now_playing_updater.register_message(
                        guild_id,
                        message,
                        payload.player,
                        payload.player.current,
                        payload.player.guild.me
                    )
        except Exception as e:
            print(f"[DEBUG] Error creating new message: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
