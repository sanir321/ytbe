import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


class PipelineError(Exception):
    pass


@dataclass
class Settings:
    kilo_api_key: str
    yt_client_id: str
    yt_client_secret: str
    yt_refresh_token: str
    yt2_client_id: str = ""
    yt2_client_secret: str = ""
    yt2_refresh_token: str = ""
    ig_username: str = ""
    ig_password: str = ""

    kilo_base_url: str = "https://api.kilo.ai/api/gateway"

    data_dir: Path = PROJECT_ROOT / "data"
    videos_raw_dir: Path = field(init=False)
    videos_processed_dir: Path = field(init=False)
    log_dir: Path = field(init=False)
    log_file: Path = field(init=False)

    max_video_duration: int = 60
    target_width: int = 1080
    target_height: int = 1920

    def __post_init__(self) -> None:
        self.videos_raw_dir = self.data_dir / "videos" / "raw"
        self.videos_processed_dir = self.data_dir / "videos" / "processed"
        self.log_dir = self.data_dir / "logs"
        self.log_file = self.data_dir / "logs" / "bot.log"
        for d in [self.videos_raw_dir, self.videos_processed_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    required = {
        "KILO_API_KEY": "Kilo Gateway API key",
        "YT_CLIENT_ID": "YouTube OAuth client ID",
        "YT_CLIENT_SECRET": "YouTube OAuth client secret",
        "YT_REFRESH_TOKEN": "YouTube OAuth refresh token",
    }

    missing = {k: v for k, v in required.items() if not os.getenv(k)}
    if missing:
        lines = "\n".join(f"  \u2022 {k} \u2014 {v}" for k, v in missing.items())
        raise PipelineError(f"Missing required environment variables:\n{lines}")

    return Settings(
        kilo_api_key=os.environ["KILO_API_KEY"],
        kilo_base_url=os.getenv("KILO_BASE_URL", "https://api.kilo.ai/api/gateway"),
        yt_client_id=os.environ["YT_CLIENT_ID"],
        yt_client_secret=os.environ["YT_CLIENT_SECRET"],
        yt_refresh_token=os.environ["YT_REFRESH_TOKEN"],
        yt2_client_id=os.getenv("YT2_CLIENT_ID", ""),
        yt2_client_secret=os.getenv("YT2_CLIENT_SECRET", ""),
        yt2_refresh_token=os.getenv("YT2_REFRESH_TOKEN", ""),
        ig_username=os.getenv("IG_USERNAME", ""),
        ig_password=os.getenv("IG_PASSWORD", ""),
        data_dir=Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data"))),
    )
