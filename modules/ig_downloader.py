"""Instagram reel downloader — consumes one URL per day from reels.txt.

Flow:
  1. Read next URL from reels.txt, mark as used
  2. Extract shortcode from URL
  3. Resolve via Post.from_shortcode() — no login needed, gets video_url + caption from page data
  4. Download video directly via requests
  5. Add to SQLite queue
"""

import logging
from pathlib import Path
from typing import Optional

import instaloader
import requests

from config.settings import Settings
from tracker.db import QueueDB
from tracker.reel_url_store import consume_next, count_unused, shortcode_from_url

logger = logging.getLogger(__name__)


class IGDownloaderError(Exception):
    """Base exception for Instagram download failures."""


class IGDownloader:
    """Downloads one reel at a time from the reels.txt URL queue.

    No login needed — Post.from_shortcode() resolves video_url from public page data.
    """

    def __init__(self, settings: Settings, db: QueueDB) -> None:
        self.settings = settings
        self.db = db
        self.loader = instaloader.Instaloader(
            download_videos=False,
            download_pictures=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            max_connection_attempts=2,
            quiet=True,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def download_next_reel(self) -> Optional[str]:
        """Consume the next URL from reels.txt, download it, add to queue."""
        remaining = count_unused()
        if remaining == 0:
            logger.warning("No URLs left in reels.txt")
            return None

        logger.info("URLs remaining: %d", remaining)

        url = consume_next()
        if not url:
            return None

        shortcode = shortcode_from_url(url)
        if not shortcode:
            logger.error("Bad URL (no shortcode): %s", url)
            return None

        logger.info("Downloading: %s", shortcode)

        post = self._resolve_post(shortcode)
        if not post:
            logger.error("Could not resolve post %s", shortcode)
            return None

        raw_path = self.settings.videos_raw_dir / f"{shortcode}.mp4"
        if not self._download_video(post.video_url, raw_path):
            logger.error("Download failed for %s", shortcode)
            return None

        caption = post.caption or ""
        self.db.add_reel(shortcode, caption)
        self.db.update_status(self._get_reel_id(shortcode), "downloaded", raw_path=str(raw_path))
        logger.info("Added to queue: %s", shortcode)
        return shortcode

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_post(shortcode: str) -> Optional[instaloader.Post]:
        try:
            ldr = instaloader.Instaloader(download_videos=False, quiet=True)
            return instaloader.Post.from_shortcode(ldr.context, shortcode)
        except Exception as e:
            logger.warning("Post resolve error for %s: %s", shortcode, e)
            return None

    @staticmethod
    def _download_video(video_url: Optional[str], output_path: Path) -> bool:
        if not video_url:
            logger.error("No video_url available")
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            resp = requests.get(
                video_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.instagram.com/",
                },
                timeout=120,
            )
            if resp.status_code != 200:
                logger.error("HTTP %d downloading video", resp.status_code)
                return False
            output_path.write_bytes(resp.content)
            logger.info("Video saved: %s (%.1f MB)", output_path.name, len(resp.content) / (1024 * 1024))
            return True
        except requests.RequestException as e:
            logger.error("Request failed: %s", e)
            return False

    def _get_reel_id(self, shortcode: str) -> int:
        recent = self.db.get_recent(1)
        return recent[0]["id"] if recent else 0
