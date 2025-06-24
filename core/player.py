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
    NONE = 0
    TRACK = 1
    QUEUE = 2

@dataclass
class PlayerState:
    oop_mode: LoopMode = LoopMode.NONE
    autoplay: bool = True
    bass_boost: bool = False
    nightcore: bool = False
    vaporwave: bool = False
    volume_before_effects: int = 75

class HarmonyPlayer(wavelink.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = wavelink.Queue()
        self.history = wavelink.Queue()
        self.state = PlayerState()
        self.controller_message: Optional[discord.Message] = None
        self.idle_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger("HarmonyPlayer")

    async def play_track(self, track: wavelink.Playable, **kwargs):
        if not self.guild:
            self.logger.debug("[DEBUG] Пропущен play_track — self.guild is None")
            return

        if self.current:
            self.history.put(self.current)

        try:
            await self.play(track, **kwargs)
        except AssertionError:
            self.logger.error("❌ Ошибка: попытка воспроизведения без guild")
            return

        if self.controller_message:
            from ui.views import MusicPlayerView
            from ui.embeds import create_now_playing_embed

            embed = create_now_playing_embed(track, self)
            view = MusicPlayerView(self)

            try:
                await self.controller_message.edit(embed=embed, view=view)
            except discord.NotFound:
                self.controller_message = None

    async def do_next(self):
        if not self.guild:
            self.logger.debug("[DEBUG] Пропущен do_next — self.guild is None")
            return

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
        if not self.guild or not self.current:
            self.logger.debug("[DEBUG] _get_autoplay_track пропущен — нет текущего трека или сервера")
            return None

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
            self.logger.error(f"❌ Ошибка в _get_autoplay_track: {e}")

        return None

    def _start_idle_timer(self):
        if self.idle_task:
            self.idle_task.cancel()

        self.idle_task = asyncio.create_task(self._idle_disconnect())

    async def _idle_disconnect(self):
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
        filters = wavelink.Filters()

        if bass is not None:
            self.state.bass_boost = bass
        if nightcore is not None:
            self.state.nightcore = nightcore
        if vaporwave is not None:
            self.state.vaporwave = vaporwave

        if self.state.bass_boost:
            filters.equalizer.set_gain(0, 0.6)
            filters.equalizer.set_gain(1, 0.7)
            filters.equalizer.set_gain(2, 0.8)

        if self.state.nightcore:
            filters.timescale.set(speed=1.2, pitch=1.2)

        if self.state.vaporwave:
            filters.timescale.set(speed=0.8, pitch=0.8)
            filters.equalizer.set_gain(0, -0.2)

        await self.set_filters(filters)
