#!/usr/bin/env python3
"""
High-CTR Professional Thumbnail Generator for Rumble Video Automation
Designed for maximum CTR without overlapping faces or awkward line breaks.
"""

import os
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
from typing import Optional, List

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

def make_thumbnail(
    bg_image_path: Optional[str],
    badge_text: str,
    headline_lines: List[str],
    output_path: str,
    highlight_color: str = "#FFE600"  # Vibrant Yellow
) -> str:
    width, height = 1280, 720

    # 1. Base dark cinematic background
    canvas = Image.new("RGB", (width, height), (10, 13, 20))
    draw = ImageDraw.Draw(canvas)

    # Vertical gradient for depth
    for y in range(height):
        r = int(10 + (y / height) * 12)
        g = int(13 + (y / height) * 15)
        b = int(22 + (y / height) * 26)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 2. Place subject / face on the RIGHT side
    if bg_image_path and os.path.exists(bg_image_path):
        face = Image.open(bg_image_path).convert("RGBA")
        aspect = face.width / face.height
        new_h = height
        new_w = int(new_h * aspect)
        face_scaled = face.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Enhance subject contrast and brightness
        enh_b = ImageEnhance.Brightness(face_scaled)
        face_scaled = enh_b.enhance(1.15)
        enh_c = ImageEnhance.Contrast(face_scaled)
        face_scaled = enh_c.enhance(1.25)

        # Position flush to the right edge
        face_x = width - new_w

        # Soft progressive alpha gradient on left edge of subject so it fades into darkness
        mask = Image.new("L", (new_w, new_h), 255)
        m_draw = ImageDraw.Draw(mask)
        fade_width = min(260, new_w // 2)
        for fx in range(fade_width):
            alpha = int((fx / fade_width) ** 1.3 * 255)
            m_draw.line([(fx, 0), (fx, new_h)], fill=alpha)

        canvas.paste(face_scaled.convert("RGB"), (face_x, 0), mask)

    # 3. Add heavy dark vignette on left side (0 to 720px) to guarantee 100% text readability
    vignette = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    v_draw = ImageDraw.Draw(vignette)
    for x in range(0, 720):
        alpha = int(245 * (1 - (x / 720) ** 1.8))
        v_draw.line([(x, 0), (x, height)], fill=(10, 13, 20, alpha))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), vignette).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # 4. Draw Red Badge Pill (Top Left)
    f_badge = ImageFont.truetype(FONT_BOLD, 26)
    bx, by = 60, 55
    b_pad_x, b_pad_y = 18, 9
    badge_label = badge_text.upper() if badge_text.startswith("🔴") or badge_text.startswith("⚡") else f"🔴 {badge_text.upper()}"
    bbox = f_badge.getbbox(badge_label)
    bw = (bbox[2] - bbox[0]) + b_pad_x * 2
    bh = (bbox[3] - bbox[1]) + b_pad_y * 2

    # Red badge with clean glow
    draw.rounded_rectangle([(bx - 2, by - 2), (bx + bw + 2, by + bh + 2)], radius=8, fill="#FF1744")
    draw.rounded_rectangle([(bx, by), (bx + bw, by + bh)], radius=8, fill="#D50000")
    draw.text((bx + b_pad_x, by + b_pad_y - 2), badge_label, font=f_badge, fill="#FFFFFF")

    # 5. Draw Headline Lines (Strictly on left, max width 550px)
    cur_y = by + bh + 35
    MAX_TEXT_WIDTH = 540

    for i, line in enumerate(headline_lines[:2]):
        line = line.strip().upper()
        if not line:
            continue
        color = highlight_color if i == 0 else "#FFFFFF"

        # Dynamically scale font size so it NEVER crosses into the face area
        font_size = 72 if i == 0 else 60
        font = ImageFont.truetype(FONT_BOLD, font_size)
        while font_size > 36:
            lbox = font.getbbox(line)
            if (lbox[2] - lbox[0]) <= MAX_TEXT_WIDTH:
                break
            font_size -= 2
            font = ImageFont.truetype(FONT_BOLD, font_size)

        lbox = font.getbbox(line)
        lw = lbox[2] - lbox[0]
        lh = lbox[3] - lbox[1]

        # Dark pill background behind text for crisp contrast
        px, py = 16, 9
        pill_rect = [(bx - px, cur_y - py), (bx + lw + px, cur_y + lh + py)]
        draw.rounded_rectangle(pill_rect, radius=8, fill=(0, 0, 0, 225))
        draw.rounded_rectangle(pill_rect, radius=8, outline=(75, 85, 105), width=2)

        # Drop shadow + text
        draw.text((bx + 3, cur_y + 3), line, font=font, fill=(0, 0, 0))
        draw.text((bx, cur_y), line, font=font, fill=color)

        cur_y += lh + py * 2 + 18

    # 6. Bottom subtitle tag
    f_sub = ImageFont.truetype(FONT_BOLD, 22)
    draw.text((bx, cur_y + 12), "▶ UNCUT CONGRESSIONAL TESTIMONY", font=f_sub, fill="#00E5FF")

    # 7. High-CTR outer gold accent border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline="#FFE600", width=6)

    canvas.save(output_path, "JPEG", quality=95)
    print(f"🖼️ Generated professional high-CTR thumbnail: {output_path}")
    return output_path

if __name__ == "__main__":
    out = "/home/samirkhadka/crypto_automation/output/test_pro_thumb.jpg"
    make_thumbnail(
        bg_image_path="/home/samirkhadka/crypto_automation/output/rp_210s.jpg",
        badge_text="HISTORIC CLASH",
        headline_lines=["IS GOLD MONEY?", "PAUL VS BERNANKE"],
        output_path=out
    )
