#!/usr/bin/env python3
"""Instagram → YouTube Shorts automation bot.

Entry point. Starts APScheduler, health server, and graceful shutdown handlers.
Runs daily at 07:30 IST.
"""

import atexit
import logging
import logging.handlers
import os
import signal
import sys
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import load_settings, ConfigError
from tracker.db import QueueDB
from tracker.reel_url_store import set_data_dir as _init_reel_store, is_stale
from modules.ig_downloader import IGDownloader
from modules.video_processor import VideoProcessor
from modules.caption_generator import CaptionGenerator
from modules.yt_uploader import YTUploader
from modules.telegram_notifier import TelegramNotifier

logger = logging.getLogger("bot")

# ------------------------------------------------------------------
# Lock file to prevent overlapping runs
# ------------------------------------------------------------------
LOCK_FILE = None  # set in main()


def acquire_lock(lock_path: str) -> bool:
    """Try to acquire a file lock. Returns True if acquired."""
    global LOCK_FILE
    try:
        LOCK_FILE = open(lock_path, "x")
        LOCK_FILE.write(str(os.getpid()))
        LOCK_FILE.flush()
        return True
    except FileExistsError:
        return False


def release_lock() -> None:
    global LOCK_FILE
    if LOCK_FILE:
        try:
            lock_path = LOCK_FILE.name
            LOCK_FILE.close()
            Path(lock_path).unlink(missing_ok=True)
        except Exception:
            pass
        LOCK_FILE = None


# ------------------------------------------------------------------
# Pipeline execution
# ------------------------------------------------------------------
def run_pipeline(settings) -> None:
    """Execute one full pipeline cycle: scrape → process → caption → upload."""
    lock_path = str(settings.data_dir / "bot.lock")
    if not acquire_lock(lock_path):
        logger.warning("Previous run still in progress — skipping")
        return

    try:
        logger.info("=" * 50)
        logger.info("Pipeline run started")

        _init_reel_store(settings.data_dir)
        db_path = settings.data_dir / "queue.db"

        if is_stale() and db_path.exists():
            stale_count = QueueDB(db_path).count_total()
            if stale_count > 0:
                db_path.unlink()
                logger.info("Stale queue detected (%d entries) with empty reels_used — reset", stale_count)

        db = QueueDB(db_path)
        telegram = TelegramNotifier(settings)

        # --- Step 1: Refill queue if running low ---
        from tracker.reel_url_store import count_unused
        unused = count_unused()
        pending_count = db.count_by_status("downloaded")
        processed_count = db.count_by_status("processed")
        caption_ready_count = db.count_by_status("caption_ready")
        ready_for_upload = processed_count + caption_ready_count
        total_in_pipeline = db.count_active()

        logger.info(
            "Queue: %d total | downloaded: %d | processed: %d | caption_ready: %d | reels.txt unused: %d",
            total_in_pipeline,
            pending_count,
            processed_count,
            caption_ready_count,
            unused,
        )

        if total_in_pipeline < settings.queue_refill_threshold:
            if unused > 0:
                logger.info("Queue low (%d), downloading next from reels.txt...", total_in_pipeline)
                try:
                    downloader = IGDownloader(settings, db)
                    shortcode = downloader.download_next_reel()
                    if shortcode:
                        logger.info("Added to queue: %s", shortcode)
                except Exception as e:
                    logger.error("Download failed: %s", e)
                    telegram.on_error("download", "unknown", str(e))
            else:
                logger.warning("reels.txt is empty — no URLs remaining")
                telegram.on_skip("reels.txt is empty")

        # --- Step 2: Process videos ---
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
                logger.info("Processed: %s", shortcode)
            else:
                db.update_status(reel["id"], "failed", error_msg="Processing failed")
                telegram.on_error("process", shortcode, "FFmpeg processing failed")
            reel = db.get_next_pending()

        # --- Step 3: Generate captions ---
        generator = CaptionGenerator(settings)
        reel = db.get_next_processed()
        while reel:
            ig_caption = reel.get("ig_caption") or ""
            meta = generator.generate(ig_caption)
            if not meta:
                meta = generator.fallback_metadata()
                logger.warning("Using fallback caption for %s", reel["ig_shortcode"])

            db.update_status(
                reel["id"],
                "caption_ready",
                yt_title=meta["title"],
                yt_description=meta["description"],
                yt_tags=",".join(meta["hashtags"]),
            )
            logger.info("Caption generated for %s: %s", reel["ig_shortcode"], meta["title"])
            reel = db.get_next_processed()

        # --- Step 4: Upload 1 video ---
        uploader = YTUploader(settings)
        reel = db.get_next_caption_ready()
        if reel:
            processed_path = reel.get("processed_path")
            if processed_path and Path(processed_path).exists():
                title = reel["yt_title"]
                desc = reel["yt_description"]
                tags = reel["yt_tags"].split(",") if reel.get("yt_tags") else []

                # Upload as public
                try:
                    video_id = uploader.upload_shorts(
                        processed_path,
                        title=title,
                        description=desc,
                        tags=tags,
                    )
                    if video_id:
                        db.update_status(reel["id"], "posted", yt_video_id=video_id)
                        logger.info("UPLOADED: https://youtu.be/%s", video_id)
                        telegram.on_upload(title, video_id)
                except Exception as e:
                    logger.error("Upload failed: %s", e)
                    db.update_status(reel["id"], "failed", error_msg=str(e))
                    telegram.on_error("upload", reel["ig_shortcode"], str(e))
            else:
                logger.warning("Processed file missing for reel #%d", reel["id"])
                db.update_status(reel["id"], "failed", error_msg="File missing at upload time")
        else:
            logger.info("No videos ready for upload today")

        # --- Step 5: Cleanup old video files ---
        _cleanup_videos(settings, db)

        logger.info("Pipeline run completed successfully")
    except Exception as e:
        logger.exception("Unhandled pipeline error: %s", e)
    finally:
        release_lock()


def _cleanup_videos(settings, db) -> None:
    """Delete raw files for posted/failed reels to save space."""
    for status in ("posted", "failed"):
        reel = db._fetchone(
            "SELECT raw_path, processed_path FROM queue WHERE status = ? AND raw_path IS NOT NULL LIMIT 5;",
            (status,),
        )
        while reel:
            for path_key in ("raw_path", "processed_path"):
                p = reel[path_key]
                if p and Path(p).exists():
                    Path(p).unlink(missing_ok=True)
                    logger.debug("Cleaned up: %s", p)
            reel = db._fetchone(
                "SELECT raw_path, processed_path FROM queue WHERE status = ? AND raw_path IS NOT NULL LIMIT 5;",
                (status,),
            )


# ------------------------------------------------------------------
# Health server (Railway requires HTTP listener)
# ------------------------------------------------------------------
def _start_health_server(port: int, settings=None, trigger_fn=None) -> None:
    """Start a minimal HTTP server for Railway health checks + /trigger."""
    import http.server
    import socketserver
    import json as json_module

    class HealthHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/trigger" and trigger_fn:
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                import threading
                t = threading.Thread(target=trigger_fn, args=[settings], daemon=True)
                t.start()
                self.wfile.write(json_module.dumps({"status": "triggered"}).encode())
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"ok","bot":"yt-shorts-bot"}')

        def log_message(self, *_) -> None:
            pass

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True
        allow_reuse_port = True

    try:
        server = ReusableTCPServer(("0.0.0.0", port), HealthHandler)
        server.timeout = 1
        logger.info("Health server listening on port %d", port)
        while True:
            server.handle_request()
    except Exception as e:
        logger.warning("Health server error: %s", e)


# ------------------------------------------------------------------
# Graceful shutdown
# ------------------------------------------------------------------
_shutting_down = False


def _handle_signal(signum, frame) -> None:
    global _shutting_down
    if _shutting_down:
        logger.warning("Forced exit")
        sys.exit(1)
    _shutting_down = True
    logger.info("Shutting down gracefully...")
    release_lock()
    sys.exit(0)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
def main() -> None:
    # Load config (fails fast if env vars missing)
    try:
        settings = load_settings()
    except ConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    log_path = settings.log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    rotating = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    console = logging.StreamHandler()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[rotating, console],
    )

    logger.info("Bot starting — target: %s, cron: %02d:%02d %s",
                settings.ig_target, settings.cron_hour, settings.cron_minute,
                settings.cron_timezone)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    atexit.register(release_lock)

    # Start health server in background (serves /trigger too)
    import threading
    health_thread = threading.Thread(
        target=_start_health_server,
        args=(settings.port, settings, run_pipeline),
        daemon=True,
    )
    health_thread.start()

    # Schedule daily pipeline (first run at 07:30 IST tomorrow)
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(
            hour=settings.cron_hour,
            minute=settings.cron_minute,
            timezone=settings.cron_timezone,
        ),
        args=[settings],
        id="daily_pipeline",
        name="Daily Instagram→YouTube pipeline",
    )

    scheduler.start()
    logger.info("Scheduler started — next run at %02d:%02d %s",
                settings.cron_hour, settings.cron_minute, settings.cron_timezone)

    # One-shot trigger: if TRIGGER_NOW is set, run pipeline immediately
    if os.getenv("TRIGGER_NOW", "").lower() in ("1", "true", "yes"):
        logger.info("TRIGGER_NOW detected — running pipeline immediately")
        t = threading.Thread(target=run_pipeline, args=[settings], daemon=True)
        t.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        _handle_signal(None, None)


if __name__ == "__main__":
    main()

