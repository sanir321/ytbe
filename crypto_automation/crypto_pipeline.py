#!/usr/bin/env python3
"""
Autonomous Crypto Video Pipeline
End-to-end generator: Real-time price tracking -> High-retention script -> Edge-TTS -> FFmpeg vertical video.
Supports optional dual-upload to Rumble & YouTube.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)
sys.path.append("/home/samirkhadka/ytbe")

from crypto_script import generate_script
from crypto_tts import build_tts
from crypto_video import create_crypto_video

MANIFEST_PATH = os.path.join(PROJECT_DIR, "manifest_crypto.json")

def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"version": "1.0.0", "niche": "cryptocurrency", "videos": []}

def save_manifest(data):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def run_pipeline(publish_rumble: bool = False, publish_youtube: bool = False, license_tier: str = "6"):
    print("=" * 60)
    print("⚡ LAUNCHING AUTONOMOUS CRYPTO SHORTS ENGINE")
    print("=" * 60)

    # 1. Generate real-time script & metadata
    print("\n[1/4] Pulling live market metrics and generating script...")
    meta = generate_script()
    title = meta["title"]
    description = meta["description"]
    tags = meta["tags"]
    btc_price = meta["btc_price"]
    btc_change = meta["btc_change"]
    
    print(f"📌 Title: {title}")
    print(f"💰 BTC Ticker: ${btc_price} ({btc_change}%)")

    # 2. Audio & Subtitles
    timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(PROJECT_DIR, "output")
    os.makedirs(out_dir, exist_ok=True)
    
    audio_file = os.path.join(out_dir, f"audio_{timestamp_slug}.mp3")
    srt_file = os.path.join(out_dir, f"subtitles_{timestamp_slug}.srt")
    video_file = os.path.join(out_dir, f"crypto_short_{timestamp_slug}.mp4")

    print("\n[2/4] Generating high-energy voiceover via Edge-TTS...")
    build_tts(meta["script_text"], audio_file, srt_file)
    print(f"✅ Audio generated: {os.path.getsize(audio_file) / 1024:.1f} KB")

    # 3. Video Rendering
    print("\n[3/4] Rendering 1080x1920 vertical video with live candlestick charts...")
    create_crypto_video(audio_file, srt_file, btc_price, btc_change, video_file)
    file_mb = round(os.path.getsize(video_file) / (1024 * 1024), 2)
    print(f"✅ Video ready: {video_file} ({file_mb} MB)")

    entry = {
        "id": timestamp_slug,
        "title": title,
        "description": description,
        "tags": tags,
        "video_file": video_file,
        "file_size_mb": file_mb,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ready"
    }

    # 4. Optional Publishing
    if publish_rumble:
        print("\n[4/4] Uploading to Rumble under Tier 6 (Exclusive with Management)...")
        try:
            from rumble_api import RumbleAPI
            ra = RumbleAPI()
            res = ra.upload_video(
                video_path=video_file,
                title=title,
                description=description,
                tags=tags,
                channel_id="7985034",
                license_tier=license_tier
            )
            if res.get("ok"):
                entry["rumble_url"] = res.get("url")
                entry["rumble_fid"] = res.get("fid")
                entry["rumble_status"] = "published"
                print(f"🎉 RUMBLE PUBLISH SUCCESS: {res.get('url')}")
            else:
                print(f"⚠️ Rumble upload error: {res.get('error')}")
        except Exception as e:
            print(f"⚠️ Rumble client error: {e}")

    manifest = load_manifest()
    manifest["videos"].append(entry)
    save_manifest(manifest)
    print(f"\n[MANIFEST] Saved video record to {MANIFEST_PATH}")
    print("=" * 60)
    print("🏁 PIPELINE EXECUTION COMPLETE")
    print("=" * 60)
    return entry

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Crypto Short Pipeline")
    parser.add_argument("--publish-rumble", action="store_true", help="Publish directly to Rumble under Tier 6")
    parser.add_argument("--publish-youtube", action="store_true", help="Publish directly to YouTube")
    args = parser.parse_args()

    run_pipeline(publish_rumble=args.publish_rumble, publish_youtube=args.publish_youtube)
