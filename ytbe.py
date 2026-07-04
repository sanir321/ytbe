#!/usr/bin/env python3
"""ytbe - interactive TUI for the Instagram->YouTube Shorts pipeline.

Usage:
    python ytbe.py            Start the interactive TUI
    python ytbe.py <command>  Run one command and exit
"""

import json
import logging
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import load_settings, PipelineError
from tracker.db import QueueDB
from tracker.reel_url_store import set_data_dir as _init_reel_store, is_stale
from modules.ig_downloader import IGDownloader
from modules.video_processor import VideoProcessor
from modules.caption_generator import CaptionGenerator
from modules.yt_uploader import YTUploader

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

console = Console()
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("ytbe")


STATUS_COLORS = {
    "downloaded": "white",
    "processed": "yellow",
    "caption_ready": "blue",
    "posted": "green",
    "failed": "red",
}


def _ensure_db(settings):
    _init_reel_store(settings.data_dir)
    db_path = settings.data_dir / "queue.db"
    if is_stale() and db_path.exists():
        stale_count = QueueDB(db_path).count_total()
        if stale_count > 0:
            db_path.unlink()
            logger.info("Stale queue detected (%d entries) - reset", stale_count)
    return QueueDB(db_path)


# ── helpers ──────────────────────────────────────────────────────────────

def status_badge(s):
    c = STATUS_COLORS.get(s, "white")
    return f"[{c}]{s}[/]"


def fmt_title(r):
    return (r["yt_title"] or "(no title)")[:50]


def run_with_spinner(desc, fn, *a, **kw):
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn(f"[progress.description]{{task.description}}"),
        console=console,
        transient=True,
    ) as p:
        p.add_task(f"[cyan]{desc}", total=None)
        return fn(*a, **kw)


# ── commands ─────────────────────────────────────────────────────────────

def cmd_list(settings, db, args):
    rows = db._fetchall(
        "SELECT id, ig_shortcode, yt_title, status, error_msg FROM queue ORDER BY id ASC;"
    )
    if not rows:
        console.print("[yellow]Queue is empty.[/]")
        return
    table = Table(header_style="bold cyan", box=box.SIMPLE, padding=(0, 2))
    table.add_column("ID", style="dim", width=4, justify="right")
    table.add_column("Status", width=16)
    table.add_column("Title")
    for r in rows:
        label = status_badge(r["status"])
        err_msg = r["error_msg"] if r["error_msg"] else ""
        if err_msg:
            label += f" [dim]({err_msg})[/]"
        table.add_row(str(r["id"]), label, fmt_title(r))
    console.print(table)


def cmd_status(settings, db, args):
    total = db.count_total()
    if total == 0:
        console.print("[yellow]Queue is empty.[/]")
        return
    labels = ("downloaded", "processed", "caption_ready", "posted", "failed")
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Status", style="dim", width=18)
    table.add_column("Count", justify="right")
    for s in labels:
        c = db.count_by_status(s)
        table.add_row(status_badge(s), str(c))
    table.add_row("", "")
    table.add_row("[bold]Total[/]", f"[bold]{total}[/]")
    console.print(table)


def cmd_download(settings, db, args):
    from tracker.reel_url_store import count_unused
    remaining = count_unused()
    if remaining == 0:
        console.print("[yellow]No URLs left in reels.txt.[/]")
        return
    downloader = IGDownloader(settings, db)
    shortcode = run_with_spinner("Downloading", downloader.download_next_reel)
    if shortcode:
        console.print(f"  [green]Downloaded[/] {shortcode}")
    else:
        console.print("  [red]Download failed or skipped[/]")


def cmd_process(settings, db, args):
    processor = VideoProcessor(settings)
    count = 0
    reel = db.get_next_by_status("downloaded")
    if not reel:
        console.print("[yellow]No videos to process.[/]")
        return
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as p:
        task = p.add_task("[yellow]Processing...", total=None)
        while reel:
            raw_path = reel["raw_path"]
            if not raw_path or not Path(raw_path).exists():
                db.update_status(reel["id"], "failed", error_msg="File not found")
                reel = db.get_next_by_status("downloaded")
                continue
            output = settings.videos_processed_dir / f"{reel['ig_shortcode']}.mp4"
            ok = processor.process_video(raw_path, output)
            if ok:
                db.update_status(reel["id"], "processed", processed_path=str(output))
                count += 1
            else:
                db.update_status(reel["id"], "failed", error_msg="Processing failed")
            reel = db.get_next_by_status("downloaded")
    console.print(f"  [green]Processed[/] {count} video(s)")


def cmd_caption(settings, db, args):
    generator = CaptionGenerator(settings)
    count = 0
    reel = db.get_next_by_status("processed")
    if not reel:
        console.print("[yellow]No videos ready for captioning.[/]")
        return
    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as p:
        task = p.add_task("[blue]Channel 1 captions...", total=None)
        while reel:
            ig_caption = reel.get("ig_caption") or ""

            p.update(task, description="[blue]Channel 1...")
            meta = generator.generate(ig_caption)
            if not meta:
                meta = generator.fallback_metadata()

            p.update(task, description="[green]Channel 2...")
            meta2 = generator.generate(ig_caption)
            if not meta2:
                meta2 = generator.fallback_metadata()

            db.update_status(
                reel["id"],
                "caption_ready",
                yt_title=meta["title"],
                yt_description=meta["description"],
                yt_tags=",".join(meta["hashtags"]),
                yt_title_ch2=meta2["title"],
                yt_description_ch2=meta2["description"],
                yt_tags_ch2=",".join(meta2["hashtags"]),
            )
            count += 1
            reel = db.get_next_by_status("processed")
    console.print(f"  [green]Captioned[/] {count} video(s) (ch1 + ch2)")


def cmd_recent(settings, db, args):
    n = int(args[0]) if args and args[0].isdigit() else 10
    rows = db.get_recent(n)
    if not rows:
        console.print("[yellow]Queue is empty.[/]")
        return
    table = Table(header_style="bold cyan", box=box.SIMPLE, padding=(0, 2))
    table.add_column("ID", style="dim", width=4, justify="right")
    table.add_column("Status", width=16)
    table.add_column("Shortcode", width=14)
    table.add_column("Title")
    for r in rows:
        c = STATUS_COLORS.get(r["status"], "white")
        table.add_row(
            str(r["id"]),
            status_badge(r["status"]),
            r["ig_shortcode"] or "",
            fmt_title(r),
        )
    console.print(table)


def cmd_run(settings, db, args):
    console.rule("[bold cyan]Full Pipeline[/]")
    cmd_download(settings, db, [])
    cmd_process(settings, db, [])
    cmd_caption(settings, db, [])
    # Upload to both channels then mark posted
    reel_id, vid1, vid2 = _upload_both(settings, db)
    if vid1 or vid2:
        kwargs = {}
        if vid1:
            kwargs["yt_video_id"] = vid1
        if vid2:
            kwargs["yt_video_id_ch2"] = vid2
        db.update_status(reel_id, "posted", **kwargs)
        _cleanup_videos(db, reel_id)
    console.rule("[bold cyan]Done[/]")


def _upload_both(settings, db):
    """Upload the next reel to both channels. Returns (reel_id, vid1, vid2)."""
    reel = db.get_next_by_status("caption_ready")
    if not reel:
        console.print("[yellow]No videos ready for upload.[/]")
        return None, None, None
    processed_path = reel.get("processed_path")
    if not processed_path or not Path(processed_path).exists():
        console.print(f"  [red]File missing:[/] {processed_path}")
        return reel["id"], None, None

    vid1 = _do_upload(settings, reel, channel=1)
    vid2 = _do_upload(settings, reel, channel=2)
    return reel["id"], vid1, vid2


def _do_upload(settings, reel, channel: int):
    """Upload a reel to one channel. Returns video_id or None."""
    uploader = YTUploader(settings, channel=channel)
    if channel == 2:
        title = reel["yt_title_ch2"] or reel["yt_title"]
        desc = reel["yt_description_ch2"] or reel["yt_description"]
        tags = (reel["yt_tags_ch2"] or reel["yt_tags"] or "").split(",")
    else:
        title = reel["yt_title"]
        desc = reel["yt_description"]
        tags = (reel["yt_tags"] or "").split(",")
    try:
        from time import time
        file_size = Path(reel["processed_path"]).stat().st_size
        start_t = time()
        last_t = [start_t]
        last_b = [0]

        def _progress(sent, total):
            now = time()
            elapsed = now - last_t[0]
            if elapsed >= 0.8:
                speed = (sent - last_b[0]) / elapsed / 1024 / 1024
                pct = sent / total * 100 if total else 0
                bar_w = 30
                filled = int(bar_w * sent / total) if total else 0
                bar = "=" * filled + " " * (bar_w - filled)
                console.print(
                    f"  Uploading ch{channel}: [{bar}] {pct:5.1f}%  {speed:.2f} MB/s",
                    end="\r",
                )
                last_t[0] = now
                last_b[0] = sent

        video_id = uploader.upload_shorts(
            reel["processed_path"],
            title=title,
            description=desc,
            tags=tags,
            progress_callback=_progress,
        )
        console.print()
    except PipelineError as e:
        console.print(f"  [red]Upload to ch{channel} failed:[/] {e}")
        return None
    if video_id:
        console.print(f"  [green]Uploaded (ch{channel})[/] https://youtu.be/{video_id}")
        return video_id
    console.print(f"  [red]ch{channel} upload returned no video ID[/]")
    return None


def _cleanup_videos(db, reel_id: int) -> None:
    row = db._fetchone("SELECT raw_path, processed_path FROM queue WHERE id = ?;", (reel_id,))
    if not row:
        return
    for key in ("raw_path", "processed_path"):
        path = row[key]
        if path and Path(path).exists():
            Path(path).unlink()
            logger.info("Deleted %s: %s", key, path)


def cmd_upload(settings, db, args):
    channel = 2 if args and args[0] == "2" else None
    if args and args[0] == "all":
        reel_id, vid1, vid2 = _upload_both(settings, db)
        if vid1 or vid2:
            kwargs = {}
            if vid1:
                kwargs["yt_video_id"] = vid1
            if vid2:
                kwargs["yt_video_id_ch2"] = vid2
            db.update_status(reel_id, "posted", **kwargs)
        _cleanup_videos(db, reel_id)
    elif channel:
        reel = db.get_next_by_status("caption_ready")
        if not reel:
            console.print("[yellow]No videos ready for upload.[/]")
            return
        vid = _do_upload(settings, reel, channel)
        if vid:
            db.update_status(reel["id"], "posted", yt_video_id=vid)
            _cleanup_videos(db, reel["id"])
    else:
        _upload_both(settings, db)


def cmd_analytics(settings, db, args):
    total = db.count_total()
    posted = db.count_by_status("posted")
    failed = db.count_by_status("failed")
    pending = db.count_by_status("downloaded") + db.count_by_status("processed") + db.count_by_status("caption_ready")
    success_rate = (posted / total * 100) if total > 0 else 0

    rows = db._fetchall("SELECT id, ig_shortcode, yt_title, yt_video_id, status FROM queue ORDER BY id DESC")
    missing_titles = sum(1 for r in rows if not r["yt_title"])

    from tracker.reel_url_store import count_unused
    urls_left = count_unused()

    console.rule("[bold cyan]Analytics[/]")
    table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Metric", style="dim", width=22)
    table.add_column("Value")
    table.add_row("Total processed", str(total))
    table.add_row("Posted", f"[green]{posted}[/]")
    table.add_row("Failed", f"[red]{failed}[/]")
    table.add_row("Pending in queue", str(pending))
    table.add_row("Success rate", f"[green]{success_rate:.0f}%[/]")
    table.add_row("URLs remaining", str(urls_left))
    table.add_row("Videos missing title", f"[yellow]{missing_titles}[/]")
    console.print(table)
    console.print()

    console.print("[bold cyan]Improvement Ideas:[/]")
    tips = []
    if missing_titles > 0:
        tips.append("[yellow]  - Caption generation returned empty titles for some videos.[/] Check IG captions were non-empty")
    if pending > 0:
        tips.append(f"[blue]  - {pending} videos stuck in pipeline.[/]  Run 'process'/'caption'/'upload' to clear them")
    if urls_left < 10:
        tips.append("[yellow]  - Running low on URLs.[/]  Add more reels to data/reels.txt")
    if total == 0:
        tips.append("[blue]  - No videos processed yet.[/]  Run 'download' to start")
    if posted >= 5:
        tips.append("[green]  - Good momentum![/]  Consider scheduling regular pipeline runs")
    tips.append("[dim]  - Vary content categories for broader reach")

    for t in tips:
        console.print(t)
    console.print()
    console.rule()



def _delete_video_files(settings):
    import shutil
    for d in [settings.videos_raw_dir, settings.videos_processed_dir]:
        if d.exists():
            count = len(list(d.iterdir()))
            shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)
            console.print(f"  [dim]Deleted {count} files from {d.name}[/]")


def cmd_clear(settings, db, args):
    total = db.count_total()
    if total == 0 and not any(p.exists() and list(p.iterdir()) for p in [settings.videos_raw_dir, settings.videos_processed_dir]):
        console.print("[yellow]Nothing to clear.[/]")
        return

    console.rule("[bold red]Clear All Data[/]")

    if total > 0:
        console.print(f"  Queue entries: [bold]{total}[/]")
    raw_count = len(list(settings.videos_raw_dir.iterdir())) if settings.videos_raw_dir.exists() else 0
    proc_count = len(list(settings.videos_processed_dir.iterdir())) if settings.videos_processed_dir.exists() else 0
    if raw_count:
        console.print(f"  Raw videos: [bold]{raw_count}[/]")
    if proc_count:
        console.print(f"  Processed videos: [bold]{proc_count}[/]")

    console.print()

    confirm = Prompt.ask(
        "Delete ALL of the above?",
        choices=["y", "n"], default="n"
    )
    if confirm != "y":
        console.print("[dim]Cancelled.[/]")
        return

    db.clear_all()
    _delete_video_files(settings)
    console.print(f"[green]Cleared database ({total} entries) + video files.[/]")

    refresh = Prompt.ask("Also reset the URL tracker? (re-use old URLs)", choices=["y", "n"], default="n")
    if refresh == "y":
        from tracker.reel_url_store import reset_all
        reset_all()
        console.print("[green]URL tracker reset. Old URLs are available again.[/]")

    console.print()


COMMANDS = {
    "list": cmd_list,
    "status": cmd_status,
    "download": cmd_download,
    "process": cmd_process,
    "caption": cmd_caption,
    "upload": cmd_upload,
    "recent": cmd_recent,
    "run": cmd_run,
    "analytics": cmd_analytics,

    "clear": cmd_clear,
}

ALIASES = {
    "ls": "list",
    "st": "status",
    "dl": "download",
    "cap": "caption",
    "up": "upload",
    "go": "run",
    "pipeline": "run",
    "all": "run",
    "auto": "run",
    "full": "run",
    "analytics": "analytics",
    "insights": "analytics",
    "report": "analytics",
    "clear": "clear",
    "reset": "clear",
    "queue": "list",
    "show": "list",
    "publish": "upload",
    "post": "upload",
    "fetch": "download",
    "get": "download",
    "convert": "process",
    "transcode": "process",
    "count": "status",
    "stats": "status",
    "last": "recent",
    "analyze": "analytics",
    "audit": "analytics",
    "help": "help",
    "?": "help",
    "exit": "exit",
    "quit": "exit",
    "q": "exit",
}


def show_help():
    commands = [
        ("list", "ls", "Show all queue entries"),
        ("status", "st", "Pipeline counts by status"),
        ("download", "dl", "Download next reel"),
        ("process", "", "Process videos (FFmpeg)"),
        ("caption", "cap", "Generate AI captions"),
        ("upload", "up", "Upload next video"),
        ("recent", "", "Show recent entries"),
        ("run", "go", "Full pipeline"),
        ("analytics", "insights", "Analytics & improvement ideas"),

        ("clear", "reset", "Delete all queue entries"),
        ("help", "?", "Show this help"),
        ("exit", "quit", "Exit"),
    ]
    table = Table(header_style="bold cyan", box=box.SIMPLE, padding=(0, 2))
    table.add_column("Command", width=14)
    table.add_column("Alias", width=8)
    table.add_column("Description")
    for name, alias, desc in commands:
        table.add_row(
            f"[bold]{name}[/]",
            f"[dim]{alias}[/]" if alias else "",
            desc,
        )
    console.print(table)


def _resolve_command(line):
    line = line.strip().lower()
    if not line:
        return None, []

    parts = line.split()
    cmd = parts[0]
    args = parts[1:]

    if cmd in ALIASES:
        cmd = ALIASES[cmd]
    if cmd == "help":
        show_help()
        return None, []

    return cmd, args


def make_welcome(settings, db):
    total = db.count_total()
    counts = {}
    statuses = ("downloaded", "processed", "caption_ready", "posted", "failed")
    for s in statuses:
        counts[s] = db.count_by_status(s)

    stats_parts = []
    for s in statuses:
        c = counts[s]
        if c > 0:
            stats_parts.append(f"{status_badge(s)}: {c}")
    stats_line = "  ".join(stats_parts) if stats_parts else "[dim]empty[/]"

    content = (
        f"[bold cyan]ytbe[/] [dim]- Instagram -> YouTube Shorts pipeline[/]\n\n"
        f"  [dim]Queue:[/] [bold]{total}[/] total  {stats_line}\n\n"
        f"  [dim]Talk naturally or type[/] [bold]help[/] [dim]for commands.  [dim]e.g. \"post to channel 2\"[/]"
    )
    console.print(Panel(content, border_style="cyan"))


def repl(settings, db):
    console.clear()
    make_welcome(settings, db)
    while True:
        try:
            line = Prompt.ask("[bold cyan]>>>[/]")
        except (EOFError, KeyboardInterrupt):
            console.print()
            break

        cmd, args = _resolve_command(line)
        if cmd is None:
            continue
        if cmd == "exit":
            break
        if cmd in COMMANDS:
            try:
                COMMANDS[cmd](settings, db, args)
            except Exception as e:
                logger.exception("Command failed: %s", e)
                console.print(f"[red]Error:[/] {e}")
            continue

        # Natural language fallback
        console.print(f"  [yellow]Unknown command:[/] {line}")


def main():
    try:
        settings = load_settings()
    except PipelineError as e:
        console.print(f"[red]CONFIG ERROR:[/] {e}")
        sys.exit(1)

    db = _ensure_db(settings)

    if len(sys.argv) > 1:
        resolved, args = _resolve_command(f"{sys.argv[1]} {' '.join(sys.argv[2:])}")
        if resolved and resolved in COMMANDS:
            COMMANDS[resolved](settings, db, args if args else sys.argv[2:])
        elif resolved is None:
            pass
        else:
            console.print(f"[red]Usage:[/] python ytbe.py [command]")
    else:
        repl(settings, db)


if __name__ == "__main__":
    main()
