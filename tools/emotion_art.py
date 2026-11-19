"""What a line's feeling looks like on screen (tools/emotion.py says which feeling has which): the mark by the
speaker's head, the speech bubble's edge, and the speaker's small move. Used by the Host engine (build_host.py),
so the Host and Chatur Kauwa reels both have it.

Everything here is small on purpose: the voice carries the feeling, the picture only nods to it.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw

INK = (26, 26, 26)
LEMON = (245, 238, 48)
RED = (214, 64, 52)
SKY = (126, 200, 255)
CLOUD = (168, 178, 200)
ROSE = (238, 86, 112)
SOFT_BLUE = (104, 134, 182)
MUTED = (150, 144, 135)

HEADROOM = {"spiky": 22, "pop": 26}   # how far a bubble style draws above its box: the bubble keeps that clear too
SHOW = 2.6            # seconds a mark stays by the head (it pops in, does its little loop, then fades)
POP_IN, FADE = 0.2, 0.3
SS = 3                # marks are drawn this many times bigger, then scaled down: smooth edges


def ease_out_back(p, s=1.7):
    p = min(1.0, max(0.0, p)) - 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def envelope(u, length):
    """(scale, opacity) of a mark u seconds into its line, for a line this many seconds long."""
    end = min(SHOW, max(0.8, length - 0.1))
    if u < 0 or u > end:
        return 0.0, 0.0
    scale = ease_out_back(u / POP_IN)
    fade = min(1.0, (end - u) / FADE)
    return scale, max(0.0, fade)


# ---------------------------------------------------------------- the marks

def _w(x):
    return max(1, int(round(x)))


def _sparkle(d, cx, cy, r, fill=LEMON, line=None):
    k = r * 0.3
    pts = [(cx, cy - r), (cx + k, cy - k), (cx + r, cy), (cx + k, cy + k), (cx, cy + r), (cx - k, cy + k),
           (cx - r, cy), (cx - k, cy - k)]
    d.polygon(pts, fill=fill, outline=INK, width=_w(line or r * 0.16))


def _stroke(d, pts, colour, width):
    """A line with a dark edge, so it reads on a light page and on the dark board."""
    d.line(pts, fill=INK, width=_w(width * 1.7), joint="curve")
    d.line(pts, fill=colour, width=_w(width), joint="curve")


def _drop(d, cx, cy, r, fill=SKY):
    """A drop: round at the bottom, pointed at the top."""
    pts = [(cx, cy - r * 1.7)]
    for k in range(0, 181, 12):
        a = math.radians(k)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=fill, outline=INK, width=_w(r * 0.22))
    d.ellipse([cx - r * 0.45, cy - r * 0.2, cx - r * 0.1, cy + r * 0.25], fill=(235, 246, 255))


def _heart(d, cx, cy, r, fill=ROSE):
    pts = []
    for k in range(0, 360, 6):
        t = math.radians(k)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * r / 17, cy - y * r / 17))
    d.polygon(pts, fill=fill, outline=INK, width=_w(r * 0.14))
    d.ellipse([cx - r * 0.62, cy - r * 0.55, cx - r * 0.3, cy - r * 0.25], fill=(255, 200, 210))


def _note(d, cx, cy, r):
    """An eighth note: the head at (cx, cy)."""
    hw, hh = r * 0.42, r * 0.32
    stem_x = cx + hw * 0.85
    _stroke(d, [(stem_x, cy - hh * 0.2), (stem_x, cy - r * 1.45)], LEMON, r * 0.14)
    _stroke(d, [(stem_x, cy - r * 1.45), (stem_x + r * 0.42, cy - r * 1.05), (stem_x + r * 0.3, cy - r * 0.7)],
            LEMON, r * 0.14)
    d.ellipse([cx - hw, cy - hh, cx + hw, cy + hh], fill=LEMON, outline=INK, width=_w(r * 0.13))


def _bang(d, cx, cy, r):
    top, bottom = cy - r, cy + r * 0.38
    d.polygon([(cx - r * 0.22, top), (cx + r * 0.22, top), (cx + r * 0.11, bottom), (cx - r * 0.11, bottom)],
              fill=RED, outline=INK, width=_w(r * 0.11))
    dot = r * 0.17
    d.ellipse([cx - dot, cy + r * 0.62 - dot, cx + dot, cy + r * 0.62 + dot], fill=RED, outline=INK, width=_w(r * 0.1))
    for side in (-1, 1):                                  # the little lines a shock gives off
        for k, a in enumerate((-30, 0, 30)):
            ang = math.radians(a)
            x0, y0 = cx + side * r * 0.5, cy - r * 0.35 + math.sin(ang) * r * 0.5
            x1, y1 = x0 + side * r * 0.32 * math.cos(ang), y0 + r * 0.32 * math.sin(ang)
            _stroke(d, [(x0, y0), (x1, y1)], LEMON, r * 0.08)


def _question(img, cx, cy, r, angle):
    import build_reel as B
    size = int(r * 2.3)
    f = B.font("anton", size)
    box = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    ImageDraw.Draw(box).text((size, size), "?", font=f, fill=LEMON, anchor="mm", stroke_width=_w(r * 0.13),
                             stroke_fill=INK)
    box = box.rotate(angle, resample=Image.BICUBIC)
    img.alpha_composite(box, (int(cx - size), int(cy - size)))


def _cloud(d, cx, cy, r, u):
    puffs = [(-0.48, 0.05, 0.36), (0.0, -0.2, 0.5), (0.46, 0.04, 0.38)]
    edge = r * 0.1
    for px, py, pr in puffs:                              # the outline first, then the body over it
        d.ellipse([cx + (px - pr) * r - edge, cy + (py - pr) * r - edge, cx + (px + pr) * r + edge,
                   cy + (py + pr) * r + edge], fill=INK)
    d.rounded_rectangle([cx - 0.84 * r - edge, cy - 0.05 * r, cx + 0.84 * r + edge, cy + 0.36 * r + edge],
                        radius=r * 0.2, fill=INK)
    for px, py, pr in puffs:
        d.ellipse([cx + (px - pr) * r, cy + (py - pr) * r, cx + (px + pr) * r, cy + (py + pr) * r], fill=CLOUD)
    d.rounded_rectangle([cx - 0.84 * r, cy - 0.02 * r, cx + 0.84 * r, cy + 0.36 * r], radius=r * 0.18, fill=CLOUD)
    for k, x in enumerate((-0.42, 0.02, 0.44)):            # rain, falling and starting again
        p = (u * 1.4 + k * 0.37) % 1.0
        y0 = cy + r * (0.5 + 0.55 * p)
        _stroke(d, [(cx + x * r, y0), (cx + x * r - r * 0.05, y0 + r * 0.22)], SKY, r * 0.08)


def _vein(d, cx, cy, r):
    """The cross-shaped mark of anger: four curves bulging towards the middle."""
    for sx in (-1, 1):
        for sy in (-1, 1):
            ox, oy = cx + sx * r * 0.78, cy + sy * r * 0.78
            rad = r * 0.62
            start = math.degrees(math.atan2(-sy, -sx))
            box = [ox - rad, oy - rad, ox + rad, oy + rad]
            d.arc(box, start - 42, start + 42, fill=INK, width=_w(r * 0.3))
            d.arc(box, start - 38, start + 38, fill=RED, width=_w(r * 0.19))


def _scribble(d, cx, cy, r, seed):
    rnd = random.Random(seed)
    pts = []
    for k in range(26):
        a = k * 2.4 + rnd.uniform(-0.4, 0.4)
        rr = r * (0.35 + 0.55 * rnd.random())
        pts.append((cx + rr * math.cos(a), cy + rr * 0.8 * math.sin(a)))
    _stroke(d, pts, RED, r * 0.09)


def _siren(d, cx, cy, r, u):
    """A blinking alarm: a red light with rings going out from it."""
    on = int(u * 4) % 2 == 0
    dot = r * 0.26
    d.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill=RED if on else (150, 52, 44), outline=INK,
              width=_w(r * 0.1))
    for k in range(3):
        p = (u * 1.6 + k / 3) % 1.0
        rad = r * (0.4 + 0.7 * p)
        if p > 0.85:
            continue
        for start in (-40, 140):
            box = [cx - rad, cy - rad, cx + rad, cy + rad]
            d.arc(box, start, start + 80, fill=INK, width=_w(r * 0.15))
            d.arc(box, start + 3, start + 77, fill=LEMON, width=_w(r * 0.08))


@lru_cache(maxsize=4096)
def mark(kind, u, size):
    """The mark for a feeling, u seconds into its line (rounded to a frame), about size pixels across.
    Its middle is the image's middle."""
    side = int(size * 2.2)
    big = side * SS
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r = big / 2, size * SS / 2
    if kind == "burst":
        for k, (x, y, s) in enumerate(((-0.45, 0.1, 0.62), (0.4, -0.5, 0.44), (0.5, 0.45, 0.34))):
            tw = 0.7 + 0.3 * math.sin(2 * math.pi * u * 1.6 + k * 2.1)
            _sparkle(d, c + x * r, c + y * r, r * s * tw, line=r * 0.09)
    elif kind == "sparkle":
        for k, (x, y, s) in enumerate(((-0.25, 0.1, 0.55), (0.45, -0.45, 0.34))):
            tw = 0.7 + 0.3 * math.sin(2 * math.pi * u * 1.3 + k * 2.6)
            _sparkle(d, c + x * r, c + y * r, r * s * tw, line=r * 0.09)
    elif kind == "notes":
        for k, (x, y) in enumerate(((-0.42, 0.45), (0.4, 0.2))):
            bob = 0.1 * r * math.sin(2 * math.pi * u / 0.8 + k * math.pi)
            _note(d, c + x * r, c + y * r + bob, r * 0.62)
    elif kind == "bang":
        _bang(d, c, c, r)
    elif kind == "question":
        _question(img, c, c, r, 9 * math.sin(2 * math.pi * u / 1.3))
    elif kind == "pulse":
        _siren(d, c, c, r, u)
    elif kind == "sweat":
        for k, (x, s) in enumerate(((-0.15, 0.36), (0.38, 0.24))):
            p = (u / 1.3 + k * 0.45) % 1.0
            _drop(d, c + x * r, c - 0.25 * r + 0.55 * r * p, r * s)
    elif kind == "cloud":
        _cloud(d, c, c - 0.2 * r, r * 0.95, u)
    elif kind == "scribble":
        _scribble(d, c, c, r, int(u / 0.14))
    elif kind == "vein":
        s = 1 + 0.12 * abs(math.sin(2 * math.pi * u * 1.6))
        _vein(d, c, c, r * 0.62 * s)
    elif kind == "heart":
        s = 1 + 0.08 * math.sin(2 * math.pi * u / 0.9)
        _heart(d, c, c, r * 0.8 * s)
    return img.resize((side, side), Image.LANCZOS)


def place(ax, ay, x, scale, width):
    """Where a mark goes for an avatar whose face is at (ax, ay), standing at x and drawn at this scale: beside the
    head, on the side away from the middle (where the cards, the bubble and the other avatar are)."""
    k = scale / 0.7
    side = -1 if x < width / 2 - 1 else 1
    return ax + side * 182 * k, ay - 132 * k


# ---------------------------------------------------------------- the speaker's move

def move(kind, u):
    """(dx, dy, zoom) for the speaker u seconds into a line: a hop when excited, a jump when surprised, a shake when
    angry, a tremble when worried, a droop when sad, leaning in when sure or curious, a nod when warm."""
    if u < 0:
        return 0.0, 0.0, 1.0
    if kind == "hop" and u < 0.72:
        return 0.0, -22 * abs(math.sin(math.pi * u / 0.36)) * (1 - 0.4 * u / 0.72), 1.0
    if kind == "jump" and u < 0.42:
        p = math.sin(math.pi * u / 0.42)
        return 0.0, -34 * p, 1 + 0.03 * p
    if kind == "shake" and u < 0.6:
        return 9 * math.sin(2 * math.pi * u * 8) * (1 - u / 0.6), 0.0, 1.0
    if kind == "tremble":
        return 2.2 * math.sin(2 * math.pi * u * 9), 0.0, 1.0
    if kind == "droop":
        p = min(1.0, u / 0.6)
        return 0.0, 14 * (3 * p * p - 2 * p ** 3), 1.0
    if kind == "lean":
        p = min(1.0, u / 0.5)
        return 0.0, 0.0, 1 + 0.025 * (3 * p * p - 2 * p ** 3)
    if kind == "nod" and u < 1.0:
        return 0.0, 6 * math.sin(2 * math.pi * u / 0.5) * (1 - u), 1.0
    return 0.0, 0.0, 1.0


# ---------------------------------------------------------------- the bubble's edge

def bubble_edge(d, style, box, radius, colour_for_angry=False, ink=INK, accent=LEMON):
    """Draw a speech bubble's body for a feeling's bubble style: "plain" and "pop" a white box with the reel's ink
    edge, "soft" a blue-grey edge (sad, worried), "spiky" points all round its top and sides (red when angry), "dashed"
    a broken grey edge (a whisper). box is [x0, y0, x1, y1] inside the bubble's image, with room around it. Returns the
    edge's colour, for the tail."""
    x0, y0, x1, y1 = box
    if style == "spiky":
        colour = RED if colour_for_angry else ink
        step, out = 34, 20
        spikes = []
        x = x0 + radius
        while x < x1 - radius:                                 # along the top
            spikes.append([(x, y0 + 4), (x + step / 2, y0 - out), (x + step, y0 + 4)])
            x += step
        y = y0 + radius
        while y < y1 - radius:                                 # down both sides
            spikes.append([(x0 + 4, y), (x0 - out, y + step / 2), (x0 + 4, y + step)])
            spikes.append([(x1 - 4, y), (x1 + out, y + step / 2), (x1 - 4, y + step)])
            y += step
        for tri in spikes:
            d.polygon(tri, fill=(255, 255, 255), outline=colour, width=5)
        d.rounded_rectangle(box, radius=radius, fill=(255, 255, 255), outline=colour, width=5)
        return colour
    if style == "soft":
        d.rounded_rectangle(box, radius=radius, fill=(255, 255, 255), outline=SOFT_BLUE, width=5)
        return SOFT_BLUE
    if style == "dashed":
        d.rounded_rectangle(box, radius=radius, fill=(255, 255, 255))
        dash, gap = 16, 11
        for (ax, ay), (bx, by) in (((x0 + radius, y0), (x1 - radius, y0)), ((x0 + radius, y1), (x1 - radius, y1)),
                                   ((x0, y0 + radius), (x0, y1 - radius)), ((x1, y0 + radius), (x1, y1 - radius))):
            length = math.hypot(bx - ax, by - ay)
            n = 0.0
            while n < length:
                e = min(length, n + dash)
                d.line([(ax + (bx - ax) * n / length, ay + (by - ay) * n / length),
                        (ax + (bx - ax) * e / length, ay + (by - ay) * e / length)], fill=MUTED, width=4)
                n += dash + gap
        for cx, cy, start in ((x0 + radius, y0 + radius, 180), (x1 - radius, y0 + radius, 270),
                              (x1 - radius, y1 - radius, 0), (x0 + radius, y1 - radius, 90)):
            d.arc([cx - radius, cy - radius, cx + radius, cy + radius], start + 20, start + 70, fill=MUTED, width=4)
        return MUTED
    d.rounded_rectangle(box, radius=radius, fill=(255, 255, 255), outline=ink, width=5)
    if style == "pop":                                         # a few lines bursting off the top corners
        for cx, side in ((x0 + 6, -1), (x1 - 6, 1)):
            for a in (-60, -35, -10):
                ang = math.radians(a)
                p0 = (cx + side * 8 * math.cos(ang), y0 + 8 * math.sin(ang))
                p1 = (cx + side * 26 * math.cos(ang), y0 + 26 * math.sin(ang))
                d.line([p0, p1], fill=ink, width=8)
                d.line([p0, p1], fill=accent, width=4)
    return ink


def pop(u):
    """How big a "pop" bubble is u seconds into its line: it bounces in."""
    if u >= 0.32:
        return 1.0
    return max(0.2, ease_out_back(u / 0.32, 2.2))
