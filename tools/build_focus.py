#!/usr/bin/env python3
"""Focus: how to do something on a website or in an app, shown on the screen itself (styles/focus/STYLE.md).
tools/build_reel.py builds an episode in this style when its episode.json says "style": "focus".

- A clean white board. The screen is the reel: as big as Instagram's own overlays allow (ZONE). A website opens in a
  MacBook as wide as the frame, and the camera moves over the page inside its screen, to each part as its line names
  it; a phone shows whole.
- Focus mode: the part being used lifts out of the screen, big and sharp, while the rest goes soft and pale; a touch
  (phone) or a cursor (laptop) taps beside its words, never on them; the screen answers (a toggle flips, a sheet slides
  up, words type themselves, a message confirms).
- Screens are drawn from Muse's description (tools/screens.py), after the newest official pages and tutorials: never
  someone else's screenshot. A screenshot GitHub takes itself on a public tool can be used as it is ("src").
- Between the screens, the idea behind them: the whole route first (route), what happens behind the screen, the
  mistake and then the fix (flow), and a checklist worth saving (checklist).
- The words: the spoken line, two lines at most, under the screen and left of Instagram's buttons. The logo and the
  route share the row over the screen. Nothing that matters goes where Instagram draws its own things.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

import build_host as Hs
import build_reel as B
import screens as K

W, H, FPS = B.W, B.H, B.FPS
ZONE = (24, 316, 1056, 1500)         # the screen: under the logo row, over the words
HOOK_ZONE = (24, 660, 1056, 1500)    # under the hook's giant words
SAFE_L, SAFE_R = 60, 930             # Instagram's buttons run down the right edge, from about y 1100
CAP_Y = 1612                         # the words' baseline, one line (two: 1578 and 1642)
CAP_SIZE = 54
READABLE = 34                        # px: the smallest body text a part being used may show
LEMON, INK, WHITE = B.LEMON, B.INK, (255, 255, 255)
GREEN, RED, BLUE = (52, 199, 89), (255, 69, 58), (10, 132, 255)
# A clean white board (PF Guru Ji): ink words, grey for what's not yet, lemon for what's now
TEXT, MUTED, FAINT, HAIR = (26, 26, 28), (110, 110, 118), (152, 152, 160), (226, 226, 232)
CHIP_OFF, CHIP_OFF_TEXT = (236, 236, 241), (140, 140, 150)
# The MacBook a laptop page opens on, in points (its screen is the page's 1280 x 800): the lid with its aluminium rim
# and black bezel, the hinge, and the base, wider than the lid
MAC_W, MAC_H = 1492.0, 878.0
MAC_LID = (86.0, 0.0, 1406.0, 844.0)
MAC_SCREEN = (106.0, 24.0, 1386.0, 824.0)
MAC_SIDE = 12                        # px between the MacBook and the frame's edges
FADE = 0.28                          # a card takes the screen's place with a short cross-fade
LIFT_IN, LIFT_OUT = 0.42, 0.3
REACH = 0.6                          # the pointer travels this long to its target before the tap
TYPE_STEP = 0.075                    # one character typed
SHOW = 0.5                           # what a touch did stays in view this long before the pointer moves on
GLIDE = 0.6                          # the camera's move from one framing to the next
LAND = 1.0                           # a page that opens is shown whole this long before the camera moves on
LOOK = 0.5                           # the camera's way to a part a line only looks at
PHONE_ZOOM = 1.5                     # how much closer a phone comes when the camera goes to one of its parts


def smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def spring(u):
    u = min(max(u, 0.0), 1.0)
    c1 = 1.5
    return 1 + (c1 + 1) * (u - 1) ** 3 + c1 * (u - 1) ** 2


def lerp(a, b, u):
    return a + (b - a) * u


def blend_view(a, b, u):
    """A camera framing between two (x, y, w, h): the middle moves straight, the size changes evenly (geometrically),
    so a zoom in and a zoom out feel the same."""
    (ax, ay, aw, ah), (bx, by, bw, bh) = a, b
    w = math.exp(lerp(math.log(max(aw, 1e-6)), math.log(max(bw, 1e-6)), u))
    h = math.exp(lerp(math.log(max(ah, 1e-6)), math.log(max(bh, 1e-6)), u))
    mx, my = lerp(ax + aw / 2, bx + bw / 2, u), lerp(ay + ah / 2, by + bh / 2, u)
    return (mx - w / 2, my - h / 2, w, h)


def ring_round(frame, box, alpha=1.0, clip=None):
    """A lemon ring round a part of the page, faded in by alpha. clip: the frame box it stays inside (a MacBook's
    screen): the ring is on the page, so a part wider than the glass has its ring cut where the glass ends."""
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    pad = 6
    x0c, y0c, x1c, y1c = max(0, x0 - pad), max(0, y0 - pad), min(W, x1 + pad), min(H, y1 + pad)
    if clip:
        x0c, y0c = max(x0c, int(math.ceil(clip[0]))), max(y0c, int(math.ceil(clip[1])))
        x1c, y1c = min(x1c, int(clip[2])), min(y1c, int(clip[3]))
    if x1c <= x0c or y1c <= y0c:
        return
    ov = Image.new("RGBA", (x1c - x0c, y1c - y0c), (0, 0, 0, 0))
    a = int(255 * max(0.0, min(1.0, alpha)))
    od = ImageDraw.Draw(ov)
    od.rounded_rectangle([x0 - x0c, y0 - y0c, x1 - x0c, y1 - y0c], 16, outline=INK + (a,), width=8)
    od.rounded_rectangle([x0 - x0c + 2, y0 - y0c + 2, x1 - x0c - 2, y1 - y0c - 2], 14, outline=LEMON + (a,), width=4)
    frame.alpha_composite(ov, (x0c, y0c))


@lru_cache(maxsize=1)
def board():
    """A clean white board, a breath of grey towards the bottom so the MacBook stands on something."""
    yy = np.mgrid[0:H, 0:W][0]
    shade = np.clip((yy - 1100) / 820.0, 0, 1) ** 2 * 7
    arr = np.repeat((255 - shade)[:, :, None], 3, axis=2)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


def macbook_rect(zone):
    """Where the MacBook sits for a zone: (points to px, its box, its screen's box), in frame pixels. As wide as the
    frame allows, in the middle of the zone."""
    zx0, zy0, zx1, zy1 = zone
    width = W - 2 * MAC_SIDE
    u = width / MAC_W
    top = (zy0 + zy1) / 2 - MAC_H * u / 2
    dev = (MAC_SIDE, top, MAC_SIDE + width, top + MAC_H * u)
    scr = (MAC_SIDE + MAC_SCREEN[0] * u, top + MAC_SCREEN[1] * u, MAC_SIDE + MAC_SCREEN[2] * u,
           top + MAC_SCREEN[3] * u)
    return u, dev, scr


@lru_cache(maxsize=4)
def macbook_body(width_px):
    """The MacBook drawn width_px wide, its screen black (the page goes on it), with its soft shadow under it: RGBA,
    30 points taller than the MacBook for the shadow."""
    k = 2.0                                                        # drawn twice as big, then shrunk: smooth edges
    u = width_px / MAC_W * k
    w, h = int(round(MAC_W * u)), int(round((MAC_H + 30) * u))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).ellipse([70 * u, (MAC_H - 12) * u, (MAC_W - 70) * u, (MAC_H + 14) * u], fill=120)
    img.paste((0, 0, 0, 255), mask=sh.filter(ImageFilter.GaussianBlur(9 * u)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 852 * u, w - 1, MAC_H * u], radius=int(12 * u), fill=(186, 188, 193))   # the base's front
    d.rounded_rectangle([0, 866 * u, w - 1, MAC_H * u], radius=int(12 * u), fill=(166, 168, 173))
    d.rounded_rectangle([3 * u, 849 * u, w - 3 * u, 858 * u], radius=int(4 * u), fill=(224, 225, 229))  # its top
    d.rounded_rectangle([(MAC_W / 2 - 96) * u, 852 * u, (MAC_W / 2 + 96) * u, 859 * u], radius=int(5 * u),
                        fill=(198, 200, 205))                                                       # the thumb notch
    d.rectangle([(MAC_LID[0] + 46) * u, 840 * u, (MAC_LID[2] - 46) * u, 850 * u], fill=(54, 55, 60))  # the hinge
    d.rounded_rectangle([MAC_LID[0] * u, MAC_LID[1] * u, MAC_LID[2] * u, MAC_LID[3] * u], radius=int(28 * u),
                        fill=(200, 202, 207), corners=(True, True, False, False))                  # the lid's rim
    d.rounded_rectangle([(MAC_LID[0] + 2.5) * u, (MAC_LID[1] + 2.5) * u, (MAC_LID[2] - 2.5) * u,
                         (MAC_LID[3] - 1) * u], radius=int(26 * u), fill=(13, 13, 15),
                        corners=(True, True, False, False))                                         # the bezel
    d.rectangle([MAC_SCREEN[0] * u, MAC_SCREEN[1] * u, MAC_SCREEN[2] * u, MAC_SCREEN[3] * u], fill=(0, 0, 0))
    cx = (MAC_LID[0] + MAC_LID[2]) / 2 * u
    d.ellipse([cx - 3.4 * u, 9 * u, cx + 3.4 * u, 15.8 * u], fill=(34, 34, 38))                     # the camera
    d.ellipse([cx - 1.4 * u, 11 * u, cx + 1.4 * u, 13.8 * u], fill=(58, 62, 84))
    return img.resize((int(round(w / k)), int(round(h / k))), Image.LANCZOS)


def wrap_caption(words, size=CAP_SIZE, width=SAFE_R - SAFE_L, avoid=()):
    """Words as one line, or two balanced lines (not broken before a word index in avoid when another break fits),
    or None when two lines can't hold them."""
    if B.text_width(" ".join(words), "caption", size, 0) <= width:
        return [words]
    best = None
    for k in range(1, len(words)):
        a = B.text_width(" ".join(words[:k]), "caption", size, 0)
        b = B.text_width(" ".join(words[k:]), "caption", size, 0)
        if max(a, b) <= width:
            key = (k in avoid, max(a, b) - (120 if words[k - 1][-1:] in ".?!।,;:" else 0))
            if best is None or key < best[0]:
                best = (key, k)
    return None if best is None else [words[:best[1]], words[best[1]:]]


def paginate(words, keep=(), times=None, size=CAP_SIZE):
    """A line's words as pages of one or two lines: [[[word index]]]. As few pages as fit; a page ends where the
    voice pauses (. ? ! , ।) rather than mid-phrase, never inside a name the screen shows (keep: sets of word indexes
    that belong together, "Set up with a partner"), never with one or two lonely words, never so short it flashes."""
    n = len(words)
    if n == 0:
        return []
    inside = {k for g in keep for k in g if k - 1 in g}          # a break before word k would split a name
    fits = {}

    def ok(a, b):
        if (a, b) not in fits:
            fits[(a, b)] = wrap_caption(words[a:b], size) is not None
        return fits[(a, b)]

    def cut(k):                                                  # a page that starts at word k
        if k == 0:
            return 0.0
        end = words[k - 1][-1:]
        return (0.0 if end in ".?!।" else 1.0 if end in ",;:" else 3.0) + (20.0 if k in inside else 0.0)

    def short(a, b):
        c = 4.0 if b - a <= 2 and n > 3 else 0.0
        if times is not None and times[b - 1][1] - times[a][0] < 0.8:
            c += 3.0
        return c
    best, back = [0.0] + [None] * n, [0] * (n + 1)
    for b in range(1, n + 1):
        for a in range(b):
            if best[a] is None or not ok(a, b):
                continue
            c = best[a] + 10.0 + cut(a) + short(a, b)
            if best[b] is None or c < best[b]:
                best[b], back[b] = c, a
    if best[n] is None:                                          # a word too long for the width: one word a page
        bounds = [(k, k + 1) for k in range(n)]
    else:
        bounds, b = [], n
        while b > 0:
            bounds.append((back[b], b))
            b = back[b]
        bounds.reverse()
    pages = []
    for a, b in bounds:
        lines = wrap_caption(words[a:b], size, avoid={k - a for k in inside if a < k < b}) or [words[a:b]]
        idx, pos = [], a
        for line in lines:
            idx.append(list(range(pos, pos + len(line))))
            pos += len(line)
        pages.append(idx)
    return pages


# ---------------------------------------------------------------- cards

class Card:
    """A card in the zone: full cards (route, flow, checklist, outro) take the screen's place for their shot; the
    headline sits over the screen on the hook."""
    full = True
    handwritten = False

    def __init__(self, spec, ctx):
        self.spec, self.ctx = spec, ctx
        self.at = float(spec.get("at", 0.0))

    def texts(self):
        return []

    def sounds(self, t0):
        return []

    def draw(self, frame, u, reel, i):
        pass


def fit_size(text, key, size, width, least=24):
    while size > least and B.text_width(text, key, size, 0) > width:
        size -= 2
    return size


class Headline(Card):
    """The hook in giant words over the screen: two lines at most, the accent on a lemon block."""
    full = False

    def lines(self):
        text = str(self.spec.get("text", "")).strip()
        if "\n" in text:
            return [x.strip() for x in text.split("\n") if x.strip()]
        accent = str(self.spec.get("accent", "")).strip()
        if accent and accent in text and accent != text:     # the accent on a line of its own: one lemon block
            head, tail = text.split(accent, 1)
            parts = [x.strip() for x in (head, accent, tail) if x.strip()]
            if len(parts) == 2:
                return parts
        words = text.split()
        if B.text_width(text, "anton", 116, 0) <= 960 or len(words) < 2:
            return [text]
        k = min(range(1, len(words)), key=lambda k: max(B.text_width(" ".join(words[:k]), "anton", 116, 0),
                                                       B.text_width(" ".join(words[k:]), "anton", 116, 0)))
        return [" ".join(words[:k]), " ".join(words[k:])]

    def texts(self):
        return [" ".join(self.lines())]

    def sounds(self, t0):
        return [("thud", max(0.02, t0))]

    def draw(self, frame, u, reel, i):
        if u < 0:
            return
        d = ImageDraw.Draw(frame)
        accent = str(self.spec.get("accent", "")).strip()
        lines = self.lines()
        y = 430 if len(lines) == 2 else 520
        a = 1.0 if self.spec.get("in") == "none" else smooth(u / 0.18)    # "in": "none": whole on the first frame
        for k, line in enumerate(lines):
            size = fit_size(line, "anton", 116, 960, 60)
            lit = accent and (accent in line or line in accent)
            tw = B.text_width(line, "anton", size, 0)
            if lit:                                         # the block sits around the letters themselves
                top, bot = B.ink_box(line, "anton", size)
                d.rectangle([(W - tw) / 2 - 28, y + top - 14, (W + tw) / 2 + 28, y + bot + 18],
                            fill=LEMON + (int(255 * a),))
            B.draw_text(frame, (W - tw) / 2, y, line, "anton", size, INK if lit else TEXT, 0)
            y += size + 30                                  # room between the lines: on white, a lemon block that
                                                            # touches the line above reads as one blur (and OCR agrees)


class Route(Card):
    """The whole route before its steps: numbered stops, the ones done ticked, the one we're on in lemon."""

    def items(self):
        return [it if isinstance(it, dict) else {"text": it} for it in self.spec.get("steps") or []]

    def texts(self):
        out = [self.spec["title"]] if self.spec.get("title") else []
        for it in self.items():
            out.append(it.get("text", ""))
            if it.get("sub"):
                out.append(it["sub"])
        return out

    def sounds(self, t0):
        return [("whoosh_soft", t0)] + [("pop", t0 + 0.25 + 0.18 * k) for k in range(len(self.items()))]

    def draw(self, frame, u, reel, i):
        d = ImageDraw.Draw(frame)
        items = self.items()
        now = int(self.spec.get("now", 0))
        title = self.spec.get("title")
        step = min(220, (ZONE[3] - ZONE[1] - (190 if title else 60)) / max(1, len(items)))
        block = (150 if title else 0) + step * len(items)
        y = (ZONE[1] + ZONE[3]) / 2 - block / 2               # the whole route sits in the middle of the zone
        if title:
            B.draw_text(frame, (W - B.text_width(title, "anton", 88, 0)) / 2, y + 88, title, "anton", 88, TEXT, 0)
            y += 150
        r = min(44, step * 0.24)
        for k, it in enumerate(items):
            a = smooth((u - 0.2 - 0.18 * k) / 0.3)
            if a <= 0:
                continue
            cy = y + k * step + step / 2
            col = GREEN if k < now else (LEMON if k == now else CHIP_OFF)
            d.ellipse([194 - r, cy - r, 194 + r, cy + r], fill=col)
            if k < now:
                K.tick_mark(d, 194 / 1.0, cy, 1.0, WHITE, 2.3 * r / 44)
            else:
                n = str(k + 1)
                B.draw_text(frame, 194 - B.text_width(n, "anton", 50, 0) / 2, cy + 20, n, "anton", 50,
                            INK if k == now else CHIP_OFF_TEXT, 0)
            if k < len(items) - 1:
                d.line([(194, cy + r + 4), (194, cy + step - r - 4)], fill=HAIR, width=6)
            sub = it.get("sub")
            B.draw_text(frame, 280, cy + (8 if sub else 24), it.get("text", ""), "anton",
                        fit_size(it.get("text", ""), "anton", 66, SAFE_R - 290), TEXT if k <= now else FAINT, 0)
            if sub:
                B.draw_text(frame, 282, cy + 54, sub, "caption", fit_size(sub, "caption", 32, SAFE_R - 290),
                            MUTED, 0)


class Flow(Card):
    """What happens behind the screen: up to three senders, one receiver, the data on its way, and what the receiver
    makes of it (the mistake in red, the fix in green)."""

    def texts(self):
        out = []
        for n in (self.spec.get("from") or []) + [self.spec.get("to") or {}]:
            out += [x for x in (n.get("title"), n.get("sub")) if x]
        out += [p.get("text", "") for p in self.spec.get("pills") or []]
        r = self.spec.get("result") or {}
        out += [x for x in (r.get("text"), r.get("sub")) if x]
        return [x for x in out if x]

    def sounds(self, t0):
        ev = [("whoosh_soft", t0)]
        for p in self.spec.get("pills") or []:
            ev.append(("plop", t0 + float(p.get("at", 0.4)) + 0.7))
        r = self.spec.get("result") or {}
        if r:
            ev.append(("thud" if r.get("tone") == "bad" else "sparkle", t0 + float(r.get("at", 1.2))))
        return ev

    def node(self, frame, box, title, sub, ring=None):
        Card_box(frame, box, ring=ring)
        x0, y0, x1, y1 = box
        cx = (x0 + x1) / 2
        tsz = fit_size(title, "caption", 42, x1 - x0 - 30)
        B.draw_text(frame, cx - B.text_width(title, "caption", tsz, 0) / 2, y0 + (70 if sub else 98), title, "caption",
                    tsz, K.TXT, 0)
        if sub:
            sz = fit_size(sub, "caption", 30, x1 - x0 - 30)
            B.draw_text(frame, cx - B.text_width(sub, "caption", sz, 0) / 2, y0 + 122, sub, "caption", sz, K.SUB, 0)

    def draw(self, frame, u, reel, i):
        """Senders on the left, the receiver on the right, its result under it: the whole diagram in the middle of
        the zone, and left of Instagram's buttons."""
        d = ImageDraw.Draw(frame)
        senders = (self.spec.get("from") or [])[:3]
        n = max(1, len(senders))
        r = self.spec.get("result")
        sh, rh = 166, 200                                     # a node's height, the result's
        gap = 160                                             # room for the data pill under each sender
        senders_h = n * sh + (n - 1) * gap + 90
        right_h = sh + (130 + rh if r else 0)
        height = max(senders_h, right_h)
        top = (ZONE[1] + ZONE[3]) / 2 - height / 2
        ys = [top + sh / 2 + k * (sh + gap) for k in range(n)]
        mid = (ys[0] + ys[-1]) / 2
        ty = max(mid, top + sh / 2) if not r else min(mid, top + height - rh - 130 - sh / 2)
        to_box = (560, ty - sh / 2, SAFE_R, ty + sh / 2)
        tx = to_box[0]
        for y in ys:                                       # the roads, under everything
            d.line([(440, y), (490, y), (520, ty), (tx, ty)], fill=(204, 204, 212), width=7, joint="curve")
        for snd, y in zip(senders, ys):
            self.node(frame, (60, y - sh / 2, 440, y + sh / 2), snd.get("title", ""), snd.get("sub", ""))
        to = self.spec.get("to") or {}
        self.node(frame, to_box, to.get("title", ""), to.get("sub", ""))
        d = ImageDraw.Draw(frame)
        for p in self.spec.get("pills") or []:
            k = int(p.get("from", 0))
            if k >= len(ys):
                continue
            v = (u - float(p.get("at", 0.4))) / 0.7
            if v < 0:
                continue
            col = {"bad": RED, "good": GREEN}.get(p.get("tone"), BLUE)
            text = p.get("text", "")
            sz = fit_size(text, "caption", 32, 340)
            pw = B.text_width(text, "caption", sz, 0) + 44
            x = 70 if v >= 1 else 70 - (1 - smooth(v)) * 40
            y = ys[k] + sh / 2 + 44
            a = int(255 * smooth(v * 2))
            d.rounded_rectangle([x, y - 34, x + pw, y + 34], 34, fill=col + (a,))
            B.draw_text(frame, x + 22, y + 12, text, "caption", sz, WHITE, 0)
        if r and u >= float(r.get("at", 1.2)):
            tone = GREEN if r.get("tone") == "good" else RED
            box = (to_box[0], to_box[3] + 130, SAFE_R, to_box[3] + 130 + rh)
            cx = (box[0] + box[2]) / 2
            d.line([(cx, to_box[3]), (cx, box[1])], fill=tone, width=6)
            Card_box(frame, box, ring=tone)
            text = r.get("text", "")
            sz = fit_size(text, "caption", 58, box[2] - box[0] - 40)
            B.draw_text(frame, cx - B.text_width(text, "caption", sz, 0) / 2, box[1] + 88, text, "caption", sz, tone, 0)
            if r.get("sub"):
                s2 = fit_size(r["sub"], "caption", 30, box[2] - box[0] - 40)
                B.draw_text(frame, cx - B.text_width(r["sub"], "caption", s2, 0) / 2, box[1] + 156, r["sub"],
                            "caption", s2, K.SUB, 0)


class Checklist(Card):
    """The list worth a screenshot: every step of the reel, ticked in as it's said."""

    def items(self):
        return [it if isinstance(it, dict) else {"text": it} for it in self.spec.get("items") or []]

    def texts(self):
        out = [x for x in (self.spec.get("title"), self.spec.get("sub")) if x]
        return out + [it.get("text", "") for it in self.items()]

    def sounds(self, t0):
        return [("whoosh_soft", t0)] + [("pop", t0 + float(it.get("at", 0.3 + 0.25 * k)))
                                        for k, it in enumerate(self.items())]

    def draw(self, frame, u, reel, i):
        items = self.items()
        rows = max(1, len(items))
        head = (150 if self.spec.get("title") else 40) + (46 if self.spec.get("sub") else 0)
        row = min(140, (ZONE[3] - ZONE[1] - 60 - head) / rows)
        h = head + rows * row + 40
        y0 = (ZONE[1] + ZONE[3]) / 2 - h / 2                 # the card in the middle of the zone
        Card_box(frame, (60, y0, SAFE_R, y0 + h))
        if self.spec.get("title"):
            sz = fit_size(self.spec["title"], "anton", 80, SAFE_R - 180)
            B.draw_text(frame, 120, y0 + 110, self.spec["title"], "anton", sz, K.TXT, 0)
        if self.spec.get("sub"):
            B.draw_text(frame, 122, y0 + (156 if self.spec.get("title") else 70), self.spec["sub"], "caption", 30,
                        K.SUB, 0)
        d = ImageDraw.Draw(frame)
        r = min(34, row * 0.26)
        for k, it in enumerate(items):
            y = y0 + head + k * row + row / 2
            on = u >= float(it.get("at", 0.3 + 0.25 * k))
            d.ellipse([120, y - r, 120 + 2 * r, y + r], fill=GREEN if on else (226, 228, 234))
            if on:
                K.tick_mark(d, 120 + r, y, 1.0, WHITE, 2.4 * r / 34)
            text = it.get("text", "")
            sz = fit_size(text, "caption", 44, SAFE_R - 230)
            B.draw_text(frame, 120 + 2 * r + 30, y + 15, text, "caption", sz, K.TXT if on else (150, 153, 162), 0)


class Outro(Card):
    """The sign-off card, as every style has it: the wordmark on lemon, the tagline, the website."""

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.card = Hs.Outro(dict(spec, at=0.0), {"photos": {}, "seed": 7, "paper": None})

    def texts(self):
        return self.card.texts()

    def sounds(self, t0):
        return [("sparkle", t0 + 0.2)]

    def draw(self, frame, u, reel, i):
        art = self.card.frame_image(max(0.0, u))
        B.paste(frame, art, 540 - art.width / 2, 860 - art.height / 2)


def Card_box(frame, box, ring=None, radius=26):
    x0, y0, x1, y1 = [int(v) for v in box]
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle([x0 + 4, y0 + 14, x1 - 4, y1 + 18], radius, fill=60)
    frame.paste((0, 0, 0, 255), mask=sh.filter(ImageFilter.GaussianBlur(22)))
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle([x0, y0, x1, y1], radius, fill=WHITE, outline=HAIR, width=2)
    if ring:
        d.rounded_rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], radius + 2, outline=ring, width=5)


CARDS = {"headline": Headline, "route": Route, "flow": Flow, "checklist": Checklist, "outro": Outro}


# ---------------------------------------------------------------- the screens on the reel

class Shown:
    """One screen as reel.json names it: drawn from its parts, or a screenshot GitHub took ("src")."""

    def __init__(self, name, spec, root):
        self.name, self.spec = name, spec
        self.device = spec.get("device", "phone")
        self.picture = None
        if spec.get("src"):
            path = Path(root) / spec["src"]
            self.picture = Image.open(path).convert("RGBA") if path.exists() else None
            if self.picture is None:
                self.picture = Image.new("RGBA", (2560 if self.device == "laptop" else 1170, 1600 if self.device ==
                                                  "laptop" else 2532), (238, 238, 238, 255))
            base_w = K.DEVICE[self.device][0]
            self.ppt = self.picture.width / base_w          # pixels per point in the screenshot
        self._cache, self._boxes = {}, {}

    def size_pt(self):
        if self.picture is not None:
            return self.picture.width / self.ppt, self.picture.height / self.ppt
        w, h = K.DEVICE[self.device]
        return (w + 2 * K.BEZEL, h + 2 * K.BEZEL) if self.device == "phone" else (w, h)

    def offset_pt(self):
        """The screen's top left inside the device's image, in points: a phone's bezel."""
        if self.picture is None and self.device == "phone":
            return float(K.BEZEL), float(K.BEZEL)
        return 0.0, 0.0

    def image(self, state):
        """(RGBA image, pixels per point, (x, y) of the screen's top left in the image, boxes in points)."""
        if self.picture is not None:
            boxes = {k: tuple(v / self.ppt for v in box) for k, box in (self.spec.get("targets") or {}).items()}
            return self.picture, self.ppt, (0, 0), boxes
        key = json.dumps(state, sort_keys=True, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
        if key not in self._cache:
            if len(self._cache) > 48:
                self._cache.clear()
            img, boxes, off, s = K.render(self.spec, state)
            self._cache[key] = (img, s, off, boxes)
        return self._cache[key]

    def boxes(self, state):
        """The parts' boxes at a state, without drawing the screen big (points)."""
        if self.picture is not None:
            return self.image(state)[3]
        key = json.dumps(state, sort_keys=True, default=lambda o: sorted(o) if isinstance(o, set) else str(o))
        if key not in self._boxes:
            if len(self._boxes) > 256:
                self._boxes.clear()
            self._boxes[key] = K.boxes_of(self.spec, state)
        return self._boxes[key]

    def lifted(self, pid, state, width_px=860):
        """(card, its text's height in px, the touched item's box on the card or None), or (None, 0, None)."""
        if self.picture is None:
            return K.lifted(self.spec, pid, state, width_px=width_px)
        box = (self.spec.get("targets") or {}).get(pid)
        if not box:
            return None, 0, None
        x0, y0, x1, y1 = box
        pad = 14 * self.ppt
        crop = self.picture.crop((int(max(0, x0 - pad)), int(max(0, y0 - pad)), int(min(self.picture.width, x1 + pad)),
                                  int(min(self.picture.height, y1 + pad))))
        k = min(width_px / crop.width, 2.4)
        big = crop.resize((max(1, int(crop.width * k)), max(1, int(crop.height * k))), Image.LANCZOS)
        card = Image.new("RGBA", (big.width + 24, big.height + 24), (0, 0, 0, 0))
        ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1], 20, fill=WHITE + (255,))
        card.paste(big, (12, 12))
        return card, 15.5 * self.ppt * k, None            # a web page's body text is about 15.5 points


# ---------------------------------------------------------------- the reel

class FocusReel(Hs.HostReel):
    CARDS = CARDS
    ZONE = ZONE
    UNDER = "the words"

    def __init__(self, ep_dir, use_voice=True):
        self.E = B.Episode(ep_dir, use_voice)
        Hs.use_brand()
        ep = self.E.ep
        self.cast, self.roles, self.kits, self.slots, self.mirror = {}, [], {}, {}, {}
        self.speaker = {l["shot"]: None for l in ep.get("script", [])}
        self.poses, self.framing = {}, []
        self.ctx_photos = self.E.photos
        self.layout_notes = None
        self.screens = {name: Shown(name, spec, self.E.dir) for name, spec in (self.E.reel.get("screens") or {}).items()}
        self.elements, self.track = [], []
        current = None
        for i, shot in enumerate(self.E.shots):
            els, entry = [], {"screen": None, "focus": None, "lift": None, "actions": [], "hook": False}
            for j, spec in enumerate(self.E.reel["shots"].get(shot["id"], [])):
                spec = self.resolve(shot, json.loads(json.dumps(spec)))
                kind = spec.get("type")
                if kind == "screen":
                    name = spec.get("screen")
                    if name not in self.screens:
                        raise SystemExit("{}: screen \"{}\" isn't in reel.json → screens ({})".format(
                            shot["id"], name, ", ".join(sorted(self.screens)) or "none"))
                    current = name
                    entry.update(screen=name, focus=spec.get("focus"), lift=spec.get("lift"))
                    for a in spec.get("do") or []:
                        entry["actions"].append(dict(a, t=shot["start"] + float(a.get("at", 0.2)), shot=i))
                    continue
                if kind not in CARDS:
                    raise SystemExit("{}: \"{}\" isn't a card of the Focus style. Cards: screen, {}".format(
                        shot["id"], kind, ", ".join(sorted(CARDS))))
                els.append(CARDS[kind](spec, {"seed": (i + 1) * 131 + j * 7}))
            if entry["screen"] is None and current and not any(el.full for el in els):
                entry["screen"] = current                  # the screen stays until a card takes its place
            entry["hook"] = i == 0 and any(isinstance(el, Headline) for el in els)
            self.elements.append(els)
            self.track.append(entry)
        self.place_goes()
        self.acts = {}
        for e in self.track:
            for a in e["actions"]:
                self.acts.setdefault(self.screen_name_at(e, a["t"]), []).append(a)
        for name in self.acts:
            self.acts[name].sort(key=lambda a: a["t"])
        self.route = self.E.reel.get("route") or []
        self.header = self.make_header()
        self.notes = []
        self.runs = self.direct()
        self.pages = [paginate(sh["words"], self.kept_words(i), sh.get("times")) for i, sh in enumerate(self.E.shots)]

    def place_goes(self):
        """Where a tap (or a typed address) opens another page, the screen changes 0.12 s after it, in its line and
        the lines after it on the same screen. Placed again once the touches have their final times."""
        for e in self.track:
            e["goes"] = []
        for a in [a for e in self.track for a in e["actions"]]:
            if a.get("go"):
                for e in self.track[a["shot"]:]:
                    if e["screen"] is None:
                        break
                    e["goes"].append((a["t"] + 0.12, a["go"]))
        for e in self.track:
            e["goes"].sort()

    # ---- resolving words into times
    def resolve(self, shot, spec):
        def at(word):
            return max(0.0, self.E.word_time(shot, word) - 0.12)
        if "on" in spec:
            spec["at"] = at(spec["on"])
        for key in ("do", "items", "pills", "steps"):
            for item in spec.get(key) or []:
                if isinstance(item, dict) and "on" in item:
                    item["at"] = at(item["on"]) - (0.0 if key == "do" else spec.get("at", 0.0))
        if isinstance(spec.get("result"), dict) and "on" in spec["result"]:
            spec["result"]["at"] = at(spec["result"]["on"]) - spec.get("at", 0.0)
        return spec

    # the Host engine's avatars and bubble aren't in this style
    def obstacles(self, i):
        return []

    def bubble_top(self, i):
        return None

    def mouth_track(self):
        return {}

    def laid_out(self):
        return []

    # ---- which screen, in which state
    def screen_name_at(self, entry, t):
        name = entry["screen"]
        for when, target in entry.get("goes", []):
            if t >= when:
                name = target
        return name

    def state_at(self, name, t):
        """A screen's state at time t: every action on it up to then, the latest still moving."""
        st = {"toggles": {}, "toggle_prog": {}, "typed": {}, "focused": [], "active": {}, "pressed": {},
              "labels": {}, "tones": {}, "chosen": {}, "checked": {}, "done": {}, "open": {}, "scroll": 0.0}
        spec = self.screens[name].spec if name in self.screens else {}
        for a in self.acts.get(name, []):
            dt = t - a["t"]
            if dt < 0:
                break
            target = a.get("tap") or a.get("write") or a.get("check") or a.get("look")
            e = dt - (0.12 if a.get("tap") else 0.0)       # what a tap does happens just after the finger lands
            if a.get("tap"):
                st["pressed"][a["tap"]] = 1.0 if dt < 0.16 else 0.0
                if "/" in str(a["tap"]):
                    owner, item = str(a["tap"]).split("/", 1)
                    if e >= 0:
                        st["active"][owner] = item
                elif e >= 0 and not any(a.get(k) for k in ("open", "close", "go", "show", "toggle", "write")):
                    ov = K.overlay_of(spec, a["tap"])     # a row tapped in a list: it's the one picked
                    if ov:
                        st["chosen"][ov] = a["tap"]
            if "toggle" in a and e >= 0:
                tid = a["toggle"] if isinstance(a["toggle"], str) else target
                was = st["toggles"].get(tid, bool((K.find_part(spec, tid) or {}).get("toggle")))
                new = a.get("to", not was) if not isinstance(a["toggle"], bool) else a["toggle"]
                st["toggles"][tid] = bool(new)
                p = smooth(e / 0.22)
                st["toggle_prog"][tid] = p if new else 1 - p
            if a.get("write") and dt >= 0:
                text = str(a.get("text", ""))
                n = min(len(text), int(dt / TYPE_STEP) + 1)
                st["typed"][a["write"]] = text[:n]
                if a["write"] not in st["focused"]:
                    st["focused"].append(a["write"])
            for key, sign in (("open", 1), ("close", -1)):
                if a.get(key) and e >= 0:
                    p = smooth(e / (0.35 if sign > 0 else 0.3))
                    st["open"][a[key]] = p if sign > 0 else (1 - p) * st["open"].get(a[key], 1.0)
            if a.get("show") and e >= 0:
                hold = float(a.get("hold", 2.4))
                st["open"][a["show"]] = smooth(e / 0.3) if e < hold else max(0.0, 1 - (e - hold) / 0.3)
            if a.get("select") and e >= 0:
                st["active"][a["select"]] = a.get("item")
            if a.get("check") and e >= 0:
                st["checked"][a["check"]] = True
            if a.get("label") and e >= 0:
                st["labels"][a.get("label_of") or target] = a["label"]
                if a.get("tone"):
                    st["tones"][a.get("label_of") or target] = a["tone"]
            if a.get("done") is not None and e >= 0:
                st["done"][a.get("list", target)] = a["done"]
            if "scroll" in a and e >= 0:
                st["scroll"] = lerp(st["scroll"], float(a["scroll"]), smooth(e / 0.6))
        return st

    # ---- the camera's plan: runs of lines on one screen, and the beats in them
    @staticmethod
    def touch(a):
        """The part an action touches (a tap, typing, a tick) or looks at, or None. A status that changes with no touch
        of its own ("label" with "label_of") is looked at: the viewer has to see it change."""
        return (a.get("tap") or a.get("write") or a.get("check") or a.get("look")
                or (a.get("label_of") if a.get("label") else None))

    @staticmethod
    def pointed(a):
        """A touch the finger (phone) or the cursor (laptop) makes: a look or a status change has no pointer."""
        return bool(a.get("tap") or a.get("write") or a.get("check"))

    @staticmethod
    def lead(a):
        """How long before a touch the camera sets off for its part on the page: the pointer needs REACH to get there;
        a look or a status change, only the camera's move."""
        return REACH if (a.get("tap") or a.get("write") or a.get("check")) else LOOK

    @staticmethod
    def navigates(a):
        """A tap that takes the viewer somewhere: another page, a dialog or a menu, a tab, a menu item, a message. The
        camera goes to it on the page and the pointer clicks it there, so the viewer sees where it is; what it opens is
        what shows next, so nothing lifts out."""
        tap = str(a.get("tap") or "")
        return bool(tap) and bool(a.get("go") or a.get("open") or a.get("close") or a.get("show")
                                  or ("/" in tap and not a.get("toggle")))

    def direct(self):
        """Lines in a row on one screen, with no card between them, make one run: the camera, the lifted part and the
        pointer flow across their lines. Returns the runs: {"shots", "start", "end", "acts", "beats"}; a beat is
        (from, to, kind, ref), kind "land" (a page that has just opened, whole), "whole" (the page), "aim" (the camera
        on a part of the sharp page, while the pointer gets there), "part" (ref lifted out) or "overlay" (ref, an open
        dialog or sheet, framed whole)."""
        runs, cur = [], None
        for i, e in enumerate(self.track):
            if not e["screen"] or any(el.full for el in self.elements[i]):
                cur = None
                continue
            before = self.screen_name_at(self.track[i - 1], self.E.shots[i - 1]["end"] - 1e-3) if i else None
            if cur is None or before != e["screen"]:
                cur = {"shots": []}
                runs.append(cur)
            cur["shots"].append(i)
        self.run_of = {}
        for run in runs:
            for i in run["shots"]:
                self.run_of[i] = run
            run["start"] = self.E.shots[run["shots"][0]]["start"]
            run["end"] = self.E.shots[run["shots"][-1]]["end"]
            run["acts"] = sorted((a for i in run["shots"] for a in self.track[i]["actions"]), key=lambda a: a["t"])
            self.time_touches(run)
        self.place_goes()                                # the pages change where the touches now land
        for run in runs:
            run["beats"] = self.beats(run)
        self.acts = {}
        for e in self.track:
            for a in e["actions"]:
                self.acts.setdefault(self.screen_name_at(e, a["t"]), []).append(a)
        for name in self.acts:
            self.acts[name].sort(key=lambda a: a["t"])
        return runs

    def time_touches(self, run):
        """Each touch lands on its word, or a little later in its line when the page or the last change hasn't been
        seen long enough: a page that opens shows whole for LAND seconds, a change for SHOW, and the pointer (for a
        look, the camera) needs its lead to get to the part. A page change after a typed address waits for the typing.
        A touch that can't wait inside its line is a fix for Muse."""
        hook = self.track[run["shots"][0]]["hook"]
        free = run["start"] + (0.3 if hook else LAND)
        for a in run["acts"]:
            a.setdefault("t_word", a["t"])
            target = self.touch(a)
            if target or a.get("go"):
                want = free + (self.lead(a) if target else 0.0)
                if want > a["t"]:
                    line_end = self.E.shots[a["shot"]]["end"] - 0.15
                    moved = min(want, max(a["t"], line_end))
                    if moved < want - 0.05:
                        self.notes.append(("fix", self.E.shots[a["shot"]]["id"], "the touch on \"{}\" comes too soon "
                                           "after the page opened or the change before it, even at the end of its "
                                           "line: give each new page a moment and each touch its own words".format(
                                               target or a.get("go"))))
                    a["t"] = moved
            busy = 0.12 + SHOW
            if a.get("write"):
                busy += len(str(a.get("text", ""))) * TYPE_STEP
            if a.get("go"):
                busy = 0.12 + LAND                       # the new page is seen whole before anything else happens
            elif a.get("open") or a.get("close") or a.get("show"):
                busy += 0.35
            if target or a.get("go") or busy > 0.12 + SHOW:
                free = max(free, a["t"] + busy)

    def arrivals(self, run):
        """When a page opens in a run: its start (bar the hook's first frame, which opens on its part) and every page
        change."""
        out = [] if self.track[run["shots"][0]]["hook"] else [run["start"]]
        return sorted(out + [a["t"] + 0.12 for a in run["acts"] if a.get("go")])

    def beats(self, run):
        """The run's beats. A page that opens is shown whole first ("land", LAND seconds). For each touch the camera then
        travels to its part on the sharp page ("aim") while the pointer gets there, and the touch lands; a touch that
        changes the part itself (typing, a tick, a switch, a status) lifts it out once it has landed ("part"), while a
        tap that opens something shows what it opened. A line's own focus: the camera travels there once the page has
        been seen, then it lifts out. An opened dialog is framed whole, a message that pops up lifts out, a closed
        dialog shows the page."""
        marks = []                                       # (time, kind, ref, only while this ref is up)
        hook = self.track[run["shots"][0]]["hook"]
        lands = self.arrivals(run)
        marks += [(t, "land", None, None) for t in lands]
        leads = [a["t"] - self.lead(a) for a in run["acts"] if self.touch(a)]
        for i in run["shots"]:
            e, start = self.track[i], self.E.shots[i]["start"]
            if not e["focus"] or any(start - 1.0 <= t <= start + 0.8 for t in leads) or any(
                    self.touch(a) == e["focus"] for a in e["actions"]):
                continue                                 # its own touch takes the camera there
            if hook and i == run["shots"][0]:            # the first frame: the hook's part, lifted out at once
                marks.append((start, "part", e["focus"], None))
                continue
            t0 = max([start] + [t + LAND for t in lands if t <= start + 1e-6])
            marks.append((t0, "aim", e["focus"], None))
            marks.append((t0 + GLIDE, "part", e["focus"], None))
        for a in run["acts"]:
            target = self.touch(a)
            e0 = a["t"] + (0.12 if a.get("tap") else 0.0)
            if target:
                marks.append((a["t"] - self.lead(a), "aim", target, None))
                if a.get("lift", not self.navigates(a)):
                    marks.append((e0 + 0.05 if self.pointed(a) else a["t"], "part", target, None))
            if a.get("show"):
                marks.append((e0 + 0.15, "part", a["show"], None))
                marks.append((e0 + float(a.get("hold", 2.4)) + 0.3, "whole", None, a["show"]))
            elif a.get("open"):
                marks.append((e0 + 0.3, "overlay", a["open"], None))
            elif a.get("close"):                          # a closed dialog shows the page; a menu on a MacBook, the
                shown = self.screens[self.screen_name_at(self.track[a["shot"]], a["t"])]   # field it hangs from,
                near = ((shown.spec.get("overlays") or {}).get(a["close"]) or {}).get("near")   # with what was picked
                marks.append((e0 + 0.15, "aim", near, None) if near and shown.device == "laptop"
                             else (e0 + 0.15, "whole", None, None))
            elif target and self.navigates(a) and not a.get("go"):   # a tab or a menu item: what changed on the page
                marks.append((e0 + SHOW, "whole", None, None))
        for t in lands:                                  # a page seen whole, then the camera settles where it reads
            if not any(t < m[0] <= t + LAND + 0.3 for m in marks if m[1] != "land"):
                marks.append((t + LAND, "whole", None, None))
        marks.sort(key=lambda m: m[0])
        beats = []
        for t, kind, ref, only in marks:
            if only is not None and not (beats and beats[-1][3] == only):
                continue
            t = min(max(t, run["start"]), run["end"])
            if beats and (beats[-1][2], beats[-1][3]) == (kind, ref):
                continue
            if beats and kind == "aim" and beats[-1][2] == "part" and beats[-1][3] == ref:
                continue                                 # it's lifted out already: the camera is there
            if beats and t - beats[-1][0] < 0.05:           # replaced before it showed
                beats.pop()
                if beats and (beats[-1][2], beats[-1][3]) == (kind, ref):
                    continue
            beats.append([t, None, kind, ref])
        if not beats or beats[0][0] > run["start"] + 1e-6:
            beats.insert(0, [run["start"], None, "whole", None])
        for k, b in enumerate(beats):
            b[1] = beats[k + 1][0] if k + 1 < len(beats) else run["end"]
        return [tuple(b) for b in beats if b[1] - b[0] > 1e-6]

    @staticmethod
    def beat_index(beats, t):
        return max([j for j, b in enumerate(beats) if b[0] <= t] or [0])

    def lifts_at(self, i, t):
        """The parts lifted out at t: [(id, progress)], one settling back into the screen first, then the one rising.
        Progress runs past 1 for a moment as a part springs up."""
        run = self.run_of.get(i)
        if self.track[i]["lift"] is False or not run:
            return []
        beats = run["beats"]
        k = self.beat_index(beats, t)
        t0, t1, kind, ref = beats[k]
        out = []
        prev = beats[k - 1] if k else None
        if prev and prev[2] == "part" and prev[3] != ref and t - t0 < LIFT_OUT:
            out.append((prev[3], 1 - smooth((t - t0) / LIFT_OUT), True))
        if kind == "part":
            p, going = spring((t - t0) / LIFT_IN), False
            if k + 1 == len(beats) and t > t1 - LIFT_OUT:   # the run's end: it settles back before the cut
                p, going = min(p, 1 - smooth((t - (t1 - LIFT_OUT)) / LIFT_OUT)), True
            out.append((ref, max(0.0, p), going))
        return out

    def aimed_at(self, i, t):
        """While the camera travels to a part on the sharp page: (its id, how far its ring has come in, whether the
        camera has arrived), else None."""
        run = self.run_of.get(i)
        if not run:
            return None
        t0, t1, kind, ref = run["beats"][self.beat_index(run["beats"], t)]
        if kind != "aim" or not ref:
            return None
        return ref, smooth((t - t0) / 0.3), t - t0 >= GLIDE - 1e-3

    def zone_for(self, i, t):
        """The screen's zone at t: under the hook's words on the hook, then the full zone."""
        if self.track[i]["hook"]:
            return HOOK_ZONE
        if i == 1 and self.track[0]["hook"]:
            u = smooth((t - self.E.shots[1]["start"]) / 0.5)
            return tuple(lerp(a, b, u) for a, b in zip(HOOK_ZONE, ZONE))
        return ZONE

    def camera(self, shown, boxes, target, zone, kind="part"):
        """(x, y, w, h) in the device image's points that the zone shows (a laptop page: laptop_camera).
        - "land": a page that has just opened, all of it: a phone whole.
        - "whole": a phone whole.
        - "aim" and "part": the part in use, close enough to read (a phone comes closer too), left of Instagram's
          buttons and never past the page's edges.
        - "overlay": an open dialog, whole."""
        if shown.device == "laptop":
            return self.laptop_camera(shown, boxes, target, zone, kind)
        sw, sh = shown.size_pt()
        ox, oy = shown.offset_pt()
        zw, zh = zone[2] - zone[0], zone[3] - zone[1]
        aspect = zh / zw
        box = boxes.get(target) if target else None
        if box:
            box = (box[0] + ox, box[1] + oy, box[2] + ox, box[3] + oy)
        if shown.device == "phone":
            fit = min(zw / sw, zh / sh)
            near = box is not None and kind in ("aim", "part")
            s = fit * (PHONE_ZOOM if near else 1.0)
            cw, ch = zw / s, zh / s
            x = max(sw / 2 - cw / 2, sw - (SAFE_R + 10 - zone[0]) / s)    # its right edge left of the buttons
            y = min(max((box[1] + box[3]) / 2 - ch / 2, 0), max(0, sh - ch)) if near else sh / 2 - ch / 2
            return (x, y, cw, ch)
        if kind == "land":
            return (0.0, (sh - sw * aspect) / 2, sw, sw * aspect)
        widest = min(sw, sh / aspect)                     # the window fills the zone: nothing past its edges
        if box and kind in ("aim", "part"):
            most = zw * 16.5 / READABLE * 0.55            # wider than this can't be read whole: frame its left end,
            if box[2] - box[0] > most:                    # where a row's name or a card's title is
                box = (box[0], box[1], box[0] + most, box[3])
        if box:
            bw = box[2] - box[0]
            cw = min(max(bw + 60 if kind == "overlay" else bw / 0.55, 440), widest)
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        else:
            cw = widest
            cx, cy = cw / 2, 0.0
        ch = cw * aspect
        x = min(max(cx - cw / 2, 0), max(0, sw - cw))
        y = min(max(cy - ch / 2, 0), max(0, sh - ch))
        if box:                                            # the part stays left of Instagram's buttons
            scale = zw / cw
            narrow = (box[2] - box[0]) * scale < SAFE_R - zone[0] - 60
            edge = zone[0] + ((box[2] if narrow else (box[0] + box[2]) / 2) - x) * scale
            limit = SAFE_R - (20 if narrow else 80)
            if edge > limit:
                x = min(max(0, sw - cw), x + (edge - limit) / scale)
        return (x, y, cw, ch)

    def laptop_camera(self, shown, boxes, target, zone, kind="part"):
        """(x, y, w, h) of the page the MacBook's screen shows, in the page's points. The MacBook stays where it is and
        the page zooms inside its screen: the whole page when it has just opened ("land") or when no part is named
        ("whole"); the part in use close enough to read ("aim", "part"), left of Instagram's buttons and never past the
        page's edges; an open dialog whole ("overlay")."""
        sw, sh = shown.size_pt()
        _, _, scr = macbook_rect(zone)
        vw, vh = scr[2] - scr[0], scr[3] - scr[1]
        aspect = vh / vw
        box = boxes.get(target) if target else None
        if not box and kind == "overlay" and target:      # an open menu or dialog: all of its own items
            ov = (shown.spec.get("overlays") or {}).get(target) or {}
            ids = [x.get("id") if isinstance(x, dict) and x.get("id") else       # an item without an id is menu/label
                   "{}/{}".format(target, x if isinstance(x, str) else (x or {}).get("text", ""))
                   for x in ov.get("items") or []]
            ids += [x.get("id") for x in ov.get("parts") or [] if isinstance(x, dict)]
            got = [boxes[k] for k in ids if k and k in boxes]
            near = boxes.get(ov.get("near")) if ov.get("near") else None
            if near and got:                               # the part it hangs from, only as far across as the menu:
                lo, hi = min(b[0] for b in got), max(b[2] for b in got)   # a field's left end, where its name is
                lo = min(max(near[0], lo), near[2])
                near = (lo, near[1], max(lo, min(near[2], hi)), near[3])
            got += [near] if near else []
            if got:
                box = (min(b[0] for b in got), min(b[1] for b in got), max(b[2] for b in got), max(b[3] for b in got))
        if kind in ("land", "whole") or not box:
            return (0.0, 0.0, sw, sw * aspect)
        least = vw * 16.5 / (READABLE + 2)                 # closer than the page's text needs to be readable
        most = least * 0.62                                # a part wider than this: frame its left end, where its
        if box[2] - box[0] > most and kind != "overlay":   # name or a row's words are
            box = (box[0], box[1], box[0] + most, box[3])
        bw, bh = box[2] - box[0], box[3] - box[1]
        cw = max(bw + 60 if kind == "overlay" else bw / 0.62, least)
        if kind == "overlay":                              # an open menu or dialog, top to bottom
            cw = max(cw, (bh + 60) / aspect)
        cw = min(cw, sw)
        ch = cw * aspect
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        x = min(max(cx - cw / 2, 0), max(0, sw - cw))
        y = min(max(cy - ch / 2, 0), max(0, sh - ch))
        scale = vw / cw                                    # the part stays left of Instagram's buttons
        narrow = (box[2] - box[0]) * scale < SAFE_R - scr[0] - 60
        edge = scr[0] + ((box[2] if narrow else (box[0] + box[2]) / 2) - x) * scale
        limit = SAFE_R - (20 if narrow else 80)
        if edge > limit:
            x = min(max(0, sw - cw), x + (edge - limit) / scale)
        return (x, y, cw, ch)

    def aim(self, shown, name, beat, t, zone):
        kind, ref = beat[2], beat[3]
        toast = ((shown.spec.get("overlays") or {}).get(ref) or {}).get("kind") == "toast"
        return self.camera(shown, shown.boxes(self.state_at(name, t)),
                           None if kind in ("whole", "land") or toast else ref, zone, kind)

    def glide(self, e, beats, t, zone, depth=0):
        """The camera on beat k's framing at t, gliding there from wherever it was when the beat began: the middle
        moves straight, and the zoom changes evenly, so a step in and a step out feel alike."""
        k = self.beat_index(beats, t)
        name = self.screen_name_at(e, t)
        cam = self.aim(self.screens[name], name, beats[k], t, zone)
        t0 = beats[k][0]
        if k == 0 or t - t0 >= GLIDE or depth > 3 or beats[k][2] == "land":
            return cam                                   # a page that opens cuts in, whole, like a page load
        was = self.glide(e, beats[:k], t0 - 1e-3, zone, depth + 1)
        return blend_view(was, cam, smooth((t - t0) / GLIDE))

    def camera_at(self, i, t, zone):
        """The screen shot i shows at t, and the camera on it."""
        e = self.track[i]
        name = self.screen_name_at(e, t)
        shown = self.screens[name]
        run = self.run_of.get(i)
        if not run:
            return shown, self.camera(shown, shown.boxes(self.state_at(name, t)), e["focus"], zone)
        return shown, self.glide(e, run["beats"], t, zone)

    # ---- drawing the screen in its zone
    def draw_screen(self, frame, i, t, stills=False):
        """The screen, as the camera frames it, with the part in use lifted out (or ringed while the camera gets
        there) and the pointer on it. Returns where things landed, for the checks: {"lift": box or None, "lifted": id,
        "hit": item box, "text_px": n, "pointers": [(x, y)], "aimed": id}."""
        e = self.track[i]
        zone = self.zone_for(i, t)
        zx0, zy0, zx1, zy1 = [int(v) for v in zone]
        zw, zh = zx1 - zx0, zy1 - zy0
        shown, (cx, cy, cw, ch) = self.camera_at(i, t, zone)
        st = self.state_at(shown.name, t)
        img, ppt, off, boxes = shown.image(st)
        lifts = self.lifts_at(i, t)
        if stills:
            lifts = [(pid, 1.0, False) for pid, _, _ in lifts[-1:]]
        info = {"lift": None, "lifted": None, "hit": None, "text_px": None, "pointers": [], "aimed": None}
        ox, oy = off[0] / ppt, off[1] / ppt                # the screen's top left in the device image, in points
        layer = Image.new("RGBA", (zw, zh), (0, 0, 0, 0))
        iw, ih = img.width / ppt, img.height / ppt
        vx0, vy0, vx1, vy1 = max(0.0, cx), max(0.0, cy), min(iw, cx + cw), min(ih, cy + ch)
        body = glass = None                                # where the device shows in the frame; a MacBook's screen
        if shown.device == "laptop":                       # a MacBook, the page on its screen, zoomed inside it
            _, dev, scr = macbook_rect(zone)
            glass = scr
            vw, vh = int(round(scr[2] - scr[0])), int(round(scr[3] - scr[1]))
            scale_pt = vw / cw
            to_frame = lambda x, y: (scr[0] + (ox + x - cx) * scale_pt, scr[1] + (oy + y - cy) * scale_pt)   # noqa: E731
            mac = macbook_body(int(round(dev[2] - dev[0])))
            layer.alpha_composite(mac, (int(round(dev[0] - zx0)), int(round(dev[1] - zy0))))
            view = Image.new("RGBA", (vw, vh), (0, 0, 0, 255))
            if vx1 > vx0 and vy1 > vy0:
                src = img.crop((int(vx0 * ppt), int(vy0 * ppt), int(math.ceil(vx1 * ppt)), int(math.ceil(vy1 * ppt))))
                dw, dh = max(1, int(round((vx1 - vx0) * scale_pt))), max(1, int(round((vy1 - vy0) * scale_pt)))
                piece = src.resize((dw, dh), Image.LANCZOS)
                view.paste(piece, (int(round((vx0 - cx) * scale_pt)), int(round((vy0 - cy) * scale_pt))), piece)
            m = Image.new("L", view.size, 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, vw - 1, vh - 1], 5, fill=255)
            view.putalpha(m)
            layer.paste(view, (int(round(scr[0] - zx0)), int(round(scr[1] - zy0))), view)
        else:
            scale_pt = zw / cw                             # pixels per point
            to_frame = lambda x, y: (zx0 + (ox + x - cx) * scale_pt, zy0 + (oy + y - cy) * scale_pt)   # noqa: E731
        if shown.device != "laptop" and vx1 > vx0 and vy1 > vy0:   # the part of the device the camera sees
            src = img.crop((int(vx0 * ppt), int(vy0 * ppt), int(math.ceil(vx1 * ppt)), int(math.ceil(vy1 * ppt))))
            dw, dh = max(1, int(round((vx1 - vx0) * scale_pt))), max(1, int(round((vy1 - vy0) * scale_pt)))
            piece = src.resize((dw, dh), Image.LANCZOS)
            m = Image.new("L", piece.size, 0)              # where the zone cuts the device, its corners are round
            ImageDraw.Draw(m).rounded_rectangle([0, 0, dw - 1, dh - 1], 30, fill=255)
            piece.putalpha(ImageChops.multiply(piece.getchannel("A"), m))
            px, py = int(round((vx0 - cx) * scale_pt)), int(round((vy0 - cy) * scale_pt))
            layer.paste(piece, (px, py))
            body = (zx0 + px, zy0 + py, zx0 + px + dw, zy0 + py + dh)
        cards = []                                         # what lifts out, and where it is on its way
        for n, (pid, p, going) in enumerate(lifts):
            box = boxes.get(pid)
            if not box or p <= 0.01:
                continue
            rising = n == len(lifts) - 1
            fx0, fy0 = to_frame(box[0], box[1])
            fx1, fy1 = to_frame(box[2], box[3])
            on_px = 16.5 * scale_pt
            if rising:
                info["text_px"] = on_px
            if not (e["lift"] if e["lift"] is not None else on_px < 40):
                if rising:                                 # big enough as it is: a ring shows it
                    cards.append(("ring", (fx0, fy0, fx1, fy1), p, None, 1.0))
                continue
            art, text_px, hit = shown.lifted(pid, st)
            if art is None:
                continue
            full_w, full_h = art.size
            sx = min(max((fx0 + fx1) / 2, zx0 + 60), zx1 - 60)   # it rises from where it is, inside the zone
            sy = min(max((fy0 + fy1) / 2, zy0 + 60), zy1 - 60)
            rest = min(max(sy, zy0 + 0.3 * zh), zy0 + 0.62 * zh)   # it rests near the middle, not on an edge
            left = min(max(sx - full_w / 2, 36), SAFE_R - full_w)
            top = min(max(rest - full_h / 2, ZONE[1] + 14), ZONE[3] - 14 - full_h)
            sc = lerp(max(40.0, min(fx1 - fx0, full_w)) / full_w, 1.0, p)
            aw, ah = max(1, int(full_w * sc)), max(1, int(full_h * sc))
            q = min(1.0, p)
            sx = min(max(sx, zx0 + aw / 2 + 12), zx1 - aw / 2 - 12)   # never past the zone's edge on its way up
            sy = min(max(sy, zy0 + ah / 2 + 12), zy1 - ah / 2 - 12)
            lx = lerp(sx - aw / 2, left + (full_w - aw) / 2, q)
            ly = lerp(sy - ah / 2, top + (full_h - ah) / 2, q)
            cards.append(("card", (lx, ly, aw, ah), p, art, max(0.0, min(1.0, p)) if going else 1.0))
            if rising:
                info.update(text_px=text_px, lift=(left, top, left + full_w, top + full_h), lifted=pid,
                            hit=None if hit is None else (left + hit[0], top + hit[1], left + hit[2], top + hit[3]))
        soft = max([c[2] for c in cards if c[0] == "card"] or [0.0])
        if soft > 0.01:                                    # focus: the rest softens and frosts over, white
            a = float(min(1.0, soft))
            blurred = layer.filter(ImageFilter.GaussianBlur(5 * a))
            frost = Image.new("RGBA", blurred.size, (255, 255, 255, int(150 * a)))
            layer = Image.alpha_composite(blurred, Image.composite(frost, Image.new("RGBA", blurred.size, (0, 0, 0, 0)),
                                                                   blurred.getchannel("A")))
        if body:
            sh = Image.new("L", (W, H), 0)
            ImageDraw.Draw(sh).rounded_rectangle([body[0] + 8, body[1] + 26, body[2] - 8, body[3] + 22],
                                                 60 if shown.device == "phone" else 30, fill=70)
            frame.paste((0, 0, 0, 255), mask=sh.filter(ImageFilter.GaussianBlur(36)))
        frame.alpha_composite(layer, (zx0, zy0))
        aimed = self.aimed_at(i, t)
        if aimed and not cards:                            # on its way: a ring round the part on the sharp page
            rid, ring_in, arrived = aimed
            box = boxes.get(rid)
            if box:
                x0, y0 = to_frame(box[0], box[1])
                x1, y1 = to_frame(box[2], box[3])
                ring_round(frame, (x0 - 10, y0 - 10, x1 + 10, y1 + 10), ring_in, glass)
                info["aimed"] = rid
                if arrived:
                    info["text_px"] = 16.5 * scale_pt
        for kind, where, p, art, fade in cards:
            if kind == "ring":
                x0, y0, x1, y1 = where
                ring_round(frame, (x0 - 12, y0 - 12, x1 + 12, y1 + 12), 1.0, glass)
                continue
            lx, ly, aw, ah = where
            framed = Image.new("RGBA", (aw + 8, ah + 8), (0, 0, 0, 0))
            fd = ImageDraw.Draw(framed)                    # white inside the edge: the part's own round corners
            fd.rounded_rectangle([3, 3, aw + 4, ah + 4], 21, fill=WHITE + (255,))   # don't show the shadow
            framed.alpha_composite(art.resize((aw, ah), Image.LANCZOS), (4, 4))
            fd.rounded_rectangle([1, 1, aw + 6, ah + 6], 23, outline=INK + (255,), width=3)
            fd.rounded_rectangle([3, 3, aw + 4, ah + 4], 21, outline=LEMON + (255,), width=4)
            if fade < 1.0:                                 # the part going back fades as it goes
                framed.putalpha(framed.getchannel("A").point(lambda v, f=fade: int(v * f)))
            s2 = Image.new("L", (W, H), 0)
            ImageDraw.Draw(s2).rounded_rectangle([lx + 6, ly + 18, lx + aw + 6, ly + ah + 22], 26,
                                                 fill=int(190 * min(1.0, p) * fade))
            frame.paste((0, 0, 0, 255), mask=s2.filter(ImageFilter.GaussianBlur(26)))
            frame.alpha_composite(framed, (int(lx) - 4, int(ly) - 4))
        if not stills:
            self.draw_pointer(frame, i, t, shown, boxes, to_frame, info)
        return info

    def tap_point(self, part, spot):
        """Where a finger or cursor lands on a part: on a toggle, at the end of a field's words, beside a button's
        label, under a tab's name: never on the words."""
        kind = (part or {}).get("kind")
        x0, y0, x1, y1 = spot
        w, h = x1 - x0, y1 - y0
        if kind == "row" and part.get("toggle") is not None:
            return x1 - 0.1 * w, (y0 + y1) / 2
        if kind == "field":
            return x0 + 0.72 * w, y1 - 0.32 * h
        if kind == "button":
            return x0 + 0.86 * w, (y0 + y1) / 2 + 0.12 * h
        if kind == "item":
            return x1 - 0.2 * w, y1 - 0.15 * h
        return x1 - min(60, 0.16 * w), (y0 + y1) / 2

    def draw_pointer(self, frame, i, t, shown, boxes, to_frame, info):
        """The finger (phone) or the cursor (laptop) travelling across the page to the part it touches, and the tap. On
        a laptop the cursor also goes to a part a line only looks at. Once the part lifts out, the card shows what the
        touch did, and the pointer leaves it."""
        laptop = shown.device == "laptop"
        run = self.run_of.get(i)
        for a in (run["acts"] if run else self.track[i]["actions"]):
            touch = a.get("tap") or a.get("write") or a.get("check")
            target = touch or (a.get("look") if laptop else None)
            lead = self.lead(a)
            if not target or not (a["t"] - lead <= t <= a["t"] + (0.5 if touch else 0.0)):
                continue
            if info.get("lifted") == target or not boxes.get(target):
                continue
            part = K.find_part(shown.spec, target) if shown.picture is None else {"kind": "button"}
            box = boxes[target]
            (fx0, fy0), (fx1, fy1) = to_frame(box[0], box[1]), to_frame(box[2], box[3])
            zx0, zy0, zx1, zy1 = self.zone_for(i, t)       # a part wider than the view: where the view shows it
            if laptop:                                     # on a MacBook, what its screen shows
                zx0, zy0, zx1, zy1 = macbook_rect((zx0, zy0, zx1, zy1))[2]
            fx0, fx1 = max(fx0, zx0 + 20), min(fx1, min(zx1, SAFE_R) - 20)
            if fx1 <= fx0:
                continue
            tx, ty = self.tap_point(part, (fx0, fy0, fx1, fy1))
            info["pointers"].append((tx, ty))
            if t < a["t"]:
                u = smooth((t - (a["t"] - lead)) / lead)
                sx, sy = tx + 150, ty + 210                # it comes in from the lower right
                if laptop:                                 # from inside the MacBook's screen
                    sx, sy = min(sx, zx1 - 50), min(sy, zy1 - 74)
                ox, oy = tx + (1 - u) * (sx - tx), ty + (1 - u) * (sy - ty)
            else:
                ox, oy = tx, ty
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(ov)
            if touch and t >= a["t"]:
                u = (t - a["t"]) / 0.5
                r = 28 + 72 * u
                d.ellipse([ox - r, oy - r, ox + r, oy + r], outline=INK + (int(200 * (1 - u)),), width=4)
                d.ellipse([ox - r * 0.6, oy - r * 0.6, ox + r * 0.6, oy + r * 0.6], fill=LEMON + (int(150 * (1 - u)),))
            if laptop:
                k = 0.85 if touch and a["t"] <= t < a["t"] + 0.12 else 1.0
                pts = [(0, 0), (0, 58), (15, 44), (26, 70), (37, 65), (26, 40), (46, 40)]
                poly = [(ox + x * k, oy + y * k) for x, y in pts]
                d.polygon(poly, fill=WHITE + (255,))
                d.line(poly + [poly[0]], fill=INK + (255,), width=4)
            else:
                r = 30 if not (a["t"] <= t < a["t"] + 0.12) else 25
                d.ellipse([ox - r, oy - r, ox + r, oy + r], fill=(26, 26, 28, 60), outline=(26, 26, 28, 170),
                          width=3)
            if laptop:                                     # the cursor is on the page: the glass's edge cuts it
                glass = Image.new("L", (W, H), 0)
                ImageDraw.Draw(glass).rectangle([math.ceil(zx0), math.ceil(zy0), int(zx1) - 1, int(zy1) - 1], fill=255)
                ov.putalpha(ImageChops.multiply(ov.getchannel("A"), glass))
            frame.alpha_composite(ov)

    # ---- the header: the logo, and the route on the same row
    def make_header(self):
        img = Image.new("RGBA", (W, 330), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        brand = self.E.reel.get("brand_label") or B.logo_text()
        size = 40
        top, bot = B.ink_box(brand, "anton", size)
        bw = B.text_width(brand, "anton", size, 1)
        d.rounded_rectangle([60, 228, 60 + bw + 36, 292], radius=14, fill=INK)
        B.draw_text(img, 78, 260 - (top + bot) / 2, brand, "anton", size, LEMON, 1)
        return img

    def route_now(self, t):
        now = -1
        for k, step in enumerate(self.route):
            start = next((s["start"] for s in self.E.shots if s["id"] == step.get("from")), None)
            if start is not None and t >= start:
                now = k
        return now

    def route_bar(self, frame, t):
        if not self.route:
            return
        first = next((s["start"] for s in self.E.shots if s["id"] == self.route[0].get("from")), None)
        if first is None or t < first:
            return
        a = smooth((t - first) / 0.35)
        d = ImageDraw.Draw(frame)
        now = self.route_now(t)
        labels = [str(s.get("label", "")) for s in self.route]
        size = 22
        widths = [B.text_width(lab, "mono_bold", size, 0) + 40 for lab in labels]
        logo_end = 60 + B.text_width(self.E.reel.get("brand_label") or B.logo_text(), "anton", 40, 1) + 36 + 24
        while sum(widths) + 10 * (len(widths) - 1) > 1020 - logo_end and size > 14:
            size -= 2
            widths = [B.text_width(lab, "mono_bold", size, 0) + 30 for lab in labels]
        x = 1020 - sum(widths) - 10 * (len(widths) - 1)
        y = 238 - int(24 * (1 - a))
        for k, (lab, w) in enumerate(zip(labels, widths)):
            done, cur = k < now, k == now
            d.rounded_rectangle([x, y, x + w, y + 44], 22, fill=GREEN if done else (LEMON if cur else CHIP_OFF))
            B.draw_text(frame, x + (w - B.text_width(lab, "mono_bold", size, 0)) / 2, y + 30, lab, "mono_bold", size,
                        WHITE if done else (INK if cur else CHIP_OFF_TEXT), 0)
            x += w + 10

    # ---- the words
    def kept_words(self, i):
        """Word positions in shot i's line that name one thing on its screen ("Set up with a partner") or one
        highlighted phrase: its pages and lines don't break inside them."""
        words = [B.norm_word(w) for w in self.E.shots[i]["words"]]
        names = list(self.screen_words(i)) + [str(h) for h in
                                              (self.E.lines.get(self.E.shots[i]["id"], {}).get("highlights") or [])]
        groups = []
        for name in names:
            seq = [w for w in (B.norm_word(x) for x in str(name).split()) if w]
            if len(seq) < 2:
                continue
            for k in range(len(words) - len(seq) + 1):
                if words[k:k + len(seq)] == seq:
                    groups.append(set(range(k, k + len(seq))))
        return groups

    def draw_words(self, frame, i, t):
        shot = self.E.shots[i]
        words, times = shot["words"], shot["times"]
        if not words or not self.pages[i]:
            return
        page = self.pages[i][0]
        for pg in self.pages[i]:
            if times[pg[0][0]][0] <= t + 0.05:
                page = pg
        highlights = {B.norm_word(w) for h in (self.E.lines.get(shot["id"], {}).get("highlights") or [])
                      for w in str(h).split()}
        lines = [[words[j] for j in line] for line in page]
        size = CAP_SIZE
        while size > 30 and any(B.text_width(" ".join(ln), "caption", size, 0) > SAFE_R - SAFE_L for ln in lines):
            size -= 4
        ys = [CAP_Y] if len(lines) == 1 else [CAP_Y - 34, CAP_Y + 30]
        d = ImageDraw.Draw(frame)
        for line, y in zip(lines, ys):
            x = (SAFE_L + SAFE_R - B.text_width(" ".join(line), "caption", size, 0)) / 2
            for w in line:
                ww = B.text_width(w, "caption", size, 0)
                if B.norm_word(w) in highlights:                  # a lemon marker behind the word
                    d.rounded_rectangle([x - 6, y - size * 0.80, x + ww + 6, y + size * 0.18], 8, fill=LEMON)
                B.draw_text(frame, x, y, w, "caption", size, TEXT, 0)
                x += B.text_width(w + " ", "caption", size, 0)

    # ---- the frame
    def zone_layer(self, i, t, stills=False):
        """Shot i's zone content at t (screen or full card) on a clear layer, with the info of where things are."""
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        info = {}
        full = [el for el in self.elements[i] if el.full]
        if full:
            u = t - self.E.shots[i]["start"]
            for el in full:
                el.draw(layer, u - el.at if not stills else 99.0, self, i)
        elif self.track[i]["screen"]:
            info = self.draw_screen(layer, i, t, stills)
        return layer, info

    def render(self, t, header=True, caption=True, stills=False):
        i = self.shot_at(t)
        shot = self.E.shots[i]
        u = t - shot["start"]
        frame = board().copy()
        if header:
            frame.alpha_composite(self.header, (0, 0))
            self.route_bar(frame, t)
        layer, _ = self.zone_layer(i, t, stills)
        if i > 0 and u < FADE and not stills:
            prev_full = any(el.full for el in self.elements[i - 1])
            cur_full = any(el.full for el in self.elements[i])
            if prev_full or cur_full:                      # a card and the screen cross-fade
                before, _ = self.zone_layer(i - 1, self.E.shots[i - 1]["end"] - 0.01)
                a = smooth(u / FADE)
                layer = Image.blend(before, layer, a)
        frame.alpha_composite(layer)
        for el in self.elements[i]:
            if not el.full:
                el.draw(frame, u - el.at if not stills else 99.0, self, i)
        if caption:
            self.draw_words(frame, i, t)
        return frame.convert("RGB")

    def render_cover(self):
        """The grid picture: the logo, the hook's words and the part the reel is about, lifted out; the whole group in
        the middle of what the profile grid shows (its 3:4 crop)."""
        cover = self.E.ep.get("post", {}).get("cover") or {}
        frame = board().copy()
        frame.alpha_composite(self.header, (0, B.COVER_HEAD))
        lines = cover.get("lines") or [self.E.ep.get("title", "")]
        sizes = [fit_size(line, "anton", 150, 940, 70) for line in lines]
        art = None
        first = next((e for e in self.track if e["screen"] and e["focus"]), None)
        if first:
            shown = self.screens[first["screen"]]
            art, _, _ = shown.lifted(first["focus"], self.state_at(shown.name, 0.0), width_px=900)
        block = sum(sz + 30 for sz in sizes) + (70 + art.height if art is not None else 0)
        y = max(460, 960 - block / 2)
        for k, (line, size) in enumerate(zip(lines, sizes)):
            y += size
            tw = B.text_width(line, "anton", size, 0)
            last = k == len(lines) - 1
            if last:
                ImageDraw.Draw(frame).rectangle([(W - tw) / 2 - 20, y + 18 - size, (W + tw) / 2 + 20, y + 30], fill=LEMON)
            B.draw_text(frame, (W - tw) / 2, y, line, "anton", size, INK if last else TEXT, 0)
            y += 30
        stamp_y = y + 10
        if art is not None:                                # lifted out as in the reel: a soft shadow, an ink and lemon edge
            ax, ay = int(round((W - art.width) / 2)), int(round(y + 70))
            sh = Image.new("L", (W, H), 0)
            ImageDraw.Draw(sh).rounded_rectangle([ax + 6, ay + 18, ax + art.width + 6, ay + art.height + 22], 26,
                                                 fill=150)
            frame.paste((0, 0, 0, 255), mask=sh.filter(ImageFilter.GaussianBlur(26)))
            d = ImageDraw.Draw(frame)
            d.rounded_rectangle([ax - 1, ay - 1, ax + art.width, ay + art.height], 21, fill=WHITE)
            B.paste(frame, art, ax, ay)
            d = ImageDraw.Draw(frame)
            d.rounded_rectangle([ax - 3, ay - 3, ax + art.width + 2, ay + art.height + 2], 23, outline=INK, width=3)
            d.rounded_rectangle([ax - 1, ay - 1, ax + art.width, ay + art.height], 21, outline=LEMON, width=4)
            stamp_y = y + 70
        if cover.get("stamp"):
            st = Hs.Sticker({"text": cover["stamp"], "x": 760, "y": stamp_y, "rot": -5, "size": 56},
                            {"seed": 1, "photos": {}})
            sticker = st.frame_image(10)
            B.paste(frame, sticker, 790 - sticker.width / 2, stamp_y - sticker.height / 2)
        return frame.convert("RGB")

    def events(self):
        ev = []
        for i, shot in enumerate(self.E.shots):
            for el in self.elements[i]:
                ev += el.sounds(shot["start"] + el.at)
            for a in self.track[i]["actions"]:
                if a.get("tap") or a.get("check"):
                    ev.append(("pop", a["t"]))
                if a.get("write"):
                    n = min(len(str(a.get("text", ""))), 14)
                    ev += [("key", a["t"] + k * TYPE_STEP) for k in range(n)]
                if a.get("open") or a.get("close"):
                    ev.append(("whoosh_soft", a["t"] + 0.12))
                if a.get("show"):
                    ev.append(("sparkle", a["t"] + 0.2))
        for run in self.runs:
            ev += [("whoosh_soft", t0 + 0.02) for t0, _, kind, _ in run["beats"] if kind == "part"]
            ev += [("whoosh", t0) for t0 in self.arrivals(run)[1 if not self.track[run["shots"][0]]["hook"] else 0:]]
        return ev

    # ---- the checks
    def check_texts(self):
        """Every word a card draws comes from its shot's card_text, and every card_text is drawn (by a card, or on the
        screen the shot shows). The screens' own words are the app's, so they may show without being listed."""
        problems = []
        shots = {s["id"]: s for s in self.E.ep["shots"]}
        for i, shot in enumerate(self.E.shots):
            allowed = list(shots[shot["id"]].get("card_text", [])) + list(shots[shot["id"]].get("motion_text", []))
            drawn = []
            for el in self.elements[i]:
                for t in el.texts():
                    if t not in allowed:
                        problems.append("{} draws \"{}\", which isn't in its card_text".format(shot["id"], t))
                    drawn.append(t)
            on_screen = " ".join(self.screen_words(i)).lower()
            for t in shots[shot["id"]].get("card_text", []):
                if t not in drawn and t.lower() not in on_screen:
                    problems.append("{}: card_text \"{}\" isn't drawn".format(shot["id"], t))
        return problems

    def screen_words(self, i):
        """The words on the screen(s) shot i shows: allowed on screen without being in its card_text."""
        e = self.track[i]
        names = {e["screen"]} | {g for _, g in e.get("goes", [])} if e["screen"] else set()
        out = []
        for name in names:
            if name in self.screens:
                spec = self.screens[name].spec
                out += K.words_of(spec) if not spec.get("src") else list((spec.get("words") or []))
        # what was typed or changed on these screens, in this line or an earlier one: it stays on the page (S12's
        # new exit date is still there when S15 shows the page again)
        end = self.E.shots[i]["end"]
        for a in [a for name in names for a in self.acts.get(name, [])] + e["actions"]:
            if a.get("t", 0.0) > end:
                continue
            if a.get("text"):
                out.append(str(a["text"]))
            if a.get("label"):
                out.append(str(a["label"]))
        return list(dict.fromkeys(out))

    def check_layout(self):
        """What the reel would show that doesn't work: a part that isn't on the screen when its line uses it, a part
        too small to read even lifted, a tap under Instagram's buttons, touches too close together, a word too long
        for the words' width. [(level, shot id, what)]"""
        out = list(self.notes)
        for i, shot in enumerate(self.E.shots):
            sid = shot["id"]
            e = self.track[i]
            if e["screen"] and e["actions"] and any(el.full for el in self.elements[i]):
                out.append(("fix", sid, "a card takes the screen's place in this line, so what its screen does can't "
                                        "be seen: give the card and the screen a line each"))
            if e["screen"]:                                  # each part on the page the line is on when it's used
                for pid, name in [(e["focus"], e["screen"])] + [(self.touch(a), self.screen_name_at(e, a["t"]))
                                                                 for a in e["actions"]]:
                    spec = self.screens[name].spec
                    ids = None if spec.get("src") else K.all_ids(spec) | set((spec.get("overlays") or {}).keys())
                    if pid and ids is not None and pid not in ids:
                        out.append(("fix", sid, "\"{}\" isn't a part of screen \"{}\": its ids are {}".format(
                            pid, name, ", ".join(sorted(ids)))))
            for page in self.pages[i]:
                for line in page:
                    text = " ".join(shot["words"][j] for j in line)
                    if B.text_width(text, "caption", 30, 0) > SAFE_R - SAFE_L:
                        out.append(("fix", sid, "a word is too long for the words' width: shorten it"))
        for run in self.runs:
            checks = set()
            for t0, t1, kind, ref in run["beats"]:
                checks.add((min(t1 - 0.05, t0 + (GLIDE if kind == "aim" else LIFT_IN) + 0.1), kind, ref))
                checks.add((t1 - 0.05, None, None))
            for a in run["acts"]:
                if a.get("tap") or a.get("write") or a.get("check"):
                    checks.add((a["t"] + 0.02, None, None))
            for t, kind, ref in sorted(checks, key=lambda c: c[0]):
                i = self.shot_at(t)
                sid = self.E.shots[i]["id"]
                if kind in ("part", "overlay", "aim") and self.screens[self.screen_name_at(self.track[i], t)].picture is None:
                    shown = self.screens[self.screen_name_at(self.track[i], t)]
                    there = ref in (shown.spec.get("overlays") or {}) if kind == "overlay" else \
                        ref in shown.boxes(self.state_at(shown.name, t))      # a menu or dialog is an overlay
                    if not there:
                        out.append(("fix", sid, "\"{}\" isn't on the screen when its line uses it (it's in a dialog "
                                                "that's closed, or on another page)".format(ref)))
                        continue
                layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                try:
                    info = self.draw_screen(layer, i, t)
                except Exception as ex:  # noqa: BLE001 — a screen that can't be drawn is a fix, not a crash
                    out.append(("fix", sid, "the screen can't be drawn at {:.1f} s: {}".format(t, ex)))
                    break
                px = info.get("text_px")
                if px is not None and px < READABLE:
                    out.append(("fix", sid, "the part in use is too small to read on a phone ({:.0f} px; {} at least): "
                                            "lift a smaller part, a row or a button, not a whole table or "
                                            "section".format(px, READABLE)))
                for (x, y) in info.get("pointers", []):
                    if x > SAFE_R and y > 1050:
                        out.append(("fix", sid, "a tap lands under Instagram's buttons (x {:.0f}, y {:.0f})".format(x, y)))
        seen, unique = set(), []
        for item in out:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique
