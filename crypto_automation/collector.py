#!/usr/bin/env python3
"""
Viral Crypto & Macro Video Discovery Engine
Finds viral, high-performing long-form videos (Congressional hearings, Fed debates, Bitcoin speeches).
"""

import os
import json
import subprocess
from typing import List, Dict, Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ARCHIVE_PATH = os.path.join(SCRIPT_DIR, "archive.json")

DEFAULT_SEARCH_TOPICS = [
    "bitcoin senate hearing uncut",
    "crypto congressional hearing full",
    "ron paul federal reserve hearing is gold money",
    "sec gary gensler crypto hearing highlights",
    "milton friedman understanding inflation",
    "cynthia lummis bitcoin speech senate",
    "federal reserve inflation hearing uncut powell",
    "jack mallers bitcoin speech monetary revolution",
    "peter van valkenburgh crypto hearing"
]

def load_archive() -> List[str]:
    if not os.path.exists(ARCHIVE_PATH):
        return []
    try:
        with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [item.get("youtube_id") for item in data if item.get("youtube_id")]
    except Exception:
        return []

def search_candidates(
    topics: Optional[List[str]] = None,
    max_per_topic: int = 5,
    min_views: int = 15000,
    min_duration_sec: int = 240,
    max_duration_sec: int = 2400
) -> List[Dict[str, Any]]:
    archived_ids = set(load_archive())
    topics = topics or DEFAULT_SEARCH_TOPICS
    candidates = []
    seen_ids = set()

    for topic in topics:
        query = f"ytsearch{max_per_topic}:{topic}"
        cmd = ["yt-dlp", "--dump-json", "--flat-playlist", query]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
            if res.returncode != 0:
                continue

            for line in res.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    d = json.loads(line)
                    yid = d.get("id")
                    if not yid or yid in archived_ids or yid in seen_ids:
                        continue

                    duration = d.get("duration") or 0
                    views = d.get("view_count") or 0

                    if duration < min_duration_sec or duration > max_duration_sec:
                        continue
                    if views < min_views:
                        continue

                    seen_ids.add(yid)
                    candidates.append({
                        "id": yid,
                        "title": d.get("title", ""),
                        "duration": duration,
                        "duration_str": f"{int(duration // 60)}m {int(duration % 60)}s",
                        "view_count": views,
                        "uploader": d.get("uploader", ""),
                        "url": f"https://www.youtube.com/watch?v={yid}",
                        "search_topic": topic
                    })
                except Exception:
                    continue
        except Exception:
            continue

    # Rank candidates by views descending
    candidates.sort(key=lambda x: x["view_count"], reverse=True)
    return candidates

def pick_top_candidate(topic: Optional[str] = None) -> Optional[Dict[str, Any]]:
    topics = [topic] if topic else DEFAULT_SEARCH_TOPICS
    candidates = search_candidates(topics=topics)
    return candidates[0] if candidates else None

if __name__ == "__main__":
    print("🔍 Searching for top viral crypto & financial hearing candidates...")
    top_candidates = search_candidates()
    print(f"✅ Found {len(top_candidates)} eligible candidates:")
    for i, c in enumerate(top_candidates[:10], 1):
        print(f"{i}. [{c['id']}] ({c['duration_str']}) {c['title']} | Views: {c['view_count']:,} | Topic: {c['search_topic']}")
