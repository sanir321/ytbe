<p align="center">
  <img src="https://img.shields.io/badge/python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.13">
  <img src="https://img.shields.io/badge/railway-deployed-0B0D0E?style=for-the-badge&logo=railway&logoColor=white" alt="Railway">
  <img src="https://img.shields.io/badge/instagram-reels-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram Reels">
  <img src="https://img.shields.io/badge/youtube-shorts-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube Shorts">
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge" alt="MIT">
</p>

<h1 align="center">ytbe</h1>
<p align="center"><b>YouTube Bot for Instagram Engagement</b></p>
<p align="center">Automated Instagram Reel → YouTube Shorts pipeline.<br>
Downloads, processes, captions, and uploads — daily, unattended, on Railway free tier.</p>

---

## Pipeline

```
                          ┌──────────────────┐
      reels.txt ──────────►  IG Downloader   │
      (546 URLs)          │  (anonymous)      │
                          └────────┬─────────┘
                                   │ .mp4
                                   ▼
                          ┌──────────────────┐
                          │ Video Processor  │
                          │  (FFmpeg)         │
                          │  • trim to 60s    │
                          │  • 1080×1920 pad  │
                          │  • -threads 2     │
                          └────────┬─────────┘
                                   │ processed.mp4
                                   ▼
                          ┌──────────────────┐
                          │ Caption Generator│
                          │  (Kilo Gateway)   │
                          │  • title          │
                          │  • description    │
                          │  • 30 hashtags    │
                          └────────┬─────────┘
                                   │ title + desc + tags
                                   ▼
                          ┌──────────────────┐
                          │  YT Uploader     │
                          │  (API v3)         │
                          │  • public upload  │
                          │  • token refresh  │
                          └────────┬─────────┘
                                   │ youtube.com/shorts/...
                                   ▼
                          ┌──────────────────┐
                          │     YouTube      │
                          │     Shorts       │
                          └──────────────────┘

                ┌─────────────────────────────────────────┐
                │  queue.db (SQLite) tracks every stage   │
                │  pending → downloaded → processed →     │
                │  caption_ready → posted                 │
                └─────────────────────────────────────────┘
```

**Schedule:** Daily at `07:30 IST` via APScheduler cron.

---

## Project Structure

```
📦 ytbe
├── 🐍 main.py                      # Entry point, scheduler, health server
├── 📁 config/
│   └── ⚙️ settings.py              # Env var loader & validation
├── 📁 tracker/
│   ├── 🗄️ db.py                    # SQLite queue (WAL, BEGIN IMMEDIATE)
│   └── 📜 reel_url_store.py        # File-based URL queue
├── 📁 modules/
│   ├── 📥 ig_downloader.py         # Anonymous Instagram downloader
│   ├── 🎬 video_processor.py       # FFmpeg trim/scale/pad
│   ├── 🤖 caption_generator.py     # AI captions via Kilo Gateway
│   └── 📤 yt_uploader.py           # YouTube Data API v3 uploader
├── 📁 scripts/
│   ├── 🧪 test_pipeline.py         # Manual pipeline tester (8 flags)
│   └── 🔑 yt_oauth_setup.py        # OAuth token exchange
├── 📁 data/
│   ├── 📄 reels.txt                # 546 unused reel URLs (git)
│   └── 📄 reels_used.txt           # Consumed URLs (git)
├── 📁 tests/                       # 61 tests across 5 files
├── 🐳 Dockerfile                   # python:3.13-slim + FFmpeg
└── 📋 railway.json                 # Docker builder config
```

---

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `KILO_API_KEY` | Kilo Gateway API key for AI caption generation |
| `YT_CLIENT_ID` | YouTube OAuth 2.0 client ID |
| `YT_CLIENT_SECRET` | YouTube OAuth 2.0 client secret |
| `YT_REFRESH_TOKEN` | YouTube OAuth 2.0 refresh token |
| `DATA_DIR` | Persistent volume path (default: `/data`) |

**Optional:** `IG_USERNAME`, `IG_PASSWORD`, `IG_TARGET` (not needed for anonymous download mode), `CRON_HOUR`, `CRON_MINUTE`, `PORT`.

---

## Deployment (Railway)

```bash
# 1. Push repo to GitHub
git push origin main

# 2. In Railway dashboard:
#    - New Project → Deploy from GitHub
#    - Add 5 env vars (see above)
#    - Add persistent volume → mount at /data
#    - Deploy — Dockerfile auto-detected
```

The bot starts, schedules the first run for next `07:30 IST`, and listens on `:8080` for health checks. Zero manual effort after deploy.

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Configure (set in .env or export)
export KILO_API_KEY=...
export YT_CLIENT_ID=...
export YT_CLIENT_SECRET=...
export YT_REFRESH_TOKEN=...

# Run the full bot
python main.py

# Test individual stages
python scripts/test_pipeline.py --download
python scripts/test_pipeline.py --upload-one

# Generate OAuth tokens
python scripts/yt_oauth_setup.py --client-id YOUR_ID --client-secret YOUR_SECRET
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **File-based URL queue** | 546 pre-collected URLs sidestep Instagram's blocked API — no login, no scraping on Railway |
| **Anonymous download** | `instaloader.Post.from_shortcode()` resolves public video URLs without credentials |
| **`-threads 2` FFmpeg** | Railway free containers (~512 MB RAM) were OOM-killed by 60 auto-detected x264 threads |
| **`BEGIN IMMEDIATE` SQLite** | Prevents race conditions on concurrent APScheduler runs |
| **`DATA_DIR=/data`** | All state on Railway persistent volume — survives restarts |
| **Self-heal** | On git restore, detects stale DB and clears it automatically |

---

<p align="center">
  <sub>Built with Python 3.13 · APScheduler · FFmpeg · Kilo Gateway · YouTube Data API v3</sub>
  <br>
  <sub>Runs on <a href="https://railway.app">Railway</a> free tier — ₹0 infra cost</sub>
</p>
