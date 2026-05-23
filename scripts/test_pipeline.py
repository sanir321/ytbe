#!/usr/bin/env python3
"""End-to-end pipeline test script.

Usage:
    python scripts/test_pipeline.py              # dry-run (scrape + process + generate, no upload)
    python scripts/test_pipeline.py --upload-one # upload 1 video to YouTube (unlisted)
    python scripts/test_pipeline.py --scrape     # scrape only
    python scripts/test_pipeline.py --process    # process 1 pending reel
    python scripts/test_pipeline.py --caption    # generate caption for 1 pending reel
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import load_settings
from tracker.db import QueueDB
from modules.ig_downloader import IGDownloader
from modules.video_processor import VideoProcessor
from modules.caption_generator import CaptionGenerator
from modules.yt_uploader import YTUploader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_pipeline")

SHORTCODE = "test_reel_001"


def _create_test_video(output_path: Path) -> bool:
    """Generate a 15-second synthetic test video using FFmpeg (no IG needed)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=1080x1920:d=15:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-vf", f"drawtext=text='{SHORTCODE}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-shortest",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("FFmpeg failed: %s", result.stderr)
        return False
    logger.info("Test video created: %.1f MB", output_path.stat().st_size / 1_048_576)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Test the Instagram-to-YouTube pipeline")
    parser.add_argument("--upload-one", action="store_true", help="Upload 1 reel to YouTube")
    parser.add_argument("--scrape", action="store_true", help="Scrape reels only")
    parser.add_argument("--process", action="store_true", help="Process 1 pending reel")
    parser.add_argument("--caption", action="store_true", help="Generate caption for 1 pending reel")
    parser.add_argument("--queue", action="store_true", help="Show queue contents")
    parser.add_argument("--all", action="store_true", help="Run full pipeline (scrape, process, caption)")
    parser.add_argument("--mock", action="store_true", help="Use synthetic video (skip IG scrape)")
    parser.add_argument("--reset-db", action="store_true", help="Reset the queue database")
    args = parser.parse_args()

    try:
        settings = load_settings()
    except Exception as e:
        logger.error("Config error: %s", e)
        sys.exit(1)

    db_path = settings.data_dir / "queue.db"
    if args.reset_db:
        if db_path.exists():
            db_path.unlink()
            logger.info("Database reset: %s", db_path)
        db = QueueDB(db_path)
    else:
        db = QueueDB(db_path)

    if args.queue:
        _show_queue(db)
    elif args.mock:
        _test_mock(settings, db, upload_one=args.upload_one)
    elif args.all:
        _test_dry_run(settings, db)
    elif args.scrape:
        _test_scrape(settings, db)
    elif args.process:
        _test_process(settings, db)
    elif args.caption:
        _test_caption(settings, db)
    elif args.upload_one:
        _test_upload(settings, db)
    else:
        _test_dry_run(settings, db)


def _show_queue(db) -> None:
    """Display current queue contents."""
    rows = db.get_recent(20)
    if not rows:
        logger.info("Queue is empty")
        return
    logger.info("Queue contents (%d items):", len(rows))
    for row in rows:
        logger.info(
            "  #%d [%s] %s — %s",
            row["id"],
            row["status"],
            row["ig_shortcode"],
            (row.get("yt_title") or "")[:50],
        )


def _test_mock(settings, db, upload_one: bool = False) -> None:
    """Run pipeline with a synthetic test video (no Instagram needed)."""
    logger.info("=== MOCK MODE (synthetic test video) ===")

    # Step 1: Create synthetic video and add to queue
    raw_video = settings.videos_raw_dir / f"{SHORTCODE}.mp4"
    if not raw_video.exists():
        if not _create_test_video(raw_video):
            logger.error("Failed to create test video")
            return

    if not db.shortcode_exists(SHORTCODE):
        db.add_reel(SHORTCODE, "Test caption for mock pipeline run")
        # Find the newly added reel's ID
        recent = db.get_recent(1)
        if recent:
            db.update_status(recent[0]["id"], "downloaded", raw_path=str(raw_video))
        logger.info("Added mock reel to queue: %s", SHORTCODE)
    else:
        logger.info("Mock reel already in queue")

    # Step 2: Process
    _run_processing(settings, db)

    # Step 3: Caption
    _run_caption(settings, db)

    # Step 4: Upload (if --upload-one)
    if upload_one:
        _run_upload(settings, db)

    logger.info("Mock pipeline complete!")


def _test_dry_run(settings, db) -> None:
    """Run all pipeline steps except actual upload."""
    logger.info("=== DRY RUN MODE (no upload) ===")

    # Step 1: Download next reel from reels.txt
    try:
        downloader = IGDownloader(settings, db)
        shortcode = downloader.download_next_reel()
        if shortcode:
            logger.info("Downloaded reel: %s", shortcode)
        else:
            logger.info("No reel downloaded (queue may be empty)")
    except Exception as e:
        logger.warning("IG download failed (%s). Use --mock to test without Instagram.", e)

    # Step 2: Process
    _run_processing(settings, db)

    # Step 3: Caption
    _run_caption(settings, db)

    logger.info("Dry run complete!")
    _show_queue(db)


def _run_processing(settings, db) -> None:
    """Process all pending reels."""
    processor = VideoProcessor(settings)
    reel = db.get_next_pending()
    while reel:
        raw_path = reel["raw_path"]
        if not raw_path or not Path(raw_path).exists():
            db.update_status(reel["id"], "failed", error_msg="File not found")
            reel = db.get_next_pending()
            continue
        shortcode = reel["ig_shortcode"]
        output = settings.videos_processed_dir / f"{shortcode}.mp4"
        ok = processor.process_video(raw_path, output)
        if ok:
            db.update_status(reel["id"], "processed", processed_path=str(output))
            logger.info("Processed %s", shortcode)
        else:
            db.update_status(reel["id"], "failed", error_msg="FFmpeg processing failed")
            logger.error("Failed to process %s", shortcode)
        reel = db.get_next_pending()


def _run_caption(settings, db) -> None:
    """Generate captions for all processed reels."""
    generator = CaptionGenerator(settings)
    reel = db.get_next_processed()
    while reel:
        ig_caption = reel.get("ig_caption") or ""
        meta = generator.generate(ig_caption)
        if not meta:
            meta = generator.fallback_metadata()
        db.update_status(
            reel["id"],
            "caption_ready",
            yt_title=meta["title"],
            yt_description=meta["description"],
            yt_tags=",".join(meta["hashtags"]),
        )
        logger.info("Caption generated for %s: %s", reel["ig_shortcode"], meta["title"])
        reel = db.get_next_processed()


def _run_upload(settings, db) -> None:
    """Upload the next caption_ready reel to YouTube."""
    reel = db.get_next_caption_ready()
    if not reel:
        logger.error("No caption_ready reels found")
        return

    processed_path = reel.get("processed_path")
    raw_path = reel.get("raw_path", "")
    if not processed_path or not Path(processed_path).exists():
        # Process if needed
        processor = VideoProcessor(settings)
        output = settings.videos_processed_dir / f"{reel['ig_shortcode']}.mp4"
        ok = processor.process_video(raw_path, output)
        if ok:
            processed_path = str(output)
        else:
            logger.error("Cannot process video for upload")
            return

    # Generate caption if missing
    title = reel.get("yt_title")
    desc = reel.get("yt_description")
    tags_str = reel.get("yt_tags")
    if not title or not desc:
        generator = CaptionGenerator(settings)
        meta = generator.generate(reel.get("ig_caption") or "")
        if not meta:
            meta = generator.fallback_metadata()
        title = meta["title"]
        desc = meta["description"]
        tags = meta["hashtags"]
    else:
        tags = tags_str.split(",") if tags_str else []

    uploader = YTUploader(settings)
    video_id = uploader.upload_shorts(
        processed_path,
        title=title,
        description=desc,
        tags=tags,
        privacy="public",
    )

    if video_id:
        db.update_status(
            reel["id"],
            "posted",
            yt_title=title,
            yt_description=desc,
            yt_tags=",".join(tags),
            yt_video_id=video_id,
        )
        logger.info("SUCCESS: https://youtu.be/%s", video_id)
    else:
        logger.error("Upload failed")
    try:
        from tracker.reel_url_store import count_unused
        unused = count_unused()
        logger.info("reels.txt: %d URLs remaining", unused)
    except Exception as e:
        logger.error("Could not check reels.txt: %s", e)


def _test_process(settings, db) -> None:
    _run_processing(settings, db)


def _test_caption(settings, db) -> None:
    _run_caption(settings, db)


def _test_upload(settings, db) -> None:
    _run_upload(settings, db)


if __name__ == "__main__":
    main()
