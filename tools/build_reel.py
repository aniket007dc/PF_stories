#!/usr/bin/env python3
"""Build a PF Guru Ji reel frame by frame, in the style of the reference reel.

    python3 tools/build_reel.py episodes/ep01-claim-reject               # the whole reel
    python3 tools/build_reel.py episodes/ep01-claim-reject --stills      # one clean still per shot
    python3 tools/build_reel.py episodes/ep01-claim-reject --frame 27.5  # one frame, to look at
    python3 tools/build_reel.py episodes/ep01-claim-reject --check       # only check reel.json

Reads the episode's episode.json (script, timing, exact card text) and reel.json (what each
shot shows and when), the paper in brand/assets/plates/ and the fonts in brand/fonts/.
Optional: photos in media/photos/, one voice file per line in media/audio/lines/ (S01.mp3 …),
and media/audio/music.mp3. Needs Pillow, numpy and ffmpeg.

Every word on screen is drawn with real fonts from reel.json, and reel.json may only contain
the shot's card text, so the text in the video is exact by construction.
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cutout  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "brand"
FONTS = BRAND / "fonts"
W, H, FPS = 1080, 1920, 30
SR = 48000


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


_BRAND = json.loads((BRAND / "brand.json").read_text(encoding="utf-8"))
_COL = _BRAND["colors"]
BRAND_NAME = _BRAND.get("brand", "")    # the header label and the end card's logo, unless reel.json gives them
CARD, STRIP, INK = hexrgb(_COL["card"]), hexrgb(_COL["caption_strip"]), hexrgb(_COL["ink"])
LEMON, RED, BLACK_CARD = hexrgb(_COL["lemon"]), hexrgb(_COL["stamp_red"]), (29, 28, 26)
GREY_WORD, GREY_MONO, MARK = (180, 174, 165), (104, 99, 92), (128, 122, 114)
GRID = (186, 196, 206)
PUSH = 0.22          # seconds the previous shot takes to leave upward
WIPE_IN, WIPE_HOLD, WIPE_OUT = 0.28, 0.05, 0.3
CAP_SIZE, CAP_LINE = 56, 66
STYLE_FILL = {"white": CARD, "yellow": LEMON, "black": BLACK_CARD, "red": RED}


# ---------------------------------------------------------------- fonts and text

FONT_FILES = {
    "anton": ("Anton-Regular.ttf", None),
    "mono": ("IBMPlexMono-SemiBold.ttf", None),
    "mono_bold": ("IBMPlexMono-Bold.ttf", None),
    "mono_med": ("IBMPlexMono-Medium.ttf", None),
    "caption": ("Archivo-Variable.ttf", [800, 100]),
    "hand": ("Caveat-Variable.ttf", [700]),
    "type": ("CourierPrime-Bold.ttf", None),
}
FALLBACKS = ["mono", "caption"]
ARROWS = {"→": 0, "↗": -45, "↘": 45, "←": 180, "↙": 135, "↖": -135, "↑": -90, "↓": 90}


@lru_cache(maxsize=None)
def font(key, size):
    file, axes = FONT_FILES[key]
    f = ImageFont.truetype(str(FONTS / file), int(size))
    if axes:
        f.set_variation_by_axes(axes)
    return f


@lru_cache(maxsize=None)
def coverage(key):
    try:
        from fontTools.ttLib import TTFont
        return frozenset(TTFont(str(FONTS / FONT_FILES[key][0])).getBestCmap())
    except Exception:  # noqa: BLE001  (no fontTools: compare with the "missing glyph" box)
        return None


NOT_A_CHAR = "\uffff"   # a Unicode noncharacter: no font maps it, so it draws the font's missing-glyph box


@lru_cache(maxsize=None)
def drawn(key, ch):
    """ch drawn with Pillow's basic layout, as (box, pixels). The basic layout takes each glyph straight
    from the font's cmap, as fontTools reads it, so a character the font lacks draws NOT_A_CHAR's box.
    Raqm's shaping would not: it builds some missing characters from others, such as Ǟ from A and accents."""
    f = ImageFont.truetype(str(FONTS / FONT_FILES[key][0]), 40, layout_engine=ImageFont.Layout.BASIC)
    box = f.getbbox(ch)
    img = Image.new("L", (max(1, box[2] - box[0]), max(1, box[3] - box[1])))
    ImageDraw.Draw(img).text((-box[0], -box[1]), ch, font=f, fill=255)
    return box, img.tobytes()


@lru_cache(maxsize=None)
def covered(key, ch):
    if ch.isspace():
        return True
    cov = coverage(key)
    if cov is not None:
        return ord(ch) in cov
    return drawn(key, ch) != drawn(key, NOT_A_CHAR)


def runs(text, key):
    """Split text into runs drawn with one font each; arrows in display fonts become drawn arrows."""
    out = []
    for ch in text:
        if ch in ARROWS and key in ("anton", "hand", "type", "caption"):
            k = "@arrow"
        elif covered(key, ch):
            k = key
        else:
            k = next((fb for fb in FALLBACKS if covered(fb, ch)), key)
        if out and out[-1][1] == k and k != "@arrow":
            out[-1][0] += ch
        else:
            out.append([ch, k])
    return out


def text_width(text, key, size, tracking=0):
    w = 0.0
    for s, k in runs(text, key):
        w += size * 0.62 if k == "@arrow" else font(k, size).getlength(s)
    return w + tracking * max(0, len(text) - 1)


def ink_box(text, key, size):
    """(top, bottom) of the ink relative to the baseline (top is negative)."""
    top, bot = 0, 0
    for s, k in runs(text, key):
        if k == "@arrow":
            top = min(top, -int(size * 0.62))
            continue
        b = font(k, size).getbbox(s, anchor="ls")
        top, bot = min(top, b[1]), max(bot, b[3])
    return top, bot


def draw_arrow(d, x, base, size, angle, fill, width=None):
    """A drawn arrow, about the height of a capital letter, starting at x on the baseline."""
    cap = size * 0.62
    cx, cy = x + cap * 0.5, base - cap * 0.5
    r = cap * 0.5
    a = math.radians(angle)
    x0, y0 = cx - r * math.cos(a), cy - r * math.sin(a)
    x1, y1 = cx + r * math.cos(a), cy + r * math.sin(a)
    w = width or max(3, int(size * 0.075))
    d.line([(x0, y0), (x1, y1)], fill=fill, width=w)
    for side in (-1, 1):
        b = a + math.pi + side * math.radians(38)
        d.line([(x1, y1), (x1 + r * 0.62 * math.cos(b), y1 + r * 0.62 * math.sin(b))], fill=fill, width=w)
    return x + cap


def draw_text(img, x, base, text, key, size, fill, tracking=0):
    d = ImageDraw.Draw(img)
    for s, k in runs(text, key):
        if k == "@arrow":
            x = draw_arrow(d, x, base, size, ARROWS[s], fill) + tracking
            continue
        f = font(k, size)
        if tracking:
            for ch in s:
                d.text((x, base), ch, font=f, fill=fill, anchor="ls")
                x += f.getlength(ch) + tracking
        else:
            d.text((x, base), s, font=f, fill=fill, anchor="ls")
            x += f.getlength(s)
    return x


# ---------------------------------------------------------------- paper, texture, shadows, torn edges

# The reference reel's paper: light warm grey, lit from the left, a little darker toward the bottom right
PAPER_TOP_LEFT = np.array([226, 220, 211], np.float32)
PAPER_FALLOFF_X, PAPER_FALLOFF_Y, CREASE = 0.11, 0.17, 0.42


class Paper:
    def __init__(self):
        plate = BRAND / "assets" / "plates" / "paper-a01.webp"
        src = Image.open(plate).convert("L").resize((W, H), Image.LANCZOS)
        g0 = np.asarray(src).astype(np.float32)
        large = np.asarray(src.filter(ImageFilter.GaussianBlur(70))).astype(np.float32)
        crease = np.clip((g0 - large) * CREASE, -26, 26)       # keep the creases, drop the plate's own lighting
        xs = np.linspace(0, 1, W, dtype=np.float32)[None, :]
        ys = np.linspace(0, 1, H, dtype=np.float32)[:, None]
        light = 1 - PAPER_FALLOFF_X * xs - PAPER_FALLOFF_Y * ys ** 1.3
        rgb = PAPER_TOP_LEFT[None, None, :] * light[..., None] + crease[..., None]
        self.rgb = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
        g = np.asarray(self.rgb.convert("L")).astype(np.float32)
        blur = np.asarray(Image.fromarray(g.astype(np.uint8)).filter(ImageFilter.GaussianBlur(18))).astype(np.float32)
        self.detail = g - blur          # crease detail, roughly -20…+20
        self.light = blur / blur.mean()  # the slow light falloff

    def texture(self, w, h, seed, strength=0.8, light=0.35):
        """A crease-and-light texture tile (float, around 0) cut from the plate."""
        rng = np.random.default_rng(seed)
        x = int(rng.integers(0, max(1, W - w))) if w < W else 0
        y = int(rng.integers(0, max(1, H - h))) if h < H else 0
        det = np.zeros((h, w), np.float32)
        lit = np.ones((h, w), np.float32)
        cw, ch = min(w, W), min(h, H)
        det[:ch, :cw] = self.detail[y:y + ch, x:x + cw]
        lit[:ch, :cw] = self.light[y:y + ch, x:x + cw]
        return det * strength, 1 + (lit - 1) * light


def textured(fill, w, h, paper, seed, strength=0.8, light=0.35):
    det, lit = paper.texture(w, h, seed, strength, light)
    base = np.empty((h, w, 3), np.float32)
    base[:] = fill
    out = base * lit[..., None] + det[..., None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def torn_profile(n, seed, amp=7.0, fine=2.2):
    rng = np.random.default_rng(seed)
    x = np.arange(n, dtype=np.float32)
    p = np.zeros(n, np.float32)
    for k, a in ((97, 1.0), (41, 0.6), (17, 0.35)):
        p += a * np.sin(x / k + rng.uniform(0, 6.28))
    p = p / 1.95 * amp
    p += np.convolve(rng.normal(0, fine, n), np.ones(3) / 3, mode="same")
    return p


def torn_mask(w, h, seed, top=True, bottom=True, left=False, right=False, depth=14, fiber=0):
    """Alpha mask with torn edges. depth = how far the tear bites in; fiber widens it (white edge)."""
    m = np.ones((h, w), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    if top:
        p = depth + torn_profile(w, seed) - fiber
        m *= (yy >= p[None, :]).astype(np.float32)
    if bottom:
        p = h - depth + torn_profile(w, seed + 1) + fiber
        m *= (yy <= p[None, :]).astype(np.float32)
    if left:
        p = depth + torn_profile(h, seed + 2) - fiber
        m *= (xx >= p[:, None]).astype(np.float32)
    if right:
        p = w - depth + torn_profile(h, seed + 3) + fiber
        m *= (xx <= p[:, None]).astype(np.float32)
    img = Image.fromarray((m * 255).astype(np.uint8))
    return img.filter(ImageFilter.GaussianBlur(0.7))


def shadowed(layer, offset=(10, 14), blur=16, opacity=0.36, pad=44):
    w, h = layer.size
    out = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("L", out.size, 0)
    sh.paste(layer.getchannel("A"), (pad + offset[0], pad + offset[1]))
    sh = sh.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * opacity))
    shadow = Image.new("RGBA", out.size, (34, 30, 26, 255))
    shadow.putalpha(sh)
    out.alpha_composite(shadow)
    out.alpha_composite(layer, (pad, pad))
    return out


def rotated(img, deg):
    if abs(deg) < 0.05:
        return img
    return img.rotate(-deg, resample=Image.BICUBIC, expand=True)


def worn(img, seed, amount=0.10):
    """Ink-stamp wear: random specks of reduced alpha."""
    a = np.asarray(img.getchannel("A")).astype(np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.random(a.shape)
    speck = Image.fromarray((noise < amount).astype(np.uint8) * 255).filter(ImageFilter.GaussianBlur(1.1))
    s = np.asarray(speck).astype(np.float32) / 255
    a = a * (1 - 0.75 * s)
    out = img.copy()
    out.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))
    return out


def grid_card(w, h, paper, seed, step=34):
    img = textured(CARD, w, h, paper, seed, 0.6, 0.25).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    for x in range(step // 2, w, step):
        d.line([(x, 0), (x, h)], fill=GRID + (110,), width=1)
    for y in range(step // 2, h, step):
        d.line([(0, y), (w, y)], fill=GRID + (110,), width=1)
    return img


def tab_image(text, size=25, fg=CARD, bg=INK, tracking=2.4):
    tw = text_width(text, "mono", size, tracking)
    top, bot = ink_box("ABC", "mono", size)
    h = int(-top + 22)
    img = Image.new("RGBA", (int(tw + 26), h), bg + (255,))
    draw_text(img, 13, h - 11, text, "mono", size, fg, tracking)
    return img


# ---------------------------------------------------------------- timing helpers

def ease_out_back(p, s=1.6):
    p = min(max(p, 0.0), 1.0) - 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def ease_out_cubic(p):
    p = min(max(p, 0.0), 1.0)
    return 1 - (1 - p) ** 3


def ease_in_cubic(p):
    p = min(max(p, 0.0), 1.0)
    return p ** 3


def ease_in_out(p):
    p = min(max(p, 0.0), 1.0)
    return 3 * p * p - 2 * p * p * p


def norm_word(w):
    return re.sub(r"[^0-9a-z₹%]", "", w.lower())


# ---------------------------------------------------------------- elements

class Element:
    """One thing on screen. Subclasses draw `art` (RGBA, unrotated, no shadow); motion is shared.

    Position: x is the horizontal centre and y the top of the element (anchor "top"),
    or x, y is its centre (anchor "center", used by stamps and notes).
    """
    entrance = "rise"
    sound = "whoosh"
    anchor = "top"

    def __init__(self, spec, ctx):
        self.spec, self.ctx = spec, ctx
        self.x = spec.get("x", 540)
        self.y = spec.get("y", 430)
        self.rot = spec.get("rot", 0)
        self.at = spec.get("at", 0.1)
        self.anim = spec.get("in", self.entrance)
        self.dur = spec.get("dur", 0.8)
        self.out = spec.get("out")
        self.seed = ctx["seed"]
        self._final = None

    # what the OCR-able text of this element is, as written in card_text
    def texts(self):
        return []

    def handwritten(self):
        """The texts drawn in handwriting, which OCR can't always read: a person checks those by eye."""
        return []

    def art(self, u):
        """The element at local time u (seconds since it started). Static by default."""
        raise NotImplementedError

    def animated_until(self):
        return 0.0

    def frame_image(self, u):
        if u >= self.animated_until():
            if self._final is None:
                self._final = self.finish(self.art(10_000))
            return self._final
        return self.finish(self.art(u))

    def finish(self, art):
        return rotated(shadowed(art) if self.spec.get("shadow", True) else art, self.rot)

    def size0(self):
        if not hasattr(self, "_size0"):
            self._size0 = self.art(10_000).size
        return self._size0

    def centre(self):
        if self.anchor == "center":
            return self.x, self.y
        if self.anchor == "left":
            w, h = self.size0()
            return self.x + w / 2, self.y + h / 2
        return self.x, self.y + self.size0()[1] / 2

    def sounds(self, t0):
        if self.anim == "none":
            return []
        if self.anim == "slam":
            return [("thud", t0 + 0.12)]
        if self.anim == "pop":
            return [("pop", t0)]
        if self.anim == "write":
            return [("scribble", t0, self.dur)]
        return [("whoosh", t0)]

    def state(self, u):
        """(dx, dy, scale, alpha, reveal) for the entrance and exit at local time u."""
        dx = dy = 0.0
        scale, alpha, reveal = 1.0, 1.0, 1.0
        a = self.anim
        if a == "drop":
            p = u / 0.45
            dy = -150 * (1 - ease_out_back(p))
            alpha = min(1.0, u / 0.08)
        elif a == "rise":
            p = u / 0.42
            dy = 300 * (1 - ease_out_back(p, 1.3))
            alpha = min(1.0, u / 0.06)
        elif a in ("slide_left", "slide_right"):
            p = u / 0.45
            dx = (-1 if a == "slide_left" else 1) * 1150 * (1 - ease_out_back(p, 1.2))
        elif a == "slam":
            p = u / 0.2
            scale = 1.0 + 0.6 * (1 - ease_out_back(p, 2.2))
            alpha = min(1.0, u / 0.05)
        elif a == "pop":
            p = u / 0.22
            scale = 0.82 + 0.18 * ease_out_back(p, 2.0)
            alpha = min(1.0, u / 0.06)
        elif a == "write":
            reveal = ease_in_out(u / self.dur)
        if self.out:
            v = u - self.out["at"]
            if v > 0:
                dy -= 2000 * ease_in_cubic(v / 0.35)
        return dx, dy, scale, alpha, reveal


class Card(Element):
    """White, yellow or black card: optional tab, prefix and big text, right label, foot line."""
    entrance = "rise"

    def texts(self):
        out = []
        if self.spec.get("tab"):
            out.append(self.spec["tab"])
        big = self.spec.get("big")
        if big:
            out.append((self.spec["prefix"] + " " + big) if self.spec.get("prefix") else big)
        if self.spec.get("label"):
            out.append(" ".join(self.spec["label"].split("\n")))
        if self.spec.get("foot"):
            out.append(self.spec["foot"])
        return out

    def art(self, u):
        s = self.spec
        style = s.get("style", "white")
        w = s.get("w", 900)
        big_size = s.get("size", 150)
        fg = CARD if style == "black" else INK
        pad = s.get("pad", 40)
        tab = s.get("tab")
        tab_img = None
        if tab:
            tab_img = tab_image(tab, s.get("tab_size", 25), fg=LEMON, bg=BLACK_CARD) if style == "black" \
                else tab_image(tab, s.get("tab_size", 25))
        big = s.get("big", "")
        top, bot = ink_box(big or "A", "anton", big_size)
        big_h = bot - top
        label_lines = s["label"].split("\n") if s.get("label") else []
        foot = s.get("foot")
        y = 30
        if tab_img:
            y += tab_img.height + 16
        big_top = y
        y += big_h
        if foot:
            y += 16 + 34
        h = max(s.get("h", 0), y + (34 if tab_img else 28))
        if not tab_img and not foot:
            big_top = (h - big_h) / 2
        img = textured(STYLE_FILL[style], w, h, self.ctx["paper"], self.seed,
                       0.45 if style == "black" else 0.85).convert("RGBA")
        if tab_img:
            img.alpha_composite(tab_img, (pad - 6, 30))
        x = pad
        base = big_top - top
        if s.get("prefix"):
            psize = int(big_size * 0.72)
            ptop, pbot = ink_box(s["prefix"], "anton", psize)
            pbase = base - big_h / 2 + (pbot - ptop) / 2
            x = draw_text(img, x, pbase, s["prefix"], "anton", psize, fg) + 18
        if big:
            draw_text(img, x, base, big, "anton", big_size, fg)
        if label_lines:
            lsize = s.get("label_size", 22)
            lh = lsize + 9
            ly = base - big_h / 2 - (len(label_lines) * lh) / 2 + lsize * 0.8
            for line in label_lines:
                lw = text_width(line, "mono", lsize, 2)
                draw_text(img, w - pad - lw, ly, line, "mono", lsize, fg, 2)
                ly += lh
        if foot:
            fsize = s.get("foot_size", 30)
            fw = text_width(foot, "mono_med", fsize, 1)
            draw_text(img, w - pad - fw, h - 34, foot, "mono_med", fsize, fg, 1)
        return img


class Stamp(Element):
    entrance = "slam"

    def texts(self):
        return [self.spec["text"]] + ([self.spec["sub"]] if self.spec.get("sub") else [])

    anchor = "center"

    def art(self, u):
        s = self.spec
        size = s.get("size", 72)
        col = INK if s.get("color") == "ink" else RED
        text = s["text"]
        tw = text_width(text, "anton", size, 2)
        top, bot = ink_box(text, "anton", size)
        sub = s.get("sub")
        ssize = int(size * 0.3)
        h = int(bot - top + 34 + (ssize + 12 if sub else 0))
        w = int(tw + 52)
        img = Image.new("RGBA", (w + 12, h + 12), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([6, 6, w + 5, h + 5], radius=12, fill=CARD + (232,), outline=col + (255,), width=6)
        draw_text(img, 6 + 26, 6 + 17 - top, text, "anton", size, col, 2)
        if sub:
            sw = text_width(sub, "mono_bold", ssize, 3)
            draw_text(img, 6 + (w - sw) / 2, h - 6, sub, "mono_bold", ssize, col, 3)
        return worn(img, self.seed, 0.08)

    def finish(self, art):
        return rotated(shadowed(art, offset=(4, 6), blur=6, opacity=0.18, pad=20), self.rot)


class Photo(Element):
    entrance = "drop"

    def texts(self):
        return [self.spec["tab"]] if self.spec.get("tab") else []

    def art(self, u):
        s = self.spec
        w, h = s.get("w", 960), s.get("h", 560)
        src = self.ctx["photos"].get(s.get("src"))
        if src and Path(src["path"]).exists():
            ph = Image.open(src["path"]).convert("L")
            r = max(w / ph.width, h / ph.height)
            ph = ph.resize((int(ph.width * r + 1), int(ph.height * r + 1)), Image.LANCZOS)
            fx, fy = s.get("focus", [0.5, 0.5])
            ox = int((ph.width - w) * fx)
            oy = int((ph.height - h) * fy)
            ph = ph.crop((ox, oy, ox + w, oy + h))
            g = np.asarray(ph).astype(np.float32)
            lo, hi = np.percentile(g, 2), np.percentile(g, 98)
            g = np.clip((g - lo) / max(1, hi - lo), 0, 1)
            g = g ** 1.1
            ht = s.get("halftone", 0.35)
            if ht > 0:
                yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
                cell = 6.0
                u_, v_ = (xx + yy) / math.sqrt(2), (xx - yy) / math.sqrt(2)
                dist = np.hypot((u_ % cell) - cell / 2, (v_ % cell) - cell / 2) / (cell / math.sqrt(2))
                dots = np.clip(((1 - g) - dist) * 6 + 0.5, 0, 1)
                g = g * (1 - ht) + (1 - dots) * ht
            tone = np.stack([g * 236 + 14, g * 232 + 14, g * 224 + 16], -1)
            photo = Image.fromarray(np.clip(tone, 0, 255).astype(np.uint8))
        else:
            photo = self.placeholder(w, h, s, src)
        mask = torn_mask(w, h, self.seed, depth=16)
        fiber = torn_mask(w, h, self.seed, depth=16, fiber=5)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        white = Image.new("RGBA", (w, h), (246, 243, 236, 255))
        white.putalpha(fiber)
        img.alpha_composite(white)
        ph = photo.convert("RGBA")
        ph.putalpha(mask)
        img.alpha_composite(ph)
        if s.get("tab"):
            t = tab_image(s["tab"], 22)
            img.alpha_composite(t, (22, h - t.height - 30))
        return img

    def placeholder(self, w, h, s, src):
        g = np.linspace(0.30, 0.18, h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
        img = Image.fromarray((g * 255).astype(np.uint8)).convert("RGB")
        d = ImageDraw.Draw(img)
        for i in range(-h, w, 26):
            d.line([(i, 0), (i + h, h)], fill=(70, 70, 68), width=2)
        title = "PHOTO {} GOES HERE".format(src["id"] if src else "?")
        tw = text_width(title, "mono_bold", 34, 3)
        draw_text(img, (w - tw) / 2, h / 2 - 10, title, "mono_bold", 34, (236, 232, 224), 3)
        alt = (src or {}).get("alt", "")
        if alt:
            aw = text_width(alt, "mono_med", 22, 1)
            draw_text(img, (w - aw) / 2, h / 2 + 34, alt, "mono_med", 22, (200, 196, 188), 1)
        return img


class Screen(Element):
    """A screenshot (of the member portal, say) shown as it is, not as a halftone photo: on a white card,
    with an optional tab, and marks that land on their words: a red ring round what to tap ("ring") or a
    lemon highlight over a word ("lemon").

    "src" names a screenshot in reel.json "screens"; "crop" ([x0, y0, x1, y1], shares of the image) shows
    part of it; "w" and "h" are the most it may take. A mark's "box" is in shares of the crop, and its "text"
    names the words it marks, so the check can tell whether it sits on them (tools/verify_media.py).
    The screenshot's own words aren't card text: the reel check leaves its area out (timeline.json)."""
    entrance = "rise"
    PAD = 14
    HOLD = 4.6          # the least time a screenshot stays on screen (reel.json "hold" changes it)

    def texts(self):
        return [self.spec["tab"]] if self.spec.get("tab") else []

    def marks(self):
        return self.spec.get("marks", [])

    def animated_until(self):
        return max(m.get("at", 0.0) for m in self.marks()) + 0.3 if self.marks() else 0.0

    def sounds(self, t0):
        return super().sounds(t0) + [("key", t0 + m.get("at", 0.0)) for m in self.marks() if m.get("at", 0.0) >= 0.15]

    def source(self):
        """The screenshot, cropped and scaled to fit w x h (made once), or None when its file is missing."""
        if getattr(self, "_shot", None) is None:
            s = self.spec
            src = self.ctx.get("screens", {}).get(s.get("src"))
            if not (src and Path(src["path"]).exists()):
                return None
            im = Image.open(src["path"]).convert("RGB")
            x0, y0, x1, y1 = s.get("crop", src.get("crop", [0, 0, 1, 1]))
            im = im.crop((round(x0 * im.width), round(y0 * im.height), round(x1 * im.width), round(y1 * im.height)))
            r = min(s.get("w", 860) / im.width, s.get("h", 760) / im.height)
            self._shot = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
        return self._shot

    def layout(self):
        """(art width, art height, and the screenshot's x, y, w, h inside the art)."""
        shot = self.source()
        sw, sh = shot.size if shot else (self.spec.get("w", 860), min(self.spec.get("h", 760), 520))
        top = tab_image(self.spec["tab"], 22).height // 2 if self.spec.get("tab") else 0
        return sw + 2 * self.PAD, sh + 2 * self.PAD + top, self.PAD, self.PAD + top, sw, sh

    def art(self, u):
        s = self.spec
        aw, ah, sx, sy, sw, sh = self.layout()
        img = Image.new("RGBA", (aw, ah), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([0, sy - self.PAD, aw - 1, ah - 1], radius=16,
                                              fill=(250, 248, 244, 255), outline=INK + (255,), width=3)
        shot = self.source() or self.placeholder(sw, sh)
        mask = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, sw - 1, sh - 1], radius=8, fill=255)
        img.paste(shot, (sx, sy), mask)
        for m in self.marks():
            p = (u - m.get("at", 0.0)) / 0.25
            if p >= 0:
                self.draw_mark(img, m, sx, sy, sw, sh, min(1.0, p))
        if s.get("tab"):
            img.alpha_composite(tab_image(s["tab"], 22), (26, 0))
        return img

    def draw_mark(self, img, m, sx, sy, sw, sh, p):
        x0, y0, x1, y1 = m["box"]
        cx, cy = sx + (x0 + x1) / 2 * sw, sy + (y0 + y1) / 2 * sh
        if m.get("style", "ring") == "lemon":
            hw, hh = (x1 - x0) * sw / 2 + 6, (y1 - y0) * sh / 2 + 4
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).rounded_rectangle([cx - hw, cy - hh, cx - hw + 2 * hw * p, cy + hh], radius=6,
                                                    fill=LEMON + (125,))
            img.alpha_composite(layer)
            return
        k = 1.25 - 0.25 * ease_out_cubic(p)          # the ring closes in on the button
        hw, hh = ((x1 - x0) * sw / 2 + 10) * k, ((y1 - y0) * sh / 2 + 8) * k
        ImageDraw.Draw(img).rounded_rectangle([cx - hw, cy - hh, cx + hw, cy + hh], radius=int(min(hh, 26)),
                                              outline=RED + (int(255 * p),), width=7)

    def placeholder(self, w, h):
        src = self.ctx.get("screens", {}).get(self.spec.get("src")) or {}
        img = Image.new("RGB", (w, h), (226, 228, 232))
        d = ImageDraw.Draw(img)
        for i in range(-h, w, 26):
            d.line([(i, 0), (i + h, h)], fill=(208, 211, 216), width=2)
        title = "SCREENSHOT {} GOES HERE".format(src.get("id", "?"))
        tw = text_width(title, "mono_bold", 30, 3)
        draw_text(img, (w - tw) / 2, h / 2 - 8, title, "mono_bold", 30, (70, 74, 82), 3)
        shows = src.get("shows", "")
        if shows:
            shows = shows if len(shows) <= 60 else shows[:57] + "..."
            draw_text(img, (w - text_width(shows, "mono_med", 20, 1)) / 2, h / 2 + 30, shows, "mono_med", 20, (90, 94, 102), 1)
        return img

    def frame_box(self):
        """The screenshot's area on the frame once the element has landed: (x0, y0, x1, y1)."""
        aw, ah, sx, sy, sw, sh = self.layout()
        cx, cy = self.centre()
        return (cx - aw / 2 + sx, cy - ah / 2 + sy, cx - aw / 2 + sx + sw, cy - ah / 2 + sy + sh)


class Headline(Element):
    entrance = "pop"
    sound = "pop"

    def texts(self):
        return list(self.spec["lines"])

    def lines_layout(self):
        size = self.spec.get("size", 250)
        widest = max(text_width(t, "anton", size) for t in self.spec["lines"])
        size = int(min(size, size * self.spec.get("max_w", 920) / widest))
        lh = int(size * self.spec.get("leading", 0.98))
        return size, lh

    def art(self, u):
        s = self.spec
        size, lh = self.lines_layout()
        lines = s["lines"]
        stagger = s.get("stagger", 0.4)
        w = int(max(text_width(t, "anton", size) for t in lines) + 40)
        h = int(lh * len(lines) + size * 0.35)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ul = s.get("underline")
        for i, line in enumerate(lines):
            v = u - i * stagger
            if v < 0:
                continue
            p = min(1.0, v / 0.2)
            sc = 0.82 + 0.18 * ease_out_back(p, 2.0)
            top, bot = ink_box(line, "anton", size)
            lw = text_width(line, "anton", size)
            layer = Image.new("RGBA", (int(lw + 10), int(bot - top + 10)), (0, 0, 0, 0))
            draw_text(layer, 2, -top + 4, line, "anton", size, INK)
            if sc < 0.999:
                layer = layer.resize((max(1, int(layer.width * sc)), max(1, int(layer.height * sc))), Image.LANCZOS)
            base_y = i * lh + size * 0.92
            cx, cy = 10 + lw / 2, base_y + (top + bot) / 2
            img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))
            if ul and ul.get("line") == i:
                q = (u - ul.get("at", 1.0)) / ul.get("dur", 0.5)
                if q > 0:
                    self.draw_underline(img, 10, base_y + 34, lw, min(q, 1.0))
        return img

    @staticmethod
    def draw_underline(img, x, y, length, q):
        pts = [(x, y), (x + length * 0.38, y - 2), (x + length * 0.43, y - 40), (x + length * 0.52, y - 44),
               (x + length * 0.55, y - 14), (x + length * 0.48, y + 8), (x + length * 0.44, y - 8),
               (x + length * 1.05, y - 4)]
        P = np.array(pts, np.float32)
        seg = np.hypot(*(P[1:] - P[:-1]).T)
        total = seg.sum() * q
        out, acc = [tuple(P[0])], 0.0
        for i, sl in enumerate(seg):
            if acc + sl >= total:
                f = (total - acc) / sl if sl else 0
                out.append(tuple(P[i] + f * (P[i + 1] - P[i])))
                break
            out.append(tuple(P[i + 1]))
            acc += sl
        d = ImageDraw.Draw(img)
        d.line(out, fill=LEMON, width=18, joint="curve")
        for px, py in (out[0], out[-1]):
            d.ellipse([px - 9, py - 9, px + 9, py + 9], fill=LEMON)

    def animated_until(self):
        s = self.spec
        end = (len(s["lines"]) - 1) * s.get("stagger", 0.4) + 0.25
        if s.get("underline"):
            end = max(end, s["underline"].get("at", 1.0) + s["underline"].get("dur", 0.5))
        return end

    def state(self, u):
        dx, dy, _, alpha, reveal = super().state(u)
        return dx, dy, 1.0, 1.0, reveal

    anchor = "left"

    def finish(self, art):
        return art

    def sounds(self, t0):
        s = self.spec
        out = [("pop", t0 + i * s.get("stagger", 0.4)) for i in range(len(s["lines"]))]
        if s.get("underline"):
            out.append(("scribble", t0 + s["underline"].get("at", 1.0), s["underline"].get("dur", 0.5)))
        return out


class Note(Element):
    entrance = "write"

    def texts(self):
        return [self.spec["text"]]

    def handwritten(self):
        return self.texts()

    def art(self, u):
        s = self.spec
        size = s.get("size", 64)
        col = {"red": RED, "ink": INK, "lemon": LEMON}[s.get("color", "red")]
        text = s["text"]
        tw = text_width(text, "hand", size)
        top, bot = ink_box(text, "hand", size)
        img = Image.new("RGBA", (int(tw + 20), int(bot - top + 20)), (0, 0, 0, 0))
        draw_text(img, 10, 10 - top, text, "hand", size, col)
        return img

    anchor = "center"

    def finish(self, art):
        return rotated(art, self.rot)


class Tag(Element):
    entrance = "slide_right"

    def texts(self):
        return [self.spec["text"]]

    def art(self, u):
        s = self.spec
        size = s.get("size", 88)
        text = s["text"]
        tw = text_width(text, "anton", size, 1)
        top, bot = ink_box(text, "anton", size)
        w, h = int(tw + 64), int(bot - top + 44)
        img = textured(STYLE_FILL[s.get("style", "yellow")], w, h, self.ctx["paper"], self.seed).convert("RGBA")
        draw_text(img, 32, 22 - top, text, "anton", size, INK, 1)
        return img


class Funnel(Element):
    entrance = "drop"

    def texts(self):
        return [self.spec["tab"]] + [r["text"] for r in self.spec["rows"]]

    def animated_until(self):
        return max(r["at"] for r in self.spec["rows"]) + 0.6

    def art(self, u):
        s = self.spec
        w = s.get("w", 900)
        rows = s["rows"]
        bar_h, gap = 98, 24
        h = 30 + 50 + 26 + len(rows) * (bar_h + gap) + 30
        img = grid_card(w, h, self.ctx["paper"], self.seed)
        t = tab_image(s["tab"])
        img.alpha_composite(t, (34, 30))
        d = ImageDraw.Draw(img)
        inner = w - 80
        y = 30 + t.height + 30
        for r in rows:
            p = ease_out_cubic((u - r["at"]) / 0.55)
            if p > 0:
                bw = inner * r["width"] * p
                x0 = w / 2 - bw / 2
                fill = LEMON if r.get("style") == "yellow" else CARD
                d.rectangle([x0, y, x0 + bw, y + bar_h], fill=fill, outline=INK, width=4)
                if p > 0.85:
                    size = r.get("size", 52)
                    tw = text_width(r["text"], "anton", size, 1)
                    top, bot = ink_box(r["text"], "anton", size)
                    draw_text(img, w / 2 - tw / 2, y + bar_h / 2 - (top + bot) / 2, r["text"], "anton", size, INK, 1)
            y += bar_h + gap
        return img

    def sounds(self, t0):
        return super().sounds(t0) + [("whoosh_soft", t0 + r["at"]) for r in self.spec["rows"]]


class LineChart(Element):
    entrance = "rise"

    def texts(self):
        s = self.spec
        return [s["tab"], s["start"]["value"], s["start"]["sub"], s["end"]["value"], s["end"]["sub"]]

    def animated_until(self):
        return self.spec.get("draw_at", 0.7) + self.spec.get("draw_dur", 1.5) + 0.1

    def art(self, u):
        s = self.spec
        w, h = s.get("w", 920), s.get("h", 560)
        img = grid_card(w, h, self.ctx["paper"], self.seed)
        t = tab_image(s["tab"])
        img.alpha_composite(t, (34, 30))
        x0, x1 = 90, w - 120
        y0, y1 = 210, h - 120
        n = 120
        xs = np.linspace(x0, x1, n)
        q = np.linspace(0, 1, n)
        ys = y0 + (y1 - y0) * (q * q * (3 - 2 * q)) * 0.85 + 30 * q
        p = ease_in_out((u - s.get("draw_at", 0.7)) / s.get("draw_dur", 1.5))
        d = ImageDraw.Draw(img)
        k = int(p * (n - 1))
        if p > 0:
            d.line(list(zip(xs[:k + 1], ys[:k + 1])), fill=RED, width=7, joint="curve")
        for frac, end, ax, ay in ((0.0, s["start"], xs[0], ys[0]), (1.0, s["end"], xs[-1], ys[-1])):
            if p >= frac - 1e-6 and (frac == 0.0 and p > 0 or p >= 0.999):
                d.ellipse([ax - 10, ay - 10, ax + 10, ay + 10], fill=RED)
                vsize = 70
                vw = text_width(end["value"], "anton", vsize)
                vx = ax - 10 if frac == 0 else ax - vw + 20
                vy = ay - 34
                draw_text(img, vx, vy, end["value"], "anton", vsize, INK)
                sw = text_width(end["sub"], "mono", 27, 2)
                sx = ax - 10 if frac == 0 else ax - sw + 20
                d.rectangle([sx - 8, ay + 22, sx + sw + 8, ay + 58], fill=CARD)
                draw_text(img, sx, ay + 50, end["sub"], "mono", 27, INK, 2)
        return img

    def sounds(self, t0):
        return super().sounds(t0) + [("scribble", t0 + self.spec.get("draw_at", 0.7), self.spec.get("draw_dur", 1.5))]


class ArrowCard(Element):
    entrance = "slide_left"

    def texts(self):
        s = self.spec
        return [s["arrow"], s["title"]] + ([s["sub"]] if s.get("sub") else [])

    def art(self, u):
        s = self.spec
        w = s.get("w", 900)
        size = s.get("size", 84)
        top, bot = ink_box(s["title"], "anton", size)
        h = int(bot - top + (60 if s.get("sub") else 40) + 34)
        img = textured(STYLE_FILL[s.get("style", "white")], w, h, self.ctx["paper"], self.seed).convert("RGBA")
        d = ImageDraw.Draw(img)
        draw_arrow(d, 36, 26 - top + 4, 110, ARROWS[s["arrow"]], INK, width=7)
        draw_text(img, 130, 24 - top, s["title"], "anton", size, INK)
        if s.get("sub"):
            draw_text(img, 132, 24 - top + 42, s["sub"], "mono", 22, INK, 2)
        return img


class Timeline(Element):
    entrance = "rise"

    def texts(self):
        s = self.spec
        return [s["tab"]] + [g["label"] for g in s["segments"]] + [t["text"] for t in s["ticks"]] + \
            ([s["foot"]] if s.get("foot") else [])

    def animated_until(self):
        return max(g["at"] for g in self.spec["segments"]) + 0.9

    def art(self, u):
        s = self.spec
        w = s.get("w", 920)
        segs = s["segments"]
        h = 30 + 50 + 30 + 100 + 70 + len(segs) * 64 + (60 if s.get("foot") else 20) + 20
        img = textured(CARD, w, h, self.ctx["paper"], self.seed).convert("RGBA")
        t = tab_image(s["tab"])
        img.alpha_composite(t, (34, 30))
        d = ImageDraw.Draw(img)
        bx0, bx1 = 50, w - 50
        by0 = 30 + t.height + 34
        by1 = by0 + 96
        d.rectangle([bx0, by0, bx1, by1], fill=(214, 209, 200))
        for g in segs:
            p = ease_out_cubic((u - g["at"]) / 0.8)
            if p > 0:
                gx0 = bx0 + (bx1 - bx0) * g["from"]
                gx1 = gx0 + (bx1 - bx0) * (g["to"] - g["from"]) * p
                d.rectangle([gx0, by0, gx1, by1], fill=STYLE_FILL[g.get("style", "white")])
        for g in segs:
            gx = bx0 + (bx1 - bx0) * g["to"]
            if g["to"] < 0.999:
                d.line([(gx, by0), (gx, by1)], fill=INK, width=3)
        d.rectangle([bx0, by0, bx1, by1], outline=INK, width=5)
        for tk in s["ticks"]:
            tx = bx0 + (bx1 - bx0) * tk["pos"]
            d.line([(tx, by1), (tx, by1 + 14)], fill=INK, width=3)
            tw = text_width(tk["text"], "mono", 30)
            draw_text(img, min(max(tx - tw / 2, bx0 - 10), bx1 - tw + 10), by1 + 50, tk["text"], "mono", 30, INK)
        ly = by1 + 112
        for g in segs:
            d.rectangle([bx0, ly - 34, bx0 + 38, ly + 4], fill=STYLE_FILL[g.get("style", "white")], outline=INK, width=3)
            draw_text(img, bx0 + 58, ly, g["label"], "anton", 50, INK, 1)
            ly += 64
        if s.get("foot"):
            draw_text(img, bx0, h - 34, s["foot"], "mono_med", 21, GREY_MONO, 1)
        return img

    def sounds(self, t0):
        return super().sounds(t0) + [("whoosh_soft", t0 + g["at"]) for g in self.spec["segments"]]


class Typewriter(Element):
    entrance = "rise"

    def texts(self):
        return [self.spec["tab"]] + list(self.spec["lines"])

    def char_times(self):
        s = self.spec
        out = []
        t = s.get("type_at", 0.6)
        for line in s["lines"]:
            per = min(0.06, (s.get("line_every", 1.2) - 0.25) / max(1, len(line)))
            out.append([t + i * per for i in range(len(line))])
            t += s.get("line_every", 1.2)
        return out

    def animated_until(self):
        s = self.spec
        end = self.char_times()[-1][-1] + 0.1
        if s.get("highlight"):
            end = max(end, s.get("highlight_at", end) + 0.35)
        return end

    def art(self, u):
        s = self.spec
        w = s.get("w", 920)
        size, lh = s.get("size", 58), s.get("leading", 88)
        widest = max(text_width(line, "type", size) for line in s["lines"])
        size = int(min(size, size * (w - 100) / widest))
        h = 30 + 50 + 34 + lh * len(s["lines"]) + 26
        img = textured(CARD, w, h, self.ctx["paper"], self.seed).convert("RGBA")
        t = tab_image(s["tab"])
        img.alpha_composite(t, (34, 30))
        y = 30 + t.height + 34 + size
        times = self.char_times()
        hl = s.get("highlight")
        for line, ts in zip(s["lines"], times):
            n = sum(1 for tt in ts if u >= tt)
            if hl and hl in line:
                q = ease_out_cubic((u - s.get("highlight_at", 4.4)) / 0.3)
                if q > 0:
                    i = line.index(hl)
                    hx0 = 44 + text_width(line[:i], "type", size)
                    hw = text_width(hl, "type", size) * q
                    ImageDraw.Draw(img).rectangle([hx0 - 6, y - size * 0.78, hx0 + hw + 6, y + size * 0.16], fill=LEMON)
            if n:
                draw_text(img, 44, y, line[:n], "type", size, INK)
            y += lh
        return img

    def sounds(self, t0):
        out = super().sounds(t0)
        for ts in self.char_times():
            out += [("key", t0 + tt) for tt in ts]
        return out


class EndCard(Element):
    """The sign-off card: the logo, the tagline, the follow line and the small print.

    The logo is the image in "logo_file" (by default brand.json's logo_file), fitted in logo_w x logo_h;
    without one, the "logo" lines (the brand name) are drawn big with a highlighter swipe on the last.
    The follow line is a handwritten note over a black button: "cta_note" and "cta", by default
    brand.json's follow note and "FOLLOW <instagram handle>" ("" leaves either out). The button pops
    in at "cta_at" ("cta_on": the word it lands on), the rest of the card with the card."""
    entrance = "pop"
    sound = "pop"
    W = 1000

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        follow = _BRAND.get("follow", {})
        handle = _BRAND.get("instagram", "")
        self.cta = spec.get("cta", follow.get("button", "FOLLOW " + handle.upper() if handle else ""))
        self.cta_note = spec.get("cta_note", follow.get("note", ""))
        self.cta_at = spec.get("cta_at", 0.0)
        self.logo_name = spec.get("logo_file", _BRAND.get("logo_file", ""))
        self.logo_file = ROOT / self.logo_name if self.logo_name else None

    def texts(self):
        s = self.spec
        return [s["tagline"]] + [t for t in (self.cta_note, self.cta) if t] + list(s.get("small", []))

    def handwritten(self):
        return [self.spec["tagline"]] + ([self.cta_note] if self.cta_note else [])

    def animated_until(self):
        return self.cta_at + 0.4 if self.cta else 0.0

    def sounds(self, t0):
        return super().sounds(t0) + ([("pop", t0 + self.cta_at)] if self.cta and self.cta_at >= 0.15 else [])

    def logo(self):
        """The logo as an image: the file fitted in logo_w x logo_h, or the brand name drawn big. Made once."""
        if getattr(self, "_logo", None) is None:
            self._logo = self._make_logo()
        return self._logo

    def _make_logo(self):
        s = self.spec
        if self.logo_file and self.logo_file.exists():
            lg = Image.open(self.logo_file).convert("RGBA")
            r = min(s.get("logo_w", 760) / lg.width, s.get("logo_h", 360) / lg.height)
            return lg.resize((round(lg.width * r), round(lg.height * r)), Image.LANCZOS)
        words = BRAND_NAME.upper().split()
        lines = s.get("logo", [words[0], " ".join(words[1:])] if len(words) > 1 else words)
        size = s.get("size", 170)
        lh = int(size * 0.93)
        img = Image.new("RGBA", (self.W, lh * len(lines) + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i, line in enumerate(lines):
            lw = text_width(line, "anton", size)
            base = (i + 1) * lh - 10
            if i == len(lines) - 1:
                top, bot = ink_box(line, "anton", size)
                hx0, hx1 = self.W / 2 - lw / 2 - 30, self.W / 2 + lw / 2 + 30
                hy0, hy1 = base + top * 0.52, base + 12
                rng = np.random.default_rng(self.seed)
                poly = [(hx0 + rng.uniform(-6, 6), hy0 + rng.uniform(-5, 5)), (hx1 + rng.uniform(-6, 6), hy0 - 10),
                        (hx1 + rng.uniform(-6, 6), hy1 + rng.uniform(-5, 5)), (hx0, hy1 + 8)]
                d.polygon(poly, fill=LEMON)
            draw_text(img, self.W / 2 - lw / 2, base, line, "anton", size, INK)
        return img

    def button(self):
        """The follow button: a black tab, its first word in lemon and the rest in card white. Made once."""
        if getattr(self, "_button", None) is None:
            self._button = self._make_button()
        return self._button

    def _make_button(self):
        size = 60
        first, _, rest = self.cta.partition(" ")
        top, bot = ink_box(self.cta, "anton", size)
        gap = text_width(" ", "anton", size)
        tw = text_width(first, "anton", size, 1) + (gap + text_width(rest, "anton", size, 1) if rest else 0)
        w, h = int(tw + 76), int(-top + 52)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle([0, 0, w - 1, h - 1], radius=16, fill=INK)
        x = draw_text(img, 38, 26 - top, first, "anton", size, LEMON, 1)
        if rest:
            draw_text(img, x + gap, 26 - top, rest, "anton", size, CARD, 1)
        return img

    def art(self, u):
        s = self.spec
        w = self.W
        img = Image.new("RGBA", (w, 1100), (0, 0, 0, 0))
        lg = self.logo()
        img.alpha_composite(lg, ((w - lg.width) // 2, 0))
        y = lg.height + s.get("tagline_gap", 88)                 # the tagline's baseline
        tag = s["tagline"]
        draw_text(img, w / 2 - text_width(tag, "hand", 84) / 2, y, tag, "hand", 84, INK)
        if self.cta_note:
            y += 74
            draw_text(img, w / 2 - text_width(self.cta_note, "hand", 64) / 2, y, self.cta_note, "hand", 64, RED)
        if self.cta:
            btn = self.button()
            top = y + 24
            p = (u - self.cta_at) / 0.32
            if p >= 0:
                k = 0.55 + 0.45 * ease_out_back(p)
                b = shadowed(btn, offset=(0, 8), blur=10, opacity=0.3, pad=24)
                if abs(k - 1) > 0.002:                         # grows, overshoots a little, settles
                    b = b.resize((max(1, round(b.width * k)), max(1, round(b.height * k))), Image.LANCZOS)
                if p < 0.3:
                    b.putalpha(b.getchannel("A").point(lambda v: int(v * p / 0.3)))
                img.alpha_composite(b, (round(w / 2 - b.width / 2), round(top + btn.height / 2 - b.height / 2)))
            y = top + btn.height + 22
        y += 44
        for line in s.get("small", []):
            draw_text(img, w / 2 - text_width(line, "mono", 24, 2) / 2, y, line, "mono", 24, GREY_MONO, 2)
            y += 40
        return img.crop((0, 0, w, min(img.height, int(y))))

    def finish(self, art):
        return art


# ---------------------------------------------------------------- paper cut-outs (PF Stories)

GROUND_Y = 1170        # where the cut-outs stand: just above the captions
STOP = 12              # stop motion: 12 poses a second


def stop_motion(u):
    """Local time held at the last of 12 poses a second, and that pose's number."""
    k = int(math.floor(max(0.0, u) * STOP + 1e-6))
    return k / STOP, k


def walk_plan(spec, speed=280.0):
    """A puppet's walks, in order: (start, end, from x, to x), times in seconds after it appears."""
    x, plan = spec.get("x", 540), []
    for m in sorted(spec.get("moves", []), key=lambda m: m.get("at", 0.0)):
        if m.get("do") == "walk":
            to = float(m["to"])
            at = m.get("at", 0.0)
            dur = m.get("dur") or max(0.4, abs(to - x) / speed)
            plan.append((at, at + dur, x, to))
            x = to
    return plan


class Cutout(Element):
    """Something cut from paper (tools/cutout.py) standing on the ground: x is its centre, y the ground line.
    It moves in stop motion, 12 poses a second, each a little off, as if moved by hand between photos."""
    entrance = "pop"
    anchor = "bottom"
    WOBBLE = 1.4            # pixels a pose can be off by

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.y = spec.get("y", GROUND_Y)
        self.scale = float(spec.get("scale", 1.0))
        self._cache, self._anchor = {}, (0, 0)

    def animated_until(self):
        return 10 ** 6

    def cut(self, art, anchor, flip=False):
        """The finished cut-out (paper finish, white edge, shadow; mirrored to face left) and its ground point."""
        if self.scale != 1.0:
            art = art.resize((max(1, int(art.width * self.scale)), max(1, int(art.height * self.scale))), Image.LANCZOS)
            anchor = (anchor[0] * self.scale, anchor[1] * self.scale)
        pad = 36
        img = shadowed(cutout.finish(art, self.ctx["paper"], self.seed), offset=(9, 12), blur=11, opacity=0.34, pad=pad)
        ax, ay = anchor[0] + cutout.PAD + pad, anchor[1] + cutout.PAD + pad
        if flip:
            img, ax = ImageOps.mirror(img), img.width - ax
        return img, (ax, ay)

    def keep(self, key, make):
        if key not in self._cache:
            self._cache[key] = make()
            if len(self._cache) > 48:
                self._cache.pop(next(iter(self._cache)))
        img, self._anchor = self._cache[key]
        return img

    def place(self, sc):
        """Where the image's top-left goes so that its ground point stands at x, y."""
        ax, ay = self._anchor
        return self.x - ax * sc, self.y - ay * sc

    def size0(self):
        return (300, 300)

    def state(self, u):
        uq, k = stop_motion(u)
        dx, dy, sc, alpha, reveal = super().state(uq)
        rng = np.random.default_rng(self.seed * 7919 + k)
        return dx + rng.uniform(-1, 1) * self.WOBBLE, dy + rng.uniform(-1, 1) * self.WOBBLE, sc, alpha, reveal


class Puppet(Cutout):
    """A person from the cast (brand.json → cast) as a jointed paper puppet. Spec: who, x, y, scale (0.8), facing
    ("right" or "left"), pose, mood, and moves, each at a time ("at": seconds after it appears) or on a word ("on"):
      {"do": "walk", "to": 760, "dur": 1.6}   walk to x = 760 (dur in seconds; by default about 280 px a second)
      {"do": "pose", "pose": "wave"}          stand, wave, point, think, phone, hips, cheer, shrug, hold, sad
      {"do": "mood", "mood": "worried"}       neutral, smile, happy, worried, surprised, sad, angry, thinking
      {"do": "turn"} · {"do": "jump"} · {"do": "nod"} · {"do": "shake"}"""
    STEPS = 2.2            # steps a second when walking
    SCALE = 0.8            # a person beside a building, by default

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.scale = float(spec.get("scale", self.SCALE))
        self.who = spec.get("who", "shivam")
        cutout.look_of(self.who)                 # an unknown name stops here, with the cast listed
        for key, ok in (("pose", cutout.POSES), ("mood", cutout.MOODS)):
            for v in [spec.get(key)] + [m.get(key) for m in spec.get("moves", [])]:
                if v is not None and v not in ok:
                    raise SystemExit("{}: no {} '{}' (there are: {})".format(self.who, key, v, ", ".join(ok)))
        self.walks = walk_plan(spec)
        self.moves = sorted(spec.get("moves", []), key=lambda m: m.get("at", 0.0))

    def look(self, u, k):
        """Where the puppet is and how it looks at local time u (pose number k): (x, dy, render key)."""
        x, walk_t, facing = self.x, None, 1 if self.spec.get("facing", "right") == "right" else -1
        for t0, t1, a, b in self.walks:
            if u < t0:
                break
            facing = 1 if b >= a else -1
            if u < t1:
                x, walk_t = a + (b - a) * (u - t0) / (t1 - t0), u - t0
                break
            x = b
        pose, mood, tilt, dy = self.spec.get("pose", "stand"), self.spec.get("mood", "smile"), 0.0, 0.0
        for m in self.moves:
            at = m.get("at", 0.0)
            if at > u:
                break
            d, v = m.get("do"), u - at
            if d == "pose":
                pose = m.get("pose", pose)
            elif d == "mood":
                mood = m.get("mood", mood)
            elif d == "turn":
                facing = -facing
            elif d == "jump" and v < 0.6:
                dy, pose = -120 * math.sin(math.pi * v / 0.6), "cheer"
            elif d == "nod" and v < 0.7:
                dy = 7 * abs(math.sin(2 * math.pi * 1.5 * v))
            elif d == "shake" and v < 0.8:
                tilt = 9 * math.sin(2 * math.pi * 2.5 * v)
        phase = None
        if walk_t is not None:
            phase, pose = round(math.pi * self.STEPS * walk_t, 2), "walk"
        blink = k % 37 == self.seed % 37 and walk_t is None and mood != "surprised"
        wave = round(math.sin(2 * math.pi * 2.4 * u), 2) if pose == "wave" else 0.0
        return x, dy, (pose, mood, phase, blink, wave, round(tilt, 1), facing)

    def frame_image(self, u):
        uq, k = stop_motion(u)
        _, _, key = self.look(uq, k)

        def make():
            pose, mood, phase, blink, wave, tilt, facing = key
            art, anchor = cutout.person(self.who, pose, mood, phase=phase, blink=blink, wave=wave, tilt=tilt)
            return self.cut(art, anchor, flip=facing < 0)
        return self.keep(key, make)

    def state(self, u):
        dx, dy, sc, alpha, reveal = super().state(u)
        uq, k = stop_motion(u)
        x, ddy, _ = self.look(uq, k)
        return dx + (x - self.x), dy + ddy, sc, alpha, reveal

    def sounds(self, t0):
        ev = super().sounds(t0)
        for a, b, _, _ in self.walks:
            ev += [("step", t0 + a + (i + 0.5) / self.STEPS) for i in range(int((b - a) * self.STEPS))]
        return ev


class Prop(Cutout):
    """A thing cut from paper (tools/cutout.py → PROPS: factory, office, bank, home, phone, document, coins, calendar,
    laptop, tick, cross, clock, suitcase, cloud, sun, desk, skyline). Spec: kind, x, y (where its bottom stands),
    scale, facing, variant (phone: tick, alert, otp, chat, portal; document: rejected; clock: "4:30"), label (the
    name on its sign, from card_text: factory, office, bank), tab (a black tab on it, from card_text), and idle:
    sway, bob, buzz, smoke (a factory's chimney; on by default) or spin (a clock's hands race: time passing)."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.kind = spec.get("kind")
        if self.kind not in cutout.PROPS:
            raise SystemExit("no prop '{}' (there are: {})".format(self.kind, ", ".join(sorted(cutout.PROPS))))
        self.idle = spec.get("idle", "smoke" if self.kind == "factory" else None)
        self._base = None

    def texts(self):
        return [t for t in (self.spec.get("label"), self.spec.get("tab")) if t]

    def base(self):
        """The prop with its sign and tab, before the paper finish: (image, anchors, ground point)."""
        if self._base is None:
            art, anchors = cutout.prop(self.kind, self.spec.get("variant"))
            art = art.copy()
            label = self.spec.get("label")
            if label and "sign" in anchors:
                x0, y0, x1, y1 = anchors["sign"]
                size = int((y1 - y0) * 0.86)
                while size > 12 and text_width(label, "anton", size, 1.5) > (x1 - x0) - 16:
                    size -= 1
                tw = text_width(label, "anton", size, 1.5)
                draw_text(art, (x0 + x1) / 2 - tw / 2, (y0 + y1) / 2 + size * 0.42, label, "anton", size,
                          cutout.col(anchors.get("sign_fg", "ink")), 1.5)
            if self.spec.get("tab"):
                tab = tab_image(self.spec["tab"], 24)
                grown = Image.new("RGBA", (max(art.width, tab.width + 20), art.height + tab.height // 2), (0, 0, 0, 0))
                grown.alpha_composite(art, ((grown.width - art.width) // 2, 0))
                grown.alpha_composite(tab, ((grown.width - tab.width) // 2, art.height - tab.height // 2))
                art = grown
            top = 260 if self.idle == "smoke" and "smoke" in anchors else 0
            if top:
                grown = Image.new("RGBA", (art.width, art.height + top), (0, 0, 0, 0))
                grown.alpha_composite(art, (0, top))
                art, anchors = grown, dict(anchors, smoke=(anchors["smoke"][0], anchors["smoke"][1] + top))
            self._base = (art, anchors, (art.width / 2, art.height))
        return self._base

    def frame_image(self, u):
        uq, k = stop_motion(u)
        art, anchors, ground = self.base()
        moving = self.idle in ("smoke", "spin")
        key = k if moving else 0

        def make():
            img = art
            if self.idle == "smoke" and "smoke" in anchors:
                img = art.copy()
                pen = cutout.Pen(img.width, img.height)
                sx, sy = anchors["smoke"]
                for j in range(3):
                    q = ((uq * 0.42) + j / 3) % 1.0
                    r = 12 + 22 * q
                    pen.ellipse(sx + 16 + 90 * q, sy - 26 - 190 * q + 10 * math.sin(5 * q + j), r * 1.2, r, "card")
                img.alpha_composite(pen.done())
            if self.kind == "clock":
                hh, mm = (str(self.spec.get("variant") or "4:30") + ":0").split(":")[:2]
                minutes = int(hh) * 60 + int(mm) + (int(uq * STOP) * 25 if self.idle == "spin" else 0)
                img = cutout.clock_hands(img, anchors["hands"], (minutes / 60) % 12, minutes % 60)
            return self.cut(img, ground, flip=self.spec.get("facing") == "left")
        img = self.keep(key, make)
        if self.idle == "sway":
            ang = round(1.6 * math.sin(2 * math.pi * 0.6 * uq), 1)
            if ang:
                img = img.rotate(-ang, resample=Image.BICUBIC, center=self._anchor)
        return img

    def state(self, u):
        dx, dy, sc, alpha, reveal = super().state(u)
        uq, k = stop_motion(u)
        if self.idle == "bob":
            dy += 7 * math.sin(2 * math.pi * 0.8 * uq)
        elif self.idle == "buzz" and uq < 0.9:
            dx += (-1) ** k * 6
        return dx, dy, sc, alpha, reveal


class Bubble(Element):
    """A speech bubble (or a thought bubble) cut from paper, with a line of dialogue from card_text. Spec: text,
    x, y (the bubble's centre), width (at most, 560), size (46), tail ("left", "right", "down-left",
    "down-right": toward whoever says it), thought (true: a thought bubble)."""
    entrance = "pop"
    anchor = "center"

    def texts(self):
        return [self.spec["text"]]

    def art(self, u):
        s = self.spec
        size, maxw = s.get("size", 46), s.get("width", 560)
        lines = [" ".join(l) for l in wrap(s["text"].split(), maxw - 60, size)]
        lh = int(size * 1.18)
        tw = max(text_width(l, "caption", size) for l in lines)
        bw, bh = int(tw + 76), int(lh * len(lines) + 52)
        m = 70
        pen = cutout.Pen(bw + 2 * m, bh + 2 * m)
        tail = s.get("tail", "down-left")
        cx = m + bw / 2
        if s.get("thought"):
            for i, (dx, r) in enumerate(((0.18, 20), (0.07, 13))):
                x = m + bw * (dx if "left" in tail else 1 - dx)
                pen.ellipse(x, m + bh + 18 + i * 30, r, r, "card")
            pen.rect(m, m, m + bw, m + bh, "card", r=min(bh / 2, 60))
        else:
            x = m + bw * (0.22 if "left" in tail else 0.78)
            tip = {"left": (m - 46, m + bh * 0.6), "right": (m + bw + 46, m + bh * 0.6),
                   "down-left": (x - 40, m + bh + 54), "down-right": (x + 40, m + bh + 54)}.get(tail, (x - 40, m + bh + 54))
            if tail in ("left", "right"):
                yb = m + bh * 0.42
                base = [(m + (14 if tail == "left" else bw - 14), yb), (m + (14 if tail == "left" else bw - 14), yb + 44)]
            else:
                base = [(x - 26, m + bh - 10), (x + 26, m + bh - 10)]
            pen.poly(base + [tip], "card")
            pen.rect(m, m, m + bw, m + bh, "card", r=34)
        img = pen.done()
        y = m + 26 + size * 0.86
        for l in lines:
            w_ = text_width(l, "caption", size)
            draw_text(img, cx - w_ / 2, y, l, "caption", size, INK)
            y += lh
        return cutout.finish(img, self.ctx["paper"], self.seed)

    def state(self, u):
        return super().state(stop_motion(u)[0])


class Ground(Element):
    """The ground the cut-outs stand on: a strip of torn paper across the frame, its top edge a little above the
    ground line y (1170). Spec: y, color (pencil), h (170)."""
    entrance = "none"

    def __init__(self, spec, ctx):
        spec = dict(spec, x=540)
        spec["y"] = spec.get("y", GROUND_Y) - 34
        super().__init__(spec, ctx)

    def art(self, u):
        w, h = W + 120, self.spec.get("h", 170)
        body = textured(cutout.col(self.spec.get("color", "pencil")), w, h, self.ctx["paper"], self.seed, 0.9, 0.3)
        body = body.convert("RGBA")
        body.putalpha(torn_mask(w, h, self.seed, top=True, bottom=False, depth=12))
        fibres = Image.new("RGBA", (w, h), (246, 243, 236, 255))
        fibres.putalpha(torn_mask(w, h, self.seed, top=True, bottom=False, depth=12, fiber=5))
        fibres.alpha_composite(body)
        return fibres

    def finish(self, art):
        return shadowed(art, offset=(0, -6), blur=10, opacity=0.25, pad=30)


ELEMENTS = {"card": Card, "stamp": Stamp, "photo": Photo, "headline": Headline, "note": Note, "tag": Tag,
            "funnel": Funnel, "line_chart": LineChart, "arrow_card": ArrowCard, "timeline": Timeline,
            "typewriter": Typewriter, "endcard": EndCard, "screen": Screen,
            "puppet": Puppet, "prop": Prop, "bubble": Bubble, "ground": Ground}


# ---------------------------------------------------------------- episode, timing, captions

def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def decode_audio(path):
    """Mono float32 at SR."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, np.float32).copy()


def speech_span(a):
    """(start, end) of speech in a mono buffer, by a simple energy threshold."""
    if len(a) == 0:
        return 0.0, 0.0
    hop = SR // 100
    e = np.sqrt(np.convolve(a ** 2, np.ones(hop) / hop, mode="same"))
    thr = max(1e-4, e.max() * 0.06)
    idx = np.where(e > thr)[0]
    if len(idx) == 0:
        return 0.0, len(a) / SR
    return idx[0] / SR, idx[-1] / SR


def word_weights(words):
    out = []
    for wd in words:
        core = re.sub(r"[^\w₹%]", "", wd)
        wgt = 0.55 + 0.11 * len(core)
        if re.search(r"\d", core):
            wgt += 0.35 * len(re.sub(r"\D", "", core))
        gap = 0.0
        if wd.endswith((",", ":", ";")):
            gap = 0.22
        elif wd.endswith((".", "?", "!")):
            gap = 0.42
        out.append((wgt, gap))
    return out


def time_words(words, t0, t1):
    ww = word_weights(words)
    total = sum(a + b for a, b in ww[:-1]) + ww[-1][0] if ww else 1
    scale = (t1 - t0) / total if total else 0
    times, t = [], t0
    for a, b in ww:
        times.append((t, t + a * scale))
        t += (a + b) * scale
    return times


def split_pages(words, highlights, max_lines=3, width=800, size=54):
    """Caption pages: whole sentences, at most max_lines lines each."""
    sentences, cur = [], []
    for i, wd in enumerate(words):
        cur.append(i)
        if wd.endswith((".", "?", "!")):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)
    pages, page = [], []
    for sent in sentences:
        trial = page + sent
        if page and len(wrap([words[i] for i in trial], width, size)) > max_lines:
            pages.append(page)
            page = list(sent)
        else:
            page = trial
    if page:
        pages.append(page)
    return pages


def wrap(words, width, size):
    lines, cur = [], []
    for wd in words:
        trial = cur + [wd]
        if cur and text_width(" ".join(trial), "caption", size) > width:
            lines.append(cur)
            cur = [wd]
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def highlight_flags(words, phrases):
    flags = [False] * len(words)
    nw = [norm_word(w) for w in words]
    for ph in phrases or []:
        pw = [norm_word(w) for w in ph.split()]
        for i in range(len(words) - len(pw) + 1):
            if nw[i:i + len(pw)] == pw:
                for j in range(i, i + len(pw)):
                    flags[j] = True
    return flags


class Episode:
    def __init__(self, ep_dir, use_voice=True):
        self.dir = Path(ep_dir)
        self.ep = load_json(self.dir / "episode.json")
        self.reel = load_json(self.dir / "reel.json")
        self.lines = {l["shot"]: l for l in self.ep["script"]}
        self.photos = {}
        for pid, p in self.reel.get("photos", {}).items():
            self.photos[pid] = dict(p, id=p.get("id", pid), path=str(ROOT / p["file"]))
        self.screens = {sid: dict(sc, id=sc.get("id", sid), path=str(ROOT / sc["file"]))
                        for sid, sc in self.reel.get("screens", {}).items()}
        self.voice = {}
        vdir = self.dir / "media" / "audio" / "lines"
        if use_voice and vdir.exists():
            for f in vdir.iterdir():
                if f.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".ogg"):
                    self.voice[f.stem.upper()] = f
        self.timing()

    def timing(self):
        """Shot start/end. With a voice file for every line, shots follow the voice; otherwise the plan."""
        shots = self.ep["shots"]
        have_voice = all(s["id"] in self.voice for s in shots)
        self.voiced = have_voice
        tail = json.loads((BRAND / "brand.json").read_text()).get("rules", {}).get("tail_seconds", 3)
        self.shots, t = [], 0.0
        for n, s in enumerate(shots):
            planned = s["end"] - s["start"]
            words = self.lines[s["id"]]["vo"].split()
            if have_voice:
                a = decode_audio(self.voice[s["id"]])
                sp0, sp1 = speech_span(a)
                lead = 0.18
                speech = sp1 - sp0                       # the silence in the file doesn't count
                dur = max(planned * 0.6, lead + speech + 0.42, self.min_length(s["id"]))
                if n == len(shots) - 1:
                    dur = max(dur, lead + speech + tail)            # hold the end card
                vo = {"audio": a, "at": t + lead - sp0, "w0": t + lead, "w1": t + lead + (sp1 - sp0)}
            else:
                dur = planned
                vo = {"audio": None, "w0": t + 0.15, "w1": t + dur - 0.4}
            self.shots.append({"id": s["id"], "start": t, "end": t + dur, "vo": vo, "words": words,
                               "times": time_words(words, vo["w0"], vo["w1"])})
            t += dur
        self.length = t
        self.breaks = {}
        for b in self.ep.get("breaks", []):
            i = next(i for i, s in enumerate(self.shots) if s["id"] == b["after"])
            self.breaks[i + 1] = b["type"]

    def min_length(self, sid):
        """The shortest a shot may be: long enough for its timed elements, and a screenshot stays at least its
        "hold" (4.6 s by default) so a viewer can find the button the voice names."""
        last = 0.0
        for spec in self.reel["shots"].get(sid, []):
            last = max(last, spec.get("at", 0.1) if "on" not in spec else 0.0)
            if spec.get("type") == "screen":
                last = max(last, spec.get("hold", Screen.HOLD) - 0.8)
            if spec.get("type") == "puppet" and "on" not in spec:        # a walk finishes inside its shot
                ends = [t1 for _, t1, _, _ in walk_plan(spec)] + [m.get("at", 0) + 0.6 for m in spec.get("moves", [])
                                                                     if "on" not in m]
                last = max([last] + [spec.get("at", 0.1) + e for e in ends])
        return last + 0.8

    def word_time(self, shot, query):
        q = norm_word(query)
        for wd, (a, _) in zip(shot["words"], shot["times"]):
            if norm_word(wd).startswith(q):
                return a - shot["start"]
        raise SystemExit("{}: no word '{}' in the line \"{}\"".format(shot["id"], query, " ".join(shot["words"])))


# ---------------------------------------------------------------- the reel

class Reel:
    def __init__(self, ep_dir, use_voice=True):
        self.E = Episode(ep_dir, use_voice)
        self.paper = Paper()
        self.base = self.paper.rgb.convert("RGBA")
        self.ctx_photos = self.E.photos
        self.elements = []
        for i, shot in enumerate(self.E.shots):
            els = []
            for j, spec in enumerate(self.E.reel["shots"].get(shot["id"], [])):
                spec = self.resolve(shot, json.loads(json.dumps(spec)))
                if i > 0 and (i not in self.E.breaks) and spec.get("at", 0.1) < PUSH:
                    spec["at"] = PUSH
                ctx = {"paper": self.paper, "photos": self.ctx_photos, "screens": self.E.screens,
                       "seed": (i + 1) * 101 + j * 7}
                els.append(ELEMENTS[spec["type"]](spec, ctx))
            self.elements.append(els)
        self.header = self.make_header()
        self.strip_cache = {}
        self.caption_cache = {}
        self.pages = [self.make_pages(i) for i in range(len(self.E.shots))]
        self.sheets = {}

    def resolve(self, shot, spec):
        """Turn every "on": "word" into a time, so things land on the word as it is spoken."""
        lead = spec.get("lead", 0.12)

        def wt(word):
            return max(0.0, self.E.word_time(shot, word) - lead)
        if "on" in spec:
            spec["at"] = wt(spec["on"])
        base = spec.get("at", 0.1)
        for k in list(spec):
            if k.endswith("_on"):
                spec[k[:-3] + "_at"] = max(0.0, wt(spec[k]) - base)
        for key in ("rows", "segments", "marks", "moves"):
            for item in spec.get(key, []):
                if "on" in item:
                    item["at"] = max(0.0, wt(item["on"]) - base)
        for key in ("out", "underline"):
            if isinstance(spec.get(key), dict) and "on" in spec[key]:
                spec[key]["at"] = max(0.0, wt(spec[key]["on"]) - base)
        return spec

    # ---- checks
    def check_texts(self):
        problems = []
        shots = {s["id"]: s for s in self.E.ep["shots"]}
        for i, shot in enumerate(self.E.shots):
            allowed = list(shots[shot["id"]].get("card_text", [])) + list(shots[shot["id"]].get("motion_text", []))
            drawn = []
            for el in self.elements[i]:
                ts = el.texts()
                if all(t in allowed for t in ts):
                    drawn += ts
                elif " ".join(ts) in allowed:      # a headline whose lines make one card string
                    drawn.append(" ".join(ts))
                else:
                    for t in ts:
                        if t not in allowed:
                            problems.append("{} draws \"{}\", which isn't in its card_text".format(shot["id"], t))
                    drawn += ts
            for t in shots[shot["id"]].get("card_text", []):
                if t not in drawn:
                    problems.append("{}: card_text \"{}\" isn't drawn".format(shot["id"], t))
        for i, shot in enumerate(self.E.shots):
            for el in self.elements[i]:
                if isinstance(el, EndCard) and el.logo_file and not el.logo_file.exists():
                    problems.append("{}: the end card's logo {} is missing (the brand name is drawn instead): run "
                                    "python3 tools/make_logo.py, then node tools/render_assets.js logo".format(
                                        shot["id"], el.logo_name))
        for i, shot in enumerate(self.E.shots):
            for el in self.elements[i]:
                if isinstance(el, Screen) and el.spec.get("src") not in self.E.screens:
                    problems.append("{}: screen \"{}\" isn't in reel.json screens".format(shot["id"], el.spec.get("src")))
        for sid, sc in self.E.screens.items():
            if not Path(sc["path"]).exists():
                problems.append("screen {} ({}) is missing: a placeholder will show".format(sc["id"], sc["file"]))
        for pid, p in self.E.photos.items():
            if not Path(p["path"]).exists():
                problems.append("photo {} ({}) is missing: a placeholder will show".format(pid, p["file"]))
        return problems

    # ---- header
    def make_header(self):
        img = Image.new("RGBA", (W, 380), (0, 0, 0, 0))
        brand = self.E.reel.get("brand_label", BRAND_NAME.upper())
        size = 40
        top, bot = ink_box(brand, "anton", size)
        bw = text_width(brand, "anton", size, 1)
        d = ImageDraw.Draw(img)
        d.rectangle([64, 234, 64 + bw + 28, 296], fill=INK)
        draw_text(img, 78, 265 - (top + bot) / 2, brand, "anton", size, CARD, 1)
        tag = self.E.ep.get("tag", "")
        tsize = 21
        tw = text_width(tag, "mono", tsize, 1.6)
        box = Image.new("RGBA", (int(tw + 64), 54), (0, 0, 0, 0))
        bd = ImageDraw.Draw(box)
        bd.rectangle([0, 0, box.width - 1, 53], fill=CARD, outline=INK, width=3)
        bd.ellipse([18, 23, 26, 31], fill=INK)
        draw_text(box, 38, 35, tag, "mono", tsize, INK, 1.6)
        box = rotated(box, -0.8)
        img.alpha_composite(box, (int(1012 - box.width), 236))
        for cx, cy in ((1000, 334),):
            self.crosshair(d, cx, cy)
        return img

    @staticmethod
    def crosshair(d, cx, cy):
        d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], outline=MARK, width=2)
        d.line([(cx - 17, cy), (cx + 17, cy)], fill=MARK, width=2)
        d.line([(cx, cy - 17), (cx, cy + 17)], fill=MARK, width=2)

    def timecode(self, frame, t):
        f = int(round(t * FPS))
        s, ff = divmod(f, FPS)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        draw_text(frame, 66, 326, "{:02d}:{:02d}:{:02d}:{:02d}".format(h, m, s, ff), "mono_med", 20, GREY_MONO, 1)

    # ---- captions
    def make_pages(self, i):
        shot = self.E.shots[i]
        line = self.E.lines[shot["id"]]
        words = shot["words"]
        flags = highlight_flags(words, line.get("highlights"))
        pages = []
        for idx in split_pages(words, line.get("highlights"), size=CAP_SIZE):
            ws = [words[k] for k in idx]
            pages.append({"idx": idx, "lines": wrap(ws, 800, CAP_SIZE), "flags": [flags[k] for k in idx],
                          "t0": shot["times"][idx[0]][0] - 0.1})
        pages[0]["t0"] = shot["start"]
        return pages

    def strip(self, n_lines):
        if n_lines not in self.strip_cache:
            h = n_lines * CAP_LINE + 60
            body = textured(STRIP, 900, h, self.paper, 900 + n_lines, 0.7, 0.2).convert("RGBA")
            body.putalpha(torn_mask(900, h, 77 + n_lines, depth=9))
            self.strip_cache[n_lines] = body
        return self.strip_cache[n_lines]

    def caption(self, i, t):
        shot = self.E.shots[i]
        pages = self.pages[i]
        k = max(j for j, p in enumerate(pages) if t >= p["t0"]) if t >= pages[0]["t0"] else 0
        page = pages[k]
        spoken = sum(1 for idx in page["idx"] if t >= shot["times"][idx][0])
        key = (i, k, spoken)
        if key in self.caption_cache:
            return self.caption_cache[key]
        strip = self.strip(len(page["lines"])).copy()
        size, lh = CAP_SIZE, CAP_LINE
        y = 30 + 47
        n = 0
        for line in page["lines"]:
            widths = [text_width(wd, "caption", size) for wd in line]
            space = text_width(" ", "caption", size)
            total = sum(widths) + space * (len(line) - 1)
            x = strip.width / 2 - total / 2
            d = ImageDraw.Draw(strip)
            for wd, ww in zip(line, widths):
                spoken_here = n < spoken
                if page["flags"][n] and spoken_here:
                    d.rectangle([x - 6, y - 44, x + ww + 6, y + 12], fill=LEMON)
                draw_text(strip, x, y, wd, "caption", size, INK if spoken_here else GREY_WORD)
                x += ww + space
                n += 1
            y += lh
        out = rotated(shadowed(strip, offset=(5, 8), blur=10, opacity=0.25, pad=24), -0.4)
        self.caption_cache = {kk: v for kk, v in self.caption_cache.items() if kk[0] >= i - 1}
        self.caption_cache[key] = (out, strip.height)
        return self.caption_cache[key]

    # ---- wipes
    def sheet(self, kind):
        if kind not in self.sheets:
            sw = W + 240
            fill = {"tear-lemon": LEMON, "tear-black": BLACK_CARD, "tear-paper": (226, 222, 214)}[kind]
            body = textured(fill, sw, H, self.paper, 5150, 1.1 if kind != "tear-black" else 0.4, 0.4).convert("RGBA")
            body.putalpha(torn_mask(sw, H, 31, top=False, bottom=False, left=True, right=True, depth=40))
            under = Image.new("RGBA", (sw, H), (247, 244, 238, 255))
            under.putalpha(torn_mask(sw, H, 31, top=False, bottom=False, left=True, right=True, depth=40, fiber=6))
            under.alpha_composite(body)
            self.sheets[kind] = shadowed(under, offset=(0, 0), blur=20, opacity=0.45, pad=40)
        return self.sheets[kind]

    # ---- composition
    def shot_at(self, t):
        for i, s in enumerate(self.E.shots):
            if t < s["end"]:
                return i
        return len(self.E.shots) - 1

    def draw_elements(self, frame, i, u, push=0.0, jolt=(0, 0), stills=False):
        for el in self.elements[i]:
            v = u - el.at
            if v < 0:
                continue
            img = el.frame_image(v)
            dx, dy, sc, alpha, reveal = el.state(v)
            if stills:
                dx = dy = 0
                sc, alpha, reveal = 1.0, 1.0, 1.0
            if sc != 1.0:
                img = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))), Image.BILINEAR)
            if isinstance(el, Cutout):
                x0, y0 = el.place(sc)          # its ground point stands on the ground line
            else:
                cx, cy = el.centre()
                x0, y0 = cx - img.width / 2, cy - img.height / 2
            x0 += dx + jolt[0]
            y0 += dy + push + jolt[1]
            if reveal < 1.0:
                img = img.copy()
                a = np.asarray(img.getchannel("A")).astype(np.float32)
                edge = int(img.width * reveal)
                ramp = np.clip((edge - np.arange(img.width)) / 18.0, 0, 1)
                img.putalpha(Image.fromarray((a * ramp[None, :]).astype(np.uint8)))
            if alpha < 1.0:
                img = img.copy()
                img.putalpha(img.getchannel("A").point(lambda p, a_=alpha: int(p * a_)))
            paste(frame, img, x0, y0)

    def jolt_at(self, i, u):
        for el in self.elements[i]:
            if el.anim == "slam":
                v = u - el.at - 0.16
                if 0 <= v < 0.14:
                    amp = 7 * (1 - v / 0.14)
                    return (int(amp * math.sin(v * 90)), int(amp * math.cos(v * 70)))
        return (0, 0)

    def render(self, t, header=True, caption=True, stills=False):
        frame = self.base.copy()
        i = self.shot_at(t)
        shot = self.E.shots[i]
        u = t - shot["start"]
        wipe = self.E.breaks.get(i) if not stills else None
        # previous shot leaves upward, unless a torn-paper wipe covers the change
        if i > 0 and not wipe and u < PUSH and not stills:
            prev = self.E.shots[i - 1]
            self.draw_elements(frame, i - 1, prev["end"] - prev["start"], push=-H * ease_in_cubic(u / PUSH))
        self.draw_elements(frame, i, u, jolt=(0, 0) if stills else self.jolt_at(i, u), stills=stills)
        if header:
            frame.alpha_composite(self.header, (0, 0))
            self.timecode(frame, t)
        show_caption = caption and not any(isinstance(el, EndCard) and u >= el.at + 0.25 for el in self.elements[i])
        if show_caption:
            cap, body_h = self.caption(i, t)
            paste(frame, cap, 510 - cap.width / 2, 1262 + body_h / 2 - cap.height / 2)
        if header:
            self.crosshair(ImageDraw.Draw(frame), 50, 1530)
        # wipes: a torn sheet covers the frame around each chapter break
        for j, kind in self.E.breaks.items():
            b = self.E.shots[j]["start"]
            if b - WIPE_IN <= t <= b + WIPE_HOLD + WIPE_OUT and not stills:
                sheet = self.sheet(kind)
                if t < b:
                    x = W - (W + 120) * ease_in_out((t - (b - WIPE_IN)) / WIPE_IN)
                elif t < b + WIPE_HOLD:
                    x = -120
                else:
                    x = -120 - (W + 140) * ease_in_out((t - b - WIPE_HOLD) / WIPE_OUT)
                paste(frame, sheet, x - 40, -40)
        return frame.convert("RGB")

    # ---- the Instagram cover (post.cover in episode.json)
    def render_cover(self):
        cover = self.E.ep.get("post", {}).get("cover") or {}
        frame = self.base.copy()
        frame.alpha_composite(self.header, (0, 0))
        lines = cover.get("lines") or [self.E.ep.get("title", "")]
        ctx = {"paper": self.paper, "photos": {}, "seed": 4242}
        head = Headline({"lines": lines, "x": 80, "y": 600, "size": 300, "in": "none"}, ctx)
        art = head.art(10_000)
        paste(frame, art, 80 - 10, 600)
        if cover.get("stamp"):
            st = Stamp({"text": cover["stamp"], "x": 640, "y": 600 + art.height + 40, "rot": -6, "size": 92}, ctx)
            img = st.frame_image(10)
            paste(frame, img, 640 - img.width / 2, 600 + art.height + 40 - img.height / 2)
        return frame.convert("RGB")

    # ---- sound effects
    def events(self):
        ev = []
        for i, shot in enumerate(self.E.shots):
            if i > 0 and i not in self.E.breaks:
                ev.append(("whoosh_soft", shot["start"]))
            for el in self.elements[i]:
                for e in el.sounds(shot["start"] + el.at):
                    ev.append(e)
        for j in self.E.breaks:
            ev.append(("tear", self.E.shots[j]["start"] - WIPE_IN))
        return ev


def paste(frame, img, x, y):
    x, y = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x), max(0, -y)
    dx0, dy0 = max(0, x), max(0, y)
    w = min(img.width - sx0, W - dx0)
    h = min(img.height - sy0, H - dy0)
    if w <= 0 or h <= 0:
        return
    frame.alpha_composite(img.crop((sx0, sy0, sx0 + w, sy0 + h)), (dx0, dy0))


# ---------------------------------------------------------------- audio

def sfx_bank():
    rng = np.random.default_rng(11)

    def noise(n):
        return rng.normal(0, 1, n).astype(np.float32)

    def smooth(x, k):
        return np.convolve(x, np.ones(k, np.float32) / k, mode="same")

    def env(n, a, d):
        t = np.arange(n) / SR
        return np.minimum(1, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / d)

    bank = {}
    n = int(0.34 * SR)
    x = noise(n)
    x = smooth(x, 6) - smooth(x, 60)
    bank["whoosh"] = 0.22 * x * env(n, 0.07, 0.09)
    bank["whoosh_soft"] = 0.5 * bank["whoosh"]
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    f = 55 + 70 * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.07)
    click = smooth(noise(n), 3) * np.exp(-t / 0.008)
    bank["thud"] = (0.9 * body + 0.35 * click).astype(np.float32)
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    bank["pop"] = (0.3 * np.sin(2 * np.pi * 520 * t) * np.exp(-t / 0.025) + 0.15 * smooth(noise(n), 2) * np.exp(-t / 0.004)).astype(np.float32)
    n = int(0.55 * SR)
    x = noise(n)
    x = x - smooth(x, 12)
    crackle = (rng.random(n) < 0.02).astype(np.float32)
    crackle = smooth(crackle, 120) * 6
    bank["tear"] = (0.25 * x * np.clip(crackle, 0, 1) * env(n, 0.05, 0.3)).astype(np.float32)
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    bank["key"] = (0.25 * smooth(noise(n), 2) * np.exp(-t / 0.006)).astype(np.float32)
    n = int(0.07 * SR)
    t = np.arange(n) / SR
    bank["step"] = (0.11 * smooth(noise(n), 5) * np.exp(-t / 0.014)).astype(np.float32)   # a paper foot on the page
    return bank


def scribble(dur):
    rng = np.random.default_rng(int(dur * 1000))
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = rng.normal(0, 1, n).astype(np.float32)
    x = np.convolve(x, np.ones(8) / 8, mode="same") - np.convolve(x, np.ones(80) / 80, mode="same")
    return (0.07 * x * (0.55 + 0.45 * np.sin(2 * np.pi * 9 * t))).astype(np.float32)


def mix_audio(reel, out_wav):
    n = int((reel.E.length + 0.5) * SR)
    sfx = np.zeros(n, np.float32)
    bank = sfx_bank()
    for e in reel.events():
        clip = scribble(e[2]) if e[0] == "scribble" else bank[e[0]]
        i = int(e[1] * SR)
        if 0 <= i < n:
            m = min(len(clip), n - i)
            sfx[i:i + m] += clip[:m]
    voice = np.zeros(n, np.float32)
    if reel.E.voiced:
        for s in reel.E.shots:
            a = s["vo"]["audio"]
            rms = np.sqrt(np.mean(a ** 2)) or 1
            a = a * (0.1 / rms)
            i = int(s["vo"]["at"] * SR)
            if i < 0:                            # the first shot: the file's silence before the words starts before 0:00
                a, i = a[-i:], 0
            m = min(len(a), n - i)
            if m > 0:
                voice[i:i + m] += a[:m]
    music = np.zeros(n, np.float32)
    mfile = next((p for p in (reel.E.dir / "media" / "audio").glob("music.*")), None) if (reel.E.dir / "media" / "audio").exists() else None
    if mfile:
        m = decode_audio(mfile)[:n]
        rms = np.sqrt(np.mean(m ** 2)) or 1
        music[:len(m)] = m * (0.018 / rms)
        fade = int(1.5 * SR)
        music[max(0, len(m) - fade):len(m)] *= np.linspace(1, 0, min(fade, len(m)))
    mix = voice + sfx * (0.55 if reel.E.voiced else 0.8) + music
    peak = np.abs(mix).max() or 1
    if peak > 0.98:
        mix = mix * (0.98 / peak)
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype(np.int16).tobytes())


# ---------------------------------------------------------------- main

def build_video(reel, out, t0=0.0, t1=None):
    t1 = reel.E.length if t1 is None else min(t1, reel.E.length)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        silent = Path(tmp) / "video.mp4"
        proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "{}x{}".format(W, H),
                                 "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                                 "-pix_fmt", "yuv420p", str(silent)], stdin=subprocess.PIPE)
        n0, n1 = int(round(t0 * FPS)), int(round(t1 * FPS))
        for k in range(n0, n1):
            proc.stdin.write(reel.render(k / FPS).tobytes())
            if (k - n0) % (FPS * 10) == 0:
                print("  {:5.1f} s of {:.1f}".format(k / FPS, t1), flush=True)
        proc.stdin.close()
        if proc.wait():
            raise SystemExit("ffmpeg failed while encoding the video")
        wav = Path(tmp) / "mix.wav"
        mix_audio(reel, wav)
        trim = "atrim={}:{},asetpts=PTS-STARTPTS".format(t0, t1)
        norm = ""
        if reel.E.voiced:
            # Two passes, as ffmpeg's loudnorm needs to land on the target: measure, then apply exactly
            target = "I=-14:TP=-1.5:LRA=11"
            probe = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(wav), "-af",
                                    "{},loudnorm={}:print_format=json".format(trim, target), "-f", "null", "-"],
                                   capture_output=True, text=True).stderr
            m = json.loads(probe[probe.rindex("{"):probe.rindex("}") + 1])
            norm = (",loudnorm={}:measured_I={}:measured_TP={}:measured_LRA={}:measured_thresh={}:offset={}:linear=true"
                    .format(target, m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"], m["target_offset"]))
        af = ["-af", trim + norm]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"] + af +
                       ["-shortest", "-movflags", "+faststart", str(out)], check=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("episode")
    ap.add_argument("--out", help="output file (default: EPISODE/media/final/<episode>.mp4)")
    ap.add_argument("--frame", type=float, action="append", help="render one frame at this second (repeatable)")
    ap.add_argument("--stills", action="store_true", help="one clean still per shot in media/keyframes/")
    ap.add_argument("--check", action="store_true", help="only check reel.json against the episode")
    ap.add_argument("--cover", action="store_true", help="only the Instagram cover, media/final/cover.jpg")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float)
    ap.add_argument("--no-voice", action="store_true", help="ignore voice files and use the planned timing")
    ap.add_argument("--force", action="store_true", help="build even if reel.json has text problems")
    ap.add_argument("--if-changed", action="store_true",
                    help="do nothing when the reel is already built from these exact files")
    a = ap.parse_args()
    ep_dir = Path(a.episode)
    if a.if_changed:
        sys.path.insert(0, str(ROOT / "tools"))
        import dc
        video = Path(a.out) if a.out else ep_dir / "media" / "final" / "{}.mp4".format(ep_dir.resolve().name)
        try:
            built = json.loads((ep_dir / "build" / "timeline.json").read_text()).get("inputs")
        except (OSError, ValueError):
            built = None
        if video.exists() and built == dc.reel_inputs_hash(ep_dir):
            print("The reel is already built from these exact files: nothing to build.")
            return
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is needed")
    reel = Reel(ep_dir, use_voice=not a.no_voice)
    problems = reel.check_texts()
    hard = [p for p in problems if "placeholder" not in p]
    for p in problems:
        print(("FAIL · " if p in hard else "WARN · ") + p)
    print("Timing: {} ({:.1f} s, {} shots)".format("from the voice files" if reel.E.voiced else "planned, no voice yet",
                                                    reel.E.length, len(reel.E.shots)))
    if a.check:
        sys.exit(1 if hard else 0)
    if hard and not a.force:
        raise SystemExit("Fix reel.json first: every word on screen must come from the shot's card_text.")
    (ep_dir / "build").mkdir(exist_ok=True)
    sys.path.insert(0, str(ROOT / "tools"))
    import dc
    (ep_dir / "build" / "timeline.json").write_text(json.dumps({
        "inputs": dc.reel_inputs_hash(ep_dir),
        "voiced": reel.E.voiced, "length": round(reel.E.length, 3),
        "shots": [{"id": s["id"], "start": round(s["start"], 3), "end": round(s["end"], 3),
                   "handwritten": [t for el in reel.elements[i] for t in el.handwritten()],
                   "screens": [[round(v) for v in el.frame_box()] for el in reel.elements[i]
                               if isinstance(el, Screen) and not el.out]}
                  for i, s in enumerate(reel.E.shots)]},
        indent=1) + "\n")
    if a.cover:
        p = ep_dir / "media" / "final" / "cover.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        reel.render_cover().save(p, quality=92)
        print("cover", p)
        return
    if a.frame:
        for t in a.frame:
            p = ep_dir / "build" / "frame-{:06.2f}.png".format(t)
            reel.render(t).save(p)
            print("frame", p)
        return
    if a.stills:
        kdir = ep_dir / "media" / "keyframes"
        kdir.mkdir(parents=True, exist_ok=True)
        for i, s in enumerate(reel.E.shots):
            p = kdir / "{}.png".format(s["id"])
            reel.render(s["end"] - 0.05, header=False, caption=False, stills=True).save(p)
            print("still", p)
        return
    out = Path(a.out) if a.out else ep_dir / "media" / "final" / "{}.mp4".format(ep_dir.name)
    print("Building", out)
    build_video(reel, out, a.t0, a.t1)
    print("Done:", out, "({:.1f} s)".format(probe_duration(out)))
    if not a.out:
        cover = out.parent / "cover.jpg"
        reel.render_cover().save(cover, quality=92)
        print("Cover:", cover)


if __name__ == "__main__":
    main()
