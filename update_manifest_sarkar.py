#!/usr/bin/env python3
"""
Expands manifest_sarkar.json from /home/samirkhadka/sh_sarkar/reels_urls.txt
Generates high-CTR gaming titles, tags, and daily schedule timestamps.
"""

import os
import json
import re
from datetime import datetime, timedelta, timezone

BASE_DIR = "/home/samirkhadka/ytbe"
MANIFEST_FILE = os.path.join(BASE_DIR, "manifest_sarkar.json")
URLS_FILE = "/home/samirkhadka/sh_sarkar/reels_urls.txt"
RAW_DIR = "/home/samirkhadka/sh_sarkar/raw"

HOOK_TITLES = [
    "M1887 ONE TAP GOD ⚡🔥 #Shorts",
    "INSANE FAST GLOO WALL 🛡️💨 #Shorts",
    "DESERT EAGLE HEADSHOT KING 🎯👑 #Shorts",
    "BRAZIL STYLE FREESTYLE 🇧🇷⚡ #Shorts",
    "SMOOTH MONTAGE HIGHLIGHTS 🎮✨ #Shorts",
    "NO RECOIL HEADSHOT BURST 💥🎯 #Shorts",
    "CUSTOM ROOM 1v4 CLUTCH 🏆🔥 #Shorts",
    "FASTEST FINGERS IN FREE FIRE ⚡📱 #Shorts",
    "SNIPER QUICK SCOPE UNREAL 🎯💀 #Shorts",
    "MP40 SQUAD WIPE HIGHLIGHTS 🌪️🔥 #Shorts",
    "JUMP SHOT HEADSHOT ACCURACY 🏹🎯 #Shorts",
    "SMOOTH DPI SENSITIVITY HIGHLIGHTS ⚡📲 #Shorts",
    "UNSTOPPABLE 1v1 DUEL ⚔️🔥 #Shorts",
    "PRO PLAYER MOVEMENT MONTAGE 🏃‍♂️💨 #Shorts",
    "MAX DAMAGE HEADSHOT ONLY 🩸🎯 #Shorts"
]

def main():
    if not os.path.exists(URLS_FILE):
        print(f"Error: {URLS_FILE} not found!")
        return

    with open(URLS_FILE) as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(urls)} URLs from {URLS_FILE}")

    # Load existing manifest if present
    existing_schedule = {}
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE) as f:
            data = json.load(f)
            for item in data.get("schedule", []):
                existing_schedule[item["instagram_url"]] = item

    schedule = []
    start_date = datetime(2026, 11, 19, 11, 0, tzinfo=timezone.utc)

    for i, url in enumerate(urls, 1):
        reel_id_m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]{11})/", url)
        reel_id = reel_id_m.group(1) if reel_id_m else f"reel_{i}"
        
        # Check if already scheduled
        if url in existing_schedule:
            entry = existing_schedule[url]
            entry["day"] = i
            entry["scheduled_time"] = (start_date + timedelta(days=i-1)).strftime("%Y-%m-%d %H:%M UTC")
            schedule.append(entry)
            continue

        raw_file = os.path.join(RAW_DIR, f"{reel_id}.mp4")
        has_local = os.path.exists(raw_file)
        
        hook = HOOK_TITLES[(i - 1) % len(HOOK_TITLES)]
        if i > len(HOOK_TITLES):
            hook_base = hook.replace(" #Shorts", "")
            hook = f"{hook_base} (Part {i}) #Shorts"

        entry = {
            "day": i,
            "type": "instagram_remix",
            "account": "sameer_exc",
            "reel_id": reel_id,
            "instagram_url": url,
            "file_path": raw_file if has_local else None,
            "title": hook,
            "description": (
                f"{hook}\n\n"
                "Rate this Free Fire freestyle montage from 1 to 10 in the comments! 👇\n\n"
                "🔔 Subscribe to @SHSARKAR for daily Free Fire montages, fast gloo walls, and insane headshot highlights!\n\n"
                "#freefire #shorts #freefirehighlights #freefiremobile #gaming #viral #fyp #trending #shsarkar #headshot #freestyle"
            ),
            "tags": [
                "freefire",
                "shorts",
                "freefirehighlights",
                "freefiremobile",
                "gaming",
                "viral",
                "fyp",
                "trending",
                "shsarkar",
                "headshot",
                "freestyle",
                "m1887",
                "gloowall"
            ],
            "scheduled_time": (start_date + timedelta(days=i-1)).strftime("%Y-%m-%d %H:%M UTC"),
            "status": "queued"
        }
        schedule.append(entry)

    manifest = {
        "version": "1.0.0",
        "channel": "SH SARKAR",
        "channel_id": "UCN5kwanpmxeRNKeqs-4fzMQ",
        "total_days": len(schedule),
        "timezone": "UTC",
        "schedule": schedule
    }

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Successfully wrote {len(schedule)} queued days into {MANIFEST_FILE}!")

if __name__ == "__main__":
    main()
