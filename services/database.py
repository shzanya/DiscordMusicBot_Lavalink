import aiosqlite
import json
import uuid
import logging
from typing import List, Optional
from dataclasses import dataclass
from config.settings import Settings

@dataclass
class GuildData:
    id: int
    name: str
    prefix: str
    dj_role: Optional[int]
    restrictions: dict

@dataclass
class FavoriteTrack:
    id: int
    user_id: int
    title: str
    uri: str

@dataclass
class Playlist:
    id: int
    user_id: int
    name: str
    tracks: List[dict]

class DatabaseService:
    """💾 Сервис работы с базой данных SQLite"""

    def __init__(self):
        self.db_path = Settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
        self.logger = logging.getLogger("DatabaseService")

    async def initialize(self):
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA foreign_keys = ON")
                await self._create_tables(db)
                await db.commit()
            self.logger.info("✅ База данных SQLite инициализирована")
        except Exception as e:
            self.logger.error(f"❌ Ошибка инициализации БД: {e}")
            raise

    async def _create_tables(self, db):
        await db.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                prefix TEXT DEFAULT '♪',
                dj_role INTEGER,
                restrictions TEXT DEFAULT '{}'
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                uri TEXT NOT NULL
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER,
                title TEXT NOT NULL,
                uri TEXT NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
            )
        ''')

        await db.execute('''
            CREATE TABLE IF NOT EXISTS shared_playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER,
                share_id TEXT UNIQUE,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
            )
        ''')

    async def create_guild(self, guild_id: int, guild_name: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO guilds (id, name, prefix)
                VALUES (?, ?, ?)
            ''', (guild_id, guild_name, Settings.COMMAND_PREFIX))
            await db.commit()

    async def get_guild(self, guild_id: int) -> Optional[GuildData]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM guilds WHERE id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return GuildData(
                        id=row["id"],
                        name=row["name"],
                        prefix=row["prefix"],
                        dj_role=row["dj_role"],
                        restrictions=json.loads(row["restrictions"])
                    )
        return None

    async def update_guild_prefix(self, guild_id: int, prefix: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE guilds SET prefix = ? WHERE id = ?', (prefix, guild_id))
            await db.commit()

    async def update_guild_dj_role(self, guild_id: int, role_id: Optional[int]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('UPDATE guilds SET dj_role = ? WHERE id = ?', (role_id, guild_id))
            await db.commit()

    async def set_command_restriction(self, guild_id: int, command: str, role_id: Optional[int]):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT restrictions FROM guilds WHERE id = ?', (guild_id,)) as cursor:
                row = await cursor.fetchone()
                restrictions = json.loads(row["restrictions"]) if row else {}
                restrictions[command] = str(role_id) if role_id else None
                await db.execute(
                    'UPDATE guilds SET restrictions = ? WHERE id = ?',
                    (json.dumps(restrictions), guild_id)
                )
                await db.commit()

    async def add_favorite(self, user_id: int, title: str, uri: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO favorites (user_id, title, uri) VALUES (?, ?, ?)',
                (user_id, title, uri)
            )
            await db.commit()

    async def get_favorites(self, user_id: int) -> List[FavoriteTrack]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM favorites WHERE user_id = ? ORDER BY id', (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [FavoriteTrack(**dict(row)) for row in rows]

    async def remove_favorite(self, user_id: int, favorite_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM favorites WHERE id = ? AND user_id = ?', (favorite_id, user_id))
            await db.commit()

    async def create_playlist(self, user_id: int, name: str) -> Playlist:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('INSERT INTO playlists (user_id, name) VALUES (?, ?)', (user_id, name))
            async with db.execute('SELECT last_insert_rowid()') as cursor:
                row = await cursor.fetchone()
                playlist_id = row[0]
            await db.commit()
            return Playlist(id=playlist_id, user_id=user_id, name=name, tracks=[])

    async def get_playlist(self, user_id: int, name: str) -> Optional[Playlist]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT p.id, p.user_id, p.name,
                       GROUP_CONCAT('{"title":"' || REPLACE(pt.title, '"', '') || '","uri":"' || REPLACE(pt.uri, '"', '') || '"}')
                       AS tracks
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
                WHERE p.user_id = ? AND p.name = ?
                GROUP BY p.id
            ''', (user_id, name)) as cursor:
                row = await cursor.fetchone()
                if row:
                    tracks = json.loads(f"[{row['tracks']}]" if row['tracks'] else "[]")
                    return Playlist(id=row["id"], user_id=row["user_id"], name=row["name"], tracks=tracks)
        return None

    async def add_to_playlist(self, playlist_id: int, title: str, uri: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO playlist_tracks (playlist_id, title, uri) VALUES (?, ?, ?)',
                (playlist_id, title, uri)
            )
            await db.commit()

    async def get_user_playlists(self, user_id: int) -> List[Playlist]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT p.id, p.user_id, p.name,
                       GROUP_CONCAT('{"title":"' || REPLACE(pt.title, '"', '') || '","uri":"' || REPLACE(pt.uri, '"', '') || '"}')
                       AS tracks
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
                WHERE p.user_id = ?
                GROUP BY p.id
                ORDER BY p.id
            ''', (user_id,)) as cursor:
                rows = await cursor.fetchall()
                return [
                    Playlist(
                        id=row["id"],
                        user_id=row["user_id"],
                        name=row["name"],
                        tracks=json.loads(f"[{row['tracks']}]" if row["tracks"] else "[]")
                    )
                    for row in rows
                ]

    async def create_share_link(self, playlist_id: int) -> str:
        share_id = str(uuid.uuid4())
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT INTO shared_playlists (playlist_id, share_id) VALUES (?, ?)',
                (playlist_id, share_id)
            )
            await db.commit()
        return share_id

    async def get_shared_playlist(self, share_id: str) -> Optional[Playlist]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT p.id, p.user_id, p.name,
                       GROUP_CONCAT('{"title":"' || REPLACE(pt.title, '"', '') || '","uri":"' || REPLACE(pt.uri, '"', '') || '"}')
                       AS tracks
                FROM playlists p
                LEFT JOIN playlist_tracks pt ON p.id = pt.playlist_id
                JOIN shared_playlists sp ON p.id = sp.playlist_id
                WHERE sp.share_id = ?
                GROUP BY p.id
            ''', (share_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    tracks = json.loads(f"[{row['tracks']}]" if row['tracks'] else "[]")
                    return Playlist(id=row["id"], user_id=row["user_id"], name=row["name"], tracks=tracks)
        return None

    async def import_playlist(self, user_id: int, playlist: Playlist) -> Playlist:
        new_playlist = await self.create_playlist(user_id, f"Импорт: {playlist.name}")
        for track in playlist.tracks:
            await self.add_to_playlist(new_playlist.id, track["title"], track["uri"])
        return new_playlist
