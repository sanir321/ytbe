#!/usr/bin/env python3
"""
AWS Cloud Rumble View Booster & Algorithmic Accelerator
Dispatches high-retention views via AWS Lambda Function URL in ap-southeast-2.
Simulates real mobile/desktop viewer traffic with randomized referrers (Reddit, Twitter, Google, Discord)
and HTTP 206 Partial Content byte-range streaming.
Can boost a single video or all published videos in manifest.json.
"""

import os
import sys
import json
import time
import re
import argparse
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional

LAMBDA_FUNCTION_URL = "https://vhtkaafmeq3ggnqljg63pkh72y0eevxe.lambda-url.ap-southeast-2.on.aws/"

def resolve_video(video_url: str) -> Dict[str, Any]:
    """Extract embed_id and stream_url from a Rumble video URL."""
    encoded_url = urllib.parse.quote(video_url)
    oembed_url = f"https://rumble.com/api/Media/oembed.json?url={encoded_url}"
    req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
    
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
    
    title = data.get("title", "Untitled")
    html = data.get("html", "")
    m = re.search(r'/embed/(?:[a-zA-Z0-9_]+\.)?([a-zA-Z0-9_]+)/', html)
    if not m:
        raise ValueError(f"Could not extract embed ID from {video_url}")
    embed_id = m.group(1)
    
    # Extract 360p or 480p stream URL
    embed_url = f"https://rumble.com/embed/{embed_id}/"
    embed_req = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(embed_req, timeout=10) as r:
        embed_html = r.read().decode("utf-8", errors="ignore")
    
    stream_url = None
    for m_res in re.finditer(r'"(\d{3,4})":\{"url":"([^"]+)".*?"size":(\d+)', embed_html):
        res_p = int(m_res.group(1))
        url = m_res.group(2).replace(r"\/", "/")
        if res_p <= 480:
            stream_url = url
            break
    
    if not stream_url:
        # Fallback search for any mp4
        m_mp4 = re.findall(r'https:\/\/[a-zA-Z0-9.\-_]+\.rmbl\.ws\/[^\s"\']+\.mp4', embed_html)
        if m_mp4:
            stream_url = m_mp4[0]
            
    return {
        "title": title,
        "embed_id": embed_id,
        "stream_url": stream_url,
        "video_url": video_url
    }

def send_view_request(payload: dict) -> dict:
    """Send a single view invocation to AWS Lambda Function URL."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LAMBDA_FUNCTION_URL,
        data=data,
        headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            lat = int((time.time() - t0) * 1000)
            res = json.loads(resp.read().decode("utf-8"))
            res["latency_ms"] = lat
            return res
    except Exception as e:
        return {"ok": False, "error": str(e), "latency_ms": int((time.time() - t0) * 1000)}

def boost_video(meta: Dict[str, Any], count: int = 300, workers: int = 8, pace: float = 0.1) -> Dict[str, Any]:
    """Execute multi-threaded cloud boost for a single video."""
    print(f"\n==========================================")
    print(f"🚀 CLOUD BOOST: {meta['title']}")
    print(f"🎯 Embed ID: {meta['embed_id']}")
    print(f"⚡ Target Views: {count} | Workers: {workers}")
    print(f"==========================================")

    payload = {
        "embed_id": meta["embed_id"],
        "stream_url": meta["stream_url"]
    }

    successes = 0
    total_bytes = 0
    t_start = time.time()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for i in range(count):
            futures.append(executor.submit(send_view_request, payload))
            if pace > 0:
                time.sleep(pace)

        for idx, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            if res.get("ok"):
                successes += 1
                total_bytes += res.get("bytes_streamed", 0)
                if idx % 25 == 0 or idx == count:
                    print(f"[{idx}/{count}] ✅ Cloud Views: {successes} | Streamed: {total_bytes // (1024*1024)} MB | Last: {res.get('latency_ms')}ms")
            else:
                if idx % 25 == 0 or idx == count:
                    print(f"[{idx}/{count}] ⚠️ Error: {res.get('error')}")

    duration = round(time.time() - t_start, 1)
    mb = round(total_bytes / (1024 * 1024), 2)
    print(f"🏁 Completed {meta['title']}: {successes}/{count} views in {duration}s ({mb} MB cloud buffer)\n")
    return {
        "title": meta["title"],
        "embed_id": meta["embed_id"],
        "requested": count,
        "successes": successes,
        "duration_s": duration,
        "cloud_mb": mb
    }

def boost_all_manifest_videos(manifest_path: str, count_per_video: int = 300, workers: int = 8) -> List[Dict[str, Any]]:
    """Scan manifest.json and boost all published Rumble videos."""
    if not os.path.exists(manifest_path):
        print(f"[ERROR] Manifest not found: {manifest_path}")
        return []

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    schedule = manifest.get("schedule", [])
    published_rumble = [e for e in schedule if e.get("rumble_url")]

    if not published_rumble:
        print("[INFO] No published Rumble videos found in manifest to boost.")
        return []

    print(f"📋 Found {len(published_rumble)} published Rumble video(s) to boost.")
    results = []

    for entry in published_rumble:
        url = entry["rumble_url"]
        try:
            meta = resolve_video(url)
            # Give newest/primary video the full count, older videos 150 views for sustained retention
            target_count = count_per_video
            res = boost_video(meta, count=target_count, workers=workers)
            results.append(res)
            
            # Record boost stats in manifest
            entry["total_boosted_views"] = entry.get("total_boosted_views", 0) + res["successes"]
            entry["last_boosted_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        except Exception as e:
            print(f"[ERROR] Failed boosting {url}: {e}")

    # Save manifest with updated metrics
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"[MANIFEST] Updated boost records in {manifest_path}")

    return results

def main():
    parser = argparse.ArgumentParser(description="AWS Cloud Rumble View Booster")
    parser.add_argument("--url", help="Direct Rumble video URL to boost")
    parser.add_argument("--all", action="store_true", help="Boost all published videos in manifest.json")
    parser.add_argument("--count", type=int, default=300, help="Number of views to send (default: 300)")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent workers (default: 8)")
    parser.add_argument("--pace", type=float, default=0.08, help="Pacing delay between dispatches in seconds")
    parser.add_argument("--manifest", default="manifest.json", help="Path to manifest.json")
    args = parser.parse_args()

    if args.all:
        boost_all_manifest_videos(args.manifest, count_per_video=args.count, workers=args.workers)
    elif args.url:
        meta = resolve_video(args.url)
        boost_video(meta, count=args.count, workers=args.workers, pace=args.pace)
    else:
        # Default: Boost all published videos in manifest
        boost_all_manifest_videos(args.manifest, count_per_video=args.count, workers=args.workers)

if __name__ == "__main__":
    main()
