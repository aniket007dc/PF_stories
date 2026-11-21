"""Build a Taali reel: Gujarati taught on a garba beat, in rhyme (styles/taali/STYLE.md).

Its own engine, not the other styles': the episode's `lesson` is a song on a bar grid. Every line takes whole bars;
Sawaj the lion sings the Gujarati word, Lali the flamingo sings back what it means, and every taught word rhymes with
the others in its group. The music (tools/taali_music.py) and the dance are made from the same grid, so the dhol hits,
the dandiya clicks and the words land together.

    python3 tools/build_taali.py styles/taali/ep00-taali-sample             # the reel, its beat, its cue sheet
    python3 tools/build_taali.py EP --check                                 # only the lesson's checks
    python3 tools/build_taali.py EP --frame 3.2 --frame 20                  # stills, into EP/media/keyframes/
    python3 tools/build_taali.py EP --cover                                 # media/final/cover.jpg

What it writes, in the episode's folder:
- media/final/<episode>.mp4: the reel, 1080x1920, 30 fps
- media/audio/beat.m4a: the music alone, to sing or record the voice over
- build/lyrics.md: the cue sheet: every line, who sings it, its bar and its second
- checks/storyboard.jpg: a frame from every few lines

Voice: a file per line in media/audio/lines/<line id>.(wav|mp3|m4a) is placed on its line's first beat (and sped up a
little if it's longer than its bars). Without them the reel is built with the music alone and the sing-along captions.
"""
import argparse
import json
import math
import multiprocessing as mp
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taali_cast as cast   # noqa: E402
import taali_music as music  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30
FONT = ROOT / "brand" / "fonts" / "BalooBhai2-Variable.ttf"

INK = (74, 8, 30)
WHITE = (255, 255, 255)
CREAM = (255, 244, 220)
RED = (200, 16, 46)
MARIGOLD = (255, 176, 0)
OUTLINE = (46, 16, 30)
RHYME_COLORS = {"teal": (0, 140, 150), "pink": (214, 40, 112), "green": (20, 140, 70), "blue": (40, 80, 200),
                "orange": (226, 96, 0), "purple": (120, 50, 170)}
WHO_LABEL = {"sawaj": "SAWAJ", "lali": "LALI", "both": "BANNE"}   # banne: both, in Gujarati
CHARS = ("sawaj", "lali")

SHOWS = ("title", "word", "meaning", "rhyme", "chorus", "turn", "blank", "ask", "bye")


# ---------------------------------------------------------------- the lesson, and its checks
def load(ep_dir):
    ep_dir = Path(ep_dir)
    ep = json.loads((ep_dir / "episode.json").read_text())
    client = {}
    slug = ep.get("client")
    if slug and (ROOT / "clients" / slug / "client.json").exists():
        client = json.loads((ROOT / "clients" / slug / "client.json").read_text())
    return ep, client


def words_of(text):
    return [w for w in text.split() if w]


def bare(w):
    return re.sub(r"[^a-z_]", "", w.lower())


def check(ep):
    """The lesson's rules (STYLE.md → Rules). Returns a list of problems; empty is good."""
    L = ep.get("lesson") or {}
    bad = []
    rhymes = L.get("rhymes") or {}
    words = {w["id"]: w for w in L.get("words") or []}
    if not words:
        bad.append("lesson.words is empty: a reel teaches 4 to 8 words")
    if not 4 <= len(words) <= 8:
        bad.append("teach 4 to 8 words a reel (this one has {})".format(len(words)))
    groups = {}
    for w in words.values():
        for k in ("gu", "roman", "meaning", "rhyme"):
            if not w.get(k):
                bad.append("word {} has no {}".format(w.get("id"), k))
        g = rhymes.get(w.get("rhyme"))
        if not g:
            bad.append("word {}: rhyme group '{}' isn't in lesson.rhymes".format(w.get("id"), w.get("rhyme")))
            continue
        groups.setdefault(w["rhyme"], []).append(w["id"])
        if not w.get("roman", "").lower().endswith(g["tail"].lower()):
            bad.append("word {} ({}) doesn't end in its rhyme '-{}': every taught word rhymes".format(
                w["id"], w.get("roman"), g["tail"]))
        if not w.get("gu", "").endswith(g["tail_gu"]):
            bad.append("word {} ({}) doesn't end in its Gujarati rhyme '{}'".format(w["id"], w.get("gu"), g["tail_gu"]))
    for k, ids in groups.items():
        if len(ids) < 2:
            bad.append("rhyme group '{}' has one word ({}): a rhyme needs two or more".format(k, ids[0]))
    lines = L.get("lines") or []
    if not lines:
        bad.append("lesson.lines is empty")
    seen_word, seen_meaning = set(), set()
    for i, ln in enumerate(lines):
        lid = ln.get("id", "#{}".format(i + 1))
        if ln.get("who") not in ("sawaj", "lali", "both"):
            bad.append("{}: who is sawaj, lali or both".format(lid))
        if ln.get("show") not in SHOWS:
            bad.append("{}: show is one of {}".format(lid, ", ".join(SHOWS)))
        if not ln.get("say"):
            bad.append("{}: no words to sing (say)".format(lid))
        n = len(words_of(ln.get("say", "")))
        beats = 4 * int(ln.get("bars", 1))
        if n > beats * 2:
            bad.append("{}: {} words in {} beats is too many to sing: give it another bar or fewer words".format(
                lid, n, beats))
        if ln.get("on") is not None:
            on = ln["on"]
            if len(on) != n:
                bad.append("{}: 'on' has {} beats for {} words: one beat per word".format(lid, len(on), n))
            elif any(b <= a for a, b in zip(on, on[1:])) or (on and (on[0] < 0 or on[-1] >= beats)):
                bad.append("{}: 'on' beats go up, from 0 to under {}".format(lid, beats))
        if ln.get("show") in ("word", "meaning"):
            wid = ln.get("word")
            if wid not in words:
                bad.append("{}: word '{}' isn't in lesson.words".format(lid, wid))
            elif ln["show"] == "word":
                seen_word.add(wid)
            else:
                if wid not in seen_word:
                    bad.append("{}: the meaning of {} comes before the word is sung".format(lid, wid))
                seen_meaning.add(wid)
        if ln.get("show") in ("rhyme", "chorus", "blank"):
            for row in ln.get("rows") or []:
                for wid in row:
                    if wid not in words:
                        bad.append("{}: word '{}' isn't in lesson.words".format(lid, wid))
            if not ln.get("rows"):
                bad.append("{}: a {} line needs rows of word ids".format(lid, ln["show"]))
        if ln.get("show") == "blank" and not ln.get("answer"):
            bad.append("{}: a blank line needs the answer that fills it".format(lid))
    for wid in words:
        if wid not in seen_word or wid not in seen_meaning:
            bad.append("word {} must be sung (show: word) and then explained (show: meaning)".format(wid))
    if lines and lines[0].get("show") != "title":
        bad.append("the first line is the title (the hook)")
    if lines and lines[-1].get("show") != "bye":
        bad.append("the last line is the sign-off (show: bye)")
    hook = L.get("hook", "")
    if not hook or len(words_of(hook)) > 6:
        bad.append("lesson.hook is the reel's first words on screen: 6 words at most")
    bpm = L.get("bpm", 128)
    if not 116 <= bpm <= 140:
        bad.append("bpm {}: keep the garba between 116 and 140".format(bpm))
    secs = sum(int(x.get("bars", 1)) for x in lines) * 240.0 / bpm
    if not 20 <= secs <= 75:
        bad.append("the reel is {:.0f} s: keep it between 20 and 75".format(secs))
    for w in words.values():
        for k in ("gu", "roman", "meaning", "en"):
            if "—" in (w.get(k) or "") or "–" in (w.get(k) or ""):
                bad.append("word {}: no dashes on screen".format(w["id"]))
    return bad


class Plan:
    """The timeline: every line's start and end in seconds, and every sung word's onset."""

    def __init__(self, ep, ep_dir=None):
        L = ep["lesson"]
        self.lines_dir = Path(ep_dir) / "media" / "audio" / "lines" if ep_dir else None
        self.L = L
        self.bpm = float(L.get("bpm", 128))
        self.beat = 60.0 / self.bpm
        self.bar = self.beat * 4
        self.words = {w["id"]: w for w in L["words"]}
        self.rhymes = L["rhymes"]
        self.lines = []
        t = 0.0
        for ln in L["lines"]:
            d = dict(ln)
            d["t0"] = t
            d["t1"] = t + int(ln.get("bars", 1)) * self.bar
            d["voice"] = self.voice_of(d)
            d["onsets"] = self.onsets(d)
            self.lines.append(d)
            t = d["t1"]
        self.length = t
        # the music plan: consecutive lines of the same part make a section
        self.sections = []
        for d in self.lines:
            part = d.get("part", "verse")
            if self.sections and self.sections[-1][0] == part:
                self.sections[-1][1] += int(d.get("bars", 1))
            else:
                self.sections.append([part, int(d.get("bars", 1))])
        self.order = [w["id"] for w in L["words"]]

    def grid(self, d):
        ws = words_of(d["say"])
        beats = 4 * int(d.get("bars", 1))
        on = d.get("on")
        if not on or len(on) != len(ws):
            span = beats - (1 if d.get("show") == "blank" else 0.5)
            on = [round(i * span / max(1, len(ws)) * 2) / 2 for i in range(len(ws))]
        return ws, beats, on

    def voice_of(self, d):
        """A voiced line, and where it goes. Its file is media/audio/lines/<id>.mp3 (or .wav, .m4a); a "both" line can
        instead be two takes, <id>.sawaj.mp3 and <id>.lali.mp3, which are mixed here, each lined up on its first sound.
        Word timings come from <id>.json when tools/taali_voice.py made it; a take downloaded from elevenlabs.io has
        none, so its first and last sounds are found in the audio. The voice is placed so its first word lands on the
        line's first beat, and sped up a little (at most 1.6x) when it would run past the line's end."""
        if not self.lines_dir:
            return None
        srcs = []
        for stem in [d["id"]] + ["{}.{}".format(d["id"], w) for w in CHARS]:
            for ext in ("wav", "mp3", "m4a"):
                f = self.lines_dir / "{}.{}".format(stem, ext)
                if f.exists():
                    srcs.append(f)
                    break
            if srcs and stem == d["id"]:
                break
        if not srcs:
            return None
        try:
            al = json.loads((self.lines_dir / "{}.json".format(d["id"])).read_text())
        except (OSError, ValueError):
            al = {}
        words = al.get("words") or []
        takes = []
        for f in srcs:
            first, last, dur = sound_span(f)
            if words and f == srcs[0]:
                first, last = float(words[0]["start"]), float(words[-1]["end"])
            takes.append({"src": f, "first": first, "last": last, "dur": dur})
        first = max(t["first"] for t in takes)
        last = max(t["last"] - t["first"] for t in takes) + first
        _, beats, on = self.grid(d)
        land = d["t0"] + on[0] * self.beat
        room = d["t1"] - land - 0.06
        tempo = max(1.0, min(1.6, (last - first) / room)) if room > 0 else 1.0
        for t in takes:
            t["start"] = land - t["first"] / tempo
        return {"takes": takes, "start": land - first / tempo, "tempo": tempo, "words": words,
                "span": (first, last)}

    def onsets(self, d):
        """[(word, t_on, t_off)]: each sung word, from the voice's own timing when the line is voiced, or else on the
        grid, by `on` (beats from the line's start) or spread evenly over the line's beats in eighth notes."""
        ws, beats, on = self.grid(d)
        v = d.get("voice")
        if v and len(v["words"]) >= len([w for w in ws if "_" not in w]):
            out, k = [], 0
            for i, w in enumerate(ws):
                if "_" in w:                      # the viewer's blank: it keeps its beat
                    a = d["t0"] + on[i] * self.beat
                    out.append((w, a, min(d["t1"], a + self.beat)))
                    continue
                vw = v["words"][k]
                k += 1
                a = v["start"] + float(vw["start"]) / v["tempo"]
                b = v["start"] + float(vw["end"]) / v["tempo"] + 0.12
                out.append((w, a, b))
            return out
        if v and not v["words"]:
            # no word timings (a take from elevenlabs.io): spread the words over the voice's sound, by their length
            a0 = v["start"] + v["span"][0] / v["tempo"]
            a1 = v["start"] + v["span"][1] / v["tempo"]
            sung = [w for w in ws if "_" not in w]
            total = sum(len(w) + 2 for w in sung) or 1
            out, x = [], a0
            for i, w in enumerate(ws):
                if "_" in w:
                    a = d["t0"] + on[i] * self.beat
                    out.append((w, a, min(d["t1"], a + self.beat)))
                    continue
                dx = (a1 - a0) * (len(w) + 2) / total
                out.append((w, x, x + dx))
                x += dx
            return out
        out = []
        for i, w in enumerate(ws):
            a = d["t0"] + on[i] * self.beat
            b = d["t0"] + (on[i + 1] * self.beat if i + 1 < len(ws) else min(beats, on[i] + 1.5) * self.beat)
            out.append((w, a, b))
        return out

    def line_at(self, t):
        for i, d in enumerate(self.lines):
            if d["t0"] <= t < d["t1"]:
                return i, d
        return len(self.lines) - 1, self.lines[-1]

    def learned(self, t):
        """How many words have been explained by time t (their meaning line has started)."""
        got = set()
        for d in self.lines:
            if d["t0"] <= t and d.get("show") == "meaning":
                got.add(d["word"])
        return len(got)

    def part_of(self, t):
        return self.line_at(t)[1].get("part", "verse")


# ---------------------------------------------------------------- type
_fonts = {}


def font(size, weight="ExtraBold"):
    key = (int(size), weight)
    if key not in _fonts:
        f = ImageFont.truetype(str(FONT), int(size), layout_engine=ImageFont.Layout.RAQM)
        try:
            f.set_variation_by_name(weight)
        except (OSError, ValueError):
            pass
        _fonts[key] = f
    return _fonts[key]


def runs_image(runs, size, stroke=0, stroke_fill=OUTLINE, weight="ExtraBold", underline=None):
    """Text in coloured runs, side by side: [(text, colour)]. underline: the index of a run to underline with a
    squiggle in its own colour (the rhyme)."""
    f = font(size, weight)
    widths = [f.getlength(t) for t, _ in runs]
    asc, desc = f.getmetrics()
    pad = stroke + 6
    w = int(sum(widths)) + 2 * pad
    h = asc + desc + 2 * pad + (int(size * 0.16) if underline is not None else 0)
    img = Image.new("RGBA", (max(1, w), h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = pad
    for i, ((t, col), wd) in enumerate(zip(runs, widths)):
        d.text((x, pad), t, font=f, fill=col, stroke_width=stroke, stroke_fill=stroke_fill)
        if underline == i and t.strip():
            y = pad + asc + desc * 0.25
            pts = [(x + k, y + math.sin(k / max(6, size * 0.09)) * size * 0.035) for k in range(0, int(wd), 3)]
            if len(pts) > 1:
                d.line(pts, fill=col, width=max(4, int(size * 0.06)), joint="curve")
        x += wd
    return img


def tight(img, pad=4):
    """Crop a text image to its ink, so cards can stack text by what shows, not by the font's line box."""
    box = img.getchannel("A").getbbox()
    if not box:
        return img
    x0, y0, x1, y1 = box
    return img.crop((max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad)))


def stack(card, items, top, bottom, gap):
    """Put items (images) one under another, centred, in the space between top and bottom of the card."""
    total = sum(i.height for i in items) + gap * (len(items) - 1)
    y = top + max(0, (bottom - top - total) // 2)
    for i in items:
        card.alpha_composite(i, ((card.width - i.width) // 2, int(y)))
        y += i.height + gap


def fit(img, max_w, max_h=None):
    s = min(1.0, max_w / img.width, (max_h / img.height) if max_h else 1.0)
    if s < 1.0:
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)
    return img


def split_tail(text, tail):
    if tail and text.lower().endswith(tail.lower()):
        return text[: len(text) - len(tail)], text[len(text) - len(tail):]
    return text, ""


def word_runs(w, group, roman=False, base=INK, blank=False):
    if roman:
        head, tail = split_tail(w["roman"].upper(), group["tail"].upper())
    else:
        head, tail = split_tail(w["gu"], group["tail_gu"])
    col = RHYME_COLORS.get(group.get("color"), RHYME_COLORS["teal"])
    if blank:
        tail = "_" * max(2, len(tail) if roman else 2)
        col = (170, 150, 150)
    return [(head, base), (tail, col)], 1


def pill(text, size, fill, ink, pad_x=30, pad_y=10, ow=5):
    t = runs_image([(text, ink)], size)
    w, h = t.width + 2 * pad_x, t.height + 2 * pad_y
    img = Image.new("RGBA", (w + 2 * ow, h + 2 * ow), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w + 2 * ow - 1, h + 2 * ow - 1], radius=(h + 2 * ow) // 2, fill=OUTLINE)
    d.rounded_rectangle([ow, ow, w + ow - 1, h + ow - 1], radius=h // 2, fill=fill)
    img.alpha_composite(t, (ow + pad_x, ow + pad_y - int(size * 0.06)))
    return img


# ---------------------------------------------------------------- the cards
def card_frame(w, h, inner=CREAM):
    """The card every lesson sits on: a bandhani-red frame of white dots, a cream panel, a mirror in each corner."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=44, fill=OUTLINE)
    d.rounded_rectangle([6, 6, w - 7, h - 7], radius=40, fill=RED)
    step = 22
    for x in range(30, w - 20, step):
        for y in (20, h - 21):
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=WHITE)
            d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(150, 10, 36))
    for y in range(42, h - 30, step):
        for x in (20, w - 21):
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=WHITE)
            d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=(150, 10, 36))
    d.rounded_rectangle([36, 36, w - 37, h - 37], radius=26, fill=OUTLINE)
    d.rounded_rectangle([40, 40, w - 41, h - 41], radius=24, fill=inner)
    for x, y in ((40, 40), (w - 41, 40), (40, h - 41), (w - 41, h - 41)):
        d.ellipse([x - 17, y - 17, x + 17, y + 17], fill=OUTLINE)
        d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=(255, 214, 64))
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=(226, 232, 240))
        d.ellipse([x - 6, y - 7, x - 1, y - 2], fill=WHITE)
    return img


def tab(text):
    return pill(text, 34, OUTLINE, (255, 214, 64), pad_x=22, pad_y=4, ow=3)


class Cards:
    """Every card a line can show, drawn once and kept."""

    def __init__(self, plan, client, ep):
        self.p = plan
        self.client = client
        self.ep = ep
        self.cache = {}

    def get(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def word(self, wid, meaning):
        def make():
            w = self.p.words[wid]
            g = self.p.rhymes[w["rhyme"]]
            cw, ch = 900, 500
            img = card_frame(cw, ch)
            n = self.p.order.index(wid) + 1
            tb = tab("SHABD {} / {}".format(n, len(self.p.order)))
            img.alpha_composite(tb, ((cw - tb.width) // 2, 14))
            runs, u = word_runs(w, g)
            gu = fit(tight(runs_image(runs, 200, underline=u)), cw - 140, 190)
            runs, u = word_runs(w, g, roman=True)
            ro = fit(tight(runs_image(runs, 76)), cw - 160)
            if meaning:
                txt = "= " + w["meaning"].upper() + ("  ·  " + w["en"].upper() if w.get("en") else "")
                pl = fit(pill(txt, 52, MARIGOLD, INK), cw - 120)
            else:
                pl = pill("=  ?", 52, (236, 224, 206), (150, 120, 120))
            stack(img, [gu, ro, pl], 66, ch - 44, 22)
            return img
        return self.get(("word", wid, meaning), make)

    def rows(self, rows, hi=None, blank_tail=None, title=None):
        """Rhyming words side by side, a row per rhyme group; hi: the word id being sung; blank_tail: a word id whose
        rhyme is still a blank."""
        def make():
            cw = 940
            row_h = 200 if len(rows) > 1 else 250
            top = 66
            ch = top + row_h * len(rows) + 40
            img = card_frame(cw, ch)
            if title:
                tb = tab(title)
                img.alpha_composite(tb, ((cw - tb.width) // 2, 14))
            for r, row in enumerate(rows):
                cells = []
                for wid in row:
                    w = self.p.words[wid]
                    g = self.p.rhymes[w["rhyme"]]
                    blank = wid == blank_tail
                    on = wid == hi
                    base = INK if (hi is None or on) else (160, 120, 130)
                    gu = tight(runs_image(word_runs(w, g, base=base, blank=blank)[0], 150, underline=1 if on else None))
                    ro = tight(runs_image(word_runs(w, g, roman=True, base=base, blank=blank)[0], 54))
                    cw_ = max(gu.width, ro.width) + 36
                    cell = Image.new("RGBA", (cw_, gu.height + ro.height + 34), (0, 0, 0, 0))
                    if on:
                        ImageDraw.Draw(cell).rounded_rectangle([0, 0, cell.width - 1, cell.height - 1], radius=26,
                                                               fill=(255, 214, 64, 255), outline=OUTLINE, width=4)
                    cell.alpha_composite(gu, ((cell.width - gu.width) // 2, 10))
                    cell.alpha_composite(ro, ((cell.width - ro.width) // 2, gu.height + 18))
                    cells.append(cell)
                gap = 26
                total = sum(c.width for c in cells) + gap * (len(cells) - 1)
                s = min(1.0, (cw - 100) / total, (row_h - 14) / max(c.height for c in cells))
                x = (cw - total * s) / 2
                y0 = top + r * row_h
                for c in cells:
                    cc = c.resize((max(1, int(c.width * s)), max(1, int(c.height * s))), Image.LANCZOS) if s < 1 else c
                    img.alpha_composite(cc, (int(x), int(y0 + (row_h - cc.height) / 2)))
                    x += c.width * s + gap * s
                if r < len(rows) - 1:
                    ImageDraw.Draw(img).line([(90, y0 + row_h), (cw - 90, y0 + row_h)], fill=(230, 200, 170),
                                             width=4)
            return img
        return self.get(("rows", json.dumps(rows), hi, blank_tail, title), make)

    def title(self):
        def make():
            L = self.p.L
            cw = 940
            img = card_frame(cw, 500)
            tb = tab(self.ep.get("tag") or "CLASS")
            img.alpha_composite(tb, ((cw - tb.width) // 2, 14))
            gu = fit(tight(runs_image([(L["title_gu"], INK)], 140)), cw - 120, 170)
            ro = fit(tight(runs_image([(L["title"].upper(), RHYME_COLORS["pink"])], 68)), cw - 140)
            hk = fit(pill(L["hook"].upper(), 48, MARIGOLD, INK), cw - 120)
            stack(img, [gu, ro, hk], 66, 456, 26)
            return img
        return self.get(("title",), make)

    def say_card(self, gu_text, roman, meaning, label, foot=None):
        def make():
            cw = 920
            img = card_frame(cw, 500)
            tb = tab(label)
            img.alpha_composite(tb, ((cw - tb.width) // 2, 14))
            gu = fit(tight(runs_image([(gu_text, INK)], 160)), cw - 120, 180)
            ro = fit(tight(runs_image([(roman.upper(), RHYME_COLORS["pink"])], 68)), cw - 140)
            pl = fit(pill("= " + meaning.upper(), 48, MARIGOLD, INK), cw - 120)
            stack(img, [gu, ro, pl], 66, 456, 24)
            return img
        return self.get(("say", gu_text, roman, meaning, label), make)


# ---------------------------------------------------------------- the stage (drawn once)
def gradient():
    y = np.linspace(0, 1, H)[:, None]
    stops = [(0.0, (22, 8, 54)), (0.45, (64, 14, 80)), (0.75, (104, 18, 64)), (1.0, (70, 10, 34))]
    out = np.zeros((H, 1, 3))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        m = (y >= a) & (y <= b)
        k = ((y - a) / (b - a))
        for c in range(3):
            out[..., c] = np.where(m, ca[c] + (cb[c] - ca[c]) * k, out[..., c])
    return np.repeat(out, W, axis=1)


def stage():
    arr = gradient()
    img = Image.fromarray(arr.astype("uint8")).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    # a faint Kutchi lattice: diamonds of stitched dots
    for yy in range(160, 1400, 90):
        for xx in range(0 if (yy // 90) % 2 else 45, W + 90, 90):
            d.polygon([(xx, yy - 20), (xx + 20, yy), (xx, yy + 20), (xx - 20, yy)], outline=(255, 200, 120, 22))
            d.ellipse([xx - 3, yy - 3, xx + 3, yy + 3], fill=(255, 220, 150, 26))
    # warm glow where the dancers are
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([40, 1080, 1040, 1760], fill=(255, 140, 60, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img.alpha_composite(glow)
    # the dance floor and its rangoli
    d.ellipse([-160, 1470, W + 160, 2140], fill=(84, 14, 40, 255))
    d.ellipse([-160, 1470, W + 160, 2140], outline=(255, 176, 0, 90), width=4)
    cx, cy = 540, 1596
    for r, col, n in ((330, (255, 176, 0, 120), 24), (250, (214, 40, 112, 130), 18), (170, (0, 150, 160, 140), 12),
                      (95, (255, 244, 220, 140), 8)):
        for i in range(n):
            a = 2 * math.pi * i / n
            px, py = cx + r * math.cos(a), cy + r * 0.28 * math.sin(a)
            pr = r * 0.16
            d.ellipse([px - pr, py - pr * 0.3, px + pr, py + pr * 0.3], fill=col)
    # the toran over the top: flags with mirrors, and mango leaves
    d.line([(0, 34), (W, 34)], fill=(255, 214, 64, 255), width=5)
    cols = [(200, 16, 46), (24, 150, 88), (255, 176, 0), (214, 40, 112), (0, 140, 150)]
    for i, x in enumerate(range(0, W + 60, 60)):
        if i % 2:
            d.polygon([(x - 18, 36), (x + 18, 36), (x, 96)], fill=(30, 120, 50, 255), outline=OUTLINE)
            d.line([(x, 40), (x, 88)], fill=(120, 200, 110, 255), width=2)
        else:
            c = cols[(i // 2) % len(cols)]
            d.polygon([(x - 26, 36), (x + 26, 36), (x + 26, 96), (x, 120), (x - 26, 96)], fill=c + (255,),
                      outline=OUTLINE)
            d.ellipse([x - 8, 70, x + 8, 86], fill=(226, 232, 240, 255), outline=(255, 214, 64, 255), width=2)
    return img


def catenary(x0, y0, x1, y1, sag, n):
    pts = []
    for i in range(n):
        t = i / (n - 1)
        pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + sag * 4 * t * (1 - t)))
    return pts


BULB_COLS = [(255, 176, 0), (255, 120, 170), (0, 210, 220), (255, 240, 200), (120, 230, 120)]


def bulb_sprites():
    out = []
    for c in BULB_COLS:
        levels = []
        for lv in (0.25, 0.55, 1.0):
            g = Image.new("RGBA", (60, 60), (0, 0, 0, 0))
            d = ImageDraw.Draw(g)
            d.ellipse([10, 10, 50, 50], fill=c + (int(110 * lv),))
            g = g.filter(ImageFilter.GaussianBlur(7))
            d = ImageDraw.Draw(g)
            core = tuple(int(v * (0.45 + 0.55 * lv)) for v in c)
            d.ellipse([23, 23, 37, 37], fill=core + (255,))
            d.ellipse([26, 25, 30, 29], fill=(255, 255, 255, int(255 * lv)))
            levels.append(g)
        out.append(levels)
    return out


def light_strands():
    pts = catenary(-20, 150, W + 20, 150, 90, 22)
    pts += catenary(14, 200, 40, 1250, 0, 18)
    pts += catenary(W - 14, 200, W - 40, 1250, 0, 18)
    return pts


def dancer_sprite(col, arms_up):
    s = cast.Pen(70, 110)
    s.oval(35, 20, 12, 12, col, ow=0)
    s.poly([(35, 32), (60, 96), (10, 96)], col, ow=0)
    if arms_up:
        s.limb([(30, 42), (14, 14)], 5, col, ow=0)
        s.limb([(40, 42), (56, 14)], 5, col, ow=0)
    else:
        s.limb([(30, 42), (8, 56)], 5, col, ow=0)
        s.limb([(40, 42), (62, 30)], 5, col, ow=0)
    s.limb([(28, 96), (26, 108)], 4, col, ow=0)
    s.limb([(42, 96), (44, 108)], 4, col, ow=0)
    return s.done()


# ---------------------------------------------------------------- the reel
def ease_out_back(x):
    c1, c3 = 1.70158, 2.70158
    x = max(0.0, min(1.0, x))
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


class Reel:
    def __init__(self, ep_dir):
        self.dir = Path(ep_dir)
        self.ep, self.client = load(ep_dir)
        self.plan = Plan(self.ep, self.dir)
        self.cards = Cards(self.plan, self.client, self.ep)
        self._stage = None
        self.name = self.client.get("logo_text") or self.ep.get("series") or "TAALI"
        self.handle = self.client.get("instagram") or ""

    # -------- the beat, as numbers the pictures move by
    def since(self, t, steps):
        """Seconds since the last of these 16th-steps in the current bar (or the bar before)."""
        best = 9.0
        bar_i = math.floor(t / self.plan.bar)
        for b in (bar_i, bar_i - 1):
            for s in steps:
                tt = b * self.plan.bar + s * self.plan.beat / 4
                if tt <= t:
                    best = min(best, t - tt)
        return best

    def until(self, t, steps):
        best = 9.0
        bar_i = math.floor(t / self.plan.bar)
        for b in (bar_i, bar_i + 1):
            for s in steps:
                tt = b * self.plan.bar + s * self.plan.beat / 4
                if tt > t:
                    best = min(best, tt - t)
        return best

    def mouth(self, t, d, who):
        if who not in (d.get("who"), ) and d.get("who") != "both":
            return 0.0
        m = 0.0
        for w, a, b in d["onsets"]:
            if "_" in w:
                continue
            n = max(1, len(re.findall(r"[aeiouAEIOU]+", w)))
            dur = min(b - a, 0.42 * n)
            for k in range(n):
                s = a + dur * k / n
                if s <= t < s + 0.3:
                    m = max(m, math.exp(-(t - s) * 9) * (1.0 if k == 0 else 0.75))
                elif s - 0.04 <= t < s:
                    m = max(m, (t - s + 0.04) / 0.04 * 0.6)
        return m

    def poses(self, t):
        p = self.plan
        bp = t / p.beat
        ph = bp - math.floor(bp)
        i, d = p.line_at(t)
        intro_still = t < p.bar and d.get("part") == "intro"
        bob = 0 if intro_still else 11 * math.exp(-5.5 * ph)
        last = d is p.lines[-1] and t > d["t0"] + p.bar
        sw = dict(
            bob=bob, tilt=7 * math.sin(math.pi * bp), lean=2.5 * math.sin(math.pi * bp),
            hit_r=0 if intro_still else math.exp(-self.since(t, music.GROOVE["bass"]) * 11),
            hit_l=0 if intro_still else math.exp(-self.since(t, music.GROOVE["tilli"]) * 13),
            mouth=self.mouth(t, d, "sawaj"), blink=1 if (t % 3.7) < 0.12 else 0,
            step=0 if intro_still else math.sin(math.pi * bp / 2), tail=math.sin(math.pi * bp * 0.5),
            look=0.5 if d.get("who") == "lali" else 0.1, happy=1 if last else 0)
        sc = self.since(t, music.GROOVE["dandiya"])
        un = self.until(t, music.GROOVE["dandiya"])
        click = max(math.exp(-sc * 9), 1 - un / 0.12 if un < 0.12 else 0)
        spin = 0.0
        if d.get("part") in ("chorus", "rhyme") or d.get("show") == "rhyme":
            k = (t - d["t0"]) / p.beat
            if k < 1.0 and (p.lines.index(d) % 2 == 0):
                spin = k
        la = dict(
            bob=bob * 0.9, tilt=9 * math.sin(math.pi * bp + 0.6), click=0.15 if intro_still else click,
            mouth=self.mouth(t, d, "lali"), blink=1 if ((t + 1.3) % 4.1) < 0.12 else 0,
            step=0 if intro_still else -math.sin(math.pi * bp / 2), skirt=math.sin(math.pi * bp), spin=spin,
            happy=1 if last else 0)
        return sw, la, d

    # -------- one frame
    def base(self):
        if self._stage is None:
            self._stage = stage()
            self._bulbs = bulb_sprites()
            self._strands = light_strands()
            dark = (36, 8, 46, 255)
            self._dancers = [dancer_sprite(dark, False), dancer_sprite(dark, True)]
            self._petal = [cast.marigold(0.8).rotate(a, resample=Image.BICUBIC, expand=True) for a in range(0, 360, 45)]
            self._diya = [cast.diya(0, 0.85), cast.diya(1.0, 0.85)]
            rng = np.random.default_rng(3)
            self._petals = [(rng.uniform(0, W), rng.uniform(0, 1), rng.uniform(120, 260), rng.uniform(-40, 40),
                             int(rng.integers(0, 8))) for _ in range(34)]
            self._spot = self.spotlight()
        return self._stage

    def spotlight(self):
        g = Image.new("RGBA", (560, 1200), (0, 0, 0, 0))
        d = ImageDraw.Draw(g)
        d.polygon([(250, 0), (310, 0), (520, 1160), (40, 1160)], fill=(255, 236, 180, 46))
        d.ellipse([60, 1100, 500, 1190], fill=(255, 236, 180, 60))
        return g.filter(ImageFilter.GaussianBlur(26))

    def frame(self, t):
        p = self.plan
        img = self.base().copy()
        bp = t / p.beat
        beat_i = int(math.floor(bp))
        ph = bp - beat_i
        i, d = p.line_at(t)
        part = d.get("part", "verse")
        busy = part in ("chorus", "turn", "outro")

        # the lights chase on the beat
        for k, (x, y) in enumerate(self._strands):
            c = k % len(BULB_COLS)
            on = (k + beat_i) % 3 == 0
            lv = 2 if on and ph < 0.5 else (1 if on or busy else 0)
            spr = self._bulbs[c][lv]
            img.alpha_composite(spr, (int(x - 30), int(y - 30)))

        # far dancers circling the garbo behind everyone
        n = 14
        for k in range(n):
            a = 2 * math.pi * k / n + t * 0.35
            x = 540 + 560 * math.cos(a)
            y = 1300 + 30 * math.sin(a) - 8 * math.exp(-5 * ph)
            spr = self._dancers[(k + beat_i) % 2]
            img.alpha_composite(spr, (int(x - 35), int(y - 55)))

        # the garbo in the middle, its flame flickering
        flame = 0.75 + 0.25 * math.sin(t * 17) * math.sin(t * 5.3)
        g = cast.garbo(flame, 0.72)
        glow_r = 120 + 30 * math.exp(-self.since(t, music.GROOVE["bass"]) * 8)
        gl = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
        ImageDraw.Draw(gl).ellipse([200 - glow_r, 200 - glow_r, 200 + glow_r, 200 + glow_r], fill=(255, 170, 60, 60))
        gl = gl.filter(ImageFilter.GaussianBlur(40))
        img.alpha_composite(gl, (540 - 200, 1470 - 200))
        img.alpha_composite(g, (540 - g.width // 2, 1560 - g.height))

        # the singer's spotlight, then the two of them
        sw, la, _ = self.poses(t)
        who = d.get("who")
        for name, x in (("sawaj", 270), ("lali", 790)):
            if who in (name, "both"):
                img.alpha_composite(self._spot, (x - 280, 380))
        s = cast.sawaj(sw)
        s = s.resize((int(s.width * 0.8), int(s.height * 0.8)), Image.LANCZOS)
        img.alpha_composite(s, (270 - s.width // 2, 1560 - s.height))
        l = cast.lali(la)
        l = l.resize((int(l.width * 0.8), int(l.height * 0.8)), Image.LANCZOS)
        img.alpha_composite(l, (790 - l.width // 2, 1560 - l.height))

        # marigold petals in the busy parts
        if busy:
            for (x0, y0, sp, drift, ai) in self._petals:
                y = ((y0 * 1500 + (t - d["t0"] + 5) * sp) % 1500) + 140
                x = x0 + drift * math.sin(t * 1.3 + y0 * 9)
                pt = self._petal[(ai + int(t * 6)) % 8]
                img.alpha_composite(pt, (int(x - pt.width / 2), int(y)))

        self.header(img, t)
        self.card(img, t, i, d, ph)
        self.karaoke(img, t, d)
        return img.convert("RGB")

    def header(self, img, t):
        name = pill(self.name.upper(), 46, (200, 16, 46), (255, 255, 255), pad_x=26, pad_y=6)
        img.alpha_composite(name, (60, 236))
        tag = pill((self.ep.get("tag") or "CLASS").upper(), 40, (255, 176, 0), INK, pad_x=22, pad_y=6)
        img.alpha_composite(tag, (W - 60 - tag.width, 240))
        n = len(self.plan.order)
        got = self.plan.learned(t)
        dw = self._diya[0].width
        gap = 12
        x0 = (W - (n * dw + (n - 1) * gap)) // 2
        for k in range(n):
            img.alpha_composite(self._diya[1 if k < got else 0], (x0 + k * (dw + gap), 322))

    def card_for(self, t, d):
        p = self.plan
        show = d.get("show")
        C = self.cards
        if show == "title":
            return C.title()
        if show in ("word", "meaning"):
            return C.word(d["word"], show == "meaning")
        if show in ("rhyme", "chorus"):
            hi = self.sung_word(t, d)
            return C.rows(d["rows"], hi, title=d.get("label") or ("RHYME!" if show == "rhyme" else "SAATHE GAO!"))
        if show == "blank":
            reveal = d["t0"] + float(d.get("reveal", 3)) * p.beat
            blank = None
            if t < reveal:
                blank = d["rows"][0][-1]
            return C.rows(d["rows"], None if blank else d["rows"][0][-1], blank_tail=blank,
                          title=d.get("label") or "TAMARO VAARO!")
        if show in ("turn", "ask", "bye"):
            c = self.ep["lesson"].get(show) or {}
            label = c.get("label") or {"turn": "TAMARO VAARO!", "ask": "COMMENT KARO!", "bye": "FOLLOW " + self.handle}[show]
            return C.say_card(c.get("gu", ""), c.get("roman", ""), c.get("meaning", ""), label.upper())
        return None

    def sung_word(self, t, d):
        cur = None
        for w, a, b in d["onsets"]:
            if a <= t:
                cur = bare(w)
        if not cur:
            return None
        for row in d.get("rows") or []:
            for wid in row:
                if bare(self.plan.words[wid]["roman"]) == cur:
                    return wid
        return None

    def card(self, img, t, i, d, ph):
        art = self.card_for(t, d)
        if art is None:
            return
        p = self.plan
        # it pops in when the card changes; it bounces on every beat
        prev = p.lines[i - 1] if i > 0 else None
        fresh = prev is None or self.card_for(d["t0"] - 1e-3, prev) is not self.card_for(d["t0"] + 1e-3, d) \
            and not (prev.get("show") in ("word", "meaning") and prev.get("word") == d.get("word"))
        if d.get("show") in ("rhyme", "chorus", "blank") and prev is not None and prev.get("show") == d.get("show"):
            fresh = False
        k = (t - d["t0"]) / 0.32
        s = ease_out_back(k) if fresh and k < 1 else 1.0
        s *= 1 + 0.028 * math.exp(-6 * ph)
        if d.get("show") == "meaning" and k < 1:
            s *= 1 + 0.05 * math.sin(k * math.pi)
        a = art
        if s != 1.0:
            a = art.resize((max(1, int(art.width * s)), max(1, int(art.height * s))), Image.BICUBIC)
        cy = 652
        img.alpha_composite(a, (W // 2 - a.width // 2, int(cy - a.height / 2)))

    def karaoke(self, img, t, d):
        """The words being sung, word by word, with a mirror bouncing from word to word."""
        ws = d["onsets"]
        reveal_at = d["t0"] + float(d.get("reveal", 3)) * self.plan.beat if d.get("show") == "blank" else None
        size = 62
        f = font(size)
        items = []
        for w, a, b in ws:
            text = w
            if "_" in w and reveal_at is not None and t >= reveal_at:
                text = d["answer"].upper() + ("!" if not d["answer"].endswith("!") else "")
            items.append((text, a, b))
        # wrap into lines of at most 900 px
        lines, cur, cw = [], [], 0
        space = f.getlength(" ") * 1.7
        for it in items:
            wd = f.getlength(it[0])
            if cur and cw + space + wd > 900:
                lines.append(cur)
                cur, cw = [], 0
            cur.append(it)
            cw += (space if cw else 0) + wd
        if cur:
            lines.append(cur)
        top = 990 if len(lines) > 1 else 1010
        label = pill(WHO_LABEL.get(d.get("who"), ""), 30, (255, 176, 0) if d.get("who") == "sawaj" else
                     ((244, 132, 172) if d.get("who") == "lali" else (0, 190, 200)), INK, pad_x=16, pad_y=2, ow=3)
        img.alpha_composite(label, (W // 2 - label.width // 2, 918))
        for li, ln in enumerate(lines):
            total = sum(f.getlength(x[0]) for x in ln) + space * (len(ln) - 1)
            x = W / 2 - total / 2
            y = top + li * 78
            for text, a, b in ln:
                wd = f.getlength(text)
                if t >= a and t < b:
                    col, sc = MARIGOLD, 1.12
                elif t >= b:
                    col, sc = WHITE, 1.0
                else:
                    col, sc = (255, 255, 255), 1.0
                alpha = 255 if t >= a else 120
                if "_" in text:
                    col = (0, 210, 220)
                if reveal_at is not None and t >= reveal_at and text.startswith(d.get("answer", "~").upper()):
                    col, sc = (0, 210, 220), 1.04
                wi = runs_image([(text, col + (alpha,))], int(size * sc), stroke=7,
                                stroke_fill=OUTLINE + (alpha,))
                img.alpha_composite(wi, (int(x + wd / 2 - wi.width / 2), int(y - (wi.height - 92) / 2 - 10)))
                # the bouncing mirror over the word being sung
                if a <= t < b:
                    k = min(1.0, (t - a) / max(0.12, min(b - a, self.plan.beat)))
                    hop = math.sin(k * math.pi) * 18
                    bx, by = x + wd / 2, y - 6 - hop
                    dd = ImageDraw.Draw(img)
                    dd.ellipse([bx - 13, by - 13, bx + 13, by + 13], fill=OUTLINE)
                    dd.ellipse([bx - 10, by - 10, bx + 10, by + 10], fill=(255, 214, 64))
                    dd.ellipse([bx - 7, by - 7, bx + 7, by + 7], fill=(226, 232, 240))
                    dd.ellipse([bx - 4, by - 5, bx, by - 1], fill=WHITE)
                x += wd + space

    # -------- sound
    def audio(self, out_wav):
        p = self.plan
        bells = [d["t0"] for d in p.lines if d.get("show") == "word"]
        st, info = music.render([tuple(s) for s in p.sections], p.bpm, p.L.get("key", "D"), bells=bells)
        beat = self.dir / "media" / "audio" / "beat.m4a"
        beat.parent.mkdir(parents=True, exist_ok=True)
        music.write_wav(Path(out_wav).with_name("beat.wav"), st)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(Path(out_wav).with_name("beat.wav")), "-c:a", "aac",
                        "-b:a", "160k", str(beat)], check=True)
        # the voice lines, each placed so its first word lands on its line's first beat
        voiced = 0
        mix = st.copy()
        for d in p.lines:
            v = d.get("voice")
            if not v:
                continue
            sig, i = None, None
            for tk in v["takes"]:
                one = decode(tk["src"], tempo=v["tempo"]) * (0.8 if len(v["takes"]) > 1 else 1.0)
                j = int(round(tk["start"] * music.SR))
                if sig is None:
                    sig, i = one, j
                    continue
                lo = min(i, j)
                n = max(i + len(sig), j + len(one)) - lo
                both = np.zeros((n, 2))
                both[i - lo:i - lo + len(sig)] += sig
                both[j - lo:j - lo + len(one)] += one
                sig, i = both, lo
            if i < 0:
                sig, i = sig[-i:], 0
            m = min(len(sig), len(mix) - i)
            if m > 0:
                env = np.ones(m)
                f = min(m, int(0.12 * music.SR))
                env[:f] = np.linspace(0, 1, f)              # the duck slides in, not a jump
                mix[i:i + m] *= (1 - 0.45 * env)[:, None]     # the music steps back under the voice
                mix[i:i + m] += sig[:m] * 1.0
                voiced += 1
        music.write_wav(out_wav, mix / max(1.0, float(np.max(np.abs(mix)))) * 0.95)
        return voiced

    # -------- files
    def cue_sheet(self):
        p = self.plan
        rows = ["# Cue sheet: {}".format(self.ep.get("title", self.dir.name)), "",
                "{} BPM, key of {}, {} bars, {:.1f} s. The music alone is `media/audio/beat.m4a`: sing each line from "
                "its first beat (there's a dhol fill into every new part). One file per line in "
                "`media/audio/lines/<id>.wav`.".format(int(p.bpm), p.L.get("key", "D"), sum(s[1] for s in p.sections),
                                                       p.length), "",
                "| Line | Part | Who | Bars | Starts | Sing |", "|---|---|---|---|---|---|"]
        bar = 1
        for d in p.lines:
            rows.append("| {} | {} | {} | {}–{} | {:.2f} s | {} |".format(
                d["id"], d.get("part", ""), WHO_LABEL.get(d["who"], d["who"]).title(), bar,
                bar + int(d.get("bars", 1)) - 1, d["t0"], d["say"]))
            bar += int(d.get("bars", 1))
        rows += ["", "## The words", "", "| Gujarati | Say it | Means | Rhymes with |", "|---|---|---|---|"]
        for w in p.L["words"]:
            mates = [x["roman"] for x in p.L["words"] if x["rhyme"] == w["rhyme"] and x["id"] != w["id"]]
            rows.append("| {} | {} | {}{} | {} |".format(w["gu"], w["roman"], w["meaning"],
                                                          " ({})".format(w["en"]) if w.get("en") else "",
                                                          ", ".join(mates)))
        out = self.dir / "build" / "lyrics.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text("\n".join(rows) + "\n")
        return out

    def voice_sheet(self):
        """build/voice.md: every line to make on elevenlabs.io, in whose voice, the exact text to paste (tags
        included) and the file name to save it as; which lines are already there."""
        import taali_voice as tv
        _, _, cast = tv.load(self.dir)
        lines_dir = self.dir / "media" / "audio" / "lines"
        rows = ["# Voice sheet: {}".format(self.ep.get("title", self.dir.name)), "",
                "Make each line on elevenlabs.io → Text to Speech, model **{}**, and save the download in `{}` under "
                "the name given. Paste the text exactly, tags included. A *both* line is two takes, one in each voice. "
                "The build lines every take up on its beat itself: never trim, join or speed up a file.".format(
                    cast.get("model", "eleven_v3"), lines_dir.resolve().relative_to(ROOT) if lines_dir.resolve().is_relative_to(ROOT)
                    else lines_dir), "",
                "| Voice | voice_id | Speed | Stability |", "|---|---|---|---|"]
        for w in CHARS:
            c = cast.get(w) or {}
            rows.append("| {} ({}) | {} | {} | {} |".format(WHO_LABEL[w].title(), c.get("voice_name") or "not chosen yet",
                                                           c.get("voice_id") or "not chosen yet", c.get("speed", 1.0),
                                                           {0.0: "Creative", 0.5: "Natural", 1.0: "Robust"}.get(
                                                               float(c.get("stability", 0.5)), c.get("stability"))))
        rows += ["", "| Line | Voice | Paste this | Save as | There? |", "|---|---|---|---|---|"]
        for d in self.plan.lines:
            for w in tv.singers(d):
                text = tv.request_for(d, w, cast)[1]["text"]
                name = "{}.mp3".format(d["id"]) if d["who"] != "both" else "{}.{}.mp3".format(d["id"], w)
                have = any((lines_dir / "{}.{}".format(Path(name).stem, e)).exists() for e in ("mp3", "wav", "m4a")) \
                    or (d["who"] == "both" and (lines_dir / "{}.mp3".format(d["id"])).exists())
                rows.append("| {} | {} | `{}` | `{}` | {} |".format(d["id"], WHO_LABEL[w].title(), text, name,
                                                                    "yes" if have else "**to make**"))
        out = self.dir / "build" / "voice.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text("\n".join(rows) + "\n")
        return out

    def storyboard(self):
        p = self.plan
        picks = [d["t0"] + min(d["t1"] - d["t0"] - 0.1, p.beat * 2.2) for d in p.lines][::2][:12]
        thumbs = [self.frame(t).resize((270, 480), Image.LANCZOS) for t in picks]
        cols = 6
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (cols * 270, rows * 480), (0, 0, 0))
        for k, im in enumerate(thumbs):
            sheet.paste(im, ((k % cols) * 270, (k // cols) * 480))
        out = self.dir / "checks" / "storyboard.jpg"
        out.parent.mkdir(exist_ok=True)
        sheet.save(out, quality=86)
        return out


_spans = {}


def sound_span(path):
    """(first sound, last sound, length) of a voice take, in seconds: where it rises above about -32 dB."""
    key = str(path)
    if key not in _spans:
        x = np.abs(decode(path)).max(axis=1)
        n = len(x)
        hop = int(0.01 * music.SR)
        env = np.array([x[k:k + hop].max() for k in range(0, n, hop)]) if n else np.zeros(1)
        on = np.where(env > 0.025)[0]
        first = on[0] * 0.01 if len(on) else 0.0
        last = (on[-1] + 1) * 0.01 if len(on) else n / music.SR
        _spans[key] = (max(0.0, first - 0.02), last, n / music.SR)
    return _spans[key]


def probe(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                             capture_output=True, text=True, check=True).stdout
        return float(out.strip())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return 0.0


def decode(path, tempo=None):
    af = ["-af", "atempo={:.4f}".format(tempo)] if tempo and tempo > 1.001 else []
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path)] + af +
                         ["-f", "f32le", "-ac", "2", "-ar", str(music.SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype="<f4").reshape(-1, 2).astype(np.float64)


def _render_chunk(args):
    ep_dir, f0, f1, out = args
    reel = Reel(ep_dir)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "{}x{}".format(W, H),
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p",
           str(out)]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fi in range(f0, f1):
        pr.stdin.write(reel.frame(fi / FPS).tobytes())
    pr.stdin.close()
    pr.wait()
    return out


def build(ep_dir, workers=None):
    ep_dir = Path(ep_dir)
    reel = Reel(ep_dir)
    final = ep_dir / "media" / "final"
    final.mkdir(parents=True, exist_ok=True)
    out = final / "{}.mp4".format(ep_dir.resolve().name)
    n_frames = int(math.ceil((reel.plan.length + 1.2) * FPS))
    workers = workers or max(1, min(mp.cpu_count(), 8))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        wav = tmp / "mix.wav"
        voiced = reel.audio(wav)
        step = math.ceil(n_frames / workers)
        jobs = [(str(ep_dir), k, min(n_frames, k + step), tmp / "part{:02d}.mp4".format(j))
                for j, k in enumerate(range(0, n_frames, step))]
        with mp.Pool(len(jobs)) as pool:
            parts = pool.map(_render_chunk, jobs)
        lst = tmp / "parts.txt"
        lst.write_text("".join("file '{}'\n".format(p) for p in parts))
        silent = tmp / "silent.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
                        str(silent)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-shortest", "-movflags", "+faststart", str(out)],
                       check=True)
    reel.frame(reel.plan.bar * 1.2).save(final / "cover.jpg", quality=92)
    return out, voiced, reel


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("episode")
    ap.add_argument("--check", action="store_true", help="only check the lesson")
    ap.add_argument("--frame", type=float, action="append", help="render one frame at this second (repeatable)")
    ap.add_argument("--cover", action="store_true", help="only the cover, media/final/cover.jpg")
    ap.add_argument("--workers", type=int)
    a = ap.parse_args()
    ep_dir = Path(a.episode)
    ep, _ = load(ep_dir)
    problems = check(ep)
    for pr in problems:
        print("FAIL · " + pr)
    if a.check or problems:
        if not problems:
            plan = Plan(ep)
            Reel(ep_dir).cue_sheet()
            print("Voice sheet:", Reel(ep_dir).voice_sheet())
            print("OK · {} words in {} rhyme groups, {} lines, {:.1f} s at {} BPM".format(
                len(plan.words), len(plan.rhymes), len(plan.lines), plan.length, int(plan.bpm)))
        sys.exit(1 if problems else 0)
    reel = Reel(ep_dir)
    if a.frame:
        kf = ep_dir / "media" / "keyframes"
        kf.mkdir(parents=True, exist_ok=True)
        for t in a.frame:
            p = kf / "t{:06.2f}.png".format(t)
            reel.frame(t).save(p)
            print(p)
        return
    if a.cover:
        p = ep_dir / "media" / "final" / "cover.jpg"
        p.parent.mkdir(parents=True, exist_ok=True)
        reel.frame(reel.plan.bar * 1.2).save(p, quality=92)
        print(p)
        return
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is needed")
    print("Cue sheet:", reel.cue_sheet())
    print("Voice sheet:", reel.voice_sheet())
    out, voiced, reel = build(ep_dir, a.workers)
    print("Storyboard:", reel.storyboard())
    for d in reel.plan.lines:
        v = d.get("voice")
        if v and v["tempo"] > 1.25:
            print("RUSHED · {} was {:.2f}x too long for its {} bar(s) and was sped up to fit: make it again a little "
                  "faster (speed 1.2), or give the line another bar".format(d["id"], v["tempo"], d.get("bars", 1)))
    print("Done: {} ({:.1f} s, {} of {} lines voiced{})".format(
        out, reel.plan.length, voiced, len(reel.plan.lines),
        "" if voiced else "; music and sing-along captions only until the voice lines are in media/audio/lines/"))


if __name__ == "__main__":
    main()
