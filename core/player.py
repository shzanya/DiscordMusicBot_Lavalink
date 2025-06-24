import wavelink
import discord
from enum import Enum
from typing import Optional
from dataclasses import dataclass
import logging
import asyncio

from config.settings import Settings
from config.constants import Colors

class LoopMode(Enum):
    """🔄 Режимы повтора"""
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"

@dataclass
class PlayerState:
    """📊 Состояние плеера"""
    loop_mode: LoopMode = LoopMode.OFF
    autoplay: bool = True
    bass_boost: bool = False
    nightcore: bool = False
    vaporwave: bool = False
    volume_before_effects: int = 75

class HarmonyPlayer(wavelink.Player):
    """🎵 Кастомный плеер с расширенными возможностями"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = wavelink.Queue()
        self.history = wavelink.Queue()
        self.state = PlayerState()
        self.controller_message: Optional[discord.Message] = None
        self.idle_task: Optional[asyncio.Task] = None

    async def play_track(self, track: wavelink.Playable, **kwargs):
        """▶️ Воспроизведение трека с логикой"""
        if self.current:
            self.history.put(self.current)

        await self.play(track, **kwargs)

        # Обновление контроллера
        if self.controller_message:
            from ui.views import MusicControllerView
            from ui.embeds import create_now_playing_embed

            embed = create_now_playing_embed(track, self)
            view = MusicControllerView(self)

            try:
                await self.controller_message.edit(embed=embed, view=view)
            except discord.NotFound:
                self.controller_message = None

    async def do_next(self):
        """⏭️ Переход к следующему треку"""
        if self.state.loop_mode == LoopMode.TRACK and self.current:
            return await self.play_track(self.current)

        if self.state.loop_mode == LoopMode.QUEUE and self.current:
            self.queue.put(self.current)

        if self.queue.is_empty:
            if self.state.autoplay and self.current:
                recommended = await self._get_autoplay_track()
                if recommended:
                    return await self.play_track(recommended)

            self._start_idle_timer()
            return

        next_track = self.queue.get()
        await self.play_track(next_track)

    async def _get_autoplay_track(self) -> Optional[wavelink.Playable]:
        """🎯 Получение рекомендованного трека"""
        try:
            if hasattr(self.current, 'recommended'):
                return await self.current.recommended()

            search_query = f"{self.current.author} similar songs"
            tracks = await wavelink.Playable.search(search_query)

            played_titles = {track.title.lower() for track in self.history}
            for track in tracks:
                if track.title.lower() not in played_titles:
                    return track

        except Exception as e:
            logger = logging.getLogger('HarmonyPlayer')
            logger.error(f"❌ Ошибка автовоспроизведения: {e}")

        return None

    def _start_idle_timer(self):
        """⏰ Запуск таймера бездействия"""
        if self.idle_task:
            self.idle_task.cancel()

        self.idle_task = asyncio.create_task(self._idle_disconnect())

    async def _idle_disconnect(self):
        """🔌 Отключение по таймауту"""
        try:
            await asyncio.sleep(Settings.AUTO_DISCONNECT_TIMEOUT)

            if not self.playing and self.queue.is_empty and self.is_connected():
                await self.disconnect()

                if self.channel:
                    embed = discord.Embed(
                        title="👋 Отключение",
                        description="Отключился из-за бездействия",
                        color=Colors.WARNING
                    )
                    await self.channel.send(embed=embed)

        except asyncio.CancelledError:
            pass

    async def set_effects(self, bass: bool = None, nightcore: bool = None, vaporwave: bool = None):
        """🎚️ Применение аудиоэффектов"""
        filters = wavelink.Filters()

        if bass is not None:
            self.state.bass_boost = bass
        if nightcore is not None:
            self.state.nightcore = nightcore
        if vaporwave is not None:
            self.state.vaporwave = vaporwave

        # Басбуст
        if self.state.bass_boost:
            filters.equalizer.set_gain(0, 0.6)
            filters.equalizer.set_gain(1, 0.7)
            filters.equalizer.set_gain(2, 0.8)

        # Найткор
        if self.state.nightcore:
            filters.timescale.set(speed=1.2, pitch=1.2)

        # Вейпорвейв
        if self.state.vaporwave:
            filters.timescale.set(speed=0.8, pitch=0.8)
            filters.equalizer.set_gain(0, -0.2)

        await self.set_filters(filters)
