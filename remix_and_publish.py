#!/usr/bin/env python3
"""
Autonomous Viral Shorts Remixer & Publisher for GitHub Actions
Downloads from Instagram (or uses cached local video), applies anti-detection remixing:
- If duration <= 60s: Uploads as single Short
- If duration > 60s: Splits into Part 1 & Part 2, uploading BOTH with explicit linked captions
- Publishes to YouTube Data API v3 & Rumble Direct API
- Updates viral_queue.json and commits back to GitHub repository
"""

import os
import sys
import json
import math
import time
import random
import argparse
import subprocess
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from publish import get_youtube_client, upload_short, upload_to_rumble

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = os.path.join(BASE_DIR, "tmp_remix")
QUEUE_FILE = os.path.join(BASE_DIR, "viral_queue.json")
os.makedirs(TMP_DIR, exist_ok=True)

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

def make_overlay(title_text, bottom_badge="ROBLOX STORY  •  LIKE & SUBSCRIBE", cta_text=None):
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_title = get_system_font(40)
    font_badge = get_system_font(22)
    font_cta = get_system_font(32)

    # 1. Top Hook Title Header
    bbox = font_title.getbbox(title_text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 36, 18
    bx0 = (1080 - tw) // 2 - pad_x
    by0 = 135
    bx1 = (1080 + tw) // 2 + pad_x
    by1 = by0 + th + (pad_y * 2)

    draw.rounded_rectangle([bx0-4, by0-4, bx1+4, by1+4], radius=22, fill=(0, 0, 0, 160))
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=20, fill=(12, 12, 18, 240), outline=(255, 45, 85, 255), width=4)
    draw.rounded_rectangle([bx0+4, by0+4, bx1-4, by1-4], radius=16, outline=(255, 215, 0, 150), width=2)
    
    tx = (1080 - tw) // 2
    ty = by0 + pad_y - bbox[1]
    draw.text((tx+2, ty+2), title_text, font=font_title, fill=(0, 0, 0, 255))
    draw.text((tx, ty), title_text, font=font_title, fill=(255, 255, 255, 255))

    # 2. Bottom Right Watermark Concealment Badge
    w_box = [570, 1800, 1060, 1870]
    draw.rounded_rectangle([w_box[0]+2, w_box[1]+2, w_box[2]+2, w_box[3]+2], radius=14, fill=(0, 0, 0, 180))
    draw.rounded_rectangle(w_box, radius=12, fill=(14, 14, 20, 245), outline=(255, 215, 0, 230), width=3)
    
    b_bbox = font_badge.getbbox(bottom_badge)
    bw, bh = b_bbox[2] - b_bbox[0], b_bbox[3] - b_bbox[1]
    btx = w_box[0] + (w_box[2] - w_box[0] - bw) // 2
    bty = w_box[1] + (w_box[3] - w_box[1] - bh) // 2 - b_bbox[1]
    draw.text((btx, bty), bottom_badge, font=font_badge, fill=(255, 255, 255, 255))

    # 3. Optional CTA (End Screen for Part 1)
    if cta_text:
        c_bbox = font_cta.getbbox(cta_text)
        cw, ch = c_bbox[2] - c_bbox[0], c_bbox[3] - c_bbox[1]
        cx0, cy0 = (1080 - cw) // 2 - 28, 1660
        cx1, cy1 = (1080 + cw) // 2 + 28, cy0 + ch + 30
        draw.rounded_rectangle([cx0-3, cy0-3, cx1+3, cy1+3], radius=18, fill=(0, 0, 0, 200))
        draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=16, fill=(255, 45, 85, 240), outline=(255, 255, 255, 255), width=3)
        draw.text(((1080 - cw) // 2, cy0 + 15 - c_bbox[1]), cta_text, font=font_cta, fill=(255, 255, 255, 255))

    return img

def get_video_duration(fpath):
    p_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", fpath]
    pres = subprocess.run(p_cmd, capture_output=True, text=True)
    try:
        return float(json.loads(pres.stdout)["format"]["duration"])
    except Exception:
        return 0.0

def download_instagram_video(url, out_prefix):
    out_tmpl = os.path.join(TMP_DIR, f"{out_prefix}.%(ext)s")
    cmd = [
        "yt-dlp", "--no-warnings",
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--write-info-json",
        "-o", out_tmpl,
    ]
    
    # Cookie detection for local and cloud environments
    cookies_path = None
    if os.environ.get("INSTAGRAM_COOKIES_FILE") and os.path.exists(os.environ["INSTAGRAM_COOKIES_FILE"]):
        cookies_path = os.environ["INSTAGRAM_COOKIES_FILE"]
    elif os.path.exists("/home/samirkhadka/instagram_cookies.txt"):
        cookies_path = "/home/samirkhadka/instagram_cookies.txt"
    elif os.environ.get("INSTAGRAM_COOKIES"):
        tmp_c = os.path.join(TMP_DIR, "ig_cookies.txt")
        try:
            with open(tmp_c, "w") as cf:
                cf.write(os.environ["INSTAGRAM_COOKIES"])
            cookies_path = tmp_c
        except Exception:
            pass

    if cookies_path:
        cmd.extend(["--cookies", cookies_path])

    cmd.append(url)
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[WARN] Failed to download {url} with cookies: {e}")
        if cookies_path:
            print("[FALLBACK] Retrying download anonymously without cookies...")
            anon_cmd = [c for c in cmd if c not in ["--cookies", cookies_path]]
            try:
                subprocess.run(anon_cmd, check=True)
            except subprocess.CalledProcessError as err2:
                print(f"[ERROR] Anonymous download also failed: {err2}")
                return None, "", "", 0.0
        else:
            return None, "", "", 0.0

    fpath = os.path.join(TMP_DIR, f"{out_prefix}.mp4")
    if not os.path.exists(fpath):
        return None, "", "", 0.0

    info_path = os.path.join(TMP_DIR, f"{out_prefix}.info.json")
    desc, title = "", f"Roblox Story ({out_prefix})"
    if os.path.exists(info_path):
        try:
            with open(info_path) as jf:
                info = json.load(jf)
                desc = info.get("description", "")
                first_line = desc.split("\n")[0].strip()
                if first_line:
                    title = first_line[:48]
        except Exception:
            pass
            
    dur = get_video_duration(fpath)
    return fpath, title, desc, round(dur, 1)

def commit_manifest():
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    print("[GIT] Configuring git for queue auto-commit...")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"])
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    subprocess.run(["git", "add", QUEUE_FILE])
    res = subprocess.run(["git", "commit", "-m", "chore(queue): update viral shorts queue [skip ci]"])
    if res.returncode == 0:
        print("[GIT] Pushing queue updates back to repository...")
        subprocess.run(["git", "pull", "--rebase"])
        subprocess.run(["git", "push"])

IST = timezone(timedelta(hours=5, minutes=30))
MAX_PART_SEC = 48.0


def pick_random_publish_at():
    """Return a randomized UTC ISO timestamp between 17:00 and 23:30 IST today (or None if too late)."""
    now_ist = datetime.now(IST)
    win_start = now_ist.replace(hour=17, minute=0, second=0, microsecond=0)
    win_end = now_ist.replace(hour=23, minute=30, second=0, microsecond=0)
    earliest = max(win_start, now_ist + timedelta(minutes=15))
    if earliest >= win_end:
        return None
    span_mins = int((win_end - earliest).total_seconds() // 60)
    offset_mins = random.randint(0, max(0, span_mins))
    target_ist = earliest + timedelta(minutes=offset_mins)
    return target_ist.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def process_target(target_item, target_url, yt, args, queue_data):
    title = target_item.get("title", "Roblox Story") if target_item else "Roblox Story"
    prefix = f"reel_{int(time.time())}_{target_item.get('id', 'item') if target_item else 'url'}"
    raw_path = None
    dur = 0.0

    # 1. Check if local video already exists
    if target_item and target_item.get("file_path") and os.path.exists(target_item["file_path"]):
        raw_path = target_item["file_path"]
        dur = target_item.get("duration_s") or round(get_video_duration(raw_path), 1)
        print(f"📦 Found local source video: {raw_path} (Duration: {dur}s)")
    else:
        print(f"⬇️ Downloading video from Instagram: {target_url}")
        raw_path, dl_title, _, dur = download_instagram_video(target_url, prefix)
        if not raw_path or not os.path.exists(raw_path):
            print(f"⚠️ Source video unavailable or removed on Instagram: {target_url}")
            if target_item:
                target_item["status"] = "unavailable"
            return False
        if not target_item or not target_item.get("title"):
            title = dl_title

    acc = target_item.get("account", "roblox").upper() if target_item else "ROBLOX"
    badge_label = f"@{acc} REMIX • LIKE & SUB"

    publish_at = None
    if args.privacy == "public" and not args.immediate:
        publish_at = pick_random_publish_at()
        if publish_at:
            print(f"🕒 Scheduled publishAt (UTC): {publish_at}")

    out_path = None

    # CASE 1: Single Short (<= 49s)
    if dur <= 49.0:
        print(f"🎬 Video duration {dur}s <= 49s -> Rendering as Single Short (<50s)")
        out_path = os.path.join(TMP_DIR, f"{prefix}_remix_short.mp4")
        ov = make_overlay(title, bottom_badge=badge_label)
        ov_path = os.path.join(TMP_DIR, f"{prefix}_ov.png")
        ov.save(ov_path)

        cmd = [
            "ffmpeg", "-y", "-i", raw_path, "-i", ov_path,
            "-filter_complex", "[0:v]scale=1080:1920,eq=contrast=1.06:brightness=0.01:saturation=1.12[base];[base][1:v]overlay=0:0[vout]",
            "-filter:a", "atempo=1.02,volume=1.05",
            "-map", "[vout]", "-map", "0:a",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-c:a", "aac", "-b:a", "192k",
            out_path
        ]
        subprocess.run(cmd, check=True)

        upload_title = f"{title} 🚨🎮 #Shorts"[:100]
        caption = f"{title} 🚨🎮 #Shorts\n\nWhat would you do? Comment below! 👇\n\n#Roblox #RobloxStory #Shorts #Animation #Viral #Gaming"
        tags = ["roblox", "shorts", "robloxstory", "animation", "gaming", "viral", "fyp"]

        yt_url, rumble_res = None, None
        if not args.dry_run:
            if yt and args.platform in ["all", "youtube"]:
                _, yt_url = upload_short(yt, out_path, upload_title, caption, tags, privacy=args.privacy, publish_at=publish_at)
            if args.platform in ["all", "rumble"]:
                rumble_res = upload_to_rumble(out_path, upload_title, caption, tags)
        else:
            print(f"[DRY-RUN] Simulating upload for: {upload_title} (publishAt={publish_at})")
            yt_url = "https://youtube.com/shorts/dry_run_test"
            rumble_res = {"url": "https://rumble.com/dry_run_test"}

        if target_item and not args.dry_run:
            target_item["status"] = "published"
            target_item["published_at"] = datetime.now(timezone.utc).isoformat()
            target_item["scheduled_for"] = publish_at or "immediate"
            target_item["published_youtube"] = yt_url
            target_item["published_rumble"] = rumble_res.get("url") if rumble_res else None

    # CASE 2: Multi-Part (> 49s) -> Split into N parts (<50s each), upload ONLY next_part today
    else:
        total_parts = max(2, math.ceil(dur / MAX_PART_SEC))
        part_dur = dur / total_parts
        part_num = int(target_item.get("next_part", 1)) if target_item else 1
        if part_num > total_parts:
            part_num = total_parts

        start_s = round((part_num - 1) * part_dur, 2)
        end_s = round(part_num * part_dur, 2) if part_num < total_parts else dur
        seg_dur = round(end_s - start_s, 1)
        is_finale = (part_num == total_parts)

        print(f"🎬 Duration {dur}s -> {total_parts} parts (~{round(part_dur,1)}s each). Rendering ONLY Part {part_num}/{total_parts} ({start_s}s-{end_s}s, {seg_dur}s)")

        out_path = os.path.join(TMP_DIR, f"{prefix}_part{part_num}.mp4")
        header_label = f"{title} (PART {part_num} FINALE)" if is_finale else f"{title} (PART {part_num}/{total_parts})"
        ov_main = make_overlay(header_label, bottom_badge=badge_label)
        ov_main_path = os.path.join(TMP_DIR, f"{prefix}_p{part_num}.png")
        ov_main.save(ov_main_path)

        if not is_finale:
            ov_cta = make_overlay(header_label, bottom_badge=badge_label, cta_text=f"👉 WATCH PART {part_num + 1} TOMORROW!")
            ov_cta_path = os.path.join(TMP_DIR, f"{prefix}_p{part_num}_cta.png")
            ov_cta.save(ov_cta_path)
            cta_start = max(0.0, seg_dur - 3.5)
            vf = f"[0:v]scale=1080:1920,eq=contrast=1.06:brightness=0.01:saturation=1.12[base];[base][1:v]overlay=0:0:enable='between(t,0,{cta_start})'[tmp];[tmp][2:v]overlay=0:0:enable='gte(t,{cta_start})'[vout]"
            cmd = [
                "ffmpeg", "-y", "-ss", str(start_s), "-to", str(end_s), "-i", raw_path,
                "-i", ov_main_path, "-i", ov_cta_path,
                "-filter_complex", vf,
                "-filter:a", "atempo=1.02,volume=1.05",
                "-map", "[vout]", "-map", "0:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-c:a", "aac", "-b:a", "192k",
                out_path
            ]
        else:
            cmd = [
                "ffmpeg", "-y", "-ss", str(start_s), "-to", str(end_s), "-i", raw_path,
                "-i", ov_main_path,
                "-filter_complex", "[0:v]scale=1080:1920,eq=contrast=1.06:brightness=0.01:saturation=1.12[base];[base][1:v]overlay=0:0[vout]",
                "-filter:a", "atempo=1.02,volume=1.05",
                "-map", "[vout]", "-map", "0:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-c:a", "aac", "-b:a", "192k",
                out_path
            ]

        subprocess.run(cmd, check=True)

        if is_finale:
            upload_title = f"{title} (Part {part_num} Finale) 🚨👑 #Shorts"[:100]
            caption = (
                f"{title} (Part {part_num} Finale) 🚨👑 #Shorts\n\n"
                f"PART {part_num}: The final conclusion!\n"
                f"(Watch Part 1 on our channel if you missed the beginning!)\n\n"
                f"💬 Did they make the right choice? Leave a comment! 👇\n\n"
                f"#Roblox #RobloxStory #Shorts #Animation #Viral #Gaming"
            )
        else:
            upload_title = f"{title} (Part {part_num}/{total_parts}) 🚨👶 #Shorts"[:100]
            caption = (
                f"{title} (Part {part_num}/{total_parts}) 🚨👶 #Shorts\n\n"
                f"Part {part_num} of {total_parts}! What happens next? 😱\n\n"
                f"👉 PART {part_num + 1} DROPS TOMORROW — Subscribe so you don't miss it!\n"
                f"💬 What would you do? Comment below! 👇\n\n"
                f"#Roblox #RobloxStory #Shorts #Animation #Viral #Gaming"
            )

        tags = ["roblox", "shorts", "robloxstory", "animation", "gaming", "viral", "fyp", f"part{part_num}"]
        yt_url, rm_res = None, None

        if not args.dry_run:
            print(f"🚀 Uploading Part {part_num}/{total_parts} ({seg_dur}s)...")
            if yt and args.platform in ["all", "youtube"]:
                _, yt_url = upload_short(yt, out_path, upload_title, caption, tags, privacy=args.privacy, publish_at=publish_at)
            if args.platform in ["all", "rumble"]:
                rm_res = upload_to_rumble(out_path, upload_title, caption, tags)
        else:
            print(f"[DRY-RUN] Simulating upload Part {part_num}/{total_parts}: {upload_title} ({seg_dur}s, publishAt={publish_at})")
            yt_url = f"https://youtube.com/shorts/dry_run_p{part_num}"
            rm_res = {"url": f"https://rumble.com/dry_run_p{part_num}"}

        if target_item and not args.dry_run:
            now_iso = datetime.now(timezone.utc).isoformat()
            target_item["total_parts"] = total_parts
            target_item["last_uploaded_at"] = now_iso
            target_item[f"part{part_num}"] = {
                "youtube": yt_url,
                "rumble": rm_res.get("url") if rm_res else None,
                "published_at": now_iso,
                "scheduled_for": publish_at or "immediate",
                "duration_s": seg_dur
            }
            if is_finale:
                target_item["status"] = "published"
                target_item["published_at"] = now_iso
                target_item.pop("next_part", None)
            else:
                target_item["status"] = "in_progress"
                target_item["next_part"] = part_num + 1

    if out_path and os.path.exists(out_path):
        try:
            os.remove(out_path)
        except Exception:
            pass
    return True


def uploaded_recently(queue_data, hours=18.0):
    now = datetime.now(timezone.utc)
    for item in queue_data.get("items", []):
        ts_list = [item.get("last_uploaded_at"), item.get("published_at")]
        for k, v in item.items():
            if k.startswith("part") and isinstance(v, dict):
                ts_list.append(v.get("published_at"))
        for ts in ts_list:
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if (now - dt).total_seconds() < hours * 3600:
                    return True, round((now - dt).total_seconds() / 3600, 1)
            except Exception:
                pass
    return False, 0.0


def main():
    parser = argparse.ArgumentParser(description="Viral Shorts Remixer & Publisher")
    parser.add_argument("--url", default=None, help="Instagram reel URL")
    parser.add_argument("--queue", action="store_true", help="Process next items from viral_queue.json")
    parser.add_argument("--target-id", default=None, help="Specific ID in viral_queue.json to process")
    parser.add_argument("--limit", type=int, default=1, help="Number of items to process from queue")
    parser.add_argument("--platform", default="all", choices=["all", "youtube", "rumble"])
    parser.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    parser.add_argument("--immediate", action="store_true", help="Publish immediately instead of scheduling randomized publishAt")
    parser.add_argument("--force", action="store_true", help="Bypass 1-Short-per-day 18h cooldown guard")
    parser.add_argument("--dry-run", action="store_true", help="Remix without uploading")
    args = parser.parse_args()

    yt = get_youtube_client() if args.platform in ["all", "youtube"] and not args.dry_run else None

    queue_data = {"items": []}
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE) as qf:
                queue_data = json.load(qf)
        except Exception as e:
            print(f"[WARN] Error reading {QUEUE_FILE}: {e}")

    # Case 1: Custom URL
    if args.url:
        process_target(None, args.url, yt, args, queue_data)
        return 0

    # Case 2: Specific Target ID from Queue
    if args.target_id:
        found = False
        for item in queue_data.get("items", []):
            if item.get("id") == args.target_id:
                found = True
                process_target(item, item["instagram_url"], yt, args, queue_data)
                break
        if not found:
            print(f"[ERROR] Target ID '{args.target_id}' not found in {QUEUE_FILE}")
            return 1
    else:
        # Daily 1-Short-per-day cooldown guard
        if not args.dry_run and not args.force:
            recent, hrs = uploaded_recently(queue_data, hours=18.0)
            if recent:
                print(f"[THROTTLE] Already uploaded a Short {hrs}h ago (<18h). Enforcing 1 Short/day rule. Exiting cleanly.")
                return 0

        # Case 3: Resume 'in_progress' story first (Part 2, Part 3...), else pick next 'queued_ready_to_remix'
        candidates = [x for x in queue_data.get("items", []) if x.get("status") == "in_progress"]
        candidates += [x for x in queue_data.get("items", []) if x.get("status") == "queued_ready_to_remix"]

        processed_count = 0
        for item in candidates:
            ok = process_target(item, item["instagram_url"], yt, args, queue_data)
            if ok:
                processed_count += 1
                if processed_count >= args.limit:
                    break

        if processed_count == 0:
            print("[INFO] No pending items processed.")
            return 0

    if not args.dry_run:
        queue_data["ready_items"] = sum(1 for x in queue_data.get("items", []) if x.get("status") == "queued_ready_to_remix")
        queue_data["in_progress_items"] = sum(1 for x in queue_data.get("items", []) if x.get("status") == "in_progress")
        queue_data["published_items"] = sum(1 for x in queue_data.get("items", []) if x.get("status") == "published")

        with open(QUEUE_FILE, "w") as qf:
            json.dump(queue_data, qf, indent=2)
        print(f"💾 Updated {QUEUE_FILE} (In-progress: {queue_data['in_progress_items']}, Ready: {queue_data['ready_items']})")

        commit_manifest()
    else:
        print("[DRY-RUN] Verification complete. Queue file and git commit untouched.")
    print("🎉 All tasks completed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
