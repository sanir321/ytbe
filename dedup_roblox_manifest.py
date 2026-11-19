#!/usr/bin/env python3
"""
Deduplicates manifest.json so every single scheduled Instagram reel is 100% unique.
Preserves published entries (Days 1-8).
Recalculates consecutive day numbers and scheduled_time (14:00 UTC daily).
"""

import json
from datetime import datetime, timedelta, timezone

MANIFEST_FILE = "/home/samirkhadka/ytbe/manifest.json"

def main():
    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)

    schedule = manifest["schedule"]
    seen_urls = set()
    clean_schedule = []

    # Preserve already published days
    for entry in schedule:
        if entry.get("status") == "published":
            clean_schedule.append(entry)
            url = entry.get("instagram_url")
            if url:
                seen_urls.add(url)

    # Queue unique items
    for entry in schedule:
        if entry.get("status") == "published":
            continue
        url = entry.get("instagram_url")
        if url:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            clean_schedule.append(entry)
        else:
            clean_schedule.append(entry)

    # Re-index days and scheduled dates starting from Day 9 (tomorrow 2026-11-20)
    base_tomorrow = datetime(2026, 11, 20, 14, 0, tzinfo=timezone.utc)
    for i, entry in enumerate(clean_schedule):
        day_num = i + 1
        entry["day"] = day_num
        if entry.get("status") != "published":
            sched_dt = base_tomorrow + timedelta(days=(day_num - 9))
            entry["scheduled_time"] = sched_dt.strftime("%Y-%m-%d %H:%M UTC")

    manifest["schedule"] = clean_schedule
    manifest["total_days"] = len(clean_schedule)

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"🎉 Deduplication Complete!")
    print(f"Total days: {manifest['total_days']}")
    print(f"Unique URLs: {len(seen_urls)}")
    print(f"Runway spans until: {clean_schedule[-1]['scheduled_time']}")

if __name__ == "__main__":
    main()
