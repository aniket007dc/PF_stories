#!/usr/bin/env python3
"""Check the brand files and every episode, then say what to do next.

It exits with code 1 only when something is wrong. Work that is waiting for a
person (an approval, a source check) is listed but doesn't fail the run.

  python3 tools/validate.py                                every episode
  python3 tools/validate.py episodes/ep01-claim-reject     one episode
  python3 tools/validate.py --write                        also save checks/validate.md per episode
  python3 tools/validate.py --json                         machine-readable output
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402
import spoken  # noqa: E402
import topics  # noqa: E402

LEVELS = ("fail", "warn", "pending", "info")
PROMPT_FILES = ["agent-setup.txt", "style-lock.txt", "motion-lock.txt", "clean-plate.txt",
                "self-check-image.txt", "script-writer.txt"]


class Report:
    def __init__(self, name):
        self.name = name
        self.items = []
        self.steps = []
        self.next_action = None

    def add(self, level, cid, step_id, msg):
        self.items.append({"level": level, "id": cid, "step": step_id, "msg": msg})

    def fail(self, cid, step_id, msg):
        self.add("fail", cid, step_id, msg)

    def warn(self, cid, step_id, msg):
        self.add("warn", cid, step_id, msg)

    def pending(self, cid, step_id, msg):
        self.add("pending", cid, step_id, msg)

    def info(self, cid, step_id, msg):
        self.add("info", cid, step_id, msg)

    def of(self, level, step_id=None):
        return [i for i in self.items if i["level"] == level and (step_id is None or i["step"] == step_id)]

    def failures_through(self, step_id):
        limit = dc.STEP_IDS.index(step_id)
        return [i for i in self.items if i["level"] == "fail" and
                (i["step"] is None or (i["step"] in dc.STEP_IDS and dc.STEP_IDS.index(i["step"]) <= limit))]


# ---------------------------------------------------------------- brand

def check_brand(r):
    try:
        b = dc.brand()
    except Exception as e:  # noqa: BLE001
        r.fail("B1", None, "brand/brand.json can't be read: {}".format(e))
        return None
    for key in ("brand", "series", "tagline", "signoff", "colors", "chapters", "rules", "approvers"):
        if key not in b:
            r.fail("B1", None, "brand/brand.json is missing '{}'".format(key))
    for name, hexv in b.get("colors", {}).items():
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(hexv)):
            r.fail("B1", None, "colour '{}' is not a #RRGGBB value: {}".format(name, hexv))
    for f in PROMPT_FILES:
        if not (dc.BRAND_DIR / "prompts" / f).exists():
            r.fail("B2", None, "brand/prompts/{} is missing".format(f))
    try:
        assets = dc.load_json(dc.BRAND_DIR / "asset-prompts.json")["assets"]
        ids = [a["id"] for a in assets]
        if len(ids) != len(set(ids)):
            r.fail("B3", None, "brand/asset-prompts.json has duplicate ids")
        for a in assets:
            if not re.fullmatch(r"A\d\d", a.get("id", "")) or not a.get("prompt"):
                r.fail("B3", None, "asset {} needs an id like A01 and a prompt".format(a.get("id")))
    except Exception as e:  # noqa: BLE001
        r.fail("B3", None, "brand/asset-prompts.json can't be read: {}".format(e))
    try:
        cap = dc.load_json(dc.BRAND_DIR / "capabilities.json")
        vals = list(cap.get("results", {}).values())
        bad = [v for v in vals if v not in ("yes", "no", "unknown")]
        if bad:
            r.fail("B4", None, "capabilities.json results must be yes, no or unknown")
        if vals and all(v == "unknown" for v in vals):
            r.info("B4", None, "Muse's capability test isn't recorded (brand/capabilities.json). Episodes with a reel.json don't need it: tools/build_reel.py builds them.")
    except Exception as e:  # noqa: BLE001
        r.fail("B4", None, "brand/capabilities.json can't be read: {}".format(e))
    if not b.get("approvers"):
        r.warn("B5", None, "brand/brand.json has no approvers. Add the names of the people allowed to approve steps.")
    try:
        forms = dc.load_json(dc.FORMS_FILE)["forms"]
        for f in forms:
            if not re.fullmatch(r"\d{1,2}[A-Z]{0,2}", str(f.get("id", ""))) or not f.get("for") or not f.get("source_url"):
                r.fail("B6", None, "brand/epfo-forms.json: form '{}' needs an id like 19 or 10C, what it's 'for' and a "
                                   "source_url".format(f.get("id")))
        if len({f.get("id") for f in forms}) != len(forms):
            r.fail("B6", None, "brand/epfo-forms.json lists a form twice")
        unchecked = [str(f.get("id")) for f in forms if not dc.is_person(f.get("checked_by"))]
        if unchecked:
            r.warn("B6", None, "brand/epfo-forms.json: a person hasn't checked Form {} on EPFO's page yet (record "
                               "checked_by and checked_on there)".format(", ".join(unchecked)))
    except Exception as e:  # noqa: BLE001
        r.fail("B6", None, "brand/epfo-forms.json can't be read: {}".format(e))
    return b


# ---------------------------------------------------------------- episode content

def check_brief(ep, r, style="paper"):
    """The brief plans one reel per chapter: the problem, why it happens, the steps that fix it,
    what to check before filing, and where to get help. A Focus how-to plans the task on the screen: the app or
    portal, its steps in order (3 to 12), how to check it worked."""
    s = "01-brief"
    brief = ep.get("brief") or {}
    focus = style == "focus"
    keys = ("topic", "viewer", "hook", "app", "steps", "check", "share_target") if focus else \
        ("topic", "viewer", "hook", "problem", "why", "steps", "check", "help", "share_target")
    for key in keys:
        if not brief.get(key):
            r.fail("E1.1", s, "brief.{} is empty".format(key))
    for key, lo, hi, what in ((("steps", 3, 12, "steps on the screen, in order"),) if focus else
                              (("why", 1, 3, "reasons"), ("steps", 2, 5, "steps, in order"))):
        value = brief.get(key)
        if value and (not isinstance(value, list) or not lo <= len(value) <= hi):
            r.fail("E1.2", s, "brief.{} needs a list of {} to {} {}".format(key, lo, hi, what))


def check_data(ep, r):
    s = "02-data"
    items = ep.get("data") or []
    ids, env = set(), {}
    for it in items:
        iid = it.get("id", "")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", iid):
            r.fail("E2.1", s, "data id '{}' must be lowercase with underscores".format(iid))
        if iid in ids:
            r.fail("E2.1", s, "data id '{}' is used twice".format(iid))
        ids.add(iid)
        if it.get("kind") not in dc.DATA_KINDS:
            r.fail("E2.1", s, "data '{}': kind must be one of {}".format(iid, ", ".join(sorted(dc.DATA_KINDS))))
        if it.get("kind") == "rule":     # a rule has a statement instead of a number
            if not str(it.get("statement") or "").strip():
                r.fail("E2.1", s, "rule '{}' needs a statement: the rule in one plain sentence".format(iid))
            continue
        if it.get("unit") not in dc.UNITS:
            r.fail("E2.1", s, "data '{}': unit must be one of {}".format(iid, ", ".join(sorted(dc.UNITS))))
        v = it.get("value")
        if isinstance(v, list):
            if not v or not all(isinstance(x, (int, float)) for x in v):
                r.fail("E2.1", s, "data '{}': value list must hold numbers".format(iid))
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            env[iid] = v
        else:
            r.fail("E2.1", s, "data '{}': value must be a number".format(iid))
    for it in items:
        iid, kind = it.get("id"), it.get("kind")
        if kind == "derived":
            if not it.get("formula"):
                r.fail("E2.2", s, "derived '{}' needs a formula".format(iid))
                continue
            try:
                got = dc.eval_formula(it["formula"], {k: v for k, v in env.items() if k != iid})
                if not dc.close(got, it.get("value", 0)):
                    r.fail("E2.2", s, "derived '{}' = {} by its formula ({}), but the file says {}".format(
                        iid, round(got, 4), it["formula"], it.get("value")))
            except Exception as e:  # noqa: BLE001
                r.fail("E2.2", s, "derived '{}': {}".format(iid, e))
        elif kind in dc.SOURCED_KINDS:
            if not it.get("source") or not it.get("source_url"):
                r.fail("E2.3", s, "{} '{}' needs a source and a source_url".format(kind, iid))
            if not it.get("checked_by") or not it.get("checked_on"):
                r.pending("E2.3", s, "{} '{}' needs a person to check the source. {}".format(
                    kind, iid, it.get("check_note", "")).strip())
            elif not dc.is_person(it["checked_by"]):
                r.pending("E2.3", s, "{} '{}' says it was checked by '{}', but only a person can check a {}: "
                          "a person opens the source and records it with tools/approve.py fact".format(kind, iid, it["checked_by"], kind))
        elif kind == "assumption":
            if not it.get("note"):
                r.warn("E2.4", s, "assumption '{}' should say where the real number will come from".format(iid))
        elif kind == "advice":
            if not it.get("reason"):
                r.warn("E2.5", s, "advice '{}' should give a reason".format(iid))
    return {it.get("id"): it for it in items}


def allowed_for(uses, data, always):
    allowed = set(str(n) for n in always)
    for u in uses:
        if u in data:
            allowed |= dc.item_canon(data[u])
    return allowed


def label_present(texts, labels):
    low = " ".join(texts).lower()
    return any(l.lower() in low for l in labels)


class _Muted:
    """Pass results through to a report, except for steps that haven't started."""

    def __init__(self, report, muted_steps):
        self.report, self.muted = report, muted_steps

    def __getattr__(self, name):
        fn = getattr(self.report, name)
        if name not in ("fail", "warn", "pending", "info"):
            return fn

        def wrapped(cid, step_id, msg):
            if step_id not in self.muted:
                fn(cid, step_id, msg)
        return wrapped


def check_script_and_shots(ep, data, brand, r, run_script=True, run_shots=True, build=False):
    muted = {s for s, on in (("03-script", run_script), ("04-shots", run_shots)) if not on}
    if muted:
        r = _Muted(r, muted)
    rules = brand.get("rules", {})
    chapters = brand.get("chapters", [])
    free = bool(brand.get("free_shape"))      # Focus: the hook first, the sign-off last, the how-to's parts between
    always = rules.get("always_allowed_numbers", [0, 1, 2, 3])
    labels = rules.get("assumption_labels", ["maan lo", "example"])
    shots = ep.get("shots") or []
    script = ep.get("script") or []
    shot_by_id = {}
    s3, s4 = "03-script", "04-shots"
    forms = dc.epfo_forms()

    # ---- shots: structure and timing
    t = 0.0
    for i, sh in enumerate(shots):
        sid = sh.get("id", "?")
        if sid in shot_by_id:
            r.fail("E4.1", s4, "shot id {} is used twice".format(sid))
        shot_by_id[sid] = sh
        needed = ("start", "end", "chapter", "card_text", "uses") + (() if build else ("assets", "keyframe_prompt", "motion_prompt"))
        for key in needed:
            if key not in sh:
                r.fail("E4.1", s4, "{} is missing '{}'".format(sid, key))
        start, end = sh.get("start", 0), sh.get("end", 0)
        if abs(start - t) > 0.05:
            r.fail("E4.1", s4, "{} starts at {} s but the previous shot ends at {} s".format(sid, start, t))
        if end <= start:
            r.fail("E4.1", s4, "{} ends before it starts".format(sid))
        t = end
        for u in sh.get("uses", []):
            if u not in data:
                r.fail("E4.6", s4, "{} uses '{}', which is not in data".format(sid, u))
        allowed = allowed_for(sh.get("uses", []), data, always)
        for txt in sh.get("card_text", []) + sh.get("motion_text", []):
            for n in dc.extract_numbers(txt):
                if n["canon"] not in allowed:
                    r.fail("E4.3", s4, "{} card text '{}' shows {} but none of the shot's data ({}) has that value".format(
                        sid, txt, n["raw"], ", ".join(sh.get("uses", [])) or "none"))
                g = dc.grouping_problem(n["digits"])
                if g:
                    r.fail("E4.3", s4, "{} card text '{}': {}".format(sid, txt, g))
        for txt in sh.get("card_text", []) + sh.get("motion_text", []):
            for f in dc.form_names(txt):
                if f not in forms:
                    r.fail("E4.11", s4, "{} card text '{}' names Form {}, which isn't in brand/epfo-forms.json: check "
                                        "the form on EPFO's site and add it there with its source".format(sid, txt, f))
        prompt = sh.get("keyframe_prompt", "")
        for txt in ([] if build else sh.get("card_text", [])):
            if '"{}"'.format(txt) not in prompt:
                r.fail("E4.4", s4, "{}: card text \"{}\" is not written in quotes in the keyframe prompt".format(sid, txt))
        for txt in ([] if build else sh.get("motion_text", [])):
            if '"{}"'.format(txt) not in sh.get("motion_prompt", ""):
                r.fail("E4.5", s4, "{}: \"{}\" is not written in quotes in the motion prompt".format(sid, txt))
        if sh.get("yellow_elements", 0) > 1:
            r.warn("E4.8", s4, "{} has {} yellow elements; the style allows one per beat".format(sid, sh["yellow_elements"]))
    lo, hi = rules.get("duration_seconds", [85, 95])
    if shots and not (lo <= t <= hi):
        r.fail("E4.2", s4, "the shots add up to {} s; the target is {}–{} s".format(t, lo, hi))

    try:
        asset_ids = {a["id"] for a in dc.load_json(dc.BRAND_DIR / "asset-prompts.json")["assets"]}
    except Exception:  # noqa: BLE001
        asset_ids = set()
    for sh in ([] if build else shots):
        for a in sh.get("assets", []):
            if a.split(":")[0].strip() not in asset_ids:
                r.fail("E4.7", s4, "{} needs asset '{}', which is not in brand/asset-prompts.json".format(sh.get("id"), a))
    for b in ep.get("breaks", []):
        if b.get("after") not in shot_by_id:
            r.fail("E4.9", s4, "break after unknown shot {}".format(b.get("after")))
        elif abs(b.get("at", -1) - shot_by_id[b["after"]]["end"]) > 0.05:
            r.fail("E4.9", s4, "break after {} should be at {} s".format(b["after"], shot_by_id[b["after"]]["end"]))
        if b.get("type") not in ("tear-lemon", "tear-paper", "tear-black"):
            r.fail("E4.9", s4, "break type must be tear-lemon, tear-paper or tear-black")
        if not build and b.get("asset", "") not in asset_ids:
            r.fail("E4.9", s4, "break asset {} is not in brand/asset-prompts.json".format(b.get("asset")))

    # ---- script (the shot cross-checks wait until step 4 has written shots)
    if shots and len(script) != len(shots):
        r.fail("E3.1", s3, "the script has {} lines but there are {} shots; use one line per shot".format(len(script), len(shots)))
    last_ch = -1
    words = 0
    seen_chapters = set()
    for i, line in enumerate(script):
        sid = line.get("shot")
        sh = shot_by_id.get(sid)
        for key in ("shot", "chapter", "vo", "tts", "highlights", "uses"):
            if key not in line:
                r.fail("E3.1", s3, "script line {} is missing '{}'".format(i + 1, key))
        for u in line.get("uses", []):
            if u not in data:
                r.fail("E3.1", s3, "{} uses '{}', which is not in data".format(sid, u))
        if shots and sh is None:
            r.fail("E3.1", s3, "script line {} points to unknown shot {}".format(i + 1, sid))
            continue
        if shots and i < len(shots) and shots[i].get("id") != sid:
            r.fail("E3.1", s3, "script line {} is for {} but shot {} is {}".format(i + 1, sid, i + 1, shots[i].get("id")))
        sh = sh or {}
        ch = line.get("chapter")
        if free:
            last = i == len(script) - 1
            if not re.fullmatch(r"[a-z][a-z_]{1,13}", str(ch or "")):
                r.fail("E3.2", s3, "{}: chapter '{}' must be one short lowercase word, the part of the how-to the line "
                                   "is in (why, route, steps, mistake, fix, check, list …)".format(sid, ch))
            elif i == 0 and ch != "hook":
                r.fail("E3.2", s3, "{}: the first line is the hook, so its chapter is 'hook'".format(sid))
            elif ch == "hook" and i > 0 and script[i - 1].get("chapter") != "hook":
                r.fail("E3.2", s3, "{}: the hook is the reel's first line or two, not later".format(sid))
            elif last != (ch == "signoff"):
                r.fail("E3.2", s3, "{}: the sign-off is the last line, and only the last".format(sid) if not last else
                       "{}: the last line is the sign-off, so its chapter is 'signoff'".format(sid))
            elif ch == "share" and script[i + 1].get("chapter") not in ("share", "signoff"):
                r.fail("E3.2", s3, "{}: the share line comes right before the sign-off".format(sid))
            seen_chapters.add(ch)
        elif ch not in chapters:
            r.fail("E3.2", s3, "{}: chapter '{}' is not one of {}".format(sid, ch, ", ".join(chapters)))
        else:
            idx = chapters.index(ch)
            if idx < last_ch:
                r.fail("E3.2", s3, "{}: chapter '{}' comes after a later chapter".format(sid, ch))
            last_ch = max(last_ch, idx)
            seen_chapters.add(ch)
        if sh and sh.get("chapter") != ch:
            r.fail("E3.11", s3, "{}: the shot says chapter '{}' but the script line says '{}'".format(sid, sh.get("chapter"), ch))
        vo = line.get("vo", "")
        n_words = len(vo.split())
        words += n_words
        if sh:
            dur = sh.get("end", 0) - sh.get("start", 0)
            if n_words / (rules.get("words_per_second", 1.85) * 1.3) > dur + 0.01:     # even a fast take
                r.warn("E3.12", s3, "{}: {} words won't fit in {} s even at a fast pace".format(sid, n_words, dur))
        for sentence in re.split(r"(?<=[.?!])\s+", vo):
            if len(sentence.split()) > rules.get("sentence_words_warn", 10):
                r.warn("E3.4", s3, "{}: long sentence ({} words): {}".format(sid, len(sentence.split()), sentence))
        line_uses = line.get("uses", sh.get("uses", []))
        allowed = allowed_for(line_uses, data, always)
        for n in dc.extract_numbers(vo):
            if n["canon"] not in allowed:
                r.fail("E3.5", s3, "{} says {} but none of the line's data ({}) has that value".format(
                    sid, n["raw"], ", ".join(line_uses) or "none"))
            g = dc.grouping_problem(n["digits"])
            if g:
                r.fail("E3.5", s3, "{} '{}': {}".format(sid, n["raw"], g))
        for f in dc.form_names(vo):
            if f not in forms:
                r.fail("E3.14", s3, "{} names Form {}, which isn't in brand/epfo-forms.json: check the form on EPFO's "
                                    "site and add it there with its source".format(sid, f))
        for h in line.get("highlights", []):
            if h not in vo:
                r.fail("E3.6", s3, "{}: highlight '{}' is not in the line".format(sid, h))
        if re.search(r"\d", line.get("tts", "")):
            r.warn("E3.10", s3, "{}: the TTS line still has digits; write numbers as spoken words".format(sid))
        elif line.get("tts"):
            # the voice must say exactly the caption's numbers, however a word is respelled to fix how it sounds
            said = spoken.spoken_numbers(line["tts"])
            want = spoken.expected_numbers(vo)
            allowed = set(want) | spoken.word_numbers(vo) | {1} | dc.form_numbers(vo)
            missing = [n for n in want if n not in said]
            extra = sorted({n for n in said if n not in allowed}, key=float)
            if missing:
                r.fail("E3.13", s3, "{}: the caption says {} but the voice text (tts) doesn't say it".format(
                    sid, ", ".join(dc.indian(n) for n in missing)))
            if extra:
                r.fail("E3.13", s3, "{}: the voice text (tts) says {}, which the caption doesn't".format(
                    sid, ", ".join(dc.indian(n) for n in extra)))
        if ch == "share" and "bhejo" not in vo.lower():
            r.fail("E3.7", s3, "{}: the share line must ask people to send it ('... bhejo')".format(sid))
        if ch == "signoff" and vo.strip() != brand.get("signoff"):
            r.fail("E3.8", s3, "{}: the sign-off must be exactly \"{}\"".format(sid, brand.get("signoff")))
    missing = [c for c in chapters if c not in seen_chapters]
    if script and missing:
        r.fail("E3.2", s3, "missing chapters: {}".format(", ".join(missing)))
    w_lo, w_hi = rules.get("script_words", [150, 175])
    if script and not (w_lo <= words <= w_hi):
        r.fail("E3.3", s3, "the script has {} words; the target is {}–{}".format(words, w_lo, w_hi))
    if script:
        wps = rules.get("words_per_second", 1.85)
        est = words / wps + rules.get("tail_seconds", 3)
        r.info("E3.3", s3, "{} words ≈ {:.0f} s of voice at {} words/s, plus a {} s tail ≈ {:.0f} s".format(
            words, words / wps, wps, rules.get("tail_seconds", 3), est))
        if not (lo <= est <= hi):
            r.warn("E3.3", s3, "estimated length {:.0f} s is outside {}–{} s; read it aloud and time it".format(est, lo, hi))
        if shots and abs(est - t) > 5:
            r.warn("E3.3", s3, "estimated length {:.0f} s and the shot timeline {:.0f} s differ by more than 5 s".format(est, t))

    # ---- the other hooks a person can pick instead of the first line: their numbers come from data too
    options = ep.get("hook_options")
    if options is not None and not (isinstance(options, list) and all(isinstance(h, str) for h in options)):
        r.fail("E3.15", s3, "hook_options must be a list of lines, like [\"…\", \"…\"]")
    elif options:
        every = allowed_for(list(data), data, always)
        for i, h in enumerate(options):
            for n in dc.extract_numbers(h):
                if n["canon"] not in every:
                    r.fail("E3.15", s3, "hook option {} says {}, which isn't a value in data".format(chr(65 + i), n["raw"]))
                g = dc.grouping_problem(n["digits"])
                if g:
                    r.fail("E3.15", s3, "hook option {} '{}': {}".format(chr(65 + i), n["raw"], g))

    # ---- example numbers are labelled where they first appear (in the line, or on that shot's cards)
    units = [(l, shot_by_id.get(l.get("shot"), {})) for l in script] or [({}, sh) for sh in shots]
    for iid, it in data.items():
        if it.get("kind") != "assumption":
            continue
        first = next(((l, sh) for l, sh in units if iid in l.get("uses", []) or iid in sh.get("uses", [])), None)
        if first is None:
            continue
        l, sh = first
        texts = [l.get("vo", "")] + sh.get("card_text", [])
        if not label_present(texts, labels):
            where = l.get("shot") or sh.get("id")
            if shots:
                r.fail("E3.9", s3, "{} first shows the example number '{}' without a label; add 'maan lo' to the line or MAAN LO / EXAMPLE to a card".format(where, iid))
            else:   # the cards aren't written yet (step N4), and one of them may carry the label
                r.warn("E3.9", s3, "{} first shows the example number '{}': say 'maan lo' in the line, or put MAAN LO / EXAMPLE on that shot's card when you write the shots".format(where, iid))
    return shot_by_id


def check_post(ep, data, brand, r):
    s = "10-publish"
    rules = brand.get("rules", {})
    post = ep.get("post") or {}
    cap = post.get("caption", "")
    if not cap:
        r.fail("E10.1", s, "post.caption is empty")
    if len(cap) > rules.get("caption_max_chars", 2200):
        r.fail("E10.1", s, "the caption has {} characters; the limit is {}".format(len(cap), rules.get("caption_max_chars", 2200)))
    tags = re.findall(r"#\w+", cap)
    if tags != post.get("hashtags", []):
        r.fail("E10.2", s, "post.hashtags must match the hashtags written in the caption")
    if len(tags) > rules.get("max_hashtags", 5):
        r.fail("E10.2", s, "{} hashtags; use at most {}".format(len(tags), rules.get("max_hashtags", 5)))
    allowed = allowed_for(list(data.keys()), data, rules.get("always_allowed_numbers", [0, 1, 2, 3]))
    cover = post.get("cover") or {}
    forms = dc.epfo_forms()
    for txt in [cap] + cover.get("lines", []) + [cover.get("stamp", "")]:
        for n in dc.extract_numbers(re.sub(r"#\w+", "", txt)):
            if n["canon"] not in allowed:
                r.fail("E10.3", s, "the post uses {} but no data item has that value".format(n["raw"]))
        for f in dc.form_names(re.sub(r"#\w+", "", txt)):
            if f not in forms:
                r.fail("E10.3", s, "the post names Form {}, which isn't in brand/epfo-forms.json".format(f))
    if not post.get("pinned_comment"):
        r.fail("E10.1", s, "post.pinned_comment is empty")
    if not cover.get("lines"):
        r.fail("E10.1", s, "post.cover.lines is empty")


def check_prompts_file(ep_dir, r):
    try:
        import build_prompts
        for name, fn in (("prompts.md", build_prompts.render), ("prompts-writing.md", build_prompts.render_writing)):
            path = ep_dir / name
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != fn(ep_dir):
                r.fail("E4.10", "04-shots", "{} is out of date or missing. Run: python3 tools/build_prompts.py {}".format(
                    name, dc.rel(ep_dir)))
    except Exception as e:  # noqa: BLE001
        r.fail("E4.10", "04-shots", "the prompt files can't be built: {}".format(e))


# ---------------------------------------------------------------- gates

def check_gates(ep_dir, ep, status, brand, r):
    approvers = brand.get("approvers") or []
    steps = status.get("steps") or {}
    shots_status = status.get("shots") or {}
    prev_ok = True
    rows = []
    for s in dc.STEPS:
        sid = s["id"]
        st = steps.get(sid)
        if st is None:
            r.fail("G1", sid, "status.json has no entry for {}".format(sid))
            rows.append((sid, s["name"], "missing", "—", "—"))
            prev_ok = False
            continue
        state = st.get("state")
        if state not in dc.STEP_STATES:
            r.fail("G1", sid, "{}: state '{}' is not valid".format(sid, state))
        fails_before = len(r.of("fail"))
        if r.of("fail", sid):
            auto = "fail"
        elif r.of("pending", sid):
            auto = "waiting"
        elif state == "todo" and not any(i["step"] == sid for i in r.items):
            auto = "—"
        else:
            auto = "pass"
        appr = st.get("approval")
        if state == "passed":
            if not prev_ok:
                r.fail("G2", sid, "{} is marked passed, but an earlier step isn't passed".format(sid))
            if r.of("fail", sid):
                r.fail("G3", sid, "{} is marked passed, but its checks fail".format(sid))
            if r.of("pending", sid):
                r.fail("G3", sid, "{} is marked passed, but it still waits for a person".format(sid))
            if s["lock"] == "section":
                if not appr or not appr.get("hash"):
                    r.fail("G4", sid, "{} is marked passed without an approval record".format(sid))
                elif appr["hash"] != dc.section_hash(dc.locked_content(ep, sid)):
                    r.fail("G5", sid, "{} changed after it was approved. Check it again and re-approve.".format(sid))
            elif s["lock"] == "file":
                if not appr or not appr.get("file") or not appr.get("hash"):
                    r.fail("G4", sid, "{} is marked passed without a file and hash".format(sid))
                else:
                    f = dc.ROOT / appr["file"]
                    if f.exists():
                        if dc.file_hash(f) != appr["hash"]:
                            r.fail("G5", sid, "{}: {} changed after it was approved".format(sid, appr["file"]))
                    else:
                        r.warn("G6", sid, "{}: {} is not in the repo, so its hash wasn't re-checked here".format(sid, appr["file"]))
            elif s["lock"] == "shots":
                for shot in ep.get("shots", []):
                    entry = (shots_status.get(shot["id"]) or {}).get(s["kind"]) or {}
                    if entry.get("state") != "passed":
                        r.fail("G3", sid, "{} is marked passed, but {} {} isn't".format(sid, shot["id"], s["kind"]))
            if s["human"] and appr:
                by = appr.get("by", "")
                if not by or by.lower() in ("auto", "auto-check", "claude", "muse"):
                    r.fail("G4", sid, "{} needs a person's name in approval.by".format(sid))
                elif approvers and by not in approvers:
                    r.fail("G4", sid, "{}: '{}' is not in brand.json approvers".format(sid, by))
        # per-shot approvals are re-checked whatever the step state
        if s["lock"] == "shots":
            for shot in ep.get("shots", []):
                entry = (shots_status.get(shot["id"]) or {}).get(s["kind"]) or {}
                if entry.get("state") not in dc.SHOT_STATES:
                    r.fail("G1", sid, "{} {}: state '{}' is not valid".format(shot["id"], s["kind"], entry.get("state")))
                if entry.get("tries", 0) > brand.get("rules", {}).get("max_tries_per_shot", 2) and entry.get("mode") == "muse":
                    r.warn("G7", sid, "{} {} failed {} times with Muse text; switch to the clean-plate route".format(
                        shot["id"], s["kind"], entry["tries"]))
                if entry.get("state") == "passed":
                    a = entry.get("approval") or {}
                    if a.get("spec_hash") != dc.shot_spec_hash(shot, s["kind"]):
                        r.fail("G5", sid, "{} changed after its {} was approved. Make and approve it again.".format(shot["id"], s["kind"]))
                    if a.get("file"):
                        f = dc.ROOT / a["file"]
                        if f.exists() and dc.file_hash(f) != a.get("file_hash"):
                            r.fail("G5", sid, "{}: {} changed after it was approved".format(shot["id"], a["file"]))
                    if not a.get("by"):
                        r.fail("G4", sid, "{} {} is passed without a person's name".format(shot["id"], s["kind"]))
        if sid == "09-final-qa" and state == "passed" and appr:
            editor = ((steps.get("08-assembly") or {}).get("approval") or {}).get("by")
            if editor and editor == appr.get("by"):
                r.warn("G8", sid, "final QA was signed off by the same person who approved the assembly ({}); a second person catches more".format(editor))
        step_ok = state == "passed" and len(r.of("fail")) == fails_before
        human = "—"
        if s["human"]:
            human = "{} · {}".format(appr.get("by"), appr.get("at", "")[:10]) if appr else ("waiting" if state == "needs_human" else "—")
        rows.append((sid, s["name"], state, auto, human))
        prev_ok = prev_ok and step_ok
    r.steps = rows
    r.next_action = next_action(ep_dir, ep, status, r)


def next_action(ep_dir, ep, status, r):
    rel = dc.rel(ep_dir)
    shots_status = status.get("shots") or {}
    for s in dc.STEPS:
        sid = s["id"]
        st = (status.get("steps") or {}).get(sid, {})
        if st.get("state") == "passed" and not r.of("fail", sid):
            continue
        guide = "pipeline/{}.md".format(sid)
        if r.of("fail", sid):
            return "Fix the failures in {} ({}), then run the checks again.".format(sid, guide)
        if r.of("pending", sid):
            first = r.of("pending", sid)[0]["msg"]
            return "{} is waiting for a person: {}".format(sid, first)
        if s["lock"] == "shots":
            todo = [x["id"] for x in ep.get("shots", []) if ((shots_status.get(x["id"]) or {}).get(s["kind"]) or {}).get("state") != "passed"]
            if todo:
                return "{}: make and check {} for {} ({}). Approve each with: python3 tools/approve.py shot {} <SHOT> {} --file <path> --by <name>".format(
                    sid, s["kind"] + "s", ", ".join(todo[:6]) + (" …" if len(todo) > 6 else ""), guide, rel, s["kind"])
        state = st.get("state", "todo")
        if s["lock"] == "file":
            return "{}: follow {}, then a person approves with: python3 tools/approve.py file {} {} --file <path> --by <name>".format(sid, guide, rel, sid)
        if state == "todo":
            return "{}: do this step with {}, run the checks, then set its state to drafted in status.json.".format(sid, guide)
        if s["human"]:
            return "{} is ready for a person to approve: python3 tools/approve.py step {} {} --by <name>".format(sid, rel, sid)
        return "{} passes its checks. Mark it done with: python3 tools/approve.py step {} {}".format(sid, rel, sid)
    return "All steps are done."


# ---------------------------------------------------------------- run

# Focus shows how to do something on the screen itself (styles/focus/STYLE.md)
FOCUS_CARDS = {"screen", "headline", "route", "flow", "checklist", "outro"}
FOCUS_DO = {"tap", "write", "text", "check", "look", "toggle", "to", "open", "close", "show", "hold", "select", "item",
            "label", "label_of", "tone", "done", "list", "scroll", "go", "on", "at", "lift"}
SOURCE_KINDS = {"official", "video", "article", "post", "forum"}


def said_word(word, line):
    """True when the line says a word starting with `word`, as the build finds an "on" word (build_reel.word_time)."""
    norm = lambda w: re.sub(r"[^0-9a-z₹%]", "", str(w).lower())   # noqa: E731
    q = norm(word)
    return bool(q) and any(norm(w).startswith(q) for w in str(line or "").split())


def is_sample(ep_dir):
    try:
        return Path(ep_dir).resolve().relative_to(dc.ROOT).parts[0] == "styles"
    except ValueError:
        return False


def check_screens(ep_dir, ep, brand, r):
    """Focus: every screen drawn from a description the newest official pages back (two sources at least, one of them
    official, read this month, one of them dated in the last two months), every part a line uses on its screen, and
    every touch on a word of its line."""
    path = ep_dir / "reel.json"
    if not path.exists() or not ep.get("shots"):
        return
    try:
        reel = dc.load_json(path)
    except Exception:  # noqa: BLE001  (the reel check reports a broken reel.json)
        return
    s = "04-shots"
    try:
        import screens as K                                 # the screens the build draws (needs Pillow)
    except Exception:  # noqa: BLE001
        K = None
    screens = reel.get("screens") or {}
    if not isinstance(screens, dict) or not screens:
        r.fail("E4.22", s, "reel.json has no screens: a Focus reel shows each step on the screen itself, drawn from its "
                           "description in reel.json → screens (prompts-writing.md → Step 4)")
        return
    rules = brand.get("rules") or {}
    source_days, seen_days = int(rules.get("source_days") or 60), int(rules.get("seen_days") or 30)
    fresh = not is_sample(ep_dir) and not topics.posted_record(ep_dir)   # a sample or a live reel never goes stale
    fetched = {}
    if (ep_dir / "research-sources.json").exists():
        try:
            fetched = dc.load_json(ep_dir / "research-sources.json").get("sources") or {}
        except Exception:  # noqa: BLE001
            fetched = {}
    today = datetime.date.fromisoformat(dc.today())

    def day(text):
        try:
            return datetime.date.fromisoformat(str(text or "")[:10])
        except ValueError:
            return None
    ids = {}
    for name, spec in screens.items():
        if not isinstance(spec, dict):
            r.fail("E4.22", s, "screen \"{}\" must be an object: device, url or title, parts".format(name))
            continue
        if spec.get("src"):
            if not (ep_dir / spec["src"]).exists():
                r.fail("E4.22", s, "screen \"{}\": its picture {} isn't in the episode folder".format(name, spec["src"]))
            if not spec.get("targets"):
                r.fail("E4.22", s, "screen \"{}\" is a picture: give \"targets\", each part the reel uses with its box "
                                   "in the picture's pixels [x0, y0, x1, y1]".format(name))
            ids[name] = set((spec.get("targets") or {}).keys())
        elif K is not None:
            for problem in K.check_spec(spec, name):
                r.fail("E4.22", s, problem)
            try:
                ids[name] = K.all_ids(spec)
            except Exception as e:  # noqa: BLE001
                r.fail("E4.22", s, "screen \"{}\" can't be drawn: {}".format(name, e))
        # where it was seen: the newest official pages and tutorials, never one old video
        sources = [x for x in spec.get("sources") or [] if isinstance(x, dict)]
        if len(sources) < 2 or not any(x.get("kind") == "official" for x in sources):
            r.fail("E4.23", s, "screen \"{}\" needs two sources at least, one of them official (the app's own help, "
                               "developer or product pages): every screen is drawn as the newest pages show it".format(name))
        dated = []
        for x in sources:
            url = str(x.get("url") or "")
            if x.get("kind") not in SOURCE_KINDS:
                r.fail("E4.23", s, "screen \"{}\": source {} needs \"kind\": one of {}".format(
                    name, url or "(no url)", ", ".join(sorted(SOURCE_KINDS))))
            if not re.match(r"https://\S+$", url):
                r.fail("E4.23", s, "screen \"{}\": every source needs its link (https://…)".format(name))
                continue
            seen = day(x.get("seen"))
            if seen is None:
                r.fail("E4.23", s, "screen \"{}\": source {} needs \"seen\", the day it was read (YYYY-MM-DD)".format(
                    name, url))
            elif fresh and (today - seen).days > seen_days:
                r.fail("E4.23", s, "screen \"{}\": source {} was read on {}, more than {} days ago: open it again and "
                                   "check the screen still looks like that, then update \"seen\"".format(
                                       name, url, seen.isoformat(), seen_days))
            when = day(x.get("updated") or x.get("published"))
            got = fetched.get(url) or {}
            if got.get("updated") and day(got["updated"]) and (when is None or day(got["updated"]) > when):
                if when is not None and fresh:
                    r.warn("E4.26", s, "screen \"{}\": {} changed on {}, after it was read: open it again and check "
                                       "the screen against it".format(name, url, got["updated"]))
                when = day(got["updated"])
            if when is not None:
                dated.append(when)
            if got and got.get("ok") is False and got.get("status") in (404, 410):
                r.fail("E4.23", s, "screen \"{}\": {} is gone ({}): find the page that replaced it".format(
                    name, url, got.get("status")))
        if fresh and sources and not any((today - d).days <= source_days for d in dated):
            r.fail("E4.23", s, "screen \"{}\": none of its sources shows a date in the last {} days, so the screen may "
                               "be an old version: add a page or a video from the last {} days that shows it (on "
                               "YouTube, sort by upload date), with its \"updated\" or \"published\" date".format(
                                   name, source_days, source_days))
        texts = " ".join(str((fetched.get(str(x.get("url"))) or {}).get("text") or "") for x in sources).lower()
        if K is not None and not spec.get("src") and len(texts) > 400:
            missing = [lab for lab in K.labels_of(spec) if " ".join(lab.lower().split()) not in " ".join(texts.split())]
            if missing:
                r.warn("E4.26", s, "screen \"{}\": its sources never say {}: check each against the newest official "
                                   "page, and write the name exactly as the app shows it".format(
                                       name, ", ".join("\"{}\"".format(m) for m in missing[:8])))
    lines = {l.get("shot"): str(l.get("vo") or "") for l in ep.get("script") or [] if isinstance(l, dict)}
    order = [sh.get("id") for sh in ep.get("shots") or []]
    current = None
    for sid in order:
        line = lines.get(sid, "")
        for el in (reel.get("shots") or {}).get(sid) or []:
            if not isinstance(el, dict):
                continue
            t = el.get("type")
            if t not in FOCUS_CARDS:
                r.fail("E4.24", s, "{}: \"{}\" isn't a card of the Focus style: {}".format(
                    sid, t, ", ".join(sorted(FOCUS_CARDS))))
                continue
            words = [el.get("on")] + [x.get("on") for key in ("do", "items", "pills", "steps") for x in el.get(key) or []
                                      if isinstance(x, dict)] + [(el.get("result") or {}).get("on")
                                                                 if isinstance(el.get("result"), dict) else None]
            for w in words:
                if w and not said_word(w, line):
                    r.fail("E4.24", s, "{}: \"on\": \"{}\" isn't a word of its line (\"{}\"): use a word the line "
                                       "says, where that touch or card should come".format(sid, w, line))
            if t != "screen":
                continue
            name = el.get("screen")
            if name not in screens:
                r.fail("E4.24", s, "{}: screen \"{}\" isn't in reel.json → screens ({})".format(
                    sid, name, ", ".join(sorted(screens))))
                continue
            current = name
            known = ids.get(name)
            spec = screens[name] if isinstance(screens[name], dict) else {}
            overlays = set((spec.get("overlays") or {}).keys())
            if el.get("focus") and known is not None and el["focus"] not in known:
                r.fail("E4.24", s, "{}: focus \"{}\" isn't a part of screen \"{}\": its ids are {}".format(
                    sid, el["focus"], name, ", ".join(sorted(known))))
            here = name                                     # the page an action happens on: a "go" moves on
            for a in el.get("do") or []:
                if not isinstance(a, dict):
                    r.fail("E4.24", s, "{}: every action in \"do\" is an object, like {{\"tap\": \"save\", \"on\": "
                                       "\"dabao\"}}".format(sid))
                    continue
                if here != name:
                    known = ids.get(here)
                    overlays = set(((screens.get(here) if isinstance(screens.get(here), dict) else {}).get("overlays")
                                    or {}).keys())
                odd = sorted(set(a) - FOCUS_DO)
                if odd:
                    r.fail("E4.24", s, "{}: an action can't say {}: it can {}".format(
                        sid, ", ".join(odd), ", ".join(sorted(FOCUS_DO - {"on", "at", "text", "to", "item", "hold",
                                                                         "label_of", "tone", "list", "lift"}))))
                for key in ("tap", "write", "check", "look", "select", "label_of"):
                    if a.get(key) and known is not None and a[key] not in known:
                        r.fail("E4.24", s, "{}: {} \"{}\" isn't a part of screen \"{}\": its ids are {}".format(
                            sid, key, a[key], here, ", ".join(sorted(known))))
                for key in ("open", "close", "show"):
                    if a.get(key) and a[key] not in overlays:
                        r.fail("E4.24", s, "{}: {} \"{}\" isn't one of screen \"{}\"'s overlays ({})".format(
                            sid, key, a[key], here, ", ".join(sorted(overlays)) or "none"))
                if a.get("go") and a["go"] not in screens:
                    r.fail("E4.24", s, "{}: go \"{}\" isn't a screen in reel.json → screens".format(sid, a["go"]))
                elif a.get("go"):
                    here = a["go"]
                if a.get("write") and not str(a.get("text") or "").strip():
                    r.fail("E4.24", s, "{}: write \"{}\" needs \"text\", the words typed in".format(sid, a["write"]))
    if current is None:
        r.fail("E4.24", s, "no line shows a screen: a Focus reel walks through the steps on the screen itself")
    live = bool(topics.posted_record(ep_dir))
    for sid, msg in walk_problems(ep, reel, screens):
        (r.warn if live else r.fail)("E4.27", s, "{} {}".format(sid, msg))
    route = reel.get("route") or []
    for step in route if isinstance(route, list) else []:
        if not isinstance(step, dict) or step.get("from") not in order:
            r.fail("E4.25", s, "route: each stop is {\"label\": \"…\", \"from\": \"<the shot where it starts>\"}, "
                               "its shot one of the episode's")
        elif len(str(step.get("label") or "")) > 12:
            r.warn("E4.25", s, "route: \"{}\" is long for a stop on the logo's row: 12 letters at most (one or two "
                               "words)".format(step.get("label")))
    if isinstance(route, list) and len(route) > 5:
        r.warn("E4.25", s, "route: {} stops crowd the logo's row: 5 at most".format(len(route)))
    for name, spec in screens.items():
        for text in personal_numbers(spec):
            r.fail("E4.28", s, "screen \"{}\" shows \"{}\", which looks like a real person's number (a UAN, Aadhaar, "
                               "PAN, mobile, bank account or member ID): a drawn screen shows nobody's details. Mask it "
                               "(XXXX XXXX 1234, ABCDE####F, XXXXXX7890) or leave it out".format(name, text))


# A person's numbers, as a drawn screen must never show them in full: a 12-digit UAN or Aadhaar, a 10-digit mobile,
# a PAN, a long bank account, or a member ID (MH/BAN/12345/000/0012345). Masked ones (XXXX XXXX 1234) are fine.
PERSONAL = [re.compile(p) for p in (r"(?<![\dX])\d{4}\s?\d{4}\s?\d{4}(?![\dX])",   # UAN or Aadhaar
                                    r"(?<![\dX])[6-9]\d{9}(?![\dX])",                    # a mobile number
                                    r"\b[A-Z]{5}\d{4}[A-Z]\b",                           # a PAN
                                    r"(?<![\dX])\d{9,18}(?![\dX])",                      # a bank account
                                    r"\b[A-Z]{2}/?[A-Z]{3}/?\d{5,7}/?\d{3}/?\d{5,7}\b")]   # a member ID


def personal_numbers(spec):
    """The texts in a drawn screen's description (its parts, items and overlays) that look like a person's number."""
    out, seen = [], set()

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and x not in seen:
            seen.add(x)
            if any(p.search(x) for p in PERSONAL):
                out.append(x)
    walk({k: v for k, v in spec.items() if k not in ("sources", "url", "accent")})
    return out


def walk_problems(ep, reel, screens):
    """Where a Focus reel jumps to a page the viewer never saw being opened, or taps a menu item that leads nowhere:
    [(shot, what)]. The walk starts at the first "steps" line (else the first screen after the route card, else the
    first after the hook): before it, the hook and the why may show any page; from there every page is reached on
    screen, by a tap that goes to it or by its address typed in the browser bar. The share line and the sign-off are
    left out."""
    lines = {l.get("shot"): l for l in ep.get("script") or [] if isinstance(l, dict)}
    order = [sh.get("id") for sh in ep.get("shots") or [] if isinstance(sh, dict)]
    shots = reel.get("shots") or {}

    def screen_of(sid):
        return next((el for el in shots.get(sid) or [] if isinstance(el, dict) and el.get("type") == "screen"), None)
    chapter = {sid: str((lines.get(sid) or {}).get("chapter") or "") for sid in order}
    begin = next((sid for sid in order if chapter[sid] == "steps" and screen_of(sid)), None)
    if begin is None:
        routed = False
        for sid in order:
            if any(isinstance(el, dict) and el.get("type") == "route" for el in shots.get(sid) or []):
                routed = True
            elif routed and screen_of(sid):
                begin = sid
                break
    if begin is None:
        begin = next((sid for sid in order[1:] if screen_of(sid)), None)
    out, walking, last = [], False, None
    for sid in order:
        el = screen_of(sid)
        walking = walking or sid == begin
        if el is None:
            continue
        name, aside = el.get("screen"), chapter[sid] in ("share", "signoff")
        if walking and sid != begin and not aside and last and name != last:
            out.append((sid, "opens on page \"{0}\", but the viewer was last on \"{1}\" and nothing on screen took them "
                             "there: start the line on \"{1}\" and tap what opens \"{0}\", on its word ({{\"tap\": "
                             "\"<the menu item, tab or link>\", \"go\": \"{0}\", \"on\": \"…\"}}), or type its address "
                             "in the browser bar ({{\"write\": \"url\", \"text\": \"<its address>\", \"on\": \"…\"}}, "
                             "then {{\"go\": \"{0}\", \"on\": \"…\"}}). Every page in the walk is reached on screen, the "
                             "way the viewer gets there".format(name, last)))
        here = name
        for a in el.get("do") or []:
            if not isinstance(a, dict):
                continue
            tap = str(a.get("tap") or "")
            spec = screens.get(here) if isinstance(screens.get(here), dict) else {}
            if walking and not aside and "/" in tap and not (a.get("go") or a.get("open")):
                owner, item = tap.split("/", 1)
                part = next((p for p in spec.get("parts") or [] if isinstance(p, dict) and p.get("id") == owner), None)
                if part and part.get("kind") == "nav":
                    if item == part.get("active"):
                        out.append((sid, "taps \"{}\", the page the viewer is already on: start the walk on the page "
                                         "they see first when they open the app (a screen of its own), and let this "
                                         "tap take them here (\"go\")".format(tap)))
                    else:
                        out.append((sid, "taps the menu item \"{}\" and no page opens: a menu item opens its page, so "
                                         "add \"go\" with that page's screen (described in reel.json → screens), or "
                                         "\"open\" when it only opens a submenu".format(tap)))
            if a.get("go") in screens:
                here = a["go"]
        if not aside:
            last = here
    return out


FIRST_FRAME_COMPANIONS = {"headline", "screen"}


def check_first_frame(ep_dir, ep, r):
    """Most people scroll with the sound off, so a Focus reel's first frame already shows the hook's words: a
    headline card, 6 words at most, over the screen's first look (E4.20)."""
    path = ep_dir / "reel.json"
    if not path.exists():
        return
    try:
        reel = dc.load_json(path)
    except Exception:  # noqa: BLE001  (the reel check reports a broken reel.json)
        return
    shots = ep.get("shots") or []
    first = shots[0].get("id", "S01") if shots else "S01"

    def at_start(el):
        try:
            return "on" not in el and float(el.get("at", 0.1)) <= 0.05 and el.get("in") == "none"
        except (TypeError, ValueError):
            return False

    els = [el for el in (reel.get("shots") or {}).get(first) or [] if isinstance(el, dict)]
    heads = [el for el in els if el.get("type") == "headline" and at_start(el)]
    if not heads:
        r.fail("E4.20", "04-shots", "{}: the first frame must show the hook's words, as a headline card: 6 words at most "
                                    "in giant letters, over the screen ({{\"type\": \"headline\", \"text\": \"…\", "
                                    "\"accent\": \"…\", \"at\": 0, \"in\": \"none\"}}, its words in card_text)".format(first))
        return
    words = len(str(heads[0].get("text") or "").split())
    if words > 6:
        r.fail("E4.20", "04-shots", "{}: the headline has {} words: it's read in a glance, so 6 at most (the cover's words "
                                    "work)".format(first, words))
    others = sorted({el.get("type") for el in els} - FIRST_FRAME_COMPANIONS)
    if others:
        r.warn("E4.20", "04-shots", "{}: the headline shares the first shot with {}: give it the screen only, and bring "
                                    "{} in on the next line".format(first, ", ".join(others),
                                                                    "it" if len(others) == 1 else "them"))


def validate_episode(ep_dir, brand):
    r = Report(ep_dir.name)
    try:
        ep = dc.load_json(ep_dir / "episode.json")
    except Exception as e:  # noqa: BLE001
        r.fail("E0", None, "episode.json can't be read: {}".format(e))
        return r, None, None
    try:
        status = dc.load_json(ep_dir / "status.json")
    except Exception as e:  # noqa: BLE001
        r.fail("G1", None, "status.json can't be read: {}".format(e))
        status = {"steps": {}, "shots": {}}
    brand = dc.for_style(brand, ep)          # the theme's chapters and rules: the paper story, or Focus
    if brand.get("style") not in (brand.get("styles") or {"paper": 1}):
        r.fail("E1.3", "01-brief", "style '{}' isn't one of the themes: {}".format(
            brand.get("style"), ", ".join(brand.get("styles") or ["paper"])))
    # Content is checked as soon as it's written (or once its step has started), so an episode
    # Muse writes is checked on its first upload. Only empty, untouched parts are skipped.
    states = {k: (v or {}).get("state", "todo") for k, v in (status.get("steps") or {}).items()}
    written = {
        "01-brief": any(v for k, v in (ep.get("brief") or {}).items() if k not in ("topic", "repeat_check")),
        "02-data": bool(ep.get("data")),
        "03-script": bool(ep.get("script")),
        "04-shots": bool(ep.get("shots")),
    }

    def active(step_id):
        return written.get(step_id, False) or states.get(step_id, "todo") != "todo"

    # Episodes made by tools/build_reel.py (a reel.json, or "route": "build") don't need the
    # keyframe and motion prompts or asset ids of the older AI-image route.
    build = ep.get("route") == "build" or (ep_dir / "reel.json").exists()

    data = check_data(ep, r) if active("02-data") else {d.get("id"): d for d in ep.get("data") or []}
    if active("01-brief"):
        check_brief(ep, r, brand.get("style"))
    run_script, run_shots = active("03-script"), active("04-shots")
    if run_script or run_shots:
        check_script_and_shots(ep, data, brand, r, run_script=run_script, run_shots=run_shots, build=build)
    if run_shots:
        check_prompts_file(ep_dir, r)
    if brand.get("style") == "focus" and run_shots:
        check_first_frame(ep_dir, ep, r)
        check_screens(ep_dir, ep, brand, r)
    if run_script or active("10-publish"):
        check_post(ep, data, brand, r)  # the post copy is written with the script
    # not a repeat of an earlier reel: topic, hook, script, photos, post (tools/topics.py)
    topics.check(ep_dir, ep, status, r)
    check_gates(ep_dir, ep, status, brand, r)
    return r, ep, status


def render(reports):
    out = []
    for r in reports:
        nf, nw, npnd = len(r.of("fail")), len(r.of("warn")), len(r.of("pending"))
        out.append("# Checks · {}".format(r.name))
        out.append("")
        out.append("**Result: {}** · {} failed · {} warnings · {} waiting for people".format("FAIL" if nf else "PASS", nf, nw, npnd))
        out.append("")
        for level, title in (("fail", "Failed"), ("pending", "Waiting for people"), ("warn", "Warnings"), ("info", "Notes")):
            items = r.of(level)
            if items:
                out.append("## " + title)
                out.append("")
                for i in items:
                    where = i["step"] or "brand"
                    out.append("- `{}` {} · {}".format(i["id"], where, i["msg"]))
                out.append("")
        if r.steps:
            out.append("## Steps")
            out.append("")
            out.append("| Step | Name | State | Auto checks | Person |")
            out.append("|---|---|---|---|---|")
            for row in r.steps:
                out.append("| " + " | ".join(str(c) for c in row) + " |")
            out.append("")
        if r.next_action:
            out.append("## Next")
            out.append("")
            out.append(r.next_action)
            out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episodes", nargs="*", help="episode folders (default: all)")
    ap.add_argument("--write", action="store_true", help="save checks/validate.md in each episode")
    ap.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    args = ap.parse_args()
    brand_report = Report("brand")
    b = check_brand(brand_report) or {}
    reports = [brand_report]
    for ep_dir in dc.episode_dirs(args.episodes):
        r, _, _ = validate_episode(ep_dir, b)
        reports.append(r)
        if args.write:
            (ep_dir / "checks").mkdir(exist_ok=True)
            (ep_dir / "checks" / "validate.md").write_text(render([r]), encoding="utf-8")
    if args.json:
        print(json.dumps([{"name": r.name, "items": r.items, "steps": r.steps, "next": r.next_action} for r in reports],
                         ensure_ascii=False, indent=2))
    else:
        print(render(reports))
    sys.exit(1 if any(r.of("fail") for r in reports) else 0)


if __name__ == "__main__":
    main()
