#!/usr/bin/env python3
"""
Autonomous Viral Video Pipeline Orchestrator for Rumble
Finds viral crypto & macro content, processes video, generates custom thumbnail, and publishes to Rumble.
"""

import os
import sys
import argparse
import traceback
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

from collector import search_candidates, pick_top_candidate
from processor import download_video, process_and_trim, extract_keyframes
from seo import generate_seo_metadata
from thumbnailer import make_thumbnail
from publisher import publish_video

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_workflow(
    topic: str = None,
    youtube_id: str = None,
    dry_run: bool = False,
    start_sec: float = 0.0,
    end_sec: float = None,
    license_tier: str = "3"
):
    print("=" * 65)
    print("🎬 STARTING AUTONOMOUS VIRAL VIDEO WORKFLOW")
    print(f"🕒 Timestamp: {os.popen('date').read().strip()}")
    print("=" * 65)

    # 1. Step 1: Candidate Selection
    candidates = []
    if youtube_id:
        print(f"🎯 Target video ID manually specified: {youtube_id}")
        meta_cand = None
        try:
            meta_json = os.popen(f"yt-dlp --remote-components ejs:github --dump-json 'https://www.youtube.com/watch?v={youtube_id}'").read().strip()
            if meta_json:
                d = json.loads(meta_json)
                meta_cand = {
                    "id": youtube_id,
                    "title": d.get("title", f"Viral Video {youtube_id}"),
                    "view_count": d.get("view_count", 0),
                    "duration_str": f"{int((d.get('duration') or 0) // 60)}m",
                    "search_topic": topic or "manual"
                }
        except Exception:
            pass

        if not meta_cand:
            meta_cand = {
                "id": youtube_id,
                "title": f"Viral Video {youtube_id}",
                "view_count": 0,
                "duration_str": "N/A",
                "search_topic": topic or "manual"
            }
        candidates = [meta_cand]
    else:
        print("🔍 Searching for highest-performing viral candidates...")
        topics = [topic] if topic else None
        candidates = search_candidates(topics=topics)
        if not candidates:
            print("⚠️ No new eligible candidates found. Archive may contain all recent queries.")
            return {"ok": False, "reason": "No eligible candidates found"}

    # 2. Step 2: Download & Process Video (with graceful fallback)
    print("\n" + "-" * 50)
    print("📥 STEP 2: DOWNLOADING 1080P SOURCE")
    print("-" * 50)

    candidate = None
    dl_res = None
    for cand in candidates:
        yid = cand["id"]
        views_val = cand.get("view_count", 0)
        views_disp = f"{views_val:,}" if isinstance(views_val, (int, float)) else str(views_val)
        print(f"\n🏆 Evaluating Candidate: [{yid}]")
        print(f"📌 Title: {cand.get('title')}")
        print(f"👀 Views: {views_disp} | ⏱️ Duration: {cand.get('duration_str', 'N/A')}")
        try:
            dl_res = download_video(yid)
            candidate = cand
            break
        except Exception as e:
            print(f"⚠️ Download failed for [{yid}]: {e}. Trying next candidate...")
            continue

    if not dl_res or not candidate:
        print("❌ All candidate downloads failed.")
        return {"ok": False, "reason": "All candidate downloads failed"}

    yid = candidate["id"]
    raw_video_path = dl_res["raw_path"]
    clean_video_path = os.path.join(OUTPUT_DIR, f"{yid}_clean.mp4")

    print("\n" + "-" * 50)
    print("✂️ STEP 3: AUDIO/VIDEO PROCESSING & TRIMMING")
    print("-" * 50)
    process_and_trim(raw_video_path, clean_video_path, start_sec=start_sec, end_sec=end_sec)

    # 3. Step 4: Extract Keyframes & Generate High-CTR Thumbnail
    print("\n" + "-" * 50)
    print("🖼️ STEP 4: EXTRACTING KEYFRAMES & GENERATING THUMBNAIL")
    print("-" * 50)
    keyframes = extract_keyframes(clean_video_path, count=3)
    bg_keyframe = keyframes[0] if keyframes else None

    # Generate SEO Metadata
    seo_meta = generate_seo_metadata(candidate)
    thumb_path = os.path.join(OUTPUT_DIR, f"{yid}_thumb.jpg")
    make_thumbnail(
        bg_image_path=bg_keyframe,
        badge_text=seo_meta["badge"],
        headline_lines=seo_meta["headline_lines"],
        output_path=thumb_path
    )

    # 4. Step 5: Publish to Rumble
    print("\n" + "-" * 50)
    print("🚀 STEP 5: RUMBLE PUBLISHING & ARCHIVAL")
    print("-" * 50)
    if dry_run:
        print("⚠️ [DRY RUN ACTIVE] Skipping Rumble API upload. Output files preserved:")
        print(f"📁 Clean Video: {clean_video_path}")
        print(f"🖼️ Thumbnail: {thumb_path}")
        print(f"📌 SEO Title: {seo_meta['title']}")
        return {"ok": True, "dry_run": True, "clean_video": clean_video_path, "thumb": thumb_path}

    pub_res = publish_video(
        video_path=clean_video_path,
        thumb_path=thumb_path,
        title=seo_meta["title"],
        description=seo_meta["description"],
        tags=seo_meta["tags"],
        youtube_id=yid,
        license_tier=license_tier
    )

    # Clean up heavy raw file, keep clean video & thumb
    try:
        if os.path.exists(raw_video_path):
            os.remove(raw_video_path)
    except Exception:
        pass

    print("\n" + "=" * 65)
    print("🏁 WORKFLOW COMPLETE")
    print("=" * 65)
    return pub_res

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Viral Video Workflow for Rumble")
    parser.add_argument("--auto", action="store_true", help="Automatically pick and publish #1 viral candidate")
    parser.add_argument("--topic", type=str, default=None, help="Specific search topic")
    parser.add_argument("--video-id", type=str, default=None, help="Target specific YouTube video ID")
    parser.add_argument("--dry-run", action="store_true", help="Run without publishing to Rumble")
    parser.add_argument("--start", type=float, default=0.0, help="Trim start time in seconds")
    parser.add_argument("--end", type=float, default=None, help="Trim end time in seconds")
    parser.add_argument("--tier", type=str, default="3", choices=["1", "2", "3", "6"], help="Rumble license tier")

    args = parser.parse_args()

    if args.auto or args.video_id or args.topic:
        res = run_workflow(
            topic=args.topic,
            youtube_id=args.video_id,
            dry_run=args.dry_run,
            start_sec=args.start,
            end_sec=args.end,
            license_tier=args.tier
        )
    else:
        parser.print_help()
