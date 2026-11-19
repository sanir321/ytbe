#!/usr/bin/env python3
"""
Scrapes all GTA 6 shorts from the top YouTube clipper channels,
filters them with strict whitelist, and merges them with Instagram clips
into a single deduplicated master catalog: gta6_master_catalog.json.
"""

import subprocess
import json
import os
import re

YT_CHANNELS = [
    "@GrandZeroGTA",
    "@gta6clipdrops",
    "@gta6.clips.dailyhq",
    "@GTA6ClipsHQ-r9s",
    "@LiveSpeedy"
]

WHITELIST = [
    "gta 6", "gta vi", "gtavi", "vice city",
    "lucia", "jason", "leonida", "gta6", "gta"
]

BLACKLIST = [
    "avatar", "kendrick", "drake", "warzone", "cod", "resident evil",
    "tlou", "the last of us", "ballon d'or", "fifa", "ronaldo", "messi"
]

def is_valid_gta6(title):
    t = title.lower()
    for bad in BLACKLIST:
        if bad in t:
            return False
    for good in WHITELIST:
        if good in t:
            return True
    return False

def scrape_youtube():
    yt_clips = []
    for ch in YT_CHANNELS:
        print(f"Scraping YouTube Shorts from {ch}...")
        url = f"https://www.youtube.com/{ch}/shorts"
        cmd = [
            "yt-dlp", "--no-warnings", "--flat-playlist",
            "--dump-json", url
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            count = 0
            for line in res.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    title = data.get("title", "")
                    v_id = data.get("id")
                    if v_id and is_valid_gta6(title):
                        yt_clips.append({
                            "source": "youtube",
                            "channel": ch,
                            "video_id": v_id,
                            "url": f"https://www.youtube.com/shorts/{v_id}",
                            "title": title,
                            "views": data.get("view_count", 0)
                        })
                        count += 1
                except:
                    continue
            print(f"  ✓ {ch}: {count} valid GTA 6 shorts found.")
        except Exception as e:
            print(f"  ✗ {ch}: {e}")

    return yt_clips

def main():
    yt_clips = scrape_youtube()
    print(f"\nTotal YouTube GTA 6 Shorts scraped: {len(yt_clips)}")

    # Load existing clean Instagram clips
    ig_file = "/home/samirkhadka/ytbe/gta6_clean_catalog.json"
    ig_clips = []
    if os.path.exists(ig_file):
        with open(ig_file) as f:
            ig_raw = json.load(f)
            for c in ig_raw:
                ig_clips.append({
                    "source": "instagram",
                    "channel": f"@{c['account']}",
                    "video_id": c['code'],
                    "url": c['url'],
                    "title": c['caption'],
                    "views": None
                })

    print(f"Total Instagram GTA 6 Reels loaded: {len(ig_clips)}")

    # Merge and deduplicate
    master = []
    seen_ids = set()

    # Prioritize YouTube high-view shorts first, then Instagram
    all_combined = yt_clips + ig_clips
    for clip in all_combined:
        v_id = clip["video_id"]
        if v_id not in seen_ids:
            seen_ids.add(v_id)
            master.append(clip)

    out_file = "/home/samirkhadka/ytbe/gta6_master_catalog.json"
    with open(out_file, "w") as f:
        json.dump(master, f, indent=2)

    print(f"\n🎉 Master catalog built with {len(master)} unique GTA 6 clips!")
    print(f"Saved to {out_file}")

if __name__ == "__main__":
    main()
