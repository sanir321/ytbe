# ytbe

**YouTube Bot for Instagram Engagement** — Automated Instagram Reel → YouTube Shorts pipeline.

Downloads one reel per day from a pre-collected URL queue, processes it with FFmpeg, generates AI-powered captions, and uploads as a public YouTube Short. Runs unattended on Railway free tier.

## Architecture

```
reels.txt ──► IG Downloader ──► Video Processor ──► Caption Generator ──► YT Uploader ──► YouTube
  (546 URLs)    (anonymous)       (FFmpeg)            (Kilo Gateway)        (API v3)         (public)

                └── queue.db (SQLite) tracks each reel through every stage ──┘
```

### Pipeline (runs daily at 07:30 IST)

| Step | Module | What it does |
|------|--------|-------------|
| 1 | `ig_downloader.py` | Reads next URL from `reels.txt`, downloads the video via `instaloader` (anonymous, no login) |
| 2 | `video_processor.py` | Trims to ≤60s, scales/pads to 1080×1920 portrait, `-threads 2` to prevent OOM |
| 3 | `caption_generator.py` | Calls `openrouter/free` on Kilo Gateway → generates title + 150–200 word description + 30 hashtags |
| 4 | `yt_uploader.py` | Resumable upload via YouTube Data API v3, privacy = `public` |

### Self-Heal

On container restart, if `reels_used.txt` is empty but the DB has entries (user restored `reels.txt` from git), the queue is auto-reset for a clean start.

## Project Structure

```
├── main.py                      # Entry point: APScheduler + health server + graceful shutdown
├── config/
│   └── settings.py              # Env var loader, validation, path derivation
├── tracker/
│   ├── db.py                    # SQLite queue (WAL mode, BEGIN IMMEDIATE, full status flow)
│   └── reel_url_store.py        # File-based URL queue, seeding & staleness detection
├── modules/
│   ├── ig_downloader.py         # Anonymous Instagram downloader (no login needed)
│   ├── video_processor.py       # FFmpeg wrapper — trim, scale, pad
│   ├── caption_generator.py     # AI caption generation via Kilo Gateway (OpenAI SDK)
│   └── yt_uploader.py           # YouTube Data API v3 — resumable upload, token refresh
├── scripts/
│   ├── test_pipeline.py         # Manual pipeline test with 8 CLI flags
│   └── yt_oauth_setup.py        # OAuth token exchange helper
├── data/
│   ├── reels.txt                # 546 unused reel URLs (git-tracked)
│   └── reels_used.txt           # Consumed URLs with timestamps (git-tracked)
├── tests/                       # 61 tests across 5 test files
├── Dockerfile                   # python:3.13-slim + FFmpeg
└── railway.json                 # Docker builder config
```

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `KILO_API_KEY` | Kilo Gateway API key for AI caption generation |
| `YT_CLIENT_ID` | YouTube OAuth 2.0 client ID |
| `YT_CLIENT_SECRET` | YouTube OAuth 2.0 client secret |
| `YT_REFRESH_TOKEN` | YouTube OAuth 2.0 refresh token |
| `DATA_DIR` | Persistent volume path (default: `/data`) |

Optional: `IG_USERNAME`, `IG_PASSWORD`, `IG_TARGET` (not needed for anonymous download mode), `CRON_HOUR`, `CRON_MINUTE`, `PORT`.

## Deployment (Railway)

1. Fork/push this repo
2. Set the 5 required env vars in Railway dashboard
3. Add a persistent volume at `/data` (for queue.db, videos, logs)
4. Deploy via Dockerfile (handled by `railway.json`)

The bot starts immediately, schedules the first pipeline run for 07:30 IST, and listens on port 8080 for Railway health checks.

## Local Development

```bash
pip install -r requirements.txt
# set env vars in .env
python main.py
# or test a single pipeline step:
python scripts/test_pipeline.py --download
python scripts/test_pipeline.py --upload-one
python scripts/yt_oauth_setup.py --client-id YOUR_ID --client-secret YOUR_SECRET
```

## Key Design Decisions

- **File-based URL queue** → 546 pre-collected reel URLs sidestep Instagram's blocked API entirely. No login, no scraping, no browser needed on Railway.
- **No Instagram credentials** → `instaloader.Post.from_shortcode()` resolves public video URLs anonymously. The 403 GraphQL warning is harmless.
- **`-threads 2` on FFmpeg** → Railway free containers have ~512 MB RAM. Auto-detected 60 threads were OOM-killed.
- **`BEGIN IMMEDIATE` on SQLite** → Prevents race conditions on concurrent APScheduler runs.
- **`DATA_DIR=/data`** → All persistent state (queue.db, videos, logs) lives on the Railway volume, survives container restarts.
- **Self-heal** → On git restore (which resets `reels.txt`), the pipeline detects a stale DB and clears it automatically.
