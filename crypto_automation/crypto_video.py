#!/usr/bin/env python3
"""
Crypto Video Compositor
Builds high-retention 1080x1920 vertical shorts with live financial ticker,
animated candlestick charts, audio voiceover, and burned-in high-contrast subtitles.
"""

import os
import sys
import subprocess
import random
from PIL import Image, ImageDraw, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def srt_to_ass(srt_path: str, ass_path: str):
    """Convert SRT to ASS with high-impact mobile subtitle styling."""
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CryptoDefault,DejaVu Sans,52,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,4,2,2,60,60,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read().strip().split("\n\n")

    for block in content:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            times = lines[1].split(" --> ")
            start = times[0].replace(",", ".")
            end = times[1].replace(",", ".")
            # Format times to h:mm:ss.cs
            start_fmt = start[1:-1] if start.startswith("0") else start
            end_fmt = end[1:-1] if end.startswith("0") else end
            text = " ".join(lines[2:]).strip()
            # Wrap text to 28 chars max per line for mobile vertical readability
            words = text.split()
            wrapped_lines = []
            cur_line = []
            for w in words:
                cur_line.append(w)
                if len(" ".join(cur_line)) > 26:
                    wrapped_lines.append(" ".join(cur_line))
                    cur_line = []
            if cur_line:
                wrapped_lines.append(" ".join(cur_line))
            final_text = "\\N".join(wrapped_lines)
            events.append(f"Dialogue: 0,{start_fmt},{end_fmt},CryptoDefault,,0,0,0,,{final_text}")

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(events))

def render_chart_frames(output_dir: str, btc_price: str, btc_change: float, num_frames: int = 60):
    """Render 60 frames (2 seconds at 30fps) of animated dark financial chart."""
    os.makedirs(output_dir, exist_ok=True)
    width, height = 1080, 1920
    font_large = ImageFont.truetype(FONT_BOLD, 68)
    font_mid = ImageFont.truetype(FONT_BOLD, 46)
    font_small = ImageFont.truetype(FONT_REGULAR, 32)
    font_micro = ImageFont.truetype(FONT_BOLD, 28)

    # Base candlestick data
    candles = [
        (64200, 64600, 64100, 64550),
        (64550, 64700, 64400, 64620),
        (64620, 64950, 64500, 64880),
        (64880, 65100, 64750, 64790),
        (64790, 65050, 64600, 64980),
        (64980, 65300, 64900, 65240),
        (65240, 65400, 65100, 65150),
        (65150, 65250, 64700, 64800)
    ]

    for f_idx in range(num_frames):
        img = Image.new("RGB", (width, height), color=(10, 14, 23))
        draw = ImageDraw.Draw(img)

        # 1. Subtle glowing dark grid
        for y in range(200, 1800, 120):
            draw.line([(0, y), (width, y)], fill=(18, 25, 40), width=1)
        for x in range(0, width, 120):
            draw.line([(x, 200), (x, 1800)], fill=(18, 25, 40), width=1)

        # 2. Top Header Pill
        draw.rounded_rectangle([(180, 80), (900, 170)], radius=25, fill=(18, 28, 48), outline=(0, 230, 118), width=2)
        draw.text((230, 102), "⚡ CRYPTO MARKET INTELLIGENCE", font=font_micro, fill=(0, 230, 118))

        # 3. Live Ticker Card
        draw.rounded_rectangle([(80, 200), (1000, 390)], radius=30, fill=(16, 23, 38), outline=(32, 48, 76), width=2)
        draw.text((120, 225), "BITCOIN / USD", font=font_mid, fill=(240, 246, 252))
        draw.text((120, 290), f"${btc_price}", font=font_large, fill=(255, 255, 255))
        
        # Change badge
        is_pos = btc_change >= 0
        badge_color = (0, 230, 118) if is_pos else (255, 59, 48)
        badge_text = f"{'+' if is_pos else ''}{btc_change}%"
        draw.rounded_rectangle([(720, 285), (960, 355)], radius=18, fill=badge_color)
        draw.text((750, 298), badge_text, font=font_mid, fill=(0, 0, 0) if is_pos else (255, 255, 255))

        # 4. Animated Candlestick Chart in Middle (y: 440 to 1150)
        chart_top = 450
        chart_bot = 1150
        min_p = 64000
        max_p = 65600
        candle_w = 45
        spacing = 90
        start_x = 160

        for i, (open_p, high_p, low_p, close_p) in enumerate(candles):
            cx = start_x + (i * spacing)
            # Add small oscillation for active feel
            osc = int(10 * (1 if (f_idx + i) % 20 < 10 else -1)) if i == len(candles)-1 else 0
            
            y_open = int(chart_bot - ((open_p - min_p) / (max_p - min_p)) * (chart_bot - chart_top))
            y_close = int(chart_bot - ((close_p + osc - min_p) / (max_p - min_p)) * (chart_bot - chart_top))
            y_high = int(chart_bot - ((high_p + max(0, osc) - min_p) / (max_p - min_p)) * (chart_bot - chart_top))
            y_low = int(chart_bot - ((low_p + min(0, osc) - min_p) / (max_p - min_p)) * (chart_bot - chart_top))

            c_color = (0, 230, 118) if close_p >= open_p else (255, 59, 48)
            # Wick
            draw.line([(cx, y_high), (cx, y_low)], fill=c_color, width=3)
            # Body
            top_b, bot_b = min(y_open, y_close), max(y_open, y_close)
            if top_b == bot_b:
                bot_b += 2
            draw.rectangle([(cx - candle_w // 2, top_b), (cx + candle_w // 2, bot_b)], fill=c_color)

        # 5. Technical Level Indicators
        draw.line([(80, 680), (1000, 680)], fill=(255, 179, 0), width=2)
        draw.text((100, 645), "RESISTANCE: $65,200", font=font_micro, fill=(255, 179, 0))

        draw.line([(80, 1020), (1000, 1020)], fill=(0, 230, 118), width=2)
        draw.text((100, 985), "SUPPORT: $64,200", font=font_micro, fill=(0, 230, 118))

        # 6. Bottom Banner (y: 1720 - 1840)
        draw.rounded_rectangle([(60, 1740), (1020, 1850)], radius=20, fill=(16, 23, 38), outline=(0, 230, 118), width=2)
        draw.text((130, 1775), "🚨 FOLLOW FOR DAILY CRYPTO SIGNALS", font=font_mid, fill=(0, 230, 118))

        frame_path = os.path.join(output_dir, f"frame_{f_idx:03d}.png")
        img.save(frame_path)

def create_crypto_video(audio_path: str, srt_path: str, btc_price: str, btc_change: float, output_mp4: str):
    """Assemble complete high-production vertical short."""
    work_dir = "/tmp/crypto_render"
    os.makedirs(work_dir, exist_ok=True)
    frames_dir = os.path.join(work_dir, "frames")
    
    # 1. Render animated chart frames
    render_chart_frames(frames_dir, btc_price, btc_change, num_frames=60)
    
    # 2. Render 2-second base loop mp4
    loop_mp4 = os.path.join(work_dir, "base_loop.mp4")
    cmd_loop = [
        "ffmpeg", "-y", "-framerate", "30",
        "-i", os.path.join(frames_dir, "frame_%03d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        loop_mp4
    ]
    subprocess.run(cmd_loop, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 3. Convert SRT to styled ASS subtitles
    ass_path = os.path.join(work_dir, "styled.ass")
    srt_to_ass(srt_path, ass_path)
    
    # 4. Final render: loop video + mux audio + burn subtitles
    cmd_final = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", loop_mp4,
        "-i", audio_path,
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_mp4
    ]
    subprocess.run(cmd_final, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_mp4

if __name__ == "__main__":
    from crypto_script import generate_script
    from crypto_tts import build_tts
    
    print("[1/3] Generating script...")
    data = generate_script()
    print("Title:", data["title"])
    
    audio_file = "/tmp/crypto_voice.mp3"
    srt_file = "/tmp/crypto_voice.srt"
    print("[2/3] Generating voiceover & subtitles with edge-tts...")
    build_tts(data["script_text"], audio_file, srt_file)
    
    out_video = "/home/samirkhadka/crypto_automation/output/sample_crypto_short.mp4"
    print("[3/3] Rendering vertical video with FFmpeg...")
    create_crypto_video(audio_file, srt_file, data["btc_price"], data["btc_change"], out_video)
    print("✅ RENDER COMPLETE:", out_video)
    print(f"File size: {os.path.getsize(out_video) / (1024*1024):.2f} MB")
