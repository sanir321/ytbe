#!/usr/bin/env python3
"""
Builds manifest_gta6.json for GTA6_DS channel (UCU4JAQ7BGkZW1BYkeZWBCww).
Includes Day 1 (Reference IShowSpeed Alligator reel Df5HcNMsA28) + 78 curated clips.
Total: 79 days of autonomous daily content!
"""

import json
import re
from datetime import datetime, timedelta, timezone

CATALOG_FILE = "/home/samirkhadka/ytbe/gta6_master_catalog.json"
OUTPUT_MANIFEST = "/home/samirkhadka/ytbe/manifest_gta6.json"

FAIR_USE_DISCLAIMER = (
    "\n\n---\n"
    "⚖️ Copyright Disclaimer Under Section 107 of the Copyright Act 1976: "
    "Allowance is made for 'fair use' for purposes such as criticism, commentary, news reporting, and entertainment. "
    "All video material belongs to their respective content creators and streamers. "
    "Transformative clipped highlights created for gaming community discussion."
)

def clean_title(raw_title, day_num):
    # Remove existing #shorts / #tags
    t = re.sub(r"#\S+", "", raw_title).strip()
    # Normalize whitespace
    t = re.sub(r"\s+", " ", t).strip()
    # If too short or generic
    if len(t) < 10 or t.lower() in ["video by gta6.clipsmp4", "gta 6", "photo by"]:
        t = f"Insane GTA 6 Stream Moment #{day_num}"
    
    # Capitalize first letter
    t = t[0].upper() + t[1:] if t else f"GTA 6 Wild Moment #{day_num}"
    
    # Ensure it ends with #Shorts
    return f"{t} 💀🔥 #Shorts"

def main():
    with open(CATALOG_FILE) as f:
        catalog = json.load(f)

    # Day 1: Reference viral IShowSpeed Alligator reel
    day_1_clip = {
        "source": "instagram",
        "channel": "@chungreels",
        "video_id": "Df5HcNMsA28",
        "url": "https://www.instagram.com/reel/Df5HcNMsA28/",
        "title": "GTA 6 alligators are NOT playing 💀 IShowSpeed found out the hard way 🐊"
    }

    all_clips = [day_1_clip] + catalog

    # Deduplicate video_id
    seen_ids = set()
    unique_clips = []
    for c in all_clips:
        v_id = c["video_id"]
        if v_id not in seen_ids:
            seen_ids.add(v_id)
            unique_clips.append(c)

    print(f"Total unique clips to schedule: {len(unique_clips)}")

    schedule = []
    base_time = datetime(2026, 11, 19, 15, 30, tzinfo=timezone.utc)

    for i, c in enumerate(unique_clips):
        day_num = i + 1
        sched_dt = base_time + timedelta(days=i)
        title = clean_title(c["title"], day_num)
        
        desc = (
            f"{title}\n\n"
            "🔔 Subscribe to @gta6_ds-b5z for daily high-retention GTA 6 stream moments, fails & clips!\n"
            "💬 What was your favorite moment? Comment below! 👇\n\n"
            "#gta6 #gtavi #shorts #gaming #viral #trending #ishowspeed #kaicenat #vicecity #gta6clips"
            f"{FAIR_USE_DISCLAIMER}"
        )

        entry = {
            "day": day_num,
            "title": title,
            "description": desc,
            "tags": [
                "gta6", "gtavi", "shorts", "gaming", "viral", "trending",
                "ishowspeed", "kaicenat", "vicecity", "gta6clips", "rockstargames"
            ],
            "source": c["source"],
            "channel_source": c["channel"],
            "video_id": c["video_id"],
            "url": c["url"],
            "scheduled_time": sched_dt.strftime("%Y-%m-%d %H:%M UTC"),
            "status": "queued",
            "youtube_id": None,
            "published_url": None,
            "published_at": None
        }
        schedule.append(entry)

    manifest = {
        "channel_title": "GTA6_DS",
        "channel_id": "UCU4JAQ7BGkZW1BYkeZWBCww",
        "custom_url": "@gta6_ds-b5z",
        "total_days": len(schedule),
        "schedule": schedule
    }

    with open(OUTPUT_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"🎉 SUCCESS! Created {OUTPUT_MANIFEST} with {len(schedule)} total days!")
    print(f"Day 1: {schedule[0]['title']}")
    print(f"Day {len(schedule)} ends on: {schedule[-1]['scheduled_time']}")

if __name__ == "__main__":
    main()
