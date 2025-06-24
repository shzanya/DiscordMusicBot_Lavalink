import discord
from discord.ext import commands
from discord import app_commands
import wavelink
from config.constants import Emojis, Colors


from ui.embeds import (
    create_error_embed, 
    send_now_playing_message,
    create_now_playing_embed,
    now_playing_updater,
    cleanup_updater       # Добавили импорт
)

class HarmonyPlayer(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous = None
        self._current_track = None  # поменяли имя

    @property
    def current_track(self):
        return self._current_track

    async def play_track(self, track: wavelink.Playable):
        """Проигрывает трек и сохраняет предыдущий"""
        if self._current_track:
            self.previous = self._current_track
        self._current_track = track
        await self.play(track)

    async def skip(self):
        """Пропускает текущий трек"""
        if not self.queue.is_empty:
            next_track = self.queue.get()
            await self.play_track(next_track)
            # Обновляем зарегистрированное сообщение, если оно есть
            if self.guild and self.guild.id in now_playing_updater.active_messages:
                info = now_playing_updater.active_messages[self.guild.id]
                message = info['message']
                requester = info['requester']
                embed = create_now_playing_embed(next_track, self, requester)
                try:
                    await message.edit(embed=embed)
                    print(f"[DEBUG] Updated embed for guild {self.guild.id} after skip")
                except Exception as e:
                    print(f"[DEBUG] Failed to update embed after skip: {e}")
                    now_playing_updater.unregister_message(self.guild.id)
        else:
            self.previous = self._current_track
            self._current_track = None
            await self.stop()
            if self.guild:
                now_playing_updater.unregister_message(self.guild.id)
                print(f"[DEBUG] Cleared embed for guild {self.guild.id} after queue end")

    async def play_previous(self):
        """Воспроизводит предыдущий трек"""
        if self.previous:
            current = self._current_track
            await self.play_track(self.previous)
            self.previous = current
            
            # Обновляем зарегистрированное сообщение, если оно есть
            if self.guild and self.guild.id in now_playing_updater.active_messages:
                info = now_playing_updater.active_messages[self.guild.id]
                message = info['message']
                requester = info['requester']
                embed = create_now_playing_embed(self._current_track, self, requester)
                try:
                    await message.edit(embed=embed)
                    print(f"[DEBUG] Updated embed for guild {self.guild.id} after play_previous")
                except Exception as e:
                    print(f"[DEBUG] Failed to update embed after play_previous: {e}")
                    now_playing_updater.unregister_message(self.guild.id)
            
            print(f"[DEBUG] Played previous track: {self._current_track.title if self._current_track else 'None'}")
            return True
        return False

    async def do_next(self):
        """Воспроизводит следующий трек из очереди, если он есть"""
        if not self.queue.is_empty:
            next_track = self.queue.get()
            await self.play_track(next_track)
        else:
            await self.stop()

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_unload(self):
        """Очистка при выгрузке модуля"""
        cleanup_updater()

        # Автодополнение для поиска треков
    async def track_autocomplete(self, interaction: discord.Interaction, current: str):
        if len(current) < 2:
            return []

        suggestions = []

        # SoundCloud поиск по названию
        try:
            tracks = await wavelink.Playable.search(current, source=wavelink.TrackSource.SoundCloud)
            if tracks:
                for track in tracks[:8]:
                    display_name = f"{track.author} - {track.title}"
                    if len(display_name) > 90:
                        display_name = display_name[:87] + "..."
                    suggestions.append(app_commands.Choice(
                        name=display_name,
                        value=track.uri
                    ))
                    if len(suggestions) >= 20:
                        break
        except Exception as e:
            print(f"[DEBUG] Autocomplete error for SoundCloud: {e}")

        # Spotify — ищем только если введённая строка является ссылкой
        if "open.spotify.com" in current:
            try:
                tracks = await wavelink.Playable.search(current)
                if tracks:
                    track = tracks[0]
                    display_name = f"{track.author} - {track.title}"
                    if len(display_name) > 90:
                        display_name = display_name[:87] + "..."
                    suggestions.append(app_commands.Choice(
                        name=display_name,
                        value=track.uri
                    ))
            except Exception as e:
                print(f"[DEBUG] Spotify link error: {e}")

        return suggestions[:25]

    @app_commands.command(name="play", description="🎵 Искать и воспроизводить музыку")
    @app_commands.describe(поиск="Название трека, исполнитель или URL")
    @app_commands.autocomplete(поиск=track_autocomplete)
    async def play(self, interaction: discord.Interaction, поиск: str):
        # Проверка голосового канала
        if not interaction.user.voice or not interaction.user.voice.channel:
            embed = create_error_embed("Голосовой канал", "Вы не в голосовом канале!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Подключение к голосовому каналу
        vc = interaction.guild.voice_client
        if not vc:
            try:
                vc = await interaction.user.voice.channel.connect(cls=HarmonyPlayer)
            except discord.ClientException:
                embed = create_error_embed("Подключение", "Не удалось подключиться к голосовому каналу!")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

        # Отложенный ответ для использования followup
        await interaction.response.defer(ephemeral=True)

        try:
            results = await self._search_tracks(поиск)

            if not results:
                embed = create_error_embed("Поиск", f"Ничего не найдено по запросу: `{поиск}`")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if isinstance(results, wavelink.Playlist):
                for track in results.tracks:
                    vc.queue.put(track)

                embed = discord.Embed(
                    title=f"{Emojis.ADD} Плейлист добавлен",
                    description=f"**{results.name}** — {len(results.tracks)} треков",
                    color=Colors.SUCCESS
                )
                await interaction.followup.send(embed=embed, ephemeral=True)

                if not vc.playing:
                    await vc.do_next()
                    await self._start_now_playing_update(interaction.channel, vc, interaction.user)

            else:
                track = results[0]

                if vc.playing:
                    vc.queue.put(track)
                    embed = discord.Embed(
                        description=f"Был добавлен в очередь трек **\"{track.author} — {track.title}\"**",
                        color=Colors.SUCCESS
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await vc.play_track(track)
                    embed = discord.Embed(
                        description=f"Был добавлен в очередь трек **\"{track.author} — {track.title}\"**",
                        color=Colors.SUCCESS
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    await self._start_now_playing_update(interaction.channel, vc, interaction.user)

        except Exception as e:
            print(f"[DEBUG] Play command error: {e}")
            embed = create_error_embed("Ошибка", "Произошла ошибка при обработке запроса!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
    async def _search_tracks(self, query: str):
        """Поиск треков по всем источникам"""
        
        sources = [
            ("SoundCloud", wavelink.TrackSource.SoundCloud),
            ("YouTube", wavelink.TrackSource.YouTube),
            ("YouTube Music", wavelink.TrackSource.YouTubeMusic)
        ]
        
        for source_name, source in sources:
            try:
                result = await wavelink.Playable.search(query, source=source)
                print(f"[DEBUG] {source_name}: {len(result) if result else 0} tracks")
                if result:
                    return result
            except Exception as e:
                print(f"[DEBUG] {source_name} search error: {e}")
                continue
        
        print(f"[DEBUG] No results found for: {query}")
        return None

    async def _start_now_playing_update(self, channel, vc, user):
        """Запуск автообновляющегося embed для текущего трека"""
        try:
            # Отправляем сообщение с автообновлением
            message = await send_now_playing_message(channel, vc.current, vc, user)
            
            # Регистрируем сообщение для автообновления
            if message and vc.guild and vc.current:
                await now_playing_updater.register_message(vc.guild.id, message, vc, vc.current, user)
                
        except Exception as e:
            print(f"[DEBUG] Error starting now playing update: {e}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Обработка окончания трека"""
        if payload.player.guild and not payload.player.queue:
            now_playing_updater.unregister_message(payload.player.guild.id)

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Обработка начала нового трека"""
        if payload.player.guild and payload.player.current:
            try:
                guild_id = payload.player.guild.id
                print(f"[DEBUG] Track started: {payload.player.current.title} in guild {guild_id}")
                
                # Проверяем, есть ли зарегистрированное сообщение
                if guild_id in now_playing_updater.active_messages:
                    info = now_playing_updater.active_messages[guild_id]
                    message = info['message']
                    requester = info['requester']
                    embed = create_now_playing_embed(
                        payload.player.current,
                        payload.player,
                        requester
                    )
                    try:
                        await message.edit(embed=embed)
                        print(f"[DEBUG] Updated existing embed for guild {guild_id}")
                    except discord.NotFound:
                        print(f"[DEBUG] Message not found for guild {guild_id}, creating new")
                        now_playing_updater.unregister_message(guild_id)
                        await self._create_new_message(payload, guild_id)
                    except discord.Forbidden:
                        print(f"[DEBUG] No permission to edit message in guild {guild_id}")
                        now_playing_updater.unregister_message(guild_id)
                else:
                    await self._create_new_message(payload, guild_id)
                    
            except Exception as e:
                print(f"[DEBUG] Error in track start handler: {e}")

    async def _create_new_message(self, payload: wavelink.TrackStartEventPayload, guild_id: int):
        """Создание нового сообщения для трека"""
        try:
            channel = payload.player.guild.system_channel
            if not channel:
                for ch in payload.player.guild.text_channels:
                    if ch.permissions_for(payload.player.guild.me).send_messages:
                        channel = ch
                        break
            
            if channel:
                message = await send_now_playing_message(
                    channel,
                    payload.player.current,
                    payload.player,
                    payload.player.guild.me  # Можно заменить на реального запрашивающего
                )
                if message:
                    await now_playing_updater.register_message(
                        guild_id,
                        message,
                        payload.player,
                        payload.player.current,
                        payload.player.guild.me
                    )
                    print(f"[DEBUG] Created new embed for guild {guild_id}")
        except Exception as e:
            print(f"[DEBUG] Error creating new message: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
