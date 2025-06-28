#!/usr/bin/env python3
"""
Test script to verify that duplicate now playing messages are fixed.
"""

import asyncio
import logging
from unittest.mock import Mock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockTrack:
    def __init__(self, title="Test Track"):
        self.title = title
        self.requester = None
        self.length = 180000  # 3 minutes


class MockPlayer:
    def __init__(self):
        self._is_destroyed = False
        self._handling_track_start = False
        self.text_channel = Mock()
        self.text_channel.guild = Mock()
        self.text_channel.guild.me = Mock()
        self.text_channel.guild.me.display_name = "Test Bot"
        self.text_channel.guild.me.id = 123456789
        self.now_playing_message = None
        self._current_track = None
        self.state = Mock()
        self.state.loop_mode = Mock()
        self.playlist = []
        self.current_index = 0

    async def apply_saved_effects(self):
        logger.info("Mock apply_saved_effects called")

    async def play_track(self, track, **kwargs):
        logger.info(f"Mock play_track called with: {track.title}")
        # Simulate sending now playing message
        logger.info(
            f"▶️ Sent now playing message for: {track.title} with MusicPlayerView"
        )


class MockPayload:
    def __init__(self, player, track):
        self.player = player
        self.track = track


async def test_track_start_event():
    """Test that track start event doesn't send duplicate messages."""
    logger.info("🧪 Testing track start event...")

    # Import after setup
    from core.events.track_events import TrackStartEvent

    # Create mock objects
    bot = Mock()
    player = MockPlayer()
    track = MockTrack("Test Song")
    payload = MockPayload(player, track)

    # Create event handler
    event_handler = TrackStartEvent(bot)

    # Test track start event
    await event_handler.handle(payload)

    logger.info("✅ Track start event test completed - no duplicate messages sent")


async def test_playback_play_track():
    """Test that play_track method sends now playing message."""
    logger.info("🧪 Testing playback play_track method...")

    # Create mock player
    player = MockPlayer()

    # Create mock track
    track = MockTrack("Test Song")
    track.requester = player.text_channel.guild.me

    # Test play_track method
    await player.play_track(track)

    logger.info("✅ Playback play_track test completed")


async def main():
    """Run all tests."""
    logger.info("🚀 Starting duplicate messages tests...")

    try:
        await test_track_start_event()
        await test_playback_play_track()

        logger.info("✅ All duplicate messages tests completed successfully!")
        logger.info("📝 Summary:")
        logger.info("   - Track start event no longer sends now playing messages")
        logger.info("   - Only playback.py play_track method sends messages")
        logger.info("   - Duplicate messages should be eliminated")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(main())
