"""Instagram reel downloader - consumes one URL per day from reels.txt.

Flow:
   1. Read next URL from reels.txt, mark as used
   2. Extract shortcode from URL
   3. Login to Instagram via API, get sessionid cookie
   4. Download video + caption via yt-dlp with cookies
   5. Add to SQLite queue
"""

import logging
import re
import http.cookiejar as cookiejar
from pathlib import Path
from typing import Optional

import requests
import yt_dlp

from config.settings import Settings
from tracker.db import QueueDB
from tracker.reel_url_store import consume_next, count_unused, shortcode_from_url

logger = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).resolve().parent.parent / "insta_cookies.txt"


def _login_and_save_cookies(username: str, password: str) -> bool:
    """Login to Instagram via web API and save sessionid cookie."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })

    try:
        resp = session.get("https://www.instagram.com/", timeout=15)
        csrf = re.search(r'csrf_token":"([^"]+)"', resp.text)
        csrf_token = csrf.group(1) if csrf else session.cookies.get("csrftoken")

        login_data = {
            "username": username,
            "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:1748880000:{password}",
            "queryParams": {},
            "optIntoOneTap": "false",
        }
        headers = {"X-CSRFToken": csrf_token, "Referer": "https://www.instagram.com/"}
        resp = session.post(
            "https://www.instagram.com/api/v1/web/accounts/login/ajax/",
            data=login_data, headers=headers, timeout=15,
        )
        result = resp.json()
        if not result.get("authenticated"):
            logger.error("IG login failed: %s", result)
            return False

        cj = cookiejar.MozillaCookieJar(str(COOKIES_FILE))
        for c in session.cookies:
            cj.set_cookie(c)
        cj.save()
        logger.info("IG login OK, cookies saved")
        return True
    except Exception as e:
        logger.error("IG login error: %s", e)
        return False


class IGDownloader:
    """Downloads one reel at a time from the reels.txt URL queue."""

    def __init__(self, settings: Settings, db: QueueDB) -> None:
        self.settings = settings
        self.db = db
        self._cookies_ready = False

    def _ensure_login(self) -> bool:
        if self._cookies_ready:
            return True
        if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
            self._cookies_ready = True
            return True
        username = self.settings.ig_username or ""
        password = self.settings.ig_password or ""
        if not username or not password:
            logger.warning("No IG credentials in .env")
            return False
        ok = _login_and_save_cookies(username, password)
        if ok:
            self._cookies_ready = True
        return ok

    def download_next_reel(self) -> Optional[str]:
        remaining = count_unused()
        if remaining == 0:
            logger.warning("No URLs left in reels.txt")
            return None

        logger.info("URLs remaining: %d", remaining)

        for _ in range(remaining):
            url = consume_next()
            if not url:
                return None

            shortcode = shortcode_from_url(url)
            if not shortcode:
                logger.error("Bad URL (no shortcode): %s", url)
                continue

            if self.db.shortcode_exists(shortcode):
                logger.info("Skipping %s - already in queue", shortcode)
                continue

            logger.info("Downloading: %s", shortcode)
            raw_path = self.settings.videos_raw_dir / f"{shortcode}.mp4"
            caption = self._download_reel(shortcode, raw_path)
            if caption is None:
                logger.error("Download failed for %s", shortcode)
                continue

            reel_id = self.db.add_reel(shortcode, caption)
            if reel_id is None:
                logger.error("Failed to add %s to queue", shortcode)
                continue
            self.db.update_status(reel_id, "downloaded", raw_path=str(raw_path))
            logger.info("Added to queue: %s", shortcode)
            return shortcode

        logger.warning("All remaining URLs are already in the queue")
        return None

    def _download_reel(self, shortcode: str, output_path: Path) -> Optional[str]:
        if not self._ensure_login():
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)

        opts = {
            "cookiefile": str(COOKIES_FILE),
            "outtmpl": str(output_path),
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": False,
            "max_filesize": 200_000_000,
        }
        url = f"https://www.instagram.com/reel/{shortcode}/"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                caption = ""
                if info:
                    caption = info.get("description") or info.get("title") or ""
                return caption
        except Exception as e:
            logger.error("yt-dlp failed for %s: %s", shortcode, e)
            return None
