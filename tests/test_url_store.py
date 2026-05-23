#!/usr/bin/env python3
"""Tests for tracker/reel_url_store.py — file-based URL queue management."""
import pytest
from pathlib import Path
from tracker.reel_url_store import shortcode_from_url, count_unused, count_used, peek_next, consume_next, refill_from_used


class TestShortcodeFromUrl:
    def test_standard_reel_url(self):
        assert shortcode_from_url("https://www.instagram.com/reel/DWOnIimjUNF/") == "DWOnIimjUNF"

    def test_photo_url(self):
        assert shortcode_from_url("https://www.instagram.com/p/CxYzAbCdEfG/") == "CxYzAbCdEfG"

    def test_with_username_prefix(self):
        assert shortcode_from_url("https://www.instagram.com/username/reel/DWOnIimjUNF/") == "DWOnIimjUNF"

    def test_with_query_params(self):
        assert shortcode_from_url("https://www.instagram.com/reel/DWOnIimjUNF/?igsh=abc123") == "DWOnIimjUNF"

    def test_no_match(self):
        assert shortcode_from_url("https://example.com/video") is None

    def test_empty_string(self):
        assert shortcode_from_url("") is None

    def test_shortcode_with_underscores_and_dashes(self):
        assert shortcode_from_url("https://www.instagram.com/reel/ABC_DEF-123/") == "ABC_DEF-123"


@pytest.fixture
def temp_reels(tmp_path, monkeypatch):
    """Set up temporary reels.txt and reels_used.txt in a temp dir."""
    monkeypatch.setattr("tracker.reel_url_store.REELS_FILE", tmp_path / "reels.txt")
    monkeypatch.setattr("tracker.reel_url_store.USED_FILE", tmp_path / "reels_used.txt")
    monkeypatch.setattr("tracker.reel_url_store.DATA_DIR", tmp_path)
    return tmp_path


class TestCountUnused:
    def test_file_not_exists(self, temp_reels):
        assert count_unused() == 0

    def test_empty_file(self, temp_reels):
        (temp_reels / "reels.txt").write_text("")
        assert count_unused() == 0

    def test_with_urls(self, temp_reels):
        (temp_reels / "reels.txt").write_text("url1\nurl2\nurl3\n")
        assert count_unused() == 3

    def test_skips_blank_lines(self, temp_reels):
        (temp_reels / "reels.txt").write_text("url1\n\n\nurl2\n")
        assert count_unused() == 2


class TestCountUsed:
    def test_file_not_exists(self, temp_reels):
        assert count_used() == 0

    def test_empty_file(self, temp_reels):
        (temp_reels / "reels_used.txt").write_text("")
        assert count_used() == 0

    def test_with_entries(self, temp_reels):
        (temp_reels / "reels_used.txt").write_text("url1  # used 2026-01-01\nurl2  # used 2026-01-02\n")
        assert count_used() == 2


class TestPeekNext:
    def test_returns_first_url(self, temp_reels):
        (temp_reels / "reels.txt").write_text("first_url\nsecond_url\n")
        assert peek_next() == "first_url"

    def test_does_not_consume(self, temp_reels):
        (temp_reels / "reels.txt").write_text("only_url\n")
        peek_next()
        assert count_unused() == 1

    def test_returns_none_when_empty(self, temp_reels):
        assert peek_next() is None


class TestConsumeNext:
    def test_consumes_first_url(self, temp_reels):
        (temp_reels / "reels.txt").write_text("url1\nurl2\n")
        result = consume_next()
        assert result == "url1"
        assert count_unused() == 1
        assert peek_next() == "url2"

    def test_appends_to_used(self, temp_reels):
        (temp_reels / "reels.txt").write_text("consumed_url\n")
        consume_next()
        used_text = (temp_reels / "reels_used.txt").read_text()
        assert "consumed_url" in used_text
        assert "used" in used_text

    def test_returns_none_when_empty(self, temp_reels):
        assert consume_next() is None

    def test_returns_none_when_no_file(self, temp_reels):
        assert consume_next() is None


class TestRefillFromUsed:
    def test_refills_from_used(self, temp_reels):
        (temp_reels / "reels_used.txt").write_text("http://used1.com  # used 2026-01-01\nhttp://used2.com  # used 2026-01-02\n")
        n = refill_from_used(top_up=10)
        assert n == 2
        assert count_unused() == 2

    def test_does_not_create_duplicates(self, temp_reels):
        (temp_reels / "reels.txt").write_text("http://existing.com\n")
        (temp_reels / "reels_used.txt").write_text("http://existing.com  # used 2026-01-01\n")
        n = refill_from_used(top_up=10)
        assert n == 0  # Duplicate, not added
        assert count_unused() == 1

    def test_respects_top_up(self, temp_reels):
        (temp_reels / "reels_used.txt").write_text("http://u1.com\nhttp://u2.com\nhttp://u3.com\nhttp://u4.com\nhttp://u5.com\n")
        n = refill_from_used(top_up=3)
        assert n == 3
        assert count_unused() == 3
