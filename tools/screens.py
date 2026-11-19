#!/usr/bin/env python3
"""Screens drawn from a short description, for the Focus style (tools/build_focus.py).

Muse never pastes someone else's screenshot or video frame: it studies the newest official pages and tutorials, and
describes each screen the way the app shows it now, as a list of parts top to bottom. This file draws that list as a
clean phone or laptop screen, at two or three times the reel's size so any zoom stays sharp, and knows where every part
is, so the reel can point the camera at it, tap it, and lift it out big.

    {"device": "phone", "title": "New reel", "accent": "#0095f6",
     "parts": [{"kind": "media", "text": "Write a caption…"},
               {"kind": "row", "id": "schedule", "text": "Schedule", "icon": "clock", "toggle": false},
               {"kind": "button", "id": "share", "text": "Share"}],
     "overlays": {"when": {"kind": "sheet", "title": "Schedule reel",
                           "parts": [{"kind": "row", "text": "Date", "value": "Fri, 21 Nov"},
                                     {"kind": "button", "id": "done", "text": "Done"}]}}}

A laptop screen is a browser window ("url" in its top bar) with an optional "nav" sidebar part. Part kinds: PARTS.
A part's "id" lets the reel point at it; a nav, tabs or chips item is "<part id>/<item text>".
"""
import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = Path(__file__).resolve().parent.parent / "brand" / "fonts" / "Archivo-Variable.ttf"
TXT, SUB, LINE, CARD = (17, 17, 20), (106, 110, 120), (226, 228, 234), (245, 246, 249)
WHITE, GOOD, BAD, WARN = (255, 255, 255), (36, 168, 82), (229, 57, 53), (240, 160, 30)
DEVICE = {"phone": (390, 844), "laptop": (1280, 800)}
SCALE = {"phone": 3, "laptop": 2}
PAD = {"phone": 16, "laptop": 32}
BEZEL = 14
CHROME = 52                       # a laptop's browser bar
NAV_W = 232
PARTS = ("bar", "title", "text", "row", "field", "button", "buttons", "tabs", "chips", "media", "stat", "stats",
         "section", "table", "badge", "space", "nav", "search", "check", "steps")
OVERLAYS = ("sheet", "dialog", "toast", "menu")
# what each part looks like in a description: the Focus reel prompt lists these (tools/build_prompts.py)
PART_DOCS = {
    "bar": ('{"kind": "bar", "text": "New reel", "action": "Next"}', "a phone app's top bar: its title, a back arrow, "
            "an action on the right"),
    "title": ('{"kind": "title", "text": "My website", "sub": "Data sources · My website"}', "the page's name"),
    "text": ('{"kind": "text", "text": "Send events from your server…"}', "a few lines of the page's own words"),
    "row": ('{"kind": "row", "id": "schedule", "text": "Schedule", "icon": "clock", "toggle": false}',
            "a list row: an icon, its words, and a switch (\"toggle\"), a value (\"value\": \"Off\") or an arrow"),
    "field": ('{"kind": "field", "id": "code", "label": "Test event code", "placeholder": "TEST1234"}',
              "a box to type in (\"value\" when it's filled)"),
    "button": ('{"kind": "button", "id": "save", "text": "Save", "style": "primary"}',
               "one button; style primary, secondary, danger, good or link"),
    "buttons": ('{"kind": "buttons", "items": [{"id": "partner", "text": "Set up with a partner"}, '
                '{"id": "manual", "text": "Set up manually", "style": "link"}]}', "buttons side by side"),
    "tabs": ('{"kind": "tabs", "id": "tabs", "items": ["Overview", "Test events", "Settings"], "active": "Overview"}',
             "tabs under a title"),
    "chips": ('{"kind": "chips", "id": "filter", "items": ["All", "Active", "Paused"], "active": "All"}', "small pills"),
    "media": ('{"kind": "media", "text": "Write a caption…"}', "a video or photo with its caption box"),
    "stat": ('{"kind": "stat", "id": "server", "label": "Server events", "value": "Not set up", "tone": "bad"}',
             "one status or number, big; tone good, bad or warn"),
    "stats": ('{"kind": "stats", "items": [{"id": "browser", "label": "Browser events", "value": "Active", '
              '"tone": "good"}, {"id": "server", "label": "Server events", "value": "Not set up", "tone": "bad"}]}',
              "two to four stats side by side"),
    "section": ('{"kind": "section", "id": "capi", "title": "Conversions API", "text": "…", "parts": [...]}',
                "a card on the page with its own parts inside"),
    "table": ('{"kind": "table", "id": "events", "head": ["Event", "Browser", "Server"], "rows": [["Purchase", "✓", '
              '"✓"]]}', "a table; ✓ and ✗ are drawn as marks"),
    "badge": ('{"kind": "badge", "id": "dedup", "text": "Deduplicated", "tone": "good"}', "a small status label"),
    "space": ('{"kind": "space", "h": 24}', "empty room between parts"),
    "nav": ('{"kind": "nav", "id": "nav", "text": "Events Manager", "active": "Data sources", "items": [{"text": '
            '"Overview", "icon": "grid"}, {"text": "Data sources", "icon": "server"}]}', "a laptop page's sidebar"),
    "search": ('{"kind": "search", "id": "find", "placeholder": "Search"}', "a search box"),
    "check": ('{"kind": "check", "id": "agree", "text": "I agree to the terms", "on": false}', "a checkbox with its words"),
    "steps": ('{"kind": "steps", "id": "setup", "items": ["Connect", "Verify", "Test"], "done": 1}',
              "a numbered progress list, the first \"done\" ticked"),
}
OVERLAY_DOCS = {
    "dialog": ('"partners": {"kind": "dialog", "title": "Choose a partner", "parts": [...]}',
               "a box over the dimmed page (on a phone it slides up)"),
    "sheet": ('"when": {"kind": "sheet", "title": "Schedule reel", "parts": [...]}', "a phone's panel from the bottom"),
    "menu": ('"more": {"kind": "menu", "near": "more_button", "items": [{"id": "edit", "text": "Edit"}, '
             '{"id": "delete", "text": "Delete"}]}', "a small menu under the part it opens from"),
    "toast": ('"saved": {"kind": "toast", "text": "Conversions API connected", "tone": "good"}',
              "a message that pops up for two seconds"),
}
ICONS = ("person", "pin", "clock", "gear", "search", "bell", "home", "plus", "link", "chart", "check", "lock", "globe",
         "cart", "code", "server", "browser", "eye", "calendar", "play", "share", "heart", "chat", "mail", "bolt", "doc",
         "shield", "user", "grid", "filter")


@lru_cache(maxsize=256)
def font(size, weight=500):
    f = ImageFont.truetype(str(FONT), max(1, int(round(size))))
    try:
        f.set_variation_by_axes([weight, 100])
    except Exception:  # noqa: BLE001 — a font without axes still draws
        pass
    return f


def rgb(value, default=(0, 132, 255)):
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(int(v) for v in value)
    s = str(value or "").lstrip("#")
    if len(s) == 6:
        try:
            return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
    return default


def tw(text, size, weight=500):
    return font(size, weight).getlength(str(text))


def wrap(text, size, width, weight=500):
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        nxt = (cur + " " + w).strip()
        if cur and tw(nxt, size, weight) > width:
            lines.append(cur)
            cur = w
        else:
            cur = nxt
    if cur:
        lines.append(cur)
    return lines or [""]


# ---------------------------------------------------------------- icons: a few strokes each, in points

def icon(d, kind, x, y, s, col, k=1.0):
    """Draw icon `kind` centred on (x, y) points, s = pixels per point, k = size (1 = 22 pt)."""
    r = 10 * k
    w = max(1, int(2 * s * k))
    P = lambda a, b: (int((x + a * k) * s), int((y + b * k) * s))           # noqa: E731
    box = lambda a, b, c, e: [P(a, b), P(c, e)]                             # noqa: E731
    if kind == "person" or kind == "user":
        d.ellipse(box(-6, -10, 6, 2), outline=col, width=w)
        d.arc(box(-11, 2, 11, 22), 200, 340, fill=col, width=w)
    elif kind == "pin":
        d.ellipse(box(-7, -10, 7, 4), outline=col, width=w)
        d.line([P(0, 4), P(0, 11)], fill=col, width=w)
    elif kind in ("clock", "calendar"):
        if kind == "clock":
            d.ellipse(box(-r, -r, r, r), outline=col, width=w)
            d.line([P(0, 0), P(0, -6)], fill=col, width=w)
            d.line([P(0, 0), P(5, 3)], fill=col, width=w)
        else:
            d.rounded_rectangle(box(-9, -8, 9, 10), int(3 * s * k), outline=col, width=w)
            d.line([P(-9, -2), P(9, -2)], fill=col, width=w)
    elif kind == "gear":
        d.ellipse(box(-9, -9, 9, 9), outline=col, width=w)
        d.ellipse(box(-3, -3, 3, 3), outline=col, width=w)
    elif kind in ("search", "filter"):
        if kind == "search":
            d.ellipse(box(-8, -8, 4, 4), outline=col, width=w)
            d.line([P(3, 3), P(9, 9)], fill=col, width=w)
        else:
            d.polygon([P(-9, -7), P(9, -7), P(2, 1), P(2, 8), P(-2, 6), P(-2, 1)], outline=col)
    elif kind == "bell":
        d.arc(box(-8, -9, 8, 9), 180, 360, fill=col, width=w)
        d.line([P(-8, 0), P(-8, 5), P(8, 5), P(8, 0)], fill=col, width=w)
        d.ellipse(box(-2, 6, 2, 10), outline=col, width=w)
    elif kind == "home":
        d.line([P(-9, 0), P(0, -9), P(9, 0)], fill=col, width=w)
        d.line([P(-7, -1), P(-7, 9), P(7, 9), P(7, -1)], fill=col, width=w)
    elif kind == "plus":
        d.line([P(-8, 0), P(8, 0)], fill=col, width=w)
        d.line([P(0, -8), P(0, 8)], fill=col, width=w)
    elif kind == "link":
        d.rounded_rectangle(box(-10, -5, 2, 5), int(5 * s * k), outline=col, width=w)
        d.rounded_rectangle(box(-2, -5, 10, 5), int(5 * s * k), outline=col, width=w)
    elif kind == "chart":
        for i, h in enumerate((6, 11, 16)):
            d.rectangle(box(-9 + i * 7, 8 - h, -5 + i * 7, 8), outline=col, width=w)
    elif kind == "check":
        d.line([P(-8, 0), P(-2, 6), P(8, -6)], fill=col, width=int(w * 1.3), joint="curve")
    elif kind == "lock" or kind == "shield":
        if kind == "lock":
            d.rounded_rectangle(box(-8, -2, 8, 10), int(2 * s * k), outline=col, width=w)
            d.arc(box(-5, -10, 5, 2), 180, 360, fill=col, width=w)
        else:
            d.polygon([P(0, -10), P(9, -6), P(7, 6), P(0, 10), P(-7, 6), P(-9, -6)], outline=col)
    elif kind == "globe":
        d.ellipse(box(-r, -r, r, r), outline=col, width=w)
        d.ellipse(box(-4, -r, 4, r), outline=col, width=w)
        d.line([P(-r, 0), P(r, 0)], fill=col, width=w)
    elif kind == "cart":
        d.line([P(-10, -8), P(-6, -8), P(-3, 5), P(8, 5), P(10, -4), P(-5, -4)], fill=col, width=w)
        d.ellipse(box(-3, 7, 0, 10), outline=col, width=w)
        d.ellipse(box(5, 7, 8, 10), outline=col, width=w)
    elif kind == "code":
        d.line([P(-4, -7), P(-10, 0), P(-4, 7)], fill=col, width=w)
        d.line([P(4, -7), P(10, 0), P(4, 7)], fill=col, width=w)
    elif kind == "server":
        for yy in (-8, 1):
            d.rounded_rectangle(box(-10, yy, 10, yy + 7), int(2 * s * k), outline=col, width=w)
    elif kind == "browser":
        d.rounded_rectangle(box(-10, -8, 10, 9), int(2 * s * k), outline=col, width=w)
        d.line([P(-10, -3), P(10, -3)], fill=col, width=w)
    elif kind == "eye":
        d.ellipse(box(-10, -6, 10, 6), outline=col, width=w)
        d.ellipse(box(-3, -3, 3, 3), fill=col)
    elif kind == "play":
        d.polygon([P(-5, -8), P(-5, 8), P(8, 0)], fill=col)
    elif kind == "share":
        d.line([P(0, -9), P(0, 4)], fill=col, width=w)
        d.line([P(-5, -4), P(0, -9), P(5, -4)], fill=col, width=w)
        d.line([P(-8, 0), P(-8, 9), P(8, 9), P(8, 0)], fill=col, width=w)
    elif kind == "heart":
        d.polygon([P(0, 9), P(-9, 0), P(-9, -5), P(-5, -9), P(0, -5), P(5, -9), P(9, -5), P(9, 0)], outline=col)
    elif kind == "chat":
        d.rounded_rectangle(box(-10, -8, 10, 6), int(4 * s * k), outline=col, width=w)
        d.line([P(-5, 6), P(-7, 10), P(-1, 6)], fill=col, width=w)
    elif kind == "mail":
        d.rectangle(box(-10, -7, 10, 7), outline=col, width=w)
        d.line([P(-10, -7), P(0, 1), P(10, -7)], fill=col, width=w)
    elif kind == "bolt":
        d.polygon([P(2, -10), P(-6, 2), P(0, 2), P(-2, 10), P(6, -2), P(0, -2)], fill=col)
    elif kind == "doc":
        d.rectangle(box(-7, -9, 7, 9), outline=col, width=w)
        for yy in (-3, 1, 5):
            d.line([P(-4, yy), P(4, yy)], fill=col, width=max(1, w // 2))
    elif kind == "grid":
        for a in (-9, 1):
            for b in (-9, 1):
                d.rectangle(box(a, b, a + 8, b + 8), outline=col, width=w)
    else:                                                    # unknown: a plain dot, never a crash
        d.ellipse(box(-4, -4, 4, 4), fill=col)


def tick_mark(d, x, y, s, col, k=1.0):
    icon(d, "check", x, y, s, col, k)


# ---------------------------------------------------------------- measuring parts

def part_height(p, w, device):
    """A part's height in points at width w."""
    k = p.get("kind")
    big = device == "phone"
    if k == "bar":
        return 52
    if k == "title":
        return 34 + (24 if p.get("sub") else 0)
    if k == "text":
        return 8 + 21 * len(wrap(p.get("text"), 15, w))
    if k == "row":
        return (58 if big else 52) + (18 if p.get("sub") else 0)
    if k == "field":
        return 50 + (24 if p.get("label") else 0)
    if k in ("button", "buttons"):
        return 50
    if k in ("tabs", "chips"):
        return 46
    if k == "media":
        return 212
    if k in ("stat", "stats"):
        return 96
    if k == "section":
        inner = w - 40
        h = 22 + (34 if p.get("title") else 0)
        if p.get("text"):
            h += 22 * len(wrap(p.get("text"), 15, inner)) + 8
        for c in p.get("parts") or []:
            h += part_height(c, inner, device) + 10
        return h + 12
    if k == "table":
        return 44 + 46 * len(p.get("rows") or [])
    if k == "badge":
        return 40
    if k == "toast":
        return 52
    if k == "space":
        return float(p.get("h", 16))
    if k == "search":
        return 46
    if k == "check":
        return 44
    if k == "steps":
        return 40 * len(p.get("items") or [])
    return 40


# ---------------------------------------------------------------- drawing parts

class Painter:
    """Draws one screen's parts at scale s (pixels per point) and records where each part with an id is."""

    def __init__(self, img, s, accent, state):
        self.img, self.s, self.acc, self.state = img, s, accent, state or {}
        self.d = ImageDraw.Draw(img)
        self.boxes = {}

    def S(self, *v):
        return [int(round(x * self.s)) for x in v]

    def text(self, x, y, t, size, weight=500, col=TXT, anchor="lm"):
        self.d.text(tuple(self.S(x, y)), str(t), font=font(size * self.s, weight), fill=col, anchor=anchor)

    def rect(self, x0, y0, x1, y1, r=12, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(self.S(x0, y0, x1, y1), int(r * self.s), fill=fill, outline=outline,
                                 width=max(1, int(width * self.s)) if outline else 0)

    def keep(self, pid, box):
        if pid:
            self.boxes[pid] = tuple(box)

    # each draws the part at (x, y) with width w and returns its height
    def part(self, p, x, y, w, device):
        k = p.get("kind")
        h = part_height(p, w, device)
        fn = getattr(self, "p_" + str(k), None)
        self.keep(p.get("id"), (x, y, x + w, y + h))        # the whole row, unless the part is narrower (a button,
        if fn:                                               # a badge): its painter keeps what it really drew
            fn(p, x, y, w, h, device)
        return h

    def p_bar(self, p, x, y, w, h, device):
        if p.get("back", True):
            self.text(x + 4, y + h / 2, "‹", 32, 400, self.acc)
        self.text(x + w / 2, y + h / 2, p.get("text", ""), 17, 650, TXT, "mm")
        if p.get("action"):
            self.text(x + w - 4, y + h / 2, p["action"], 16, 650, self.acc, "rm")
        self.d.line(self.S(x - 16, y + h, x + w + 16, y + h), fill=LINE, width=max(1, int(self.s)))

    def p_title(self, p, x, y, w, h, device):
        self.text(x, y + 16, p.get("text", ""), 24 if device == "laptop" else 22, 750)
        if p.get("sub"):
            self.text(x, y + 44, p["sub"], 14, 500, SUB)

    def p_text(self, p, x, y, w, h, device):
        for i, line in enumerate(wrap(p.get("text"), 15, w)):
            self.text(x, y + 14 + i * 21, line, 15, 450, SUB)

    def p_row(self, p, x, y, w, h, device):
        mid = y + (h - (18 if p.get("sub") else 0)) / 2
        chosen = p.get("id") is not None and p.get("id") in self.state.get("chosen", {}).values()
        if chosen or self.state.get("pressed", {}).get(p.get("id"), 0.0) > 0:     # a tapped row lights up
            self.rect(x - 8, y + 3, x + w + 4, y + h - 3, 10,
                      fill=tuple(int(c * 0.12 + 255 * 0.88) for c in self.acc))
        tx = x
        if p.get("icon"):
            icon(self.d, p["icon"], x + 14, mid, self.s, SUB, 0.95)
            tx = x + 40
        self.text(tx, mid, p.get("text", ""), 17 if device == "phone" else 16, 520)
        if p.get("sub"):
            self.text(tx, mid + 22, p["sub"], 13.5, 450, SUB)
        on = self.state.get("toggles", {}).get(p.get("id"), p.get("toggle"))
        if on is not None and on is not False and on is not True:
            on = bool(on)
        if p.get("toggle") is not None or p.get("id") in self.state.get("toggles", {}):
            prog = self.state.get("toggle_prog", {}).get(p.get("id"), 1.0 if on else 0.0)
            tx1 = x + w - 2
            tx0 = tx1 - 50
            col = tuple(int(LINE[i] + (GOOD[i] - LINE[i]) * prog) for i in range(3))
            self.rect(tx0, mid - 15, tx1, mid + 15, 15, fill=col)
            kx = tx0 + 15 + (50 - 30) * prog
            self.d.ellipse(self.S(kx - 13, mid - 13, kx + 13, mid + 13), fill=WHITE, outline=(214, 214, 220),
                           width=max(1, int(self.s)))
        elif p.get("value") is not None:
            self.text(x + w - (22 if p.get("chevron", True) else 2), mid, p["value"], 16, 600,
                      self.acc if p.get("tone") != "muted" else SUB, "rm")
            if p.get("chevron", True):
                self.text(x + w - 2, mid, "›", 24, 400, (190, 192, 200), "rm")
        elif chosen:                                  # the one picked from a list: a tick where the arrow was
            self.d.ellipse(self.S(x + w - 26, mid - 12, x + w - 2, mid + 12), fill=self.acc)
            tick_mark(self.d, x + w - 14, mid, self.s, WHITE, 0.6)
        elif p.get("chevron", True):
            self.text(x + w - 2, mid, "›", 24, 400, (190, 192, 200), "rm")
        if p.get("line", True):
            self.d.line(self.S(tx, y + h, x + w, y + h), fill=LINE, width=max(1, int(self.s)))

    def p_field(self, p, x, y, w, h, device):
        y0 = y
        if p.get("label"):
            self.text(x, y + 10, p["label"], 14, 600, SUB)
            y0 = y + 24
        typed = self.state.get("typed", {}).get(p.get("id"))
        # what was typed, else a value picked from a list ("label" on the field), else its own value
        val = typed if typed is not None else self.state.get("labels", {}).get(p.get("id"), p.get("value"))
        focus = p.get("id") in self.state.get("focused", set())
        self.rect(x, y0, x + w, y0 + 46, 10, fill=WHITE, outline=self.acc if focus else (200, 203, 210), width=1.5)
        if val:
            self.text(x + 14, y0 + 23, val, 16, 500, TXT)
            if focus:
                cx = x + 14 + tw(val, 16, 500) + 2
                self.d.line(self.S(cx, y0 + 12, cx, y0 + 34), fill=self.acc, width=max(1, int(2 * self.s)))
        else:
            self.text(x + 14, y0 + 23, p.get("placeholder", ""), 16, 450, (150, 153, 162))

    def _button(self, p, x, y, w, h):
        style = p.get("style", "primary")
        pressed = self.state.get("pressed", {}).get(p.get("id"), 0.0)
        k = 1 - 0.04 * pressed
        cx, cy = x + w / 2, y + h / 2
        x0, x1 = cx - w / 2 * k, cx + w / 2 * k
        y0, y1 = cy - (h - 4) / 2 * k, cy + (h - 4) / 2 * k
        label = self.state.get("labels", {}).get(p.get("id"), p.get("text", ""))
        if style == "link":
            self.text(cx, cy, label, 16, 650, self.acc, "mm")
            return
        fill = {"primary": self.acc, "danger": BAD, "good": GOOD}.get(style, WHITE)
        ink = WHITE if style in ("primary", "danger", "good") else TXT
        self.rect(x0, y0, x1, y1, 12, fill=fill, outline=None if style != "secondary" else (200, 203, 210), width=1.5)
        self.text(cx, cy, label, 16.5, 650, ink, "mm")

    def p_button(self, p, x, y, w, h, device):
        bw = w if p.get("width", "full" if device == "phone" else "auto") == "full" else max(
            120, tw(p.get("text", ""), 16.5, 650) + 44)
        bx = x if p.get("align", "left") == "left" else x + w - bw
        self._button(p, bx, y, bw, h)
        self.keep(p.get("id"), (bx, y, bx + bw, y + h))

    def p_buttons(self, p, x, y, w, h, device):
        bx = x
        for b in p.get("items") or []:
            bw = max(120, tw(b.get("text", ""), 16.5, 650) + 44)
            self._button(b, bx, y, bw, h)
            self.keep(b.get("id"), (bx, y, bx + bw, y + h))
            bx += bw + 12

    def _items(self, p, x, y, w, h, pill):
        active = self.state.get("active", {}).get(p.get("id"), p.get("active"))
        bx = x
        for it in p.get("items") or []:
            label = it if isinstance(it, str) else it.get("text", "")
            iw = tw(label, 15.5, 650) + (32 if pill else 8)
            on = label == active
            if pill:
                self.rect(bx, y + 6, bx + iw, y + h - 6, (h - 12) / 2, fill=self.acc if on else CARD,
                          outline=None if on else LINE, width=1)
                self.text(bx + iw / 2, y + h / 2, label, 15.5, 650, WHITE if on else TXT, "mm")
            else:
                self.text(bx + iw / 2, y + h / 2 - 2, label, 15.5, 650, self.acc if on else SUB, "mm")
                if on:
                    self.rect(bx, y + h - 4, bx + iw, y + h, 1, fill=self.acc)
            if p.get("id"):
                self.keep("{}/{}".format(p["id"], label), (bx, y, bx + iw, y + h))
            bx += iw + (10 if pill else 26)
        if not pill:
            self.d.line(self.S(x, y + h, x + w, y + h), fill=LINE, width=max(1, int(self.s)))

    def p_tabs(self, p, x, y, w, h, device):
        self._items(p, x, y, w, h, False)

    def p_chips(self, p, x, y, w, h, device):
        self._items(p, x, y, w, h, True)

    def p_media(self, p, x, y, w, h, device):
        thumb = Image.new("RGB", (int(120 * self.s), int(200 * self.s)))
        td = ImageDraw.Draw(thumb)
        for yy in range(thumb.height):
            u = yy / thumb.height
            td.line([0, yy, thumb.width, yy], fill=(int(250 - 40 * u), int(170 - 80 * u), int(80 + 60 * u)))
        mask = Image.new("L", thumb.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, thumb.width - 1, thumb.height - 1], int(12 * self.s), fill=255)
        self.img.paste(thumb, tuple(self.S(x, y + 4)), mask)
        icon(self.d, "play", x + 60, y + 104, self.s, WHITE, 1.4)
        if p.get("text"):
            self.text(x + 136, y + 18, p["text"], 16, 450, SUB)

    def _stat(self, p, x, y, w, h):
        self.rect(x, y + 4, x + w, y + h - 4, 14, fill=CARD)
        self.text(x + 16, y + 26, p.get("label", ""), 14, 600, SUB)
        pid = p.get("id")
        tone = {"good": GOOD, "bad": BAD, "warn": WARN}.get(self.state.get("tones", {}).get(pid, p.get("tone")), TXT)
        self.text(x + 16, y + 62, self.state.get("labels", {}).get(pid, p.get("value", "")), 30, 800, tone)
        if p.get("sub"):
            self.text(x + w - 16, y + 62, p["sub"], 13.5, 500, SUB, "rm")

    def p_stat(self, p, x, y, w, h, device):
        self._stat(p, x, y, w, h)

    def p_stats(self, p, x, y, w, h, device):
        items = p.get("items") or []
        n = max(1, len(items))
        gw = (w - 12 * (n - 1)) / n
        for i, it in enumerate(items):
            bx = x + i * (gw + 12)
            self._stat(it, bx, y, gw, h)
            self.keep(it.get("id"), (bx, y, bx + gw, y + h))

    def p_section(self, p, x, y, w, h, device):
        self.rect(x, y, x + w, y + h - 6, 16, fill=CARD)
        cy = y + 22
        if p.get("title"):
            self.text(x + 20, cy + 6, p["title"], 18, 720)
            cy += 34
        if p.get("text"):
            for i, line in enumerate(wrap(p["text"], 15, w - 40)):
                self.text(x + 20, cy + 6 + i * 22, line, 15, 450, SUB)
            cy += 22 * len(wrap(p["text"], 15, w - 40)) + 8
        for c in p.get("parts") or []:
            cy += self.part(c, x + 20, cy, w - 40, device) + 10

    def p_table(self, p, x, y, w, h, device):
        head = p.get("head") or []
        n = max(1, len(head) or len((p.get("rows") or [[]])[0]))
        first = w * 0.4 if n > 1 else w
        rest = (w - first) / max(1, n - 1)
        cols = [x] + [x + first + i * rest for i in range(n - 1)]
        self.rect(x, y, x + w, y + 40, 8, fill=CARD)
        for i, hd in enumerate(head):
            self.text(cols[i] + 14, y + 20, hd, 13.5, 700, SUB)
        for r, row in enumerate(p.get("rows") or []):
            ry = y + 44 + r * 46
            for i, cell in enumerate(row):
                cx = cols[min(i, len(cols) - 1)] + 14
                if cell in ("✓", "yes", "Yes"):
                    tick_mark(self.d, cx + 10, ry + 22, self.s, GOOD, 0.9)
                elif cell in ("✗", "no", "No"):
                    self.text(cx, ry + 22, "×", 22, 700, BAD)
                else:
                    self.text(cx, ry + 22, cell, 15, 600 if i == 0 else 500, TXT if i == 0 else SUB)
            self.d.line(self.S(x, ry + 44, x + w, ry + 44), fill=LINE, width=max(1, int(self.s)))
            if p.get("id"):
                self.keep("{}/{}".format(p["id"], row[0] if row else r), (x, ry, x + w, ry + 46))

    def p_toast(self, p, x, y, w, h, device):
        """A message that pops up ("Conversions API connected"): only ever drawn alone, lifted out of the screen."""
        self.rect(x, y, x + w, y + h, 16, fill=(30, 31, 36))
        tone = {"good": GOOD, "bad": BAD}.get(p.get("tone", "good"), GOOD)
        self.d.ellipse(self.S(x + 16, y + h / 2 - 11, x + 38, y + h / 2 + 11), fill=tone)
        tick_mark(self.d, x + 27, y + h / 2, self.s, WHITE, 0.55)
        self.text(x + 50, y + h / 2, p.get("text", ""), 15, 600, WHITE)

    def p_badge(self, p, x, y, w, h, device):
        tone = {"good": GOOD, "bad": BAD, "warn": WARN}.get(p.get("tone"), self.acc)
        bw = tw(p.get("text", ""), 15, 700) + 48
        self.rect(x, y + 4, x + bw, y + h - 4, (h - 8) / 2, fill=tuple(int(c * 0.14 + 255 * 0.86) for c in tone))
        if p.get("tone") == "good":
            tick_mark(self.d, x + 18, y + h / 2, self.s, tone, 0.7)
        self.text(x + (30 if p.get("tone") == "good" else 24), y + h / 2, p.get("text", ""), 15, 700, tone)
        self.keep(p.get("id"), (x, y, x + bw, y + h))

    def p_search(self, p, x, y, w, h, device):
        self.rect(x, y + 3, x + w, y + h - 3, (h - 6) / 2, fill=CARD)
        icon(self.d, "search", x + 22, y + h / 2, self.s, SUB, 0.8)
        typed = self.state.get("typed", {}).get(p.get("id"))
        self.text(x + 42, y + h / 2, typed or p.get("placeholder", "Search"), 15.5, 450, TXT if typed else SUB)

    def p_check(self, p, x, y, w, h, device):
        on = self.state.get("checked", {}).get(p.get("id"), bool(p.get("on")))
        self.rect(x, y + 11, x + 22, y + 33, 6, fill=self.acc if on else WHITE, outline=None if on else (180, 183, 190),
                  width=1.5)
        if on:
            tick_mark(self.d, x + 11, y + 22, self.s, WHITE, 0.6)
        self.text(x + 34, y + 22, p.get("text", ""), 16, 520)

    def p_steps(self, p, x, y, w, h, device):
        done = self.state.get("done", {}).get(p.get("id"), p.get("done", 0))
        for i, it in enumerate(p.get("items") or []):
            yy = y + i * 40 + 20
            on = i < done
            self.d.ellipse(self.S(x, yy - 12, x + 24, yy + 12), fill=GOOD if on else CARD,
                           outline=None if on else LINE)
            if on:
                tick_mark(self.d, x + 12, yy, self.s, WHITE, 0.55)
            self.text(x + 36, yy, it, 16, 520, TXT if on else SUB)

    def p_space(self, p, x, y, w, h, device):
        pass

    # ---- laptop sidebar, drawn by the screen, not in the flow
    def nav(self, p, x, y, w, h):
        self.d.rectangle(self.S(x, y, x + w, y + h), fill=(247, 248, 251))
        self.d.line(self.S(x + w, y, x + w, y + h), fill=LINE, width=max(1, int(self.s)))
        active = self.state.get("active", {}).get(p.get("id"), p.get("active"))
        if p.get("text"):
            self.text(x + 22, y + 34, p["text"], 17, 750)
        iy = y + (70 if p.get("text") else 24)
        for it in p.get("items") or []:
            label = it if isinstance(it, str) else it.get("text", "")
            ic = None if isinstance(it, str) else it.get("icon")
            on = label == active
            if on:
                self.rect(x + 10, iy, x + w - 10, iy + 40, 10, fill=tuple(int(c * 0.12 + 255 * 0.88) for c in self.acc))
            if ic:
                icon(self.d, ic, x + 32, iy + 20, self.s, self.acc if on else SUB, 0.8)
            self.text(x + (52 if ic else 26), iy + 20, label, 15.5, 650 if on else 520, self.acc if on else TXT)
            if p.get("id"):
                self.keep("{}/{}".format(p["id"], label), (x + 10, iy, x + w - 10, iy + 40))
            iy += 46


# ---------------------------------------------------------------- the whole screen

def content_box(spec):
    """Where the parts go, in points: (x0, y0, x1) inside the device."""
    dev = spec.get("device", "phone")
    W, H = DEVICE[dev]
    pad = PAD[dev]
    if dev == "laptop":
        nav = next((p for p in spec.get("parts") or [] if p.get("kind") == "nav"), None)
        x0 = (NAV_W if nav else 0) + pad
        return x0, CHROME + 28, W - pad
    top = 52 if not any(p.get("kind") == "bar" for p in spec.get("parts") or []) else 44
    return pad, top, W - pad


def layout(spec):
    """Every part's box (points), without drawing: what the reel needs to aim its camera."""
    img = Image.new("RGB", (1, 1))
    p = Painter(img, 0.0001, (0, 0, 0), {})
    return draw_parts(spec, p, measure_only=True)


def draw_parts(spec, painter, measure_only=False, scroll=0.0):
    dev = spec.get("device", "phone")
    x0, y, x1 = content_box(spec)
    y -= scroll
    W, H = DEVICE[dev]
    for part in spec.get("parts") or []:
        k = part.get("kind")
        if k == "nav":
            if not measure_only:
                painter.nav(part, 0, CHROME, NAV_W, H - CHROME)
            else:
                iy = CHROME + (70 if part.get("text") else 24)
                for it in part.get("items") or []:
                    label = it if isinstance(it, str) else it.get("text", "")
                    if part.get("id"):
                        painter.keep("{}/{}".format(part["id"], label), (10, iy, NAV_W - 10, iy + 40))
                    iy += 46
            continue
        if k == "bar":
            h = 52
            if not measure_only:
                painter.p_bar(part, x0, 44 - scroll * 0, x1 - x0, h, dev)
            painter.keep(part.get("id"), (x0, 44, x1, 44 + h))
            y = max(y, 44 + h + 12)
            continue
        if measure_only:
            h = part_height(part, x1 - x0, dev)
            painter.keep(part.get("id"), (x0, y, x1, y + h))
            _keep_children(painter, part, x0, y, x1 - x0, dev)
        else:
            h = painter.part(part, x0, y, x1 - x0, dev)
        y += h + (12 if dev == "laptop" else 8)
    return painter.boxes


def _keep_children(painter, part, x, y, w, dev):
    """Boxes of a part's own items when only measuring (the painter records them while drawing)."""
    k = part.get("kind")
    if k == "section":
        cy = y + 22 + (34 if part.get("title") else 0)
        if part.get("text"):
            cy += 22 * len(wrap(part["text"], 15, w - 40)) + 8
        for c in part.get("parts") or []:
            ch = part_height(c, w - 40, dev)
            painter.keep(c.get("id"), (x + 20, cy, x + w - 20, cy + ch))
            _keep_children(painter, c, x + 20, cy, w - 40, dev)
            cy += ch + 10
    elif k in ("tabs", "chips") and part.get("id"):
        bx = x
        for it in part.get("items") or []:
            label = it if isinstance(it, str) else it.get("text", "")
            iw = tw(label, 15.5, 650) + (32 if k == "chips" else 8)
            painter.keep("{}/{}".format(part["id"], label), (bx, y, bx + iw, y + 46))
            bx += iw + (10 if k == "chips" else 26)
    elif k == "buttons":
        bx = x
        for b in part.get("items") or []:
            bw = max(120, tw(b.get("text", ""), 16.5, 650) + 44)
            painter.keep(b.get("id"), (bx, y, bx + bw, y + 50))
            bx += bw + 12
    elif k == "button":
        bw = w if part.get("width", "full" if dev == "phone" else "auto") == "full" else max(
            120, tw(part.get("text", ""), 16.5, 650) + 44)
        bx = x if part.get("align", "left") == "left" else x + w - bw
        painter.keep(part.get("id"), (bx, y, bx + bw, y + 50))
    elif k == "stats":
        items = part.get("items") or []
        n = max(1, len(items))
        gw = (w - 12 * (n - 1)) / n
        for i, it in enumerate(items):
            painter.keep(it.get("id"), (x + i * (gw + 12), y, x + i * (gw + 12) + gw, y + 96))
    elif k == "table" and part.get("id"):
        for r, row in enumerate(part.get("rows") or []):
            ry = y + 44 + r * 46
            painter.keep("{}/{}".format(part["id"], row[0] if row else r), (x, ry, x + w, ry + 46))
    elif k == "badge":
        bw = tw(part.get("text", ""), 15, 700) + 48
        painter.keep(part.get("id"), (x, y, x + bw, y + 40))


def overlay_layout(spec, oid):
    """An overlay's parts' boxes, fully open (points in the device)."""
    ov = (spec.get("overlays") or {}).get(oid) or {}
    img = Image.new("RGB", (1, 1))
    p = Painter(img, 0.0001, (0, 0, 0), {})
    _overlay(spec, ov, p, 1.0, measure_only=True)
    return p.boxes


def _overlay_frame(spec, ov):
    """(x0, y0, x1, y1) of an overlay's panel when fully open, and the parts' left, top and width."""
    dev = spec.get("device", "phone")
    W, H = DEVICE[dev]
    kind = ov.get("kind")
    if kind == "toast":
        tw_ = min(W - 48, tw(ov.get("text", ""), 15, 600) + 80)
        y1 = H - (110 if dev == "phone" else 40)
        x0 = (W - tw_) / 2 if dev == "phone" else W - tw_ - 32
        return x0, y1 - 52, x0 + tw_, y1, None
    parts = ov.get("parts") or []
    if kind == "sheet" or (kind == "dialog" and dev == "phone"):
        w = W - 32
        h = 70 + sum(part_height(p, w, dev) + 8 for p in parts) + 30
        return 0, H - h, W, H + 30, (16, H - h + 64, w)
    if kind == "menu":
        w = ov.get("w", 260)
        h = 16 + 46 * len(ov.get("items") or [])
        return 0, 0, w, h, None
    w = min(620, W - 120)
    h = 80 + sum(part_height(p, w - 48, dev) + 10 for p in parts) + 24
    x0, y0 = (W - w) / 2, (H - h) / 2
    return x0, y0, x0 + w, y0 + h, (x0 + 24, y0 + 72, w - 48)


def _overlay(spec, ov, painter, prog, measure_only=False, anchor=None):
    dev = spec.get("device", "phone")
    W, H = DEVICE[dev]
    kind = ov.get("kind")
    x0, y0, x1, y1, inner = _overlay_frame(spec, ov)
    if kind == "menu" and anchor:
        ax0, ay0, ax1, ay1 = anchor
        mw = x1 - x0
        x0, x1 = ax0, ax0 + mw
        y0, y1 = ay1 + 6, ay1 + 6 + (y1 - y0)
    off = 0.0
    if kind in ("sheet",) or (kind == "dialog" and dev == "phone"):
        off = (1 - prog) * (y1 - y0)
    elif kind == "toast":
        off = (1 - prog) * 30
    if not measure_only:
        d = painter.d
        if kind in ("sheet", "dialog"):
            shade = Image.new("RGBA", painter.img.size, (0, 0, 0, int(95 * prog)))
            painter.img.alpha_composite(shade) if painter.img.mode == "RGBA" else None
            d = painter.d = ImageDraw.Draw(painter.img)
        if kind == "toast":
            painter.rect(x0, y0 + off, x1, y1 + off, 16, fill=(30, 31, 36))
            tone = {"good": GOOD, "bad": BAD}.get(ov.get("tone", "good"), GOOD)
            d.ellipse(painter.S(x0 + 16, y0 + off + 15, x0 + 38, y0 + off + 37), fill=tone)
            tick_mark(d, x0 + 27, y0 + off + 26, painter.s, WHITE, 0.55)
            painter.text(x0 + 50, (y0 + y1) / 2 + off, ov.get("text", ""), 15, 600, WHITE)
        elif kind == "menu":
            painter.rect(x0, y0, x1, y1, 12, fill=WHITE, outline=LINE, width=1)
            for i, it in enumerate(ov.get("items") or []):
                label = it if isinstance(it, str) else it.get("text", "")
                painter.text(x0 + 18, y0 + 8 + 46 * i + 23, label, 15.5, 520)
        else:
            r = 24 if kind == "sheet" or dev == "phone" else 16
            painter.rect(x0, y0 + off, x1, y1 + off, r, fill=WHITE)
            if kind == "sheet" or dev == "phone":
                painter.rect(W / 2 - 18, y0 + off + 9, W / 2 + 18, y0 + off + 14, 3, fill=LINE)
            painter.text((inner[0] if inner else x0 + 24), y0 + off + 42, ov.get("title", ""), 20, 720)
    if kind == "menu":
        for i, it in enumerate(ov.get("items") or []):
            label = it if isinstance(it, str) else it.get("text", "")
            iid = None if isinstance(it, str) else it.get("id")
            painter.keep(iid or "{}/{}".format(ov.get("id", "menu"), label), (x0, y0 + 8 + 46 * i, x1, y0 + 8 + 46 * (i + 1)))
        return
    if inner:
        ix, iy, iw = inner
        iy += off
        for p in ov.get("parts") or []:
            if measure_only:
                h = part_height(p, iw, dev)
                painter.keep(p.get("id"), (ix, iy, ix + iw, iy + h))
                _keep_children(painter, p, ix, iy, iw, dev)
            else:
                h = painter.part(p, ix, iy, iw, dev)
            iy += h + (10 if dev == "laptop" else 8)
    if ov.get("id"):
        painter.keep(ov["id"], (x0, y0 + off, x1, y1 + off))


def render(spec, state=None, scale=None):
    """The screen at its state: (RGBA image of the device with its frame, boxes {id: (x0, y0, x1, y1) points inside the
    device's screen}, (ox, oy) the screen's top left in the image, in pixels, and s, pixels per point).

    state: {"toggles": {id: bool}, "toggle_prog": {id: 0..1}, "typed": {id: text}, "focused": {id}, "active": {id: item},
            "pressed": {id: 0..1}, "labels": {id: text}, "checked": {id: bool}, "done": {id: n},
            "open": {overlay id: 0..1}, "scroll": points}"""
    state = state or {}
    dev = spec.get("device", "phone")
    s = scale or SCALE[dev]
    W, H = DEVICE[dev]
    acc = rgb(spec.get("accent"))
    scr = Image.new("RGBA", (int(W * s), int(H * s)), WHITE + (255,))
    painter = Painter(scr, s, acc, state)
    d = painter.d
    if dev == "laptop":
        d.rectangle(painter.S(0, 0, W, CHROME), fill=(236, 237, 241))
        for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
            d.ellipse(painter.S(18 + i * 22, 20, 30 + i * 22, 32), fill=c)
        if spec.get("url"):
            painter.rect(110, 12, W - 110, 40, 14, fill=WHITE)
            icon(d, "lock", 132, 26, s, SUB, 0.55)
            typed = state.get("typed", {}).get("url")
            painter.text(148, 26, typed if typed is not None else spec["url"], 14.5, 500, TXT)
            painter.keep("url", (110, 12, W - 110, 40))
    else:
        painter.text(30, 24, "9:41", 15, 650)
        painter.rect(W / 2 - 55, 11, W / 2 + 55, 41, 15, fill=(12, 12, 14))
    boxes = draw_parts(spec, painter, scroll=float(state.get("scroll", 0.0)))
    for oid, ov in (spec.get("overlays") or {}).items():
        prog = float(state.get("open", {}).get(oid, 0.0))
        if prog > 0.001:
            anchor = boxes.get(ov.get("near")) if ov.get("near") else None
            _overlay(spec, dict(ov, id=oid), painter, prog, anchor=anchor)
    boxes = dict(painter.boxes)
    if dev == "phone":
        out = Image.new("RGBA", (int((W + 2 * BEZEL) * s), int((H + 2 * BEZEL) * s)), (0, 0, 0, 0))
        od = ImageDraw.Draw(out)
        od.rounded_rectangle([0, 0, out.width - 1, out.height - 1], int((46 + BEZEL) * s), fill=(20, 20, 24))
        od.rounded_rectangle([2, 2, out.width - 3, out.height - 3], int((46 + BEZEL) * s), outline=(70, 72, 84),
                             width=max(1, int(2 * s)))
        mask = Image.new("L", scr.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, scr.width - 1, scr.height - 1], int(46 * s), fill=255)
        out.paste(scr, (int(BEZEL * s), int(BEZEL * s)), mask)
        return out, boxes, (int(BEZEL * s), int(BEZEL * s)), s
    out = Image.new("RGBA", scr.size, (0, 0, 0, 0))
    mask = Image.new("L", scr.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, scr.width - 1, scr.height - 1], int(14 * s), fill=255)
    out.paste(scr, (0, 0), mask)
    return out, boxes, (0, 0), s


def boxes_of(spec, state=None):
    """Every part's box (points) at a state, overlays included, without the cost of drawing at full size."""
    return render(spec, state, scale=0.25)[1]


def overlay_of(spec, pid):
    """The overlay (dialog, sheet, menu) a part sits in, or None when it's on the page itself."""
    def has(parts):
        for p in parts or []:
            if isinstance(p, dict) and (p.get("id") == pid or has(p.get("parts")) or any(
                    isinstance(c, dict) and c.get("id") == pid for c in p.get("items") or [])):
                return True
        return False
    for oid, ov in (spec.get("overlays") or {}).items():
        if has(ov.get("parts")) or any(isinstance(it, dict) and it.get("id") == pid for it in ov.get("items") or []):
            return oid
    return None


def find_part(spec, pid):
    """The part (or overlay part, or item) a target id names, or None."""
    item_kind = {"buttons": "button", "stats": "stat"}

    def walk(parts):
        for p in parts or []:
            if p.get("id") == pid:
                return p
            for c in p.get("items") or []:             # a button in a row of buttons is a button, and so on
                if isinstance(c, dict) and c.get("id") == pid:
                    return dict(c, kind=c.get("kind") or item_kind.get(p.get("kind"), "row"))
            found = walk([c for c in p.get("parts") or [] if isinstance(c, dict)])
            if found:
                return found
        return None
    hit = walk(spec.get("parts"))
    if hit:
        return hit
    for oid, ov in (spec.get("overlays") or {}).items():
        if oid == pid:
            return dict(ov, kind=ov.get("kind"))
        hit = walk(ov.get("parts"))
        if hit:
            return hit
        for it in ov.get("items") or []:
            if isinstance(it, dict) and it.get("id") == pid:
                return dict(it, kind="row")
    if "/" in str(pid):
        owner, item = str(pid).split("/", 1)
        for p in spec.get("parts") or []:
            if p.get("id") == owner:
                return {"kind": "row", "text": item, "chevron": False}
        for oid, ov in (spec.get("overlays") or {}).items():
            if oid == owner:
                return {"kind": "row", "text": item, "chevron": False}
    if pid == "url" and spec.get("url"):
        return {"kind": "field", "value": spec["url"]}
    return None


def owner_of(spec, pid):
    """An "owner/item" id's owner when it's a row of items the viewer should see switch (tabs, chips, a sidebar, a
    table) and the item: (part, item) or (None, None)."""
    if "/" not in str(pid):
        return None, None
    owner, item = str(pid).split("/", 1)

    def walk(parts):
        for p in parts or []:
            if isinstance(p, dict):
                if p.get("id") == owner:
                    return p
                found = walk(p.get("parts"))
                if found:
                    return found
        return None
    found = walk(spec.get("parts"))
    for ov in (spec.get("overlays") or {}).values():
        found = found or walk(ov.get("parts"))
    if found and found.get("kind") in ("tabs", "chips", "nav", "table"):
        return found, item
    return None, None


def lifted(spec, pid, state=None, width_px=860, text_px=40):
    """The part `pid`, drawn alone and big on a white card for the reel to lift out: as wide as width_px at most, its
    body text text_px tall where it fits. A laptop part is laid out again at a phone's width, so its words grow instead
    of the card. A tab, a chip, a sidebar link or a table row comes with its neighbours (the tabs around it, the
    table's head), so the switch from one to the other shows.
    Returns (RGBA image, its body text's height in px, the touched item's box in the image or None), or (None, 0,
    None)."""
    owner, item = owner_of(spec, pid)
    if owner is not None:
        return _lifted_owner(spec, owner, item, state or {}, width_px, text_px)
    part = find_part(spec, pid)
    if part is None:
        return None, 0, None
    part = dict(part)
    kind = part.get("kind")
    if kind in ("row", "field", "button", "check", "search"):
        part["id"] = pid                             # its state (a toggle, typed words, a pressed button) follows it
    w_pt = 520 if kind in ("stats", "table", "buttons", "section") else 358
    if kind == "button":
        part["width"] = "full"
        w_pt = max(180, min(358, tw(part.get("text", ""), 16.5, 650) + 90))
    elif kind == "badge":                             # a small thing gets a small card, not a wide empty one
        w_pt = tw(part.get("text", ""), 15, 700) + 56
    elif kind == "toast":
        w_pt = min(358, tw(part.get("text", ""), 15, 600) + 70)
    elif kind == "row" and part.get("toggle") is None and part.get("value") is None and not part.get("icon"):
        w_pt = max(150, min(358, tw(part.get("text", ""), 17, 520) + 60))
    s = min(width_px / (w_pt + 32), text_px / 16.5)
    h_pt = part_height(part, w_pt, "phone")
    img = Image.new("RGBA", (int((w_pt + 32) * s), int((h_pt + 28) * s)), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([0, 0, img.width - 1, img.height - 1], int(20 * s), fill=WHITE + (255,))
    Painter(img, s, rgb(spec.get("accent")), state or {}).part(part, 16, 14, w_pt, "phone")
    return img, 16.5 * s, None


def _lifted_owner(spec, owner, item, state, width_px, text_px):
    kind = owner["kind"]
    part = dict(owner)
    items = owner.get("items") or []
    labels = [it if isinstance(it, str) else it.get("text", "") for it in items]
    if kind in ("tabs", "chips"):
        pill = kind == "chips"
        widths = [tw(lab, 15.5, 650) + (32 if pill else 8) for lab in labels]
        gap = 10 if pill else 26

        def span(a, b):
            return sum(widths[a:b]) + gap * max(0, b - a - 1)
        lo = labels.index(item) if item in labels else 0
        hi = lo + 1
        grew = True
        while grew:                                  # the item and as many neighbours as a phone's width holds
            grew = False
            if hi < len(labels) and span(lo, hi + 1) <= 358:
                hi, grew = hi + 1, True
            if lo > 0 and span(lo - 1, hi) <= 358:
                lo, grew = lo - 1, True
        part["items"] = items[lo:hi]
        w_pt = max(span(lo, hi), 120)
        h_pt = part_height(part, w_pt, "phone")
    elif kind == "nav":
        w_pt = NAV_W
        h_pt = (70 if owner.get("text") else 24) + 46 * len(labels)
    else:                                            # a table: its head and the item's row
        rows = owner.get("rows") or []
        part["rows"] = [r for r in rows if r and str(r[0]) == item] or rows[:1]
        w_pt = 358
        h_pt = part_height(part, w_pt, "phone")
    s = min(width_px / (w_pt + 32), text_px / 16.5)
    img = Image.new("RGBA", (int((w_pt + 32) * s), int((h_pt + 28) * s)), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle([0, 0, img.width - 1, img.height - 1], int(20 * s), fill=WHITE + (255,))
    painter = Painter(img, s, rgb(spec.get("accent")), state)
    if kind == "nav":
        painter.nav(part, 16, 14, w_pt, h_pt)
    else:
        painter.part(part, 16, 14, w_pt, "phone")
    box = painter.boxes.get("{}/{}".format(owner.get("id"), item))
    return img, 16.5 * s, (tuple(v * s for v in box) if box else None)


def labels_of(spec):
    """The names a screen gives its parts (buttons, tabs, sidebar and menu items, section, field and stat labels,
    table heads, dialog titles): what the newest official pages should say too. Not example values, body text or the
    page's own name."""
    out = []

    def add(t):
        t = " ".join(str(t or "").split())
        if len(t) > 1 and not re.fullmatch(r"[\d\s.,%₹$:/+-]+", t):
            out.append(t)

    def walk(parts):
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            k = p.get("kind")
            if k in ("button", "row", "check", "badge"):
                add(p.get("text"))
            elif k == "section":
                add(p.get("title"))
            elif k in ("field", "stat"):
                add(p.get("label"))
            elif k == "nav":
                add(p.get("text"))
            for it in p.get("items") or []:
                add(it if isinstance(it, str) else (it.get("text") or it.get("label")) if isinstance(it, dict) else None)
            for h in p.get("head") or []:
                add(h)
            walk([c for c in p.get("parts") or [] if isinstance(c, dict)])
    walk(spec.get("parts"))
    for ov in (spec.get("overlays") or {}).values():
        if ov.get("kind") != "toast":
            add(ov.get("title"))
        walk(ov.get("parts"))
        for it in ov.get("items") or []:
            add(it if isinstance(it, str) else it.get("text") if isinstance(it, dict) else None)
    return list(dict.fromkeys(out))


def check_spec(spec, sid="screen"):
    """Problems in a screen's description: unknown kinds, a laptop part on a phone, ids used twice."""
    out = []
    dev = spec.get("device", "phone")
    if dev not in DEVICE and not spec.get("src"):
        out.append("{}: device must be \"phone\" or \"laptop\", not \"{}\"".format(sid, dev))
        return out
    seen = set()

    def walk(parts, where):
        for p in parts or []:
            if not isinstance(p, dict):
                out.append("{}: every part is an object like {{\"kind\": \"row\", \"text\": \"...\"}}".format(where))
                continue
            k = p.get("kind")
            if k not in PARTS:
                out.append("{}: part kind \"{}\" isn't one the screens can draw: {}".format(where, k, ", ".join(PARTS)))
            if k == "nav" and dev != "laptop":
                out.append("{}: a nav sidebar is a laptop part".format(where))
            if k == "bar" and dev != "phone":
                out.append("{}: a bar is a phone part (a laptop page has its url and title)".format(where))
            if p.get("icon") and p["icon"] not in ICONS:
                out.append("{}: icon \"{}\" isn't drawn: {}".format(where, p["icon"], ", ".join(ICONS)))
            pid = p.get("id")
            if pid:
                if pid in seen:
                    out.append("{}: id \"{}\" is used twice".format(where, pid))
                seen.add(pid)
            walk([c for c in p.get("parts") or [] if isinstance(c, dict)], where)
            if k in ("buttons", "stats"):
                walk([dict(c, kind="button" if k == "buttons" else "stat") for c in p.get("items") or []
                      if isinstance(c, dict)], where)
    walk(spec.get("parts"), sid)
    for oid, ov in (spec.get("overlays") or {}).items():
        if ov.get("kind") not in OVERLAYS:
            out.append("{}: overlay \"{}\" kind must be one of {}".format(sid, oid, ", ".join(OVERLAYS)))
        if oid in seen:
            out.append("{}: id \"{}\" is used twice".format(sid, oid))
        seen.add(oid)
        walk(ov.get("parts"), "{} → {}".format(sid, oid))
    return out


def all_ids(spec):
    """Every id the reel can point at on this screen (parts, items, overlays and their parts)."""
    ids = set(boxes_of(spec).keys())
    for oid, ov in (spec.get("overlays") or {}).items():
        ids.add(oid)
        ids |= set(overlay_layout(spec, oid).keys())
    if spec.get("url"):
        ids.add("url")
    return ids


def words_of(spec):
    """Every word a screen shows (its labels, values, titles): what the OCR and the sources check may read on it."""
    out = []

    def add(t):
        if t:
            out.append(str(t))

    def walk(parts):
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            for key in ("text", "title", "sub", "label", "value", "placeholder", "action"):
                add(p.get(key))
            for it in p.get("items") or []:
                if isinstance(it, dict):
                    for key in ("text", "label", "value"):
                        add(it.get(key))
                else:
                    add(it)
            for row in p.get("rows") or []:
                for c in row:
                    add(c)
            for h in p.get("head") or []:
                add(h)
            walk([c for c in p.get("parts") or [] if isinstance(c, dict)])
    add(spec.get("title"))
    add(spec.get("url"))
    walk(spec.get("parts"))
    for ov in (spec.get("overlays") or {}).values():
        add(ov.get("title"))
        add(ov.get("text"))
        walk(ov.get("parts"))
        for it in ov.get("items") or []:
            add(it if isinstance(it, str) else it.get("text"))
    return out
