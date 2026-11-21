"""The Taali style's cast and props, drawn in code (styles/taali/STYLE.md → The cast).

- Sawaj (સાવજ, the Kathiyawadi word for lion): a Gir lion cub, Gujarat's pride, in a red bandhani pagdi, with a dhol.
  He sings the Gujarati word.
- Lali (લાલી): a flamingo, Gujarat's state bird, from the Rann of Kutch, in a mirror-work chaniya, with dandiya sticks.
  She sings back what it means.
- The garbo (the clay pot with a lamp inside that garba is named after), diyas, bulbs, marigolds, mirror-work.

Every drawing takes a pose (a dict of numbers the build moves on the beat), and is drawn at twice the size and scaled
down, so the outlines stay smooth.

    python3 tools/taali_cast.py sheet.png     # a sheet of both characters in several poses
"""
import math
import sys

from PIL import Image, ImageDraw, ImageFilter

SS = 2                                   # draw at 2x, scale down

OUT = (46, 16, 30, 255)                  # the outline every shape has: a deep maroon-brown
WHITE = (255, 255, 255, 255)
CREAM = (255, 244, 220, 255)
RED = (200, 16, 46, 255)                 # bandhani red
DEEP_RED = (150, 10, 36, 255)
MARIGOLD = (255, 176, 0, 255)
YELLOW = (255, 214, 64, 255)
GREEN = (24, 150, 88, 255)
TEAL = (0, 150, 160, 255)
PINK = (244, 132, 172, 255)
DEEP_PINK = (222, 78, 130, 255)
SILVER = (226, 232, 240, 255)

LION = (226, 160, 62, 255)
LION_LIGHT = (250, 216, 160, 255)
MANE = (160, 74, 26, 255)
MANE_2 = (196, 102, 38, 255)
NOSE = (74, 32, 24, 255)


def rot(px, py, cx, cy, deg):
    a = math.radians(deg)
    dx, dy = px - cx, py - cy
    return cx + dx * math.cos(a) - dy * math.sin(a), cy + dx * math.sin(a) + dy * math.cos(a)


class Pen:
    """A drawing surface in 1x units, drawn at SS x."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def _p(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def oval_pts(self, cx, cy, rx, ry, deg=0.0, n=72):
        pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
        return [rot(x, y, cx, cy, deg) for x, y in pts] if deg else pts

    def poly(self, pts, fill, ow=4.5, outline=OUT):
        if ow:
            self.d.polygon(self._p(pts), fill=outline)
            self.d.line(self._p(pts + pts[:1]), fill=outline, width=int(ow * 2 * SS), joint="curve")
            for x, y in pts[:: max(1, len(pts) // 24)]:
                r = ow * SS
                self.d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=outline)
        self.d.polygon(self._p(pts), fill=fill)

    def oval(self, cx, cy, rx, ry, fill, ow=4.5, deg=0.0, outline=OUT):
        self.poly(self.oval_pts(cx, cy, rx, ry, deg), fill, ow, outline)

    def dot(self, cx, cy, r, fill):
        self.d.ellipse([(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS], fill=fill)

    def limb(self, pts, w, fill, ow=4.5, outline=OUT):
        """A thick round-capped stroke through pts (with an outline)."""
        for width, col in (((w + 2 * ow), outline), (w, fill)):
            if width <= 0 or col is None:
                continue
            self.d.line(self._p(pts), fill=col, width=int(width * SS), joint="curve")
            for x, y in (pts[0], pts[-1]):
                r = width / 2 * SS
                self.d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=col)

    def line(self, pts, w, fill):
        self.d.line(self._p(pts), fill=fill, width=max(1, int(w * SS)), joint="curve")

    def arc(self, box, a0, a1, w, fill):
        x0, y0, x1, y1 = box
        self.d.arc([x0 * SS, y0 * SS, x1 * SS, y1 * SS], a0, a1, fill=fill, width=int(w * SS))

    def done(self):
        return self.img.resize((self.w, self.h), Image.LANCZOS)


def bezier(p0, p1, p2, p3, n=24):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def spiky(cx, cy, r_out, r_in, n, phase=0.0, wobble=0.0):
    pts = []
    for i in range(n * 2):
        a = math.pi * i / n + phase
        r = r_out if i % 2 == 0 else r_in
        r += wobble * math.sin(i * 1.7)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def bandhani_dots(pen, cx, cy, rx, ry, step=13, r=2.6, deg=0.0, col=WHITE):
    """The tie-dye dots of bandhani: little white rings, in rows, inside an oval."""
    y = -ry
    row = 0
    while y <= ry:
        x = -rx + (step / 2 if row % 2 else 0)
        while x <= rx:
            if (x / rx) ** 2 + (y / ry) ** 2 < 0.8:
                px, py = rot(cx + x, cy + y, cx, cy, deg)
                pen.dot(px, py, r, col)
                pen.dot(px, py, r * 0.45, DEEP_RED)
            x += step
        y += step * 0.85
        row += 1


def mirror(pen, cx, cy, r):
    """One abhla: the little round mirror of Kutchi embroidery, in its stitched ring."""
    pen.dot(cx, cy, r + 2.6, OUT)
    pen.dot(cx, cy, r + 1.4, YELLOW)
    pen.dot(cx, cy, r, SILVER)
    pen.dot(cx - r * 0.3, cy - r * 0.3, r * 0.35, WHITE)


# ---------------------------------------------------------------- Sawaj, the Gir lion cub
SAWAJ_SIZE = (420, 560)


def sawaj(pose=None):
    """pose: bob (px down), tilt (head degrees), lean (body degrees), hit_l / hit_r (0 rest … 1 stick on the drum),
    mouth (0 shut … 1 wide), blink (0/1), step (-1 left foot up … 1 right foot up), tail (−1 … 1), look (−1 … 1),
    happy (0/1: eyes shut in a smile)."""
    p = dict(bob=0, tilt=0, lean=0, hit_l=0, hit_r=0, mouth=0, blink=0, step=0, tail=0, look=0.4, happy=0)
    p.update(pose or {})
    W, H = SAWAJ_SIZE
    cx = W / 2
    b = p["bob"]

    body = Pen(W, H)
    # the tail, behind everything: a curve out to the left with a dark tuft
    sw = p["tail"] * 30
    tail = bezier((cx - 70, 450 + b), (cx - 150, 450 + b), (cx - 170, 360 + b + sw * 0.3), (cx - 140 + sw, 320 + b))
    body.limb(tail, 13, LION)
    body.poly(spiky(tail[-1][0], tail[-1][1], 24, 15, 7, 0.3), MANE)
    # legs: a garba step lifts one foot at a time
    for side, sx in ((-1, cx - 42), (1, cx + 42)):
        lift = max(0.0, p["step"] * side) * 26
        body.oval(sx, 505 + b * 0.4 - lift, 34, 36, LION)
        body.oval(sx + side * 4, 530 + b * 0.2 - lift, 30, 16, LION_LIGHT)
        for k in (-12, 0, 12):
            body.line([(sx + side * 4 + k, 524 - lift + b * 0.2), (sx + side * 4 + k, 538 - lift + b * 0.2)], 2.2, OUT)
    # the body and its pale belly
    body.oval(cx, 410 + b, 96, 104, LION, deg=p["lean"])
    body.oval(cx, 432 + b, 60, 70, LION_LIGHT, ow=0, deg=p["lean"])
    # a kediyu (the frilled Kathiyawadi top): a white yoke with red piping
    yoke = [(cx - 78, 340 + b), (cx + 78, 340 + b), (cx + 64, 372 + b), (cx - 64, 372 + b)]
    body.poly(yoke, WHITE, 4)
    for k in range(-60, 61, 20):
        body.dot(cx + k, 362 + b, 4, RED)
    # the dhol: a barrel across the belly, red with a yellow rope zigzag, on a strap over the shoulder
    body.limb([(cx - 76, 336 + b), (cx + 40, 400 + b), (cx + 88, 440 + b)], 8, MARIGOLD, ow=3)
    dy = 462 + b
    body.poly([(cx - 88, dy - 40), (cx + 88, dy - 40), (cx + 96, dy), (cx + 88, dy + 40), (cx - 88, dy + 40),
               (cx - 96, dy)], RED, 4.5)
    zig = []
    for i in range(13):
        zig.append((cx - 78 + i * 13, dy - 32 if i % 2 == 0 else dy + 32))
    body.line(zig, 4.5, YELLOW)
    body.line([(cx - 88, dy - 34), (cx + 88, dy - 34)], 3, DEEP_RED)
    body.line([(cx - 88, dy + 34), (cx + 88, dy + 34)], 3, DEEP_RED)
    body.oval(cx - 98, dy, 16, 42, CREAM)
    body.oval(cx + 98, dy, 16, 42, CREAM)
    # arms: paws with sticks, swinging onto the drum heads
    for side, hit in ((-1, p["hit_l"]), (1, p["hit_r"])):
        sh = (cx + side * 78, 352 + b)
        up = (1 - hit)
        hand = (cx + side * (112 + 18 * up), dy - 18 - 62 * up)
        elbow = (cx + side * (122 + 10 * up), 400 + b - 10 * up)
        body.limb([sh, elbow, hand], 34, LION)
        # the stick: the left hand's thin cane (tilli), the right hand's curved dagga
        tip = (hand[0] - side * (18 + 40 * hit), hand[1] + 26 + 30 * hit - 34 * up)
        body.limb([hand, tip], 6 if side < 0 else 9, (130, 70, 30, 255), ow=2.5)
        body.oval(hand[0], hand[1], 22, 20, LION)
        body.oval(hand[0], hand[1] + 6, 12, 8, LION_LIGHT, ow=0)

    # the head, drawn on its own layer and tilted round the neck
    head = Pen(W, H)
    hy = 228 + b
    head.poly(spiky(cx, hy, 150, 120, 16, 0.1, 3), MANE)
    head.poly(spiky(cx, hy + 4, 124, 104, 16, 0.3, 2), MANE_2, ow=0)
    for side in (-1, 1):
        head.oval(cx + side * 92, hy - 66, 26, 24, LION)
        head.oval(cx + side * 92, hy - 64, 13, 12, (230, 130, 110, 255), ow=0)
    head.oval(cx, hy + 6, 92, 86, LION)
    # the pagdi: a red bandhani turban with a yellow band and a little turra plume
    head.poly([(cx - 104, hy - 46), (cx - 96, hy - 98), (cx - 40, hy - 132), (cx + 40, hy - 132), (cx + 96, hy - 98),
               (cx + 104, hy - 46), (cx + 60, hy - 60), (cx, hy - 66), (cx - 60, hy - 60)], RED, 4.5)
    bandhani_dots(head, cx, hy - 96, 92, 32, step=15, r=3.0)
    head.line([(cx - 100, hy - 66), (cx - 40, hy - 84), (cx + 40, hy - 84), (cx + 100, hy - 66)], 9, YELLOW)
    head.line([(cx - 70, hy - 124), (cx + 30, hy - 72)], 3, DEEP_RED)
    head.limb([(cx + 64, hy - 118), (cx + 84, hy - 168)], 9, GREEN, ow=3)
    head.oval(cx + 88, hy - 176, 15, 22, YELLOW, deg=18)
    mirror(head, cx, hy - 74, 9)
    # the muzzle, the nose, the mouth
    for side in (-1, 1):
        head.oval(cx + side * 30, hy + 46, 36, 28, LION_LIGHT)
    m = max(0.0, min(1.0, p["mouth"]))
    if m > 0.08:
        mw, mh = 16 + 14 * m, 8 + 26 * m
        head.oval(cx, hy + 74 + mh * 0.45, mw, mh, (110, 24, 32, 255), ow=4)
        head.oval(cx, hy + 80 + mh * 0.75, mw * 0.6, mh * 0.35, (240, 110, 120, 255), ow=0)
        for side in (-1, 1):
            head.oval(cx + side * 30, hy + 50, 34, 24, LION_LIGHT, ow=0)
    else:
        head.arc((cx - 28, hy + 56, cx, hy + 80), 20, 160, 4, OUT)
        head.arc((cx, hy + 56, cx + 28, hy + 80), 20, 160, 4, OUT)
    for side in (-1, 1):
        for k in range(3):
            head.dot(cx + side * (22 + 12 * k), hy + 50 + (k % 2) * 8, 2.6, (160, 100, 60, 255))
    head.poly([(cx - 22, hy + 26), (cx + 22, hy + 26), (cx + 6, hy + 48), (cx - 6, hy + 48)], NOSE, 3)
    head.dot(cx - 8, hy + 31, 4, (140, 90, 80, 255))
    # eyes: big and bright, looking at Lali (right) by default
    for side in (-1, 1):
        ex, ey = cx + side * 36, hy - 12
        if p["happy"]:
            head.arc((ex - 16, ey - 10, ex + 16, ey + 18), 200, 340, 5, OUT)
        elif p["blink"]:
            head.line([(ex - 15, ey + 4), (ex + 15, ey + 4)], 5, OUT)
        else:
            head.oval(ex, ey, 18, 21, WHITE, ow=3.5)
            px = ex + p["look"] * 6
            head.dot(px, ey + 3, 11, (34, 20, 18, 255))
            head.dot(px + 4, ey - 2, 4, WHITE)
        head.line([(ex - 16, ey - 30 - m * 4), (ex + 14, ey - 34 - m * 4)][:: side], 5, MANE)

    img = body.done()
    h = head.done()
    if p["tilt"]:
        h = h.rotate(-p["tilt"], resample=Image.BICUBIC, center=(cx, 330 + b))
    img.alpha_composite(h)
    return img


# ---------------------------------------------------------------- Lali, the flamingo
LALI_SIZE = (400, 620)


def lali(pose=None):
    """pose: bob, tilt (neck sway, degrees), click (0 sticks apart … 1 sticks together), mouth, blink,
    step (−1 … 1: which leg is lifted), spin (0 … 1 one full garba twirl), skirt (−1 … 1 flare), happy."""
    p = dict(bob=0, tilt=0, click=0, mouth=0, blink=0, step=0, spin=0, skirt=0, happy=0)
    p.update(pose or {})
    W, H = LALI_SIZE
    cx = W / 2
    b = p["bob"]
    pen = Pen(W, H)

    # legs: long and pink, the knee bending backwards as a flamingo's does; one lifts for the garba step
    hip_y = 420 + b
    for side, sx in ((-1, cx - 20), (1, cx + 20)):
        lift = max(0.0, p["step"] * side)
        knee = (sx + side * 6 + 26 * lift, 500 + b * 0.5 - 34 * lift)
        foot = (sx + side * 10 - 30 * lift, 596 - 70 * lift)
        pen.limb([(sx, hip_y), knee, foot], 9, PINK, ow=3.5)
        pen.oval(knee[0], knee[1], 8, 8, DEEP_PINK, ow=3)
        pen.limb([(foot[0] - 20, foot[1] + 2), (foot[0] + 20, foot[1] + 2)], 7, DEEP_PINK, ow=3)

    # the chaniya: a flared skirt, green with a red hem, a yellow zigzag and mirrors
    fl = p["skirt"]
    top_y, hem_y = 380 + b, 470 + b
    sk = [(cx - 70, top_y), (cx + 70, top_y)]
    n = 10
    hem = []
    for i in range(n + 1):
        x = cx + 110 + 22 * fl - (220 + 44 * fl) * i / n
        y = hem_y + (10 if i % 2 else 0) + 6 * math.sin(i * 1.3 + fl * 3)
        hem.append((x, y))
    pen.poly(sk + hem, GREEN, 4.5)
    pen.poly([(hem[0][0] + 4, hem[0][1] - 30)] + hem + [(hem[-1][0] - 4, hem[-1][1] - 30)], RED, 0)
    pen.line([(x, y - 18 - (6 if i % 2 else 0)) for i, (x, y) in enumerate(hem)], 4, YELLOW)
    for i in range(1, n, 2):
        mirror(pen, hem[i][0], hem[i][1] - 44, 6)
    for k in (-44, 0, 44):
        mirror(pen, cx + k, top_y + 30, 5)

    # the body: a pink oval tilted up at the back, with darker tail feathers
    pen.poly([(cx - 70, 352 + b), (cx - 150, 320 + b), (cx - 132, 352 + b), (cx - 156, 360 + b), (cx - 70, 386 + b)],
             DEEP_PINK, 4)
    pen.oval(cx, 350 + b, 100, 60, PINK, deg=-8)
    # a choli: a red bodice band with a mirror
    pen.poly([(cx - 52, 318 + b), (cx + 62, 312 + b), (cx + 70, 344 + b), (cx - 50, 352 + b)], RED, 3.5)
    mirror(pen, cx + 8, 332 + b, 6)

    # wings as arms, holding the dandiya; they meet in front of her, left of the neck, on the click
    c = max(0.0, min(1.0, p["click"]))
    for side in (-1, 1):
        sh = (cx - 20 + side * 46, 336 + b)
        apart = (cx - 20 + side * 140, 262 + b)
        together = (cx - 44 + side * 16, 236 + b)
        hand = (apart[0] + (together[0] - apart[0]) * c, apart[1] + (together[1] - apart[1]) * c)
        mid = ((sh[0] + hand[0]) / 2 + side * 30, (sh[1] + hand[1]) / 2 + 26)
        pen.limb([sh, mid, hand], 30, DEEP_PINK, ow=4)
        pen.limb([sh, mid, hand], 14, PINK, ow=0)
        # the stick: striped, with a little bell at the top
        ang = math.radians(-90 + side * (38 - 30 * c))
        tip = (hand[0] + 96 * math.cos(ang), hand[1] + 96 * math.sin(ang))
        base = (hand[0] - 26 * math.cos(ang), hand[1] - 26 * math.sin(ang))
        pen.limb([base, tip], 11, YELLOW, ow=3.5)
        for k in range(1, 5):
            t = k / 5
            x, y = base[0] + (tip[0] - base[0]) * t, base[1] + (tip[1] - base[1]) * t
            pen.dot(x, y, 5.5, RED if k % 2 else GREEN)
        pen.dot(tip[0], tip[1], 9, OUT)
        pen.dot(tip[0], tip[1], 6.5, SILVER)
        # the wingtip: three feathers wrapped round the stick
        for k, dd in enumerate((-16, 0, 16)):
            pen.oval(hand[0] + side * 10 + dd * 0.3, hand[1] + 10 + abs(dd) * 0.2, 9, 20, DEEP_PINK if k != 1 else PINK,
                     ow=3, deg=side * (25 + dd))

    # the neck: an S-curve up to the head, swaying
    t = p["tilt"]
    head = (cx + 60 + t * 2.2, 128 + b - abs(t) * 0.4)
    neck = bezier((cx + 50, 318 + b), (cx + 120, 260 + b), (cx - 10 + t, 210 + b), head, 28)
    pen.limb(neck, 24, PINK, ow=4.5)
    hx, hy = head
    pen.oval(hx, hy, 40, 34, PINK, deg=t * 0.4)
    # a tikka on her forehead, and a red bindi
    pen.limb([(hx - 8, hy - 34), (hx - 2, hy - 20)], 3, YELLOW, ow=1.5)
    pen.dot(hx - 2, hy - 16, 5, RED)
    # the beak: pale, bending down to a black tip; the lower half opens to sing
    m = max(0.0, min(1.0, p["mouth"]))
    up = [(hx + 26, hy - 10), (hx + 66, hy - 6), (hx + 82, hy + 18), (hx + 78, hy + 44), (hx + 66, hy + 22),
          (hx + 30, hy + 10)]
    lo = [rot(x, y, hx + 28, hy + 8, 22 * m) for x, y in
          [(hx + 30, hy + 10), (hx + 64, hy + 22), (hx + 74, hy + 46), (hx + 58, hy + 30), (hx + 28, hy + 22)]]
    if m > 0.05:
        pen.poly([(hx + 30, hy + 10), (hx + 66, hy + 22)] + lo[2:4][::-1] + [(hx + 28, hy + 22)],
                 (110, 24, 32, 255), 0)
    pen.poly(lo, (250, 232, 214, 255), 3.5)
    pen.poly(up, (250, 232, 214, 255), 3.5)
    pen.poly([(hx + 72, hy + 6), (hx + 82, hy + 18), (hx + 78, hy + 44), (hx + 66, hy + 22)], OUT, 0)
    # the eye, with lashes
    ex, ey = hx + 6, hy - 8
    if p["happy"]:
        pen.arc((ex - 12, ey - 8, ex + 12, ey + 12), 200, 340, 4.5, OUT)
    elif p["blink"]:
        pen.line([(ex - 11, ey + 2), (ex + 11, ey + 2)], 4.5, OUT)
    else:
        pen.oval(ex, ey, 13, 14, WHITE, ow=3)
        pen.dot(ex + 3, ey + 1, 7.5, (34, 20, 18, 255))
        pen.dot(ex + 5, ey - 2, 2.8, WHITE)
    for k in (-1, 0, 1):
        pen.line([(ex - 6 + k * 7, ey - 13), (ex - 10 + k * 9, ey - 22)], 3, OUT)
    pen.dot(hx - 14, hy + 12, 8, (250, 160, 190, 255))

    img = pen.done()
    sp = p["spin"] % 1.0
    if sp:
        sx = math.cos(sp * 2 * math.pi)
        w = max(14, int(abs(sx) * W))
        flat = img.resize((w, H), Image.BICUBIC)
        if sx < 0:
            flat = flat.transpose(Image.FLIP_LEFT_RIGHT)
        out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        out.alpha_composite(flat, ((W - w) // 2, 0))
        img = out
    return img


# ---------------------------------------------------------------- props
def garbo(flame=1.0, size=1.0):
    """The garbo: a clay pot full of holes with a lamp burning inside: what garba is named after."""
    W, H = int(220 * size), int(300 * size)
    pen = Pen(W, H)
    s = size
    cx = W / 2
    by = 190 * s
    # flame on top
    fh = (46 + 14 * flame) * s
    pen.poly([(cx - 16 * s, 82 * s), (cx, 82 * s - fh), (cx + 16 * s, 82 * s), (cx, 92 * s)], MARIGOLD, 3)
    pen.poly([(cx - 7 * s, 84 * s), (cx, 84 * s - fh * 0.55), (cx + 7 * s, 84 * s)], (255, 244, 170, 255), 0)
    # the pot
    pen.oval(cx, by, 96 * s, 92 * s, (196, 88, 40, 255))
    pen.oval(cx, 100 * s, 44 * s, 14 * s, (150, 60, 30, 255))
    pen.line([(cx - 92 * s, by - 10 * s), (cx + 92 * s, by - 10 * s)], 5 * s, YELLOW)
    pen.line([(cx - 84 * s, by + 40 * s), (cx + 84 * s, by + 40 * s)], 4 * s, WHITE)
    for r, n in ((60, 9), (30, 6)):
        for i in range(n):
            a = 2 * math.pi * i / n
            x, y = cx + r * s * math.cos(a), by + 10 * s + r * 0.7 * s * math.sin(a)
            pen.dot(x, y, 7 * s, (255, 226, 120, int(170 + 85 * flame)))
    pen.dot(cx, by + 10 * s, 8 * s, (255, 236, 150, 255))
    return pen.done()


def diya(lit=1.0, size=1.0):
    """A clay lamp: dark until its word is learned, then lit."""
    W, H = int(70 * size), int(70 * size)
    pen = Pen(W, H)
    s = size
    cx = W / 2
    if lit > 0:
        fh = 26 * s * lit
        pen.poly([(cx - 8 * s, 40 * s), (cx, 40 * s - fh), (cx + 8 * s, 40 * s)], MARIGOLD, 2.5)
    pen.poly([(cx - 30 * s, 40 * s), (cx + 30 * s, 40 * s), (cx + 20 * s, 60 * s), (cx - 20 * s, 60 * s)],
             (196, 88, 40, 255) if lit else (110, 60, 50, 255), 3)
    pen.line([(cx - 26 * s, 46 * s), (cx + 26 * s, 46 * s)], 3 * s, YELLOW if lit else (150, 120, 90, 255))
    return pen.done()


def marigold(size=1.0):
    W = int(44 * size)
    pen = Pen(W, W)
    c = W / 2
    pen.poly(spiky(c, c, 20 * size, 15 * size, 9), MARIGOLD, 2.5)
    pen.dot(c, c, 7 * size, (230, 120, 0, 255))
    return pen.done()


def sheet(path):
    poses = [dict(), dict(bob=8, tilt=-8, hit_l=1, mouth=0.9, step=1, tail=1),
             dict(bob=2, tilt=7, hit_r=1, mouth=0.4, step=-1, blink=1, tail=-1), dict(happy=1, mouth=0.7, tilt=4)]
    lposes = [dict(), dict(click=1, mouth=0.9, step=1, tilt=8, skirt=1),
              dict(click=0.3, spin=0.18, step=-1, skirt=-1, tilt=-6), dict(happy=1, mouth=0.6, click=1)]
    W = 4 * 420
    img = Image.new("RGBA", (W, 560 + 620 + 330), (40, 14, 60, 255))
    for i, ps in enumerate(poses):
        img.alpha_composite(sawaj(ps), (i * 420, 0))
    for i, ps in enumerate(lposes):
        img.alpha_composite(lali(ps), (i * 420 + 10, 560))
    img.alpha_composite(garbo(1.0), (40, 1190))
    for i in range(4):
        img.alpha_composite(diya(1.0 if i < 2 else 0, 1.3), (330 + i * 100, 1260))
    img.alpha_composite(marigold(1.5), (800, 1260))
    img.convert("RGB").save(path)


if __name__ == "__main__":
    sheet(sys.argv[1] if len(sys.argv) > 1 else "taali-cast.png")
