#!/usr/bin/env python3
"""
Expands manifest_sarkar.json from /home/samirkhadka/sh_sarkar/reels_urls.txt
Preserves historical published entries (Days 1 to 16) and schedules 1 reel per day for new URLs.
"""

import os
import json
import re
from datetime import datetime, timedelta

BASE_DIR = "/home/samirkhadka/ytbe"
MANIFEST_FILE = os.path.join(BASE_DIR, "manifest_sarkar.json")
URLS_FILE = "/home/samirkhadka/sh_sarkar/reels_urls.txt"

HOOK_TITLES = [
    "FASTEST ONE TAP HEADSHOT ⚡🔥 #Shorts",
    "M1887 MOVEMENT KING 🏃‍♂️💨 #Shorts",
    "SMOOTH DPI SENSITIVITY HIGHLIGHTS 🎮📱 #Shorts",
    "INSANE 1v4 CUSTOM ROOM CLUTCH 🏆💀 #Shorts",
    "DESERT EAGLE HEADSHOT GOD 🎯👑 #Shorts",
    "BRAZIL STYLE FREESTYLE MONTAGE 🇧🇷⚡ #Shorts",
    "FASTEST GLOO WALL IN FREE FIRE 🛡️⚡ #Shorts",
    "MP40 SQUAD WIPE HIGHLIGHTS 🌪️🔥 #Shorts",
    "UNSTOPPABLE 1v1 DUEL ⚔️🔥 #Shorts",
    "SNIPER QUICK SCOPE UNREAL 🎯💀 #Shorts",
    "MAX DAMAGE ONLY RED NUMBERS 🩸🎯 #Shorts",
    "PRO PLAYER MOVEMENT HIGHLIGHTS 🏃‍♂️⚡ #Shorts",
    "INSANE FASTEST DRAG HEADSHOT 🏹💥 #Shorts",
    "SMOOTH MONTAGE HIGHLIGHTS 🎮✨ #Shorts",
    "NO RECOIL HEADSHOT BURST 💥🎯 #Shorts"
]

def main():
    if not os.path.exists(URLS_FILE):
        print(f"Error: {URLS_FILE} not found!")
        return

    with open(URLS_FILE) as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"Loaded {len(urls)} URLs from {URLS_FILE}")

    past_entries = []
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE) as f:
            old_manifest = json.load(f)
            past_entries = [entry for entry in old_manifest.get("schedule", []) if entry.get("day", 0) <= 16]

    start_date = datetime(2026, 11, 27)
    slots = ["06:30 UTC", "12:30 UTC"]

    new_entries = []
    for idx, url in enumerate(urls):
        day_num = 17 + idx
        reel_id_m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]{11})/", url)
        reel_id = reel_id_m.group(1) if reel_id_m else f"reel_{day_num}"

        day_offset = idx
        slot = slots[idx % len(slots)]
        sched_dt = start_date + timedelta(days=day_offset)
        sched_str = f"{sched_dt.strftime('%Y-%m-%d')} {slot}"

        hook_base = HOOK_TITLES[idx % len(HOOK_TITLES)]
        clean_hook = hook_base.replace(" #Shorts", "")
        title = f"{clean_hook} (Part {idx + 1}) #Shorts"

        entry = {
            "day": day_num,
            "type": "instagram_remix",
            "account": "erenexeff",
            "reel_id": reel_id,
            "instagram_url": url,
            "file_path": None,
            "title": title,
            "description": (
                f"{title}\n\n"
                "Rate this Free Fire insane movement and headshot montage 1 to 10 in comments! 👇\n\n"
                "🔔 Subscribe to @SHSARKAR for daily Free Fire montages, fast gloo walls, and pro gameplay!\n\n"
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
            "scheduled_time": sched_str,
            "status": "queued"
        }
        new_entries.append(entry)

    final_schedule = past_entries + new_entries

    manifest = {
        "version": "2.0.0",
        "channel": "SH SARKAR",
        "channel_id": "UCN5kwanpmxeRNKeqs-4fzMQ",
        "total_days": len(final_schedule),
        "timezone": "UTC",
        "schedule": final_schedule
    }

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Successfully wrote {len(final_schedule)} days into {MANIFEST_FILE}!")

if __name__ == "__main__":
    main()
