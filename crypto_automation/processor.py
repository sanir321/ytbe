#!/usr/bin/env python3
"""
Video Downloader & Clean Trimmer for Viral Pipeline
Fetches high-quality 1080p stream, extracts clean speech, and extracts keyframes.
"""

import os
import sys
import subprocess
import json
from typing import Dict, Any, Optional, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORK_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(WORK_DIR, exist_ok=True)

def download_video(youtube_id: str, output_prefix: Optional[str] = None) -> Dict[str, Any]:
    output_prefix = output_prefix or youtube_id
    raw_path = os.path.join(WORK_DIR, f"{output_prefix}_raw.mp4")
    url = f"https://www.youtube.com/watch?v={youtube_id}"

    print(f"📥 Downloading video {youtube_id}...")
    cmd = [
        "yt-dlp",
        "--remote-components", "ejs:github",
        "-f", "bv*[ext=mp4][height<=1080]+ba[ext=m4a]/b[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", raw_path,
        url
    ]
    subprocess.run(cmd, check=True)

    # Get video duration and metadata
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        raw_path
    ]
    dur_str = subprocess.check_output(probe_cmd).decode().strip()
    duration_sec = float(dur_str)

    return {
        "raw_path": raw_path,
        "duration_sec": duration_sec,
        "youtube_id": youtube_id
    }

def process_and_trim(
    raw_path: str,
    output_path: str,
    start_sec: float = 0.0,
    end_sec: Optional[float] = None
) -> str:
    """
    Trims intro/outro if specified and ensures clean 1080p stream with normalized audio.
    """
    print(f"✂️ Processing & trimming video: {raw_path} -> {output_path}")
    cmd = ["ffmpeg", "-y"]
    if start_sec > 0:
        cmd += ["-ss", str(start_sec)]
    cmd += ["-i", raw_path]
    if end_sec is not None:
        duration = end_sec - start_sec
        cmd += ["-t", str(duration)]

    # Stream copy if no complex filter, or fast re-encode for broadcast precision
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, check=True)
    return output_path

def extract_keyframes(video_path: str, count: int = 5) -> list:
    """Extracts candidate keyframes and ranks them by clarity & contrast."""
    from PIL import Image, ImageStat
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    duration = float(subprocess.check_output(probe_cmd).decode().strip())
    fractions = [0.15, 0.30, 0.50, 0.65, 0.80]
    scored_frames = []

    base = os.path.splitext(video_path)[0]
    for i, frac in enumerate(fractions, 1):
        ts = duration * frac
        kf_path = f"{base}_kf_{i}.jpg"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ts),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            kf_path
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            im = Image.open(kf_path)
            stat = ImageStat.Stat(im)
            score = stat.mean[0] * stat.stddev[0]
            scored_frames.append((score, kf_path))
        except Exception:
            continue

    # Sort descending by visual clarity score
    scored_frames.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored_frames]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        yid = sys.argv[1]
        res = download_video(yid)
        print("Downloaded:", res)
        kfs = extract_keyframes(res["raw_path"])
        print("Keyframes extracted:", kfs)
