#!/usr/bin/env python3
"""
High-CTR Thumbnail Generator for Rumble Video Automation
Creates high-contrast, attention-grabbing 1280x720 thumbnails.
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from typing import Optional, List

FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def make_thumbnail(
    bg_image_path: Optional[str],
    badge_text: str,
    headline_lines: List[str],
    output_path: str,
    highlight_color: str = "#FFE600"  # Vibrant Yellow
) -> str:
    width, height = 1280, 720

    if bg_image_path and os.path.exists(bg_image_path):
        bg = Image.open(bg_image_path).convert("RGBA")
        bg = bg.resize((width, height), Image.Resampling.LANCZOS)
        # Apply slight contrast and darkness so text pops
        enhancer = ImageEnhance.Brightness(bg)
        bg = enhancer.enhance(0.55)
    else:
        bg = Image.new("RGBA", (width, height), (12, 16, 24, 255))

    draw = ImageDraw.Draw(bg)

    # Dark gradient vignette on left / bottom
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    for x in range(0, 850):
        alpha = int(220 * (1 - (x / 850) ** 1.5))
        ov_draw.line([(x, 0), (x, height)], fill=(0, 0, 0, alpha))
    bg = Image.alpha_composite(bg, overlay)
    draw = ImageDraw.Draw(bg)

    # 1. Badge Pill (Top Left)
    font_badge = ImageFont.truetype(FONT_BOLD, 30)
    badge_pad_x, badge_pad_y = 24, 12
    bx, by = 60, 60
    bbox = font_badge.getbbox(badge_text.upper())
    bw = (bbox[2] - bbox[0]) + badge_pad_x * 2
    bh = (bbox[3] - bbox[1]) + badge_pad_y * 2

    # Draw badge glow & background
    draw.rounded_rectangle([(bx - 3, by - 3), (bx + bw + 3, by + bh + 3)], radius=12, fill="#FF2244")
    draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=10, fill="#CC0022")
    draw.text((bx + badge_pad_x, by + badge_pad_y - 2), badge_text.upper(), font=font_badge, fill="#FFFFFF")

    # 2. Main Headline (Multi-line)
    font_main = ImageFont.truetype(FONT_BOLD, 74)
    font_sub = ImageFont.truetype(FONT_BOLD, 62)

    cur_y = by + bh + 40
    for i, line in enumerate(headline_lines):
        line = line.strip()
        if not line:
            continue
        font = font_main if i == 0 else font_sub
        color = highlight_color if i == 0 else "#FFFFFF"

        # Background pill behind text for maximum readability
        lbox = font.getbbox(line)
        lw = lbox[2] - lbox[0]
        lh = lbox[3] - lbox[1]

        px, py = 18, 10
        pill_rect = [(bx - px, cur_y - py), (bx + lw + px, cur_y + lh + py)]
        draw.rounded_rectangle(pill_rect, radius=8, fill=(0, 0, 0, 210))
        draw.rounded_rectangle(pill_rect, radius=8, outline=(60, 70, 90, 255), width=2)

        # Drop shadow
        draw.text((bx + 4, cur_y + 4), line, font=font, fill=(0, 0, 0, 240))
        # Text
        draw.text((bx, cur_y), line, font=font, fill=color)
        cur_y += lh + py * 2 + 18

    # 3. Outer border accent
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline="#FFE600", width=4)

    final_img = bg.convert("RGB")
    final_img.save(output_path, "JPEG", quality=95)
    print(f"🖼️ Generated high-CTR thumbnail: {output_path}")
    return output_path

if __name__ == "__main__":
    out = "/home/samirkhadka/crypto_automation/output/test_thumb.jpg"
    make_thumbnail(
        bg_image_path=None,
        badge_text="CONGRESSIONAL CLASH",
        headline_lines=["IS GOLD MONEY?", "RON PAUL CONFRONTS", "THE FEDERAL RESERVE"],
        output_path=out
    )
