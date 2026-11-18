#!/usr/bin/env python3
"""Every reel's topic in one register, and the checks that stop a new reel repeating an old one.

    python3 tools/topics.py                  print the register
    python3 tools/topics.py --write          save it as TOPICS.md (GitHub does this after every upload)
    python3 tools/topics.py --check "PF claim kitne din mein settle hota hai?"    is this topic new?
    python3 tools/topics.py --is-posted episodes/ep01-claim-reject                exit 0 if it's live

A new reel must not repeat one we've made: not its topic, its hook or cover, its script or its
photos, and no reel is ever posted twice. validate.py runs these checks (E11) on every episode. Each
episode is compared with every earlier one (a lower number) and with the reels in
brand/topics-done.json (posted before this repo). When a person decides a flagged repeat is fine,
they record it:

    python3 tools/approve.py repeat-ok EP OTHER topic --by NAME --note "why it's different"

Standard library only. With Pillow installed it also catches photos that look the same.
"""
import argparse
import difflib
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402

DONE_FILE = dc.BRAND_DIR / "topics-done.json"
REGISTER = dc.ROOT / "TOPICS.md"
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp"}
WHAT = ("topic", "hook", "script", "photos")
POST_URL = re.compile(r"https://(www\.)?instagram\.com/(reel|reels|p)/[A-Za-z0-9_-]+/?(\?\S*)?")

# Words that say nothing about what a reel is about (Hinglish and English)
STOP = set("""
a an the of to in on for and or is are was be been it its this that these those what how why when where which who
your you my me i we our us with from by at as vs per than then so if not no do does did can will just only very more
most ka ki ke ko se mein me main par pe aur ya hai hain tha thi ho hota hoti hote hoga hogi honge kya kaise kyun kyon
kab kahan kitna kitne kitni kaun kaunsa kaunsi koi kuch ek yeh ye woh wo isse usse apna apne apni aap aapka aapke
aapki tum hum hamara hamare mera meri mere bhi hi toh na nahi nahin mat sirf bas ab abhi phir jab tab agar lekin
magar wala wale wali karo karna karne kar kare karein karen kiya kiye milega milegi milenge milta milti milte mila
mile chahiye lagega lagta lagti lagte sahi rs inr rupee rupees rupay rupaye
""".split())

# Words nearly every PF Guru Ji reel has. They count towards how close two topics are, but two topics need
# more than these in common to be called the same: "PF claim reject" and "PF claim kitne din" share only these.
GENERIC = {"pf", "fund", "claim", "form", "uan", "online", "portal", "member", "account", "settlement", "paisa",
           "paise", "job", "employer", "india"}

# EPF, EPFO and provident fund are all "pf" here; a word and its other forms count as one word.
SYNONYMS = {"epf": "pf", "epfo": "pf", "provident": "pf", "rejected": "reject", "rejection": "reject",
            "withdrawal": "withdraw", "nikalna": "withdraw", "nikaalna": "withdraw", "nikale": "withdraw",
            "nikaale": "withdraw", "nikalein": "withdraw", "nikaalein": "withdraw", "eps": "pension",
            "naukri": "job", "company": "employer", "kampani": "employer", "settle": "settlement"}

TOKEN = re.compile(r"\d+(?:\.\d+)?|[a-z]+|[\u0900-\u097f]+")


# ---------------------------------------------------------------- words

def _norm(w):
    w = SYNONYMS.get(w, w)
    if w.isascii() and w.isalpha() and len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]  # views → view, reels → reel
    return w


def tokens(text, drop_stop=False):
    """The words and numbers of a text, in order, lowercase: "₹15,000 ka Ad" → ["15000", "ka", "ad"]."""
    t = re.sub(r"(?<=\d),(?=\d)", "", str(text or "").lower())
    return [_norm(w) for w in TOKEN.findall(t) if not (drop_stop and w in STOP)]


def shape(text):
    """A hook's words with every number replaced by #, so "₹500 roz" and "₹1,000 roz" look alike."""
    return ["#" if w[0].isdigit() else w for w in tokens(text)]


def norm_prompt(text):
    return " ".join(tokens(text))


# ---------------------------------------------------------------- what each reel is

def number_of(name):
    m = re.match(r"ep(\d+)", str(name))
    return int(m.group(1)) if m else None


_PHOTO_CACHE = {}


def photo_hash(path):
    """(sha256 of the file, a 64-bit picture hash or None). The picture hash stays nearly the same when a
    photo is re-saved, resized or recompressed, so it catches the same photo under another name."""
    path = Path(path)
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _PHOTO_CACHE:
        return _PHOTO_CACHE[key]
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    dh = None
    try:
        from PIL import Image
        with Image.open(path) as im:
            g = im.convert("L").resize((9, 8), Image.LANCZOS)
        px = g.tobytes()  # one byte per pixel (greyscale)
        dh = 0
        for row in range(8):
            for col in range(8):
                dh = (dh << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
    except Exception:  # noqa: BLE001  (no Pillow, or not a picture it can open)
        dh = None
    _PHOTO_CACHE[key] = (sha, dh)
    return sha, dh


def posted_record(ep_dir):
    """The live post of an episode, or None: posted.json (Muse writes it right after posting) or
    status.json → post (tools/approve.py posted)."""
    ep_dir = Path(ep_dir)
    f = ep_dir / "posted.json"
    if f.exists():
        try:
            d = dc.load_json(f)
            return {"url": str(d.get("url") or ""), "on": str(d.get("posted_on") or ""), "file": "posted.json",
                    "by": str(d.get("post_it_from") or "")}
        except Exception as e:  # noqa: BLE001
            return {"url": "", "on": "", "file": "posted.json", "by": "", "error": "posted.json can't be read: {}".format(e)}
    try:
        post = dc.load_json(ep_dir / "status.json").get("post") or {}
    except Exception:  # noqa: BLE001
        post = {}
    if post.get("url"):
        return {"url": post["url"], "on": str(post.get("posted_at") or "")[:10], "file": "status.json", "by": post.get("by", "")}
    return None


def fingerprint(ep_dir):
    """What a reel is: its topic, hook, cover, script, photos and whether it's posted."""
    ep_dir = Path(ep_dir)
    try:
        ep = dc.load_json(ep_dir / "episode.json")
    except Exception:  # noqa: BLE001
        ep = {}
    try:
        reel = dc.load_json(ep_dir / "reel.json") if (ep_dir / "reel.json").exists() else {}
    except Exception:  # noqa: BLE001
        reel = {}
    brief = ep.get("brief") or {}
    cover = (ep.get("post") or {}).get("cover") or {}
    script = [x for x in ep.get("script") or [] if isinstance(x, dict)]
    photos = []
    folder = ep_dir / "media" / "photos"
    if folder.is_dir():
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in PHOTO_TYPES:
                sha, dh = photo_hash(f)
                photos.append({"file": f.name, "sha": sha, "dhash": dh})
    reel_photos = {k: v for k, v in (reel.get("photos") or {}).items() if isinstance(v, dict)}
    return {
        "id": ep_dir.name, "num": number_of(ep_dir.name), "old": False,
        "title": str(ep.get("title") or ""), "topic": str(brief.get("topic") or ""), "hook": str(brief.get("hook") or ""),
        "first_line": str(script[0].get("vo") or "") if script else "",
        "cover": " ".join([str(x) for x in cover.get("lines") or []] + [str(cover.get("stamp") or "")]).strip(),
        "why": [str(x) for x in brief.get("why") or []], "steps": [str(x) for x in brief.get("steps") or []], "covers": "",
        # the share line and the sign-off follow the series format in every reel, so they don't count
        "script": [(str(x.get("shot") or ""), str(x.get("vo") or "")) for x in script
                   if x.get("chapter") not in ("share", "signoff")],
        "photos": photos,
        "prompts": {k: str(v.get("prompt")) for k, v in reel_photos.items() if v.get("prompt")},
        "alts": [(str(v.get("id") or k), str(v.get("alt") or k)) for k, v in reel_photos.items()],
        "posted": posted_record(ep_dir),
    }


def old_reels():
    """Reels posted before this repo (brand/topics-done.json), as old-01, old-02 … in their order."""
    try:
        items = dc.load_json(DONE_FILE).get("topics") or []
    except FileNotFoundError:
        return []
    out = []
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict) or not it.get("topic"):
            continue
        link, on = str(it.get("link") or ""), str(it.get("posted") or "")
        out.append({"id": "old-{:02d}".format(i), "num": 0, "old": True, "title": str(it["topic"]), "topic": "",
                    "hook": str(it.get("hook") or ""), "first_line": "", "cover": "", "why": [], "steps": [],
                    "covers": str(it.get("covers") or ""), "script": [], "photos": [], "prompts": {}, "alts": [],
                    "posted": {"url": link, "on": on, "file": "topics-done.json", "by": ""} if (link or on) else None})
    return out


def episode_folders(base):
    base = Path(base)
    if not base.is_dir():
        return []
    return sorted(d for d in base.iterdir() if d.is_dir() and (d / "episode.json").exists())


def earlier(ep_dir):
    """Every reel this one must not repeat: the old reels and the episodes with a lower number."""
    ep_dir = Path(ep_dir).resolve()
    me = number_of(ep_dir.name)
    out = []
    for d in episode_folders(ep_dir.parent):
        if d.name == ep_dir.name:
            continue
        n = number_of(d.name)
        if me is None or n is None or n < me:
            out.append(fingerprint(d))
    return old_reels() + out


def resolve(name, reels):
    """Find a reel by its folder name, its number (ep01) or its old-NN id."""
    name = str(name or "").strip().rstrip("/").split("/")[-1]
    for o in reels:
        if name and (o["id"] == name or (not o["old"] and o["id"].split("-")[0] == name)):
            return o
    return None


# ---------------------------------------------------------------- how alike two reels are

def topic_words(fp):
    return set(tokens("{} {}".format(fp.get("title", ""), fp.get("topic", "")), drop_stop=True))


def topic_match(a, b):
    """("same" | "close" | None, the words both topics share)."""
    A, B = topic_words(a), topic_words(b)
    if not A or not B:
        return None, set()
    shared = A & B
    specific = shared - GENERIC
    score = len(shared) / min(len(A), len(B))
    if A == B or (score >= 0.75 and len(specific) >= 2):
        return "same", shared
    if score >= 0.5 and len(specific) >= 1:
        return "close", shared
    return None, shared


def hook_match(a, b):
    """True when two hooks are the same line, even with other numbers in it."""
    A, B = shape(a), shape(b)
    if len(A) < 3 or len(B) < 3:
        return False
    return A == B or difflib.SequenceMatcher(None, A, B, autojunk=False).ratio() >= 0.8


def runs(lines, n=4):
    out = set()
    for _, vo in lines:
        t = tokens(vo)
        out |= {tuple(t[i:i + n]) for i in range(len(t) - n + 1)}
    return out


def script_match(a, b):
    """(the share of a's 4-word runs that are also in b, [(a's line, b's line)] that are nearly the same)."""
    A, B = runs(a["script"]), runs(b["script"])
    share = len(A & B) / len(A) if A else 0.0
    same = []
    for sa, va in a["script"]:
        ta = tokens(va)
        if len(ta) < 4:
            continue
        for sb, vb in b["script"]:
            tb = tokens(vb)
            if len(tb) >= 4 and difflib.SequenceMatcher(None, ta, tb, autojunk=False).ratio() >= 0.85:
                same.append((sa, sb))
                break
    return share, same


def photo_matches(a, b):
    """[(a's photo, b's photo, how)] for photos that are the same file, look the same or share a prompt."""
    out = []
    for pa in a["photos"]:
        for pb in b["photos"]:
            if pa["sha"] == pb["sha"]:
                out.append((pa["file"], pb["file"], "is the same file as"))
            elif pa["dhash"] is not None and pb["dhash"] is not None and bin(pa["dhash"] ^ pb["dhash"]).count("1") <= 6:
                out.append((pa["file"], pb["file"], "looks the same as"))
    theirs = {norm_prompt(v): k for k, v in b["prompts"].items()}
    for k, v in a["prompts"].items():
        if norm_prompt(v) in theirs:
            out.append(("the prompt for photo " + k, "prompt for photo " + theirs[norm_prompt(v)], "is the same as"))
    return out


def lock(fp, what):
    """A fingerprint of the part a person said is fine, so their OK lapses if that part changes."""
    if what == "topic":
        parts = [fp["title"], fp["topic"]]
    elif what == "hook":
        parts = [fp["hook"], fp["first_line"], fp["cover"]]
    elif what == "script":
        parts = [vo for _, vo in fp["script"]]
    else:
        parts = sorted(p["sha"] for p in fp["photos"]) + sorted(fp["prompts"].values())
    return dc.section_hash(parts)


def allowed(status, other, what, fp):
    for ok in (status or {}).get("repeat_ok") or []:
        if ok.get("other") == other and ok.get("what") == what and ok.get("lock") == lock(fp, what):
            return ok
    return None


# ---------------------------------------------------------------- the checks (validate.py, E11)

def check(ep_dir, ep, status, r):
    """Add the not-a-repeat checks for one episode to a validate.Report."""
    ep_dir = Path(ep_dir).resolve()
    me = fingerprint(ep_dir)
    others = earlier(ep_dir)
    brief = ep.get("brief") or {}

    def flag(code, step_id, other, what, msg):
        ok = allowed(status, other["id"], what, me)
        if ok:
            r.info(code, step_id, "{} · a person ({}) said it's fine: {}".format(msg, ok.get("by"), ok.get("note") or "no note"))
        else:
            r.fail(code, step_id, msg)

    # E11.5 · one folder, one number
    ep_id, slug = str(ep.get("id") or ""), str(ep.get("slug") or "")
    if ep_id and not re.fullmatch(r"ep\d{2,3}", ep_id):
        r.fail("E11.5", "01-brief", "id '{}' must look like ep02".format(ep_id))
    elif ep_id and slug and ep_dir.name != "{}-{}".format(ep_id, slug):
        r.fail("E11.5", "01-brief", "the folder is {} but episode.json has id {} and slug {}: the folder must be "
                                    "episodes/{}-{}".format(ep_dir.name, ep_id, slug, ep_id, slug))
    n = number_of(ep_dir.name)
    twins = [d.name for d in episode_folders(ep_dir.parent) if d.name != ep_dir.name and n is not None and number_of(d.name) == n]
    if twins:
        r.fail("E11.5", "01-brief", "episode number {} is also used by {}: every episode has its own number "
                                    "(TOPICS.md says which is next)".format(n, ", ".join(twins)))

    if not (me["title"] or me["topic"]):
        return

    # E11.1 · the topic
    near = []
    for o in others:
        level, shared = topic_match(me, o)
        about = ", ".join(sorted(shared))
        if level:
            near.append(o["id"])
        if level == "same":
            flag("E11.1", "01-brief", o, "topic", "the topic repeats {} (\"{}\"): both are about {}".format(o["id"], o["title"], about))
        elif level == "close":
            r.warn("E11.1", "01-brief", "the topic is close to {} (\"{}\"): both mention {}. Make sure the angle is new "
                                        "and brief.repeat_check says how".format(o["id"], o["title"], about))

    # E11.6 · the brief names the closest earlier reel and says how this one is different
    if others:
        rc = brief.get("repeat_check") or {}
        closest, why = str(rc.get("closest") or "").strip(), str(rc.get("different_because") or "").strip()
        named = resolve(closest, others)
        if not closest or not why:
            r.fail("E11.6", "01-brief", "brief.repeat_check is empty: in 'closest', name the reel in TOPICS.md nearest to "
                                        "this topic; in 'different_because', say in one sentence how this one is different")
        elif not named:
            r.fail("E11.6", "01-brief", "brief.repeat_check.closest is '{}', which isn't an earlier reel in TOPICS.md. "
                                        "Use one of: {}".format(closest, ", ".join(o["id"] for o in others)))
        elif near and named["id"] not in near:
            r.fail("E11.6", "01-brief", "brief.repeat_check.closest is {}, but the check finds {} nearer to this topic: "
                                        "compare with {} and say how this one is different".format(
                                            named["id"], " and ".join(near), near[0] if len(near) == 1 else "the nearest"))
        elif len(why.split()) < 6:
            r.fail("E11.6", "01-brief", "brief.repeat_check.different_because is too short to tell: say how this reel's "
                                        "question, numbers or viewer differ from {}'s".format(named["id"]))

    # E11.2 · the hook, the first line and the cover
    for label, text, step_id in (("brief.hook", me["hook"], "01-brief"), ("the first line", me["first_line"], "03-script"),
                                 ("the cover", me["cover"], "10-publish")):
        if not text:
            continue
        for o in others:
            hit = next(((ol, ot) for ol, ot in (("hook", o["hook"]), ("first line", o["first_line"]), ("cover", o["cover"]))
                        if ot and hook_match(text, ot)), None)
            if hit:
                flag("E11.2", step_id, o, "hook", "{} \"{}\" is the same line as {}'s {} \"{}\"".format(label, text, o["id"], hit[0], hit[1]))

    # E11.3 · the script
    for o in others:
        if not (me["script"] and o["script"]):
            continue
        share, same = script_match(me, o)
        if share >= 0.25 or len(same) >= 3:
            lines = "; lines like {}'s: {}".format(o["id"], ", ".join("{} ≈ {}".format(a, b) for a, b in same[:8])) if same else ""
            flag("E11.3", "03-script", o, "script", "the script repeats {}: {:.0%} of its 4-word phrases are in that "
                                                    "reel's script{}".format(o["id"], share, lines))

    # E11.4 · the photos
    for o in others:
        for a, b, how in photo_matches(me, o):
            flag("E11.4", "04-shots", o, "photos", "{} {} {}'s {}".format(a, how, o["id"], b))

    # E11.7 · the post record
    rec = me["posted"]
    if rec and rec["file"] == "posted.json":
        if rec.get("error"):
            r.fail("E11.7", "10-publish", rec["error"])
        elif not POST_URL.fullmatch(rec["url"]):
            r.fail("E11.7", "10-publish", "posted.json → url must be the post's Instagram link, like "
                                          "https://www.instagram.com/reel/ABC123/ (it has '{}')".format(rec["url"]))
        elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", rec["on"]):
            r.fail("E11.7", "10-publish", "posted.json → posted_on must be the day it went live, as YYYY-MM-DD")
        else:
            for d in episode_folders(ep_dir.parent):
                other = posted_record(d) if d.name != ep_dir.name else None
                if other and other["url"].rstrip("/") == rec["url"].rstrip("/"):
                    r.fail("E11.7", "10-publish", "{} has the same post link: each episode is its own post".format(d.name))


# ---------------------------------------------------------------- the register (TOPICS.md)

def cell(text):
    return str(text or "").replace("|", "\\|").replace("\n", " ").strip() or "—"


def posted_text(rec):
    if not rec:
        return "not yet"
    if rec.get("url"):
        return "[{}]({})".format(rec.get("on") or "live", rec["url"])
    return rec.get("on") or "yes"


def register(base=None):
    base = Path(base) if base else dc.EPISODES_DIR
    eps = [fingerprint(d) for d in episode_folders(base)]
    old = old_reels()
    nums = [e["num"] for e in eps if e["num"] is not None]
    nxt = "ep{:02d}".format((max(nums) if nums else 0) + 1)
    out = ["# Topics we've made", "",
           "Every {} reel. A new reel needs its own topic, hook, script and photos, and no reel is "
           "ever posted twice.".format(dc.brand().get("brand", "")), "",
           "- **Next episode number: {}**".format(nxt),
           "- **Muse:** read this before choosing a topic (MUSE.md → N1). In the new episode's `brief.repeat_check`, "
           "name the reel here that's closest to yours and say how yours is different.",
           "- **The checks** compare every new episode with all of these (check report → Not a repeat).",
           "- GitHub rewrites this file after every upload (`tools/topics.py`). Don't edit it. To add a reel posted "
           "before this repo, add it to `brand/topics-done.json`.", "",
           "| Reel | Topic | Hook | Posted |", "|---|---|---|---|"]
    for e in reversed(eps):
        out.append("| {} | {} | {} | {} |".format(e["id"], cell(e["topic"] or e["title"]), cell(e["hook"]), posted_text(e["posted"])))
    for o in reversed(old):
        out.append("| {} (before this repo) | {} | {} | {} |".format(o["id"], cell(o["title"]), cell(o["hook"]), posted_text(o["posted"])))
    if not eps and not old:
        out.append("| — | nothing yet | — | — |")
    out.append("")
    for e in reversed(eps):
        out += ["## {}".format(e["id"]), "",
                "- **Title:** {}".format(cell(e["title"])),
                "- **Topic:** {}".format(cell(e["topic"])),
                "- **Hook:** {}".format(cell(e["hook"])),
                "- **Covers:** {}{}".format("Why: " + " · ".join(e["why"]) + ". " if e["why"] else "",
                                            "Steps: " + " · ".join(e["steps"]) if e["steps"] else ""),
                "- **Cover:** {}".format(cell(e["cover"])),
                "- **Photos:** {}".format(" · ".join("{} {}".format(i, a) for i, a in e["alts"]) or "—"),
                "- **Posted:** {}".format(posted_text(e["posted"])), ""]
    if old:
        out += ["## Posted before this repo", "", "From `brand/topics-done.json`.", ""]
        for o in old:
            out.append("- **{}** · {}{}{} · {}".format(o["id"], o["title"], " · hook: " + o["hook"] if o["hook"] else "",
                                                     " · covers: " + o["covers"] if o["covers"] else "", posted_text(o["posted"])))
        out.append("")
    return "\n".join(out)


def check_text(text, base=None):
    """Compare a proposed topic with every reel. Returns (verdict, lines)."""
    base = Path(base) if base else dc.EPISODES_DIR
    probe = {"id": "(new)", "title": text, "topic": "", "hook": "", "first_line": "", "cover": ""}
    worst, lines = "NEW", []
    for o in old_reels() + [fingerprint(d) for d in episode_folders(base)]:
        level, shared = topic_match(probe, o)
        hook = any(hook_match(text, t) for t in (o["hook"], o["first_line"], o["cover"]) if t)
        if level == "same" or hook:
            worst = "REPEAT"
            lines.append("REPEAT · {} (\"{}\"){}".format(o["id"], o["title"], ": both are about " + ", ".join(sorted(shared)) if shared else ": same hook"))
        elif level == "close":
            worst = "CLOSE" if worst == "NEW" else worst
            lines.append("CLOSE · {} (\"{}\"): both mention {}".format(o["id"], o["title"], ", ".join(sorted(shared))))
    return worst, lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="save the register as TOPICS.md")
    ap.add_argument("--check", metavar="TOPIC", help="compare a proposed topic with every reel")
    ap.add_argument("--is-posted", metavar="EPISODE", help="exit 0 and print the link if the episode is live")
    a = ap.parse_args()
    if a.is_posted:
        rec = posted_record(a.is_posted)
        if rec and (rec.get("url") or rec.get("on")):
            print("POSTED · {} · {}".format(rec.get("url"), rec.get("on")))
            sys.exit(0)
        print("not posted")
        sys.exit(1)
    if a.check:
        verdict, lines = check_text(a.check)
        print({"NEW": "NEW · no reel has this topic", "CLOSE": "CLOSE · a reel is near this topic: make sure the angle is new",
               "REPEAT": "REPEAT · a reel already has this topic: pick another"}[verdict])
        for line in lines:
            print("  " + line)
        sys.exit(1 if verdict == "REPEAT" else 0)
    text = register()
    if a.write:
        REGISTER.write_text(text + "\n", encoding="utf-8")
        print("Wrote {}".format(dc.rel(REGISTER)))
    else:
        print(text)


if __name__ == "__main__":
    main()
