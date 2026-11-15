#!/usr/bin/env python3
"""
Direct Viral Video Publisher for Rumble
Uploads downloaded viral YouTube videos directly to Rumble under Tier 6 with original voice and custom thumbnail.
"""

import os
import sys
import argparse

sys.path.append("/home/samirkhadka/ytbe")
from rumble_api import RumbleAPI

VIDEO_PATH = "/home/samirkhadka/crypto_automation/downloaded_viral/Bitcoin_Senate_Hearing_Public_Domain_Clean.mp4"
THUMB_PATH = "/home/samirkhadka/crypto_automation/downloaded_viral/senate_clean_thumb.jpg"

TITLE = "The Greatest Bitcoin Explanation of ALL TIME (Senate Banking Hearing)"
DESCRIPTION = (
    "The legendary Senate Banking Committee testimony by Peter Van Valkenburgh explaining Bitcoin, "
    "decentralized public ledgers, and why the open monetary network is as revolutionary as the early internet.\n\n"
    "Full uncut testimony from the US Senate Committee on Banking, Housing, and Urban Affairs.\n\n"
    "#bitcoin #crypto #cryptocurrency #finance #banking #money #documentary #rumble"
)
TAGS = "bitcoin, crypto, cryptocurrency, finance, banking, money, documentary, rumble, btc"

def publish_to_rumble(channel_id="7985034", license_tier="3"):
    print("=" * 60)
    print("🚀 PUBLISHING PUBLIC DOMAIN SENATE TESTIMONY TO RUMBLE")
    print(f"📌 Title: {TITLE}")
    print(f"📁 Video: {VIDEO_PATH} ({os.path.getsize(VIDEO_PATH) / (1024*1024):.2f} MB)")
    print(f"🖼️ Thumbnail: {THUMB_PATH}")
    print(f"🎯 Channel: {channel_id} | License Tier: {license_tier} (Rumble Only)")
    print("=" * 60)

    ra = RumbleAPI()
    res = ra.upload_video(
        video_path=VIDEO_PATH,
        title=TITLE,
        description=DESCRIPTION,
        tags=TAGS,
        channel_id=channel_id,
        license_tier=license_tier,
        custom_thumb_path=THUMB_PATH
    )

    if res.get("ok"):
        print("\n🎉 RUMBLE PUBLISH SUCCESS!")
        print(f"🔗 Video URL: {res.get('url')}")
        print(f"🆔 FID: {res.get('fid')}")
        return res
    else:
        print("\n❌ RUMBLE PUBLISH FAILED:")
        print(res.get("error"))
        return res

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish viral video directly to Rumble")
    parser.add_argument("--channel", default="7985034", help="Rumble channel ID (default: 7985034)")
    parser.add_argument("--license", default="3", choices=["1", "2", "3", "6"], help="Rumble license tier (default: 3 - Rumble Only/Non-Exclusive)")
    args = parser.parse_args()
    publish_to_rumble(channel_id=args.channel, license_tier=args.license)
