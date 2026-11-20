#!/usr/bin/env python3
"""5HU cover / banner generator (Facebook cover + YouTube banner).

Brand: black #0A0A0A, white type (Inter Black), lime #C8FF2E dot, pink/cyan accents, film grain.
All text stays inside each platform's safe zone so nothing is cropped on mobile/desktop/TV.

    python3 make_cover.py <out_dir> ["KICKER"] ["HEADLINE"]

Without KICKER/HEADLINE it renders the evergreen brand version. With them it renders the
"latest drop" version, which is what the pipeline can regenerate after every new video.
"""
import os, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

F = "/usr/share/fonts/opentype/inter/"
BLACK, WHITE, LIME = (10, 10, 10), (245, 245, 240), (200, 255, 46)
PINK, CYAN, GREY = (255, 62, 165), (46, 230, 255), (150, 150, 145)


def font(name, size):
    return ImageFont.truetype(F + name, size)


def text_w(draw, s, f, track=0):
    return sum(draw.textlength(c, font=f) + track for c in s) - track


def draw_tracked(draw, xy, s, f, fill, track=0):
    x, y = xy
    for c in s:
        draw.text((x, y), c, font=f, fill=fill)
        x += draw.textlength(c, font=f) + track
    return x


def fit(draw, s, name, max_w, start, track_ratio=-0.03, min_size=40):
    size = start
    while size > min_size:
        f = font(name, size)
        if text_w(draw, s, f, int(size * track_ratio)) <= max_w:
            return f, int(size * track_ratio)
        size -= 4
    return font(name, min_size), int(min_size * track_ratio)


def grain(img, amount=14, seed=5):
    random.seed(seed)
    noise = Image.effect_noise(img.size, 40).convert("L")
    noise = noise.point(lambda v: 128 + (v - 128) * amount // 40)
    return Image.blend(img, Image.merge("RGB", (noise, noise, noise)), 0.06)


def stripes(draw, W, H, seed=3):
    """Kinetic accent bars (the video's lime/pink/cyan energy), kept thin and off the text."""
    random.seed(seed)
    for col, y, h, x0, x1 in [
        (LIME, 0.12, 6, 0.00, 0.30), (PINK, 0.86, 4, 0.62, 1.00), (CYAN, 0.90, 3, 0.70, 0.94),
        (LIME, 0.08, 3, 0.72, 0.98)]:
        draw.rectangle([int(W * x0), int(H * y), int(W * x1), int(H * y) + h], fill=col)


def render(W, H, safe, kicker=None, headline=None, seed=7):
    """safe = (x0, y0, x1, y1): every glyph goes in here."""
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    stripes(d, W, H, seed)
    x0, y0, x1, y1 = safe
    sw, sh = x1 - x0, y1 - y0

    # wordmark "5HU" + lime dot, right side of the safe zone
    wm_size = int(sh * 0.56)
    wf = font("Inter-Black.otf", wm_size)
    wtrack = int(-wm_size * 0.06)
    ww = text_w(d, "5HU", wf, wtrack)
    dot_r = int(wm_size * 0.11)
    wx = x1 - ww - dot_r * 2 - int(wm_size * 0.04)
    top_off = wf.getbbox("5HU")[1]
    wy = y0 + (sh - (wf.getbbox("5HU")[3] - top_off)) // 2 - top_off
    draw_tracked(d, (wx, wy), "5HU", wf, WHITE, wtrack)
    base = wy + wf.getbbox("5HU")[3]
    cx = wx + ww + int(wm_size * 0.04) + dot_r
    d.ellipse([cx - dot_r, base - dot_r * 2, cx + dot_r, base], fill=LIME)

    # left column: kicker + headline (or the brand promise)
    col_w = int((wx - x0) * 0.92)
    if headline:
        k = (kicker or "LATEST").upper()
        lines = [headline.upper()]
    else:
        k = "NEW SHORTS · 09:00 & 19:00"
        lines = ["FASHION'S NEXT", "BIG NAMES."]
    kf = font("Inter-Bold.otf", max(22, int(sh * 0.065)))
    while text_w(d, k, kf, int(kf.size * 0.08)) + kf.size * 1.3 > col_w and kf.size > 18:
        kf = font("Inter-Bold.otf", kf.size - 2)
    # wrap the headline into max 2 lines
    if headline:
        words, lines, cur = headline.upper().split(), [], ""
        hf, ht = fit(d, headline.upper(), "Inter-Black.otf", col_w, int(sh * 0.30))
        if text_w(d, headline.upper(), hf, ht) > col_w or hf.size < sh * 0.2:
            half = len(words) // 2 or 1
            lines = [" ".join(words[:half]), " ".join(words[half:])]
        else:
            lines = [headline.upper()]
    longest = max(lines, key=lambda s: len(s))
    hf, ht = fit(d, longest, "Inter-Black.otf", col_w, int(sh * (0.30 if len(lines) == 1 else 0.22)))
    line_h = int(hf.size * 0.98)
    block_h = int(kf.size * 1.9) + line_h * len(lines) + int(sh * 0.12)
    y = y0 + (sh - block_h) // 2
    d.rectangle([x0, y + kf.size // 2 - 3, x0 + int(kf.size * 0.9), y + kf.size // 2 + 3], fill=LIME)
    draw_tracked(d, (x0 + int(kf.size * 1.3), y), k, kf, LIME, int(kf.size * 0.08))
    y += int(kf.size * 1.9)
    for ln in lines:
        draw_tracked(d, (x0 - int(hf.size * 0.04), y - hf.getbbox(ln)[1] + int(hf.size * 0.1)), ln, hf, WHITE, ht)
        y += line_h
    sub = "Before everyone else." if not headline else "We find them first."
    sf = font("Inter-Medium.otf", max(20, int(sh * 0.07)))
    d.text((x0, y + int(sh * 0.04)), sub, font=sf, fill=GREY)
    return grain(img)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    kicker = sys.argv[2] if len(sys.argv) > 2 else None
    headline = sys.argv[3] if len(sys.argv) > 3 else None
    os.makedirs(out, exist_ok=True)
    tag = "latest" if headline else "brand"
    # Facebook cover 1640x924: desktop shows the middle 1640x624, mobile the full 16:9.
    # Keep clear of the profile picture (bottom-left) -> safe zone starts right of it and above.
    fb = render(1640, 924, (190, 210, 1500, 690), kicker, headline)
    fb.save(f"{out}/5hu_facebook_cover_{tag}.png")
    # YouTube banner 2560x1440: text-and-logo safe area is the central 1546x423.
    yt = render(2560, 1440, (527, 518, 2033, 921), kicker, headline)
    yt.save(f"{out}/5hu_youtube_banner_{tag}.png")
    print("ok", out, tag)


if __name__ == "__main__":
    main()
