"""SQLite queue — tracks every reel through the pipeline.

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
                yt_video_id     TEXT,
                status          TEXT    NOT NULL DEFAULT 'pending',
                retry_count     INTEGER NOT NULL DEFAULT 0,
                error_msg       TEXT,
                created_at      TEXT    NOT NULL,
                posted_at       TEXT
            );
        """)
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
    def add_reel(self, shortcode: str, ig_caption: str = "") -> bool:
        """Insert a new reel. Returns False if shortcode already exists."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._execute(
                "INSERT INTO queue (ig_shortcode, ig_caption, status, created_at) VALUES (?, ?, 'downloaded', ?);",
                (shortcode, ig_caption, now),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_next_pending(self) -> Optional[dict]:
        """Get the oldest downloaded reel ready for processing."""
        row = self._fetchone(
            "SELECT * FROM queue WHERE status = 'downloaded' ORDER BY id ASC LIMIT 1;"
        )
        return dict(row) if row else None

    def get_next_processed(self) -> Optional[dict]:
        """Get the oldest processed reel ready for caption generation."""
        row = self._fetchone(
            "SELECT * FROM queue WHERE status = 'processed' ORDER BY id ASC LIMIT 1;"
        )
        return dict(row) if row else None

    def get_next_caption_ready(self) -> Optional[dict]:
        """Get the oldest caption_ready reel ready for upload."""
        row = self._fetchone(
            "SELECT * FROM queue WHERE status = 'caption_ready' ORDER BY id ASC LIMIT 1;"
        )
        return dict(row) if row else None

    def update_status(
        self,
        reel_id: int,
        status: str,
        *,
        raw_path: str | None = None,
        processed_path: str | None = None,
        yt_title: str | None = None,
        yt_description: str | None = None,
        yt_tags: str | None = None,
        yt_video_id: str | None = None,
        error_msg: str | None = None,
        retry_count: int | None = None,
    ) -> None:
        """Update a reel's status and optional metadata."""
        fields = ["status = ?"]
        params: list = [status]

        if raw_path is not None:
            fields.append("raw_path = ?")
            params.append(raw_path)
        if processed_path is not None:
            fields.append("processed_path = ?")
            params.append(processed_path)
        if yt_title is not None:
            fields.append("yt_title = ?")
            params.append(yt_title)
        if yt_description is not None:
            fields.append("yt_description = ?")
            params.append(yt_description)
        if yt_tags is not None:
            fields.append("yt_tags = ?")
            params.append(yt_tags)
        if yt_video_id is not None:
            fields.append("yt_video_id = ?")
            params.append(yt_video_id)
        if error_msg is not None:
            fields.append("error_msg = ?")
            params.append(error_msg)
        if retry_count is not None:
            fields.append("retry_count = ?")
            params.append(retry_count)
        if status in ("posted", "failed"):
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

    def shortcode_exists(self, shortcode: str) -> bool:
        row = self._fetchone(
            "SELECT 1 FROM queue WHERE ig_shortcode = ?;", (shortcode,)
        )
        return row is not None
