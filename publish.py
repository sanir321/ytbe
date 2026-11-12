#!/usr/bin/env python3
"""
Autonomous Multi-Platform Shorts Publisher for GitHub Actions
Reads manifest.json, picks the scheduled video, uploads to:
1. YouTube Data API v3 (Shorts)
2. Rumble Direct API (Roblox Shorts Network, Channel 7985034, Tier 6 Monetization)
And commits the updated publication status back to GitHub.
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

try:
    from rumble_api import RumbleAPI
except ImportError:
    RumbleAPI = None

try:
    from rumble_booster import boost_all_manifest_videos
except ImportError:
    boost_all_manifest_videos = None

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

def load_manifest(manifest_path="manifest.json"):
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_manifest(data, manifest_path="manifest.json"):
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_youtube_client():
    client_id = os.environ.get("YT_CLIENT_ID")
    client_secret = os.environ.get("YT_CLIENT_SECRET")
    refresh_token = os.environ.get("YT_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        token_file = os.path.expanduser("~/youtube_token.json")
        if os.path.exists(token_file):
            print(f"[AUTH] Loading local credentials from {token_file}")
            with open(token_file) as f:
                tf = json.load(f)
                client_id = tf.get("client_id")
                client_secret = tf.get("client_secret")
                refresh_token = tf.get("refresh_token")

    if not all([client_id, client_secret, refresh_token]):
        print("[WARNING] Missing YouTube credentials (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN). Skipping YouTube.")
        return None

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    if not creds.valid:
        print("[AUTH] Refreshing YouTube OAuth access token...")
        creds.refresh(Request())
        print("[AUTH] Token refreshed successfully.")

    return build("youtube", "v3", credentials=creds)

def upload_short(youtube, file_path, title, description, tags, privacy="public"):
    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags if isinstance(tags, list) else [tags],
            "categoryId": "20"  # Gaming category
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        file_path,
        chunksize=1024*1024*4,
        resumable=True,
        mimetype="video/mp4"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    print(f"[YOUTUBE] Starting upload for '{title}' ({os.path.getsize(file_path)/(1024*1024):.1f} MB)...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[YOUTUBE] Progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    video_url = f"https://youtube.com/shorts/{video_id}"
    print(f"[YOUTUBE SUCCESS] Uploaded: {video_url}")
    return video_id, video_url

def upload_to_rumble(video_file, title, description, tags, channel_id="7985034", license_tier="6"):
    if not RumbleAPI:
        print("[RUMBLE] RumbleAPI module not available. Skipping Rumble upload.")
        return None

    client = RumbleAPI()
    if not client.cookies.get("u_s") and not client.cookies.get("a_s"):
        print("[RUMBLE WARNING] No Rumble session cookies found in RUMBLE_COOKIES_JSON or session file. Skipping Rumble.")
        return None

    # Formatted description with channel branding & viral tags
    rumble_description = (
        f"{description}\n\n"
        f"🎬 Channel: Roblox Shorts Network (@samir432)\n"
        f"🔔 Follow @samir432 for daily viral Roblox story shorts and animations!\n"
        f"💬 Rant, like, and leave your thoughts below!\n\n"
        f"#Shorts #Roblox #Gaming #Animation #Viral #RumbleShorts #RobloxStories"
    )
    rumble_tags = ", ".join(tags) if isinstance(tags, list) else str(tags)

    print(f"[RUMBLE] Starting direct upload for '{title}' to Channel {channel_id} (Tier {license_tier})...")
    res = client.upload_video(
        video_path=video_file,
        title=title,
        description=rumble_description,
        tags=rumble_tags,
        visibility="public",
        channel_id=channel_id,
        license_tier=license_tier
    )

    if res.get("ok"):
        url = res.get("url")
        print(f"[RUMBLE SUCCESS] Published: {url}")
        return res
    else:
        print(f"[RUMBLE ERROR] Upload response: {res}")
        return None

def commit_and_push_manifest(manifest_path, day_num=None, action_note=None):
    if not os.environ.get("GITHUB_ACTIONS"):
        print("[GIT] Running locally; skipping git auto-commit.")
        return

    print("[GIT] Configuring git for auto-commit...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", manifest_path], check=True)
    
    if day_num:
        commit_msg = f"chore(schedule): publish Day {day_num} & boost views [skip ci]"
    elif action_note:
        commit_msg = f"chore(schedule): {action_note} [skip ci]"
    else:
        commit_msg = "chore(schedule): update published status [skip ci]"

    res = subprocess.run(["git", "commit", "-m", commit_msg])
    if res.returncode == 0:
        print("[GIT] Pushing manifest update back to repository...")
        subprocess.run(["git", "push"], check=True)
        print("[GIT] Push completed successfully.")
    else:
        print("[GIT] No changes to commit.")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Multi-Platform Shorts Publisher")
    parser.add_argument("--day", default="auto", help="Day number (1-28), 'auto', or 'boost-only'")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without uploading")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"], help="YouTube Privacy status")
    parser.add_argument("--platform", default="all", choices=["all", "youtube", "rumble"], help="Platform target")
    parser.add_argument("--boost-count", type=int, default=300, help="Views per video for daily cloud boost (default: 300)")
    parser.add_argument("--no-boost", action="store_true", help="Skip automated AWS cloud view booster")
    parser.add_argument("--force", action="store_true", help="Force upload even if a video was already published today")
    args = parser.parse_args()

    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
    manifest = load_manifest(manifest_path)
    schedule = manifest.get("schedule", [])

    if args.day == "boost-only":
        if boost_all_manifest_videos:
            boost_all_manifest_videos(manifest_path, count_per_video=args.boost_count)
            commit_and_push_manifest(manifest_path, action_note="daily cloud boost")
        return 0

    target_entry = None
    if args.day == "auto":
        # Check if a video has already been published today (UTC)
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        already_published_today = any(
            (e.get("published_at") or "").startswith(today_utc) or (e.get("rumble_published_at") or "").startswith(today_utc)
            for e in schedule
            if e.get("status") == "published"
        )
        if already_published_today and not args.force:
            print(f"[THROTTLE] A video was already published today ({today_utc}). Skipping new upload to maintain strict 1/day schedule.")
            if not args.no_boost and boost_all_manifest_videos and args.platform in ["all", "rumble"]:
                boost_all_manifest_videos(manifest_path, count_per_video=args.boost_count)
                commit_and_push_manifest(manifest_path, action_note="daily cloud boost")
            return 0

        now_utc = datetime.now(timezone.utc)
        for entry in schedule:
            # Need upload if not fully published to both platforms
            yt_done = bool(entry.get("youtube_id"))
            rm_done = bool(entry.get("rumble_url"))
            needs_pub = entry.get("status") == "queued" or (args.platform == "rumble" and not rm_done) or (args.platform == "youtube" and not yt_done) or (args.platform == "all" and (not yt_done or not rm_done))
            if needs_pub:
                # Strictly enforce scheduled_time unless --force is passed
                sched_str = entry.get("scheduled_time", "")
                if sched_str and not args.force:
                    try:
                        sched_dt = datetime.strptime(sched_str, "%Y-%m-%d %H:%M %Z").replace(tzinfo=timezone.utc)
                        if now_utc < sched_dt:
                            print(f"[SCHEDULE] Day {entry['day']} is scheduled for {sched_str}. Not due yet (Current UTC: {now_utc.strftime('%Y-%m-%d %H:%M')}).")
                            break
                    except Exception:
                        pass
                target_entry = entry
                break
        if not target_entry:
            print("[INFO] All scheduled videos in the manifest have already been published!")
            if not args.no_boost and boost_all_manifest_videos and args.platform in ["all", "rumble"]:
                boost_all_manifest_videos(manifest_path, count_per_video=args.boost_count)
                commit_and_push_manifest(manifest_path, action_note="daily cloud boost")
            return 0
    else:
        day_val = int(args.day)
        for entry in schedule:
            if entry.get("day") == day_val:
                target_entry = entry
                break
        if not target_entry:
            print(f"[ERROR] Day {args.day} not found in manifest!")
            return 1

    day_num = target_entry["day"]
    video_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), target_entry["video_file"])
    title = target_entry["title"]
    description = target_entry["description"]
    tags = target_entry["tags"]

    print(f"\n==========================================")
    print(f"🎬 EXECUTING DUAL PUBLISH FOR DAY {day_num}")
    print(f"📌 Title: {title}")
    print(f"📁 Video File: {video_file}")
    print(f"🎯 Target Platform: {args.platform}")
    print(f"==========================================\n")

    if args.dry_run:
        print(f"[DRY-RUN] Verification complete. Video file exists: {os.path.exists(video_file)}")
        print(f"[DRY-RUN] Size: {os.path.getsize(video_file) / (1024*1024):.1f} MB")
        print("[DRY-RUN] Skipping live API uploads.")
        return 0

    published_anything = False

    # 1. YouTube Upload
    if args.platform in ["all", "youtube"] and not target_entry.get("youtube_id"):
        try:
            youtube = get_youtube_client()
            if youtube:
                v_id, v_url = upload_short(youtube, video_file, title, description, tags, privacy=args.privacy)
                target_entry["youtube_id"] = v_id
                target_entry["published_url"] = v_url
                target_entry["published_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                published_anything = True
        except Exception as e:
            print(f"[YOUTUBE ERROR] Failed: {e}")

    # 2. Rumble Upload
    if args.platform in ["all", "rumble"] and not target_entry.get("rumble_url"):
        try:
            r_res = upload_to_rumble(video_file, title, description, tags, channel_id="7985034", license_tier="6")
            if r_res:
                target_entry["rumble_url"] = r_res.get("url")
                target_entry["rumble_fid"] = r_res.get("fid")
                target_entry["rumble_status"] = "published"
                target_entry["rumble_published_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                published_anything = True
        except Exception as e:
            print(f"[RUMBLE ERROR] Failed: {e}")

    if target_entry.get("youtube_id") and target_entry.get("rumble_url"):
        target_entry["status"] = "published"
    elif target_entry.get("youtube_id") or target_entry.get("rumble_url"):
        target_entry["status"] = "partially_published"

    if published_anything:
        save_manifest(manifest, manifest_path)
        print(f"[MANIFEST] Updated manifest for Day {day_num}.")

    # 3. Cloud View Boost for all published Rumble videos
    if not args.no_boost and boost_all_manifest_videos and args.platform in ["all", "rumble"]:
        print(f"\n==========================================")
        print(f"⚡ EXECUTING DAILY AWS CLOUD BOOST ({args.boost_count} views/video)")
        print(f"==========================================")
        try:
            boost_res = boost_all_manifest_videos(manifest_path, count_per_video=args.boost_count)
            if boost_res:
                published_anything = True
        except Exception as e:
            print(f"[BOOST ERROR] Cloud booster encountered error: {e}")

    if published_anything:
        commit_and_push_manifest(manifest_path, day_num=day_num)
    else:
        print("[INFO] No new uploads or boosts performed.")

    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
