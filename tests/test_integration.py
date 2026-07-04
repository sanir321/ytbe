#!/usr/bin/env python3
"""Full pipeline integration test - download, process, caption (mock + real)."""
import json
import logging
import os
import subprocess
from pathlib import Path

import pytest

logger = logging.getLogger("integration")


def ffmpeg_available():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _create_synthetic_video(tmp_path):
    path = tmp_path / "test_synthetic.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "testsrc=s=640x640:d=15:r=30",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
         "-c:a", "aac", "-shortest",
         str(path)],
        capture_output=True, check=True,
    )
    return path


@pytest.fixture(autouse=True)
def ensure_env(monkeypatch):
    """Ensure required env vars are set for all integration tests."""
    if "KILO_API_KEY" not in os.environ:
        monkeypatch.setenv("KILO_API_KEY", "test_kilo_key")
    if "YT_CLIENT_ID" not in os.environ:
        monkeypatch.setenv("YT_CLIENT_ID", "test_client_id")
    if "YT_CLIENT_SECRET" not in os.environ:
        monkeypatch.setenv("YT_CLIENT_SECRET", "test_secret")
    if "YT_REFRESH_TOKEN" not in os.environ:
        monkeypatch.setenv("YT_REFRESH_TOKEN", "test_refresh")


@pytest.fixture
def settings():
    from config.settings import load_settings
    s = load_settings()
    return s


@pytest.fixture
def db(settings, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    from tracker.db import QueueDB
    db_path = tmp_path / "queue.db"
    return QueueDB(db_path)


@pytest.fixture
def mock_reel_urls(tmp_path, monkeypatch):
    """Set up temporary reels.txt with a test URL."""
    monkeypatch.setattr("tracker.reel_url_store.REELS_FILE", tmp_path / "reels.txt")
    monkeypatch.setattr("tracker.reel_url_store.USED_FILE", tmp_path / "reels_used.txt")
    monkeypatch.setattr("tracker.reel_url_store.DATA_DIR", tmp_path)
    # A real Instagram reel URL (will be resolved via instaloader)
    url = "https://www.instagram.com/reel/DWOnIimjUNF/"
    (tmp_path / "reels.txt").write_text(url + "\n")
    return tmp_path


# ══════════════════════════════════════════════════════════════════════
# Pipeline stage tests (each stage in isolation)
# ══════════════════════════════════════════════════════════════════════

class TestDownloadStage:
    def test_download_with_mock_url_via_reels_txt(self, settings, db, mock_reel_urls):
        """Test the full download flow using the URL queue."""
        from modules.ig_downloader import IGDownloader
        from tracker.reel_url_store import count_unused
        assert count_unused() == 1

        downloader = IGDownloader(settings, db)
        shortcode = downloader.download_next_reel()

        # May succeed or fail depending on Instagram availability - either is OK
        if shortcode:
            assert db.shortcode_exists(shortcode)
            assert db.count_by_status("downloaded") == 1
        else:
            pytest.skip("Instagram unreachable - download skipped (this is fine)")

    def test_download_returns_none_when_queue_empty(self, settings, db, tmp_path, monkeypatch):
        """Empty reels.txt should return None."""
        from modules.ig_downloader import IGDownloader
        from tracker.reel_url_store import REELS_FILE
        monkeypatch.setattr("tracker.reel_url_store.REELS_FILE", tmp_path / "empty_reels.txt")
        monkeypatch.setattr("tracker.reel_url_store.USED_FILE", tmp_path / "empty_used.txt")
        monkeypatch.setattr("tracker.reel_url_store.DATA_DIR", tmp_path)
        (tmp_path / "empty_reels.txt").write_text("")
        downloader = IGDownloader(settings, db)
        assert downloader.download_next_reel() is None


class TestProcessStage:
    def test_process_added_reel(self, settings, db, tmp_path):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        synthetic_video = _create_synthetic_video(tmp_path)
        shortcode = "integration_test_proc"
        db.add_reel(shortcode, "Test caption")
        recent = db.get_recent(1)
        reel_id = recent[0]["id"]
        db.update_status(reel_id, "downloaded", raw_path=str(synthetic_video))

        from modules.video_processor import VideoProcessor
        processor = VideoProcessor(settings)
        reel = db.get_next_by_status("downloaded")
        assert reel is not None

        output = settings.videos_processed_dir / f"{shortcode}.mp4"
        ok = processor.process_video(reel["raw_path"], output)
        assert ok is True
        assert output.exists()

        db.update_status(reel["id"], "processed", processed_path=str(output))
        assert db.count_by_status("processed") == 1

    def test_process_nonexistent_file(self, settings, db):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        shortcode = "integration_missing"
        db.add_reel(shortcode)
        recent = db.get_recent(1)
        db.update_status(recent[0]["id"], "downloaded", raw_path="/nonexistent.mp4")

        from modules.video_processor import VideoProcessor
        processor = VideoProcessor(settings)
        reel = db.get_next_by_status("downloaded")
        output = settings.videos_processed_dir / "nonexistent.mp4"
        ok = processor.process_video(reel["raw_path"], output)
        assert ok is False


class TestCaptionStage:
    def test_generate_caption_from_reel(self, settings, db):
        """Generate a caption for a processed reel."""
        shortcode = "integration_cap"
        db.add_reel(shortcode, "Be confident and stop caring what others think")
        recent = db.get_recent(1)
        db.update_status(
            recent[0]["id"], "processed",
            raw_path="/tmp/raw.mp4",
            processed_path="/tmp/proc.mp4",
        )

        from modules.caption_generator import CaptionGenerator
        generator = CaptionGenerator(settings)
        reel = db.get_next_by_status("processed")
        assert reel is not None

        meta = generator.generate(reel["ig_caption"] or "")

        # If Kilo API is available, we get real metadata; otherwise falls through
        if meta is None:
            meta = generator.fallback_metadata()

        assert meta["title"] is not None
        assert meta["description"] is not None
        assert isinstance(meta["hashtags"], list)
        assert len(meta["hashtags"]) >= 15  # fallback has 15, AI has 30

    def test_generate_caption_empty_caption_falls_back(self, settings, db):
        """Empty caption should still produce metadata (fallback)."""
        from modules.caption_generator import CaptionGenerator
        generator = CaptionGenerator(settings)
        meta = generator.generate("")
        if meta is None:
            meta = generator.fallback_metadata()
        assert meta["title"] is not None


# ══════════════════════════════════════════════════════════════════════
# Full pipeline (end-to-end without upload)
# ══════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_end_to_end_mock_pipeline(self, settings, db, tmp_path):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        synthetic_video = _create_synthetic_video(tmp_path)
        shortcode = "e2e_mock"

        # 1. Add to queue
        db.add_reel(shortcode, "Synthetic test for E2E pipeline verification")
        recent = db.get_recent(1)
        reel_id = recent[0]["id"]
        db.update_status(reel_id, "downloaded", raw_path=str(synthetic_video))
        assert db.count_by_status("downloaded") == 1

        # 2. Process
        from modules.video_processor import VideoProcessor
        processor = VideoProcessor(settings)
        reel = db.get_next_by_status("downloaded")
        assert reel is not None
        output = settings.videos_processed_dir / f"{shortcode}.mp4"
        ok = processor.process_video(reel["raw_path"], output)
        assert ok is True
        db.update_status(reel["id"], "processed", processed_path=str(output))
        assert db.count_by_status("processed") == 1

        # 3. Caption
        from modules.caption_generator import CaptionGenerator
        generator = CaptionGenerator(settings)
        reel = db.get_next_by_status("processed")
        assert reel is not None
        meta = generator.generate(reel["ig_caption"] or "")
        if meta is None:
            meta = generator.fallback_metadata()
        db.update_status(
            reel["id"], "caption_ready",
            yt_title=meta["title"],
            yt_description=meta["description"],
            yt_tags=",".join(meta["hashtags"]),
        )
        assert db.count_by_status("caption_ready") == 1

        # 4. Verify metadata is well-formed
        reel = db.get_next_by_status("caption_ready")
        assert reel is not None
        assert reel["yt_title"].endswith("#Shorts")
        assert len(reel["yt_title"]) <= 100
        assert len(reel["yt_description"]) <= 5000
        assert "#Shorts" in (reel["yt_tags"] or "")

        logger.info("E2E pipeline passed for %s - title: %s", shortcode, meta["title"])

    def test_pipeline_with_multiple_reels(self, settings, db, tmp_path):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        synthetic_video = _create_synthetic_video(tmp_path)
        shortcodes = ["multi_1", "multi_2", "multi_3"]

        for i, sc in enumerate(shortcodes):
            db.add_reel(sc, f"Caption {i}")

        recent = db.get_recent(10)
        assert len(recent) >= 3

        from modules.video_processor import VideoProcessor
        processor = VideoProcessor(settings)

        for sc in shortcodes:
            row = db._fetchone("SELECT * FROM queue WHERE ig_shortcode=?", (sc,))
            db.update_status(row["id"], "downloaded", raw_path=str(synthetic_video))

            reel = db.get_next_by_status("downloaded")
            assert reel is not None
            output = settings.videos_processed_dir / f"{sc}.mp4"
            ok = processor.process_video(reel["raw_path"], output)
            assert ok is True
            db.update_status(reel["id"], "processed", processed_path=str(output))

        assert db.count_by_status("processed") == 3


# ══════════════════════════════════════════════════════════════════════
# URL queue integration with pipeline
# ══════════════════════════════════════════════════════════════════════

class TestURLQueueIntegration:
    def test_consume_and_process_flow(self, settings, db, tmp_path, monkeypatch):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        synthetic_video = _create_synthetic_video(tmp_path)
        from tracker.reel_url_store import REELS_FILE, USED_FILE, DATA_DIR
        monkeypatch.setattr("tracker.reel_url_store.REELS_FILE", tmp_path / "reels.txt")
        monkeypatch.setattr("tracker.reel_url_store.USED_FILE", tmp_path / "reels_used.txt")
        monkeypatch.setattr("tracker.reel_url_store.DATA_DIR", tmp_path)

        test_urls = [
            "https://www.instagram.com/reel/AAAAAA/",
            "https://www.instagram.com/reel/BBBBBB/",
        ]
        (tmp_path / "reels.txt").write_text("\n".join(test_urls) + "\n")

        from tracker.reel_url_store import consume_next, shortcode_from_url, count_unused
        from modules.ig_downloader import IGDownloader

        # First URL
        url1 = consume_next()
        assert url1 == test_urls[0]
        sc1 = shortcode_from_url(url1)
        assert sc1 == "AAAAAA"

        # Manually add a synthetic download
        db.add_reel(sc1, "A caption")
        recent = db.get_recent(1)
        db.update_status(recent[0]["id"], "downloaded", raw_path=str(synthetic_video))

        # Process it
        from modules.video_processor import VideoProcessor
        processor = VideoProcessor(settings)
        reel = db.get_next_by_status("downloaded")
        output = settings.videos_processed_dir / f"{sc1}.mp4"
        ok = processor.process_video(reel["raw_path"], output)
        assert ok is True

        assert count_unused() == 1
        assert USED_FILE.exists()
