"""Video processing module - FFmpeg wrapper for YouTube Shorts conversion."""

import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from config.settings import Settings, PipelineError

logger = logging.getLogger(__name__)

FFMPEG_BIN = "ffmpeg"
FFPROBE_BIN = "ffprobe"


class VideoProcessor:
    """Converts Instagram reels to YouTube Shorts format (1080x1920, ≤60s)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._check_ffmpeg()

    # ------------------------------------------------------------------
    # Pre-flight
    # ------------------------------------------------------------------
    @staticmethod
    def _check_ffmpeg() -> None:
        """Verify FFmpeg is installed and available."""
        try:
            subprocess.run(
                [FFMPEG_BIN, "-version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise PipelineError(
                "FFmpeg not found. Install it: https://ffmpeg.org/"
            ) from e

    # ------------------------------------------------------------------
    # Duration check
    # ------------------------------------------------------------------
    @staticmethod
    def get_duration(file_path: str | Path) -> float:
        """Get video duration in seconds using ffprobe."""
        result = subprocess.run(
            [
                FFPROBE_BIN,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------
    def process_video(
        self, input_path: str | Path, output_path: str | Path
    ) -> bool:
        """Convert a video to YouTube Shorts format.

        Args:
            input_path: Path to source .mp4.
            output_path: Path for the converted output.

        Returns:
            True if processing succeeded, False otherwise.
        """
        input_path = Path(input_path)
        output_path = Path(output_path)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            logger.error("Input file not found: %s", input_path)
            return False

        # Check duration - skip processing if already ≤ 60s
        try:
            duration = self.get_duration(input_path)
        except Exception as e:
            logger.warning("Could not determine duration: %s", e)
            duration = 999  # process anyway

        target_w = self.settings.target_width
        target_h = self.settings.target_height
        max_dur = self.settings.max_video_duration

        cmd = [
            FFMPEG_BIN, "-y",
            "-i", str(input_path),
        ]

        if duration > max_dur:
            vf = (
                f"scale={target_w}:{target_h}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:"
                f"(ow-iw)/2:(oh-ih)/2:black"
            )
            cmd.extend(["-t", str(max_dur), "-vf", vf])

        cmd.extend([
            "-c:v", "libx264",
            "-profile:v", "high",
            "-level:v", "4.2",
            "-pix_fmt", "yuv420p",
            "-threads", "2",
            "-crf", "16",
            "-preset", "slow",
            "-maxrate", "30M",
            "-bufsize", "60M",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ])

        logger.info("FFmpeg: %s", " ".join(str(c) for c in cmd))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                stderr_tail = (result.stderr or "")[-1500:]
                stdout_tail = (result.stdout or "")[-500:]
                logger.error("FFmpeg exited with code %d\nstderr tail:\n%s\nstdout tail:\n%s",
                             result.returncode, stderr_tail, stdout_tail)
                return False
            logger.info("Processed: %s -> %s", input_path.name, output_path.name)
            return True
        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timed out after 300s for %s", input_path.name)
            return False
        except Exception as e:
            logger.error("FFmpeg exception: %s", e)
            return False
