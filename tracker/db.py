"""SQLite queue - tracks every reel through the pipeline.

Schema matches the PRD with one addition: retry_count for failed items.
Uses BEGIN IMMEDIATE to prevent race conditions on concurrent access.
"""

import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class QueueDB:
    """Manages the SQLite queue table for reel processing."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queue (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ig_shortcode    TEXT    NOT NULL UNIQUE,
                raw_path        TEXT,
                processed_path  TEXT,
                ig_caption      TEXT,
                yt_title        TEXT,
                yt_description  TEXT,
                yt_tags         TEXT,
                yt_title_ch2    TEXT,
                yt_description_ch2 TEXT,
                yt_tags_ch2     TEXT,
                yt_video_id     TEXT,
                status          TEXT    NOT NULL DEFAULT 'pending',
                retry_count     INTEGER NOT NULL DEFAULT 0,
                error_msg       TEXT,
                created_at      TEXT    NOT NULL,
                posted_at       TEXT
            );
        """)
        # Migration: add ch2 columns for existing databases
        existing_cols = {col[1] for col in conn.execute("PRAGMA table_info(queue);")}
        migration_cols = {
            "yt_title_ch2": "TEXT",
            "yt_description_ch2": "TEXT",
            "yt_tags_ch2": "TEXT",
            "yt_video_id_ch2": "TEXT",
        }
        for col_name, col_type in migration_cols.items():
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE queue ADD COLUMN {col_name} {col_type};")
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------
    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a write query with IMMEDIATE transaction."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE;")
        try:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(sql, params).fetchone()
        conn.close()
        return row

    def _fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return rows

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_reel(self, shortcode: str, ig_caption: str = "") -> int | None:
        """Insert a new reel. Returns the row ID, or None if duplicate."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN IMMEDIATE;")
        try:
            cur = conn.execute(
                "INSERT INTO queue (ig_shortcode, ig_caption, status, created_at) VALUES (?, ?, 'downloaded', ?);",
                (shortcode, ig_caption, now),
            )
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_next_by_status(self, status: str) -> Optional[dict]:
        """Get the oldest reel with a given status."""
        row = self._fetchone(
            "SELECT * FROM queue WHERE status = ? ORDER BY id ASC LIMIT 1;", (status,)
        )
        return dict(row) if row else None

    def update_status(self, reel_id: int, status: str, **kwargs) -> None:
        """Update a reel's status and optional metadata."""
        fields = ["status = ?"]
        params: list = [status]
        set_posted_at = status in ("posted", "failed")

        col_map = {
            "raw_path": "raw_path", "processed_path": "processed_path",
            "yt_title": "yt_title", "yt_description": "yt_description",
            "yt_tags": "yt_tags", "yt_title_ch2": "yt_title_ch2",
            "yt_description_ch2": "yt_description_ch2", "yt_tags_ch2": "yt_tags_ch2",
            "yt_video_id": "yt_video_id", "yt_video_id_ch2": "yt_video_id_ch2",
            "error_msg": "error_msg", "retry_count": "retry_count",
        }
        for key, col in col_map.items():
            val = kwargs.get(key)
            if val is not None:
                fields.append(f"{col} = ?")
                params.append(val)

        if set_posted_at:
            fields.append("posted_at = ?")
            params.append(datetime.now(timezone.utc).isoformat())

        params.append(reel_id)
        self._execute(
            f"UPDATE queue SET {', '.join(fields)} WHERE id = ?;", tuple(params)
        )

    def count_by_status(self, status: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM queue WHERE status = ?;", (status,)
        )
        return row["cnt"] if row else 0

    def count_total(self) -> int:
        row = self._fetchone("SELECT COUNT(*) AS cnt FROM queue;")
        return row["cnt"] if row else 0

    def get_recent(self, limit: int = 10) -> list[dict]:
        rows = self._fetchall(
            "SELECT * FROM queue ORDER BY id DESC LIMIT ?;", (limit,)
        )
        return [dict(r) for r in rows]

    def clear_all(self) -> None:
        self._execute("DELETE FROM queue;")

    def shortcode_exists(self, shortcode: str) -> bool:
        row = self._fetchone(
            "SELECT 1 FROM queue WHERE ig_shortcode = ?;", (shortcode,)
        )
        return row is not None
