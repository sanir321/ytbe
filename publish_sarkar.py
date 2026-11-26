#!/usr/bin/env python3
"""
Autonomous Daily Shorts Publisher for SH SARKAR Channel (87.9K Subscribers)
Channel ID: UCN5kwanpmxeRNKeqs-4fzMQ
Downloads from @sameer_exc, applies anti-detection visual remixing, and publishes to YouTube.
"""

import os
import sys
import json
import time
import pickle
import argparse
import subprocess
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_FILE = os.path.join(BASE_DIR, "manifest_sarkar.json")
TMP_DIR = os.path.join(BASE_DIR, "tmp_remix_sarkar")
TOKEN_PICKLE = os.path.expanduser("~/.sarkar_token.pickle")
os.makedirs(TMP_DIR, exist_ok=True)

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

def get_system_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for cand in candidates:
        if os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, size)
            except Exception:
                pass
    return ImageFont.load_default()

def clean_title_for_render(title):
    # Strip complex emojis that cause font box artifacts in Linux fonts
    import re
    clean = re.sub(r'[^\w\s\-\:\.\,\!\?\#\⚡\★\•]', '', title)
    return clean.strip()

def make_overlay(title_text):
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_title = get_system_font(38)
    font_badge = get_system_font(24)
    font_banner = get_system_font(28)

    # 1. Top Hook Title Header
    clean_title = clean_title_for_render(title_text)
    bbox = font_title.getbbox(clean_title)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 36, 18
    bx0 = (1080 - tw) // 2 - pad_x
    by0 = 135
    bx1 = (1080 + tw) // 2 + pad_x
    by1 = by0 + th + (pad_y * 2)

    draw.rounded_rectangle([bx0-4, by0-4, bx1+4, by1+4], radius=22, fill=(0, 0, 0, 180))
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=20, fill=(12, 12, 18, 250), outline=(0, 220, 255, 255), width=4)
    draw.rounded_rectangle([bx0+4, by0+4, bx1-4, by1-4], radius=16, outline=(255, 215, 0, 160), width=2)
    
    tx = (1080 - tw) // 2
    ty = by0 + pad_y - bbox[1]
    draw.text((tx+2, ty+2), clean_title, font=font_title, fill=(0, 0, 0, 255))
    draw.text((tx, ty), clean_title, font=font_title, fill=(255, 255, 255, 255))

    # 2. Watermark / Handle Concealment Banner (covers original @sameer_exc text at y=1365-1445)
    wm_box = [200, 1365, 880, 1445]
    draw.rounded_rectangle([wm_box[0]-4, wm_box[1]-4, wm_box[2]+4, wm_box[3]+4], radius=18, fill=(0, 0, 0, 255))
    draw.rounded_rectangle(wm_box, radius=16, fill=(12, 12, 18, 255), outline=(255, 70, 70, 255), width=3)
    wm_text = "★ SH SARKAR HIGHLIGHTS ★"
    w_bbox = font_banner.getbbox(wm_text)
    ww, wh = w_bbox[2] - w_bbox[0], w_bbox[3] - w_bbox[1]
    wtx = wm_box[0] + (wm_box[2] - wm_box[0] - ww) // 2
    wty = wm_box[1] + (wm_box[3] - wm_box[1] - wh) // 2 - w_bbox[1]
    draw.text((wtx+2, wty+2), wm_text, font=font_banner, fill=(0, 0, 0, 255))
    draw.text((wtx, wty), wm_text, font=font_banner, fill=(255, 255, 255, 255))

    # 3. Bottom Centered Call-To-Action Pill
    b_box = [280, 1790, 800, 1865]
    draw.rounded_rectangle([b_box[0]-3, b_box[1]-3, b_box[2]+3, b_box[3]+3], radius=18, fill=(0, 0, 0, 200))
    draw.rounded_rectangle(b_box, radius=16, fill=(14, 14, 22, 245), outline=(0, 220, 255, 240), width=3)
    badge_text = "• SUBSCRIBE TO SH SARKAR •"
    b_bbox = font_badge.getbbox(badge_text)
    bw, bh = b_bbox[2] - b_bbox[0], b_bbox[3] - b_bbox[1]
    btx = b_box[0] + (b_box[2] - b_box[0] - bw) // 2
    bty = b_box[1] + (b_box[3] - b_box[1] - bh) // 2 - b_bbox[1]
    draw.text((btx+2, bty+2), badge_text, font=font_badge, fill=(0, 0, 0, 255))
    draw.text((btx, bty), badge_text, font=font_badge, fill=(255, 215, 0, 255))

    return img

def get_authenticated_service():
    client_id = os.environ.get("SARKAR_YT_CLIENT_ID")
    client_secret = os.environ.get("SARKAR_YT_CLIENT_SECRET")
    refresh_token = os.environ.get("SARKAR_YT_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        print("[AUTH] Using GitHub Secrets / environment credentials for SH SARKAR...")
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=None
        )
        if not creds.valid:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        # Channel Safety Lock
        ch_resp = yt.channels().list(part="snippet", mine=True).execute()
        if ch_resp.get("items"):
            cur_id = ch_resp["items"][0]["id"]
            cur_title = ch_resp["items"][0]["snippet"]["title"]
            if cur_id != "UCN5kwanpmxeRNKeqs-4fzMQ":
                raise ValueError(f"FATAL: Authenticated to {cur_title} ({cur_id}), but expected SH SARKAR (UCN5kwanpmxeRNKeqs-4fzMQ)! Aborting.")
        return yt

    if os.path.exists(TOKEN_PICKLE):
        print(f"[AUTH] Loading local credentials from {TOKEN_PICKLE}...")
        with open(TOKEN_PICKLE, "rb") as f:
            creds = pickle.load(f)
        if not creds.valid and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PICKLE, "wb") as f:
                pickle.dump(creds, f)
        yt = build("youtube", "v3", credentials=creds)
        # Channel Safety Lock
        ch_resp = yt.channels().list(part="snippet", mine=True).execute()
        if ch_resp.get("items"):
            cur_id = ch_resp["items"][0]["id"]
            cur_title = ch_resp["items"][0]["snippet"]["title"]
            if cur_id != "UCN5kwanpmxeRNKeqs-4fzMQ":
                raise ValueError(f"FATAL: Local pickle belongs to {cur_title} ({cur_id}), NOT SH SARKAR! Aborting.")
        return yt

    raise ValueError("No credentials found! Set SARKAR_YT_* env vars or ensure ~/.youtube_token.pickle exists.")

def prepare_video(entry, day_num):
    raw_path = None
    if entry.get("file_path") and os.path.exists(entry["file_path"]):
        raw_path = entry["file_path"]
        print(f"📦 Found local source: {raw_path}")
    else:
        print(f"⬇️ Downloading reel from Instagram: {entry['instagram_url']}...")
        out_tmpl = os.path.join(TMP_DIR, f"raw_day_{day_num}.%(ext)s")
        cookie_path = None
        if os.environ.get("INSTAGRAM_COOKIES"):
            cookie_path = "/tmp/gh_ig_cookies.txt"
            with open(cookie_path, "w") as f:
                f.write(os.environ["INSTAGRAM_COOKIES"])
        elif os.path.exists("/home/samirkhadka/instagram_cookies.txt"):
            cookie_path = "/home/samirkhadka/instagram_cookies.txt"

        download_cmd = [
            "yt-dlp", "--no-warnings",
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", out_tmpl
        ]
        downloaded = False
        if cookie_path and os.path.exists(cookie_path):
            try:
                subprocess.run(download_cmd + ["--cookies", cookie_path, entry["instagram_url"]], check=True)
                downloaded = True
            except subprocess.CalledProcessError as e:
                print(f"[RETRY] Download with cookies failed ({e}). Retrying without cookies...")

        if not downloaded:
            subprocess.run(download_cmd + [entry["instagram_url"]], check=True)
        raw_path = os.path.join(TMP_DIR, f"raw_day_{day_num}.mp4")

    # Uploader Verification Check: reject non-Free-Fire / non-sameer_exc reels
    try:
        check_cmd = ["yt-dlp", "--no-warnings", "--dump-json", entry["instagram_url"]]
        if cookie_path and os.path.exists(cookie_path):
            check_cmd += ["--cookies", cookie_path]
        proc = subprocess.run(check_cmd, capture_output=True, text=True, timeout=12)
        if proc.returncode == 0 and proc.stdout.strip():
            meta = json.loads(proc.stdout)
            uploader = (meta.get("uploader") or meta.get("uploader_id") or "").lower()
            expected_acc = entry.get("account", "").lower()
            allowed_creators = ["sameer", "exc", "eren", "erenexeff", "xff"]
            if expected_acc:
                allowed_creators.append(expected_acc)
            if uploader and not any(k in uploader for k in allowed_creators):
                print(f"[SECURITY REJECT] Day {day_num} reel uploader is '{uploader}', NOT authorized creator ({allowed_creators})! Skipping.")
                return "WRONG_UPLOADER"
    except Exception as e:
        print(f"[SECURITY CHECK] Warning checking uploader: {e}")

    clean_title = entry["title"].split("#")[0].strip()
    ov = make_overlay(clean_title)
    ov_path = os.path.join(TMP_DIR, f"ov_day_{day_num}.png")
    ov.save(ov_path)

    out_file = os.path.join(TMP_DIR, f"sarkar_day_{day_num}.mp4")

    # Check if source video contains an audio stream
    has_audio = False
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", raw_path],
            capture_output=True, text=True
        )
        has_audio = bool(probe.stdout.strip())
    except Exception:
        pass

    if not has_audio:
        print(f"[REJECT] Day {day_num} ({entry.get('reel_id')}) has NO AUDIO TRACK. Skipping per policy.")
        return None

    cmd = [
        "ffmpeg", "-y", "-i", raw_path, "-i", ov_path,
        "-filter_complex", "[0:v]scale=1080:1920,eq=contrast=1.06:brightness=0.01:saturation=1.12[base];[base][1:v]overlay=0:0[vout]",
        "-filter:a", "atempo=1.025,volume=1.05",
        "-map", "[vout]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-b:a", "192k",
        "-t", "50",
        "-shortest",
        out_file
    ]
    subprocess.run(cmd, check=True)
    return out_file

def delete_video(youtube, video_id):
    try:
        youtube.videos().delete(id=video_id).execute()
        print(f"[YOUTUBE DELETED] Successfully deleted video {video_id} from SH SARKAR.")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to delete video {video_id}: {e}")
        return False

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

    print(f"[YOUTUBE] Uploading to SH SARKAR: '{title}' ({os.path.getsize(file_path)/(1024*1024):.1f} MB)...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[YOUTUBE] Progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    video_url = f"https://youtube.com/shorts/{video_id}"
    print(f"[YOUTUBE SUCCESS] Uploaded to SH SARKAR: {video_url}")
    return video_id, video_url

def commit_manifest():
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    print("[GIT] Configuring git for manifest auto-commit...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"])
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    subprocess.run(["git", "add", MANIFEST_FILE])
    res = subprocess.run(["git", "commit", "-m", "chore(sarkar): update daily shorts manifest [skip ci]"])
    if res.returncode == 0:
        print("[GIT] Pushing manifest updates back to repository...")
        subprocess.run(["git", "pull", "--rebase"])
        subprocess.run(["git", "push"])

def main():
    parser = argparse.ArgumentParser(description="SH SARKAR Daily Shorts Publisher")
    parser.add_argument("--day", default="auto", help="Day number (1-330) or 'auto'")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--dry-run", action="store_true", help="Remix without uploading")
    parser.add_argument("--force", action="store_true", help="Force upload even if daily limit reached")
    parser.add_argument("--delete", default=None, help="Video ID to delete from channel")
    parser.add_argument("--count", type=int, default=1, help="Number of videos to publish in this run (1 or 2)")
    args = parser.parse_args()

    with open(MANIFEST_FILE, "r") as f:
        manifest = json.load(f)
    schedule = manifest.get("schedule", [])

    # Case 0: Direct Deletion
    if args.delete:
        yt = get_authenticated_service()
        deleted = delete_video(yt, args.delete)
        if deleted:
            for entry in schedule:
                if entry.get("youtube_id") == args.delete:
                    entry["status"] = "deleted_no_audio"
                    entry["deleted_at"] = datetime.now(timezone.utc).isoformat()
                    entry["published_url"] = None
                    print(f"[MANIFEST] Marked Day {entry.get('day')} ({entry.get('reel_id')}) as deleted_no_audio.")
            with open(MANIFEST_FILE, "w") as f:
                json.dump(manifest, f, indent=2)
            commit_manifest()
        return 0

    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.strftime("%Y-%m-%d")

    # 2 videos per day policy
    max_daily = 2
    published_today = [
        e for e in schedule
        if e.get("status") == "published" and (e.get("published_at") or "").startswith(today_utc)
    ]
    if len(published_today) >= max_daily and not args.force:
        print(f"[THROTTLE] Already published {len(published_today)}/{max_daily} videos to SH SARKAR today ({today_utc}). Skipping to maintain 2/day schedule.")
        return 0

    to_publish = min(args.count, max_daily - len(published_today)) if not args.force else args.count
    published_count = 0
    yt = None if args.dry_run else get_authenticated_service()

    for entry in schedule:
        if published_count >= to_publish:
            break
        if entry.get("status") != "queued":
            continue

        day_num = entry["day"]
        if args.day != "auto" and str(day_num) != str(args.day):
            continue

        print(f"\n==========================================")
        print(f"🎬 EVALUATING SH SARKAR CANDIDATE: DAY {day_num} ({entry.get('reel_id')})")
        print(f"📌 Title: {entry['title']}")
        print(f"🔗 Instagram URL: {entry.get('instagram_url')}")
        print(f"==========================================\n")

        try:
            remixed_video = prepare_video(entry, day_num)
        except Exception as e:
            print(f"⚠️ Error preparing Day {day_num} ({e}). Marking failed and advancing to next queued candidate...")
            entry["status"] = "download_failed"
            entry["error"] = str(e)
            continue
        if remixed_video == "WRONG_UPLOADER":
            entry["status"] = "skipped_wrong_account"
            entry["skipped_at"] = datetime.now(timezone.utc).isoformat()
            print(f"🛑 Day {day_num} skipped (non-Free-Fire reel). Advancing to next queued candidate...")
            continue
        if remixed_video is None:
            # Video rejected due to missing audio
            entry["status"] = "skipped_no_audio"
            entry["skipped_at"] = datetime.now(timezone.utc).isoformat()
            print(f"⚠️ Day {day_num} skipped (no audio track). Advancing to next queued candidate...")
            continue

        if args.dry_run:
            print(f"[DRY-RUN] Verification complete for Day {day_num}. (Skipping API upload)")
            published_count += 1
            continue

        title = entry["title"]
        desc = entry["description"]
        tags = entry["tags"]
        video_id, video_url = upload_short(yt, remixed_video, title, desc, tags, privacy=args.privacy)

        entry["status"] = "published"
        entry["youtube_id"] = video_id
        entry["published_url"] = video_url
        entry["published_at"] = datetime.now(timezone.utc).isoformat()
        published_count += 1

        if os.path.exists(remixed_video):
            try:
                os.remove(remixed_video)
            except Exception:
                pass

        print(f"🎉 Day {day_num} successfully published to SH SARKAR: {video_url}")

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"💾 Updated {MANIFEST_FILE} ({published_count} new video(s) published).")

    commit_manifest()
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
