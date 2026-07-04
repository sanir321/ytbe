"""File-based URL queue - reads one reel URL per day from reels.txt.

This replaces the old approach of scraping Instagram on every run.
Now we:
   1. ONE-TIME: Run scrape_reels_urls.py or playwright_scrape.py to fill reels.txt
   2. DAILY:   consume_next() returns one URL, moves it to reels_used.txt

reels.txt         - unused URLs (one per line)
reels_used.txt    - completed URLs (one per line, for audit)

Paths are initially relative to the working directory but can be moved
to a persistent volume via set_data_dir().
"""

import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REELS_FILE = Path("data") / "reels.txt"
USED_FILE = Path("data") / "reels_used.txt"
DATA_DIR = Path("data")

_GIT_REELS = Path("data") / "reels.txt"  # tracked in git, shipped in Docker


def set_data_dir(data_dir: str | Path) -> None:
    """Redirect all file paths under a persistent data directory.

    On the first call, if no reels.txt exists at the new location it
    is seeded from the git-tracked copy so the queue survives restarts.
    Call once at startup before any other function.
    """
    global REELS_FILE, USED_FILE, DATA_DIR
    DATA_DIR = Path(data_dir)
    REELS_FILE = DATA_DIR / "reels.txt"
    USED_FILE = DATA_DIR / "reels_used.txt"

    if not REELS_FILE.exists() and _GIT_REELS.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(_GIT_REELS), str(REELS_FILE))
        lines = [l for l in REELS_FILE.read_text().splitlines() if l.strip()]
        logger.info("Seeded %s from app directory (%d URLs)", REELS_FILE, len(lines))


def is_stale() -> bool:
    """Return True if reels.txt is full but reels_used.txt is empty,
    meaning the user restored the queue from git and wants a reset."""
    return (REELS_FILE.exists()
            and (not USED_FILE.exists() or not USED_FILE.read_text().strip()))


def shortcode_from_url(url: str) -> Optional[str]:
    """Extract the Instagram shortcode from a reel URL.

    Handles formats:
      https://www.instagram.com/reel/SHORTCODE/
      https://www.instagram.com/p/SHORTCODE/
      https://www.instagram.com/stravity.official/reel/SHORTCODE/
    """
    match = re.search(r'/(?:reel|p)/([A-Za-z0-9_\-]+)', url)
    return match.group(1) if match else None


def count_unused() -> int:
    """Return the number of unused URLs in reels.txt."""
    if not REELS_FILE.exists():
        return 0
    lines = [l.strip() for l in REELS_FILE.read_text().splitlines() if l.strip()]
    return len(lines)


def consume_next() -> Optional[str]:
    """Return the next unused URL and move it to reels_used.txt.

    Atomically reads the first line from reels.txt, removes it,
    and appends it to reels_used.txt with a timestamp.

    Returns:
        The URL string, or None if the queue is empty.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not REELS_FILE.exists():
        logger.warning("reels.txt not found - run playwright_scrape.py first")
        return None

    lines = [l.strip() for l in REELS_FILE.read_text().splitlines() if l.strip()]
    if not lines:
        logger.warning("reels.txt is empty - run playwright_scrape.py to refill")
        return None

    url = lines[0]
    remaining = lines[1:]

    # Remove from reels.txt
    REELS_FILE.write_text("\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8")

    # Append to reels_used.txt with timestamp
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(USED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{url}  # used {timestamp}\n")

    logger.info("Consumed: %s (%d remaining)", url, len(remaining))
    return url


def reset_all() -> None:
    """Move all used URLs back to reels.txt, wipe history."""
    if USED_FILE.exists():
        used_lines = [l.strip() for l in USED_FILE.read_text().splitlines() if l.strip()]
        urls = [l.split("  #")[0].strip() for l in used_lines if l.startswith("http")]
        existing = set()
        if REELS_FILE.exists():
            existing = {l.strip() for l in REELS_FILE.read_text().splitlines() if l.strip()}
        new = [u for u in urls if u not in existing]
        if new:
            current = REELS_FILE.read_text().strip() if REELS_FILE.exists() else ""
            REELS_FILE.write_text(current + "\n" + "\n".join(new) + "\n")
        USED_FILE.write_text("")


