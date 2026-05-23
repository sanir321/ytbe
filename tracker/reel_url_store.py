"""File-based URL queue — reads one reel URL per day from reels.txt.

This replaces the old approach of scraping Instagram on every run.
Now we:
  1. ONE-TIME: Run scrape_reels_urls.py or playwright_scrape.py to fill reels.txt
  2. DAILY:   consume_next() returns one URL, moves it to reels_used.txt

reels.txt         — unused URLs (one per line)
reels_used.txt    — completed URLs (one per line, for audit)
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

REELS_FILE = Path("data") / "reels.txt"
USED_FILE = Path("data") / "reels_used.txt"
DATA_DIR = Path("data")


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


def count_used() -> int:
    """Return the number of used URLs."""
    if not USED_FILE.exists():
        return 0
    lines = [l.strip() for l in USED_FILE.read_text().splitlines() if l.strip()]
    return len(lines)


def peek_next() -> Optional[str]:
    """Return the next URL without consuming it (or None if empty)."""
    if not REELS_FILE.exists():
        return None
    lines = [l.strip() for l in REELS_FILE.read_text().splitlines() if l.strip()]
    return lines[0] if lines else None


def consume_next() -> Optional[str]:
    """Return the next unused URL and move it to reels_used.txt.

    Atomically reads the first line from reels.txt, removes it,
    and appends it to reels_used.txt with a timestamp.

    Returns:
        The URL string, or None if the queue is empty.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not REELS_FILE.exists():
        logger.warning("reels.txt not found — run playwright_scrape.py first")
        return None

    lines = [l.strip() for l in REELS_FILE.read_text().splitlines() if l.strip()]
    if not lines:
        logger.warning("reels.txt is empty — run playwright_scrape.py to refill")
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


def refill_from_used(top_up: int = 10) -> int:
    """Move URLs from used back to unused (for testing or retries).

    Args:
        top_up: Number of most recent used URLs to recycle.

    Returns:
        Number of URLs restored.
    """
    if not USED_FILE.exists():
        return 0

    lines = [l.strip() for l in USED_FILE.read_text().splitlines() if l.strip()]
    # Extract URLs (strip the trailing comment)
    urls = [l.split("  #")[0].strip() for l in lines if l.startswith("http")]
    if not urls:
        return 0

    recycled = urls[-top_up:]  # most recent first
    # Add to reels.txt
    existing = set()
    if REELS_FILE.exists():
        existing = {l.strip() for l in REELS_FILE.read_text().splitlines() if l.strip()}

    new = []
    for url in recycled:
        if url not in existing:
            new.append(url)
            existing.add(url)

    if new:
        current = REELS_FILE.read_text().strip() if REELS_FILE.exists() else ""
        REELS_FILE.write_text(current + "\n" + "\n".join(new) + "\n", encoding="utf-8")

    logger.info("Recycled %d URLs back to reels.txt", len(new))
    return len(new)
