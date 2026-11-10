#!/usr/bin/env python3
"""
Autonomous YouTube Shorts Publisher for GitHub Actions
Reads manifest.json, picks the scheduled video, uploads to YouTube Data API v3,
and commits the updated publication status back to GitHub.
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

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
        # Try local token fallback if running outside GitHub Actions
        token_file = os.path.expanduser("~/youtube_token.json")
        if os.path.exists(token_file):
            print(f"[AUTH] Loading local credentials from {token_file}")
            with open(token_file) as f:
                tf = json.load(f)
                client_id = tf.get("client_id")
                client_secret = tf.get("client_secret")
                refresh_token = tf.get("refresh_token")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("Missing YouTube credentials (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN).")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    print("[AUTH] Refreshing YouTube OAuth access token...")
    creds.refresh(Request())
    print("[AUTH] Token refreshed successfully.")

    return build("youtube", "v3", credentials=creds)

def upload_short(youtube, video_path, title, description, tags, privacy="public"):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found at: {video_path}")

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    print(f"[UPLOAD] Starting upload for '{title}' ({file_size_mb:.1f} MB)...")

    # YouTube Shorts optimal snippet
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags[:30],
            "categoryId": "24",  # Entertainment
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en"
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        chunksize=4 * 1024 * 1024,
        resumable=True
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"[UPLOAD] Progress: {pct}%")

    video_id = response.get("id")
    video_url = f"https://youtube.com/shorts/{video_id}"
    print(f"[SUCCESS] Uploaded: {video_url}")
    return video_id, video_url

def commit_and_push_manifest(manifest_path="manifest.json", day_num=None):
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print("[GIT] Local environment detected; skipping auto-commit.")
        return

    print("[GIT] Configuring git for auto-commit...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", manifest_path], check=True)
    
    commit_msg = f"chore(schedule): mark Day {day_num} as published [skip ci]" if day_num else "chore(schedule): update published status [skip ci]"
    res = subprocess.run(["git", "commit", "-m", commit_msg])
    if res.returncode == 0:
        print("[GIT] Pushing manifest update back to repository...")
        subprocess.run(["git", "push"], check=True)
        print("[GIT] Push completed successfully.")
    else:
        print("[GIT] No changes to commit.")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Shorts Publisher")
    parser.add_argument("--day", default="auto", help="Day number (1-28) or 'auto'")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without uploading")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"], help="Privacy status")
    args = parser.parse_args()

    manifest_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manifest.json")
    manifest = load_manifest(manifest_path)
    schedule = manifest.get("schedule", [])

    target_entry = None
    if args.day == "auto":
        for entry in schedule:
            if entry.get("status") == "queued":
                target_entry = entry
                break
        if not target_entry:
            print("[INFO] All scheduled videos in the manifest have already been published!")
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
    print(f"🎬 EXECUTING PUBLISH FOR DAY {day_num}")
    print(f"📌 Title: {title}")
    print(f"📁 Video File: {video_file}")
    print(f"🔒 Privacy: {args.privacy}")
    print(f"==========================================\n")

    if args.dry_run:
        print(f"[DRY-RUN] Verification complete. Video file exists: {os.path.exists(video_file)}")
        print(f"[DRY-RUN] Size: {os.path.getsize(video_file) / (1024*1024):.1f} MB")
        print("[DRY-RUN] Skipping live YouTube API upload.")
        return 0

    youtube = get_youtube_client()
    video_id, video_url = upload_short(youtube, video_file, title, description, tags, privacy=args.privacy)

    target_entry["status"] = "published"
    target_entry["youtube_id"] = video_id
    target_entry["published_url"] = video_url
    target_entry["published_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    save_manifest(manifest, manifest_path)
    print(f"[MANIFEST] Updated manifest for Day {day_num}.")

    commit_and_push_manifest(manifest_path, day_num=day_num)
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
