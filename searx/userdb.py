# SPDX-License-Identifier: AGPL-3.0-or-later
"""SQLite database for per-user search history and favorites.

Follows the :py:obj:`searx.sqlitedb.SQLiteAppl` pattern used by the rest of
SearXNG so no extra ORM dependency is needed.
"""

import datetime
import sqlite3

from searx import logger, get_setting
from searx.sqlitedb import SQLiteAppl

logger = logger.getChild("userdb")

_DB_INSTANCE: "UserDB | None" = None


def get_userdb() -> "UserDB":
    """Return the singleton :py:obj:`UserDB` instance, creating it on first call."""
    global _DB_INSTANCE
    if _DB_INSTANCE is None:
        db_path = get_setting("oidc.userdb_path", "/tmp/searxng_users.db")
        _DB_INSTANCE = UserDB(str(db_path))
        conn = _DB_INSTANCE.connect()
        conn.close()
    return _DB_INSTANCE


class UserDB(SQLiteAppl):
    """Stores search history and favorites, keyed by the OIDC ``sub`` claim."""

    DB_SCHEMA: int = 1

    DDL_CREATE_TABLES: dict[str, str] = {
        "search_history": (
            "CREATE TABLE IF NOT EXISTS search_history ("
            "  id          INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  user_id     TEXT    NOT NULL,"
            "  query       TEXT    NOT NULL,"
            "  searched_at INTEGER DEFAULT (strftime('%s', 'now'))"
            ")"
        ),
        "search_history_idx": (
            "CREATE INDEX IF NOT EXISTS idx_history_user"
            " ON search_history(user_id, searched_at DESC)"
        ),
        "favorites": (
            "CREATE TABLE IF NOT EXISTS favorites ("
            "  id       INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  user_id  TEXT    NOT NULL,"
            "  url      TEXT    NOT NULL,"
            "  title    TEXT    NOT NULL,"
            "  saved_at INTEGER DEFAULT (strftime('%s', 'now')),"
            "  UNIQUE(user_id, url)"
            ")"
        ),
        "favorites_idx": (
            "CREATE INDEX IF NOT EXISTS idx_favorites_user"
            " ON favorites(user_id, saved_at DESC)"
        ),
    }

    # --- Search History -------------------------------------------------------

    def add_history(self, user_id: str, query: str) -> None:
        with self.DB:
            self.DB.execute(
                "DELETE FROM search_history WHERE user_id = ? AND query = ?",
                (user_id, query),
            )
            self.DB.execute(
                "INSERT INTO search_history (user_id, query) VALUES (?, ?)",
                (user_id, query),
            )

    def get_history(self, user_id: str, limit: int = 50) -> list[dict]:
        rows = self.DB.execute(
            "SELECT id, query, searched_at FROM search_history"
            " WHERE user_id = ? ORDER BY searched_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [
            {
                "id": r[0],
                "query": r[1],
                "searched_at": datetime.datetime.fromtimestamp(r[2]).strftime("%d.%m.%Y %H:%M"),
            }
            for r in rows
        ]

    def clear_history(self, user_id: str) -> None:
        with self.DB:
            self.DB.execute("DELETE FROM search_history WHERE user_id = ?", (user_id,))

    # --- Favorites ------------------------------------------------------------

    def add_favorite(self, user_id: str, url: str, title: str) -> None:
        with self.DB:
            self.DB.execute(
                "INSERT OR IGNORE INTO favorites (user_id, url, title) VALUES (?, ?, ?)",
                (user_id, url, title),
            )

    def get_favorites(self, user_id: str) -> list[dict]:
        rows = self.DB.execute(
            "SELECT id, url, title, saved_at FROM favorites"
            " WHERE user_id = ? ORDER BY saved_at DESC",
            (user_id,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "url": r[1],
                "title": r[2],
                "saved_at": datetime.datetime.fromtimestamp(r[3]).strftime("%d.%m.%Y %H:%M"),
            }
            for r in rows
        ]

    def remove_favorite(self, user_id: str, fav_id: int) -> None:
        with self.DB:
            self.DB.execute(
                "DELETE FROM favorites WHERE id = ? AND user_id = ?",
                (fav_id, user_id),
            )
