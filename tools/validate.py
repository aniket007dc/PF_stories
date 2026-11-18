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

def check_brief(ep, r):
    """The brief plans one reel per chapter: the problem, why it happens, the steps that fix it,
    what to check before filing, and where to get help."""
    s = "01-brief"
    brief = ep.get("brief") or {}
    for key in ("topic", "viewer", "hook", "problem", "why", "steps", "check", "help", "share_target"):
        if not brief.get(key):
            r.fail("E1.1", s, "brief.{} is empty".format(key))
    for key, lo, hi, what in (("why", 1, 3, "reasons"), ("steps", 2, 5, "steps, in order")):
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
        if ch not in chapters:
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
        check_brief(ep, r)
    run_script, run_shots = active("03-script"), active("04-shots")
    if run_script or run_shots:
        check_script_and_shots(ep, data, brand, r, run_script=run_script, run_shots=run_shots, build=build)
    if run_shots:
        check_prompts_file(ep_dir, r)
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
