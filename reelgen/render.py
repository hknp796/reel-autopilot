"""Frame drawing for 9:16 Reels. Each scene type turns (scene spec, time, beat times) into a frame.

Beats are the moments new elements appear. The voiceover decides them: beat i starts when
the scene's say[i] line starts speaking (see voice.py), so text lands with the voice.
"""
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
BG = (10, 13, 24)
GRID = (22, 27, 44)
WHITE = (245, 247, 250)
MUTED = (140, 148, 170)
LIME = (198, 255, 61)
RED = (255, 84, 84)
GOLD = (255, 196, 61)
CARD = (22, 27, 42)
CARD2 = (30, 36, 56)

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_fonts = {}


def font(weight, size):
    key = (weight, int(size))
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(str(FONT_DIR / f"InterDisplay-{weight}.otf"), int(size))
    return _fonts[key]


def fit(text, weight, size, max_w):
    """Largest font <= size whose rendered text fits max_w."""
    while size > 20 and font(weight, size).getlength(text) > max_w:
        size -= 2
    return font(weight, size)


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_back(x):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def lerp(a, b, x):
    return a + (b - a) * x


# ---------- primitives ----------
_bg = None


def background():
    global _bg
    if _bg is None:
        im = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(im)
        for x in range(0, W, 90):
            d.line([(x, 0), (x, H)], fill=GRID, width=1)
        for y in range(0, H, 90):
            d.line([(0, y), (W, y)], fill=GRID, width=1)
        glow = Image.new("RGB", (W, H), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse([600, -300, 1400, 500], fill=(40, 60, 10))
        gd.ellipse([-400, 1400, 400, 2200], fill=(15, 25, 50))
        glow = glow.filter(ImageFilter.GaussianBlur(160))
        arr = np.asarray(im, dtype="int16") + np.asarray(glow, dtype="int16")
        _bg = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
    return _bg.copy()


def text_layer(txt, f, color):
    bb = f.getbbox(txt)
    w, h = bb[2] - bb[0] + 4, bb[3] - bb[1] + 4
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((-bb[0] + 2, -bb[1] + 2), txt, font=f, fill=color + (255,))
    return lay


def _fade(lay, alpha):
    if alpha >= 1:
        return lay
    lay = lay.copy()
    lay.putalpha(lay.getchannel("A").point(lambda v: int(v * alpha)))
    return lay


def paste(im, lay, x, y, alpha=1.0, scale=1.0):
    if alpha <= 0.001:
        return
    if scale != 1.0:
        lay = lay.resize((max(1, int(lay.width * scale)), max(1, int(lay.height * scale))), Image.LANCZOS)
    lay = _fade(lay, alpha)
    im.paste(lay, (int(x - lay.width / 2), int(y - lay.height / 2)), lay)


def anim_text(im, txt, f, color, cx, cy, t, start, dur=0.45, rise=60, pop=False):
    p = prog(t, start, dur)
    if p <= 0:
        return
    lay = text_layer(txt, f, color)
    if pop:
        paste(im, lay, cx, cy, alpha=clamp(p * 2), scale=lerp(0.6, 1.0, ease_back(p)))
    else:
        paste(im, lay, cx, cy + (1 - ease_out(p)) * rise, alpha=clamp(p * 1.6))


def overlay(im, fn, alpha):
    """Draw with fn(draw, layer) on a transparent layer, composite at alpha."""
    if alpha <= 0.001:
        return
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fn(ImageDraw.Draw(lay), lay)
    lay = _fade(lay, alpha)
    im.paste(lay, (0, 0), lay)


def badge(d, cx, cy, s, col, ok=True):
    d.ellipse([cx - s, cy - s, cx + s, cy + s], fill=col)
    k = s * 0.45
    if ok:
        d.line([(cx - k, cy + 0.05 * s), (cx - 0.12 * s, cy + k * 0.8), (cx + k * 1.05, cy - k * 0.8)],
               fill=BG, width=int(s * 0.28), joint="curve")
    else:
        d.line([(cx - k, cy - k), (cx + k, cy + k)], fill=BG, width=int(s * 0.26))
        d.line([(cx - k, cy + k), (cx + k, cy - k)], fill=BG, width=int(s * 0.26))


def search_bar(d, y, typed, cursor_on):
    d.rounded_rectangle([90, y, 990, y + 130], 65, fill=(255, 255, 255))
    cx, cy = 165, y + 65
    d.ellipse([cx - 22, cy - 22, cx + 14, cy + 14], outline=(110, 115, 130), width=7)
    d.line([(cx + 10, cy + 10), (cx + 30, cy + 30)], fill=(110, 115, 130), width=8)
    f = font("Medium", 50)
    d.text((225, cy), typed, font=f, fill=(30, 33, 45), anchor="lm")
    if cursor_on:
        tw = d.textlength(typed, font=f)
        d.rectangle([230 + tw, cy - 30, 235 + tw, cy + 30], fill=(30, 33, 45))


def result_card(d, y, name, sub, stars, highlight=False, dim=False, rank=None):
    fill = (34, 44, 20) if highlight else CARD
    d.rounded_rectangle([90, y, 990, y + 190], 32, fill=fill,
                        outline=LIME if highlight else CARD2, width=5 if highlight else 3)
    tc = (90, 96, 115) if dim else WHITE
    sc = (70, 76, 95) if dim else MUTED
    x0 = 140
    if rank is not None:
        d.rounded_rectangle([130, y + 50, 220, y + 140], 24, fill=LIME if highlight else CARD2)
        d.text((175, y + 95), f"#{rank}", font=fit(f"#{rank}", "Black", 42, 80),
               fill=BG if highlight else MUTED, anchor="mm")
        x0 = 255
    right = 950 - (110 if stars else 0)
    d.text((x0, y + 68), name, font=fit(name, "Bold", 50, right - x0), fill=tc, anchor="lm")
    d.text((x0, y + 130), sub, font=fit(sub, "Medium", 36, 950 - x0), fill=sc, anchor="lm")
    if stars:
        d.text((950, y + 68), stars, font=font("Bold", 40), fill=(90, 80, 50) if dim else GOLD, anchor="rm")


# ---------- scene types ----------
# Each entry: earliest time (s) each beat may start, given the beat index.
def min_beats(scene):
    k = scene["type"]
    if k == "statement":
        return [0.15, 1.5]
    if k == "search":
        return [0.2, 2.9]
    if k == "list":
        return [0.05] + [0.55] * len(scene["items"])
    if k == "rank_up":
        return [0.35, 1.3, 1.6]
    if k == "cta":
        return [0.05, 0.6]
    raise ValueError(f"unknown scene type {k}")


def _stack(n, gap, center):
    top = center - gap * (n - 1) / 2
    return [top + i * gap for i in range(n)]


def statement(s, t, b):
    im = background()
    lines, accent = s.get("lines", []), s.get("accent", [])
    big = min(fit(l, "Black", 112, 920).size for l in lines) if lines else 112
    acc = min(fit(l, "Black", 96, 920).size for l in accent) if accent else 96
    eyebrow = s.get("eyebrow")
    block = (70 if eyebrow else 0) + len(lines) * (big * 1.16) + (110 + len(accent) * acc * 1.2 if accent else 0)
    y = 860 - block / 2
    if eyebrow:
        anim_text(im, eyebrow, fit(eyebrow, "Bold", 40, 900), LIME, W / 2, y + 20, t, b[0] - 0.1)
        y += 70
    for i, l in enumerate(lines):
        anim_text(im, l, font("Black", big), WHITE, W / 2, y + big * 0.58, t, b[0] + 0.05 + i * 0.2)
        y += big * 1.16
    y += 110 - acc * 0.6
    for i, l in enumerate(accent):
        anim_text(im, l, font("Black", acc), LIME, W / 2, y + acc * 0.6, t, b[1] - 0.15 + i * 0.15, pop=True)
        y += acc * 1.2
    return im


def search(s, t, b):
    im = background()
    q = s["query"]
    type_dur = 1.0
    n = int(prog(t, b[0], type_dur) * len(q))
    overlay(im, lambda d, lay: search_bar(d, 360, q[:n], int(t * 3) % 2 == 0 or n < len(q)),
            ease_out(prog(t, b[0] - 0.2, 0.3)))
    t_res = b[0] + type_dur + 0.15
    for i, (name, sub, stars) in enumerate(s["results"][:3]):
        p = ease_out(prog(t, t_res + i * 0.18, 0.4))
        if p > 0:
            y = 560 + i * 220 + (1 - p) * 80
            overlay(im, lambda d, lay, y=y, a=name, c=sub, st=stars, i=i: result_card(d, y, a, c, st, rank=i + 1), p)
    you = s.get("you")
    if you:
        p = ease_out(prog(t, t_res + 0.85, 0.45))
        if p > 0:
            y = 1260 + (1 - p) * 80
            overlay(im, lambda d, lay: result_card(d, y, you["name"], you["sub"], "", dim=True, rank=you["rank"]), p)
    if s.get("punch"):
        anim_text(im, s["punch"], fit(s["punch"], "ExtraBold", 62, 900), RED, W / 2, 1560, t, b[1] - 0.1)
    return im


def list_scene(s, t, b):
    im = background()
    title, accent, items = s.get("title", []), s.get("accent", []), s["items"]
    good = s.get("kind", "good") == "good"
    tsz = min(fit(l, "Black", 104, 920).size for l in title + accent)
    row_gap = 165 if good else 200
    block = (len(title) + len(accent)) * tsz * 1.16 + 90 + len(items) * row_gap
    y = 930 - block / 2
    for i, l in enumerate(title):
        anim_text(im, l, font("Black", tsz), WHITE, W / 2, y + tsz * 0.58, t, b[0] + i * 0.15)
        y += tsz * 1.16
    for i, l in enumerate(accent):
        anim_text(im, l, font("Black", tsz), LIME, W / 2, y + tsz * 0.58, t, b[0] + (len(title) + i) * 0.15)
        y += tsz * 1.16
    y += 90 + row_gap / 2
    half = 65 if good else 80
    for i, item in enumerate(items):
        p = prog(t, b[i + 1] - 0.1, 0.4)
        if p <= 0:
            y += row_gap
            continue
        e = ease_out(p)
        x_off = 0 if good else (1 - e) * -120

        def draw(d, lay, y=y, item=item, e=e, p=p, x_off=x_off):
            d.rounded_rectangle([90 + x_off, y - half, 990 + x_off, y + half], 34, fill=CARD, outline=CARD2, width=3)
            if good:
                r = 36 * ease_back(clamp(p * 1.2))
                if r > 1:
                    badge(d, 165, y, r, LIME, ok=True)
                d.text((235 + (1 - e) * 40, y), item, font=fit(item, "Bold", 48, 720), fill=WHITE, anchor="lm")
            else:
                badge(d, 180 + x_off, y, 44, RED, ok=False)
                d.text((260 + x_off, y), item, font=fit(item, "Bold", 58, 700), fill=WHITE, anchor="lm")

        overlay(im, draw, e)
        y += row_gap
    return im


def rank_up(s, t, b):
    im = background()
    overlay(im, lambda d, lay: search_bar(d, 360, s["query"], False), 1.0)
    p = ease_out(prog(t, b[0], 1.0))
    you = s["you"]

    def draw(d, lay):
        for i, (name, sub, stars) in enumerate(s["results"][:3]):
            y = lerp(560 + i * 200, 560 + (i + 1) * 200, p)
            result_card(d, y, name, sub, stars, rank=i + 1 + (1 if p > 0.5 else 0))
        result_card(d, lerp(1160, 560, p), you["name"], you["sub"], you.get("stars", ""),
                    highlight=p > 0.3, rank=1 if p > 0.5 else you.get("from_rank", 27))

    overlay(im, draw, 1.0)
    lines, accent = s.get("lines", []), s.get("accent", [])
    y = 1450
    for l in lines:
        anim_text(im, l, fit(l, "Black", 104, 920), WHITE, W / 2, y, t, b[1] - 0.1)
        y += 120
    for l in accent:
        anim_text(im, l, fit(l, "Black", 104, 920), LIME, W / 2, y, t, b[2] - 0.1)
        y += 120
    return im


def cta(s, t, b):
    im = background()
    lines = s["lines"]
    sz = min(fit(l, "Black", 116, 940).size for l in lines)
    ys = _stack(len(lines), sz * 1.17, 690)
    for i, (l, y) in enumerate(zip(lines, ys)):
        anim_text(im, l, font("Black", sz), WHITE, W / 2, y, t, b[0] + i * 0.15)
    b0 = b[1] - 0.3
    p = prog(t, b0, 0.5)
    if p > 0:
        pulse = 1 + 0.035 * math.sin((t - b0 - 0.5) * 2 * math.pi * 1.2) if t > b0 + 0.5 else 1
        sc = ease_back(p) * pulse
        label = s["button"]
        f = fit(label, "Black", 66, 640)
        bw, bh = (f.getlength(label) + 120) * sc, 170 * sc
        cy = ys[-1] + 280

        def draw(d, lay):
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(glow).rounded_rectangle(
                [W / 2 - bw / 2 - 10, cy - bh / 2 - 10, W / 2 + bw / 2 + 10, cy + bh / 2 + 10], bh / 2, fill=LIME + (90,))
            lay.alpha_composite(glow.filter(ImageFilter.GaussianBlur(30)))
            d2 = ImageDraw.Draw(lay)
            d2.rounded_rectangle([W / 2 - bw / 2, cy - bh / 2, W / 2 + bw / 2, cy + bh / 2], bh / 2, fill=LIME)
            d2.text((W / 2, cy), label, font=font("Black", f.size * sc), fill=BG, anchor="mm")

        overlay(im, draw, clamp(p * 2))
        if s.get("sub"):
            anim_text(im, s["sub"], fit(s["sub"], "SemiBold", 46, 900), MUTED, W / 2, cy + 210, t, b[1] + 0.4)
    return im


SCENES = {"statement": statement, "search": search, "list": list_scene, "rank_up": rank_up, "cta": cta}


def frame(scene, t, beats):
    return SCENES[scene["type"]](scene, t, beats)
