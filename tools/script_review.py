#!/usr/bin/env python3
"""The script review: a person reads a new reel's script and hook, and approves them, before anything else is made.

    python3 tools/script_review.py episodes/ep05-uan-activate              # where its review stands
    python3 tools/script_review.py episodes/ep05-uan-activate --write      # write its script page, script.md
    python3 tools/script_review.py episodes/ep05-uan-activate --cleared    # exit 0 only when the reel may be made

GitHub writes every new episode's script page, episodes/<episode>/script.md, from episode.json (new_episode.py
--prepare): the hook and the other hooks to pick from, every line as the captions show it and how it's said, every
number and rule with its source, the cover and the caption, and a version code for exactly this script. Muse sends the
page to a person and makes nothing else. When the person writes that the script is OK, Muse uploads
script-approved.json next to episode.json, with the version on the page they approved:

    {"version": "3fa9c1", "approved_by": "Divyank Sharma", "approved_on": "2026-11-16", "their_words": "script OK"}

(A person can also record it: python3 tools/approve.py script EPISODE --by NAME --words "script OK".)

Until a person in brand.json → approvers has approved the script that's in episode.json now, the report lists the
review for the person and checks nothing that comes after it, and GitHub builds no reel. If the script changes after
it's approved, it goes back to the person. The approval covers what the reel says and what hooks it: every line's
words (vo) and part (chapter), the cover and the trial hook. How a line is spelled for the voice (tts) and how it's
said (delivery) can change without it.

Reels before brand.json → rules → script_review_from ("ep05") were made before reviews began and don't need one.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402
import topics  # noqa: E402

PAGE = "script.md"
APPROVAL = "script-approved.json"
FIELDS = ("version", "approved_by", "approved_on", "their_words")


# ---------------------------------------------------------------- which reels, and which version

def first_reviewed():
    """The first episode number whose script a person reviews (brand.json → rules → script_review_from), or None."""
    m = re.search(r"\d+", str((dc.brand().get("rules") or {}).get("script_review_from") or ""))
    return int(m.group()) if m else None


def number(ep_dir):
    m = re.match(r"ep(\d+)", Path(ep_dir).name)
    return int(m.group(1)) if m else None


def reviewed(ep_dir):
    """True for an episode whose script a person reviews: script_review_from and every episode after it."""
    first, n = first_reviewed(), number(ep_dir)
    return first is not None and n is not None and n >= first


def _words(text):
    return " ".join(str(text or "").split())


def locked(ep):
    """What an approval is locked to: what the reel says (every line's words and part) and what hooks it (the cover
    and the trial hook). Not how a line is spelled for the voice (tts), or how it's said (delivery)."""
    post = ep.get("post") or {}
    cover = post.get("cover") or {}
    return {"lines": [[l.get("shot"), l.get("chapter"), _words(l.get("vo"))] for l in ep.get("script") or []],
            "cover": [[_words(x) for x in cover.get("lines") or []], _words(cover.get("stamp"))],
            "trial_hook": _words(post.get("trial_hook"))}


def version(ep):
    """A 6-letter code for exactly this script: it changes whenever its words do."""
    return dc.section_hash(locked(ep))[:6]


def clean(v):
    """A version as someone copied it ("`3FA9C1`", "version 3fa9c1"), as the code alone."""
    return re.sub(r"[^0-9a-f]", "", re.sub(r"(?i)\bversion\b", "", str(v or "")).lower())


# ---------------------------------------------------------------- where the review stands

def status(ep_dir, ep=None):
    """Where an episode's script review stands, as a dict:

    state    "not needed"       made before reviews began (script_review_from)
             "posted"           live; its script is final
             "no script"        nothing to review yet
             "waiting"          the script waits for a person
             "wrong file"       script-approved.json isn't filled in right (problems says how)
             "not an approver"  the name in it isn't in brand.json → approvers
             "changed"          the script changed after the person approved it
             "approved"         a person approved the script that's in episode.json now
    version  the version of the script in episode.json now (None without a script)
    record   script-approved.json, when it can be read
    problems what's wrong with script-approved.json
    cleared  True when the reel may be made: approved, or no review needed
    """
    ep_dir = Path(ep_dir)
    ep = ep if ep is not None else dc.load_json(ep_dir / "episode.json")
    out = {"state": None, "version": version(ep) if ep.get("script") else None, "record": None, "problems": [],
           "cleared": False}

    def done(state, cleared=False):
        out.update(state=state, cleared=cleared)
        return out

    if not reviewed(ep_dir):
        return done("not needed", True)
    if topics.posted_record(ep_dir):
        return done("posted", True)
    if not ep.get("script"):
        return done("no script")
    f = ep_dir / APPROVAL
    if not f.exists():
        return done("waiting")
    try:
        rec = dc.load_json(f)
        if not isinstance(rec, dict):
            raise ValueError("it isn't a JSON object")
    except Exception as e:  # noqa: BLE001
        out["problems"].append("{} can't be read: {}".format(APPROVAL, e))
        return done("wrong file")
    out["record"] = rec
    for k in FIELDS:
        if not str(rec.get(k) or "").strip():
            out["problems"].append("'{}' is empty".format(k))
    by = str(rec.get("approved_by") or "").strip()
    if by and not dc.is_person(by):
        out["problems"].append("approved_by is '{}': only the person who approved the script goes there".format(by))
    on = str(rec.get("approved_on") or "").strip()
    if on and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", on):
        out["problems"].append("approved_on '{}' isn't a date like 2026-11-16".format(on))
    if rec.get("version") and len(clean(rec["version"])) != 6:
        out["problems"].append("version '{}' isn't the 6-letter code on the script page".format(rec["version"]))
    if out["problems"]:
        return done("wrong file")
    approvers = dc.brand().get("approvers") or []
    if approvers and by not in approvers:
        return done("not an approver")
    if clean(rec["version"]) != out["version"]:
        return done("changed")
    return done("approved", True)


def cleared(ep_dir):
    """True when the reel may be made: its script is approved, or it needs no review."""
    return status(ep_dir)["cleared"]


def link(path):
    """The page on GitHub when running there, otherwise its path in the repo."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    return "https://github.com/{}/blob/main/{}".format(repo, dc.rel(path)) if repo else dc.rel(path)


# ---------------------------------------------------------------- the page a person reads

def _cell(text):
    return _words(text).replace("|", "\\|")


def _source(item):
    kind = item.get("kind")
    if kind in dc.SOURCED_KINDS:
        src = item.get("source") or "its source"
        src = "[{}]({})".format(src, item["source_url"]) if item.get("source_url") else src
        checked = "checked by {}".format(item["checked_by"]) if item.get("checked_by") else "**not checked yet**"
        return "{} · {}".format(src, checked)
    return {"assumption": "an example (the script says maan lo)",
            "derived": "worked out: {}".format(item.get("formula", "")),
            "input": "chosen for this reel",
            "advice": "advice"}.get(kind, kind or "")


def _status_lines(ep_dir, st, approvers):
    rec, v = st["record"] or {}, st["version"]
    state = st["state"]
    if state == "approved":
        return ["**Approved** by {} on {} (\"{}\"). The shots, photos and voice are made from this version.".format(
            rec.get("approved_by"), rec.get("approved_on"), _words(rec.get("their_words")))]
    if state == "posted":
        live = topics.posted_record(ep_dir) or {}
        return ["**Live** since {}: {}. This script is final.".format(live.get("on") or "?", live.get("url") or "")]
    if state == "not needed":
        return ["Made before script reviews began."]
    if state == "changed":
        return ["**Changed since {} approved version `{}`.** Read it again and reply (see *How to reply*): nothing "
                "new is made until you approve this version.".format(rec.get("approved_by"), clean(rec.get("version")))]
    if state == "not an approver":
        return ["**{} approved it, but isn't one of the approvers in brand/brand.json ({}).** An approver reads it and "
                "replies, or a person adds {} to the approvers.".format(rec.get("approved_by"), ", ".join(approvers),
                                                                        rec.get("approved_by"))]
    return ["**Waiting for your review.** Read the hook and the script, then reply (see *How to reply* at the end). "
            "Nothing else is made until you approve version `{}`.".format(v)]


def render(ep_dir, ep=None):
    """The script page a person reads before anything is made: episodes/<episode>/script.md."""
    ep_dir = Path(ep_dir)
    ep = ep if ep is not None else dc.load_json(ep_dir / "episode.json")
    st = status(ep_dir, ep)
    brand = dc.brand()
    rules = brand.get("rules") or {}
    script = ep.get("script") or []
    post = ep.get("post") or {}
    cover = post.get("cover") or {}
    words = sum(len(str(l.get("vo") or "").split()) for l in script)
    secs = words / rules.get("words_per_second", 2.6) + rules.get("tail_seconds", 3)

    out = ["<!-- GitHub writes this page from episode.json (tools/script_review.py). Change episode.json, not this page. -->",
           "# Script for review · {} · {}".format(ep.get("id") or ep_dir.name, ep.get("title") or ""), ""]
    if not script:
        return "\n".join(out + ["The script isn't written yet (MUSE.md → N3).", ""])
    out += ["**Version `{}`** · {} lines · {} words · about {:.0f} seconds".format(st["version"], len(script), words, secs), ""]
    out += _status_lines(ep_dir, st, brand.get("approvers") or []) + [""]

    # the hook
    hook = [l for l in script if l.get("chapter") == "hook"] or script[:1]
    out += ["## The hook", "", "The reel opens with {}:".format(" and ".join(l.get("shot", "?") for l in hook)), ""]
    for l in hook:
        out.append("> **{}**  ".format(_words(l.get("vo"))))
        out.append("> {}{}".format(l.get("shot", ""), " · said: " + _words(l.get("delivery")) if l.get("delivery") else ""))
        out.append(">")
    out.pop()
    options = [h for h in ep.get("hook_options") or [] if isinstance(h, str) and h.strip()]
    if options:
        out += ["", "Other hooks you can pick instead of {}:".format(hook[0].get("shot", "the first line")), ""]
        out += ["- **Hook {}** · {}".format(chr(65 + i), _words(h)) for i, h in enumerate(options)]
    if cover.get("lines") or cover.get("stamp"):
        out += ["", "The cover says **{}**{}.".format(" / ".join(_words(x) for x in cover.get("lines") or []),
                                                      ", with the stamp **{}**".format(_words(cover["stamp"])) if cover.get("stamp") else "")]
    if post.get("trial_hook"):
        out += ["", "Trial hook (another opening, for an Instagram trial reel): {}".format(_words(post["trial_hook"]))]
    out.append("")

    # the script, line by line
    said = any(l.get("delivery") for l in script)
    out += ["## The script", ""]
    out.append("| Line | Part | What the voice says (as the captions show it) |" + (" How to say it |" if said else ""))
    out.append("|---|---|---|" + ("---|" if said else ""))
    for l in script:
        row = "| {} | {} | {} |".format(l.get("shot", ""), l.get("chapter", ""), _cell(l.get("vo")))
        out.append(row + (" {} |".format(_cell(l.get("delivery"))) if said else ""))
    out.append("")

    # every number the lines use, and every rule the script relies on, with where it comes from
    used, first = {}, {}
    for i, l in enumerate(script):
        for u in l.get("uses") or []:
            used.setdefault(u, []).append(l.get("shot", ""))
            first.setdefault(u, i)
    items = [d for d in ep.get("data") or [] if d.get("id") in used or d.get("kind") == "rule"]
    items.sort(key=lambda d: first.get(d.get("id"), len(script)))   # the numbers in script order, then the rules
    if items:
        out += ["## Every number and rule, and where it comes from", "",
                "| In | What | Value | Where it comes from |", "|---|---|---|---|"]
        for item in items:
            shots = ", ".join(dict.fromkeys(used.get(item.get("id"), []))) or "—"
            value = "rule" if item.get("kind") == "rule" else dc.display(item)
            out.append("| {} | {} | {} | {} |".format(shots, _cell(item.get("label") or item.get("id")), _cell(value),
                                                      _source(item).replace("|", "\\|")))
        out.append("")

    # the post
    if post.get("caption") or post.get("pinned_comment"):
        out += ["## Caption and pinned comment", "", "These go with the post. You see them again before it's posted.", ""]
        if post.get("caption"):
            out += [("> " + x).rstrip() for x in str(post["caption"]).split("\n")] + [""]
        if post.get("pinned_comment"):
            out += ["**Pinned comment:** {}".format(_words(post["pinned_comment"])), ""]

    if st["state"] != "posted":
        out += ["## How to reply", "",
                "- **To change a line:** write its number and the new words, for example \"S03: FD safe hai, par byaaj "
                "sabse kam.\"",
                "- **To use another hook:** write \"Hook A\" (or B)." if options else
                "- **To change the hook:** write \"S01:\" and the new words.",
                "- **When it's right:** write \"script OK\".", "",
                "Any change makes a new version, and you get the new page to approve. Your OK counts for version `{}` "
                "only: if the script changes after that, it comes back to you.".format(st["version"]), ""]
    return "\n".join(out)


def write(ep_dir):
    """Write the script page of an episode whose script a person reviews. Returns True when the page changed."""
    ep_dir = Path(ep_dir)
    ep = dc.load_json(ep_dir / "episode.json")
    if not reviewed(ep_dir) or not ep.get("script"):
        return False
    text = render(ep_dir, ep)
    path = ep_dir / PAGE
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def describe(st):
    rec = st["record"] or {}
    return {"not needed": "made before script reviews began: no review needed",
            "posted": "posted: its script is final",
            "no script": "no script yet",
            "waiting": "waiting for a person to approve version {}".format(st["version"]),
            "wrong file": "{} isn't filled in right: {}".format(APPROVAL, "; ".join(st["problems"])),
            "not an approver": "approved by {}, who isn't in brand.json approvers".format(rec.get("approved_by")),
            "changed": "changed after {} approved version {}; now version {}".format(
                rec.get("approved_by"), clean(rec.get("version")), st["version"]),
            "approved": "approved by {} on {} (version {})".format(rec.get("approved_by"), rec.get("approved_on"),
                                                                   st["version"])}[st["state"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episodes", nargs="+", help="episode folders")
    ap.add_argument("--write", action="store_true", help="write each episode's script page (script.md)")
    ap.add_argument("--cleared", action="store_true", help="exit 0 only when every episode's reel may be made")
    a = ap.parse_args()
    ok = True
    for e in a.episodes:
        ep_dir = Path(e)
        if a.write and write(ep_dir):
            print("wrote", dc.rel(ep_dir / PAGE))
        st = status(ep_dir)
        print("{}: {}".format(ep_dir.name, describe(st)))
        ok = ok and st["cleared"]
    if a.cleared:
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
