# ytbe — Instagram → YouTube Shorts CLI

Interactive CLI pipeline. Downloads Instagram reels, processes them with FFmpeg, generates AI captions via Kilo Gateway, and uploads to YouTube Shorts.

```bash
python ytbe.py
ytbe> help
ytbe> download
ytbe> process
ytbe> caption
ytbe> upload
```

## Structure

```
ytbe.py              Interactive REPL (entry point)
config/settings.py   Env var loading & validation
tracker/db.py        SQLite queue (WAL mode)
tracker/reel_url_store.py  File-based URL queue
modules/
  ig_downloader.py    Anonymous Instagram downloader
  video_processor.py  FFmpeg trim/scale/pad
  caption_generator.py AI captions (Kilo Gateway)
  yt_uploader.py      YouTube Data API v3
```

## Setup

```bash
pip install -r requirements.txt
```

Set in `.env` or environment:
- `KILO_API_KEY` — Kilo Gateway for AI captions
- `YT_CLIENT_ID` / `YT_CLIENT_SECRET` / `YT_REFRESH_TOKEN` — YouTube OAuth

## Usage

```bash
# Interactive mode
python ytbe.py

# One-off commands
python ytbe.py list
python ytbe.py upload
python ytbe.py run
```

Commands: `list`, `status`, `download`, `process`, `caption`, `upload`, `recent`, `run`, `help`, `exit`.
