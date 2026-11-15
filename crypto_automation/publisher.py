#!/usr/bin/env python3
"""
Rumble Publisher & Archive Tracker for Autonomous Workflow
Publishes videos to Rumble channel 7985034 under Tier 3 and logs to archive.json.
"""

import os
import sys
import json
import datetime
from typing import Dict, Any, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SRENT_DIR := "/home/samirkhadka/ytbe":
    if os.path.exists(SRENT_DIR) and SRENT_DIR not in sys.path:
        sys.path.append(SRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from rumble_api import RumbleAPI

ARCHIVE_PATH = os.path.join(SCRIPT_DIR, "archive.json")
CHANNEL_ID = "7985034"
CHANNEL_NAME = "BitcoinFrontier"

def append_to_archive(record: Dict[str, Any]) -> None:
    records = []
    if os.path.exists(ARCHIVE_PATH):
        try:
            with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
    records.append(record)
    with open(ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

def publish_video(
    video_path: str,
    thumb_path: str,
    title: str,
    description: str,
    tags: str,
    youtube_id: str,
    license_tier: str = "3"
) -> Dict[str, Any]:
    print("=" * 60)
    print("🚀 DISPATCHING TO RUMBLE (BITCOIN FRONTIER)")
    print(f"📌 Title: {title}")
    print(f"📁 Video: {video_path} ({os.path.getsize(video_path) / (1024*1024):.2f} MB)")
    print(f"🖼️ Thumbnail: {thumb_path}")
    print(f"🎯 Channel: {CHANNEL_NAME} ({CHANNEL_ID}) | Tier: {license_tier} (Rumble Only)")
    print("=" * 60)

    ra = RumbleAPI()
    res = ra.upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        channel_id=CHANNEL_ID,
        license_tier=license_tier,
        custom_thumb_path=thumb_path
    )

    if res.get("ok"):
        rumble_url = res.get("url")
        fid = res.get("fid")
        print("\n🎉 RUMBLE UPLOAD SUCCESSFUL!")
        print(f"🔗 Video URL: {rumble_url}")
        print(f"🆔 FID: {fid}")

        archive_entry = {
            "youtube_id": youtube_id,
            "title": title,
            "rumble_url": rumble_url,
            "fid": fid,
            "channel_id": CHANNEL_ID,
            "channel_name": CHANNEL_NAME,
            "published_at": datetime.datetime.now().isoformat(),
            "license_tier": license_tier
        }
        append_to_archive(archive_entry)
        res["archive_entry"] = archive_entry
        return res
    else:
        print("\n❌ RUMBLE UPLOAD FAILED:")
        print(res.get("error"))
        return res

if __name__ == "__main__":
    print("Rumble publisher module loaded.")
