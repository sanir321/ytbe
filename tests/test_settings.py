#!/usr/bin/env python3
"""Tests for config/settings.py — env loading and validation."""
import os
import pytest
from pathlib import Path
from config.settings import load_settings, ConfigError, Settings, PROJECT_ROOT


class TestLoadSettings:
    def test_raises_on_missing_required(self):
        for key in ["KILO_API_KEY", "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"]:
            os.environ.pop(key, None)
        with pytest.raises(ConfigError, match="Missing required"):
            load_settings()

    def test_raises_on_partial_missing(self):
        os.environ["KILO_API_KEY"] = "test_key"
        os.environ.pop("YT_CLIENT_ID", None)
        os.environ["YT_CLIENT_SECRET"] = "test_secret"
        os.environ["YT_REFRESH_TOKEN"] = "test_refresh"
        with pytest.raises(ConfigError):
            load_settings()

    def test_loads_successfully(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "kilo_key")
        monkeypatch.setenv("YT_CLIENT_ID", "client_id")
        monkeypatch.setenv("YT_CLIENT_SECRET", "client_secret")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "refresh_token")
        settings = load_settings()
        assert settings.kilo_api_key == "kilo_key"
        assert settings.yt_client_id == "client_id"
        assert settings.yt_client_secret == "client_secret"
        assert settings.yt_refresh_token == "refresh_token"

    def test_optional_instagram_defaults_empty(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
        monkeypatch.delenv("IG_USERNAME", raising=False)
        monkeypatch.delenv("IG_PASSWORD", raising=False)
        monkeypatch.delenv("IG_TARGET", raising=False)
        settings = load_settings()
        assert settings.ig_username == ""
        assert settings.ig_password == ""
        assert settings.ig_target == ""

    def test_optional_instagram_can_be_set(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
        monkeypatch.setenv("IG_USERNAME", "myuser")
        monkeypatch.setenv("IG_PASSWORD", "mypass")
        monkeypatch.setenv("IG_TARGET", "mytarget")
        settings = load_settings()
        assert settings.ig_username == "myuser"

    def test_yt_refresh_token_with_equals_in_value(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "1//abc123=def456==")
        settings = load_settings()
        assert settings.yt_refresh_token == "1//abc123=def456=="


class TestDefaults:
    def test_kilo_base_url_default(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
        settings = load_settings()
        assert settings.kilo_base_url == "https://api.kilo.ai/api/gateway"

    def test_cron_defaults(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
        settings = load_settings()
        assert settings.cron_hour == 7
        assert settings.cron_minute == 30
        assert settings.cron_timezone == "Asia/Kolkata"

    def test_max_video_duration_default(self):
        s = Settings(kilo_api_key="k", yt_client_id="c", yt_client_secret="s", yt_refresh_token="r")
        assert s.max_video_duration == 60
        assert s.target_width == 1080
        assert s.target_height == 1920

    def test_port_default(self):
        s = Settings(kilo_api_key="k", yt_client_id="c", yt_client_secret="s", yt_refresh_token="r")
        assert s.port == 8080

    def test_data_dir_default(self):
        s = Settings(kilo_api_key="k", yt_client_id="c", yt_client_secret="s", yt_refresh_token="r")
        assert s.data_dir == PROJECT_ROOT / "data"


class TestDirectories:
    def test_dirs_created_on_init(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
        monkeypatch.setenv("DATA_DIR", str(tmp_path / "custom_data"))
        settings = load_settings()
        # data_dir itself is not auto-created, but derived dirs are
        assert settings.videos_raw_dir.exists()
        assert settings.videos_processed_dir.exists()
        assert settings.log_dir.exists()

    def test_client_secret_path(self):
        s = Settings(kilo_api_key="k", yt_client_id="my_client_id", yt_client_secret="s", yt_refresh_token="r")
        assert s.client_secret_path.name == "client_secret_my_client_id.json"
        assert s.client_secret_path.parent == PROJECT_ROOT


class TestCustomEnvOverrides:
    def test_custom_kilo_base_url(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
        monkeypatch.setenv("KILO_BASE_URL", "https://custom.ai/")
        settings = load_settings()
        assert settings.kilo_base_url == "https://custom.ai/"

    def test_custom_data_dir(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
        monkeypatch.setenv("DATA_DIR", "/custom/path")
        settings = load_settings()
        assert settings.data_dir == Path("/custom/path")

    def test_custom_cron(self, monkeypatch):
        monkeypatch.setenv("KILO_API_KEY", "k")
        monkeypatch.setenv("YT_CLIENT_ID", "c")
        monkeypatch.setenv("YT_CLIENT_SECRET", "s")
        monkeypatch.setenv("YT_REFRESH_TOKEN", "r")
        monkeypatch.setenv("CRON_HOUR", "14")
        monkeypatch.setenv("CRON_MINUTE", "30")
        settings = load_settings()
        assert settings.cron_hour == 14
        assert settings.cron_minute == 30
