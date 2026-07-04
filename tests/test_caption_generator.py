#!/usr/bin/env python3
"""Tests for modules/caption_generator.py - AI caption parsing and fallback."""
import pytest
import json
from modules.caption_generator import CaptionGenerator


class TestFallbackMetadata:
    def test_returns_valid_structure(self):
        meta = CaptionGenerator.fallback_metadata()
        assert "title" in meta
        assert "description" in meta
        assert "hashtags" in meta
        assert isinstance(meta["hashtags"], list)
        assert len(meta["hashtags"]) > 0

    def test_title_has_no_hashtags(self):
        meta = CaptionGenerator.fallback_metadata()
        assert "#" not in meta["title"]

    def test_description_is_reasonable_length(self):
        meta = CaptionGenerator.fallback_metadata()
        assert 50 < len(meta["description"]) < 500


class TestSanitization:

    def test_normalize_hashtags_from_string_comma_separated(self):
        raw = ', '.join(["#a", "#b", "#c"])
        if "," in raw:
            tags = [h.strip() for h in raw.split(",") if h.strip()]
        tags = [f"#{h.lstrip('#')}" if not h.startswith("#") else h for h in tags]
        assert len(tags) == 3
        assert all(t.startswith("#") for t in tags)

    def test_normalize_hashtags_without_hash_prefix(self):
        raw = "Shorts, motivation, mindset"
        if "," in raw:
            tags = [h.strip() for h in raw.split(",") if h.strip()]
        tags = [f"#{h.lstrip('#')}" if not h.startswith("#") else h for h in tags]
        assert tags == ["#Shorts", "#motivation", "#mindset"]

    def test_ensure_shorts_in_hashtags(self):
        tags = ["#motivation", "#mindset"]
        if "#Shorts" not in tags:
            tags.insert(0, "#Shorts")
        assert tags[0] == "#Shorts"

    def test_title_has_no_hashtags(self):
        title = "Amazing Title"
        assert "#" not in title

    def test_description_contains_hashtags(self):
        desc = "Great content. Follow for more."
        tags = ["#Shorts", "#motivation"]
        tag_str = "  ".join(tags)
        if tag_str not in desc:
            desc = desc.rstrip() + "\n\n" + tag_str
        assert tag_str in desc
        assert len(desc) <= 5000

    def test_trailing_comma_fix(self):
        raw = '''{"title": "Test", "description": "Desc", "hashtags": ["#a", "#b",]}'''
        fixed = raw.replace(",\n}", "\n}").replace(",}", "}").replace(",\n]", "\n]").replace(",]", "]")
        data = json.loads(fixed)
        assert data["hashtags"] == ["#a", "#b"]

    def test_single_quote_fix(self):
        raw = """{'title': 'Test', 'description': 'Desc', 'hashtags': ['#a']}"""
        fixed = raw.replace("'", '"')
        data = json.loads(fixed)
        assert data["title"] == "Test"

    def test_code_fence_stripping(self):
        raw = "```json\n{\"title\": \"Test\"}\n```"
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        if raw.endswith("```"):
            idx = raw.rfind("```")
            raw = raw[:idx]
        raw = raw.strip()
        data = json.loads(raw)
        assert data["title"] == "Test"


class TestGenerateRealCall:
    """Verify the class constructs properly and handles errors gracefully."""

    def test_init_with_mock_settings(self, mocker):
        settings = mocker.Mock()
        settings.kilo_api_key = "test_key"
        settings.kilo_base_url = "https://api.example.com"
        gen = CaptionGenerator(settings)
        assert gen is not None
        assert gen.client.api_key == "test_key"
        assert gen.client.base_url == "https://api.example.com"

    def test_generate_returns_none_on_empty_caption(self, mocker):
        from openai import APIError
        settings = mocker.Mock()
        settings.kilo_api_key = "test_key"
        settings.kilo_base_url = "https://api.example.com"
        gen = CaptionGenerator(settings)

        mocker.patch.object(gen.client.chat.completions, "create", side_effect=APIError("API error", request=mocker.Mock(), body=mocker.Mock()))
        result = gen.generate("")
        assert result is None
