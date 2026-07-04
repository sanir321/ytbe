#!/usr/bin/env python3
"""Tests for modules/video_processor.py - FFmpeg wrapper for Shorts conversion."""
import json
import logging
import subprocess
from pathlib import Path

import pytest
from modules.video_processor import VideoProcessor
from config.settings import PipelineError

logger = logging.getLogger(__name__)


def ffmpeg_available():
    """Check if ffmpeg is available on this system."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


class TestCheckFFmpeg:
    def test_ffmpeg_available_or_skip(self):
        """FFmpeg should be available. Skip cleanly if not."""
        if not ffmpeg_available():
            pytest.skip("FFmpeg not installed on this system")
        VideoProcessor._check_ffmpeg()  # Should not raise

    def test_ffmpeg_not_found_raises(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found"))
        with pytest.raises(PipelineError, match="FFmpeg not found"):
            VideoProcessor._check_ffmpeg()



# Use fixture in older-style to avoid pytest collection issues
@pytest.fixture
def settings(mocker):
    s = mocker.Mock()
    s.max_video_duration = 60
    s.target_width = 1080
    s.target_height = 1920
    return s


def _create_short_video(tmp_path):
    path = tmp_path / "input_short.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=blue:s=640x640:d=10:r=30",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
         "-c:a", "aac", "-shortest",
         str(path)],
        capture_output=True, check=True,
    )
    return path


def _create_long_video(tmp_path):
    path = tmp_path / "input_long.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", "color=c=red:s=720x1280:d=90:r=30",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
         "-c:a", "aac", "-shortest",
         str(path)],
        capture_output=True, check=True,
    )
    return path


class TestProcessVideo:
    def test_process_short_video_reencodes(self, settings, tmp_path, mocker):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        short_video = _create_short_video(tmp_path)
        output = tmp_path / "output_short.mp4"

        ffprobe_out = mocker.Mock(returncode=0, stdout='{"format":{"duration":"15.0"}}', stderr="")
        ffmpeg_out = mocker.Mock(returncode=0)
        mocker.patch("subprocess.run", side_effect=[ffmpeg_out, ffprobe_out, ffmpeg_out])

        proc = VideoProcessor(settings)
        result = proc.process_video(short_video, output)
        assert result is True
        call_args = subprocess.run.call_args[0][0]
        assert "-c:v" in call_args
        assert "libx264" in call_args

    def test_process_long_video_trims(self, settings, tmp_path):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        long_video = _create_long_video(tmp_path)
        output = tmp_path / "output_long.mp4"
        proc = VideoProcessor(settings)
        result = proc.process_video(long_video, output)
        assert result is True
        assert output.exists()
        info = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(output)],
            capture_output=True, text=True, check=True,
        )
        dur = float(json.loads(info.stdout)["format"]["duration"])
        assert dur <= 61

    def test_process_long_video_proper_dimensions(self, settings, tmp_path):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        long_video = _create_long_video(tmp_path)
        output = tmp_path / "output_dim.mp4"
        proc = VideoProcessor(settings)
        proc.process_video(long_video, output)
        info = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(output)],
            capture_output=True, text=True, check=True,
        )
        streams = json.loads(info.stdout)["streams"]
        vs = [s for s in streams if s["codec_type"] == "video"][0]
        assert vs["width"] == 1080
        assert vs["height"] == 1920

    def test_process_nonexistent_input(self, settings, tmp_path):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        output = tmp_path / "output.mp4"
        proc = VideoProcessor(settings)
        result = proc.process_video(tmp_path / "nonexistent.mp4", output)
        assert result is False

    def test_process_invalid_input(self, settings, tmp_path):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        input_file = tmp_path / "invalid.txt"
        input_file.write_text("not a video")
        output = tmp_path / "output.mp4"
        proc = VideoProcessor(settings)
        result = proc.process_video(input_file, output)
        assert result is False


class TestAspectRatioConversion:
    def test_square_to_portrait(self, settings, tmp_path, mocker):
        if not ffmpeg_available():
            pytest.skip("FFmpeg not available")
        short_video = _create_short_video(tmp_path)
        output = tmp_path / "padded.mp4"
        original_run = subprocess.run
        mocker.patch("subprocess.run", side_effect=lambda *a, **kw: (
            mocker.Mock(returncode=0, stdout='{"format":{"duration":"90.0"}}', stderr="")
            if any("-show_format" in str(x) for x in a[0])
            else original_run(*a, **kw)
        ))
        proc = VideoProcessor(settings)
        proc.process_video(short_video, output)
        info = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", str(output)],
            capture_output=True, text=True, check=True,
        )
        vs = [s for s in json.loads(info.stdout)["streams"] if s["codec_type"] == "video"][0]
        assert vs["width"] == 1080
        assert vs["height"] == 1920
