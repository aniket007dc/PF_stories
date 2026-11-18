"""Draw the PF Guru Ji logo as SVG files, with every letter turned into an outline so it looks
the same in any app, with or without the fonts installed.

    python3 tools/make_logo.py
    node tools/render_assets.js logo      # then the PNGs (needs Node, Playwright and Chromium)

Writes brand/assets/logo/:
    pfguruji-logo.svg              stacked: the form mark over GURU JI, for light backgrounds
    pfguruji-logo-on-dark.svg      the same for dark backgrounds
    pfguruji-logo-horizontal.svg   the mark beside GURU JI, for wide spaces
    pfguruji-mark.svg              the form mark alone (watermarks, small icons)
    pfguruji-avatar.svg            square, lemon, safe for a round crop (Instagram profile picture)

The mark is a claim form: an ink sheet with its corner folded down, PF on it, and a lemon tick.
GURU JI sits on a lemon highlighter swipe, like the end card of every reel. Colours come from
brand/brand.json. Needs fontTools (requirements-build.txt).
"""
import json
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "brand" / "brand.json").read_text(encoding="utf-8"))
C = BRAND["colors"]
OUT = ROOT / "brand" / "assets" / "logo"
SLUG = BRAND["instagram"].lstrip("@") or "logo"


def num(v):
    return ("%.2f" % v).rstrip("0").rstrip(".")


class Face:
    def __init__(self, file):
        self.font = TTFont(str(ROOT / "brand" / "fonts" / file))
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upem = self.font["head"].unitsPerEm

    def _glyph(self, ch):
        return self.glyphs[self.cmap[ord(ch)]]

    def width(self, text, size, tracking=0.0):
        """Advance width in px; tracking is in em, added between letters."""
        return sum(self._glyph(c).width for c in text) * size / self.upem + tracking * size * (len(text) - 1)

    def ink(self, text, size):
        """(left, top, right, bottom) of the letters' ink, from the pen position and the baseline (y down)."""
        glyf = self.font["glyf"]
        x, box = 0.0, None
        for c in text:
            g = glyf[self.cmap[ord(c)]]
            if g.numberOfContours:
                b = (x + g.xMin, -g.yMax, x + g.xMax, -g.yMin)
                box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
            x += self._glyph(c).width
        k = size / self.upem
        return tuple(v * k for v in box)

    def path(self, text, x, baseline, size, tracking=0.0):
        """SVG path data for the text, with its pen starting at x on the baseline."""
        k = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=num)
        for c in text:
            g = self._glyph(c)
            g.draw(TransformPen(pen, (k, 0, 0, -k, x, baseline)))
            x += g.width * k + tracking * size
        return pen.getCommands()


ANTON = Face("Anton-Regular.ttf")
SHEET = 1.3                         # the sheet's height, as a share of its width


# ------------------------------------------------------------------ parts

def mark(x, y, w, sheet, letters, fold, tick):
    """The claim form, w wide with its top-left corner at x, y. Returns (svg, height).

    The tick reaches a little past the sheet's right edge (by 0.07 w), below the letters."""
    h = w * SHEET
    f = w * 0.3                     # the folded corner
    r = w * 0.05                    # the other corners
    body = ("M{x0} {y1r2}V{y0r}Q{x0} {y0} {x0r} {y0}H{xf}L{x1} {yf}V{y1r}Q{x1} {y1} {x1r} {y1}H{x0r}Q{x0} {y1} {x0} {y1r2}Z"
            .format(x0=num(x), y0=num(y), x1=num(x + w), y1=num(y + h), y0r=num(y + r), x0r=num(x + r),
                    xf=num(x + w - f), yf=num(y + f), y1r=num(y + h - r), x1r=num(x + w - r), y1r2=num(y + h - r)))
    flap = "M{} {}V{}H{}Z".format(num(x + w - f), num(y), num(y + f), num(x + w))
    size = w * 0.74
    left, top, right, bottom = ANTON.ink("PF", size)
    px = x + w * 0.45 - (left + right) / 2
    base = y + f + w * 0.07 - top
    letters_path = ANTON.path("PF", px, base, size)
    sw = w * 0.1
    t0, t1, t2 = (x + w * 0.56, y + w * 1.14), (x + w * 0.68, y + w * 1.24), (x + w * 1.07, y + w * 0.93)
    tick_d = "M{} {}L{} {}L{} {}".format(*map(num, (*t0, *t1, *t2)))
    stroke = '<path d="{}" fill="none" stroke="{}" stroke-width="{}" stroke-linecap="round" stroke-linejoin="round"/>'
    svg = ('<path d="{}" fill="{}"/><path d="{}" fill="{}"/><path d="{}" fill="{}"/>'.format(
        body, sheet, flap, fold, letters_path, letters)
        + stroke.format(tick_d, sheet, num(sw * 2)) + stroke.format(tick_d, tick, num(sw)))
    return svg, h


def swipe_text(text, cx, baseline, size, ink, swipe, tracking=0.02):
    """Text centred on cx, with a lemon highlighter swipe across its lower half, as on the reels' end card.
    Returns (svg, (left, top, right, bottom))."""
    w = ANTON.width(text, size, tracking)
    left, top, right, bottom = ANTON.ink(text, size)
    x = cx - w / 2
    box = [x + left, baseline + top, x + w - (ANTON.width(text[-1], size) - right + left) * 0, baseline + bottom]
    parts = []
    if swipe:
        pad, k = size * 0.11, size / 236
        y0, y1 = baseline + top * 0.52, baseline + size * 0.05
        pts = [(x - pad, y0), (x + w + pad, y0 - 10 * k), (x + w + pad - 6 * k, y1), (x - pad - 6 * k, y1 + 8 * k)]
        parts.append('<path d="M{}Z" fill="{}"/>'.format("L".join("{} {}".format(num(a), num(b)) for a, b in pts), swipe))
        box = [min(box[0], x - pad - 6 * k), box[1], max(box[2], x + w + pad), max(box[3], y1 + 8 * k)]
    parts.append('<path d="{}" fill="{}"/>'.format(ANTON.path(text, x, baseline, size, tracking), ink))
    return "".join(parts), tuple(box)


def svg_file(w, h, body, title, bg=None):
    rect = '<rect width="{}" height="{}" fill="{}"/>'.format(num(w), num(h), bg) if bg else ""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            '<title>{t}</title>{r}{b}</svg>\n').format(w=num(w), h=num(h), t=title, r=rect, b=body)


# ------------------------------------------------------------------ the files

MARK_OVER = 0.07                    # how far the tick reaches past the sheet, as a share of its width


def stacked(dark=False):
    """The mark over GURU JI, centred together."""
    sheet = C["card"] if dark else C["ink"]
    letters = C["ink"] if dark else C["card"]
    words = C["lemon"] if dark else C["ink"]
    size, mw, pad = 250, 330, 40
    t, box = swipe_text("GURU JI", 0, 0, size, words, None if dark else C["lemon"])
    W = max(box[2] - box[0], mw * (1 + MARK_OVER)) + 2 * pad
    m, mh = mark(W / 2 - mw * (1 + MARK_OVER) / 2, pad, mw, sheet, letters, C["lemon"], C["lemon"])
    base = pad + mh + 46 - box[1]
    t, box = swipe_text("GURU JI", W / 2, base, size, words, None if dark else C["lemon"])
    return svg_file(W, box[3] + pad, m + t, BRAND["brand"])


def horizontal():
    """The mark beside GURU JI, the capitals centred on the sheet."""
    size, mw, pad = 300, 250, 40
    m, mh = mark(pad, pad, mw, C["ink"], C["card"], C["lemon"], C["lemon"])
    _, rel = swipe_text("GURU JI", 0, 0, size, C["ink"], C["lemon"])
    cx = pad + mw * (1 + MARK_OVER) + 44 - rel[0]
    base = pad + mh / 2 - rel[1] / 2
    t, box = swipe_text("GURU JI", cx, base, size, C["ink"], C["lemon"])
    return svg_file(box[2] + pad, max(pad + mh, box[3]) + pad, m + t, BRAND["brand"])


def mark_only():
    mw, pad = 400, 30
    m, mh = mark(pad, pad, mw, C["ink"], C["card"], C["lemon"], C["lemon"])
    return svg_file(mw * (1 + MARK_OVER) + 2 * pad, mh + 2 * pad, m, BRAND["brand"])


def avatar():
    """Square and lemon; everything inside a circle of 0.78 of the side, so a round crop keeps it."""
    S, mw, size, gap = 1080, 380, 176, 40
    mh = mw * SHEET
    _, top, _, bottom = ANTON.ink("GURU JI", size)
    total = mh + gap + (bottom - top)
    y0 = S / 2 - total / 2
    m, _ = mark(S / 2 - mw * (1 + MARK_OVER) / 2, y0, mw, C["ink"], C["lemon"], C["card"], C["card"])
    t, _ = swipe_text("GURU JI", S / 2, y0 + mh + gap - top, size, C["ink"], None)
    return svg_file(S, S, m + t, BRAND["brand"], bg=C["lemon"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "logo": stacked(),
        "logo-on-dark": stacked(dark=True),
        "logo-horizontal": horizontal(),
        "mark": mark_only(),
        "avatar": avatar(),
    }
    for name, svg in files.items():
        p = OUT / "{}-{}.svg".format(SLUG, name)
        p.write_text(svg, encoding="utf-8")
        print("wrote", p.relative_to(ROOT) if p.is_relative_to(ROOT) else p)


if __name__ == "__main__":
    main()
