#!/usr/bin/env python3
"""The Host style: avatars present from the bottom of the screen while cards appear above them.

tools/build_reel.py builds an episode in this style when its episode.json says "style": "host":

    python3 tools/build_reel.py styles/host/sample

What it reads:
- episode.json: the script (every line names its "speaker"), "cast" (role → an avatar kit in brand/avatars/), the
  card text of every shot;
- reel.json: what each shot shows ("shots": cards, poses, framing) and "progress" (the steps bar);
- the avatar kits (tools/avatars.py, styles/host/AVATAR-KIT.md) and the voice lines.

The avatar is a cut-out: one picture per pose, with the mouth and the eyes swapped on top. The pose comes from
reel.json; the mouth follows the loudness of the speaker's voice line (or a syllable rhythm when there's no voice
yet); the eyes blink every few seconds. Every word on screen comes from the shot's card_text, as in the Paper style.

Every line's feeling (its "emotion" in the script, tools/emotion.py) shows a little on its speaker: a mark by the head,
the speech bubble's edge, a small move, and a pose that fits it when the line sets none (tools/emotion_art.py).
"""
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

import avatars
import build_reel as B
import emotion
import emotion_art as EA

W, H, FPS, SR = B.W, B.H, B.FPS, B.SR
INK, LEMON, RED = B.INK, B.LEMON, B.RED
BG = (246, 243, 236)
DOT = (214, 208, 197)
WHITE = (255, 255, 255)
SOFT = (234, 230, 222)
MUTED = (150, 144, 135)
FILL = {"lemon": (LEMON, INK), "ink": (INK, WHITE), "white": (WHITE, INK), "red": (RED, WHITE), "soft": (SOFT, INK)}


def use_brand():
    """The colours of the episode being built (build_reel.use_brand): a client's reel is in the client's colours."""
    global INK, LEMON, RED
    INK, LEMON, RED = B.INK, B.LEMON, B.RED
    FILL.update({"lemon": (LEMON, INK), "ink": (INK, WHITE), "white": (WHITE, INK), "red": (RED, WHITE), "soft": (SOFT, INK)})
PILL_Y = 400
CARD_TOP = 466
CAP_SIZE = 52                 # the spoken words in the bubble: big enough to read at a glance on a phone
CAP_LINE = 64                 # the height of a bubble's line
CAP_WRAP = 470                # the width of a bubble's line
HEADLINE_Y = 590              # the hook's giant words: the middle of the card zone
OPEN = 0.45                   # the reel's first moment: the frame punches in from 107%, so it moves from frame one
LAYOUTS = {1: [(330, 0.80)], 2: [(262, 0.70), (818, 0.70)], 3: [(190, 0.56), (540, 0.56), (890, 0.56)]}
CLOSE = (540, 0.98)           # the call-to-action framing: one avatar, big and centred
TURN = 0.24                   # seconds an avatar takes to turn to another view (Chatur facing us)
CARDS_BOTTOM = 960            # cards stay above this; the avatars and their speech bubbles are below it
# Instagram draws its own things over a reel: the username, caption and audio over about the bottom 340 px, and the
# like, comment and share buttons down the right edge beside the speech bubble. Faces and spoken words stay clear.
STAGE_LIFT = 90               # the avatars stand this far up at the two-avatar scale, so their mouths clear the caption
STAGE_FADE = (1690, 1800)     # under them the board fades back in (clear at the first y, solid from the second)
SAFE_RIGHT = 940              # the speech bubble's words stay left of Instagram's buttons
HEAD_GAP = 8                  # between the bubble's tail and the top of the speaker's head
ZONE = (40, 400, 1040, CARDS_BOTTOM)   # where a shot's cards go: left, top, right, bottom
GAP = 22                      # between a card and the one the layout puts it under
LEAST = 0.6                   # the most the layout shrinks a shot's cards to fit them on the board
SHUT_EYES = {"drink"}         # poses drawn with the eyes shut: no blinking over them
FEEL_POSE = 1.8               # seconds a feeling's own pose holds (when the line sets none) before the speaker talks on
FEEL_LAG = 0.12               # a line's feeling shows this long after its shot starts, with its first words
MARK_SIZE = 120               # a feeling's mark by the head, at the two-avatar scale (0.7)
BM = 18                       # room around a speech bubble's box for its feeling's edge (spikes, bursting lines)

# Mouth shapes from the voice text (Devanagari): every syllable is a consonant shape, then a vowel shape.
LIPS = set("पफबभमव")                     # lips together: p, b, m (and the v/w of व as the lips meet)
FV = {"फ़", "व़"}                          # f: top teeth on the bottom lip
TONGUE = set("लळ")
VOWEL_SHAPE = {"ा": "wide", "आ": "wide", "ि": "teeth", "ी": "teeth", "इ": "teeth", "ई": "teeth", "े": "open",
               "ै": "open", "ए": "open", "ऐ": "open", "ु": "oo", "ू": "oo", "उ": "oo", "ऊ": "oo", "ो": "round",
               "ौ": "round", "ओ": "round", "औ": "round", "ॉ": "round", "ऑ": "round", "ृ": "teeth", "अ": "open"}


def visemes(word):
    """The mouth shapes for one Devanagari word, in order: "पंद्रह" → closed, open, teeth, teeth, open."""
    out, i, n = [], 0, len(word)
    while i < n:
        c = word[i]
        if c in VOWEL_SHAPE:                                  # a vowel on its own (अ, आ, इ …)
            out.append(VOWEL_SHAPE[c])
            i += 1
            continue
        if "\u0915" <= c <= "\u0939" or "\u0958" <= c <= "\u095f":
            j = i + 1
            nukta = j < n and word[j] == "\u093c"
            if nukta:
                j += 1
            if c + ("\u093c" if nukta else "") in FV or c == "\u095e":
                shape = "fv"
            elif c in LIPS:
                shape = "closed"
            elif c in TONGUE:
                shape = "tongue"
            else:
                shape = "teeth"
            out.append(shape)
            if j < n and word[j] == "\u094d":                 # halant: a cluster, no vowel of its own
                i = j + 1
                continue
            if j < n and word[j] in VOWEL_SHAPE:
                out.append(VOWEL_SHAPE[word[j]])
                j += 1
            elif any("\u0915" <= x <= "\u0939" or "\u0958" <= x <= "\u095f" or x in VOWEL_SHAPE for x in word[j:]):
                out.append("open")                           # the "a" every consonant carries…
            # …except at the end of a word, where Hindi drops it: मिनट is "minat"
            i = j
            continue
        i += 1                                               # ं ँ ः, punctuation: no shape of their own
    return out


# ---------------------------------------------------------------- drawing helpers

def tw(s, size, key="caption"):
    return B.text_width(s, key, size)


def panel(w, h, fill=WHITE, outline=None, radius=30, width=5):
    outline = INK if outline is None else outline
    img = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
    k = width // 2
    ImageDraw.Draw(img).rounded_rectangle([k, k, w - 1 - k, h - 1 - k], radius=radius, fill=fill, outline=outline, width=width)
    return img


def centred(img, cx, base, s, size, fill=None, key="caption"):
    B.draw_text(img, cx - tw(s, size, key) / 2, base, s, key, size, INK if fill is None else fill)


def wrap_text(s, size, width, key="caption"):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and tw(trial, size, key) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    return lines + ([cur] if cur else [])


@lru_cache(maxsize=8192)
def fit_size(s, size, width, key="caption", least=None):
    """The biggest size, up to `size`, at which `s` is at most `width` pixels wide, but never under `least` (by default
    half of `size`): so no text spills out of its card."""
    s, size = str(s), int(size)
    least = int(least) if least else max(12, size // 2)
    if not s or width <= 0 or tw(s, size, key) <= width:
        return size
    k = max(least, min(size, int(size * width / max(1.0, tw(s, size, key)))))
    while k > least and tw(s, k, key) > width:
        k -= 1
    return k


def _hits(a, b, slack=2):
    """Do two boxes (x0, y0, x1, y1) overlap by more than a hair?"""
    return a[0] < b[2] - slack and a[2] > b[0] + slack and a[1] < b[3] - slack and a[3] > b[1] + slack


def _overlap(a, b):
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _area(a):
    return max(1.0, (a[2] - a[0]) * (a[3] - a[1]))


def _together(a, b):
    """Are two of a shot's elements on screen at the same time?"""
    def until(e):
        return e.out["at"] + 0.35 if e.out else 1e9
    return a.at < until(b) and b.at < until(a)


def _kind(el):
    return {"NumberCard": "number card", "Sticker": "sticker", "Pill": "pill", "Checklist": "checklist",
            "Steps": "steps card", "Search": "search card", "Chat": "chat", "Bars": "bar chart", "Tiles": "tiles",
            "TaskGrid": "grid", "Timer": "timer", "Picture": "picture card", "Outro": "outro card",
            "Shiny": "coin card", "Chalk": "chalk", "Sticky": "sticky note", "Annotate": "mark"}.get(
        type(el).__name__, type(el).__name__.lower())


def _describe(el):
    texts = [t for t in el.texts() if t]
    return "the {} \"{}\"".format(_kind(el), texts[0]) if texts else "the " + _kind(el)


def tick(d, cx, cy, r, fill=None, mark=None):
    fill, mark = (LEMON if fill is None else fill), (INK if mark is None else mark)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=INK, width=4)
    d.line([(cx - r * 0.45, cy + r * 0.02), (cx - r * 0.1, cy + r * 0.38), (cx + r * 0.5, cy - r * 0.38)], fill=mark,
           width=max(4, int(r * 0.22)), joint="curve")


def cross(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED, outline=INK, width=4)
    k = r * 0.38
    for a, b in (((cx - k, cy - k), (cx + k, cy + k)), ((cx - k, cy + k), (cx + k, cy - k))):
        d.line([a, b], fill=WHITE, width=max(4, int(r * 0.22)))


def ease(p):
    return B.ease_out_cubic(min(1.0, max(0.0, p)))


# ---------------------------------------------------------------- cards

class HostElement(B.Element):
    """A card in the Host style. Positions: x is the centre; y the top (anchor "top") or the centre.
    block: a card the layout keeps clear of the others (labels, marks and effects aren't). shrink: how much the layout
    had to shrink it to fit the board. shrunk: the texts drawn smaller than asked, so they fit their card."""
    entrance = "pop"
    handwritten = False
    block = True

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.y = spec.get("y", CARD_TOP)
        self.w = int(spec.get("w", 860))
        self.shrink = 1.0
        self.shrunk = {}

    def fitted(self, s, size, width, key="caption", least=None):
        """fit_size, remembering a text that had to shrink a lot, for the layout report."""
        k = fit_size(str(s), int(size), float(width), key, least)
        if k < size * 0.8 or tw(str(s), k, key) > width + 1:
            self.shrunk[str(s)] = (round(k / size, 2), tw(str(s), k, key) <= width + 1)
        return k

    # the layout's view of the card: its size, its box, moving and shrinking it
    def size0(self):
        if not hasattr(self, "_size0"):
            self._size0 = self.art(10_000).size
        w, h = self._size0
        return w * self.shrink, h * self.shrink

    def box(self):
        """(x0, y0, x1, y1) on the frame once it's in place, turned by its rotation."""
        cx, cy = self.centre()
        w, h = self.size0()
        a = math.radians(abs(self.rot or 0))
        w, h = w * math.cos(a) + h * math.sin(a), w * math.sin(a) + h * math.cos(a)
        return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2

    def move_to(self, x0, y0):
        """Put the card's box with its top-left corner at (x0, y0)."""
        bx0, by0, _, _ = self.box()
        self.x += x0 - bx0
        self.y += y0 - by0

    def frame_image(self, u):
        img = super().frame_image(u)
        if self.shrink >= 0.999:
            return img
        size = (max(1, int(img.width * self.shrink)), max(1, int(img.height * self.shrink)))
        if u >= self.animated_until():
            cached = getattr(self, "_shrunk_final", None)
            if cached is None or cached[0] is not img:
                cached = (img, img.resize(size, Image.LANCZOS))
                self._shrunk_final = cached
            return cached[1]
        return img.resize(size, Image.LANCZOS)

    def finish(self, art):
        if not self.spec.get("shadow", True):
            return B.rotated(art, self.rot)
        return B.rotated(B.shadowed(art, offset=(0, 10), blur=18, opacity=0.2), self.rot)

    def items(self, key="items", gap=0.4, first=0.3):
        """[(item, its time from the card's start)]: on its word ("on", which the reel turned into "on_t", seconds from
        the shot's start: the card itself is up first), at its "at", or one after another."""
        out = []
        for k, it in enumerate(self.spec.get(key, [])):
            it = it if isinstance(it, dict) else {"text": it}
            if "on_t" in it:
                t = max(0.15, it["on_t"] - self.at)
                if out and t < out[-1][1] + 0.25:        # two words said before the card is up: still one by one
                    t = out[-1][1] + 0.25
            elif "at" in it:
                t = it["at"]
            else:
                t = first + gap * k
            out.append((it, t))
        return out

    def last_item(self, key="items"):
        times = [t for _, t in self.items(key)]
        return (max(times) + 0.45) if times else 0.0

    def sounds(self, t0):
        out = super().sounds(t0)
        out += [("pop", t0 + t) for _, t in self.items()]
        return out


class Pill(HostElement):
    """The beat's name above the cards."""
    anchor = "center"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.y = spec.get("y", PILL_Y)

    def texts(self):
        return [self.spec["text"]]

    block = False

    def art(self, u):
        size = self.fitted(self.spec["text"], 30, 900, least=20)
        fill, fg = FILL[self.spec.get("style", "lemon")]
        img = panel(tw(self.spec["text"], size) + 60, 62, fill, INK, 31, 4)
        centred(img, img.width / 2, 31 + size * 0.4, self.spec["text"], size, fg)
        return img

    def sounds(self, t0):
        return [] if self.anim == "none" else [("pop", t0)]


class Headline(HostElement):
    """The hook in giant words, for the reel's first frame: the viewer judges the reel on it before a word is said.
    Drawn the way the cover draws its lines, straight on the board (dark words on a light board, white on a dark one),
    with the words in "accent", or else the last line, on a block of the account's colour."""
    entrance = "slam"
    anchor = "center"

    def __init__(self, spec, ctx):
        if "text" not in spec and spec.get("lines"):        # written as the Paper style's headline: its lines, joined
            spec["text"] = " ".join(str(x) for x in spec["lines"])
        super().__init__(spec, ctx)
        self.y = spec.get("y", HEADLINE_Y)

    def texts(self):
        return [self.spec["text"]]

    def rows(self):
        """(lines, size): as big as fits in at most "lines" rows, with no word wider than the card."""
        text = str(self.spec["text"])
        width = min(int(self.spec.get("w", 960)), 980)
        asked, most = int(self.spec.get("size", 140)), int(self.spec.get("lines", 3))
        size = asked
        while size > 64:
            rows = wrap_text(text, size, width, "anton")
            if len(rows) <= most and all(tw(w, size, "anton") <= width for w in text.split()):
                break
            size -= 4
        if size < asked * 0.8:
            self.shrunk[text] = (round(size / asked, 2), True)
        return self.wrapped(text, size, width), size

    def wrapped(self, text, size, width):
        """The headline's rows. When the usual wrap would cut the accent phrase across two rows, the phrase starts a
        row of its own instead, if that takes no more rows."""
        rows = wrap_text(text, size, width, "anton")
        words = text.split()
        want = [w.strip(",.?!:").upper() for w in str(self.spec.get("accent") or "").split()]
        plain = [w.strip(",.?!:").upper() for w in words]
        at = next((k for k in range(len(words) - len(want) + 1) if want and plain[k:k + len(want)] == want), None)
        if at is None or at == 0:
            return rows
        row_of, n = [], 0
        for r, row in enumerate(rows):
            row_of += [r] * len(row.split())
        if len(set(row_of[at:at + len(want)])) <= 1:
            return rows
        alt = wrap_text(" ".join(words[:at]), size, width, "anton") + wrap_text(" ".join(words[at:]), size, width, "anton")
        first = alt[len(wrap_text(" ".join(words[:at]), size, width, "anton"))].split()
        return alt if len(alt) <= len(rows) and len(first) >= len(want) else rows

    SWEEP = (0.3, 0.6)      # the colour block sweeps across its words between these seconds: every word is readable
    #                         from the first frame, and the hook's key words move while the thumb is deciding

    def animated_until(self):
        return max(super().animated_until(), self.SWEEP[1] + 0.04)

    def art(self, u):
        lit = self.words(True)
        if u >= self.SWEEP[1]:
            return lit
        plain = self.words(False)
        p = B.ease_out_cubic(max(0.0, (u - self.SWEEP[0]) / (self.SWEEP[1] - self.SWEEP[0])))
        edge = int(lit.width * p)
        if edge > 0:
            plain.paste(lit.crop((0, 0, edge, lit.height)), (0, 0))
        return plain

    def words(self, blocks):
        """The headline's picture: with its colour block under the accent words, or (blocks False) every word plain."""
        rows, size = self.rows()
        accent = {w.strip(",.?!:").upper() for w in str(self.spec.get("accent") or "").split()}
        fg = WHITE if self.ctx.get("dark") else INK
        space, lh, pad = tw(" ", size, "anton"), int(size * 1.16), 18
        widths = [tw(r, size, "anton") for r in rows]
        img = Image.new("RGBA", (int(max(widths) + 2 * pad + 24), int(lh * len(rows) + 2 * pad)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for k, (row, rw) in enumerate(zip(rows, widths)):
            base = pad + k * lh + size * 0.9
            x = (img.width - rw) / 2
            whole = not accent and k == len(rows) - 1          # no accent given: the last line goes on the block
            placed = []                                         # (x, width, word, on the block)
            for w in row.split():
                ww = tw(w, size, "anton")
                placed.append((x, ww, w, blocks and (whole or w.strip(",.?!:").upper() in accent)))
                x += ww + space
            run = []
            for item in placed + [(0, 0, "", False)]:           # one block under each run of accent words: no seams
                if item[3]:
                    run.append(item)
                    continue
                if run:
                    boxes = [B.ink_box(w, "anton", size) for _, _, w, _ in run]
                    d.rectangle([run[0][0] - 12, base + min(t for t, _ in boxes) - 10,
                                 run[-1][0] + run[-1][1] + 12, base + max(b for _, b in boxes) + 12], fill=LEMON)
                    run = []
            for wx, _, w, lit in placed:
                B.draw_text(img, wx, base, w, "anton", size, INK if lit else fg)
        return img

    def sounds(self, t0):
        return [] if self.anim == "none" else [("thud", t0 + 0.08)]


class Sticker(HostElement):
    """A slap-on label: red by default."""
    entrance = "slam"
    anchor = "center"
    deco = True

    def texts(self):
        return [self.spec["text"]]

    block = False

    def art(self, u):
        size = self.fitted(self.spec["text"], int(self.spec.get("size", 40)), 860, least=22)
        fill, fg = FILL[self.spec.get("style", "red")]
        img = panel(tw(self.spec["text"], size) + 56, size + 40, fill, INK, 16, 5)
        centred(img, img.width / 2, size + 13, self.spec["text"], size, fg)
        return img


class NumberCard(HostElement):
    """A big number with a small label above it and a line under it."""
    entrance = "rise"

    def texts(self):
        return [t for t in (self.spec.get("label"), self.spec.get("big"), self.spec.get("sub")) if t]

    def art(self, u):
        """Label, big text and sub line, each fitted to the card's width; the card is as tall as they need, so the big
        text never touches the line under it or the card's edge."""
        fill, fg = FILL[self.spec.get("style", "white")]
        label, big_text, sub = self.spec.get("label"), str(self.spec.get("big", "")), self.spec.get("sub")
        inner = self.w - 84
        lsize = self.fitted(label, 26, inner - 1.5 * len(label), "mono_bold", least=18) if label else 0
        big = self.fitted(big_text, int(self.spec.get("size", 170)), inner, "anton", least=64)
        top, bot = B.ink_box(big_text, "anton", big)
        ssize = self.fitted(sub, 34, inner, least=22) if sub else 0
        y = 40 + (lsize + 22 if label else 0)                   # the top of the big text's ink
        base = y - top
        end = base + max(bot, 0)                                # the bottom of its ink
        sub_base = end + 22 + ssize * 0.8                       # the sub line's baseline, clear of the big text
        h = int(sub_base + ssize * 0.25 + 28) if sub else int(end + 36)
        img = panel(self.w, h, fill, INK, 34, 5)
        if label:
            B.draw_text(img, 42, 40 + lsize, label, "mono_bold", lsize, fg if fill != WHITE else MUTED, 1.5)
        B.draw_text(img, 40, base, big_text, "anton", big, fg)
        if sub:
            B.draw_text(img, 44, sub_base, sub, "caption", ssize, fg)
        return img


class Checklist(HostElement):
    """A title and rows that appear one by one, each with ✓ (yes), ✗ (no) or an empty circle. A ✗ row's words are
    grey and never struck through: a line through them hides them (the text check read 2 rows in 6 that way)."""
    entrance = "rise"

    def texts(self):
        return ([self.spec["title"]] if self.spec.get("title") else []) + [it["text"] for it, _ in self.items()]

    def animated_until(self):
        return self.last_item()

    def art(self, u):
        rows = self.items()
        head = 84 if self.spec.get("title") else 26
        h = head + 92 * len(rows) + 22
        img = panel(self.w, h, WHITE, INK, 34, 5)
        d = ImageDraw.Draw(img)
        if self.spec.get("title"):
            B.draw_text(img, 40, 60, self.spec["title"], "caption", self.fitted(self.spec["title"], 36, self.w - 80, least=24), INK)
            d.line([(36, 82), (self.w - 36, 82)], fill=SOFT, width=3)
        for k, (it, t) in enumerate(rows):
            if u < t:
                continue
            p = ease((u - t) / 0.25)
            y = head + 92 * k + 46
            rsize = self.fitted(it["text"], 38, self.w - 150, least=24)
            mark = it.get("mark", "yes")
            if mark == "yes":
                tick(d, 70, y, 26 * p + 1)
            elif mark == "no":
                cross(d, 70, y, 26 * p + 1)
            else:
                d.ellipse([44, y - 26, 96, y + 26], outline=INK, width=4)
            B.draw_text(img, 120 - 30 * (1 - p), y + 14, it["text"], "caption", rsize, INK if mark != "no" else (90, 86, 80))
        return img


class Steps(HostElement):
    """Numbered slots that show ??? until their step is said; the newest one is lemon."""
    entrance = "rise"

    def texts(self):
        return [it["text"] for it, _ in self.items()]

    def animated_until(self):
        return self.last_item()

    def art(self, u):
        rows = self.items()
        h = 26 + 112 * len(rows)
        img = Image.new("RGBA", (self.w, h), (0, 0, 0, 0))
        shown = [k for k, (_, t) in enumerate(rows) if u >= t]
        for k, (it, t) in enumerate(rows):
            on = k in shown
            newest = on and k == max(shown)
            fill = LEMON if newest else (WHITE if on else SOFT)
            row = panel(self.w, 96, fill, INK, 48, 5)
            d = ImageDraw.Draw(row)
            d.ellipse([18, 14, 86, 82], fill=INK)
            centred(row, 52, 64, str(k + 1), 40, WHITE, "anton")
            text = it["text"] if on else self.spec.get("hidden", "? ? ?")
            B.draw_text(row, 112, 63, text, "caption", self.fitted(text, 38, self.w - 140, least=24), INK if on else MUTED)
            img.alpha_composite(row, (0, 13 + 112 * k))
        return img


class Search(HostElement):
    """A search bar that types its query, then shows suggestions."""
    entrance = "rise"

    def texts(self):
        return [self.spec["query"]] + list(self.spec.get("suggestions", []))

    def typing(self):
        return 0.25, 0.25 + 0.07 * len(self.spec["query"])

    def animated_until(self):
        return self.typing()[1] + 0.35 * len(self.spec.get("suggestions", [])) + 0.5

    def art(self, u):
        sug = self.spec.get("suggestions", [])
        h = 112 + (70 * len(sug) + 24 if sug else 0)
        img = panel(self.w, h, WHITE, INK, 34, 5)
        d = ImageDraw.Draw(img)
        d.ellipse([34, 30, 74, 70], outline=INK, width=6)
        d.line([(68, 64), (86, 84)], fill=INK, width=7)
        t0, t1 = self.typing()
        n = len(self.spec["query"]) if u >= t1 else max(0, int((u - t0) / 0.07))
        typed = self.spec["query"][:n]
        qsize = self.fitted(self.spec["query"], 40, self.w - 150, least=24)
        B.draw_text(img, 110, 70, typed, "caption", qsize, INK)
        if u < t1 + 0.6 and int(u * 3) % 2 == 0:
            x = 112 + tw(typed, qsize)
            d.line([(x, 34), (x, 76)], fill=INK, width=4)
        if sug:
            d.line([(30, 108), (self.w - 30, 108)], fill=SOFT, width=3)
        for k, s in enumerate(sug):
            if u < t1 + 0.35 * (k + 1):
                continue
            y = 150 + 70 * k
            d.line([(46, y + 6), (70, y - 14)], fill=MUTED, width=5)
            d.line([(58, y - 14), (70, y - 14), (70, y - 2)], fill=MUTED, width=5)
            B.draw_text(img, 96, y + 12, s, "caption", self.fitted(s, 34, self.w - 130, least=22), INK)
        return img

    def sounds(self, t0):
        t_start, t_end = self.typing()
        keys = [("key", t0 + t_start + 0.07 * k) for k in range(len(self.spec["query"]))]
        return super(HostElement, self).sounds(t0) + keys + [("pop", t0 + t_end + 0.35 * (k + 1))
                                                              for k in range(len(self.spec.get("suggestions", [])))]


class Chat(HostElement):
    """A chat: their messages on the left in white, ours on the right in lemon, each on its word."""
    entrance = "rise"

    def texts(self):
        return ([self.spec["title"]] if self.spec.get("title") else []) + [it["text"] for it, _ in self.items("messages", 0.6)]

    def animated_until(self):
        return self.last_item("messages")

    def layout(self):
        rows, y = [], 104 if self.spec.get("title") else 30
        for it, t in self.items("messages", 0.6):
            lines = wrap_text(it["text"], 36, self.w * 0.62)
            bh = 30 + 48 * len(lines)
            rows.append((it, t, lines, y, bh))
            y += bh + 18
        return rows, y + 12

    def art(self, u):
        rows, h = self.layout()
        img = panel(self.w, h, WHITE, INK, 34, 5)
        d = ImageDraw.Draw(img)
        if self.spec.get("title"):
            d.rounded_rectangle([3, 3, self.w - 4, 82], radius=31, fill=INK)
            d.rectangle([3, 50, self.w - 4, 82], fill=INK)
            d.ellipse([28, 18, 76, 66], fill=LEMON)
            B.draw_text(img, 96, 56, self.spec["title"], "caption", self.fitted(self.spec["title"], 34, self.w - 130, least=22), WHITE)
        for it, t, lines, y, bh in rows:
            if u < t:
                continue
            p = ease((u - t) / 0.22)
            mine = it.get("from", "them") == "me"
            bw = max(tw(line, 36) for line in lines) + 52
            x = self.w - 30 - bw if mine else 30
            dy = int(16 * (1 - p))
            d.rounded_rectangle([x, y + dy, x + bw, y + dy + bh], radius=26, fill=LEMON if mine else WHITE, outline=INK, width=4)
            for k, line in enumerate(lines):
                B.draw_text(img, x + 26, y + dy + 52 + 48 * k, line, "caption", 36, INK)
        return img


class Bars(HostElement):
    """A bar chart: each bar grows on its word, with its label under it and its value text over it."""
    entrance = "rise"

    def texts(self):
        out = [self.spec["title"]] if self.spec.get("title") else []
        for it, _ in self.items("bars", 0.5):
            out += [t for t in (it.get("label"), it.get("text")) if t]
        return out

    def animated_until(self):
        return self.last_item("bars") + 0.3

    def art(self, u):
        bars = self.items("bars", 0.5)
        h = int(self.spec.get("h", 560))
        img = panel(self.w, h, WHITE, INK, 34, 5)
        d = ImageDraw.Draw(img)
        if self.spec.get("title"):
            B.draw_text(img, 40, 62, self.spec["title"], "caption", self.fitted(self.spec["title"], 36, self.w - 80, least=24), INK)
        top, base = 150, h - 92
        vmax = max([it.get("value", 1) for it, _ in bars] + [1])
        slot = (self.w - 80) / max(1, len(bars))
        for k, (it, t) in enumerate(bars):
            cx = 40 + slot * (k + 0.5)
            bw = min(170, slot * 0.6)
            full = (base - top) * it.get("value", 1) / vmax
            p = ease((u - t) / 0.6) if u >= t else 0
            fill = FILL[it.get("style", "lemon")][0]
            if p > 0:
                d.rounded_rectangle([cx - bw / 2, base - full * p, cx + bw / 2, base], radius=14, fill=fill, outline=INK, width=4)
            if it.get("label"):
                centred(img, cx, base + 50, it["label"], self.fitted(it["label"], 30, slot - 16, least=18), INK)
            if it.get("text") and p >= 1:
                centred(img, cx, base - full - 18, it["text"], self.fitted(it["text"], 34, slot - 12, least=20), INK)
        d.line([(34, base), (self.w - 34, base)], fill=INK, width=4)
        return img


class Tiles(HostElement):
    """Word tiles that pop in, three to a row."""
    entrance = "none"

    def texts(self):
        return [it["text"] for it, _ in self.items(gap=0.3)]

    def animated_until(self):
        return self.last_item() + 0.2

    def art(self, u):
        tiles = self.items(gap=0.3)
        per = self.spec.get("per_row", 3)
        rows = (len(tiles) + per - 1) // per
        tw_ = (self.w - 24 * (per - 1)) / per
        img = Image.new("RGBA", (self.w, 150 * rows), (0, 0, 0, 0))
        styles = ["lemon", "white", "ink"]
        for k, (it, t) in enumerate(tiles):
            if u < t:
                continue
            p = B.ease_out_back(min(1.0, (u - t) / 0.25), 2.0)
            fill, fg = FILL[it.get("style", styles[k % 3])]
            tile = panel(tw_, 124, fill, INK, 24, 5)
            size = self.fitted(it["text"], 38, tw_ - 30, least=20)
            centred(tile, tw_ / 2, 76, it["text"], size, fg)
            if p < 1:
                tile = tile.resize((max(1, int(tile.width * (0.6 + 0.4 * p))), max(1, int(tile.height * (0.6 + 0.4 * p)))))
            x = (k % per) * (tw_ + 24) + (tw_ - tile.width) / 2
            y = (k // per) * 150 + (124 - tile.height) / 2
            img.alpha_composite(tile, (int(x), int(y)))
        return img


class Sticky(HostElement):
    """A lemon sticky note with handwriting."""
    entrance = "drop"
    anchor = "center"
    handwritten = True
    block = False
    deco = True

    def texts(self):
        return [self.spec["text"]]

    def art(self, u):
        w = int(self.spec.get("w", 480))
        lines = wrap_text(self.spec["text"], 64, w - 60, "hand")
        h = 80 + 70 * len(lines)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w - 1, h - 1], fill=LEMON)
        d.rectangle([w * 0.35, -2, w * 0.65, 22], fill=(255, 255, 255, 150))
        for k, line in enumerate(lines):
            B.draw_text(img, 30, 86 + 70 * k, line, "hand", 64, INK)
        return img


class TaskGrid(HostElement):
    """Tiles two to a row that tick off one by one."""
    entrance = "rise"

    def texts(self):
        return [it["text"] for it, _ in self.items()]

    def animated_until(self):
        return self.last_item()

    def art(self, u):
        tiles = self.items()
        rows = (len(tiles) + 1) // 2
        cw = (self.w - 24) / 2
        img = Image.new("RGBA", (self.w, 136 * rows), (0, 0, 0, 0))
        for k, (it, t) in enumerate(tiles):
            done = u >= t
            tile = panel(cw, 112, LEMON if done else WHITE, INK, 26, 5)
            d = ImageDraw.Draw(tile)
            B.draw_text(tile, 30, 70, it["text"], "caption", self.fitted(it["text"], 36, cw - 110, least=20), INK)
            if done:
                tick(d, cw - 50, 56, 26 * ease((u - t) / 0.2) + 1, fill=WHITE)
            img.alpha_composite(tile, (int((k % 2) * (cw + 24)), int((k // 2) * 136)))
        return img


class Timer(HostElement):
    """A ring that fills while its number counts up to the final value."""
    entrance = "pop"
    anchor = "center"

    def texts(self):
        return [t for t in (self.spec.get("to"), self.spec.get("label")) if t]

    def animated_until(self):
        return 0.3 + self.spec.get("dur", 1.4)

    def art(self, u):
        r = int(self.spec.get("r", 190))
        img = Image.new("RGBA", (2 * r + 20, 2 * r + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = r + 10
        d.ellipse([10, 10, 2 * r + 10, 2 * r + 10], fill=WHITE, outline=INK, width=6)
        d.ellipse([34, 34, 2 * r - 14, 2 * r - 14], outline=SOFT, width=26)
        p = ease((u - 0.3) / self.spec.get("dur", 1.4))
        if p > 0:
            d.arc([34, 34, 2 * r - 14, 2 * r - 14], -90, -90 + 360 * p, fill=LEMON, width=26)
        final = self.spec.get("to", "")
        shown = final if p >= 1 else count_to(final, p)
        centred(img, c, c + 30, shown, self.fitted(final, 84, 2 * r - 80, "anton", least=40), INK, "anton")
        if self.spec.get("label"):
            centred(img, c, c + 86, self.spec["label"], self.fitted(self.spec["label"], 30, 2 * r - 90, least=18), MUTED)
        return img


def count_to(final, p):
    """The final text with its digits counted up: "20:00" at p = 0.5 reads "10:00"."""
    import re
    m = re.match(r"(\D*)(\d+)(.*)", final)
    if not m:
        return final
    return "{}{}{}".format(m.group(1), str(int(int(m.group(2)) * p)).zfill(len(m.group(2))), m.group(3))


class Picture(HostElement):
    """A picture from reel.json → photos in a rounded card, with an optional label."""
    entrance = "rise"

    def texts(self):
        return [self.spec["label"]] if self.spec.get("label") else []

    def art(self, u):
        w, h = self.w, int(self.spec.get("h", 560))
        card = panel(w, h, SOFT, INK, 34, 6)
        photo = (self.ctx["photos"] or {}).get(self.spec.get("src"))
        inner = Image.new("RGBA", (w - 12, h - 12), SOFT + (255,))
        if photo and Path(photo["path"]).exists():
            pic = Image.open(photo["path"]).convert("RGBA")
            s = max(inner.width / pic.width, inner.height / pic.height)
            pic = pic.resize((int(pic.width * s) + 1, int(pic.height * s) + 1))
            inner = pic.crop(((pic.width - inner.width) // 2, (pic.height - inner.height) // 2,
                              (pic.width - inner.width) // 2 + inner.width, (pic.height - inner.height) // 2 + inner.height))
        else:
            centred(inner, inner.width / 2, inner.height / 2 + 14, "PICTURE {} GOES HERE".format(
                (photo or {}).get("id", self.spec.get("src", ""))), 34, MUTED, "mono_bold")
        mask = Image.new("L", inner.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, inner.width - 1, inner.height - 1], radius=28, fill=255)
        card.paste(inner, (6, 6), mask)
        ImageDraw.Draw(card).rounded_rectangle([3, 3, w - 4, h - 4], radius=34, outline=INK, width=6)
        if self.spec.get("label"):
            lsize = self.fitted(self.spec["label"], 28, w - 100, least=18)
            lab = panel(tw(self.spec["label"], lsize) + 44, 52, INK, INK, 26, 2)
            B.draw_text(lab, 22, 26 + lsize * 0.36, self.spec["label"], "caption", lsize, WHITE)
            card.alpha_composite(lab, (24, h - 76))
        return card


class Outro(HostElement):
    """The sign-off card: the wordmark on a lemon highlight, the tagline, and the account's website ("web")."""
    entrance = "pop"

    def texts(self):
        return [t for t in (self.spec.get("logo") or B.logo_text(), self.spec.get("tagline", ""), self.spec.get("web")) if t]

    def art(self, u):
        web = self.spec.get("web")
        img = panel(self.w, 400 if web else 330, INK, INK, 40, 2)
        d = ImageDraw.Draw(img)
        logo = self.spec.get("logo") or B.logo_text()
        lsize = self.fitted(logo, 96, self.w - 120, "anton", least=48)
        lw = tw(logo, lsize, "anton")
        d.rectangle([self.w / 2 - lw / 2 - 18, 70, self.w / 2 + lw / 2 + 18, 190], fill=LEMON)
        centred(img, self.w / 2, 130 + lsize * 0.44, logo, lsize, INK, "anton")
        tagline = self.spec.get("tagline", "")
        centred(img, self.w / 2, 268, tagline, self.fitted(tagline, 56, self.w - 80, "hand", least=30), WHITE, "hand")
        if web:
            centred(img, self.w / 2, 346, web, self.fitted(web, 34, self.w - 80, "mono_bold", least=20), LEMON, "mono_bold")
        return img


class Confetti(HostElement):
    """A burst of lemon, red and ink paper bits. No words, and drawn behind the cards (Reel.draw_elements)."""
    behind = True
    entrance = "none"
    anchor = "center"
    block = False

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        self.x, self.y = spec.get("x", 540), spec.get("y", 760)
        rng = np.random.default_rng(self.seed)
        self.bits = [(rng.uniform(-1, 1), rng.uniform(-1.6, -0.4), rng.integers(0, 3), rng.uniform(0, 6.28)) for _ in range(70)]

    def animated_until(self):
        return 2.2

    def finish(self, art):
        return art

    def art(self, u):
        img = Image.new("RGBA", (1000, 1000), (0, 0, 0, 0))
        if u > 2.0:
            return img
        d = ImageDraw.Draw(img)
        for vx, vy, c, ph in self.bits:
            x = 500 + vx * 520 * u
            y = 500 + vy * 700 * u + 900 * u * u
            col = (LEMON, RED, INK)[int(c)]
            k = 9 + 5 * math.sin(ph + u * 9)
            d.rectangle([x - k, y - 6, x + k, y + 6], fill=col)
        return img

    def sounds(self, t0):
        return [("pop", t0), ("pop", t0 + 0.05)]


CARDS = {"pill": Pill, "headline": Headline, "sticker": Sticker, "number": NumberCard, "checklist": Checklist, "steps": Steps,
         "search": Search, "chat": Chat, "bars": Bars, "tiles": Tiles, "sticky": Sticky, "grid": TaskGrid,
         "timer": Timer, "picture": Picture, "outro": Outro, "confetti": Confetti}
DIRECTIONS = {"pose", "framing"}          # not drawn: they move the avatars
ITEM_KEYS = ("items", "messages", "bars") # the lists inside a card whose entries come in one by one


# ---------------------------------------------------------------- the reel

def fit_tag(tag, room, size=21, least=15):
    """(the tag, its size, its width) so the header's tag pill ends clear of the brand label beside it: a long tag gets
    smaller letters, and one that still doesn't fit loses its last words (the pill covered the brand's name)."""
    width = lambda t, sz: tw(t, sz, "mono") + 2 * len(t)
    while size > least and width(tag, size) + 50 > room:
        size -= 1
    words = tag.split()
    while len(words) > 1 and width(tag, size) + 50 > room:
        words = words[:-1]
        tag = " ".join(words).rstrip(" ·,") + "…"
    return tag, size, width(tag, size)


def even_out(chunks, flags, fits):
    """The bubbles of one sentence (lists of word numbers), evened out in place: no bubble of one lone word flashing by
    at the end, and no highlighted phrase cut between two bubbles, wherever moving a word or two fixes it."""
    for p in range(len(chunks) - 1, 0, -1):
        a, b = chunks[p - 1], chunks[p]
        while len(b) < 2 and len(a) > 2 and fits([a[-1]] + b):
            b.insert(0, a.pop())
    for p in range(len(chunks) - 1):
        a, b = chunks[p], chunks[p + 1]
        if not (flags[a[-1]] and flags[b[0]]):
            continue
        tail = next((n for n in range(len(a)) if not flags[a[-1 - n]]), len(a))     # the phrase's words ending a
        head = next((n for n in range(len(b)) if not flags[b[n]]), len(b))          # and its words starting b
        if len(a) - tail >= 2 and fits(a[-tail:] + b):
            b[:0] = a[-tail:]
            del a[-tail:]
        elif len(b) - head >= 2 and fits(a + b[:head]):
            a += b[:head]
            del b[:head]


def floor_y(scale):
    """Where an avatar placed at this scale stands: the y of its drawing's bottom edge. At the two-avatar scale it's
    STAGE_LIFT above the usual floor (just under the frame), so the face is clear of Instagram's caption; a bigger
    avatar's face is higher already, so it's lifted less, and a close-up not at all."""
    return H + 30 - STAGE_LIFT * max(0.0, (CLOSE[1] - scale) / (CLOSE[1] - 0.7))


def punch_in(frame, t):
    """The reel's first moment: the frame punches in from 107% to 100%, so something moves from the very first frame,
    while the thumb is deciding."""
    if t >= OPEN:
        return frame
    k = 1 + 0.07 * (1 - B.ease_out_cubic(t / OPEN))
    big = frame.resize((int(W * k), int(H * k)), Image.BILINEAR)
    x0, y0 = (big.width - W) // 2, (big.height - H) // 2
    return big.crop((x0, y0, x0 + W, y0 + H))


class HostReel:
    CARDS = CARDS                  # a style built on this one (build_corvid.py) brings its own cards
    DARK = False                   # a light board: the headline's words are dark (Chatur Kauwa's board is dark)
    ZONE = ZONE                    # where its cards go, and what's under them
    UNDER = "the speech bubble"

    def __init__(self, ep_dir, use_voice=True):
        self.E = B.Episode(ep_dir, use_voice)
        use_brand()
        ep = self.E.ep
        self.cast = dict(ep.get("cast") or {})
        if not self.cast:
            raise SystemExit("episode.json needs a \"cast\": which avatar plays which role, e.g. {\"host\": \"stand-in-host\"}")
        missing = [n for n in self.cast.values() if not (avatars.AVATARS / n).is_dir()]
        if missing:
            raise SystemExit("cast: no avatar kit {} in brand/avatars/ (there are: {})".format(
                ", ".join(missing), ", ".join(avatars.names())))
        roles = list(self.cast)
        if "host" in roles and len(roles) > 1:          # the host stands on the right, the others from the left
            roles = [r for r in roles if r != "host"] + ["host"]
        self.roles = roles
        self.kits = {r: avatars.load(self.cast[r]) for r in roles}
        self.slots = {r: LAYOUTS[min(3, len(roles))][k] for k, r in enumerate(roles[:3])}
        self.mirror = {r: self.faces_away(r) for r in roles}
        first = roles[-1] if "host" in roles else roles[0]
        self.speaker = {l["shot"]: (l.get("speaker") or first) for l in ep.get("script", [])}
        self.ctx_photos = self.E.photos
        self.elements, self.poses, self.framing = [], {r: [] for r in roles}, []
        for i, shot in enumerate(self.E.shots):
            els = []
            for j, spec in enumerate(self.E.reel["shots"].get(shot["id"], [])):
                spec = B.Reel.resolve(self, shot, json.loads(json.dumps(spec)))
                self.resolve_items(shot, spec)
                t = shot["start"] + spec.get("at", 0.0 if spec["type"] in DIRECTIONS else 0.1)
                if spec["type"] == "pose":
                    who = spec.get("who") or self.speaker[shot["id"]]
                    if who in self.poses:
                        self.poses[who].append((t, spec.get("pose", "talk"), i, str(spec.get("view") or "")))
                    continue
                if spec["type"] == "framing":
                    self.framing.append((t, spec.get("mode", "normal"), spec.get("who") or self.speaker[shot["id"]]))
                    continue
                if spec["type"] not in self.CARDS:
                    raise SystemExit("{}: \"{}\" isn't a card of this style. Cards: {}".format(
                        shot["id"], spec["type"], ", ".join(self.CARDS)))
                if i > 0 and spec.get("at", 0.1) < B.PUSH:
                    spec["at"] = B.PUSH
                ctx = {"photos": self.ctx_photos, "seed": (i + 1) * 131 + j * 7, "paper": None, "dark": self.DARK}
                els.append(self.CARDS[spec["type"]](spec, ctx))
            self.elements.append(els)
        self.feel = [emotion.spec(self.E.lines.get(s["id"], {})) for s in self.E.shots]
        self.settle_framing()
        self.add_feeling_poses()
        for r in roles:
            self.poses[r].sort()
        self.framing.sort(key=lambda f: f[0])
        self.base = self.make_base()
        self.header = self.make_header()
        self.progress = self.E.reel.get("progress") or {}
        self.pages = [self.make_pages(i) for i in range(len(self.E.shots))]
        self.mouth = self.mouth_track()
        self.blinks = {r: self.blink_times(k) for k, r in enumerate(roles)}
        self.bubble_cache = {}
        self.layout_notes = None                # laid out on first use, once a style built on this one is set up

    def resolve_items(self, shot, spec):
        """A row, message, bar or tile inside a card with "on": "word" comes in as that word is said ("on_t": seconds
        from the shot's start), like a card does. It never waits past the shot's last second, so it's read."""
        lead = spec.get("lead", 0.12)
        last = max(0.3, shot["end"] - shot["start"] - 0.9)
        for key in ITEM_KEYS:
            for item in spec.get(key) or []:
                if isinstance(item, dict) and "on" in item:
                    item["on_t"] = min(last, max(0.0, self.E.word_time(shot, item["on"]) - lead))

    def settle_framing(self):
        """A close-up lasts for its own line, and on while the same speaker goes on with no card (the sign-off's own
        card aside). The next line of another speaker, or with a card, brings everyone back by itself unless it sets
        its own framing: so the spoken words are never over the wrong face, and a card never loses its room."""
        mode, who, back = "normal", None, []
        for i, shot in enumerate(self.E.shots):
            mine = sorted((f for f in self.framing if shot["start"] <= f[0] < shot["end"]), key=lambda f: f[0])
            if not mine and mode == "close":
                cards = [el for el in self.elements[i] if getattr(el, "block", False) and not isinstance(el, Outro)]
                if self.speaker.get(shot["id"]) != who or cards:
                    back.append((shot["start"], "normal", None))
                    mode = "normal"
            for _, m, w in mine:
                mode, who = m, w
        self.framing = sorted(self.framing + back, key=lambda f: f[0])

    def add_feeling_poses(self):
        """A line that sets no pose for its speaker gets one that fits its feeling (emotion.FEELINGS → poses, the first
        one the avatar has), held for its first FEEL_POSE seconds."""
        for i, shot in enumerate(self.E.shots):
            who, feel = self.speaker.get(shot["id"]), self.feel[i]
            if who not in self.poses or not feel.poses or any(sh == i for _, _, sh, _ in self.poses[who]):
                continue
            pose = next((p for p in feel.poses if p in self.kits[who]["poses"]), None)
            if pose is None:
                continue
            t0 = shot["start"] + FEEL_LAG
            self.poses[who].append((t0, pose, i, ""))
            if shot["end"] - t0 > FEEL_POSE + 0.6:
                self.poses[who].append((t0 + FEEL_POSE, "talk", i, ""))

    # ---- the layout: every card on the board, every word inside its card, nothing on top of anything else
    def obstacles(self, i):
        """Boxes a shot's cards keep clear of besides each other and the pills (Chatur Kauwa adds its corner pot)."""
        return []

    def bubble_top(self, i):
        """How high the speech bubble rides in shot i when the speaker is framed close (None otherwise: then it stays
        below the cards). The sign-off's card says the words itself, so there the bubble steps aside."""
        shot = self.E.shots[i]
        if any(isinstance(el, Outro) for el in self.elements[i]):
            return None
        lines = max((len(pg["lines"]) for pg in self.pages[i]), default=1)
        tops = []
        for t in (shot["start"] + 0.05, (shot["start"] + shot["end"]) / 2, shot["end"] - 0.05):
            mode, who, _ = self.framing_at(t)
            if mode == "close" and who in self.kits:
                tops.append(self.bubble_foot(who, CLOSE[1], self.look_at(who, t)[1]) - (34 + CAP_LINE * lines + 10 + 50)
                            - EA.HEADROOM.get(self.feel[i].bubble, 0))
        return min(tops) if tops else None

    def lay_out(self, i):
        """Shot i's cards stay on the board, clear of each other, the pills, the bubble and the style's own things: a
        card that would overlap one goes under it, a label or mark drawn on a card moves with that card, and cards too
        tall for the board shrink together. Returns [(level, shot, what)]: "note" for what it changed, "fix" for
        what it couldn't."""
        sid = self.E.shots[i]["id"]
        els = self.elements[i]
        x_lo, y_lo, x_hi, y_hi = self.ZONE
        top_of_bubble = self.bubble_top(i)
        if top_of_bubble is not None:
            y_hi = min(y_hi, top_of_bubble - 16)
        zone = (x_lo, y_lo, x_hi, y_hi)
        blocks = [el for el in els if getattr(el, "block", False)]
        decos = [el for el in els if getattr(el, "deco", False)]
        pills = [el for el in els if isinstance(el, Pill)]
        out = []
        for el in blocks + decos + pills:
            el._plan = (el.x, el.y, el.shrink)
        fixed = self.obstacles(i)
        for el in pills:                                        # a pill keeps its height; it steps aside if it must
            x0, y0, x1, y1 = el.box()
            for ob in fixed:
                if _hits((x0, y0, x1, y1), ob):
                    el.move_to(max(x_lo, ob[0] - GAP - (x1 - x0)), y0)
                    x0, y0, x1, y1 = el.box()
            if x0 < x_lo or x1 > x_hi:
                el.move_to(min(max(x0, x_lo), x_hi - (x1 - x0)), y0)
        fixed = fixed + [el.box() for el in pills]
        on = {}                                                 # each label or mark: the card it's drawn on
        for d in decos:
            db = d.box()
            area = max(1.0, (db[2] - db[0]) * (db[3] - db[1]))
            best = max(((b, _overlap(db, b.box())) for b in blocks if _together(b, d)),     # most covered, then the
                       key=lambda x: (x[1], x[0].at <= d.at, x[0].at), default=None)       # card shown just before it
            if best and best[1] / area >= 0.15:
                on[d] = (best[0], best[0].box(), db)
        k = 1.0
        for _ in range(8):
            self.stack(blocks, fixed, zone, k)
            if not blocks:
                break
            first = min(b.box()[1] for b in blocks)
            bottom = max(b.box()[3] for b in blocks)
            if bottom <= y_hi + 1 or k <= LEAST:
                break
            k = max(LEAST, k * min(0.97, (y_hi - first) / max(1.0, bottom - first)))
        for d in decos:
            if d in on:                                         # it moves and shrinks with its card
                b, (bx0, by0, bx1, by1), (dx0, dy0, dx1, dy1) = on[d]
                nb = b.box()
                r = (nb[2] - nb[0]) / max(1.0, bx1 - bx0)
                d.shrink = d._plan[2] * r
                cx = nb[0] + ((dx0 + dx1) / 2 - bx0) * r
                cy = nb[1] + ((dy0 + dy1) / 2 - by0) * r
                w, h = d.box()[2] - d.box()[0], d.box()[3] - d.box()[1]
                d.move_to(cx - w / 2, cy - h / 2)
            self.keep_on_board(d, zone, fixed)
            if d not in on:
                self.clear_of_cards(d, blocks, zone, fixed)
        loose = sorted((d for d in decos if d not in on), key=lambda d: d.at)
        crowded = [(d, hit) for k, d in enumerate(loose)        # a label that still covers one shown before it
                   for hit in [self.clear_of_labels(d, loose[:k], blocks, zone, fixed)] if hit is not None]
        # what the layout did, and what it couldn't, for the report
        for el in blocks + decos:
            name = _describe(el)
            (px, py, pk) = el._plan
            if el in on:                                    # it went with its card: the card's note says it
                pass
            elif el.shrink < pk * 0.98:
                out.append(("note", sid, "shrank {} to {:.0%} so it fits on the board".format(name, el.shrink / pk)))
            moved = abs(el.x - px) + abs(el.y - py)
            if moved > 12 and el not in on:
                out.append(("note", sid, "moved {} {:.0f} px so it overlaps nothing".format(name, moved)))
            for text, (share, fits) in el.shrunk.items():
                if not fits:
                    out.append(("fix", sid, "\"{}\" is too long for its {} even at its smallest size: use fewer words "
                                            "(or a shorter form, like 27 NOV)".format(text, _kind(el))))
                elif share < 0.8:
                    out.append(("note", sid, "drew \"{}\" at {:.0%} of its size so it fits its {}".format(
                        text, share, _kind(el))))
        if blocks and max(b.box()[3] for b in blocks) > y_hi + 1:
            out.append(("fix", sid, "too much on the board: even at {:.0%} its cards reach below y {:.0f}, into {}. "
                                    "Drop a card, or split the shot".format(LEAST, y_hi, self.UNDER)))
        for d in decos:
            if d not in on and any(_overlap(d.box(), b.box()) > 0.25 * _area(d.box()) for b in blocks if _together(b, d)):
                out.append(("fix", sid, "{} covers a card and there's no room to move it: put it beside the card, "
                                        "or drop it".format(_describe(d))))
        for d, other in crowded:
            out.append(("fix", sid, "{} covers {} and there's no room on the board for both{}: keep one of them, or "
                                    "show the other in the next shot".format(
                                        _describe(d), _describe(other),
                                        " (a close-up leaves room for one label)" if top_of_bubble is not None else "")))
        return out

    def stack(self, blocks, fixed, zone, k):
        """Put the cards back where they were planned, k times their size, then move each card that would overlap a
        card above it, a pill or an obstacle to just under it, and back onto the board sideways."""
        x_lo, y_lo, x_hi, _ = zone
        placed = []
        for el in sorted(blocks, key=lambda e: (e._plan[1], e.at)):
            el.x, el.y, el.shrink = el._plan[0], el._plan[1], el._plan[2] * k
            x0, y0, x1, y1 = el.box()
            if x1 - x0 > x_hi - x_lo:                            # wider than the board
                el.shrink *= (x_hi - x_lo) / (x1 - x0)
                x0, y0, x1, y1 = el.box()
            left = min(max(x0, x_lo), x_hi - (x1 - x0))
            top = max(y0, y_lo)
            moved = True
            while moved:
                moved = False
                for ob in fixed + [p.box() for p in placed if _together(p, el)]:
                    if _hits((left, top, left + x1 - x0, top + y1 - y0), ob):
                        top = ob[3] + GAP
                        moved = True
            el.move_to(left, top)
            placed.append(el)

    def keep_on_board(self, el, zone, fixed):
        """A label or mark: on the screen, above the bubble, and clear of the pills and obstacles."""
        x_lo, y_lo, x_hi, y_hi = zone
        x0, y0, x1, y1 = el.box()
        left = min(max(x0, x_lo), x_hi - (x1 - x0))
        top = min(max(y0, y_lo), y_hi - (y1 - y0))
        for ob in fixed:
            if _hits((left, top, left + x1 - x0, top + y1 - y0), ob):
                top = ob[3] + GAP
        el.move_to(left, top)

    def clear_of_cards(self, el, blocks, zone, fixed):
        """A label that isn't drawn on a card mustn't cover one: under the cards if there's room, else above them."""
        x_lo, y_lo, x_hi, y_hi = zone
        x0, y0, x1, y1 = el.box()
        w, h = x1 - x0, y1 - y0
        hit = [b.box() for b in blocks if _together(b, el) and _overlap((x0, y0, x1, y1), b.box()) > 0.25 * w * h]
        if not hit:
            return
        below = max(b[3] for b in hit) + GAP
        above = min(b[1] for b in hit) - GAP - h
        others = [b.box() for b in blocks if _together(b, el)] + fixed
        for top in (below, above):
            if y_lo <= top and top + h <= y_hi and not any(_hits((x0, top, x1, top + h), ob) for ob in others):
                el.move_to(x0, top)
                return

    def clear_of_labels(self, el, placed, blocks, zone, fixed):
        """A label mustn't cover a label that's on screen with it (a sticker under a sticky note can't be read): it
        goes under that one if there's room, else above it, else beside it. Returns the label it still covers when
        there's no room anywhere, else None."""
        x_lo, y_lo, x_hi, y_hi = zone
        x0, y0, x1, y1 = el.box()
        w, h = x1 - x0, y1 - y0
        shown = [p for p in placed if _together(p, el)]
        hit = [p for p in shown if _overlap((x0, y0, x1, y1), p.box()) > 0.1 * min(w * h, _area(p.box()))]
        if not hit:
            return None
        keep = [p.box() for p in shown] + [b.box() for b in blocks if _together(b, el)] + fixed
        boxes = [p.box() for p in hit]
        spots = [(x0, max(b[3] for b in boxes) + GAP), (x0, min(b[1] for b in boxes) - GAP - h),
                 (max(b[2] for b in boxes) + GAP, y0), (min(b[0] for b in boxes) - GAP - w, y0)]
        for sx, sy in spots:
            box = (sx, sy, sx + w, sy + h)
            if x_lo <= sx and sx + w <= x_hi and y_lo <= sy and sy + h <= y_hi and not any(_hits(box, ob) for ob in keep):
                el.move_to(sx, sy)
                return None
        return hit[0]

    def laid_out(self):
        """Lay every shot out once: [(level, shot, what)] for the report."""
        if self.layout_notes is None:
            self.layout_notes = []
            for i in range(len(self.E.shots)):
                self.layout_notes += self.lay_out(i)
        return self.layout_notes

    def check_layout(self):
        """What the layout changed (notes) and what it couldn't fix (fix), shot by shot."""
        return list(self.laid_out())

    # ---- the parts the Paper build shares
    def check_texts(self):
        return B.Reel.check_texts(self)

    def draw_elements(self, frame, i, u, push=0.0, jolt=(0, 0), stills=False):
        self.laid_out()
        return B.Reel.draw_elements(self, frame, i, u, push, jolt, stills)

    def jolt_at(self, i, u):
        return B.Reel.jolt_at(self, i, u)

    def shot_at(self, t):
        return B.Reel.shot_at(self, t)

    # ---- the frame
    def make_base(self):
        img = Image.new("RGBA", (W, H), BG + (255,))
        d = ImageDraw.Draw(img)
        for y in range(18, H, 36):
            for x in range(18, W, 36):
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=DOT)
        return img

    def make_header(self):
        img = Image.new("RGBA", (W, 330), (0, 0, 0, 0))
        brand = self.E.reel.get("brand_label") or B.logo_text()
        size = 40
        top, bot = B.ink_box(brand, "anton", size)
        bw = tw(brand, size, "anton")
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([60, 228, 60 + bw + 36, 292], radius=14, fill=INK)
        B.draw_text(img, 78, 260 - (top + bot) / 2, brand, "anton", size, LEMON, 1)
        tag = self.E.ep.get("tag", "")
        if tag:
            tag, tsize, tag_w = fit_tag(tag, 1020 - (60 + bw + 36) - 18)
            box = panel(tag_w + 50, 52, WHITE, INK, 26, 3)
            B.draw_text(box, 25, 26 + tsize * 0.38, tag, "mono", tsize, INK, 1.6)
            img.alpha_composite(box, (int(1020 - box.width), 234))
        return img

    def progress_bar(self, frame, t):
        steps = self.progress.get("steps") or []
        if not steps:
            return
        start_id = self.progress.get("from") or steps[0].get("shot")
        start = next((s["start"] for s in self.E.shots if s["id"] == start_id), 0.0)
        if t < start:
            return
        p = ease((t - start) / 0.35)
        starts = [next((s["start"] for s in self.E.shots if s["id"] == st.get("shot")), 1e9) for st in steps]
        labels = [st["label"] for st in steps] + ["END"]
        size = 22
        widths = [max(116, tw(lab, size, "mono_bold") + 2 * len(lab) + 56) for lab in labels]
        total = sum(widths) + 12 * (len(widths) - 1)
        x = (W - total) / 2
        y = 316 - int(30 * (1 - p))
        d = ImageDraw.Draw(frame)
        for k, (lab, w) in enumerate(zip(labels, widths)):
            if k < len(steps):
                done = k + 1 < len(steps) and t >= starts[k + 1]
                active = not done and t >= starts[k]
            else:
                done, active = False, False
            fill = LEMON if done else (WHITE if active else (INK if k == len(steps) else SOFT))
            fg = INK if (done or active) else (LEMON if k == len(steps) else MUTED)
            d.rounded_rectangle([x, y, x + w, y + 46], radius=23, fill=fill, outline=INK, width=3)
            tx = x + 22
            if done:
                tick(d, x + 24, y + 23, 13, fill=WHITE)
                tx = x + 44
            B.draw_text(frame, tx, y + 32, lab, "mono_bold", size, fg, 2)
            x += w + 12

    # ---- the avatars
    def mouth_track(self):
        """The mouth shape of the speaking role on every frame: {frame: (role, shape)}.

        The shapes come from the line's voice text, syllable by syllable (visemes), and are spread over the frames
        where the voice is actually sounding, so the mouth closes in the pauses and each syllable lands on its sound.
        With no voice yet, the words' planned times stand in for the sound."""
        n = int(self.E.length * FPS) + 2
        track = {}
        for s in self.E.shots:
            role = self.speaker.get(s["id"])
            vo = s["vo"]
            f0, f1 = int(vo["w0"] * FPS), min(n - 1, int(vo["w1"] * FPS) + 1)
            if f1 <= f0:
                continue
            level = np.zeros(f1 - f0, np.float32)
            if vo.get("audio") is not None:
                a = vo["audio"]
                for k, f in enumerate(range(f0, f1)):
                    i0 = int((f / FPS - vo["at"]) * SR)
                    chunk = a[max(0, i0):max(0, i0 + SR // FPS)]
                    level[k] = float(np.sqrt(np.mean(chunk ** 2))) if len(chunk) else 0.0
                top = float(np.percentile(level, 90)) or 1.0
                level = level / top
            else:
                for (w0, w1) in s["times"]:
                    for f in range(int(w0 * FPS) + 1, int(w1 * FPS)):          # a frame's gap between words
                        if f0 <= f < f1:
                            level[f - f0] = 1.0
            line = self.E.lines.get(s["id"], {})
            seq = [v for w in emotion.clean(line.get("tts", "")).split() for v in visemes(w)]     # tags aren't said
            sounding = [k for k in range(len(level)) if level[k] >= 0.14]
            shapes = ["closed"] * len(level)
            for j, k in enumerate(sounding):
                if seq:
                    shape = seq[min(len(seq) - 1, j * len(seq) // len(sounding))]
                else:
                    v = level[k]
                    shape = "teeth" if v < 0.42 else "open" if v < 0.75 else "wide"
                if shape == "open" and level[k] > 0.92:
                    shape = "wide"
                shapes[k] = shape
            for k in range(1, len(shapes) - 1):                    # no shape shows for a single frame
                if shapes[k] != shapes[k - 1] and shapes[k] != shapes[k + 1]:
                    shapes[k] = shapes[k - 1]
            for k, f in enumerate(range(f0, f1)):
                track[f] = (role, shapes[k])
        return track

    def blink_times(self, k):
        rng = np.random.default_rng(97 + 13 * k)
        out, t = [], rng.uniform(0.8, 2.0)
        while t < self.E.length + 5:
            out.append(t)
            t += rng.uniform(2.4, 4.6)
        return out

    def look_at(self, role, t):
        """(pose, view) at time t. A pose lasts for its own line: each line starts from "talk", in the kit's own view,
        unless it sets a pose. A pose with a "view" (Chatur's "front") turns the avatar for the rest of that line."""
        i, pose, view = self.shot_at(t), "talk", ""
        for t0, p, shot, v in self.poses[role]:
            if shot == i and t >= t0:
                pose, view = p, v or view
        kit = self.kits[role]["views"].get(view) if view else None
        if kit is None:
            kit, view = self.kits[role], ""
        return (pose if pose in kit["poses"] else "talk"), view

    def pose_at(self, role, t):
        return self.look_at(role, t)[0]

    def turn_at(self, role, t):
        """When the avatar changed view less than TURN seconds ago: (seconds since, the pose and view before)."""
        moments = {s["start"] for s in self.E.shots} | {t0 for t0, *_ in self.poses[role]}
        for c in sorted((m for m in moments if t - TURN < m <= t), reverse=True):
            before = self.look_at(role, c - 1e-3)
            if before[1] != self.look_at(role, c)[1]:
                return t - c, before
        return None

    def framing_at(self, t):
        mode, who, since = "normal", None, 0.0
        for t0, m, w in self.framing:
            if t >= t0:
                mode, who, since = m, w, t0
        return mode, who, since

    def faces_away(self, role, view=""):
        """True when a side-on avatar ("faces" in avatar.json) would look off the screen from where it stands: it's then
        drawn mirrored, so it always looks towards the middle, where the cards and the other characters are."""
        kit = self.kits[role]["views"].get(view, self.kits[role]) if view else self.kits[role]
        faces = str(kit["meta"].get("faces") or "").lower()
        x = self.slots.get(role, (W / 2, 0))[0]
        return (faces == "left" and x < W / 2) or (faces == "right" and x > W / 2)

    @lru_cache(maxsize=1024)
    def avatar_image(self, role, pose, mouth, blink, scale, view=""):
        img = avatars.compose(self.kits[role], pose, mouth, blink, view=view or None)
        if self.faces_away(role, view):
            img = ImageOps.mirror(img)
        size = max(1, int(img.width * scale))
        return img.resize((size, size), Image.LANCZOS)

    def head_anchor(self, role, x, scale, view="", slot=None):
        """Where the speech bubble points: the face, in frame pixels. slot: the scale the avatar is placed at, when
        it's drawn a little bigger or smaller than that for a moment (listening, a jump): it stands where its place is."""
        kit = self.kits[role]["views"].get(view, self.kits[role]) if view else self.kits[role]
        cx, cy = kit["anchor"]
        if self.faces_away(role, view):
            cx = avatars.CANVAS - cx
        top = floor_y(scale if slot is None else slot) - avatars.CANVAS * scale
        return x + (cx - avatars.CANVAS / 2) * scale, top + cy * scale

    @lru_cache(maxsize=64)
    def head_top(self, role, view=""):
        """The top of the avatar's head in its own drawing (0 is the drawing's top edge): the first row with ink above
        the face. The speech bubble's tail stops just above it, whatever the avatar's shape."""
        kit = self.kits[role]["views"].get(view, self.kits[role]) if view else self.kits[role]
        pose = "talk" if "talk" in kit["poses"] else next(iter(kit["poses"]))
        alpha = np.asarray(avatars.compose(self.kits[role], pose, "closed", False, view=view or None).getchannel("A"))
        cx = int(kit["anchor"][0])
        rows = np.where(alpha[:, max(0, cx - 110):cx + 110].max(axis=1) > 96)[0]
        return int(rows[0]) if len(rows) else max(0, int(kit["anchor"][1]) - 220)

    def placements(self, t):
        """[(role, x, scale)] for the avatars on screen at time t."""
        mode, who, since = self.framing_at(t)
        if mode == "close" and who in self.kits:
            p = ease((t - since) / 0.45)
            x0, s0 = self.slots[who]
            return [(who, x0 + (CLOSE[0] - x0) * p, s0 + (CLOSE[1] - s0) * p)]
        return [(r, *self.slots[r]) for r in self.roles[:3]]

    def draw_avatars(self, frame, t):
        f = int(round(t * FPS))
        speaking = self.mouth.get(f)
        i = self.shot_at(t)
        u = t - self.E.shots[i]["start"] - FEEL_LAG               # how far into its line's feeling
        speaker, feel = self.speaker.get(self.E.shots[i]["id"]), self.feel[i]
        marks = []
        for k, (role, x, scale) in enumerate(self.placements(t)):
            pose, view = self.look_at(role, t)
            mouth = speaking[1] if speaking and speaking[0] == role else "closed"
            blink = pose not in SHUT_EYES and any(b <= t < b + 0.11 for b in self.blinks[role])
            listening = len(self.roles) > 1 and speaking is not None and speaking[0] != role
            feels = role == speaker and pose not in SHUT_EYES
            dx, dy, zoom = EA.move(feel.move, u) if feels else (0.0, 0.0, 1.0)
            s = round(scale * (0.96 if listening else 1.0) * zoom, 3)
            turn, squeeze = self.turn_at(role, t), 1.0
            if turn is not None:                    # turning to a new view: narrow to an edge, then open out again
                since, before = turn
                squeeze = abs(math.cos(math.pi * since / TURN))
                if since < TURN / 2:
                    pose, view = before
            img = self.avatar_image(role, pose, mouth, blink, s, view)
            if squeeze < 0.999:
                img = img.resize((max(1, int(img.width * max(squeeze, 0.04))), img.height), Image.LANCZOS)
            breathe = 3 * math.sin(2 * math.pi * t / 3.4 + k * 1.7) + (6 if listening else 0)
            B.paste(frame, img, x + dx - img.width / 2, floor_y(scale) - img.height + breathe + dy)
            if feels and feel.mark:
                marks.append((role, x, s, view, dx, dy + breathe, scale))
        self.fade_floor(frame)
        for role, x, s, view, dx, dy, slot in marks:               # on top of every avatar
            self.draw_mark(frame, i, u, role, x, s, view, dx, dy, slot)

    def fade_floor(self, frame):
        """Under the avatars the board fades back in, so a lifted avatar never ends in a cut edge."""
        if getattr(self, "_floor", None) is None:
            y0, y1 = STAGE_FADE
            ramp = np.clip((np.arange(y0, H) - y0) / float(y1 - y0), 0, 1) * 255
            mask = Image.fromarray(np.repeat(ramp.astype(np.uint8)[:, None], W, axis=1), "L")
            self._floor = (self.base.crop((0, y0, W, H)).convert("RGB"), mask, y0)
        board, mask, y0 = self._floor
        frame.paste(board, (0, y0), mask)

    def draw_mark(self, frame, i, u, role, x, s, view, dx, dy, slot=None):
        """The line's feeling, by its speaker's head: it pops in with the first words and goes after a moment."""
        shot = self.E.shots[i]
        grow, alpha = EA.envelope(u, shot["end"] - shot["start"] - FEEL_LAG)
        size = int(round(MARK_SIZE * s / 0.7 * grow))
        if alpha <= 0.02 or size < 8:
            return
        img = EA.mark(self.feel[i].mark, round(u * FPS) / FPS, size)
        if alpha < 0.99:
            img = img.copy()
            img.putalpha(img.getchannel("A").point(lambda a: int(a * alpha)))
        ax, ay = self.head_anchor(role, x, s, view, slot)
        mx, my = EA.place(ax, ay, x, s, W)
        mx = min(max(mx + dx, img.width / 2 + 6), W - img.width / 2 - 6)
        my = max(my + dy, CARDS_BOTTOM + 8 + img.height / 2 * 0.6)
        B.paste(frame, img, mx - img.width / 2, my - img.height / 2)

    # ---- the speech bubble
    def make_pages(self, i):
        shot = self.E.shots[i]
        line = self.E.lines[shot["id"]]
        words = shot["words"]
        flags = B.highlight_flags(words, line.get("highlights"))
        lines_of = lambda idx: B.wrap([words[k] for k in idx], CAP_WRAP, CAP_SIZE)
        fits = lambda idx: len(lines_of(idx)) <= 2
        pages = []
        for idx in B.split_pages(words, line.get("highlights"), max_lines=2, width=CAP_WRAP, size=CAP_SIZE):
            chunks, cur = [], []
            for k in idx:                                  # a long sentence: two lines at a time, so the bubble
                if cur and not fits(cur + [k]):            # stays small and below the cards
                    chunks.append(cur)
                    cur = [k]
                else:
                    cur = cur + [k]
            if cur:
                chunks.append(cur)
            even_out(chunks, flags, fits)
            for sub in chunks:
                pages.append({"idx": sub, "lines": lines_of(sub), "flags": [flags[m] for m in sub],
                              "t0": shot["times"][sub[0]][0] - 0.1})
        pages[0]["t0"] = shot["start"]
        return pages

    def page_at(self, i, t):
        """(its number, the page) of shot i's words that the bubble shows at time t."""
        pages = self.pages[i]
        k = max(j for j, p in enumerate(pages) if t >= p["t0"]) if t >= pages[0]["t0"] else 0
        return k, pages[k]

    @staticmethod
    def bubble_size(page):
        """(width, height) of the bubble's box for a page of words, without its tail."""
        space = tw(" ", CAP_SIZE)
        widths = [sum(tw(w, CAP_SIZE) for w in line) + space * (len(line) - 1) for line in page["lines"]]
        return int(max(widths) + 60), 34 + CAP_LINE * len(page["lines"]) + 10

    def bubble_foot(self, role, scale, view=""):
        """The y where a bubble above this avatar's head ends: the tip of its tail, just over the head."""
        return floor_y(scale) - avatars.CANVAS * scale + self.head_top(role, view) * scale - HEAD_GAP

    def bubble(self, i, t, tail, side):
        """The bubble's picture. tail: where its tail leaves the box (x from the box's left edge) when it hangs under
        the box ("below"), so it points at the speaker wherever the box had to go."""
        shot = self.E.shots[i]
        k, page = self.page_at(i, t)
        spoken = sum(1 for idx in page["idx"] if t >= shot["times"][idx][0])
        bw, bh = self.bubble_size(page)
        tail = bw / 2 if tail is None else min(max(tail, 52), bw - 52)
        key = (i, k, spoken, side, int(tail) // 3)
        if key not in self.bubble_cache:
            space = tw(" ", CAP_SIZE)
            img = Image.new("RGBA", (bw + 40 + 2 * BM, bh + 50 + 2 * BM), (0, 0, 0, 0))   # BM all round: the edge's room
            d = ImageDraw.Draw(img)
            feel = self.feel[i]
            edge = EA.bubble_edge(d, feel.bubble, [BM + 3, BM + 3, BM + bw, BM + bh], 28,
                                  colour_for_angry=feel is emotion.FEELINGS["angry"], ink=INK, accent=LEMON)
            if side == "below":
                tip = [(tail - 20, bh - 4), (tail + 20, bh - 4), (tail, bh + 40)]
            else:
                tip = [(36, bh - 4), (70, bh - 4), (24, bh + 40)]
            tip = [(tx + BM, ty + BM) for tx, ty in tip]
            d.polygon(tip, fill=WHITE)
            d.line([tip[1], tip[2], tip[0]], fill=edge, width=5)
            y, n = 30 + int(CAP_SIZE * 0.9) + BM, 0
            for line in page["lines"]:
                x = 33 + BM
                for w in line:
                    ww = tw(w, CAP_SIZE)
                    said = n < spoken
                    if page["flags"][n] and said:
                        d.rounded_rectangle([x - 6, y - int(CAP_SIZE * 0.95), x + ww + 6, y + int(CAP_SIZE * 0.23)],
                                            radius=8, fill=LEMON)
                    B.draw_text(img, x, y, w, "caption", CAP_SIZE, INK if said else (178, 172, 162))
                    x += ww + space
                    n += 1
                y += CAP_LINE
            self.bubble_cache = {kk: v for kk, v in self.bubble_cache.items() if kk[0] >= i - 1}
            self.bubble_cache[key] = img
        return self.bubble_cache[key]

    def draw_bubble(self, frame, t, i):
        role = self.speaker.get(self.E.shots[i]["id"])
        place = {r: (x, s) for r, x, s in self.placements(t)}
        if role not in place:
            role = next(iter(place))
        x, s = place[role]
        view = self.look_at(role, t)[1]
        ax, ay = self.head_anchor(role, x, s, view)
        bw, bh = self.bubble_size(self.page_at(i, t)[1])
        iw, ih = bw + 40, bh + 50                            # the bubble itself with its tail, without its edge's room
        below = CARDS_BOTTOM + 20 + EA.HEADROOM.get(self.feel[i].bubble, 0)   # spikes and bursts stay off the cards too
        if len(place) == 1 and self.framing_at(t)[0] != "close":
            side, tail = "left", None                        # beside the head, its tail towards the face
            bx = min(ax + 70, SAFE_RIGHT - bw)
            by = max(ay - 120 - ih, below)                   # a long line's bubble stays below the cards
        else:
            side = "below"
            bx = min(max(ax - iw / 2 + 20, 30), SAFE_RIGHT - bw)   # left of Instagram's buttons
            tail = ax - bx                                   # and its tail still points at the speaker
            by = self.bubble_foot(role, s, view) - ih
            if self.framing_at(t)[0] != "close":
                by = max(by, below)                                 # never over the cards
        img = self.bubble(i, t, tail, side)
        bx, by = bx - BM, by - BM
        if self.feel[i].bubble == "pop" and i > 0:           # an excited or surprised line's bubble bounces in (the
            k = EA.pop(t - self.E.shots[i]["start"] - FEEL_LAG)    # reel's first frame shows its bubble whole)
            if k < 0.999 or k > 1.001:
                w0, h0 = img.width, img.height
                img = img.resize((max(1, int(w0 * k)), max(1, int(h0 * k))), Image.BILINEAR)
                bx, by = bx + (w0 - img.width) / 2, by + (h0 - img.height)
        B.paste(frame, img, bx, by)

    # ---- composition
    def render(self, t, header=True, caption=True, stills=False):
        frame = self.base.copy()
        i = self.shot_at(t)
        shot = self.E.shots[i]
        u = t - shot["start"]
        if header:
            frame.alpha_composite(self.header, (0, 0))
            self.progress_bar(frame, t)
        if i > 0 and u < B.PUSH and not stills:
            prev = self.E.shots[i - 1]
            self.draw_elements(frame, i - 1, prev["end"] - prev["start"], push=-H * B.ease_in_cubic(u / B.PUSH))
        self.draw_elements(frame, i, u, jolt=(0, 0) if stills else self.jolt_at(i, u), stills=stills)
        self.draw_avatars(frame, t)
        # the sign-off card says the words itself, so the bubble steps aside once it's up
        if caption and not any(isinstance(el, Outro) and u >= el.at + 0.25 for el in self.elements[i]):
            self.draw_bubble(frame, t, i)
        if not stills:
            frame = punch_in(frame, t)
        return frame.convert("RGB")

    def render_cover(self):
        cover = self.E.ep.get("post", {}).get("cover") or {}
        frame = self.base.copy()
        frame.alpha_composite(self.header, (0, B.COVER_HEAD))
        lines = cover.get("lines") or [self.E.ep.get("title", "")]
        y = 520
        for k, line in enumerate(lines):
            size = 150
            while tw(line, size, "anton") > 940 and size > 60:
                size -= 6
            top, bot = B.ink_box(line, "anton", size)
            if k == len(lines) - 1:
                d = ImageDraw.Draw(frame)
                d.rectangle([70, y + top - 10, 90 + tw(line, size, "anton"), y + bot + 14], fill=LEMON)
            B.draw_text(frame, 80, y, line, "anton", size, INK)
            y += size + 30
        role = "host" if "host" in self.kits else self.roles[0]
        pose = "point" if "point" in self.kits[role]["poses"] else "talk"
        img = self.avatar_image(role, pose, "wide", False, 0.98)
        B.paste(frame, img, 540 - img.width / 2, H + 30 - img.height)
        if cover.get("stamp"):
            st = Sticker({"text": cover["stamp"], "x": 760, "y": y + 70, "rot": -5, "size": 52}, {"seed": 1, "photos": {}})
            art = st.frame_image(10)
            B.paste(frame, art, 760 - art.width / 2, y + 70 - art.height / 2)
        return frame.convert("RGB")

    def events(self):
        ev = [("thud", 0.02)]                               # the hook lands with a hit on the very first frame
        for i, shot in enumerate(self.E.shots):
            if i > 0:
                ev.append(("whoosh_soft", shot["start"]))
            for el in self.elements[i]:
                ev += el.sounds(shot["start"] + el.at)
        return ev
