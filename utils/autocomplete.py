"""
Advanced autocomplete utilities for music bot.
Provides intelligent search suggestions with caching and rate limiting.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple
import discord
from discord import app_commands
import wavelink

logger = logging.getLogger(__name__)


class AutocompleteManager:
    """Manages autocomplete functionality with caching and rate limiting."""

    def __init__(self):
        self._cache: Dict[str, Tuple[float, List[app_commands.Choice[str]]]] = {}
        self._cache_lock = asyncio.Lock()
        self._max_cache_size = 100
        self._cache_ttl = 30  # seconds
        self._search_timeout = 0.5  # seconds
        self._max_results = 15
        self._min_query_length = 2
        self._max_query_length = 50

    async def track_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """Provide track autocomplete suggestions."""
        query = (current or "").strip()

        # Validate query length
        if len(query) < self._min_query_length:
            return []

        # Limit query length
        query = query[: self._max_query_length]

        # Check cache first
        cached_result = await self._get_cached_result(query)
        if cached_result:
            return cached_result

        # Perform search
        try:
            choices = await self._search_tracks(query)

            # Cache results
            await self._cache_result(query, choices)

            return choices

        except Exception as e:
            logger.error(f"Autocomplete search failed: {e}")
            return []

    async def _get_cached_result(
        self, query: str
    ) -> Optional[List[app_commands.Choice[str]]]:
        """Get cached autocomplete result."""
        async with self._cache_lock:
            if query in self._cache:
                cached_time, cached_choices = self._cache[query]
                if time.time() - cached_time < self._cache_ttl:
                    return cached_choices
        return None

    async def _cache_result(
        self, query: str, choices: List[app_commands.Choice[str]]
    ) -> None:
        """Cache autocomplete result."""
        async with self._cache_lock:
            self._cache[query] = (time.time(), choices)

            # Clean up old entries if cache is too large
            if len(self._cache) > self._max_cache_size:
                self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """Remove oldest cache entries."""
        if len(self._cache) <= self._max_cache_size:
            return

        # Sort by timestamp and remove oldest
        sorted_items = sorted(self._cache.items(), key=lambda x: x[1][0])

        # Remove oldest entries
        items_to_remove = len(self._cache) - self._max_cache_size
        for i in range(items_to_remove):
            del self._cache[sorted_items[i][0]]

    async def _search_tracks(self, query: str) -> List[app_commands.Choice[str]]:
        """Search for tracks and return formatted choices."""
        try:
            # Determine search source
            is_url = self._is_url(query)
            source = None if is_url else wavelink.TrackSource.SoundCloud

            # Perform search with timeout
            results = await asyncio.wait_for(
                wavelink.Playable.search(query, source=source),
                timeout=self._search_timeout,
            )

            if not results:
                return []

            # Format results
            choices = []
            for track in results[: self._max_results]:
                try:
                    choice = self._format_track_choice(track)
                    if choice:
                        choices.append(choice)
                except Exception as e:
                    logger.debug(f"Failed to format track choice: {e}")
                    continue

            return choices

        except asyncio.TimeoutError:
            logger.warning(f"Search timeout for query: {query}")
            return []
        except Exception as e:
            logger.error(f"Search error for query '{query}': {e}")
            return []

    def _is_url(self, query: str) -> bool:
        """Check if query is a URL."""
        return query.startswith(("http://", "https://"))

    def _format_track_choice(
        self, track: wavelink.Playable
    ) -> Optional[app_commands.Choice[str]]:
        """Format track into autocomplete choice."""
        try:
            # Extract track information
            title = getattr(track, "title", "Unknown") or "Unknown"
            author = getattr(track, "author", "Unknown") or "Unknown"
            uri = getattr(track, "uri", "") or getattr(track, "identifier", "")

            if not uri:
                return None

            # Create display name
            display = f"{author} – {title}"
            if len(display) > 97:  # Leave room for "..."
                display = display[:94] + "..."

            # Limit URI length to 100 characters (Discord limit)
            if len(uri) > 100:
                # Try to keep the most important part
                if len(title) > 50:
                    title = title[:47] + "..."
                if len(author) > 30:
                    author = author[:27] + "..."
                display = f"{author} – {title}"
                # If still too long, truncate
                if len(display) > 97:
                    display = display[:94] + "..."

            return app_commands.Choice(name=display, value=uri[:100])

        except Exception as e:
            logger.debug(f"Failed to format track: {e}")
            return None

    async def clear_cache(self) -> None:
        """Clear all cached results."""
        async with self._cache_lock:
            self._cache.clear()

    async def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        async with self._cache_lock:
            return {
                "size": len(self._cache),
                "max_size": self._max_cache_size,
                "ttl": self._cache_ttl,
            }


# Global instance
autocomplete_manager = AutocompleteManager()


# Convenience function for backward compatibility
async def track_autocomplete(
    interaction: discord.Interaction, current: str
) -> List[app_commands.Choice[str]]:
    """Track autocomplete function for slash commands."""
    return await autocomplete_manager.track_autocomplete(interaction, current)
