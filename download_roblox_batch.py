#!/usr/bin/env python3
"""
Downloads queued Roblox Instagram reels into /home/samirkhadka/ytbe/raw_roblox/
and updates manifest.json with local file_path attributes.
"""

import os
import json
import re
import subprocess
import time

BASE_DIR = "/home/samirkhadka/ytbe"
MANIFEST_FILE = os.path.join(BASE_DIR, "manifest.json")
RAW_DIR = os.path.join(BASE_DIR, "raw_roblox")
COOKIES_FILE = "/home/samirkhadka/instagram_cookies.txt"
os.makedirs(RAW_DIR, exist_ok=True)

def main():
    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)

    schedule = manifest["schedule"]
    print(f"Loaded {len(schedule)} total entries from {MANIFEST_FILE}")

    downloaded = 0
    skipped = 0
    failed = 0

    # Collect unique URLs that need download
    for idx, entry in enumerate(schedule):
        if entry.get("type") != "instagram_remix" or not entry.get("instagram_url"):
            continue

        url = entry["instagram_url"]
        m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]{11})/", url)
        if not m:
            continue
        reel_id = m.group(1)
        target_path = os.path.join(RAW_DIR, f"{reel_id}.mp4")

        # If already exists and valid
        if os.path.exists(target_path) and os.path.getsize(target_path) > 100 * 1024:
            if entry.get("file_path") != target_path:
                entry["file_path"] = target_path
            skipped += 1
            continue

        print(f"[{downloaded+1}] Downloading Day {entry.get('day')}: {url} -> {reel_id}.mp4 ...")
        cmd = [
            "yt-dlp", "--no-warnings", "--quiet",
            "--cookies", COOKIES_FILE,
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", target_path,
            url
        ]

        try:
            res = subprocess.run(cmd, timeout=45)
            if res.returncode == 0 and os.path.exists(target_path) and os.path.getsize(target_path) > 100 * 1024:
                sz_mb = os.path.getsize(target_path) / (1024 * 1024)
                print(f"  ✓ Success! ({sz_mb:.1f} MB)")
                entry["file_path"] = target_path
                downloaded += 1
            else:
                print(f"  ✗ Failed to download {url}")
                failed += 1
        except subprocess.TimeoutExpired:
            print(f"  ✗ Timeout downloading {url}")
            failed += 1

        # Periodically save manifest checkpoint
        if downloaded % 5 == 0 and downloaded > 0:
            with open(MANIFEST_FILE, "w") as f:
                json.dump(manifest, f, indent=2)
            print(f"  💾 Checkpoint saved: {downloaded} downloaded, {skipped} existing.")

        time.sleep(1)

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print("\n==========================================")
    print(f"🎉 Download Summary: {downloaded} new, {skipped} existing, {failed} failed.")
    print("==========================================")

if __name__ == "__main__":
    main()
