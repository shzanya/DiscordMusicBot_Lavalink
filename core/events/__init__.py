"""
Core events module for music bot.
Handles track start, end, and other player events.
"""

from .track_events import TrackStartEvent, TrackEndEvent

__all__ = ["TrackStartEvent", "TrackEndEvent"]
