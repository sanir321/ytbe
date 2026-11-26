#!/usr/bin/env python3
"""
GTA6_DS Autonomous Daily Publisher
Channel: GTA6_DS (UCU4JAQ7BGkZW1BYkeZWBCww)
Applies 4-layer anti-detection remixing and uploads publicly to YouTube Shorts.
"""

import os
import sys
import json
import re
import argparse
import subprocess
from datetime import datetime, timezone
import shutil
from PIL import Image, ImageDraw, ImageFont

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle

BASE_DIR = "/home/samirkhadka/ytbe" if os.path.exists("/home/samirkhadka/ytbe") else "."
MANIFEST_FILE = os.path.join(BASE_DIR, "manifest_gta6.json")
TMP_DIR = os.path.join(BASE_DIR, "tmp_remix_gta6")
LOCAL_TOKEN_FILE = os.path.expanduser("~/.youtube_token.pickle")
COOKIES_FILE = "/home/samirkhadka/instagram_cookies.txt"

os.makedirs(TMP_DIR, exist_ok=True)

def get_authenticated_service():
    client_id = os.environ.get("GTA6_YT_CLIENT_ID")
    client_secret = os.environ.get("GTA6_YT_CLIENT_SECRET")
    refresh_token = os.environ.get("GTA6_YT_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        print("[AUTH] Using GitHub Secrets / environment credentials for GTA6_DS...")
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret
        )
        creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        # Channel Safety Lock
        ch_resp = yt.channels().list(part="snippet", mine=True).execute()
        if ch_resp.get("items"):
            cur_id = ch_resp["items"][0]["id"]
            cur_title = ch_resp["items"][0]["snippet"]["title"]
            if cur_id != "UCU4JAQ7BGkZW1BYkeZWBCww":
                raise ValueError(f"FATAL: Connected channel {cur_title} ({cur_id}) does not match GTA6_DS (UCU4JAQ7BGkZW1BYkeZWBCww)! Aborting.")
        return yt

    elif os.path.exists(LOCAL_TOKEN_FILE):
        print(f"[AUTH] Using local token file {LOCAL_TOKEN_FILE}...")
        with open(LOCAL_TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[AUTH] Refreshing expired token...")
                creds.refresh(Request())
                with open(LOCAL_TOKEN_FILE, "wb") as f:
                    pickle.dump(creds, f)
        yt = build("youtube", "v3", credentials=creds)
        # Channel Safety Lock
        ch_resp = yt.channels().list(part="snippet", mine=True).execute()
        if ch_resp.get("items"):
            cur_id = ch_resp["items"][0]["id"]
            cur_title = ch_resp["items"][0]["snippet"]["title"]
            if cur_id != "UCU4JAQ7BGkZW1BYkeZWBCww":
                raise ValueError(f"FATAL: Connected channel {cur_title} ({cur_id}) does not match GTA6_DS (UCU4JAQ7BGkZW1BYkeZWBCww)! Aborting.")
        return yt

    else:
        raise RuntimeError("No valid YouTube credentials found in environment or local pickle file.")

def make_overlay_badge(title_hook="", channel_badge="★ GTA6_DS • DAILY 2K CLIPS ★"):
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"

    font_title = ImageFont.truetype(font_path, 42)
    font_badge = ImageFont.truetype(font_path, 28)

    # 1. Top Hook Banner (Neon Vice City Hot Pink + Cyan inner outline)
    clean_hook = re.sub(r'[^\w\s\-\:\.\,\!\?\#\⚡\★\•\💀\🔥\🌴\🚨]', '', title_hook).strip()
    if clean_hook:
        bbox = font_title.getbbox(clean_hook)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        bx0 = (1080 - tw) // 2 - 32
        by0 = 140
        bx1 = (1080 + tw) // 2 + 32
        by1 = by0 + th + 36

        # Draw glowing Vice City rounded box
        draw.rounded_rectangle([bx0-4, by0-4, bx1+4, by1+4], radius=22, fill=(0, 0, 0, 180))
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=20, fill=(12, 10, 18, 245), outline=(255, 45, 85, 255), width=4)
        draw.rounded_rectangle([bx0+5, by0+5, bx1-5, by1-5], radius=15, outline=(0, 240, 255, 180), width=2)

        tx = (1080 - tw) // 2
        ty = by0 + 18 - bbox[1]
        draw.text((tx+3, ty+3), clean_hook, font=font_title, fill=(0, 0, 0, 255))
        draw.text((tx, ty), clean_hook, font=font_title, fill=(255, 255, 255, 255))

    # 2. Bottom Banner positioning (y=1780 to cover previous clipper handles)
    w_bbox = font_badge.getbbox(channel_badge)
    ww = w_bbox[2] - w_bbox[0]
    wh = w_bbox[3] - w_bbox[1]
    wx0 = (1080 - ww) // 2 - 28
    wy0 = 1780
    wx1 = (1080 + ww) // 2 + 28
    wy1 = wy0 + wh + 28

    draw.rounded_rectangle([wx0-3, wy0-3, wx1+3, wy1+3], radius=18, fill=(0, 0, 0, 200))
    draw.rounded_rectangle([wx0, wy0, wx1, wy1], radius=16, fill=(14, 12, 22, 245), outline=(0, 240, 255, 240), width=3)
    wtx = (1080 - ww) // 2
    wty = wy0 + 14 - w_bbox[1]
    draw.text((wtx+2, wty+2), channel_badge, font=font_badge, fill=(0, 0, 0, 255))
    draw.text((wtx, wty), channel_badge, font=font_badge, fill=(255, 215, 0, 255))

    return img

def download_clip(url, target_path, source="instagram"):
    if os.path.exists(target_path) and os.path.getsize(target_path) > 100 * 1024:
        print(f"[CACHE] Using already downloaded video: {target_path}")
        return target_path

    print(f"[DOWNLOAD] Downloading on-the-fly from {url}...")
    cookie_path = None
    if os.environ.get("INSTAGRAM_COOKIES"):
        cookie_path = "/tmp/gh_ig_cookies.txt"
        with open(cookie_path, "w") as f:
            f.write(os.environ["INSTAGRAM_COOKIES"])
    elif os.path.exists(COOKIES_FILE):
        cookie_path = COOKIES_FILE

    base_cmd = [
        "yt-dlp", "--no-warnings",
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", target_path
    ]
    if source == "instagram" and cookie_path and os.path.exists(cookie_path):
        try:
            subprocess.run(base_cmd + ["--cookies", cookie_path, url], check=True)
            return target_path
        except subprocess.CalledProcessError as e:
            print(f"[RETRY] Instagram cookie download failed ({e}). Retrying without cookies...")

    subprocess.run(base_cmd + [url], check=True)
    return target_path

def get_video_dimensions(video_path):
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", video_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True).stdout.strip()
        if res and "," in res:
            w, h = map(int, res.split(","))
            return w, h
    except Exception:
        pass
    return 1080, 1920

def upscale_video_2k(raw_path, out_path):
    w, h = get_video_dimensions(raw_path)
    if w > h:
        # Landscape video (16:9): upscale to 2560x1440 2K QHD (no conversion/cropping)
        scale_filter = "scale=2560:1440:flags=lanczos,cas=strength=0.35"
        print(f"[UPSCALE] Landscape video detected ({w}x{h}) -> Upscaling to native 2560x1440 2K QHD...")
    else:
        # Vertical video (9:16): upscale to 1440x2560 2K Vertical
        scale_filter = "scale=1440:2560:flags=lanczos,cas=strength=0.35"
        print(f"[UPSCALE] Vertical video detected ({w}x{h}) -> Upscaling to native 1440x2560 2K Vertical...")

    cmd = [
        "ffmpeg", "-y", "-i", raw_path,
        "-vf", scale_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        out_path
    ]
    subprocess.run(cmd, check=True)
    print(f"[UPSCALE SUCCESS] Created 2K master: {out_path} ({os.path.getsize(out_path)/(1024*1024):.1f} MB)")
    return out_path

def remix_video(raw_path, out_path, title_hook="", channel_badge="★ GTA6_DS • DAILY 2K CLIPS ★"):
    print(f"[REMIX] Applying 4-layer anti-detection remix filters with Neon Hook: '{title_hook}'...")
    ov = make_overlay_badge(title_hook, channel_badge)
    ov_path = os.path.join(TMP_DIR, "ov_gta6_temp.png")
    ov.save(ov_path)

    cmd = [
        "ffmpeg", "-y", "-i", raw_path, "-i", ov_path,
        "-filter_complex", (
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            "eq=contrast=1.05:brightness=0.01:saturation=1.10[base];"
            "[base][1:v]overlay=0:0[vout];"
            "[0:a]atempo=1.025,volume=1.05[aout]"
        ),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-b:v", "10M", "-maxrate", "14M", "-bufsize", "20M",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", "58",
        out_path
    ]
    subprocess.run(cmd, check=True)
    print(f"[REMIX SUCCESS] Created: {out_path} ({os.path.getsize(out_path)/(1024*1024):.1f} MB)")
    return out_path

def upload_short(youtube, file_path, title, description, tags, privacy="public"):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "20" # Gaming category
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(file_path, chunksize=4*1024*1024, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    print(f"[YOUTUBE] Uploading '{title}' ({os.path.getsize(file_path)/(1024*1024):.1f} MB) as {privacy}...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[YOUTUBE] Progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    video_url = f"https://youtube.com/shorts/{video_id}"
    print(f"[YOUTUBE SUCCESS] Uploaded Live: {video_url}")
    return video_id, video_url

def main():
    parser = argparse.ArgumentParser(description="GTA6_DS Daily YouTube Publisher")
    parser.add_argument("--day", default="auto", help="Day number to publish or 'auto'")
    parser.add_argument("--mode", default="remix", choices=["remix", "upscale", "original"], help="Upload mode: 'remix' (default: Vice City neon hook + anti-detection + 2K badge), 'upscale' (2K Quad-HD + AMD CAS), or 'original' (raw)")
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"], help="Privacy status")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without uploading")
    args = parser.parse_args()

    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)

    schedule = manifest["schedule"]
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.day == "auto":
        # Check if already published today (allow max 2 Shorts per day, min 3.5 hours apart)
        today_published = []
        for entry in schedule:
            pub_at = entry.get("published_at")
            if pub_at and pub_at.startswith(today_str):
                today_published.append(entry)

        if len(today_published) >= 2:
            print(f"[THROTTLE] Already reached max 2 Shorts published today ({today_str}). Skipping.")
            return 0

        if len(today_published) == 1:
            try:
                last_pub = datetime.fromisoformat(today_published[-1]["published_at"])
                hours_since = (datetime.now(timezone.utc) - last_pub).total_seconds() / 3600
                if hours_since < 3.5:
                    print(f"[THROTTLE] Only {hours_since:.1f} hours since last upload today. Need >= 3.5 hrs spacing. Skipping.")
                    return 0
            except Exception:
                pass

        queued_entries = [e for e in schedule if e.get("status") == "queued"]
        if not queued_entries:
            print("[INFO] All days in manifest are published! Queue complete.")
            return 0
    else:
        day_num = int(args.day)
        target_entry = next((e for e in schedule if e["day"] == day_num), None)
        if not target_entry:
            print(f"[ERROR] Day {day_num} not found in {MANIFEST_FILE}")
            return 1
        queued_entries = [target_entry]

    target_entry = None
    raw_path = None
    for cand in queued_entries:
        day_num = cand["day"]
        print(f"\n==========================================")
        print(f"🎬 Processing GTA6_DS Day {day_num} [{args.mode.upper()} QUALITY]: {cand['title']}")
        print(f"🔗 Source URL: {cand['url']}")
        print(f"==========================================\n")

        cand_raw_path = os.path.join(TMP_DIR, f"raw_gta6_day_{day_num}.mp4")
        if not os.path.exists(cand_raw_path) and os.path.exists("/tmp/gta6_sample.mp4") and day_num == 1:
            shutil.copy2("/tmp/gta6_sample.mp4", cand_raw_path)
            target_entry = cand
            raw_path = cand_raw_path
            break
        try:
            download_clip(cand["url"], cand_raw_path, source=cand.get("source", "instagram"))
            target_entry = cand
            raw_path = cand_raw_path
            break
        except Exception as e:
            print(f"[SKIP] Day {day_num} unavailable/failed download ({e}). Marking unavailable...")
            cand["status"] = "unavailable"
            with open(MANIFEST_FILE, "w") as f:
                json.dump(manifest, f, indent=2)
            if args.day != "auto":
                return 1

    if not target_entry or not raw_path:
        print("[ERROR] No downloadable queued GTA6_DS clips remaining.")
        return 1

    day_num = target_entry["day"]

    if args.mode == "upscale":
        upscaled_path = os.path.join(TMP_DIR, f"upscale_2k_gta6_day_{day_num}.mp4")
        upload_path = upscale_video_2k(raw_path, upscaled_path)
    elif args.mode == "original":
        upload_path = raw_path
        print(f"[MODE] ORIGINAL QUALITY: Skipping re-encode to preserve 100% untouched native bitrate ({os.path.getsize(upload_path)/(1024*1024):.1f} MB)")
    else:
        remixed_path = os.path.join(TMP_DIR, f"remix_gta6_day_{day_num}.mp4")
        clean_hook = re.sub(r'[^\w\s\-\:\.\,\!\?]', '', target_entry["title"].split("#")[0]).strip().upper()[:36]
        remix_video(raw_path, remixed_path, title_hook=clean_hook)
        upload_path = remixed_path

    if args.dry_run:
        print("[DRY-RUN] Finished render. Skipping upload.")
        return 0

    yt = get_authenticated_service()
    vid_id, vid_url = upload_short(
        yt, upload_path,
        target_entry["title"],
        target_entry["description"],
        target_entry["tags"],
        privacy=args.privacy
    )

    target_entry["status"] = "published"
    target_entry["youtube_id"] = vid_id
    target_entry["published_url"] = vid_url
    target_entry["published_at"] = datetime.now(timezone.utc).isoformat()

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"💾 Updated {MANIFEST_FILE} for Day {day_num}.")
    print(f"🎉 Live URL: {vid_url}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
