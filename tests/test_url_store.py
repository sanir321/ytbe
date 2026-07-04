#!/usr/bin/env python3
"""Tests for tracker/reel_url_store.py - file-based URL queue management."""
import pytest
from pathlib import Path
from tracker.reel_url_store import shortcode_from_url, count_unused, consume_next


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


class TestConsumeNext:
    def test_consumes_first_url(self, temp_reels):
        (temp_reels / "reels.txt").write_text("url1\nurl2\n")
        result = consume_next()
        assert result == "url1"
        assert count_unused() == 1
        lines = (temp_reels / "reels.txt").read_text().strip().splitlines()
        assert lines == ["url2"]

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


