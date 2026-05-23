"""Application configuration — loads & validates all env vars at startup."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

# Project root is one level up from config/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


class ConfigError(Exception):
    """Raised when a required config variable is missing or invalid."""


@dataclass
class Settings:
    """Immutable settings container. All values pulled from env at construction."""

    # Required — Kilo Gateway (AI captions)
    kilo_api_key: str

    # Required — YouTube
    yt_client_id: str
    yt_client_secret: str
    yt_refresh_token: str

    # Optional — Instagram (not needed with pre-collected URLs)
    ig_username: str = ""
    ig_password: str = ""
    ig_target: str = ""

    # Kilo base URL (default after all required fields)
    kilo_base_url: str = "https://api.kilo.ai/api/gateway"

    # Paths — video & log dirs are derived from data_dir in __post_init__
    data_dir: Path = PROJECT_ROOT / "data"
    videos_raw_dir: Path = field(init=False)
    videos_processed_dir: Path = field(init=False)
    log_dir: Path = field(init=False)
    log_file: Path = field(init=False)

    # Scheduling
    cron_hour: int = 7
    cron_minute: int = 30
    cron_timezone: str = "Asia/Kolkata"

    # Limits
    max_video_duration: int = 60
    target_width: int = 1080
    target_height: int = 1920
    queue_refill_threshold: int = 5
    ig_scrape_count: int = 10

    # Railway
    port: int = 8080

    def __post_init__(self) -> None:
        """Derive paths from data_dir and ensure all directories exist."""
        self.videos_raw_dir = self.data_dir / "videos" / "raw"
        self.videos_processed_dir = self.data_dir / "videos" / "processed"
        self.log_dir = self.data_dir / "logs"
        self.log_file = self.data_dir / "logs" / "bot.log"
        for d in [self.videos_raw_dir, self.videos_processed_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def client_secret_path(self) -> Path:
        return PROJECT_ROOT / f"client_secret_{self.yt_client_id}.json"


def load_settings() -> Settings:
    """Load and validate all settings from environment variables.

    Returns:
        Settings object with all validated values.

    Raises:
        ConfigError: If any required variable is missing.
    """
    required = {
        "KILO_API_KEY": "Kilo Gateway API key",
        "YT_CLIENT_ID": "YouTube OAuth client ID",
        "YT_CLIENT_SECRET": "YouTube OAuth client secret",
        "YT_REFRESH_TOKEN": "YouTube OAuth refresh token",
    }

    missing = {k: v for k, v in required.items() if not os.getenv(k)}
    if missing:
        lines = "\n".join(f"  • {k} — {v}" for k, v in missing.items())
        raise ConfigError(f"Missing required environment variables:\n{lines}")

    return Settings(
        ig_username=os.getenv("IG_USERNAME", ""),
        ig_password=os.getenv("IG_PASSWORD", ""),
        ig_target=os.getenv("IG_TARGET", ""),
        kilo_api_key=os.environ["KILO_API_KEY"],
        kilo_base_url=os.getenv("KILO_BASE_URL", "https://api.kilo.ai/api/gateway"),
        yt_client_id=os.environ["YT_CLIENT_ID"],
        yt_client_secret=os.environ["YT_CLIENT_SECRET"],
        yt_refresh_token=os.environ["YT_REFRESH_TOKEN"],
        cron_hour=int(os.getenv("CRON_HOUR", "7")),
        cron_minute=int(os.getenv("CRON_MINUTE", "30")),
        port=int(os.getenv("PORT", "8080")),
        data_dir=Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data"))),
    )
