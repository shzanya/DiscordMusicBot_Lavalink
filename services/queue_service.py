"""
Queue management service for music bot.
Handles queue persistence in MongoDB.
"""

import logging
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
import discord
import wavelink

from services import mongo_service
from core.player import LoopMode

if TYPE_CHECKING:
    from commands.music.playback import HarmonyPlayer

logger = logging.getLogger(__name__)


class QueueTrack:
    """Represents a track in the queue with metadata."""

    def __init__(
        self,
        track: wavelink.Playable,
        requester: Optional[discord.Member] = None,
        added_at: Optional[datetime] = None,
    ):
        self.track = track
        self.requester = requester
        self.added_at = added_at or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "track": self.track.encoded,
            "title": self.track.title,
            "author": getattr(self.track, "author", "Unknown"),
            "uri": getattr(self.track, "uri", ""),
            "length": getattr(self.track, "length", 0),
            "requester_id": self.requester.id if self.requester else None,
            "requester_name": self.requester.display_name
            if self.requester
            else "Unknown",
            "added_at": self.added_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueTrack":
        """Create from dictionary."""
        # Проверяем, что data является словарем
        if not isinstance(data, dict):
            logger.error(f"Invalid track data type: {type(data)}")
            raise ValueError(f"Expected dict, got {type(data)}")

        # Проверяем наличие обязательных полей
        if "track" not in data:
            logger.error("Missing 'track' field in track data")
            raise ValueError("Missing 'track' field")

        # Recreate track from encoded data
        track = wavelink.Playable(data["track"])
        track.title = data.get("title", "Unknown")
        track.author = data.get("author", "Unknown")
        track.uri = data.get("uri", "")
        track.length = data.get("length", 0)

        return cls(
            track=track,
            requester=None,  # Will be set when loading
            added_at=datetime.fromisoformat(data["added_at"])
            if data.get("added_at")
            else datetime.utcnow(),
        )


class QueueManager:
    """Manages queue persistence in MongoDB."""

    def __init__(self):
        self.collection_name = "queues"

    async def get_queue(self, guild_id: int) -> Dict[str, Any]:
        """Get queue for guild from database."""
        try:
            collection = mongo_service.get_collection(self.collection_name)
            doc = await collection.find_one({"guild_id": str(guild_id)})

            if doc:
                return doc
            else:
                # Create new queue document
                return await self.create_queue(guild_id)

        except Exception as e:
            logger.error(f"Error getting queue for guild {guild_id}: {e}")
            return await self.create_queue(guild_id)

    async def create_queue(self, guild_id: int) -> Dict[str, Any]:
        """Create new queue document for guild."""
        try:
            collection = mongo_service.get_collection(self.collection_name)

            queue_doc = {
                "guild_id": str(guild_id),
                "voice_channel_id": "0",
                "text_channel_id": "0",
                "message_id": "0",
                "volume": 100,
                "loop_mode": "none",
                "filter": "none",
                "tracks": [],
                "current_index": -1,
                "history": [],
                "is_playing": False,
                "is_paused": False,
                "paused_at": 0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }

            result = await collection.insert_one(queue_doc)
            queue_doc["_id"] = result.inserted_id

            logger.info(f"Created new queue for guild {guild_id}")
            return queue_doc

        except Exception as e:
            logger.error(f"Error creating queue for guild {guild_id}: {e}")
            return {}

    async def save_queue(self, guild_id: int, player: "HarmonyPlayer") -> bool:
        """Save current queue state to database."""
        try:
            collection = mongo_service.get_collection(self.collection_name)

            # Convert tracks to serializable format
            tracks = []
            for track in player.playlist:
                queue_track = QueueTrack(
                    track=track, requester=getattr(track, "requester", None)
                )
                tracks.append(queue_track.to_dict())

            # Convert history
            history = []
            for track in player.history:
                queue_track = QueueTrack(
                    track=track, requester=getattr(track, "requester", None)
                )
                history.append(queue_track.to_dict())

            # Prepare update document
            update_doc = {
                "voice_channel_id": str(player.channel.id) if player.channel else "0",
                "text_channel_id": str(player.text_channel.id)
                if player.text_channel
                else "0",
                "message_id": str(player.now_playing_message.id)
                if player.now_playing_message
                else "0",
                "volume": getattr(player, "volume", 100),
                "loop_mode": player.state.loop_mode.value
                if player.state.loop_mode
                else "none",
                "filter": "none",  # TODO: Add filter support
                "tracks": tracks,
                "current_index": player.current_index,
                "history": history,
                "is_playing": not getattr(player, "paused", False),
                "is_paused": getattr(player, "paused", False),
                "paused_at": getattr(player, "paused_at", 0),
                "updated_at": datetime.utcnow().isoformat(),
            }

            await collection.update_one(
                {"guild_id": str(guild_id)}, {"$set": update_doc}, upsert=True
            )

            logger.debug(f"Saved queue for guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving queue for guild {guild_id}: {e}")
            return False

    async def load_queue(self, guild_id: int, player: "HarmonyPlayer") -> bool:
        """Load queue from database into player."""
        try:
            queue_doc = await self.get_queue(guild_id)

            if not queue_doc or not queue_doc.get("tracks"):
                logger.info(f"No saved queue found for guild {guild_id}")
                return False

            # Load tracks
            tracks = []
            for track_data in queue_doc["tracks"]:
                try:
                    # Проверяем, что track_data является словарем
                    if not isinstance(track_data, dict):
                        logger.warning(
                            f"Invalid track data type: {type(track_data)}, skipping"
                        )
                        continue

                    queue_track = QueueTrack.from_dict(track_data)
                    tracks.append(queue_track.track)
                except Exception as e:
                    logger.debug(f"Failed to load track: {e}")
                    continue

            if not tracks:
                logger.info(
                    f"No valid tracks found in saved queue for guild {guild_id}"
                )
                return False

            # Load into player
            player.playlist = tracks
            player.current_index = queue_doc.get("current_index", 0)

            # Load history
            history = []
            for track_data in queue_doc.get("history", []):
                try:
                    queue_track = QueueTrack.from_dict(track_data)
                    history.append(queue_track.track)
                except Exception as e:
                    logger.warning(f"Failed to load history track: {e}")
                    continue

            player._history = history

            # Load other settings
            if queue_doc.get("volume"):
                player.volume = queue_doc["volume"]

            if queue_doc.get("loop_mode"):
                loop_mode = queue_doc["loop_mode"]
                if loop_mode == "track":
                    player.state.loop_mode = LoopMode.TRACK
                elif loop_mode == "queue":
                    player.state.loop_mode = LoopMode.QUEUE
                else:
                    player.state.loop_mode = LoopMode.NONE

            logger.info(
                f"Loaded {len(tracks)} tracks from saved queue for guild {guild_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error loading queue for guild {guild_id}: {e}")
            return False

    async def clear_queue(self, guild_id: int) -> bool:
        """Clear queue for guild."""
        try:
            collection = mongo_service.get_collection(self.collection_name)

            await collection.update_one(
                {"guild_id": str(guild_id)},
                {
                    "$set": {
                        "tracks": [],
                        "current_index": -1,
                        "history": [],
                        "is_playing": False,
                        "is_paused": False,
                        "paused_at": 0,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                },
            )

            logger.info(f"Cleared queue for guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error clearing queue for guild {guild_id}: {e}")
            return False

    async def delete_queue(self, guild_id: int) -> bool:
        """Delete queue document for guild."""
        try:
            collection = mongo_service.get_collection(self.collection_name)
            await collection.delete_one({"guild_id": str(guild_id)})

            logger.info(f"Deleted queue for guild {guild_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting queue for guild {guild_id}: {e}")
            return False


# Global queue manager instance
queue_manager = QueueManager()
