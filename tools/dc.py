"""Shared helpers for the reel pipeline. Standard library only (Python 3.9+)."""
import ast
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "brand"
FORMS_FILE = BRAND_DIR / "epfo-forms.json"   # the EPFO forms a reel may name, each with its official source
EPISODES_DIR = ROOT / "episodes"

# The per-episode steps, in order. "section" is the part of episode.json an approval locks.
STEPS = [
    {"id": "01-brief", "name": "Brief", "human": True, "lock": "section", "section": "brief"},
    {"id": "02-data", "name": "Data and sources", "human": True, "lock": "section", "section": "data"},
    {"id": "03-script", "name": "Script", "human": True, "lock": "section", "section": "script"},
    {"id": "04-shots", "name": "Shot list and prompts", "human": False, "lock": "section", "section": "shots"},
    {"id": "05-keyframes", "name": "Keyframes", "human": True, "lock": "shots", "kind": "keyframe"},
    {"id": "06-motion", "name": "Motion", "human": True, "lock": "shots", "kind": "motion"},
    {"id": "07-voice", "name": "Voice", "human": True, "lock": "file"},
    {"id": "08-assembly", "name": "Assembly", "human": True, "lock": "file"},
    {"id": "09-final-qa", "name": "Final QA", "human": True, "lock": "file"},
    {"id": "10-publish", "name": "Publish", "human": True, "lock": "section", "section": "post"},
    {"id": "11-measure", "name": "Measure", "human": False, "lock": "none"},
]
STEP_IDS = [s["id"] for s in STEPS]
STEP_STATES = {"todo", "drafted", "in_progress", "needs_human", "passed", "failed"}
SHOT_STATES = {"todo", "in_progress", "needs_human", "passed", "failed"}
# "rule" is a sourced rule or procedure without a number ("the claim status shows why it was rejected"): like a fact,
# a person checks its source before it can pass.
DATA_KINDS = {"input", "fact", "rule", "assumption", "derived", "advice"}
SOURCED_KINDS = {"fact", "rule"}
UNITS = {"INR", "%", "count", "days", "months", "years", "minutes", "seconds", "x"}


def step(step_id):
    for s in STEPS:
        if s["id"] == step_id:
            return s
    raise KeyError("unknown step " + step_id)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def today():
    return datetime.date.today().isoformat()


def now():
    return datetime.datetime.now().replace(microsecond=0).isoformat()


# ---------- hashing (approvals are locked to content) ----------

def section_hash(obj):
    blob = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def shot_spec_hash(shot, kind):
    """What a keyframe or motion approval is locked to: the text and the prompt, not the timing."""
    keys = ("card_text", "keyframe_prompt") if kind == "keyframe" else ("card_text", "motion_prompt", "motion_text")
    return section_hash({k: shot.get(k) for k in keys})


def locked_content(episode, step_id):
    """The part of the episode an approval of this step is locked to."""
    s = step(step_id)
    if s.get("section") == "shots":
        return {"shots": episode.get("shots"), "breaks": episode.get("breaks")}
    if s.get("section"):
        return episode.get(s["section"])
    return None


# ---------- numbers ----------

NUM_RE = re.compile(
    r"(?<![A-Za-z0-9#])(₹\s?)?(\d(?:[\d,]*\d)?(?:\.\d+)?)(\s?%)?(\s+(?:lakh|lac|crore)\b)?",   # ends on a digit: "₹1,50,000," is ₹1,50,000
    re.IGNORECASE,
)
INDIAN_GROUPING = re.compile(r"^\d{1,2}(,\d{2})*,\d{3}$")
# EPFO form names ("Form 19", "Form 10C", "Forms 19 aur 10C", "FORM 15G/15H") are names, not amounts. The number
# checks skip them (and the voice says them in English: फ़ॉर्म नाइनटीन); validate.py checks each name against
# brand/epfo-forms.json instead.
_FORM_ID = r"\d{1,2}[A-Za-z]{0,2}\b"
FORM_RE = re.compile(r"\bForms?[\s-]*(" + _FORM_ID + r"(?:\s*(?:,|/|&|\baur\b|\band\b|\bya\b|\bor\b)\s*" + _FORM_ID + r")*)",
                     re.IGNORECASE)


def form_names(text):
    """The EPFO forms a text names, upper case: "Form 19 aur 10C bharo" → ["19", "10C"]."""
    return [f.upper() for m in FORM_RE.finditer(text or "") for f in re.findall(_FORM_ID, m.group(1))]


def form_numbers(text):
    """The numbers inside those names, {19, 10}: heard in a voice line, they're the form's name, not an amount."""
    return {int(re.match(r"\d+", f).group()) for f in form_names(text)}


def canonical(value, kind):
    v = round(float(value), 6)
    v = int(v) if v.is_integer() else v
    if kind == "INR":
        return "₹{}".format(v)
    if kind == "%":
        return "{}%".format(v)
    return "{}".format(v)


def extract_numbers(text):
    """Every number written with digits in a piece of text, in a comparable form."""
    out = []
    text = FORM_RE.sub(lambda m: " " * len(m.group(0)), text or "")   # a form's name isn't an amount
    for m in NUM_RE.finditer(text):
        cur, digits, pct, mult = m.groups()
        try:
            value = float(digits.replace(",", ""))
        except ValueError:
            continue
        if mult:
            value *= 100000 if mult.strip().lower() in ("lakh", "lac") else 10000000
        kind = "INR" if cur else ("%" if pct else "n")
        out.append({"raw": m.group(0).strip(), "digits": digits, "value": value,
                    "canon": canonical(value, kind), "kind": kind})
    return out


def grouping_problem(digits):
    """Return a message if a number doesn't use Indian digit grouping, else None."""
    whole = digits.split(".")[0]
    if "," in whole:
        if not INDIAN_GROUPING.match(whole):
            return "use Indian grouping (for example 1,00,000)"
        return None
    if len(whole) >= 5:
        return "add Indian commas (for example 15,000 or 1,00,000)"
    return None


def item_canon(item):
    values = item["value"] if isinstance(item.get("value"), list) else [item.get("value")]
    out = set()
    for v in values:
        if not isinstance(v, (int, float)):
            continue
        if item.get("unit") == "%":
            out.add(canonical(round(v * 100, 6), "%"))
        elif item.get("unit") == "INR":
            out.add(canonical(v, "INR"))
        else:
            out.add(canonical(v, "n"))
    return out


def indian(n):
    """Format a number with Indian digit grouping: 100000 -> 1,00,000."""
    n = round(float(n), 6)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if n.is_integer():
        whole, frac = str(int(n)), ""
    else:
        whole, frac = repr(n).split(".")
        frac = "." + frac
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return sign + whole + frac


def display(item):
    """How a data item's value reads on screen: ₹15,000 · 18% · 1,00,000 · 30 days. A rule reads as its statement."""
    if item.get("kind") == "rule":
        return str(item.get("statement") or "")
    values = item["value"] if isinstance(item.get("value"), list) else [item.get("value")]
    unit = item.get("unit")
    shown = []
    for v in values:
        if unit == "INR":
            shown.append("₹" + indian(v))
        elif unit == "%":
            shown.append(canonical(round(v * 100, 6), "%"))
        else:
            shown.append(indian(v))
    text = ", ".join(shown)
    if unit in ("days", "months", "years", "minutes", "seconds"):
        text += " " + unit
    return text


# ---------- safe formula maths ----------

_ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.Constant,
                  ast.Add, ast.Sub, ast.Mult, ast.Div, ast.USub, ast.UAdd)


def eval_formula(expr, env):
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError("only + - * / and data ids are allowed, found " + type(node).__name__)
        if isinstance(node, ast.Name) and node.id not in env:
            raise ValueError("unknown data id '{}'".format(node.id))
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
            raise ValueError("only numbers are allowed as constants")
    return eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, dict(env))


def close(a, b):
    return abs(a - b) <= max(1e-9, abs(b) * 0.005)


# ---------- files ----------

def rel(path):
    """A path relative to the repo when it's inside it, otherwise the full path."""
    path = Path(path).resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def episode_dirs(selected=None):
    if selected:
        return [Path(p).resolve() for p in selected]
    return sorted(p for p in EPISODES_DIR.iterdir() if (p / "episode.json").exists())


def brand():
    return load_json(BRAND_DIR / "brand.json")


def epfo_forms():
    """{id: form} from brand/epfo-forms.json, or {} when it can't be read (check_brand reports that)."""
    try:
        return {str(f["id"]).upper(): f for f in load_json(FORMS_FILE)["forms"]}
    except Exception:  # noqa: BLE001
        return {}


def follow_line():
    """(note, button) of the follow line on every end card, from brand.json "follow"."""
    b = brand()
    f = b.get("follow", {})
    handle = b.get("instagram", "")
    return f.get("note", ""), f.get("button", "FOLLOW " + handle.upper() if handle else "")


def prompt_text(name):
    """A prompt from brand/prompts/, with the brand's fixed lines filled in."""
    text = read_text(BRAND_DIR / "prompts" / name).strip()
    b = brand()
    note, button = follow_line()
    cast = "; ".join("{} ({}: {})".format(k, v.get("name", k), v.get("about", "")) for k, v in (b.get("cast") or {}).items())
    for key, value in (("SIGNOFF", b.get("signoff", "")), ("TAGLINE", b.get("tagline", "")),
                       ("INSTAGRAM", b.get("instagram", "")), ("FOLLOW_NOTE", note), ("FOLLOW_BUTTON", button),
                       ("CAST", cast or "none yet")):
        text = text.replace("{{" + key + "}}", value)
    return text


# Names that aren't a person: an AI never approves or checks its own work
NOT_PEOPLE = {"", "auto", "auto-check", "claude", "muse", "meta muse", "ai", "bot", "meta ai", "github-actions"}


def is_person(name):
    return bool(name) and str(name).strip().lower() not in NOT_PEOPLE


def reel_inputs_hash(ep_dir):
    """A fingerprint of everything a reel is built from (episode.json, reel.json, photos, screenshots, voice lines, music),
    so a check can tell a reel that is out of date from one that is wrong."""
    import hashlib
    ep_dir = Path(ep_dir)
    files = [ep_dir / "episode.json", ep_dir / "reel.json"]
    for sub in ("media/photos", "media/screens", "media/audio/lines"):
        folder = ep_dir / sub
        if folder.exists():
            files += sorted(p for p in folder.iterdir() if p.is_file() and p.name != ".gitkeep")
    audio = ep_dir / "media" / "audio"
    if audio.exists():
        files += sorted(audio.glob("music.*"))
    h = hashlib.sha256()
    for f in files:
        if f.exists():
            h.update(f.relative_to(ep_dir).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]
