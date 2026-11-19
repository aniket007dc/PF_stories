#!/usr/bin/env python3
"""Avatar kits for the Host style: load them, check them, put a frame together, and draw stand-ins.

    python3 tools/avatars.py                     check every kit in brand/avatars/
    python3 tools/avatars.py --stand-ins         (re)draw the two stand-in kits
    python3 tools/avatars.py --dc-host           (re)draw our host, after our sticker avatar
    python3 tools/avatars.py --grandpa           (re)draw the grandpa kit (a client for tests and samples)
    python3 tools/avatars.py --chatur            (re)draw Chatur, our crow: the host of the Corvid style
    python3 tools/avatars.py --used-by NAME ...  the episode folders whose cast uses these avatars

A kit is a folder brand/avatars/<name>/ (styles/host/AVATAR-KIT.md), in one of two formats.

Whole poses (easiest to draw by hand):
    poses/<pose>.png      the whole character in each pose, mouth closed, eyes open
    mouths/<shape>.png    the mouth alone, on a patch of skin, on the same canvas
    eyes/blink.png        the eyes closed, on the same canvas
    fronts/<pose>.png     optional: what sits in front of the face in that pose (a wing over the eye)

Layers (easiest to make with an AI image tool):
    bodies/<pose>.png     the body in each pose, without the head
    heads/<shape>.png     the whole head with each mouth shape, placed where it sits on the body
    heads/blink.png       the head with its eyes closed
    fronts/<pose>.png     optional: what sits in front of the head in that pose (a hand on the chin)

Either way: every file is a 1080 × 1080 PNG with a transparent background, on the same canvas, so the parts line up.
avatar.json (optional): {"name", "about", "voice": {"voice_id", "voice_name", "speed", ...}, "bust", "faces"}.
A head-and-shoulders kit ("bust": true, no hands) needs only poses/talk.png; its other poses are expressions.
A side-on kit says which way it looks ("faces": "left"): the build mirrors it to face the middle of the screen.
A kit can have other views of the same character, each a whole kit of its own in views/<view>/ (Chatur facing us is
views/front/): a pose in reel.json with "view": "front" turns the avatar for that line.
"""
import argparse
import math
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402

AVATARS = dc.BRAND_DIR / "avatars"
CANVAS = 1080
POSES = ["talk", "point", "open_hand", "shrug", "think", "one", "two", "three", "phone"]
EXTRA_POSES = ["ok", "thumbs_up", "wave", "clap", "celebrate", "point_down", "point_left", "facepalm", "arms_crossed",
               "surprised", "write", "four", "five", "listen"]
MOUTHS = ["closed", "teeth", "open", "wide", "round"]
EXTRA_MOUTHS = ["oo", "fv", "tongue", "smile"]
# a kit without a shape uses the nearest one it has
NEAREST = {"teeth": ["small", "open"], "small": ["teeth", "open"], "oo": ["round", "small"], "fv": ["teeth", "small", "closed"],
           "tongue": ["open", "teeth"], "smile": ["teeth", "closed"], "round": ["oo", "open"], "wide": ["open"],
           "open": ["wide", "teeth", "small"]}


def names():
    return sorted(p.name for p in AVATARS.iterdir() if p.is_dir()) if AVATARS.is_dir() else []


def views(name):
    """The other views a kit has, e.g. ["front"]: each is a whole kit in views/<view>/, loaded as "<name>/views/<view>"."""
    folder = AVATARS / name / "views"
    return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []


def pose_names(name):
    """The poses a kit (or a view of it, "<name>/views/<view>") has."""
    folder = AVATARS / name
    return sorted(p.stem for p in (folder / ("bodies" if layered(folder) else "poses")).glob("*.png"))


def meta(name):
    p = AVATARS / name / "avatar.json"
    try:
        return dc.load_json(p) if p.exists() else {}
    except Exception:  # noqa: BLE001
        return {}


def layered(folder):
    return (folder / "bodies").is_dir()


def _solid(im):
    """Where a picture is opaque: 255 there, 0 elsewhere."""
    return im.getchannel("A").point(lambda v: 255 if v > 128 else 0)


def check_kit(name):
    """Problems with one kit, in plain words. Empty when it's ready."""
    from PIL import Image, ImageChops
    folder = AVATARS / name
    if not folder.is_dir():
        return ["brand/avatars/{} doesn't exist".format(name)]
    problems = []
    needed = ["talk"] if meta(name).get("bust") else POSES       # head and shoulders: no hands, so no gestures
    if layered(folder):
        files = [("bodies", p) for p in needed] + [("heads", m) for m in MOUTHS + ["blink"]]
    else:
        files = [("poses", p) for p in needed] + [("mouths", m) for m in MOUTHS] + [("eyes", "blink")]
        files += [("poses", p.stem) for p in sorted((folder / "poses").glob("*.png")) if p.stem not in needed] \
            if (folder / "poses").is_dir() else []
    images = {}
    for sub, stem in files:
        f = folder / sub / "{}.png".format(stem)
        if not f.exists() and stem == "teeth" and (folder / sub / "small.png").exists():
            f = folder / sub / "small.png"          # the older name for it
        if not f.exists():
            problems.append("{}/{}/{}.png is missing".format(name, sub, stem))
            continue
        try:
            im = Image.open(f)
            im.load()
        except Exception as e:  # noqa: BLE001
            problems.append("{}/{}/{}.png can't be opened: {}".format(name, sub, stem, e))
            continue
        if im.size != (CANVAS, CANVAS):
            problems.append("{}/{}/{}.png is {}×{}; every file must be {}×{}".format(name, sub, stem, im.width, im.height, CANVAS, CANVAS))
        if im.mode != "RGBA" or im.getchannel("A").getextrema()[0] == 255:
            problems.append("{}/{}/{}.png has no transparent background".format(name, sub, stem))
        images[(sub, stem)] = im.convert("RGBA")
    if not layered(folder):
        # the mouths and the blink must land on the face of every pose. Side-on, a beak opens past the outline of
        # the head and its moving half isn't in the poses, so there the part every mouth shares (the top of the beak
        # and the cheek) has to land on it.
        foot = None
        if meta(name).get("faces"):
            for (sub, stem), over in images.items():
                if sub == "mouths":
                    foot = _solid(over) if foot is None else ImageChops.multiply(foot, _solid(over))
            if foot is not None and not foot.histogram()[255]:
                problems.append("{}/mouths: the mouth shapes share no part (the top of the beak) to line them up "
                                "with the face".format(name))
                foot = None
        for (sub, stem), over in images.items():
            if sub == "poses":
                continue
            box = over.getchannel("A").getbbox()
            if not box:
                problems.append("{}/{}/{}.png is empty".format(name, sub, stem))
                continue
            for pose in sorted({p for s_, p in images if s_ == "poses"}):
                body = images.get(("poses", pose))
                if body is None:
                    continue
                if foot is not None and sub == "mouths":
                    covered = ImageChops.multiply(foot, _solid(body)).histogram()[255] / max(1, foot.histogram()[255])
                else:
                    a = body.getchannel("A").crop(box)
                    covered = sum(a.histogram()[129:]) / max(1, a.width * a.height)
                if covered < 0.9:
                    problems.append("{}/{}/{}.png doesn't sit on the face in poses/{}.png: the head must be in the same "
                                    "place in every pose".format(name, sub, stem, pose))
                    break
    voice = (meta(name).get("voice") or {})
    if voice and not voice.get("voice_id"):
        problems.append("{}/avatar.json → voice needs a voice_id".format(name))
    for view in views(name):
        problems += check_kit("{}/views/{}".format(name, view))
    return problems


@lru_cache(maxsize=None)
def load(name):
    """A kit, ready to put frames together with compose(). Poses it doesn't have show as talk."""
    from PIL import Image
    folder = AVATARS / name

    def imgs(sub):
        return {p.stem: Image.open(p).convert("RGBA") for p in sorted((folder / sub).glob("*.png"))} if (folder / sub).is_dir() else {}
    kit = {"name": name, "meta": meta(name), "layered": layered(folder)}
    if kit["layered"]:
        kit.update(poses=imgs("bodies"), heads=imgs("heads"), fronts=imgs("fronts"), mouths={}, blink=None)
        if "closed" not in kit["heads"]:
            raise SystemExit("brand/avatars/{} has no heads/closed.png".format(name))
        box = kit["heads"]["closed"].getchannel("A").getbbox()
        kit["anchor"] = ((box[0] + box[2]) / 2, box[1] + 0.45 * (box[3] - box[1])) if box else (540, 400)
    else:
        kit.update(poses=imgs("poses"), mouths=imgs("mouths"), heads={}, fronts=imgs("fronts"))
        blink = folder / "eyes" / "blink.png"
        kit["blink"] = Image.open(blink).convert("RGBA") if blink.exists() else None
        box = kit["blink"].getchannel("A").getbbox() if kit["blink"] is not None else None
        kit["anchor"] = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2) if box else (540, 400)
    if "talk" not in kit["poses"]:
        raise SystemExit("brand/avatars/{} has no {}/talk.png".format(name, "bodies" if kit["layered"] else "poses"))
    kit["views"] = {v: load("{}/views/{}".format(name, v)) for v in views(name)}
    return kit


def nearest(shapes, want):
    """The kit's picture for a mouth shape, or the nearest shape it has."""
    for s in [want] + NEAREST.get(want, []) + ["open", "closed"]:
        if s in shapes:
            return shapes[s]
    return None


def compose(kit, pose, mouth="closed", blink=False, view=None):
    """The character on its 1080 × 1080 canvas: in this pose, with this mouth, eyes open or closed, in one of its views
    (None: the kit's own)."""
    kit = kit.get("views", {}).get(view, kit) if view else kit
    img = kit["poses"].get(pose, kit["poses"]["talk"]).copy()
    if kit["layered"]:
        head = kit["heads"].get("blink") if blink else None
        img.alpha_composite(head if head is not None else nearest(kit["heads"], mouth))
        front = kit["fronts"].get(pose)
        if front is not None:
            img.alpha_composite(front)
        return img
    if blink and kit["blink"] is not None:
        img.alpha_composite(kit["blink"])
    if mouth != "closed" or kit["meta"].get("faces"):       # side-on, the poses leave out the part that moves
        m = nearest(kit["mouths"], mouth)
        if m is not None:
            img.alpha_composite(m)
    front = kit["fronts"].get(pose)
    if front is not None:
        img.alpha_composite(front)
    return img


# ---------------------------------------------------------------- stand-ins

STAND_INS = {
    "stand-in-host": {"name": "Stand-in host", "skin": (196, 132, 84), "hair": (34, 28, 26), "top": (26, 26, 26),
                      "trim": (245, 238, 48), "hair_style": "short",
                      "about": "A placeholder host until the real avatar kit is uploaded."},
    "stand-in-client": {"name": "Stand-in client", "skin": (224, 170, 122), "hair": (52, 34, 26), "top": (200, 68, 58),
                        "trim": (243, 240, 234), "hair_style": "bun",
                        "about": "A placeholder client (a shop owner) until the real avatar kit is uploaded."},
}
INK = (26, 26, 26)
HEAD = (540, 400)           # where the face is, in every pose
MOUTH = (540, 512)
EYES = ((478, 392), (602, 392))
DOWN_L, DOWN_R = (330, 1010), (750, 1010)


def _hand_targets(pose):
    """(left hand, right hand, extra) in canvas pixels: where the hands go in each pose."""
    return {
        "talk": (DOWN_L, DOWN_R, None),
        "point": (DOWN_L, (905, 300), "point"),
        "open_hand": (DOWN_L, (860, 760), "palm"),
        "shrug": ((175, 760), (905, 760), "palms"),
        "think": (DOWN_L, (640, 655), "chin"),
        "one": (DOWN_L, (850, 420), 1),
        "two": (DOWN_L, (850, 420), 2),
        "three": (DOWN_L, (850, 420), 3),
        "four": (DOWN_L, (850, 420), 4),
        "five": (DOWN_L, (850, 420), 5),
        "phone": (DOWN_L, (735, 800), "phone"),
        "ok": (DOWN_L, (850, 440), "ok"),
        "thumbs_up": (DOWN_L, (850, 460), "thumb"),
        "wave": (DOWN_L, (880, 330), 5),
        "clap": ((480, 770), (600, 770), "clap"),
        "celebrate": ((190, 300), (890, 300), "fists"),
        "point_down": (DOWN_L, (830, 960), "point_down"),
        "point_left": ((175, 300), DOWN_R, "point_left"),
        "facepalm": (DOWN_L, (585, 300), "palm_front"),
        "arms_crossed": (None, None, "crossed"),
        "surprised": ((392, 540), (688, 540), "cheeks"),
        "write": ((430, 840), (600, 800), "write"),
        "listen": (DOWN_L, (735, 410), "ear"),
    }[pose]


def _arm(d, start, end, top, width_out=88, width_in=70):
    sx, sy = start
    tx, ty = end
    mx, my = (sx + tx) / 2 + (40 if tx > sx else -40), (sy + ty) / 2 + 40
    for width, colour in ((width_out, INK), (width_in, top)):
        d.line([(sx, sy), (mx, my), (tx, ty)], fill=colour, width=width, joint="curve")


def _hand(d, xy, skin, r=44):
    d.ellipse([xy[0] - r, xy[1] - r, xy[0] + r, xy[1] + r], fill=skin, outline=INK, width=9)


def _finger(d, x, y0, y1, skin, w=11):
    d.rounded_rectangle([x - w, min(y0, y1), x + w, max(y0, y1)], radius=w, fill=skin, outline=INK, width=6)


def _draw_stand_in(look, pose):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    skin, top, trim = look["skin"], look["top"], look["trim"]
    ol = 9
    d.rounded_rectangle([250, 690, 830, 1180], radius=150, fill=top, outline=INK, width=ol)
    d.polygon([(470, 690), (540, 790), (610, 690)], fill=skin, outline=INK)
    d.line([(470, 690), (540, 790), (610, 690)], fill=INK, width=ol)
    d.rounded_rectangle([505, 860, 575, 930], radius=18, fill=trim, outline=INK, width=6)   # a badge, no words
    d.rectangle([495, 560, 585, 700], fill=skin, outline=INK, width=ol)
    hx, hy = HEAD
    d.ellipse([hx - 205, hy - 20, hx - 155, hy + 70], fill=skin, outline=INK, width=ol)
    d.ellipse([hx + 155, hy - 20, hx + 205, hy + 70], fill=skin, outline=INK, width=ol)
    d.ellipse([hx - 170, hy - 190, hx + 170, hy + 190], fill=skin, outline=INK, width=ol)
    hair = look["hair"]
    if look["hair_style"] == "short":
        d.chord([hx - 178, hy - 205, hx + 178, hy + 120], 180, 360, fill=hair, outline=INK, width=ol)
        d.ellipse([hx - 120, hy - 225, hx + 60, hy - 120], fill=hair, outline=INK, width=ol)
    else:
        d.ellipse([hx - 80, hy - 300, hx + 80, hy - 160], fill=hair, outline=INK, width=ol)
        d.chord([hx - 178, hy - 200, hx + 178, hy + 110], 180, 360, fill=hair, outline=INK, width=ol)
    surprised = pose == "surprised"
    for ex, ey in EYES:
        r = 38 if surprised else 34
        d.ellipse([ex - r, ey - r + 4, ex + r, ey + r - 4], fill=(255, 255, 255), outline=INK, width=6)
        d.ellipse([ex - 14, ey - 12, ex + 14, ey + 16], fill=INK)
        d.ellipse([ex - 5, ey - 6, ex + 3, ey + 2], fill=(255, 255, 255))
        lift = 14 if surprised else 0
        d.arc([ex - 40, ey - 78 - lift, ex + 40, ey - 30 - lift], 200, 340, fill=INK, width=8)
    d.arc([hx - 22, hy + 10, hx + 22, hy + 70], 300, 60, fill=INK, width=6)
    d.arc([MOUTH[0] - 46, MOUTH[1] - 34, MOUTH[0] + 46, MOUTH[1] + 22], 20, 160, fill=INK, width=8)
    lh, rh, extra = _hand_targets(pose)
    if extra == "crossed":
        lighter = tuple(min(255, int(c + (255 - c) * 0.22)) for c in top)   # visible across the body
        for start, end in (((300, 760), (720, 860)), ((780, 760), (360, 860))):
            _arm(d, start, end, lighter)
        return img
    for start, hand in (((300, 760), lh), ((780, 760), rh)):
        _arm(d, start, hand, top)
    for hand in (lh, rh):
        if hand[1] < 1000:
            _hand(d, hand, skin)
    rx, ry = rh
    if isinstance(extra, int):
        for k in range(extra):
            fx = rx - 12 * (extra - 1) + 24 * k
            _finger(d, fx, ry - 105 + (10 if k in (0, extra - 1) and extra > 2 else 0), ry - 30, skin)
    elif extra == "point":
        _finger(d, rx + 22, ry - 110, ry - 30, skin, 12)
    elif extra == "point_down":
        _finger(d, rx - 10, ry + 30, ry + 110, skin, 12)
    elif extra == "point_left":
        _finger(d, lh[0] - 22, lh[1] - 110, lh[1] - 30, skin, 12)
    elif extra == "phone":
        d.rounded_rectangle([rx - 70, ry - 150, rx + 50, ry + 60], radius=22, fill=INK, outline=INK, width=6)
        d.rounded_rectangle([rx - 58, ry - 136, rx + 38, ry + 40], radius=14, fill=(60, 60, 64))
        _hand(d, (rx + 40, ry + 10), skin, 30)
    elif extra == "thumb":
        _finger(d, rx, ry - 100, ry - 30, skin, 12)
    elif extra == "ok":
        d.ellipse([rx - 30, ry - 80, rx + 10, ry - 40], outline=INK, width=8)
    elif extra == "clap":
        for k in range(3):
            d.arc([rx - 160 - 30 * k, ry - 120 - 30 * k, rx + 40 + 30 * k, ry + 80 + 30 * k], 230, 310, fill=INK, width=5)
    elif extra == "write":
        d.rectangle([lh[0] - 90, lh[1] - 120, lh[0] + 70, lh[1] + 40], fill=(255, 255, 255), outline=INK, width=7)
        for k in range(4):
            d.line([(lh[0] - 70, lh[1] - 90 + 30 * k), (lh[0] + 50, lh[1] - 90 + 30 * k)], fill=(170, 170, 170), width=4)
        _hand(d, lh, skin, 40)
        d.line([(rx, ry), (rx - 60, ry + 70)], fill=(245, 238, 48), width=16)
        _hand(d, rh, skin, 36)
    return img


def _mouth(look, shape):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    mx, my = MOUTH
    d.ellipse([mx - 70, my - 48, mx + 70, my + 46], fill=look["skin"])      # covers the closed smile
    dark, tongue, white = (60, 20, 24), (214, 96, 102), (255, 255, 255)
    if shape == "closed":
        d.arc([mx - 46, my - 34, mx + 46, my + 22], 20, 160, fill=INK, width=8)
    elif shape == "teeth":                                                  # lips apart, teeth together
        d.rounded_rectangle([mx - 38, my - 6, mx + 38, my + 22], radius=12, fill=white, outline=INK, width=6)
        d.line([(mx - 32, my + 8), (mx + 32, my + 8)], fill=(150, 150, 150), width=3)
    elif shape == "open":
        d.ellipse([mx - 32, my - 16, mx + 32, my + 34], fill=dark, outline=INK, width=6)
        d.chord([mx - 22, my + 8, mx + 22, my + 34], 180, 360, fill=tongue)
    elif shape == "wide":
        d.rounded_rectangle([mx - 50, my - 12, mx + 50, my + 34], radius=18, fill=dark, outline=INK, width=6)
        d.rectangle([mx - 40, my - 6, mx + 40, my + 6], fill=white)
    elif shape == "round":
        d.ellipse([mx - 22, my - 14, mx + 22, my + 30], fill=dark, outline=INK, width=6)
    elif shape == "oo":                                                     # lips pushed forward
        d.ellipse([mx - 20, my - 4, mx + 20, my + 30], fill=(172, 82, 86), outline=INK, width=6)
        d.ellipse([mx - 8, my + 6, mx + 8, my + 20], fill=dark)
    elif shape == "fv":                                                     # top teeth on the bottom lip
        d.rectangle([mx - 30, my, mx + 30, my + 12], fill=white, outline=INK, width=4)
        d.arc([mx - 36, my - 2, mx + 36, my + 26], 20, 160, fill=INK, width=7)
    elif shape == "tongue":                                                 # l: the tongue up behind the teeth
        d.ellipse([mx - 32, my - 16, mx + 32, my + 34], fill=dark, outline=INK, width=6)
        d.ellipse([mx - 14, my - 10, mx + 14, my + 12], fill=tongue)
    elif shape == "smile":
        d.chord([mx - 52, my - 30, mx + 52, my + 32], 0, 180, fill=white, outline=INK, width=6)
    return img


def _blink(look):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for ex, ey in EYES:
        d.ellipse([ex - 42, ey - 40, ex + 42, ey + 40], fill=look["skin"])
        d.arc([ex - 30, ey - 14, ex + 30, ey + 18], 20, 160, fill=INK, width=8)
    return img

# ---------------------------------------------------------------- characters drawn in code: our host and the grandpa

SS = 3        # drawn 3× bigger, then shrunk: smooth edges


class _Scaled:
    """An ImageDraw that draws everything k times bigger, so the same 1080-canvas numbers draw a big, smooth picture."""

    def __init__(self, d, k):
        self.d, self.k = d, k

    def _xy(self, xy):
        if isinstance(xy[0], (tuple, list)):
            return [(x * self.k, y * self.k) for x, y in xy]
        return [v * self.k for v in xy]

    def _kw(self, kw):
        kw = dict(kw)
        if "width" in kw:
            kw["width"] = max(1, int(round(kw["width"] * self.k)))
        if "radius" in kw:
            kw["radius"] = kw["radius"] * self.k
        return kw

    def ellipse(self, xy, **kw):
        self.d.ellipse(self._xy(xy), **self._kw(kw))

    def rectangle(self, xy, **kw):
        self.d.rectangle(self._xy(xy), **self._kw(kw))

    def rounded_rectangle(self, xy, **kw):
        self.d.rounded_rectangle(self._xy(xy), **self._kw(kw))

    def polygon(self, xy, **kw):
        self.d.polygon(self._xy(xy), **self._kw(kw))

    def line(self, xy, **kw):
        self.d.line(self._xy(xy), **self._kw(kw))

    def arc(self, xy, start, end, **kw):
        self.d.arc(self._xy(xy), start, end, **self._kw(kw))

    def chord(self, xy, start, end, **kw):
        self.d.chord(self._xy(xy), start, end, **self._kw(kw))


def _drawn(paint, *args):
    """One kit picture: painted big on a transparent canvas, then shrunk to 1080 × 1080."""
    from PIL import Image, ImageDraw
    big = Image.new("RGBA", (CANVAS * SS, CANVAS * SS), (0, 0, 0, 0))
    paint(_Scaled(ImageDraw.Draw(big), SS), *args)
    # shrunk with premultiplied alpha, so the empty (black) canvas doesn't darken the edges of what's drawn
    return big.convert("RGBa").resize((CANVAS, CANVAS), Image.LANCZOS).convert("RGBA")


def _gestures(d, pose, sleeve, skin, crossed, parts=None):
    """The arms and hands for a pose, as the stand-ins have them. parts swaps them for a bird's: "arm", "hand" and
    "finger" drawing functions, the "phone" colours (case, screen) and the "mark" colour for motion lines and rings."""
    parts = parts or {}
    arm, hand_, finger = parts.get("arm", _arm), parts.get("hand", _hand), parts.get("finger", _finger)
    case, screen = parts.get("phone", (INK, (60, 60, 64)))
    mark = parts.get("mark", INK)
    lh, rh, extra = _hand_targets(pose)
    if extra == "crossed":
        for start, end in (((300, 760), (720, 860)), ((780, 760), (360, 860))):
            arm(d, start, end, crossed)
        return
    for start, hand in (((300, 760), lh), ((780, 760), rh)):
        arm(d, start, hand, sleeve)
    for hand in (lh, rh):
        if hand[1] < 1000:
            hand_(d, hand, skin)
    rx, ry = rh
    if isinstance(extra, int):
        for k in range(extra):
            fx = rx - 12 * (extra - 1) + 24 * k
            finger(d, fx, ry - 105 + (10 if k in (0, extra - 1) and extra > 2 else 0), ry - 30, skin)
    elif extra == "point":
        finger(d, rx + 22, ry - 110, ry - 30, skin, 12)
    elif extra == "point_down":
        finger(d, rx - 10, ry + 30, ry + 110, skin, 12)
    elif extra == "point_left":
        finger(d, lh[0] - 22, lh[1] - 110, lh[1] - 30, skin, 12)
    elif extra == "phone":
        d.rounded_rectangle([rx - 70, ry - 150, rx + 50, ry + 60], radius=22, fill=case, outline=INK, width=6)
        d.rounded_rectangle([rx - 58, ry - 136, rx + 38, ry + 40], radius=14, fill=screen)
        hand_(d, (rx + 40, ry + 10), skin, 30)
    elif extra == "thumb":
        finger(d, rx, ry - 100, ry - 30, skin, 12)
    elif extra == "ok":
        d.ellipse([rx - 30, ry - 80, rx + 10, ry - 40], outline=mark, width=8)
    elif extra == "clap":
        for k in range(3):
            d.arc([rx - 160 - 30 * k, ry - 120 - 30 * k, rx + 40 + 30 * k, ry + 80 + 30 * k], 230, 310, fill=mark, width=5)
    elif extra == "write":
        d.rectangle([lh[0] - 90, lh[1] - 120, lh[0] + 70, lh[1] + 40], fill=(255, 255, 255), outline=INK, width=7)
        for k in range(4):
            d.line([(lh[0] - 70, lh[1] - 90 + 30 * k), (lh[0] + 50, lh[1] - 90 + 30 * k)], fill=(170, 170, 170), width=4)
        hand_(d, lh, skin, 40)
        d.line([(rx, ry), (rx - 60, ry + 70)], fill=(245, 238, 48), width=16)
        hand_(d, rh, skin, 36)


def _make_kit(name, meta, paint_pose, paint_mouth, paint_blink, paint_front=None, more_poses=()):
    """Draw a whole Format A kit. paint_front(d, pose), when given, draws what's in front of the face in a pose; it
    becomes fronts/<pose>.png wherever it covers a mouth or the blink, so a wing over the eye stays over it."""
    import shutil
    import numpy as np
    from PIL import Image
    folder = AVATARS / name
    kept = {}
    if (folder / "avatar.json").exists():                # a person's choices (the voice) survive a redraw
        kept = {k: v for k, v in dc.load_json(folder / "avatar.json").items() if k not in meta}
    shutil.rmtree(folder, ignore_errors=True)
    for sub in ("poses", "mouths", "eyes"):
        (folder / sub).mkdir(parents=True, exist_ok=True)

    def save(img, path):
        a = np.array(img)
        a[a[..., 3] == 0, :3] = 0                    # nothing hidden under the transparent parts: smaller files
        Image.fromarray(a, "RGBA").save(path, optimize=True)
    for pose in POSES + EXTRA_POSES + list(more_poses):
        save(_drawn(paint_pose, pose), folder / "poses" / "{}.png".format(pose))
    face = np.zeros((CANVAS, CANVAS), bool)
    for shape in MOUTHS + EXTRA_MOUTHS:
        img = _drawn(paint_mouth, shape)
        face |= np.asarray(img.getchannel("A")) > 8
        save(img, folder / "mouths" / "{}.png".format(shape))
    img = _drawn(paint_blink)
    face |= np.asarray(img.getchannel("A")) > 8
    save(img, folder / "eyes" / "blink.png")
    for pose in POSES + EXTRA_POSES + list(more_poses) if paint_front else []:
        img = _drawn(paint_front, pose)
        if (np.asarray(img.getchannel("A")) > 8)[face].any():
            (folder / "fronts").mkdir(exist_ok=True)
            save(img, folder / "fronts" / "{}.png".format(pose))
    dc.save_json(folder / "avatar.json", dict(meta, **kept))
    print("drew", dc.rel(folder))


# ---- our host, drawn after our sticker avatar

DC_HOST = {"name": "DC host", "about": "Digital Corvids' host: a friendly young presenter with fair skin, a short-trimmed "
           "dark beard, black side-swept hair, thick brows and a yellow hoodie over a white T-shirt. Sharp, warm and quick.",
           "skin": (243, 212, 192), "shade": (226, 188, 166), "line": (198, 146, 124), "crease": (230, 192, 170),
           "hair": (28, 24, 24), "hair_light": (74, 66, 64), "beard": (82, 74, 72), "beard_dark": (54, 47, 46),
           "grey": (146, 142, 140), "lips": (200, 124, 116), "iris": (48, 32, 26),
           "hoodie": (250, 205, 92), "hoodie_shade": (226, 172, 62), "tee": (238, 240, 242),
           "string": (248, 244, 230), "tip": (176, 178, 186)}
H_MOUTH = (540, 534)          # under the moustache, inside the beard


def _host_eye(d, h, ex, ey, wide=False):
    """An almond eye under a slightly heavy lid, with a very dark brown iris."""
    top, bot = (19, 15) if wide else (13, 11)
    d.arc([ex - 40, ey - top - 16, ex + 40, ey + 6], 200, 340, fill=h["crease"], width=6)          # the lid's crease
    d.arc([ex - 30, ey + 4, ex + 30, ey + bot + 16], 30, 150, fill=h["crease"], width=5)           # a shadow under the eye
    pts = [(ex - 36, ey + 3), (ex - 22, ey - top + 4), (ex, ey - top), (ex + 22, ey - top + 4), (ex + 36, ey + 2),
           (ex + 20, ey + bot), (ex, ey + bot + 2), (ex - 20, ey + bot)]
    d.polygon(pts, fill=(250, 246, 240), outline=INK, width=4)
    r = 14 if wide else 13
    d.ellipse([ex - r, ey - r + 3, ex + r, ey + r + 3], fill=h["iris"], outline=INK, width=3)       # a little under the lid
    d.ellipse([ex - 6, ey - 2, ex + 6, ey + 10], fill=(14, 10, 8))
    d.ellipse([ex - 8, ey - 6, ex - 2, ey], fill=(255, 255, 255))
    d.line(pts[:5], fill=INK, width=9, joint="curve")                       # the upper lid and its lashes


def _host_brow(d, h, ex, ey, inward, lift=0, frown=0):
    """Thick, nearly straight brows. inward: +1 when the inner end is to the right (the left eye), -1 for the right."""
    pts = [(ex - inward * 48, ey - 36 - lift), (ex - inward * 10, ey - 48 - lift), (ex + inward * 40, ey - 46 - lift + frown)]
    d.line(pts, fill=h["hair"], width=21, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=h["hair"])


def _host_closed_lips(d, h):
    mx, my = H_MOUTH
    d.chord([mx - 28, my - 4, mx + 28, my + 18], 0, 180, fill=h["lips"], outline=INK, width=4)   # the lower lip
    d.arc([mx - 38, my - 22, mx + 38, my + 4], 25, 155, fill=INK, width=6)                       # where the lips meet


def _grey_strands(d, h, spots):
    """A few grey hairs where the beard is greying: the chin and the corners of the moustache."""
    for x, y, dx in spots:
        d.line([(x, y), (x + dx, y + 10)], fill=h["grey"], width=3)


def _host_beard_area():
    """The short beard: from the sideburns along the jaw (the face's own outline) and up to the cheek line."""
    import math
    hx, hy = HEAD
    cx, cy, rx, ry = hx, hy + 12, 156, 202
    outer = [(cx + rx * math.cos(math.radians(t)), cy + ry * math.sin(math.radians(t))) for t in range(-4, 185, 6)]
    cheek = [(hx - 150, hy + 6), (hx - 140, hy + 50), (hx - 118, hy + 84), (hx - 74, hy + 96), (hx - 36, hy + 84),
             (hx, hy + 80), (hx + 36, hy + 84), (hx + 74, hy + 96), (hx + 118, hy + 84), (hx + 140, hy + 50),
             (hx + 150, hy + 6)]
    return outer + cheek


def _inside(pt, poly):
    x, y = pt
    hit = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


@lru_cache(maxsize=None)
def _host_stubble():
    """Dark specks over the beard, so it reads as short hair; always the same, so the mouths can match them."""
    import random
    rng = random.Random(11)
    area = _host_beard_area()
    xs, ys = [p[0] for p in area], [p[1] for p in area]
    out = []
    while len(out) < 200:
        pt = (rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys)))
        if _inside(pt, area):
            out.append((round(pt[0], 1), round(pt[1], 1), rng.choice((1.6, 2.0, 2.4))))
    return tuple(out)


@lru_cache(maxsize=None)
def _host_grey():
    """A few grey hairs at the chin."""
    import random
    rng = random.Random(5)
    hx, hy = HEAD
    return tuple((round(hx + rng.uniform(-30, 30), 1), round(hy + rng.uniform(178, 204), 1)) for _ in range(10))


def _paint_dc_host(d, pose):
    h = DC_HOST
    hx, hy = HEAD
    ol, skin = 9, h["skin"]
    # the hood bunched behind the neck, the open hoodie, the white T-shirt
    d.ellipse([392, 628, 688, 772], fill=h["hoodie_shade"], outline=INK, width=ol)
    d.rounded_rectangle([250, 690, 830, 1180], radius=150, fill=h["hoodie"], outline=INK, width=ol)
    for box, a0, a1 in (([300, 760, 470, 1020], 110, 170), ([610, 760, 780, 1020], 10, 70)):      # folds
        d.arc(box, a0, a1, fill=h["hoodie_shade"], width=6)
    d.rectangle([496, 560, 584, 712], fill=skin, outline=INK, width=ol)                            # the neck
    d.polygon([(492, 706), (588, 706), (606, 1180), (474, 1180)], fill=h["tee"])
    d.line([(492, 706), (474, 1180)], fill=INK, width=7)
    d.line([(588, 706), (606, 1180)], fill=INK, width=7)
    d.arc([496, 676, 584, 730], 20, 160, fill=INK, width=6)                                        # the T-shirt's neck
    for x0, x1 in ((516, 506), (564, 576)):                                                        # the drawstrings
        d.line([(x0, 718), (x1, 930)], fill=INK, width=16)
        d.line([(x0, 718), (x1, 930)], fill=h["string"], width=9)
        d.rounded_rectangle([x1 - 9, 922, x1 + 9, 964], radius=6, fill=h["tip"], outline=INK, width=5)
    # the hair behind the head: its outline is the hair's shape, black, full and a little messy on top
    back = [(hx - 150, hy - 6), (hx - 166, hy - 60), (hx - 176, hy - 124), (hx - 172, hy - 180), (hx - 158, hy - 222),
            (hx - 138, hy - 242), (hx - 128, hy - 264), (hx - 96, hy - 270), (hx - 76, hy - 290), (hx - 40, hy - 288),
            (hx - 14, hy - 304), (hx + 24, hy - 296), (hx + 58, hy - 300), (hx + 86, hy - 282), (hx + 118, hy - 274),
            (hx + 140, hy - 248), (hx + 166, hy - 226), (hx + 178, hy - 180), (hx + 188, hy - 120), (hx + 178, hy - 56),
            (hx + 156, hy - 16), (hx, hy - 40)]
    d.polygon(back, fill=h["hair"], outline=INK, width=8)
    # ears and face: a long oval
    for side in (-1, 1):
        x0, x1 = (hx - 196, hx - 142) if side < 0 else (hx + 142, hx + 196)
        d.ellipse([x0, hy - 20, x1, hy + 86], fill=skin, outline=INK, width=ol)
        d.arc([x0 + 14, hy, x1 - 14, hy + 64], 90 if side < 0 else 270, 270 if side < 0 else 90, fill=h["line"], width=5)
    face = [hx - 156, hy - 190, hx + 156, hy + 214]
    d.ellipse(face, fill=skin, outline=INK, width=ol)
    d.chord(face, 312, 48, fill=h["shade"])                                                       # shade on one side
    d.arc(face, 0, 360, fill=INK, width=ol)
    # the fringe: swept from a parting on the left across the top, falling towards the right temple
    front = [(hx - 172, hy - 140), (hx - 152, hy - 218), (hx - 96, hy - 262), (hx - 10, hy - 286), (hx + 80, hy - 276),
             (hx + 150, hy - 230), (hx + 186, hy - 150), (hx + 180, hy - 70), (hx + 150, hy - 84), (hx + 128, hy - 112),
             (hx + 96, hy - 140), (hx + 50, hy - 160), (hx, hy - 172), (hx - 50, hy - 176), (hx - 96, hy - 170),
             (hx - 126, hy - 150), (hx - 144, hy - 118), (hx - 156, hy - 80)]
    d.polygon(front, fill=h["hair"])
    d.line(front[7:] + [front[0]], fill=INK, width=7, joint="curve")                             # the hairline
    for pts in (((hx - 120, hy - 240), (hx - 40, hy - 250), (hx + 60, hy - 222), (hx + 140, hy - 150)),     # the sweep
                ((hx - 146, hy - 196), (hx - 70, hy - 214), (hx + 20, hy - 196), (hx + 110, hy - 140)),
                ((hx - 30, hy - 276), (hx + 60, hy - 262), (hx + 132, hy - 216), (hx + 170, hy - 140)),
                ((hx - 112, hy - 178), (hx - 40, hy - 192), (hx + 40, hy - 176), (hx + 90, hy - 150))):
        d.line(pts, fill=h["hair_light"], width=6, joint="curve")
    d.line([(hx - 150, hy - 214), (hx - 60, hy - 236), (hx + 40, hy - 208), (hx + 124, hy - 128)], fill=INK, width=4, joint="curve")
    for pts in (((hx + 60, hy - 162), (hx + 88, hy - 130), (hx + 100, hy - 96)),                          # loose strands
                ((hx + 94, hy - 142), (hx + 118, hy - 112), (hx + 126, hy - 82))):
        d.line(pts, fill=h["hair"], width=7, joint="curve")
    # the beard: trimmed short (a 1 or 2 guard), hugging the jaw up to the sideburns, with a trimmed moustache
    d.polygon(_host_beard_area(), fill=h["beard"])
    for x, y, r in _host_stubble():
        d.ellipse([x - r, y - r, x + r, y + r], fill=h["beard_dark"])
    for x, y in _host_grey():
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=h["grey"])
    d.polygon([(hx - 72, hy + 100), (hx - 36, hy + 84), (hx, hy + 80), (hx + 36, hy + 84), (hx + 72, hy + 100),
               (hx + 52, hy + 112), (hx, hy + 106), (hx - 52, hy + 112)], fill=h["beard_dark"])          # the moustache
    d.arc(face, -6, 186, fill=INK, width=ol)                                                       # the jaw stays crisp
    _host_closed_lips(d, h)
    # the nose: long and straight, with a rounded tip
    d.line([(hx + 8, hy - 40), (hx + 18, hy + 40)], fill=h["line"], width=5)
    d.arc([hx - 22, hy + 40, hx + 22, hy + 72], 40, 140, fill=h["line"], width=5)                  # the tip
    d.arc([hx - 44, hy + 34, hx - 16, hy + 68], 130, 260, fill=INK, width=5)                       # the nostril wings
    d.arc([hx + 16, hy + 34, hx + 44, hy + 68], 280, 50, fill=INK, width=5)
    for x in (hx - 14, hx + 14):
        d.ellipse([x - 7, hy + 62, x + 7, hy + 70], fill=(70, 40, 32))
    # eyes and brows: surprised opens them, thinking furrows the brows
    wide = pose in ("surprised", "celebrate")
    lift = 16 if pose in ("surprised", "shrug", "celebrate") else 0
    frown = 10 if pose in ("think", "arms_crossed", "facepalm") else 0
    for k, (ex, ey) in enumerate(EYES):
        _host_eye(d, h, ex, ey, wide)
        _host_brow(d, h, ex, ey, 1 if k == 0 else -1, lift, frown)
    _gestures(d, pose, h["hoodie"], skin, h["hoodie_shade"])


def _paint_dc_host_mouth(d, shape):
    h = DC_HOST
    mx, my = H_MOUTH
    d.ellipse([mx - 50, my - 12, mx + 50, my + 36], fill=h["beard"])            # covers the closed lips, inside the beard
    for x, y, r in _host_stubble():                                             # the beard's specks, as in the pose
        if ((x - mx) / 50) ** 2 + ((y - (my + 12)) / 24) ** 2 <= 1:
            d.ellipse([x - r, y - r, x + r, y + r], fill=h["beard_dark"])
    dark, tongue, teeth = (62, 22, 26), (206, 98, 104), (250, 248, 240)
    if shape == "closed":
        _host_closed_lips(d, h)
    elif shape == "teeth":
        d.rounded_rectangle([mx - 32, my - 8, mx + 32, my + 14], radius=9, fill=teeth, outline=INK, width=5)
        d.line([(mx - 26, my + 3), (mx + 26, my + 3)], fill=(165, 165, 165), width=3)
        d.chord([mx - 28, my + 6, mx + 28, my + 28], 0, 180, fill=h["lips"], outline=INK, width=4)
    elif shape == "open":
        d.ellipse([mx - 28, my - 10, mx + 28, my + 30], fill=dark, outline=INK, width=5)
        d.chord([mx - 20, my + 10, mx + 20, my + 30], 180, 360, fill=tongue)
        d.chord([mx - 30, my + 16, mx + 30, my + 36], 0, 180, fill=h["lips"], outline=INK, width=4)
    elif shape == "wide":
        d.rounded_rectangle([mx - 40, my - 10, mx + 40, my + 32], radius=16, fill=dark, outline=INK, width=5)
        d.rectangle([mx - 30, my - 5, mx + 30, my + 5], fill=teeth)
        d.chord([mx - 18, my + 14, mx + 18, my + 32], 180, 360, fill=tongue)
        d.chord([mx - 38, my + 20, mx + 38, my + 40], 0, 180, fill=h["lips"], outline=INK, width=4)
    elif shape == "round":
        d.ellipse([mx - 20, my - 10, mx + 20, my + 26], fill=dark, outline=INK, width=5)
        d.arc([mx - 24, my - 14, mx + 24, my + 30], 20, 160, fill=h["lips"], width=6)
    elif shape == "oo":
        d.ellipse([mx - 18, my - 2, mx + 18, my + 26], fill=h["lips"], outline=INK, width=5)
        d.ellipse([mx - 7, my + 6, mx + 7, my + 18], fill=dark)
    elif shape == "fv":
        d.rectangle([mx - 26, my - 4, mx + 26, my + 8], fill=teeth, outline=INK, width=4)
        d.chord([mx - 30, my + 2, mx + 30, my + 22], 0, 180, fill=h["lips"], outline=INK, width=4)
    elif shape == "tongue":
        d.ellipse([mx - 28, my - 10, mx + 28, my + 30], fill=dark, outline=INK, width=5)
        d.ellipse([mx - 12, my - 6, mx + 12, my + 12], fill=tongue)
        d.chord([mx - 30, my + 16, mx + 30, my + 36], 0, 180, fill=h["lips"], outline=INK, width=4)
    elif shape == "smile":
        d.chord([mx - 42, my - 16, mx + 42, my + 28], 0, 180, fill=teeth, outline=INK, width=5)
        d.chord([mx - 40, my + 10, mx + 40, my + 34], 0, 180, fill=h["lips"], outline=INK, width=4)


def _paint_dc_host_blink(d):
    h = DC_HOST
    for ex, ey in EYES:
        d.ellipse([ex - 42, ey - 24, ex + 42, ey + 22], fill=h["skin"])
        d.arc([ex - 40, ey - 29, ex + 40, ey + 6], 200, 340, fill=h["crease"], width=6)
        d.arc([ex - 34, ey - 12, ex + 34, ey + 14], 15, 165, fill=INK, width=8)


def make_dc_host():
    _make_kit("dc-host", {"name": DC_HOST["name"], "about": DC_HOST["about"],
                          "drawn_by": "tools/avatars.py --dc-host, after our sticker avatar"},
              _paint_dc_host, _paint_dc_host_mouth, _paint_dc_host_blink)


# ---- the grandpa (a client for tests and samples)

GRANDPA = {"name": "Dadaji", "about": "A grandfather in his seventies who runs the family shop: white moustache, "
           "round glasses, cream kurta and a brown Nehru vest. Warm, curious, and a little doubtful about anything online.",
           "skin": (176, 120, 86), "shade": (150, 98, 68), "light": (198, 142, 106), "line": (112, 70, 50),
           "hair": (240, 238, 232), "kurta": (240, 232, 214), "vest": (112, 66, 42), "button": (214, 170, 70),
           "frame": (44, 32, 28)}
G_MOUTH = (540, 568)          # below the moustache


def _moustache(d, g):
    hx, hy = HEAD
    for side in (-1, 1):
        x0, x1 = (hx - 112, hx + 4) if side < 0 else (hx - 4, hx + 112)
        d.chord([x0, hy + 76, x1, hy + 170], 180, 360, fill=g["hair"], outline=INK, width=7)
        d.ellipse([hx + side * 110 - 21, hy + 84, hx + side * 110 + 21, hy + 126], fill=g["hair"], outline=INK, width=6)
        for k in range(3):                                                    # a few strands
            x = hx + side * (30 + 26 * k)
            d.line([(x, hy + 90), (x + side * 8, hy + 116)], fill=(200, 198, 190), width=3)
    d.line([(hx, hy + 84), (hx, hy + 112)], fill=(200, 198, 190), width=4)


def _paint_grandpa(d, pose):
    g = GRANDPA
    ol, skin = 9, g["skin"]
    hx, hy = HEAD
    # body: a cream kurta, a brown Nehru vest with gold buttons
    d.rounded_rectangle([250, 690, 830, 1180], radius=150, fill=g["kurta"], outline=INK, width=ol)
    for side in (-1, 1):
        inner, outer = (515, 262) if side < 0 else (565, 818)
        d.polygon([(outer, 760), (inner - side * 40, 700), (inner, 800), (inner, 1180), (outer + side * -12, 1180)],
                  fill=g["vest"], outline=INK)
        d.line([(inner - side * 40, 700), (inner, 800), (inner, 1180)], fill=INK, width=7)
    for y in (850, 925, 1000):
        d.ellipse([574, y - 12, 598, y + 12], fill=g["button"], outline=INK, width=4)
    d.rectangle([498, 560, 582, 700], fill=skin, outline=INK, width=ol)                       # the neck
    d.rounded_rectangle([484, 664, 596, 712], radius=16, fill=g["kurta"], outline=INK, width=7)  # band collar
    # head: white hair at the sides, the ears, a bald crown
    for side in (-1, 1):
        for cx, cy, r in ((168, -62, 44), (182, -12, 40), (160, -104, 34), (176, 34, 30)):
            d.ellipse([hx + side * cx - r, hy + cy - r, hx + side * cx + r, hy + cy + r], fill=g["hair"], outline=INK, width=6)
        ex0, ex1 = (hx - 214, hx - 150) if side < 0 else (hx + 150, hx + 214)
        d.ellipse([ex0, hy - 24, ex1, hy + 86], fill=skin, outline=INK, width=ol)
        d.arc([ex0 + 14, hy - 4, ex1 - 14, hy + 64], 90 if side < 0 else 270, 270 if side < 0 else 90, fill=g["line"], width=5)
    d.ellipse([hx - 170, hy - 190, hx + 170, hy + 216], fill=skin, outline=INK, width=ol)
    d.chord([hx - 170, hy - 190, hx + 170, hy + 216], 305, 55, fill=g["shade"])           # shade on one side
    d.arc([hx - 170, hy - 190, hx + 170, hy + 216], 0, 360, fill=INK, width=ol)
    d.ellipse([hx - 96, hy - 176, hx + 30, hy - 120], fill=g["light"])                     # light on the crown
    for k, y in enumerate((hy - 118, hy - 96, hy - 74)):                                    # forehead lines
        w = 92 - k * 10
        d.arc([hx - w, y - 18, hx + w, y + 18], 200, 340, fill=g["line"], width=5)
    # eyes behind round glasses, white bushy brows
    surprised = pose == "surprised"
    for k, (ex, ey) in enumerate(EYES):
        r = 30 if surprised else 25
        d.ellipse([ex - r, ey - r + 5, ex + r, ey + r - 3], fill=(255, 255, 255), outline=INK, width=5)
        d.ellipse([ex - 12, ey - 10, ex + 12, ey + 14], fill=INK)
        d.ellipse([ex - 4, ey - 5, ex + 3, ey + 2], fill=(255, 255, 255))
        d.arc([ex - 30, ey + 8, ex + 30, ey + 46], 20, 160, fill=g["line"], width=4)            # bags under the eyes
        out = -1 if k == 0 else 1
        d.line([(ex + out * 58, ey + 4), (ex + out * 82, ey - 6)], fill=g["line"], width=4)     # crow's feet
        d.line([(ex + out * 58, ey + 18), (ex + out * 84, ey + 20)], fill=g["line"], width=4)
        lift = 16 if surprised else 0
        brow = [(ex - 50, ey - 50 - lift + (6 if out < 0 else -2)), (ex, ey - 66 - lift), (ex + 50, ey - 50 - lift + (6 if out > 0 else -2)),
                (ex + 44, ey - 36 - lift), (ex, ey - 46 - lift), (ex - 44, ey - 36 - lift)]
        d.polygon(brow, fill=g["hair"], outline=INK)
        d.line(brow + [brow[0]], fill=INK, width=5, joint="curve")
    for ex, ey in EYES:
        d.ellipse([ex - 56, ey - 46, ex + 56, ey + 50], outline=g["frame"], width=9)
    (lx, ly), (rx_, ry_) = EYES
    d.line([(lx + 54, ly - 6), (rx_ - 54, ry_ - 6)], fill=g["frame"], width=8)
    d.line([(lx - 56, ly - 4), (hx - 158, hy - 4)], fill=g["frame"], width=7)
    d.line([(rx_ + 56, ry_ - 4), (hx + 158, hy - 4)], fill=g["frame"], width=7)
    # nose, smile lines, moustache, mouth
    d.arc([hx - 34, hy - 6, hx + 34, hy + 72], 300, 60, fill=INK, width=6)
    d.arc([hx - 40, hy + 40, hx - 8, hy + 68], 120, 260, fill=INK, width=5)
    d.arc([hx + 8, hy + 40, hx + 40, hy + 68], 280, 60, fill=INK, width=5)
    _moustache(d, g)
    mx, my = G_MOUTH
    d.arc([mx - 34, my - 22, mx + 34, my + 12], 25, 155, fill=INK, width=7)
    _gestures(d, pose, g["kurta"], skin, tuple(int(c * 0.92) for c in g["kurta"]))


def _paint_grandpa_mouth(d, shape):
    """The mouth under the moustache: a patch of skin over the closed mouth, then the shape."""
    g = GRANDPA
    mx, my = G_MOUTH
    d.ellipse([mx - 58, my - 36, mx + 58, my + 36], fill=g["skin"])        # stays under the moustache, inside the jaw
    dark, tongue, white = (60, 20, 24), (214, 96, 102), (250, 248, 240)
    if shape == "closed":
        d.arc([mx - 34, my - 22, mx + 34, my + 12], 25, 155, fill=INK, width=7)
    elif shape == "teeth":
        d.rounded_rectangle([mx - 32, my - 8, mx + 32, my + 18], radius=10, fill=white, outline=INK, width=6)
        d.line([(mx - 26, my + 5), (mx + 26, my + 5)], fill=(150, 150, 150), width=3)
    elif shape == "open":
        d.ellipse([mx - 28, my - 14, mx + 28, my + 32], fill=dark, outline=INK, width=6)
        d.chord([mx - 20, my + 8, mx + 20, my + 32], 180, 360, fill=tongue)
    elif shape == "wide":
        d.rounded_rectangle([mx - 42, my - 12, mx + 42, my + 34], radius=16, fill=dark, outline=INK, width=6)
        d.rectangle([mx - 32, my - 6, mx + 32, my + 4], fill=white)
    elif shape == "round":
        d.ellipse([mx - 20, my - 12, mx + 20, my + 28], fill=dark, outline=INK, width=6)
    elif shape == "oo":
        d.ellipse([mx - 18, my - 2, mx + 18, my + 28], fill=(150, 76, 70), outline=INK, width=6)
        d.ellipse([mx - 7, my + 6, mx + 7, my + 20], fill=dark)
    elif shape == "fv":
        d.rectangle([mx - 26, my - 2, mx + 26, my + 10], fill=white, outline=INK, width=4)
        d.arc([mx - 32, my - 4, mx + 32, my + 24], 20, 160, fill=INK, width=7)
    elif shape == "tongue":
        d.ellipse([mx - 28, my - 14, mx + 28, my + 32], fill=dark, outline=INK, width=6)
        d.ellipse([mx - 12, my - 8, mx + 12, my + 12], fill=tongue)
    elif shape == "smile":
        d.chord([mx - 44, my - 26, mx + 44, my + 28], 0, 180, fill=white, outline=INK, width=6)


def _paint_grandpa_blink(d):
    g = GRANDPA
    for ex, ey in EYES:
        d.ellipse([ex - 34, ey - 32, ex + 34, ey + 30], fill=g["skin"])
        d.arc([ex - 26, ey - 10, ex + 26, ey + 16], 20, 160, fill=INK, width=7)
        d.arc([ex - 30, ey + 8, ex + 30, ey + 46], 20, 160, fill=g["line"], width=4)


def make_grandpa():
    _make_kit("grandpa", {"name": GRANDPA["name"], "about": GRANDPA["about"], "drawn_by": "tools/avatars.py --grandpa"},
              _paint_grandpa, _paint_grandpa_mouth, _paint_grandpa_blink)


# ---- Meera: a founder in official dress (the client for our own reels: she looks like our viewers)

MEERA = {"name": "Meera", "about": "Meera, a founder in her thirties who runs a growing brand: black shoulder-length hair "
         "with a side parting, tucked behind one ear, a navy-blue suit over a crisp white shirt, small gold earrings. Sharp, busy and practical: "
         "she wants proof before she spends.",
         "skin": (212, 158, 122), "shade": (192, 138, 104), "line": (150, 98, 72), "crease": (190, 136, 104),
         "blush": (220, 148, 124), "hair": (26, 22, 24), "hair_light": (78, 70, 74), "lips": (176, 78, 90),
         "lips_dark": (142, 56, 68), "iris": (54, 34, 24), "blazer": (60, 90, 138), "blazer_shade": (46, 70, 112),
         "lapel": (54, 82, 128), "shirt": (248, 248, 246), "shirt_shade": (214, 220, 230), "gold": (226, 180, 64),
         "button": (36, 38, 46)}
M_MOUTH = (540, 530)
M_VOICE = {"voice_id": "EXAVITQu4vr4xnSDxMaL", "voice_name": "Sarah — Mature, Reassuring, Confident (default voice)",
           "about": "ElevenLabs default (premade) voice: usable on the free plan via the API. A Voice Library voice with "
                    "an Indian accent would suit her better on a paid plan."}


def _cuffed_arm(d, start, end, top):
    """A suit sleeve, as _arm draws it, with the white shirt cuff showing at the wrist."""
    _arm(d, start, end, top)
    sx, sy = start
    tx, ty = end
    if ty >= 1000:                                        # the hand is below the picture: no cuff to show
        return
    mx, my = (sx + tx) / 2 + (40 if tx > sx else -40), (sy + ty) / 2 + 40
    length = math.hypot(tx - mx, ty - my) or 1
    ux, uy = (tx - mx) / length, (ty - my) / length
    a, b = (tx - ux * 80, ty - uy * 80), (tx - ux * 44, ty - uy * 44)
    d.line([a, b], fill=INK, width=80)
    d.line([a, b], fill=MEERA["shirt"], width=62)


def _meera_eye(d, m, ex, ey, outward, wide=False):
    """An almond eye, lined, with a small flick at the outer corner. outward: -1 when the outer corner is on the left."""
    top, bot = (19, 15) if wide else (14, 11)
    d.arc([ex - 40, ey - top - 16, ex + 40, ey + 6], 200, 340, fill=m["crease"], width=5)          # the lid's crease
    pts = [(ex - 36, ey + 3), (ex - 22, ey - top + 4), (ex, ey - top), (ex + 22, ey - top + 4), (ex + 36, ey + 2),
           (ex + 20, ey + bot), (ex, ey + bot + 2), (ex - 20, ey + bot)]
    d.polygon(pts, fill=(250, 246, 240), outline=INK, width=4)
    r = 14 if wide else 13
    d.ellipse([ex - r, ey - r + 3, ex + r, ey + r + 3], fill=m["iris"], outline=INK, width=3)
    d.ellipse([ex - 6, ey - 2, ex + 6, ey + 10], fill=(14, 10, 8))
    d.ellipse([ex - 8, ey - 6, ex - 2, ey], fill=(255, 255, 255))
    d.line(pts[:5], fill=INK, width=11, joint="curve")                       # the upper lid, lined
    ox = ex + outward * 36
    d.polygon([(ox, ey + 4), (ox + outward * 18, ey - 12), (ox - outward * 6, ey - 4)], fill=INK)   # the flick
    for k, t in enumerate((0.55, 0.75)):                                     # two lashes towards the outer corner
        x = ex + outward * 36 * t
        y = ey - top * (1 - t * t) + 2
        d.line([(x, y), (x + outward * 8, y - 12)], fill=INK, width=5)


def _meera_brow(d, m, ex, ey, inward, lift=0, frown=0):
    """Groomed, arched brows. inward: +1 when the inner end is to the right (the left eye), -1 for the right."""
    pts = [(ex + inward * 40, ey - 45 - lift + frown), (ex + inward * 4, ey - 55 - lift), (ex - inward * 22, ey - 56 - lift),
           (ex - inward * 46, ey - 44 - lift)]
    d.line(pts, fill=m["hair"], width=12, joint="curve")
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=m["hair"])


def _meera_closed_lips(d, m):
    mx, my = M_MOUTH
    d.chord([mx - 30, my - 10, mx + 30, my + 18], 0, 180, fill=m["lips"], outline=INK, width=4)      # the lower lip
    upper = [(mx - 34, my + 1), (mx - 20, my - 10), (mx - 7, my - 9), (mx, my - 5), (mx + 7, my - 9), (mx + 20, my - 10),
             (mx + 34, my + 1)]
    d.polygon(upper, fill=m["lips_dark"])                                                           # the upper lip
    d.line(upper, fill=INK, width=4, joint="curve")
    d.line([(mx - 34, my + 1), (mx - 12, my + 3), (mx, my + 2), (mx + 12, my + 3), (mx + 34, my + 1)], fill=INK, width=5,
           joint="curve")                                                                           # where they meet


def _meera_hair_back(d, m):
    """The long bob behind her head, falling to the nape: its outline is the hair's shape."""
    hx, hy = HEAD
    back = [(hx - 168, hy + 252), (hx - 192, hy + 160), (hx - 202, hy + 40), (hx - 196, hy - 80), (hx - 176, hy - 172),
            (hx - 134, hy - 240), (hx - 62, hy - 280), (hx + 20, hy - 286), (hx + 98, hy - 266), (hx + 154, hy - 218),
            (hx + 190, hy - 134), (hx + 204, hy - 20), (hx + 198, hy + 100), (hx + 184, hy + 196), (hx + 166, hy + 252),
            (hx + 120, hy + 266), (hx, hy + 270), (hx - 120, hy + 266)]
    d.polygon(_spline(back), fill=m["hair"], outline=INK, width=8)


def _meera_hair_front(d, m):
    """The fringe swept from a parting on her right (our left) across the forehead, and the hair framing her face."""
    hx, hy = HEAD
    front = [(hx - 146, hy + 210), (hx - 180, hy + 70), (hx - 186, hy - 70), (hx - 162, hy - 182), (hx - 108, hy - 250),
             (hx - 30, hy - 276), (hx + 60, hy - 268), (hx + 136, hy - 226), (hx + 184, hy - 142), (hx + 198, hy - 52),
             (hx + 184, hy - 14), (hx + 150, hy - 22), (hx + 130, hy - 52), (hx + 92, hy - 96), (hx + 36, hy - 128), (hx - 24, hy - 150), (hx - 70, hy - 168), (hx - 104, hy - 150),
             (hx - 126, hy - 104), (hx - 134, hy - 10), (hx - 128, hy + 120)]
    shape = _spline(front)
    d.polygon(shape, fill=m["hair"])
    d.line(shape + shape[:2], fill=INK, width=7, joint="curve")
    for pts in (((hx - 60, hy - 256), (hx + 10, hy - 230), (hx + 90, hy - 190), (hx + 150, hy - 120)),     # the sweep
                ((hx - 120, hy - 214), (hx - 50, hy - 214), (hx + 40, hy - 170), (hx + 110, hy - 100)),
                ((hx + 150, hy - 160), (hx + 178, hy - 100), (hx + 184, hy - 50)),
                ((hx - 154, hy - 120), (hx - 162, hy - 20), (hx - 156, hy + 100))):
        d.line(_spline(list(pts), closed=False), fill=m["hair_light"], width=6, joint="curve")
    d.line(_spline([(hx - 58, hy - 272), (hx - 66, hy - 220), (hx - 72, hy - 170)], closed=False), fill=INK, width=4,
           joint="curve")                                                                           # the parting


def _meera_suit(d, m):
    """A navy-blue blazer with notched lapels and one button, over a white shirt with an open collar."""
    ol = 9
    d.rounded_rectangle([250, 690, 830, 1180], radius=150, fill=m["blazer"], outline=INK, width=ol)
    d.polygon([(700, 720), (812, 820), (826, 1180), (700, 1180)], fill=m["blazer_shade"])          # shade on one side
    d.rounded_rectangle([250, 690, 830, 1180], radius=150, outline=INK, width=ol)
    d.polygon([(478, 692), (602, 692), (552, 946), (528, 946)], fill=m["shirt"], outline=INK, width=6)   # the shirt
    d.polygon([(512, 698), (568, 698), (540, 770)], fill=m["skin"])                                # the open neck
    for sgn in (-1, 1):
        def x(v):
            return 540 + sgn * (v - 540)
        collar = [(x(474), 690), (x(530), 702), (x(540), 774), (x(492), 760)]
        d.polygon(collar, fill=m["shirt"], outline=INK, width=5)
        d.line([(x(500), 744), (x(528), 712)], fill=m["shirt_shade"], width=4)
        lapel = [(x(478), 692), (x(430), 700), (x(420), 742), (x(398), 752), (x(428), 790), (x(534), 952), (x(546), 940)]
        d.polygon(lapel, fill=m["lapel"], outline=INK, width=6)
        d.line([(x(424), 760), (x(522), 920)], fill=m["blazer_shade"], width=4)                    # the lapel's roll
    d.ellipse([528, 972, 552, 996], fill=m["button"], outline=INK, width=4)                       # one button
    d.line([(640, 860), (730, 850)], fill=INK, width=6)                                            # the breast pocket
    d.polygon([(652, 858), (668, 832), (690, 856)], fill=m["shirt"], outline=INK, width=4)        # its pocket square


def _paint_meera(d, pose):
    m = MEERA
    hx, hy = HEAD
    skin = m["skin"]
    _meera_hair_back(d, m)
    _meera_suit(d, m)
    d.rectangle([502, 560, 578, 700], fill=skin, outline=INK, width=9)                             # the neck
    d.chord([502, 520, 578, 620], 0, 180, fill=m["shade"])                                         # shade under the jaw
    d.line([(502, 560), (502, 700)], fill=INK, width=9)
    d.line([(578, 560), (578, 700)], fill=INK, width=9)
    for side in (-1, 1):                                                                           # ears, gold studs
        x0, x1 = (hx - 190, hx - 140) if side < 0 else (hx + 140, hx + 190)
        d.ellipse([x0, hy - 10, x1, hy + 90], fill=skin, outline=INK, width=8)
        d.arc([x0 + 12, hy + 8, x1 - 12, hy + 70], 90 if side < 0 else 270, 270 if side < 0 else 90, fill=m["line"], width=5)
        cx = hx + side * 160
        d.ellipse([cx - 11, hy + 78, cx + 11, hy + 100], fill=m["gold"], outline=INK, width=4)
    face = [hx - 150, hy - 186, hx + 150, hy + 206]
    d.ellipse(face, fill=skin, outline=INK, width=9)
    d.chord(face, 312, 48, fill=m["shade"])                                                       # shade on one side
    d.arc(face, 0, 360, fill=INK, width=9)
    for sgn in (-1, 1):                                                                            # a little blush
        d.ellipse([hx + sgn * 92 - 30, hy + 54, hx + sgn * 92 + 30, hy + 82], fill=m["blush"])
    _meera_hair_front(d, m)
    # the nose: small and straight
    d.line([(hx + 6, hy - 24), (hx + 12, hy + 42)], fill=m["line"], width=5)
    d.arc([hx - 18, hy + 42, hx + 18, hy + 68], 40, 140, fill=m["line"], width=5)
    d.arc([hx - 36, hy + 38, hx - 12, hy + 66], 130, 260, fill=INK, width=4)
    d.arc([hx + 12, hy + 38, hx + 36, hy + 66], 280, 50, fill=INK, width=4)
    _meera_closed_lips(d, m)
    wide = pose in ("surprised", "celebrate")
    lift = 16 if pose in ("surprised", "shrug", "celebrate") else 0
    frown = 10 if pose in ("think", "arms_crossed", "facepalm") else 0
    for k, (ex, ey) in enumerate(EYES):
        _meera_eye(d, m, ex, ey, -1 if k == 0 else 1, wide)
        _meera_brow(d, m, ex, ey, 1 if k == 0 else -1, lift, frown)
    _gestures(d, pose, m["blazer"], skin, m["blazer_shade"], parts={"arm": _cuffed_arm})


def _paint_meera_mouth(d, shape):
    m = MEERA
    mx, my = M_MOUTH
    d.ellipse([mx - 46, my - 20, mx + 46, my + 34], fill=m["skin"])          # covers the closed lips
    dark, tongue, teeth = (66, 20, 28), (206, 98, 104), (250, 248, 240)
    if shape == "closed":
        _meera_closed_lips(d, m)
    elif shape == "teeth":
        d.rounded_rectangle([mx - 30, my - 9, mx + 30, my + 12], radius=9, fill=teeth, outline=INK, width=5)
        d.line([(mx - 24, my + 2), (mx + 24, my + 2)], fill=(165, 165, 165), width=3)
        d.chord([mx - 32, my - 18, mx + 32, my - 2], 180, 360, fill=m["lips_dark"], outline=INK, width=4)
        d.chord([mx - 28, my + 4, mx + 28, my + 24], 0, 180, fill=m["lips"], outline=INK, width=4)
    elif shape == "open":
        d.ellipse([mx - 28, my - 12, mx + 28, my + 28], fill=dark, outline=INK, width=5)
        d.chord([mx - 20, my + 8, mx + 20, my + 28], 180, 360, fill=tongue)
        d.chord([mx - 32, my - 20, mx + 32, my - 2], 180, 360, fill=m["lips_dark"], outline=INK, width=4)
        d.chord([mx - 30, my + 14, mx + 30, my + 34], 0, 180, fill=m["lips"], outline=INK, width=4)
    elif shape == "wide":
        d.rounded_rectangle([mx - 40, my - 12, mx + 40, my + 30], radius=16, fill=dark, outline=INK, width=5)
        d.rectangle([mx - 30, my - 7, mx + 30, my + 3], fill=teeth)
        d.chord([mx - 18, my + 12, mx + 18, my + 30], 180, 360, fill=tongue)
        d.chord([mx - 42, my - 22, mx + 42, my - 4], 180, 360, fill=m["lips_dark"], outline=INK, width=4)
        d.chord([mx - 38, my + 18, mx + 38, my + 38], 0, 180, fill=m["lips"], outline=INK, width=4)
    elif shape == "round":
        d.ellipse([mx - 22, my - 14, mx + 22, my + 26], fill=m["lips"], outline=INK, width=5)
        d.ellipse([mx - 12, my - 4, mx + 12, my + 16], fill=dark)
    elif shape == "oo":
        d.ellipse([mx - 18, my - 4, mx + 18, my + 24], fill=m["lips"], outline=INK, width=5)
        d.ellipse([mx - 7, my + 4, mx + 7, my + 16], fill=dark)
    elif shape == "fv":
        d.chord([mx - 32, my - 16, mx + 32, my + 2], 180, 360, fill=m["lips_dark"], outline=INK, width=4)
        d.rectangle([mx - 24, my - 2, mx + 24, my + 8], fill=teeth, outline=INK, width=4)
        d.chord([mx - 28, my + 2, mx + 28, my + 22], 0, 180, fill=m["lips"], outline=INK, width=4)
    elif shape == "tongue":
        d.ellipse([mx - 28, my - 12, mx + 28, my + 28], fill=dark, outline=INK, width=5)
        d.ellipse([mx - 12, my - 6, mx + 12, my + 12], fill=tongue)
        d.chord([mx - 30, my + 14, mx + 30, my + 34], 0, 180, fill=m["lips"], outline=INK, width=4)
    elif shape == "smile":
        d.chord([mx - 42, my - 18, mx + 42, my + 26], 0, 180, fill=teeth, outline=INK, width=5)
        d.chord([mx - 40, my + 8, mx + 40, my + 32], 0, 180, fill=m["lips"], outline=INK, width=4)
        d.arc([mx - 44, my - 26, mx + 44, my - 6], 200, 340, fill=m["lips_dark"], width=6)


def _paint_meera_blink(d):
    m = MEERA
    for k, (ex, ey) in enumerate(EYES):
        outward = -1 if k == 0 else 1
        d.ellipse([ex - 46, ey - 26, ex + 46, ey + 24], fill=m["skin"])
        d.arc([ex - 40, ey - 31, ex + 40, ey + 6], 200, 340, fill=m["crease"], width=5)
        d.arc([ex - 36, ey - 14, ex + 36, ey + 14], 15, 165, fill=INK, width=9)
        ox = ex + outward * 34
        d.line([(ox, ey + 4), (ox + outward * 12, ey + 14)], fill=INK, width=6)          # lashes, eyes shut
        d.line([(ex + outward * 18, ey + 12), (ex + outward * 24, ey + 24)], fill=INK, width=5)


def _paint_meera_front(d, pose):
    """Her arms again, for the poses where one crosses her face (facepalm): they stay over the mouths and the blink."""
    _gestures(d, pose, MEERA["blazer"], MEERA["skin"], MEERA["blazer_shade"], parts={"arm": _cuffed_arm})


def make_meera():
    _make_kit("founder", {"name": MEERA["name"], "about": MEERA["about"], "drawn_by": "tools/avatars.py --founder"},
              _paint_meera, _paint_meera_mouth, _paint_meera_blink, _paint_meera_front)
    p = AVATARS / "founder" / "avatar.json"
    kit = dc.load_json(p)
    if not kit.get("voice"):                                 # her voice, unless a person has chosen another
        kit["voice"] = dict(M_VOICE)
        dc.save_json(p, kit)


# ---- Chatur: Digital Corvids' clever crow, the host of the Corvid style
# An Indian house crow (the kauwa), side-on and facing left, towards the cards and the client: the long beak opens for
# lip sync, the near wing is his arm and its flight feathers his fingers. Shapes are smooth curves through points.

CHATUR = {"name": "Chatur", "about": "Chatur, Digital Corvids' clever crow and the host of our own style: an Indian house "
          "crow, glossy black with the grey shawl round his neck, drawn side-on. Sharp, playful and patient; explains "
          "marketing like the thirsty crow solved the pot, one smart pebble at a time.",
          "plume": (21, 22, 30), "plume_mid": (35, 37, 52), "gloss": (42, 46, 70), "wing": (46, 50, 78), "flight": (36, 40, 64),
          "wing_far": (28, 30, 44), "sheen": (84, 96, 166), "glint": (140, 152, 218), "rim": (86, 98, 158),
          "shawl": (134, 138, 150), "shawl_light": (172, 176, 188), "shawl_dark": (100, 104, 118),
          "beak": (56, 59, 72), "beak_light": (142, 150, 172), "beak_dark": (36, 38, 48),
          "mouth": (150, 50, 66), "tongue": (228, 122, 138),
          "eye": (247, 247, 241), "iris": (60, 38, 28), "pupil": (8, 8, 10), "lemon": (245, 238, 48),
          "paper": (250, 248, 240)}

C_EYE = (432, 280)
C_HINGE = (372, 346)            # the corner of the beak: the lower half turns about it to open
C_SHOULDER = (650, 664)         # where the near wing leaves the body
C_SHOULDER_FAR = (712, 620)
# the outline of head and body together (the beak is drawn over its front)
C_BODY = [(350, 252), (382, 200), (444, 168), (522, 160), (598, 178), (652, 224), (680, 290), (690, 360),
          (700, 428), (728, 490), (786, 556), (852, 640), (898, 744), (924, 860), (930, 970), (906, 1080),
          (870, 1160), (520, 1160), (452, 1080), (402, 980), (376, 860), (374, 740), (388, 640), (396, 580),
          (382, 510), (362, 450), (346, 404), (338, 330)]
C_BACK = C_BODY[1:13]           # the lit edge, from the forehead over the head and down the back
C_HACKLES = [(352, 428, 0.8), (364, 470, 1.0), (378, 516, 0.85)]     # the shaggy feathers of the throat
# the grey shawl of the house crow: the back of the head, the nape, the neck and the top of the breast
C_SHAWL_BACK = [(598, 178), (652, 224), (680, 290), (690, 360), (700, 428), (728, 490), (786, 556), (816, 596)]
C_SHAWL_LOW = [(816, 596), (744, 652), (642, 692), (540, 702), (452, 694), (388, 678)]
C_SHAWL_EDGE = [(388, 678), (392, 640), (406, 600), (432, 556), (466, 502), (500, 446), (530, 386), (556, 318),
                (578, 248), (598, 178)]
# the beak, closed: the upper half (the ridge to the hooked tip, then the cutting edge back to the corner), the lower
C_UPPER = [(378, 256), (334, 256), (284, 264), (230, 282), (180, 310), (140, 342), (114, 372), (106, 392), (122, 394),
           (176, 372), (242, 358), (308, 350), (378, 346)]
C_LOWER = [(378, 346), (308, 350), (242, 358), (176, 372), (134, 387), (140, 398), (188, 400), (252, 398), (316, 400),
           (378, 404)]
C_UPPER_EDGE = [(372, 346), (308, 350), (242, 358), (176, 372), (128, 389)]     # the cutting edges, corner → tip
C_LOWER_EDGE = [(372, 346), (308, 350), (242, 358), (176, 372), (136, 389)]
C_CHEEK = [(366, 338), (404, 334), (418, 372), (402, 406), (366, 410)]          # covers the root of the lower half


def _spline(pts, closed=True, n=10):
    """A smooth curve through the points (Catmull-Rom), as a list of points."""
    P = list(pts)
    P = ([P[-1]] + P + [P[0], P[1]]) if closed else ([P[0]] + P + [P[-1]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(tuple(0.5 * (2 * p1[j] + (p2[j] - p0[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t
                                    + (3 * p1[j] - p0[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in (0, 1)))
    if not closed:
        out.append(P[-2])
    return out


def _resample(line, step):
    """Points every step pixels along a polyline."""
    acc = [0.0]
    for a, b in zip(line, line[1:]):
        acc.append(acc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    n = max(2, int(acc[-1] / step) + 1)
    out, j = [], 0
    for k in range(n):
        s = acc[-1] * k / (n - 1)
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        t = (s - acc[j]) / max(1e-9, acc[j + 1] - acc[j])
        a, b = line[j], line[j + 1]
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _frill(pts, amp, every, side=1, pointed=False):
    """A curve through pts with feather tips along it: round scallops, or pointed ones, on one side."""
    line = _resample(_spline(pts, closed=False, n=16), every / 8)
    out = []
    for k, p in enumerate(line):
        a, b = line[max(0, k - 1)], line[min(len(line) - 1, k + 1)]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        nx, ny = -(b[1] - a[1]) / L * side, (b[0] - a[0]) / L * side
        ph = (k % 8) / 8
        off = amp * ((1 - abs(2 * ph - 1)) if pointed else math.sin(math.pi * ph))
        out.append((p[0] + nx * off, p[1] + ny * off))
    return out


def _blob(d, pts, fill, outline=None, width=0, smooth=True):
    poly = _spline(pts) if smooth else list(pts)
    d.polygon(poly, fill=fill)
    if outline:
        d.line(poly + poly[:2], fill=outline, width=width, joint="curve")
    return poly


def _stroke(d, pts, fill, width):
    d.line(_spline(pts, closed=False, n=8), fill=fill, width=width, joint="curve")


def _taper(d, pts, fill, width):
    """A highlight that is widest in the middle and thins to nothing at both ends."""
    line = _resample(_spline(pts, closed=False, n=10), 6)
    for k, (a, b) in enumerate(zip(line, line[1:])):
        w = max(1.5, width * math.sin(math.pi * (k + 0.5) / (len(line) - 1)))
        d.line([a, b], fill=fill, width=w)
        d.ellipse([b[0] - w / 2, b[1] - w / 2, b[0] + w / 2, b[1] + w / 2], fill=fill)


def _rot(p, about, deg):
    """p turned about a point; positive degrees turn a left-pointing beak downwards."""
    a = math.radians(deg)
    x, y = p[0] - about[0], p[1] - about[1]
    return about[0] + x * math.cos(a) + y * math.sin(a), about[1] - x * math.sin(a) + y * math.cos(a)


def _arc_pts(cx, cy, rx, ry, a0, a1, step=4):
    """Points along an ellipse from angle a0 to a1 (degrees, clockwise from 3 o'clock, as Pillow counts them)."""
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * k / (n - 1))),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * k / (n - 1)))) for k in range(n)]


def _polar(origin, deg, length):
    a = math.radians(deg)
    return origin[0] + math.cos(a) * length, origin[1] + math.sin(a) * length


def _feather(d, base, tip, width, fill, edge=None, outline=INK, ow=5, bend=0.0, shaft=True):
    """One feather from base to tip: slim at the base, widest past the middle, a rounded tip. bend curves it sideways."""
    bx, by = base
    L = max(1.0, math.hypot(tip[0] - bx, tip[1] - by))
    ux, uy = (tip[0] - bx) / L, (tip[1] - by) / L
    nx, ny = -uy, ux

    def at(s, w):
        bow = bend * L * 4 * s * (1 - s)
        return bx + ux * L * s + nx * (w * width / 2 + bow), by + uy * L * s + ny * (w * width / 2 + bow)
    prof = [(0.0, 0.34), (0.3, 0.86), (0.62, 1.0), (0.84, 0.88), (0.95, 0.56), (1.0, 0.0)]
    pts = [at(s, w) for s, w in prof] + [at(s, -w) for s, w in reversed(prof[:-1])]
    poly = _spline(pts, n=6)
    d.polygon(poly, fill=fill)
    if edge:
        d.line(_spline([at(s, 0.6 * w) for s, w in prof[1:5]], closed=False, n=6), fill=edge, width=4, joint="curve")
    if shaft:
        d.line([at(0.06, 0), at(0.5, -0.04), at(0.86, 0)], fill=CHATUR["sheen"], width=3, joint="curve")
    if outline:
        d.line(poly + poly[:2], fill=outline, width=ow, joint="curve")


def _scallops(d, pts, colour, size=30, width=4, every=34):
    """A row of feather tips: small arcs along a line."""
    for p in _resample(_spline(pts, closed=False, n=12), every):
        d.arc([p[0] - size / 2, p[1] - size / 2, p[0] + size / 2, p[1] + size / 2], 20, 160, fill=colour, width=width)


# ---- the wings

def _folded_wing(d):
    """The near wing folded along his back: the primaries to the tip, the secondaries, then rows of coverts."""
    c = CHATUR
    for base, tip in (((800, 830), (966, 1100)), ((786, 836), (944, 1082)), ((770, 840), (920, 1060)),
                      ((752, 840), (894, 1036))):
        _feather(d, base, tip, 76, c["wing"], edge=c["sheen"], bend=-0.03)
    for base, tip in (((700, 760), (884, 1000)), ((676, 748), (850, 968)), ((650, 736), (814, 936)),
                      ((624, 724), (778, 904)), ((598, 712), (742, 872))):
        _feather(d, base, tip, 84, c["wing"], edge=c["sheen"], bend=-0.04)
    top = [(556, 694), (590, 630), (660, 590), (744, 576), (812, 616), (862, 690), (888, 782)]
    bottom = _frill([(888, 782), (842, 816), (770, 798), (690, 770), (614, 748), (566, 728)], 16, 46, side=-1)
    poly = _spline(top, closed=False, n=10) + bottom
    d.polygon(poly, fill=c["wing"])
    d.line(poly + poly[:1], fill=INK, width=5, joint="curve")
    for row in ([(590, 668), (650, 650), (720, 656), (790, 690), (840, 740)],
                [(614, 712), (680, 712), (746, 730), (806, 768)]):
        _scallops(d, row, c["sheen"], size=42, width=5, every=42)
    _taper(d, top[:5], c["glint"], 7)                                            # the lit leading edge


def _raised_wing(d, wrist, fingers, far=False, hand_only=False, shoulder=None, lead=(-0.6, -0.8), fold=1.0, size=1.0):
    """A crow's wing lifted like an arm, its upper side towards us: the slotted primaries fanned from the wrist like
    fingers, long secondaries along the trailing edge, a row of greater coverts over their roots and the small coverts
    along the lit leading edge. fingers: [(angle, length, width)], back to front, in degrees (0 = right, 90 = down).
    lead: the way the leading edge faces. fold: 1 for a spread wing, less for a half-folded one."""
    c = CHATUR
    fill, flight, edge = (c["wing_far"], c["wing_far"], None) if far else (c["wing"], c["flight"], c["sheen"])
    sx, sy = shoulder or (C_SHOULDER_FAR if far else C_SHOULDER)
    wx, wy = wrist
    L = max(1.0, math.hypot(wx - sx, wy - sy))
    ux, uy = (wx - sx) / L, (wy - sy) / L
    nx, ny, side = -uy, ux, 1
    if nx * lead[0] + ny * lead[1] < 0:
        nx, ny, side = -nx, -ny, -1
    tx, ty = -nx * 0.9 - ux * 0.42, -ny * 0.9 - uy * 0.42           # the trailing edge, swept back towards the body
    tl = math.hypot(tx, ty)
    tx, ty = tx / tl, ty / tl
    for ang, length, width in fingers:                                 # the primaries: his fingers
        _feather(d, _polar(wrist, ang, 6), _polar(wrist, ang, length), width, flight, edge=edge, bend=0.03)
    mean = math.degrees(math.atan2(sum(math.sin(math.radians(f[0])) for f in fingers),
                                   sum(math.cos(math.radians(f[0])) for f in fingers))) if fingers else 0
    if not hand_only:
        for k in range(8):                                             # the secondaries; the inner ones lie on top
            t = 0.98 - 0.11 * k
            bx, by = sx + (wx - sx) * t - nx * 8, sy + (wy - sy) * t - ny * 8
            length = (170 + 60 * math.sin(math.pi * min(1.0, t + 0.12))) * fold * size
            _feather(d, (bx, by), (bx + tx * length, by + ty * length), 86 * size, flight, edge=edge, bend=0.05)
        for k in range(6):                                             # the greater coverts over their roots
            t = 0.93 - 0.14 * k
            bx, by = sx + (wx - sx) * t + nx * 6, sy + (wy - sy) * t + ny * 6
            cl = 104 * max(fold, 0.7) * size
            _feather(d, (bx, by), (bx + tx * cl, by + ty * cl), 74 * size, fill, edge=edge, bend=0.03, shaft=False)
        mx, my = (sx + wx) / 2 + nx * 10, (sy + wy) / 2 + ny * 10
        s = size
        front = [(sx - ux * 40 * s + nx * 6, sy - uy * 40 * s + ny * 6), (sx + nx * 44 * s, sy + ny * 44 * s),
                 (mx + nx * 46 * s, my + ny * 46 * s), (wx + nx * 34 * s, wy + ny * 34 * s),
                 (wx + ux * 22 * s, wy + uy * 22 * s)]
        back = _frill([(wx - nx * 22 * s + ux * 6, wy - ny * 22 * s + uy * 6), (mx - nx * 26 * s, my - ny * 26 * s),
                       (sx - nx * 32 * s, sy - ny * 32 * s), (sx - ux * 40 * s, sy - uy * 40 * s)], 11, 36, side=side)
        poly = _spline(front, closed=False, n=10) + back
        d.polygon(poly, fill=fill)
        d.line(poly + poly[:1], fill=INK, width=5, joint="curve")
        if not far:
            _scallops(d, [(sx + nx * 12, sy + ny * 12), (mx + nx * 12, my + ny * 12), (wx + nx * 8, wy + ny * 8)],
                      c["sheen"], size=34, width=4, every=36)
            _taper(d, [(sx + nx * 36, sy + ny * 36), (mx + nx * 40, my + ny * 40), (wx + nx * 28, wy + ny * 28)],
                   c["glint"], 7)
    for off in (-26, 0, 26):                                           # the coverts over the roots of the fingers
        _feather(d, _polar(wrist, mean + 180, 22 * size), _polar(wrist, mean + off, 76 * size), 56 * size, fill,
                 edge=edge, shaft=False)


def _fan(center, n, spread, length, width=50):
    """n feathers fanned evenly across spread degrees, back to front."""
    if n == 1:
        return [(center, length, width)]
    return [(center - spread / 2 + spread * k / (n - 1), length, width) for k in range(n)]


def _count(n):
    """n feathers up like fingers, the rest folded down into the palm."""
    up = [(264 - 9 * (n - 1) + 18 * k, 236 - (16 if k in (0, n - 1) and n > 2 else 0), 50) for k in range(n)]
    folded = [(310 + 16 * k, 92, 50) for k in range(5 - n)]
    return folded + up


def _pointing(direction):
    """A wingtip pointing: the leading feather out longest, like a finger."""
    return [(direction - 24, 150, 50), (direction - 15, 176, 50), (direction - 6, 200, 50), (direction + 3, 290, 52)]


# the wings and the things held, pose by pose. He faces left, so left is in front of him.
C_POSES = {
    "talk": {},
    "point": {"near": ((384, 612), _pointing(202))},
    "point_left": {"near": ((372, 690), _pointing(180))},
    "point_down": {"near": ((420, 776), _pointing(128))},
    "open_hand": {"near": ((380, 730), _fan(206, 5, 72, 180))},
    "shrug": {"near": ((370, 730), _fan(204, 5, 66, 176)), "far": ((872, 560), _fan(306, 4, 56, 180)), "lift": 12},
    "think": {"near": ((456, 540), _fan(246, 4, 26, 132, 46)), "fold": 0.5, "look": (-4, -9), "frown": 8},
    "one": {"near": ((292, 740), _count(1))},
    "two": {"near": ((292, 740), _count(2))},
    "three": {"near": ((292, 740), _count(3))},
    "four": {"near": ((292, 740), _count(4))},
    "five": {"near": ((292, 740), _count(5))},
    "phone": {"near": ((360, 772), [(232, 92, 48), (250, 100, 48), (268, 96, 48)]), "prop": "phone", "look": (-6, 9),
              "lid": 0.32},
    "ok": {"near": ((306, 712), [(250, 190, 48), (266, 206, 48), (282, 190, 48)]), "prop": "ok"},
    "thumbs_up": {"near": ((314, 724), [(194, 84, 52), (212, 88, 52), (230, 84, 52), (268, 186, 58)]),
                  "prop": "sparkle", "lift": 6},
    "wave": {"near": ((292, 640), _fan(244, 5, 80, 200)), "prop": "wave", "lift": 6},
    "clap": {"near": ((404, 730), _fan(214, 4, 30, 166)), "far_front": ((372, 708), _fan(236, 3, 26, 148)),
             "prop": "clap", "lift": 6},
    "celebrate": {"near": ((632, 334), _fan(274, 5, 100, 210)), "far": ((812, 392), _fan(296, 5, 88, 200)),
                  "prop": "sparkle_high", "wide": True, "crest": True, "lift": 12},
    "facepalm": {"near": ((566, 476), _fan(238, 4, 30, 250, 56)), "fold": 0.55, "frown": 10},
    "arms_crossed": {"near": ((432, 744), _fan(334, 4, 24, 160)), "far_front": ((404, 660), _fan(28, 3, 22, 144)),
                     "lid": 0.44, "frown": 8},
    "surprised": {"near": ((388, 590), _fan(238, 5, 84, 180)), "far": ((836, 486), _fan(298, 4, 66, 180)),
                  "wide": True, "crest": True, "lift": 14},
    "write": {"near": ((410, 690), [(196, 92, 48), (214, 100, 48), (232, 92, 48)]), "prop": "write", "look": (-6, 9),
              "lid": 0.32},
    "listen": {"near": ((644, 474), _fan(224, 4, 30, 160, 48)), "fold": 0.5, "look": (-8, 0), "lid": 0.2},
    "pebble": {"near": ((306, 712), [(234, 132, 48), (250, 150, 48), (266, 136, 48)]), "prop": "pebble", "look": (-6, 4),
               "lift": 6},
    "drink": {"happy": True, "lift": 8},
}


def _pebble(d, cx, cy, s=1.0):
    """A pebble from the thirsty crow's story: a smooth grey stone, as the reel's pot shows them."""
    pts = [(cx + 42 * s * math.cos(a) * (1 + 0.05 * math.sin(3 * a)), cy + 30 * s * math.sin(a) * (1 + 0.07 * math.cos(2 * a)))
           for a in [k * math.pi / 24 for k in range(48)]]
    d.polygon(pts, fill=(150, 152, 162))
    d.line(pts + pts[:1], fill=(88, 90, 102), width=5)
    d.arc([cx - 30 * s, cy - 22 * s, cx + 8 * s, cy + 8 * s], 200, 290, fill=(214, 216, 224), width=5)


def _happy_eye(d, at=C_EYE, size=1.0):
    """An eye shut in happiness, curved up: the way he drinks from the full pot."""
    c = CHATUR
    ex, ey = at
    k = size
    d.ellipse([ex - 44 * k, ey - 46 * k, ex + 44 * k, ey + 46 * k], fill=c["plume_mid"])
    d.arc([ex - 34 * k, ey - 8 * k, ex + 34 * k, ey + 40 * k], 200, 340, fill=INK, width=9)
    d.arc([ex - 28 * k, ey - 18 * k, ex + 28 * k, ey + 26 * k], 215, 325, fill=c["sheen"], width=4)


def _props(d, pose):
    c = CHATUR
    prop = C_POSES[pose].get("prop")
    if prop == "pebble":
        _pebble(d, 250, 584, 1.15)
        _feather(d, (306, 712), (276, 612), 46, c["wing"], edge=c["sheen"], bend=0.02)     # the feather holding it
    if prop == "phone":
        cx, cy = 300, 650
        corner = [(-62, -108), (62, -108), (62, 108), (-62, 108)]
        case = [_rot((cx + x, cy + y), (cx, cy), 8) for x, y in corner]
        d.polygon(case, fill=c["lemon"])
        d.line(case + case[:1], fill=INK, width=6)
        d.polygon([_rot((cx + x * 0.82, cy + y * 0.84 - 4), (cx, cy), 8) for x, y in corner], fill=(24, 28, 40))
        for w, yy, col, right in ((66, -60, c["paper"], False), (52, -24, c["lemon"], True), (60, 12, c["paper"], False)):
            x0 = cx + 36 - w if right else cx - 36
            d.polygon([_rot(p, (cx, cy), 8) for p in ((x0, cy + yy), (x0 + w, cy + yy), (x0 + w, cy + yy + 22),
                                                       (x0, cy + yy + 22))], fill=col)
    elif prop == "ok":
        cx, cy, r = 256, 676, 30
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c["lemon"], width=11)
    elif prop in ("sparkle", "sparkle_high"):
        spots = [(250, 524), (204, 572), (284, 482)] if prop == "sparkle" else [(860, 170), (520, 120), (930, 300)]
        for x, y in spots:
            for a in (0, 90):
                d.line([_polar((x, y), a, 20), _polar((x, y), a + 180, 20)], fill=c["lemon"], width=8)
    elif prop == "wave":
        for k in range(3):
            r = 196 + 26 * k
            d.arc([300 - r, 620 - r, 300 + r, 620 + r], 178, 214, fill=c["lemon"], width=7)
    elif prop == "clap":
        for k in range(3):
            d.arc([250 - 28 * k, 596 - 28 * k, 400 + 28 * k, 746 + 28 * k], 186, 236, fill=c["lemon"], width=7)
    elif prop == "write":
        pad = [(206, 660), (356, 644), (368, 806), (218, 822)]
        d.polygon(pad, fill=c["paper"])
        d.line(pad + pad[:1], fill=INK, width=6)
        for k in range(4):
            d.line([(228, 694 + 30 * k), (344, 682 + 30 * k)], fill=(176, 176, 182), width=4)
        d.line([(344, 668), (290, 770)], fill=INK, width=22)
        d.line([(344, 668), (290, 770)], fill=c["lemon"], width=13)
        d.polygon([(282, 762), (298, 770), (282, 792)], fill=INK)


# ---- the face

def _chatur_eye(d, look=(-7, 1), lid=0.26, tilt=0, wide=False, at=C_EYE, inner=-1, size=1.0):
    """An eye: a big dark iris under a calm, clever lid. tilt drops the lid's inner end (a frown); inner is the side
    the inner corner faces (-1: left, as side-on, where the beak is)."""
    c = CHATUR
    ex, ey = at
    k = size
    rx, ry = ((39, 42) if wide else (36, 38))
    rx, ry = rx * k, ry * k
    d.ellipse([ex - rx - 8 * k, ey - ry - 8 * k, ex + rx + 8 * k, ey + ry + 8 * k], fill=c["plume_mid"])  # bare skin round it
    d.ellipse([ex - rx, ey - ry, ex + rx, ey + ry], fill=c["eye"])
    ix, iy = ex + look[0] * k, ey + look[1] * k
    d.ellipse([ix - 26 * k, iy - 26 * k, ix + 26 * k, iy + 26 * k], fill=c["iris"])
    d.ellipse([ix - 16 * k, iy - 16 * k, ix + 16 * k, iy + 16 * k], fill=c["pupil"])
    d.ellipse([ix - 15 * k, iy - 17 * k, ix - 2 * k, iy - 4 * k], fill=(255, 255, 255))
    d.ellipse([ix + 8 * k, iy + 7 * k, ix + 15 * k, iy + 14 * k], fill=c["lemon"])
    if lid > 0:
        # the upper lid: a cap over the top of the eye; tilt drops its front end (a frown)
        a = math.degrees(math.asin(max(-0.9, min(0.9, 1 - 2 * lid))))
        cap = (_arc_pts(ex, ey, rx, ry, 180 + a - tilt, 360 - a - tilt * 0.3) if inner < 0 else
               _arc_pts(ex, ey, rx, ry, 180 + a + tilt * 0.3, 360 - a + tilt))
        d.polygon(cap, fill=c["plume_mid"])
        d.line([cap[0], cap[-1]], fill=INK, width=7)
    d.ellipse([ex - rx, ey - ry, ex + rx, ey + ry], outline=INK, width=5)


def _chatur_brow(d, lift=0, frown=0, at=C_EYE, inner=-1, size=1.0):
    """A ridge of glossy feathers over an eye. lift raises it; frown drops its inner end."""
    c = CHATUR
    ex, ey = at
    offsets = [(-56, -44 + frown - lift * 0.6), (-34, -62 + frown - lift), (6, -72 - lift), (46, -66 - lift),
               (62, -54 - lift), (12, -56 - lift), (-28, -50 + frown * 0.8 - lift)]
    pts = [(ex + dx * size, ey + dy * size) for dx, dy in offsets]
    if inner > 0:
        pts = [(2 * ex - x, y) for x, y in pts]
    _blob(d, pts, c["sheen"], INK, 4)
    _taper(d, pts[1:4], c["glint"], 7)


def _bristles(d):
    """The tuft of stiff feathers over the root of the beak, hiding the nostrils, as on every crow."""
    c = CHATUR
    for (x, y), (tx, ty) in (((384, 254), (316, 268)), ((388, 270), (306, 290)), ((390, 288), (312, 312)),
                             ((384, 306), (326, 330))):
        d.polygon([(x, y - 10), (tx, ty), (x, y + 10)], fill=c["plume"])
        d.line([(x - 6, y - 3), (tx + 8, ty)], fill=c["sheen"], width=3)


def _chatur_upper(d):
    """The top half of the beak, which never moves, with the bristles over its root."""
    c = CHATUR
    up = _spline(C_UPPER[:7], closed=False, n=8) + list(C_UPPER[7:])
    d.polygon(up, fill=c["beak"])
    _taper(d, [(374, 266), (330, 266), (276, 276), (222, 294), (172, 322), (136, 352)], c["beak_light"], 12)
    d.line(_spline([(366, 316), (300, 326), (234, 342)], closed=False), fill=c["beak_dark"], width=4)
    d.line(up + up[:1], fill=INK, width=6, joint="curve")
    _bristles(d)


def _chatur_beak(d, angle=0.0, smile=False):
    """The bottom half of the beak turned down about the corner by angle degrees (the mouths), its root under the
    cheek feathers, then the top half over it. Side-on there's nothing between the two halves: the board shows."""
    c = CHATUR
    lower = [_rot(p, C_HINGE, angle) for p in C_LOWER]
    d.polygon(lower, fill=c["beak_dark"])
    d.line([_rot(p, C_HINGE, angle) for p in ((190, 392), (252, 390), (316, 392), (366, 396))], fill=c["beak"],
           width=6, joint="curve")
    d.line(lower + lower[:1], fill=INK, width=6, joint="curve")
    _blob(d, C_CHEEK, c["plume"])
    _chatur_upper(d)
    if smile:                                                         # the corner of the beak curls up into the cheek
        _stroke(d, [(362, 348), (388, 344), (410, 326)], INK, 7)
        _stroke(d, [(378, 334), (402, 320)], c["sheen"], 4)


# ---- the whole bird

def _hackle(x, y, s=1.0):
    return _spline([(x + 20 * s, y - 20 * s), (x - 4 * s, y + 2 * s), (x - 16 * s, y + 16 * s), (x + 14 * s, y + 20 * s)],
                   n=6)


def _silhouette(d):
    c = CHATUR
    body = _spline(C_BODY)
    shapes = [body] + [_hackle(*h) for h in C_HACKLES]
    for s in shapes:                                                            # the cool light all round him
        d.line(s + s[:2], fill=c["rim"], width=16, joint="curve")
    for s in shapes:
        d.polygon(s, fill=c["plume"])
    for x, y, s in C_HACKLES:
        d.line([(x + 14 * s, y - 10 * s), (x - 8 * s, y + 10 * s)], fill=c["plume_mid"], width=4)
    _taper(d, C_BACK, c["lemon"], 10)                                           # lemon light along his back
    _taper(d, [(392, 650), (380, 760), (386, 880), (412, 990)], c["gloss"], 14)  # light from below on the breast
    for row in ([(410, 760), (470, 772), (540, 770)], [(420, 830), (490, 842), (560, 838)],
                [(430, 900), (500, 912), (570, 906)]):
        _scallops(d, row, c["plume_mid"], size=40, width=4, every=44)


def _tail(d):
    c = CHATUR
    for base, tip in (((846, 880), (1010, 1150)), ((866, 866), (1060, 1110)), ((884, 852), (1096, 1060))):
        _feather(d, base, tip, 96, c["plume_mid"], edge=c["sheen"], bend=0.02)


def _shawl(d):
    c = CHATUR
    back = _spline(C_SHAWL_BACK, closed=False, n=10)
    low = _frill(C_SHAWL_LOW, 9, 40, side=-1)
    edge = _frill(C_SHAWL_EDGE, 7, 34, side=-1)
    d.polygon(back + low + edge, fill=c["shawl"])
    for row in ([(618, 222), (640, 270), (656, 324), (664, 380)], [(592, 336), (604, 400), (640, 460), (690, 520)],
                [(500, 470), (546, 530), (620, 580), (700, 600)], [(430, 610), (500, 640), (580, 648), (660, 640)]):
        _scallops(d, row, c["shawl_light"], size=38, width=5, every=42)
    d.line(low + edge, fill=c["shawl_dark"], width=4, joint="curve")           # where the black begins


def _face(d, pose):
    c = CHATUR
    p = C_POSES.get(pose, {})
    _taper(d, [(394, 214), (446, 190), (504, 186)], c["sheen"], 11)            # gloss on the crown
    if p.get("crest"):
        for (bx, by), (tx, ty) in (((440, 200), (414, 140)), ((470, 190), (468, 124)), ((500, 188), (518, 132))):
            spike = [(bx - 16, by + 6), (tx, ty), (bx + 16, by + 4)]
            d.line(spike + spike[:1], fill=c["rim"], width=10, joint="curve")
            d.polygon(spike, fill=c["plume"])
            d.line([(bx, by), ((bx + tx) / 2, (by + ty) / 2)], fill=c["sheen"], width=4)
    _stroke(d, [(450, 344), (474, 380), (488, 424)], c["plume_mid"], 6)          # the line of the cheek
    if pose == "facepalm":
        _paint_chatur_blink(d)                                 # the eye shut behind the wing, as the blink draws it
    elif p.get("happy"):
        _happy_eye(d)
    else:
        _chatur_eye(d, look=p.get("look", (-7, 1)), lid=0 if p.get("wide") else p.get("lid", 0.26),
                    tilt=p.get("frown", 0) * 2, wide=p.get("wide", False))
    _chatur_brow(d, lift=p.get("lift", 0), frown=p.get("frown", 0))


def _paint_chatur(d, pose):
    p = C_POSES[pose]
    if p.get("far"):
        _raised_wing(d, *p["far"], far=True)
    _tail(d)
    if p.get("near") and not p.get("far"):
        for base, tip in (((820, 840), (990, 1090)), ((800, 850), (962, 1100))):
            _feather(d, base, tip, 74, CHATUR["wing_far"], bend=-0.03)
    _silhouette(d)
    _shawl(d)
    if not p.get("near"):
        _folded_wing(d)
    _face(d, pose)
    _chatur_upper(d)                                       # the bottom half of the beak is in the mouths
    _paint_chatur_front(d, pose)


def _paint_chatur_front(d, pose):
    """What's in front of him in a pose: the near wing, what it holds, and the far wingtip when it comes round."""
    p = C_POSES[pose]
    if p.get("far_front"):
        _raised_wing(d, *p["far_front"], far=True, hand_only=True)
    if p.get("near"):
        if p.get("prop") in ("phone", "write"):
            _props(d, pose)
        _raised_wing(d, *p["near"], fold=p.get("fold", 1.0))
        if p.get("prop") not in ("phone", "write"):
            _props(d, pose)


C_MOUTHS = {"closed": {}, "fv": {"angle": 3}, "teeth": {"angle": 7}, "oo": {"angle": 8}, "round": {"angle": 12},
            "open": {"angle": 15}, "tongue": {"angle": 13}, "wide": {"angle": 21}, "smile": {"smile": True}}


def _paint_chatur_mouth(d, shape):
    _chatur_beak(d, **C_MOUTHS[shape])
    if shape == "smile":                                     # a happy eye: wide awake, the lower lid lifted a little
        c = CHATUR
        ex, ey = C_EYE
        _chatur_eye(d, look=(-6, 1), lid=0)
        rx, ry = 42, 45
        bottom = [(ex + rx * math.cos(math.radians(a)), ey + ry * math.sin(math.radians(a))) for a in range(0, 181, 10)]
        top = _spline([(ex - rx, ey + 30), (ex, ey + 20), (ex + rx, ey + 30)], closed=False)
        d.polygon(bottom + top, fill=c["plume_mid"])
        d.line(top, fill=INK, width=6, joint="curve")


def _paint_chatur_blink(d):
    c = CHATUR
    ex, ey = C_EYE
    d.ellipse([ex - 44, ey - 46, ex + 44, ey + 46], fill=c["plume_mid"])
    d.arc([ex - 34, ey - 22, ex + 34, ey + 18], 20, 160, fill=INK, width=8)
    d.arc([ex - 30, ey - 14, ex + 30, ey + 10], 30, 150, fill=c["sheen"], width=4)


# ---- Chatur facing us (brand/avatars/chatur/views/front): for the lines he says to the viewer. Face-on, the beak
# points at us, so when it opens we see into the mouth.

F_EYES = ((452, 330), (628, 330))       # on the sides of the head, as a crow's are: not close together, like an owl's
F_EYE_SIZE = 0.84
F_SHOULDERS = ((392, 652), (688, 652))     # his right wing (on our left), his left wing (on our right)
F_LEADS = ((-0.5, -0.85), (0.5, -0.85))
F_HEAD = [(540, 188), (612, 202), (668, 230), (700, 284), (712, 350), (700, 420), (664, 474), (608, 508), (540, 520),
          (472, 508), (416, 474), (380, 420), (368, 350), (380, 284), (412, 230), (468, 202)]
F_BODY = [(540, 470), (650, 494), (730, 580), (770, 730), (768, 900), (738, 1060), (690, 1160), (390, 1160),
          (342, 1060), (312, 900), (310, 730), (350, 580), (430, 494)]
F_SHAWL = [(392, 430), (688, 430), (728, 520), (730, 640)]             # the grey collar: neck and top of the breast
F_SHAWL_LOW = [(730, 640), (680, 712), (540, 736), (400, 712), (350, 640)]
F_BIB = [(468, 492), (612, 492), (604, 556), (580, 606), (540, 652), (500, 606), (476, 556)]   # the black throat
F_UPPER_L = [(474, 382), (478, 408), (490, 446), (506, 486), (522, 522), (534, 548), (540, 558)]   # the top half's left side
F_LOWER = [(494, 478), (586, 478), (574, 518), (556, 552), (540, 574), (524, 552), (506, 518)]


def _mirror_x(pts, cx=540):
    return [(2 * cx - x, y) for x, y in pts]


def _face_on_fingers(fingers, k=0.86):
    """Fingers for the wing on our left, face-on: the side-on hand (which points left), a little smaller."""
    return [(a, length * k, width * 0.92) for a, length, width in fingers]


def _face_on_mirrored(fingers, k=0.86):
    """Fingers for the wing on our right: the side-on hand mirrored, so it points right and folds inwards."""
    return [((540 - a) % 360, length, width) for a, length, width in _face_on_fingers(fingers, k)]


# the wings and what they hold, pose by pose: "R" is the wing on our right (his left), "L" the one on our left.
# Each is (wrist, fingers) and an optional fold.
F_POSES = {
    "talk": {},
    "point": {"R": ((772, 400), _face_on_mirrored(_pointing(275))), "R_lead": (-0.8, -0.6)},
    "point_left": {"L": ((300, 410), _face_on_fingers(_pointing(226))), "L_lead": (0.8, -0.6)},
    "point_down": {"R": ((770, 820), _face_on_mirrored(_pointing(70)))},
    "open_hand": {"R": ((810, 730), _face_on_mirrored(_fan(220, 5, 72, 170)))},
    "shrug": {"L": ((266, 724), _face_on_fingers(_fan(200, 5, 64, 166))),
              "R": ((814, 724), _face_on_mirrored(_fan(200, 5, 64, 166))), "lift": 12},
    "think": {"R": ((646, 640), _face_on_mirrored(_fan(300, 4, 26, 128))), "R_fold": 0.5, "look": (0, -9), "frown": 8},
    "one": {"R": ((806, 560), _face_on_mirrored(_count(1))), "R_lead": (-0.8, -0.6)},
    "two": {"R": ((806, 560), _face_on_mirrored(_count(2))), "R_lead": (-0.8, -0.6)},
    "three": {"R": ((806, 560), _face_on_mirrored(_count(3))), "R_lead": (-0.8, -0.6)},
    "four": {"R": ((806, 560), _face_on_mirrored(_count(4))), "R_lead": (-0.8, -0.6)},
    "five": {"R": ((806, 560), _face_on_mirrored(_count(5))), "R_lead": (-0.8, -0.6)},
    "phone": {"R": ((780, 790), [(308, 84, 44), (290, 92, 44), (272, 88, 44)]), "prop": "phone", "look": (5, 9),
              "lid": 0.32},
    "ok": {"R": ((806, 590), [(290, 164, 44), (274, 178, 44), (258, 164, 44)]), "prop": "ok", "R_lead": (-0.8, -0.6)},
    "thumbs_up": {"R": ((806, 610), [(194, 76, 48), (212, 80, 48), (230, 76, 48), (272, 160, 52)]), "prop": "sparkle",
                  "lift": 6, "R_lead": (-0.8, -0.6)},
    "wave": {"R": ((826, 420), _face_on_mirrored(_fan(240, 5, 80, 196))), "prop": "wave", "lift": 6, "R_lead": (-0.8, -0.6)},
    "clap": {"L": ((488, 742), [(330, 112, 44), (316, 124, 44), (302, 112, 44)]),
             "R": ((592, 742), [(210, 112, 44), (224, 124, 44), (238, 112, 44)]), "prop": "clap", "lift": 6},
    "celebrate": {"L": ((290, 366), _face_on_fingers(_fan(240, 5, 92, 190))),
                  "R": ((790, 366), _face_on_mirrored(_fan(240, 5, 92, 190))), "prop": "sparkle_high", "wide": True,
                  "crest": True, "lift": 12, "L_lead": (0.8, -0.6), "R_lead": (-0.8, -0.6)},
    "facepalm": {"R": ((680, 430), [(196, 200, 52), (210, 220, 52), (224, 222, 52), (238, 206, 52)]), "R_fold": 0.5,
                 "frown": 10, "R_lead": (-0.8, -0.6)},
    "arms_crossed": {"L": ((628, 790), [(344, 118, 44), (330, 128, 44), (316, 118, 44)]),
                     "R": ((452, 790), [(196, 118, 44), (210, 128, 44), (224, 118, 44)]), "lid": 0.44, "frown": 8},
    "surprised": {"L": ((404, 560), [(238, 120, 44), (254, 132, 44), (270, 124, 44)]),
                  "R": ((676, 560), [(302, 120, 44), (286, 132, 44), (270, 124, 44)]), "L_fold": 0.5, "R_fold": 0.5,
                  "wide": True, "crest": True, "lift": 14, "R_lead": (-0.8, -0.6), "L_lead": (0.8, -0.6)},
    "write": {"L": ((420, 806), [(330, 70, 44), (316, 76, 44)]),
              "R": ((612, 770), [(214, 84, 44), (232, 92, 44), (250, 84, 44)]), "prop": "write", "look": (0, 10),
              "lid": 0.32},
    "listen": {"R": ((754, 446), _face_on_mirrored(_fan(300, 4, 30, 120))), "R_fold": 0.5, "look": (-8, 0), "lid": 0.2, "R_lead": (-0.8, -0.6)},
    "pebble": {"R": ((806, 600), [(300, 128, 44), (284, 146, 44), (268, 132, 44)]), "prop": "pebble", "look": (5, -2),
               "lift": 6, "R_lead": (-0.8, -0.6)},
    "drink": {"happy": True, "lift": 8},
}


def _face_on_props(d, pose):
    c = CHATUR
    prop = F_POSES[pose].get("prop")
    if prop == "pebble":
        _pebble(d, 796, 448, 1.15)
        _feather(d, (806, 600), (782, 492), 42, c["wing"], edge=c["sheen"], bend=-0.02)
    if prop == "phone":
        cx, cy = 744, 660
        corner = [(-62, -108), (62, -108), (62, 108), (-62, 108)]
        case = [_rot((cx + x, cy + y), (cx, cy), -6) for x, y in corner]
        d.polygon(case, fill=c["lemon"])
        d.line(case + case[:1], fill=INK, width=6)
        d.polygon([_rot((cx + x * 0.82, cy + y * 0.84 - 4), (cx, cy), -6) for x, y in corner], fill=(24, 28, 40))
        for w, yy, col, right in ((66, -60, c["paper"], False), (52, -24, c["lemon"], True), (60, 12, c["paper"], False)):
            x0 = cx + 36 - w if right else cx - 36
            d.polygon([_rot(p, (cx, cy), -6) for p in ((x0, cy + yy), (x0 + w, cy + yy), (x0 + w, cy + yy + 22),
                                                        (x0, cy + yy + 22))], fill=col)
    elif prop == "ok":
        d.ellipse([728, 526, 788, 586], outline=c["lemon"], width=11)
    elif prop in ("sparkle", "sparkle_high"):
        spots = [(870, 420), (920, 470), (840, 380)] if prop == "sparkle" else [(200, 180), (880, 170), (540, 110)]
        for x, y in spots:
            for a in (0, 90):
                d.line([_polar((x, y), a, 20), _polar((x, y), a + 180, 20)], fill=c["lemon"], width=8)
    elif prop == "wave":
        for k in range(3):
            r = 190 + 26 * k
            d.arc([826 - r, 420 - r, 826 + r, 420 + r], 300, 336, fill=c["lemon"], width=7)
    elif prop == "clap":
        for k in range(3):
            d.arc([450 - 28 * k, 560 - 28 * k, 630 + 28 * k, 740 + 28 * k], 240, 300, fill=c["lemon"], width=7)
    elif prop == "write":
        pad = [(360, 720), (520, 708), (530, 880), (370, 892)]
        d.polygon(pad, fill=c["paper"])
        d.line(pad + pad[:1], fill=INK, width=6)
        for k in range(4):
            d.line([(382, 756 + 30 * k), (508, 746 + 30 * k)], fill=(176, 176, 182), width=4)
        d.line([(580, 752), (500, 840)], fill=INK, width=22)
        d.line([(580, 752), (500, 840)], fill=c["lemon"], width=13)
        d.polygon([(492, 830), (508, 842), (488, 860)], fill=INK)


def _face_on_beak_upper(d):
    """The top half of the beak, face-on: long, pointing down at us, lit on one side, the bristles over its root."""
    c = CHATUR
    left = _spline(F_UPPER_L, closed=False, n=8)
    top = _spline([(606, 380), (570, 366), (540, 362), (510, 366), (474, 380)], closed=False, n=8)
    shape = left + _mirror_x(left)[::-1][1:] + top[1:-1]
    d.polygon(shape, fill=c["beak"])
    d.polygon([(540, 364)] + _mirror_x(left)[::-1][1:] + [(568, 366)], fill=c["beak_dark"])     # the shaded half
    _taper(d, [(532, 372), (527, 424), (528, 474), (532, 516), (538, 546)], c["beak_light"], 13)
    d.line(shape + shape[:1], fill=INK, width=6, joint="curve")
    for sgn in (-1, 1):                                                     # the bristles, from the middle outwards
        for (x, y), (tx, ty) in (((540, 350), (500, 392)), ((546, 360), (514, 406)), ((552, 344), (522, 380))):
            pts = [(540 + sgn * (x - 540), y - 10), (540 + sgn * (tx - 540), ty), (540 + sgn * (x - 540 + 6), y + 10)]
            d.polygon(pts, fill=c["plume"])
            d.line([pts[0], pts[1]], fill=c["sheen"], width=3)


def _face_on_beak(d, drop=0, narrow=0.0, tongue=0, smile=False):
    """The beak face-on: the bottom half drops to open it, and between the halves we see the mouth."""
    c = CHATUR
    w = drop * 0.12 * (1 - narrow)
    if drop:
        inset = 14 * narrow
        mouth = [(482 + inset, 404), (598 - inset, 404), (594 - inset + w, 470 + drop * 0.5),
                 (574 + w, 510 + drop), (540, 520 + drop), (506 - w, 510 + drop), (486 + inset - w, 470 + drop * 0.5)]
        _blob(d, mouth, c["mouth"])
        d.ellipse([520, 500 + drop * 0.2, 560, 516 + drop * 0.7], fill=(98, 28, 40))     # the throat
        ty = 496 + drop * (0.55 if tongue > 1 else 0.92)
        d.ellipse([540 - 30 - w * 0.4, ty - 14, 540 + 30 + w * 0.4, ty + 14], fill=c["tongue"])
    lower = [(x + (-w if x < 540 else w if x > 540 else 0), y + drop) for x, y in F_LOWER]
    d.polygon(lower, fill=c["beak_dark"])
    d.line(lower + lower[:1], fill=INK, width=6, joint="curve")
    _face_on_beak_upper(d)
    if smile:                                                               # the corners of the beak curl up
        for sgn in (-1, 1):
            _stroke(d, [(540 + sgn * 60, 404), (540 + sgn * 74, 394), (540 + sgn * 84, 376)], INK, 7)


def _face_on_grey_sides(d):
    """The house crow's grey, face-on: it wraps the sides of the head behind the eyes and runs down into the collar,
    so the black face (forehead, eyes, beak, throat) is framed by grey, the way a kauwa looks at you."""
    c = CHATUR
    head = _spline(F_HEAD)
    for sgn in (-1, 1):
        def m(pts):
            return _mirror_x(pts) if sgn > 0 else pts
        side = [p for p in (head if sgn < 0 else _mirror_x(head)) if p[0] < 446 and 262 <= p[1] <= 496]
        side.sort(key=lambda p: p[1])                                   # down the side of the head
        inner = _frill([(436, 494), (420, 452), (408, 404), (400, 352), (398, 300), (392, 262)], 6, 26, side=1)
        patch = side + inner
        d.polygon(m(patch), fill=c["shawl"])
        d.line(m(inner), fill=c["shawl_dark"], width=4, joint="curve")
        _scallops(d, m([(390, 330), (402, 392), (420, 446)]), c["shawl_light"], size=30, width=4, every=40)


def _face_on_folded_wing(d, sgn):
    """A wing folded at his side, face-on: rows of coverts at the shoulder, the long flight feathers down his flank."""
    c = CHATUR

    def m(pts):
        return _mirror_x(pts) if sgn > 0 else pts
    for base, tip in (((356, 780), (336, 1090)), ((376, 770), (362, 1100)), ((396, 760), (392, 1100))):
        b_, t_ = m([base, tip])
        _feather(d, b_, t_, 70, c["flight"], edge=c["sheen"], bend=0.03 * -sgn)
    covert = m([(400, 590), (356, 630), (330, 700), (322, 780), (352, 820), (398, 812), (418, 740), (420, 650)])
    _blob(d, covert, c["wing"], INK, 5)
    for row in ([(384, 640), (358, 690), (348, 744)], [(400, 700), (380, 750)]):
        _scallops(d, m(row), c["sheen"], size=36, width=4, every=40)
    _taper(d, m([(400, 594), (360, 630), (334, 700), (326, 770)]), c["glint"], 6)


def _paint_chatur_face_on(d, pose):
    c = CHATUR
    p = F_POSES[pose]
    body = _spline(F_BODY)
    head = _spline(F_HEAD)
    for s in (body, head):                                                  # the cool light all round him
        d.line(s + s[:2], fill=c["rim"], width=16, joint="curve")
    d.polygon(body, fill=c["plume"])
    _taper(d, [(650, 500), (730, 590), (768, 740), (764, 920)], c["lemon"], 10)        # lemon light on one side
    for row in ([(430, 800), (540, 812), (650, 800)], [(440, 870), (540, 882), (640, 870)],
                [(450, 940), (540, 952), (630, 940)]):
        _scallops(d, row, c["plume_mid"], size=40, width=4, every=46)
    low = _frill(F_SHAWL_LOW, 9, 40, side=-1)
    d.polygon(_spline(F_SHAWL, closed=False) + low + [(352, 520)], fill=c["shawl"])        # the grey collar
    for row in ([(372, 540), (430, 580)], [(708, 540), (650, 580)], [(400, 650), (470, 690), (540, 700), (610, 690),
                                                                         (680, 650)]):
        _scallops(d, row, c["shawl_light"], size=38, width=5, every=44)
    for sgn in (-1, 1):
        if ("L", "R")[sgn > 0] not in p:
            _face_on_folded_wing(d, sgn)
    bib = _frill(F_BIB + F_BIB[:1], 7, 26, side=-1, pointed=True)
    d.polygon(bib, fill=c["plume"])                                         # the black throat, shaggy at its edge
    d.polygon(head, fill=c["plume"])
    _face_on_grey_sides(d)
    _taper(d, [(668, 230), (700, 284), (712, 350)], c["lemon"], 9)
    _taper(d, [(468, 216), (540, 204), (612, 216)], c["sheen"], 11)       # gloss on the crown
    if p.get("crest"):
        for (bx, by), (tx, ty) in (((510, 210), (494, 150)), ((540, 204), (540, 138)), ((570, 210), (586, 150))):
            spike = [(bx - 16, by + 6), (tx, ty), (bx + 16, by + 6)]
            d.line(spike + spike[:1], fill=c["rim"], width=10, joint="curve")
            d.polygon(spike, fill=c["plume"])
    if pose == "facepalm":
        _paint_chatur_face_on_blink(d)
    elif p.get("happy"):
        for at in F_EYES:
            _happy_eye(d, at, F_EYE_SIZE)
    else:
        look = p.get("look", (0, 2))
        for k, at in enumerate(F_EYES):
            gaze = (look[0] + (3 if k == 0 else -3), look[1])
            _chatur_eye(d, look=gaze, lid=0 if p.get("wide") else p.get("lid", 0.26), tilt=p.get("frown", 0) * 2,
                        wide=p.get("wide", False), at=at, inner=1 if k == 0 else -1, size=F_EYE_SIZE)
    for k, at in enumerate(F_EYES):
        _chatur_brow(d, lift=p.get("lift", 0), frown=p.get("frown", 0), at=at, inner=1 if k == 0 else -1, size=F_EYE_SIZE)
    _face_on_beak(d)
    _paint_chatur_face_on_front(d, pose)


def _paint_chatur_face_on_front(d, pose):
    """What's in front of him face-on: his wings, when they're up, and what they hold."""
    p = F_POSES[pose]
    held = p.get("prop") in ("phone", "write")
    if held:
        _face_on_props(d, pose)
    for side, k in (("L", 0), ("R", 1)):
        if side in p:
            wrist, fingers = p[side]
            _raised_wing(d, wrist, fingers, shoulder=F_SHOULDERS[k], lead=p.get(side + "_lead", F_LEADS[k]),
                         fold=p.get(side + "_fold", 1.0), size=0.82)
    if not held:
        _face_on_props(d, pose)


F_MOUTHS = {"closed": {}, "fv": {"drop": 10}, "teeth": {"drop": 22}, "oo": {"drop": 30, "narrow": 0.7},
            "round": {"drop": 46, "narrow": 0.5}, "open": {"drop": 56}, "tongue": {"drop": 50, "tongue": 2},
            "wide": {"drop": 76}, "smile": {"smile": True}}


def _paint_chatur_face_on_mouth(d, shape):
    _face_on_beak(d, **F_MOUTHS[shape])
    if shape == "smile":                                     # happy eyes: wide awake, the lower lids lifted a little
        c = CHATUR
        for k, (ex, ey) in enumerate(F_EYES):
            _chatur_eye(d, look=(3 if k == 0 else -3, 1), lid=0, at=(ex, ey), inner=1 if k == 0 else -1, size=F_EYE_SIZE)
            q = F_EYE_SIZE
            rx, ry = 42 * q, 45 * q
            bottom = [(ex + rx * math.cos(math.radians(a)), ey + ry * math.sin(math.radians(a))) for a in range(0, 181, 10)]
            top = _spline([(ex - rx, ey + 30 * q), (ex, ey + 20 * q), (ex + rx, ey + 30 * q)], closed=False)
            d.polygon(bottom + top, fill=c["plume_mid"])
            d.line(top, fill=INK, width=6, joint="curve")


def _paint_chatur_face_on_blink(d):
    c = CHATUR
    q = F_EYE_SIZE
    for ex, ey in F_EYES:
        d.ellipse([ex - 44 * q, ey - 46 * q, ex + 44 * q, ey + 46 * q], fill=c["plume_mid"])
        d.arc([ex - 34 * q, ey - 22 * q, ex + 34 * q, ey + 18 * q], 20, 160, fill=INK, width=8)
        d.arc([ex - 30 * q, ey - 14 * q, ex + 30 * q, ey + 10 * q], 30, 150, fill=c["sheen"], width=4)


CHATUR_POSES = ("pebble", "drink")     # his own: holding up a pebble, and drinking from the full pot at the end


def make_chatur():
    # "sip": where the pot's mouth meets his beak (the build brings the full pot there at the end of the reel)
    _make_kit("chatur", {"name": CHATUR["name"], "about": CHATUR["about"], "faces": "left", "sip": [124, 394],
                         "drawn_by": "tools/avatars.py --chatur"},
              _paint_chatur, _paint_chatur_mouth, _paint_chatur_blink, _paint_chatur_front, CHATUR_POSES)
    _make_kit("chatur/views/front", {"name": "Chatur, facing us", "about": "Chatur turned to the viewer, for the lines "
                                     "he says to them", "sip": [540, 568], "drawn_by": "tools/avatars.py --chatur"},
              _paint_chatur_face_on, _paint_chatur_face_on_mouth, _paint_chatur_face_on_blink, _paint_chatur_face_on_front,
              CHATUR_POSES)


def make_stand_ins():
    import shutil
    for name, look in STAND_INS.items():
        folder = AVATARS / name
        shutil.rmtree(folder, ignore_errors=True)
        for sub in ("poses", "mouths", "eyes"):
            (folder / sub).mkdir(parents=True, exist_ok=True)
        for pose in POSES + EXTRA_POSES:
            _draw_stand_in(look, pose).save(folder / "poses" / "{}.png".format(pose), optimize=True)
        for shape in MOUTHS + EXTRA_MOUTHS:
            _mouth(look, shape).save(folder / "mouths" / "{}.png".format(shape), optimize=True)
        _blink(look).save(folder / "eyes" / "blink.png", optimize=True)
        dc.save_json(folder / "avatar.json", {"name": look["name"], "about": look["about"], "stand_in": True})
        print("drew", dc.rel(folder))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stand-ins", action="store_true", help="draw the two stand-in kits")
    ap.add_argument("--grandpa", action="store_true", help="draw the grandpa kit")
    ap.add_argument("--dc-host", action="store_true", help="draw our host")
    ap.add_argument("--chatur", action="store_true", help="draw Chatur, our crow")
    ap.add_argument("--founder", action="store_true", help="draw Meera, a founder in official dress (a client)")
    ap.add_argument("--used-by", nargs="+", metavar="NAME", help="print the episode folders whose cast uses these avatars")
    a = ap.parse_args()
    if a.used_by:
        out = []
        for d in sorted(dc.EPISODES_DIR.iterdir()) if dc.EPISODES_DIR.is_dir() else []:
            try:
                cast = set((dc.load_json(d / "episode.json").get("cast") or {}).values())
            except Exception:  # noqa: BLE001
                continue
            if cast & set(a.used_by):
                out.append(dc.rel(d))
        print(" ".join(out))
        return
    if a.stand_ins:
        make_stand_ins()
    if a.grandpa:
        make_grandpa()
    if a.dc_host:
        make_dc_host()
    if a.chatur:
        make_chatur()
    if a.founder:
        make_meera()
    bad = 0
    for name in names():
        problems = check_kit(name)
        extra = " · views: {}".format(", ".join(views(name))) if views(name) else ""
        print("{} · {} · poses: {}{}".format(name, "ready" if not problems else "; ".join(problems),
                                            ", ".join(pose_names(name)), extra))
        bad += bool(problems)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
