"""Paper cut-outs for PF Stories: people and things cut from coloured paper, drawn from shapes.

Nothing here is drawn by AI, so a character looks the same in every shot of every reel, and nothing carries words
of its own: a sign or a speech bubble gets its words from the shot's card text (tools/build_reel.py draws them).

    person(look, pose, mood, ...)   one frame of a jointed paper puppet (the cast is in brand/brand.json → cast)
    prop(kind, variant)             a thing: factory, office, bank, home, phone, document, coins, calendar, ...
    finish(img, paper, seed)        the cut-out look: paper fibres on the colours and the white edge scissors leave

Every piece is drawn over a darker copy of itself, a little down and to the right: the edge of a piece of card
lying on the one below. tools/build_reel.py places the cut-outs, moves them in stop motion (12 poses a second,
each a little off) and gives them their shadow on the page. Colours come from brand/brand.json → colors.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
_BRAND = json.loads((ROOT / "brand" / "brand.json").read_text(encoding="utf-8"))
SS = 2                                  # drawn at twice the size, then scaled down: smooth paper edges
CUT_WHITE = (250, 248, 243)
EDGE = 7.0                              # the white margin around a cut-out
PAD = int(EDGE + 4)                     # what finish() adds on every side


def _hex(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


COLORS = {k: _hex(v) for k, v in _BRAND["colors"].items()}
COLORS.setdefault("skin", _hex("#C98E62"))
COLORS.setdefault("skin_dark", _hex("#9E6A45"))
CAST = _BRAND.get("cast", {})


def col(name):
    """A brand colour by name (lemon, stamp_red, ink, card, pencil, skin …) or a #hex."""
    if isinstance(name, (tuple, list)):
        return tuple(name)
    if str(name).startswith("#"):
        return _hex(name)
    return COLORS[name]


def shade(c, k=0.72):
    return tuple(int(v * k) for v in c)


def light(c, k=0.35):
    return tuple(int(v + (255 - v) * k) for v in c)


# ---------------------------------------------------------------- geometry

def _dir(deg):
    """A unit vector at deg degrees from straight down, positive toward the right."""
    a = math.radians(deg)
    return math.sin(a), math.cos(a)


def _rot(pts, deg, pivot):
    if not deg:
        return list(pts)
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    px, py = pivot
    return [(px + (x - px) * c - (y - py) * s, py + (x - px) * s + (y - py) * c) for x, y in pts]


def _ell(cx, cy, rx, ry, n=44, a0=0.0, a1=360.0):
    return [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
            for a in np.linspace(a0, a1, n, endpoint=(a1 - a0) < 360)]


class Pen:
    """Draws on a supersampled canvas in 1x pixels. Every filled shape goes over a darker copy of itself, set a
    little down and right, so overlapping pieces read as layers of card."""

    def __init__(self, w, h, ox=0, oy=0, edge=(1.7, 2.5)):
        self.w, self.h, self.ox, self.oy, self.edge = w, h, ox, oy, edge
        self.img = Image.new("RGBA", (int(w * SS), int(h * SS)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pts, dx=0.0, dy=0.0):
        return [((x + self.ox + dx) * SS, (y + self.oy + dy) * SS) for x, y in pts]

    def poly(self, pts, fill, edge=True):
        fill = col(fill)
        if edge:
            self.d.polygon(self._p(pts, *self.edge), fill=shade(fill) + (255,))
        self.d.polygon(self._p(pts), fill=fill + (255,))

    def ellipse(self, cx, cy, rx, ry, fill, edge=True):
        self.poly(_ell(cx, cy, rx, ry), fill, edge)

    def rect(self, x0, y0, x1, y1, fill, edge=True, r=0.0):
        if r:
            pts = []
            for cx, cy, a0 in ((x1 - r, y0 + r, 270), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
                pts += _ell(cx, cy, r, r, 8, a0, a0 + 90)
            self.poly(pts, fill, edge)
        else:
            self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, edge)

    def capsule(self, p0, p1, width, fill, edge=True):
        """A limb: a bar with round ends."""
        (x0, y0), (x1, y1) = p0, p1
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        r = width / 2
        pts = _ell(x1, y1, r, r, 14, ang - 90, ang + 90) + _ell(x0, y0, r, r, 14, ang + 90, ang + 270)
        self.poly(pts, fill, edge)

    def line(self, pts, width, fill):
        fill = col(fill) + (255,)
        p = self._p(pts)
        self.d.line(p, fill=fill, width=max(1, int(width * SS)), joint="curve")
        r = width * SS / 2
        for x, y in (p[0], p[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=fill)

    def done(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


# ---------------------------------------------------------------- people

# A puppet faces right (the builder mirrors it to face left). Sizes in pixels at scale 1, from the ground up: a big
# head and short legs, like a paper doll.
HIP_Y, SHOULDER_Y, NECK_Y, HEAD_Y = -258, -436, -458, -538
HIP_X, SHOULDER_X = 29, 64
THIGH, SHIN, UPPER_ARM, FOREARM = 122, 112, 100, 92
HEAD_RX, HEAD_RY = 70, 78
CANVAS_W, CANVAS_H, GROUND_X, GROUND_Y = 780, 860, 390, 800

# Each pose places the far arm and the near arm (the one on the side the puppet faces): ("angle", outward angle of
# the upper arm from hanging down, elbow bend toward the chest), or ("hand", where) with where one of the HANDS
# targets below, the elbow found by itself.
POSES = {
    "stand": {"arms": (("angle", 9, 8), ("angle", 9, 8))},
    "wave": {"arms": (("angle", 9, 8), ("hand", "wave"))},
    "point": {"arms": (("angle", 9, 8), ("hand", "point"))},
    "think": {"arms": (("angle", 12, 14), ("hand", "chin"))},
    "phone": {"arms": (("angle", 12, 14), ("hand", "ear"))},
    "hips": {"arms": (("hand", "hip"), ("hand", "hip"))},
    "cheer": {"arms": (("hand", "up"), ("hand", "up"))},
    "shrug": {"arms": (("hand", "shrug"), ("hand", "shrug"))},
    "hold": {"arms": (("hand", "chest"), ("hand", "chest"))},
    "sad": {"arms": (("angle", 4, 2), ("angle", 4, 2)), "slump": True},
    "walk": {"arms": (("angle", 9, 12), ("angle", 9, 12))},
}
MOODS = ("neutral", "smile", "happy", "worried", "surprised", "sad", "angry", "thinking")


def _hands(where, side, L):
    """Where a hand goes, for the arm on side -1 (far) or 1 (near), from the body's landmarks L."""
    hx, hy, sh_y, hip_y = L["hx"], L["hy"], L["sh_y"], L["hip_y"]
    return {"chin": (hx + 18, hy + 70), "ear": (hx + HEAD_RX + 2, hy + 4),
            "hip": (side * 62, hip_y - 6), "up": (side * 92, sh_y - 196), "shrug": (side * 168, sh_y - 6),
            "chest": (side * 26, sh_y + 92), "point": (side * 250, sh_y + 4),
            "wave": (side * 118 + L["wave"] * 26, sh_y - 150)}[where]


def _ik(sho, target, a, b, side):
    """The elbow for a hand at target: of the two ways the arm can bend, the one with the elbow out and down."""
    dx, dy = target[0] - sho[0], target[1] - sho[1]
    d = max(abs(a - b) + 1, min(a + b - 1, math.hypot(dx, dy)))
    base = math.atan2(dy, dx)
    alpha = math.acos(max(-1.0, min(1.0, (a * a + d * d - b * b) / (2 * a * d))))
    best = None
    for ang in (base + alpha, base - alpha):
        el = (sho[0] + a * math.cos(ang), sho[1] + a * math.sin(ang))
        score = side * el[0] + 0.5 * el[1]
        if best is None or score > best[0]:
            best = (score, el)
    el = best[1]
    ex, ey = target[0] - el[0], target[1] - el[1]
    n = math.hypot(ex, ey) or 1
    return el, (el[0] + ex / n * b, el[1] + ey / n * b)


def look_of(who):
    """The look of a cast member (brand.json → cast), or of a look given in full."""
    if isinstance(who, dict):
        return who
    if who not in CAST:
        raise KeyError("'{}' isn't in brand.json → cast ({})".format(who, ", ".join(CAST) or "empty"))
    return CAST[who]


def person(who, pose="stand", mood="neutral", phase=None, blink=False, wave=0.0, tilt=0.0, slump=None):
    """One frame of a paper puppet, facing right: (RGBA image, (x, y) of the point between its feet on the ground).

    phase: the walk cycle in radians (None when standing); wave: -1…1, the waving hand's swing; tilt: the head's
    tilt in degrees."""
    lk = look_of(who)
    p = POSES.get(pose, POSES["stand"])
    shirt, pants = col(lk.get("shirt", "lemon")), col(lk.get("pants", "ink"))
    skin = col(lk.get("skin", "skin"))
    pen = Pen(CANVAS_W, CANVAS_H, GROUND_X, GROUND_Y)
    slump = p.get("slump", False) if slump is None else slump
    walking = phase is not None
    s = math.sin(phase) if walking else 0.0
    dy = (6 * abs(s) if walking else 0.0) + (8 if slump else 0)
    kurta = lk.get("top") == "kurta"

    # legs: they scissor when walking, and the back one bends at the knee; the lower foot stays on the ground
    legs = []
    for side in (-1, 1):
        swing = 21 * s * side
        thigh_a = side * 3 + swing
        knee = -1.2 * swing if (walking and swing < 0) else 0.0
        hip = (side * HIP_X, HIP_Y + dy)
        k = (hip[0] + _dir(thigh_a)[0] * THIGH, hip[1] + _dir(thigh_a)[1] * THIGH)
        ank = (k[0] + _dir(thigh_a - knee)[0] * SHIN, k[1] + _dir(thigh_a - knee)[1] * SHIN)
        legs.append([hip, k, ank])
    lift = max(l[2][1] for l in legs) + 22
    legs = [[(x, y - lift) for x, y in l] for l in legs]
    hip_y, sh_y, nk_y = HIP_Y + dy - lift, SHOULDER_Y + dy - lift, NECK_Y + dy - lift
    for hip, k, ank in legs:
        pen.capsule(hip, k, 54, pants)
        pen.capsule(k, ank, 48, pants)
        pen.ellipse(ank[0] + 14, ank[1] + 9, 34, 16, lk.get("shoes", "ink"))

    # torso: a shirt, or a kurta that reaches the knees, over the top of the trousers
    hem = hip_y + (96 if kurta else 20)
    pen.rect(-54, hip_y - 26, 54, hip_y + 34, pants, r=18)
    wide = 64 if kurta else 58
    pen.poly([(-SHOULDER_X - 10, sh_y - 2), (-24, sh_y - 18), (24, sh_y - 18), (SHOULDER_X + 10, sh_y - 2),
              (58, hip_y - 40), (wide, hem), (-wide, hem), (-58, hip_y - 40)], shirt)
    pen.poly([(-18, sh_y - 17), (0, sh_y + 28), (18, sh_y - 17)], shade(shirt, 0.84), edge=False)
    if lk.get("tie"):
        pen.poly([(-9, sh_y - 8), (9, sh_y - 8), (13, sh_y + 92), (0, sh_y + 110), (-13, sh_y + 92)], lk["tie"])
    elif not kurta:
        for i in range(3):
            pen.ellipse(0, sh_y + 46 + i * 40, 4.5, 4.5, shade(shirt, 0.55), edge=False)
    if lk.get("dupatta"):
        pen.poly([(-SHOULDER_X - 8, sh_y + 2), (-SHOULDER_X + 22, sh_y - 12), (54, hip_y - 16), (30, hip_y + 12)],
                 lk["dupatta"])

    # head and neck, tilted about the neck
    neck = (0, nk_y)
    hx, hy = 0.0, HEAD_Y + dy - lift + (6 if slump else 0)
    tilt = tilt + (10 if slump else 0)

    def H(pts):
        return _rot(pts, tilt, neck)

    pen.capsule((0, nk_y + 16), (0, nk_y - 26), 38, shade(skin, 0.9))
    hair = lk.get("hair", "short")
    hair_col = col("pencil") if hair == "grey" else col(lk.get("hair_color", "ink"))
    if hair == "long":
        pen.poly(H(_ell(hx - 2, hy + 40, HEAD_RX + 14, HEAD_RY + 50, 40, 180, 360) + [(hx + 82, hy + 132), (hx - 86, hy + 132)]),
                 hair_col)
    elif hair == "bun":
        pen.poly(H(_ell(hx - 34, hy - 70, 34, 30)), hair_col)
    for ex in (-HEAD_RX + 3, HEAD_RX - 3):
        pen.poly(H(_ell(hx + ex, hy + 8, 14, 18)), skin)
    pen.poly(H(_ell(hx, hy, HEAD_RX, HEAD_RY)), skin)
    top = _ell(hx, hy - 2, HEAD_RX + 6, HEAD_RY + 6, 30, 190, 350)
    if hair == "grey":
        line = [(hx + 62, hy - 30), (hx + 34, hy - 52), (hx, hy - 58), (hx - 34, hy - 52), (hx - 64, hy - 28)]
    elif hair in ("long", "bun"):
        line = [(hx + 70, hy - 10), (hx + 40, hy - 46), (hx + 8, hy - 58), (hx - 4, hy - 40), (hx - 36, hy - 50), (hx - 72, hy - 6)]
    else:
        line = [(hx + 70, hy - 16), (hx + 46, hy - 36), (hx + 14, hy - 46), (hx - 20, hy - 34), (hx - 52, hy - 42), (hx - 72, hy - 4)]
    pen.poly(H(top + line), hair_col)

    # the face, turned a little toward where the puppet faces
    fx, eye_y = hx + 10, hy - 2
    if blink:
        for ex in (-25, 25):
            pen.line(H([(fx + ex - 8, eye_y + 2), (fx + ex + 8, eye_y + 2)]), 4.5, "ink")
    elif mood == "surprised":
        for ex in (-25, 25):
            pen.poly(H(_ell(fx + ex, eye_y, 12, 13)), CUT_WHITE, edge=False)
            pen.poly(H(_ell(fx + ex + 2, eye_y + 1, 6, 6.5)), "ink", edge=False)
    else:
        up = -3 if mood == "thinking" else 0
        for ex in (-25, 25):
            pen.poly(H(_ell(fx + ex + 2, eye_y + up, 6.2, 8.2)), "ink", edge=False)
            pen.poly(H(_ell(fx + ex + 4, eye_y + up - 3, 1.8, 1.8)), CUT_WHITE, edge=False)
    lift_b, slant = {"happy": (-3, 0), "worried": (-2, 8), "surprised": (-9, 0), "sad": (0, 7), "angry": (2, -8),
                     "thinking": (-4, 3)}.get(mood, (0, 0))
    for side in (-1, 1):
        x_in, x_out = fx + side * 14, fx + side * 36
        y_in = eye_y - 23 + lift_b - slant * 0.5
        y_out = eye_y - 23 + lift_b + slant * 0.5
        if mood == "thinking" and side == 1:
            y_in, y_out = y_in - 6, y_out - 7
        pen.line(H([(x_in, y_in), (x_out, y_out)]), 5.2, hair_col)
    pen.poly(H([(fx + 3, hy + 8), (fx + 12, hy + 24), (fx + 1, hy + 26)]), shade(skin, 0.8), edge=False)
    if mood in ("happy", "smile"):
        for ex in (-40, 46):
            pen.poly(H(_ell(fx + ex, hy + 30, 11, 7)), light(col("stamp_red"), 0.45), edge=False)
    if lk.get("moustache"):
        pen.poly(H(_ell(fx, hy + 34, 23, 7, 20, 180, 360) + [(fx + 23, hy + 38), (fx - 23, hy + 38)]), hair_col, edge=False)
    my = hy + 44
    if mood == "happy":
        pen.poly(H(_ell(fx, my - 5, 23, 17, 22, 0, 180)), "ink", edge=False)
        pen.poly(H(_ell(fx, my - 4, 17, 6, 16, 0, 180)), CUT_WHITE, edge=False)
    elif mood == "smile":
        pen.line(H([(fx + 18 * math.cos(math.radians(a)), my - 7 + 10 * math.sin(math.radians(a)))
                    for a in range(20, 161, 20)]), 4.5, "ink")
    elif mood == "sad":
        pen.line(H([(fx + 16 * math.cos(math.radians(a)), my + 6 - 9 * math.sin(math.radians(a)))
                    for a in range(20, 161, 20)]), 4.5, "ink")
    elif mood == "worried":
        pen.line(H([(fx - 17 + i * 5.7, my + 2 + (2.6 if i % 2 else -2.6)) for i in range(7)]), 4.2, "ink")
    elif mood == "surprised":
        pen.poly(H(_ell(fx, my, 9, 12)), "ink", edge=False)
    elif mood == "angry":
        pen.line(H([(fx - 15, my), (fx + 15, my - 3)]), 5, "ink")
    elif mood == "thinking":
        pen.line(H([(fx - 4, my), (fx + 16, my - 5)]), 4.5, "ink")
    else:
        pen.line(H([(fx - 12, my), (fx + 12, my)]), 4.5, "ink")
    if lk.get("glasses"):
        for ex in (-25, 25):
            pts = _ell(fx + ex, eye_y, 17, 15, 24)
            pen.line(H(pts + [pts[0]]), 3.4, "ink")
        pen.line(H([(fx - 8, eye_y - 2), (fx + 8, eye_y - 2)]), 3.2, "ink")

    # arms last: a hand can come up to the face
    L = {"hx": hx, "hy": hy, "sh_y": sh_y, "hip_y": hip_y, "wave": wave}
    arms = p["arms"]
    if walking:
        arms = (("angle", 9 - 16 * s, 14), ("angle", 9 + 16 * s, 14))
    sleeve = shirt if lk.get("sleeves", "short") == "long" else None
    near_hand = None
    for spec, side in ((arms[0], -1), (arms[1], 1)):
        sho = (side * SHOULDER_X, sh_y + 8)
        if spec[0] == "hand":
            tx, ty = _hands(spec[1], side, L)
            if spec[1] in ("chin", "ear", "wave", "point") and side == -1:
                tx = -tx
            el, wr = _ik(sho, (tx, ty), UPPER_ARM, FOREARM, side)
        else:
            ua = side * spec[1]
            el = (sho[0] + _dir(ua)[0] * UPPER_ARM, sho[1] + _dir(ua)[1] * UPPER_ARM)
            fa = ua - side * spec[2]
            wr = (el[0] + _dir(fa)[0] * FOREARM, el[1] + _dir(fa)[1] * FOREARM)
        pen.capsule(sho, el, 46, shirt)
        pen.capsule(el, wr, 38, sleeve or skin)
        ux, uy = wr[0] - el[0], wr[1] - el[1]
        n = math.hypot(ux, uy) or 1
        pen.ellipse(wr[0] + ux / n * 10, wr[1] + uy / n * 10, 21, 21, skin)
        if sleeve is None:
            mx, my_ = sho[0] + (el[0] - sho[0]) * 0.62, sho[1] + (el[1] - sho[1]) * 0.62
            pen.capsule(sho, (mx, my_), 50, shirt)
        if side == 1:
            near_hand = (wr[0] + ux / n * 10, wr[1] + uy / n * 10)
    if pose == "phone" and near_hand:
        x, y = near_hand
        pen.rect(x - 4, y - 66, x + 28, y + 4, "ink", r=7)
    return pen.done(), (GROUND_X, GROUND_Y)


# ---------------------------------------------------------------- things

def _factory(v):
    pen = Pen(620, 450)
    pen.rect(446, 30, 486, 210, "ink")
    for y in (64, 120):
        pen.rect(446, y, 486, y + 16, "stamp_red", edge=False)
    pen.rect(40, 190, 580, 440, "pencil")
    for i in range(3):
        x = 40 + i * 180
        pen.poly([(x, 192), (x, 112), (x + 180, 192)], "ink")
        pen.poly([(x + 8, 184), (x + 8, 128), (x + 52, 152), (x + 52, 184)], "lemon", edge=False)
    for i in range(5):
        pen.rect(70 + i * 100, 236, 120 + i * 100, 286, "lemon")
    pen.rect(270, 340, 350, 440, "stamp_red")
    pen.ellipse(336, 392, 5, 5, "ink", edge=False)
    return pen.done(), {"smoke": (466, 22), "sign": (60, 300, 260, 334), "sign_fg": "ink"}


def _office(v):
    """A public office with columns and an empty sign board for its name; no emblem, no logo."""
    roof = {"bank": "lemon"}.get(v, "card")
    pen = Pen(580, 480)
    for i, (x0, x1) in enumerate(((40, 540), (60, 520), (80, 500))):
        pen.rect(x0, 452 - i * 20, x1, 472 - i * 20, "pencil")
    pen.rect(70, 200, 510, 414, "card")
    for i in range(5):
        x = 92 + i * 90
        pen.rect(x, 232, x + 38, 414, "card")
    pen.rect(250, 300, 330, 414, "ink")
    pen.rect(50, 190, 530, 232, "ink")
    pen.poly([(40, 192), (290, 70), (540, 192)], roof)
    pen.ellipse(290, 148, 24, 24, "pencil")
    pen.ellipse(290, 148, 15, 15, "ink", edge=False)
    return pen.done(), {"sign": (110, 194, 470, 230), "sign_fg": "lemon" if v != "bank" else "card"}


def _home(v):
    pen = Pen(440, 420)
    pen.rect(290, 60, 330, 160, "ink")
    pen.rect(70, 170, 370, 410, "card")
    pen.poly([(36, 186), (220, 40), (404, 186)], "stamp_red")
    pen.rect(190, 286, 250, 410, "ink")
    for x in (96, 280):
        pen.rect(x, 220, x + 64, 276, "lemon")
        pen.line([(x + 32, 220), (x + 32, 276)], 4, "ink")
        pen.line([(x, 248), (x + 64, 248)], 4, "ink")
    return pen.done(), {}


def _phone(v):
    pen = Pen(220, 400)
    pen.rect(20, 10, 200, 390, "ink", r=26)
    pen.rect(34, 50, 186, 340, "card", edge=False)
    pen.rect(90, 24, 130, 32, "pencil", edge=False, r=4)
    pen.ellipse(110, 364, 13, 13, "pencil", edge=False)
    cx, cy = 110, 195
    if v == "tick":
        pen.ellipse(cx, cy, 52, 52, "lemon")
        pen.line([(cx - 24, cy + 2), (cx - 6, cy + 22), (cx + 26, cy - 20)], 10, "ink")
    elif v == "alert":
        pen.ellipse(cx, cy, 52, 52, "stamp_red")
        pen.line([(cx, cy - 26), (cx, cy + 8)], 11, "card")
        pen.ellipse(cx, cy + 26, 6.5, 6.5, "card", edge=False)
    elif v == "otp":
        for i in range(4):
            pen.rect(46 + i * 34, cy - 18, 72 + i * 34, cy + 18, "pencil", r=5)
            pen.ellipse(59 + i * 34, cy, 6, 6, "ink", edge=False)
    elif v == "chat":
        pen.rect(46, 92, 150, 140, "pencil", r=14)
        pen.rect(70, 160, 174, 208, "lemon", r=14)
        pen.rect(46, 228, 128, 270, "pencil", r=14)
    else:            # the member portal, as bars
        pen.rect(34, 50, 186, 90, "ink", edge=False)
        for i, w in enumerate((120, 96, 132, 80)):
            pen.rect(48, 112 + i * 52, 48 + w, 136 + i * 52, "pencil" if i != 2 else "lemon", r=6)
    return pen.done(), {"screen": (34, 50, 186, 340)}


def _document(v):
    pen = Pen(320, 400)
    sheet = [(30, 20), (230, 20), (290, 80), (290, 380), (30, 380)]
    pen.poly(sheet, "card")
    pen.poly([(230, 20), (230, 80), (290, 80)], "pencil")
    widths = (170, 210, 150, 220, 190, 120)
    for i, w in enumerate(widths):
        y = 110 + i * 40
        pen.rect(60, y, 60 + w, y + 12, "pencil" if i != 3 else "lemon", edge=False, r=5)
    pen.line([(70, 352), (96, 336), (112, 356), (138, 338), (160, 352)], 4, "ink")
    if v == "rejected":
        pen.line([(50, 60), (270, 360)], 14, "stamp_red")
        pen.line([(270, 60), (50, 360)], 14, "stamp_red")
    return pen.done(), {"stamp": (160, 230)}


def _coins(v):
    pen = Pen(260, 230)
    for i in range(5):
        pen.ellipse(100, 190 - i * 24, 66, 22, "lemon")
    for x, y in ((200, 196), (214, 160)):
        pen.ellipse(x, y, 34, 20, "lemon")
    return pen.done(), {}


def _calendar(v):
    pen = Pen(320, 340)
    pen.rect(20, 40, 300, 320, "card", r=10)
    pen.rect(20, 40, 300, 100, "stamp_red", r=10)
    for x in (90, 230):
        pen.rect(x - 7, 18, x + 7, 62, "ink", r=6)
    for r in range(4):
        for c in range(5):
            x, y = 40 + c * 52, 118 + r * 48
            pen.rect(x, y, x + 40, y + 34, "pencil" if (r, c) != (2, 3) else "lemon", edge=False, r=4)
    pts = _ell(40 + 3 * 52 + 20, 118 + 2 * 48 + 17, 32, 26, 30)
    pen.line(pts + pts[:2], 5, "stamp_red")
    return pen.done(), {}


def _laptop(v):
    pen = Pen(380, 270)
    pen.rect(50, 10, 330, 200, "ink", r=12)
    pen.rect(64, 24, 316, 186, "card", edge=False)
    for i, w in enumerate((180, 140, 200)):
        pen.rect(84, 50 + i * 40, 84 + w, 70 + i * 40, "pencil" if i != 1 else "lemon", edge=False, r=5)
    pen.poly([(30, 210), (350, 210), (370, 250), (10, 250)], "pencil")
    return pen.done(), {"screen": (64, 24, 316, 186)}


def _tick(v):
    pen = Pen(220, 220)
    pen.ellipse(110, 110, 92, 92, "lemon")
    pen.line([(66, 112), (98, 146), (156, 74)], 20, "ink")
    return pen.done(), {}


def _cross(v):
    pen = Pen(220, 220)
    pen.ellipse(110, 110, 92, 92, "stamp_red")
    pen.line([(76, 76), (144, 144)], 20, "card")
    pen.line([(144, 76), (76, 144)], 20, "card")
    return pen.done(), {}


def _clock(v):
    pen = Pen(240, 240)
    pen.ellipse(120, 120, 104, 104, "ink")
    pen.ellipse(120, 120, 90, 90, "card", edge=False)
    for i in range(12):
        a = math.radians(i * 30)
        pen.line([(120 + 74 * math.sin(a), 120 - 74 * math.cos(a)), (120 + 82 * math.sin(a), 120 - 82 * math.cos(a))], 5, "ink")
    return pen.done(), {"hands": (120, 120)}


def _suitcase(v):
    pen = Pen(260, 230)
    pen.rect(96, 20, 164, 60, "ink", r=12)
    pen.rect(108, 32, 152, 60, "paper", edge=False)
    pen.rect(30, 56, 230, 214, "stamp_red", r=16)
    for x in (80, 180):
        pen.rect(x - 7, 56, x + 7, 214, shade(col("stamp_red"), 0.75), edge=False)
    return pen.done(), {}


def _cloud(v):
    pen = Pen(300, 150)
    for cx, cy, r in ((80, 92, 44), (140, 66, 56), (206, 88, 46), (150, 104, 44)):
        pen.ellipse(cx, cy, r * 1.15, r, "card")
    return pen.done(), {}


def _sun(v):
    pen = Pen(240, 240)
    for i in range(10):
        a = math.radians(i * 36)
        pen.poly([(120 + 104 * math.sin(a), 120 - 104 * math.cos(a)),
                  (120 + 70 * math.sin(a + 0.22), 120 - 70 * math.cos(a + 0.22)),
                  (120 + 70 * math.sin(a - 0.22), 120 - 70 * math.cos(a - 0.22))], "lemon")
    pen.ellipse(120, 120, 64, 64, "lemon")
    return pen.done(), {}


def _desk(v):
    pen = Pen(460, 240)
    for x in (60, 380):
        pen.rect(x, 50, x + 22, 236, "ink")
    pen.rect(20, 30, 440, 64, "pencil")
    pen.rect(300, 64, 420, 170, "pencil")
    for y in (96, 136):
        pen.rect(340, y, 380, y + 8, "ink", edge=False, r=3)
    return pen.done(), {}


def _skyline(v):
    pen = Pen(1180, 320)
    x = 0
    rng = np.random.default_rng(7)
    while x < 1180:
        w = int(rng.integers(90, 170))
        h = int(rng.integers(120, 290))
        tone = "card" if rng.random() < 0.6 else "pencil"
        pen.rect(x, 320 - h, x + w - 8, 330, tone)
        for wy in range(320 - h + 24, 300, 46):
            for wx in range(x + 18, x + w - 30, 34):
                if rng.random() < 0.55:
                    pen.rect(wx, wy, wx + 16, wy + 22, "lemon" if rng.random() < 0.35 else shade(col(tone), 0.86), edge=False)
        x += w
    return pen.done(), {}


PROPS = {"factory": _factory, "office": _office, "bank": lambda v: _office("bank"), "home": _home, "phone": _phone,
         "document": _document, "coins": _coins, "calendar": _calendar, "laptop": _laptop, "tick": _tick,
         "cross": _cross, "clock": _clock, "suitcase": _suitcase, "cloud": _cloud, "sun": _sun, "desk": _desk,
         "skyline": _skyline}


def prop(kind, variant=None):
    """A thing as a paper cut-out: (RGBA image, anchors). anchors name points or boxes in the image: "sign" (where a
    name goes), "screen", "smoke", "stamp", "hands"."""
    if kind not in PROPS:
        raise KeyError("no prop '{}' (props: {})".format(kind, ", ".join(sorted(PROPS))))
    return PROPS[kind](variant)


def clock_hands(img, centre, hour, minute):
    pen = Pen(img.width, img.height)
    cx, cy = centre
    for frac, length, width in ((hour / 12.0, 50, 9), (minute / 60.0, 72, 6)):
        a = math.radians(frac * 360)
        pen.line([(cx, cy), (cx + length * math.sin(a), cy - length * math.cos(a))], width, "stamp_red" if width == 6 else "ink")
    out = img.copy()
    out.alpha_composite(pen.done())
    return out


# ---------------------------------------------------------------- the cut-out finish

def finish(img, paper, seed, edge=EDGE, fibres=0.5):
    """The cut-out look: the paper's fibres and light on the colours, and the white margin scissors leave around the
    shape. Returns a larger RGBA image (PAD more on every side)."""
    pad = int(edge + 4)
    out = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    out.paste(img, (pad, pad))
    a = out.getchannel("A")
    det, lit = paper.texture(out.width, out.height, seed, fibres, 0.25)
    rgb = np.asarray(out.convert("RGB")).astype(np.float32) * lit[..., None] + det[..., None]
    body = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).convert("RGBA")
    body.putalpha(a)
    grown = a.filter(ImageFilter.GaussianBlur(edge * 0.6)).point(lambda v: 255 if v > 22 else v * 11)
    white = Image.new("RGBA", out.size, CUT_WHITE + (255,))
    white.putalpha(grown.filter(ImageFilter.GaussianBlur(0.7)))
    white.alpha_composite(body)
    return white
