#!/usr/bin/env python3
"""Tests for tracker/db.py - SQLite queue management."""
import pytest
from pathlib import Path
from tracker.db import QueueDB


@pytest.fixture
def db(tmp_path):
    """Create a fresh QueueDB in a temp directory."""
    path = tmp_path / "test_queue.db"
    return QueueDB(path)


class TestInit:
    def test_creates_table(self, tmp_path):
        path = tmp_path / "queue.db"
        db = QueueDB(path)
        rows = db._fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        assert any(r["name"] == "queue" for r in rows)

    def test_pragma_wal(self, tmp_path):
        path = tmp_path / "queue.db"
        db = QueueDB(path)
        row = db._fetchone("PRAGMA journal_mode")
        assert row[0] == "wal"


class TestAddReel:
    def test_adds_reel(self, db):
        result = db.add_reel("shortcode1", "Test caption")
        assert isinstance(result, int)
        assert db.count_total() == 1

    def test_status_defaults_to_downloaded(self, db):
        db.add_reel("sc01", "caption")
        row = db._fetchone("SELECT status FROM queue WHERE ig_shortcode = ?", ("sc01",))
        assert row["status"] == "downloaded"

    def test_duplicate_shortcode_returns_none(self, db):
        db.add_reel("unique_sc")
        assert db.add_reel("unique_sc") is None
        assert db.count_total() == 1

    def test_caption_is_stored(self, db):
        db.add_reel("sc02", "Important caption text")
        row = db._fetchone("SELECT ig_caption FROM queue WHERE ig_shortcode = ?", ("sc02",))
        assert row["ig_caption"] == "Important caption text"


class TestStatusFlow:
    def test_full_lifecycle(self, db):
        db.add_reel("sc_lifecycle", "Original caption")
        reel = db.get_next_by_status("downloaded")
        assert reel is not None
        assert reel["ig_shortcode"] == "sc_lifecycle"

        db.update_status(reel["id"], "processed", processed_path="/tmp/processed.mp4")
        reel = db.get_next_by_status("processed")
        assert reel is not None
        assert reel["ig_shortcode"] == "sc_lifecycle"

        db.update_status(reel["id"], "caption_ready", yt_title="Test Title", yt_description="Test Desc")
        reel = db.get_next_by_status("caption_ready")
        assert reel is not None
        assert reel["yt_title"] == "Test Title"

        db.update_status(reel["id"], "posted", yt_video_id="abc123")
        assert db.count_by_status("posted") == 1
        assert db.count_by_status("pending") == 0

    def test_get_next_by_status_returns_oldest_first(self, db):
        db.add_reel("first")
        db.add_reel("second")
        db.add_reel("third")
        reel = db.get_next_by_status("downloaded")
        assert reel["ig_shortcode"] == "first"

    def test_skips_non_matching_status(self, db):
        db.add_reel("downloaded_reel")
        row = db._fetchone("SELECT * FROM queue WHERE ig_shortcode='downloaded_reel'")
        db.update_status(row["id"], "posted", yt_video_id="yay")
        assert db.get_next_by_status("downloaded") is None

    def test_caption_ready_skips_without_title(self, db):
        db.add_reel("sc_no_title")
        row = db._fetchone("SELECT * FROM queue WHERE ig_shortcode='sc_no_title'")
        db.update_status(row["id"], "caption_ready")  # No yt_title
        assert db.get_next_by_status("caption_ready") is not None


class TestUpdateStatus:
    def test_metadata_update(self, db):
        db.add_reel("sc_meta")
        reel = db.get_next_by_status("downloaded")
        db.update_status(
            reel["id"], "processed",
            raw_path="/raw.mp4",
            processed_path="/proc.mp4",
        )
        row = db._fetchone("SELECT * FROM queue WHERE ig_shortcode='sc_meta'")
        assert row["raw_path"] == "/raw.mp4"
        assert row["processed_path"] == "/proc.mp4"
        assert row["status"] == "processed"

    def test_posted_sets_timestamp(self, db):
        db.add_reel("sc_posted")
        row = db._fetchone("SELECT * FROM queue WHERE ig_shortcode='sc_posted'")
        db.update_status(row["id"], "posted", yt_video_id="vid123")
        row = db._fetchone("SELECT * FROM queue WHERE ig_shortcode='sc_posted'")
        assert row["posted_at"] is not None
        assert row["yt_video_id"] == "vid123"


class TestCounts:
    def test_count_by_status(self, db):
        db.add_reel("a")
        db.add_reel("b")
        db.add_reel("c")
        db.add_reel("d")
        rows_a = db._fetchall("SELECT * FROM queue")
        db.update_status(rows_a[0]["id"], "processed")
        db.update_status(rows_a[1]["id"], "processed")
        db.update_status(rows_a[2]["id"], "posted", yt_video_id="x")
        assert db.count_by_status("processed") == 2
        assert db.count_by_status("posted") == 1
        assert db.count_by_status("downloaded") == 1
        assert db.count_total() == 4

    def test_count_total_empty_db(self, tmp_path):
        db = QueueDB(tmp_path / "empty.db")
        assert db.count_total() == 0


class TestShortcodeExists:
    def test_exists(self, db):
        db.add_reel("exists_sc")
        assert db.shortcode_exists("exists_sc") is True

    def test_not_exists(self, db):
        assert db.shortcode_exists("nonexistent") is False


class TestGetRecent:
    def test_returns_most_recent_first(self, db):
        db.add_reel("first")
        db.add_reel("second")
        db.add_reel("third")
        recent = db.get_recent(5)
        assert len(recent) == 3
        assert recent[0]["ig_shortcode"] == "third"
        assert recent[-1]["ig_shortcode"] == "first"

    def test_limits_result(self, db):
        for i in range(10):
            db.add_reel(f"sc_{i}")
        recent = db.get_recent(3)
        assert len(recent) == 3


class TestEdgeCases:
    def test_empty_get_next_by_status(self, tmp_path):
        db = QueueDB(tmp_path / "empty.db")
        assert db.get_next_by_status("downloaded") is None

    def test_update_nonexistent_reel(self, db):
        db.update_status(999, "failed", error_msg="Not found")
        assert db.count_by_status("failed") == 0  # No error - just no-op

    def test_very_long_caption(self, db):
        long_caption = "x" * 10000
        db.add_reel("long_cap", long_caption)
        row = db._fetchone("SELECT ig_caption FROM queue WHERE ig_shortcode='long_cap'")
        assert len(row["ig_caption"]) == 10000
