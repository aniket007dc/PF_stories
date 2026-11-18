#!/usr/bin/env python3
"""Check one episode from end to end and write what to fix: <episode>/checks/report.md

    python3 tools/check_episode.py episodes/ep02-uan-activate
    python3 tools/check_episode.py episodes/ep02-uan-activate --no-voice --no-ocr   # the files only, quick

GitHub runs this after every upload (Build reel). It checks, in order: the episode file (every number
traced to data, the script rules), reel.json (every word on screen from card_text), the voice lines
(every number and the brand name heard, nothing trimmed) and the finished reel (every card read back,
length, size, sound). The report starts with one RESULT line:

  FIX      Muse has something to fix. Each item says what is wrong and how to fix it.
           Fix them all, upload, and wait for the next report.
  WAITING  Nothing for Muse to fix: only a person's part is left (a fact to check, a line to listen to).
  PASS     Everything made so far is right.
  POSTED   The reel is live (posted.json). Never post it again; anything listed is for a person.

It also checks that the episode doesn't repeat an earlier reel (topic, hook, script, photos: tools/topics.py).
From brand.json → rules → script_review_from (ep05) on, a person reviews each reel's script and hook before anything
else is made (tools/script_review.py): until they approve the script that's in episode.json, the report lists the
review for the person and checks nothing that comes after the script.
It only reports; it never changes the episode.
"""
import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402
import script_review  # noqa: E402
import topics  # noqa: E402
import validate  # noqa: E402

AREA = {"E1": "Brief", "E2": "Data", "E3": "Script", "E4": "Shots", "E10": "Post", "E11": "Not a repeat",
        "G": "Approvals", "B": "Brand"}

HOW = {
    "E1": "Fill in that brief field, as pipeline/01-brief.md describes.",
    "E2.1": "Correct the data item as the message says.",
    "E2.2": "Make the value equal its formula (or correct the formula), then upload episode.json.",
    "E3.5": "Use the number from data exactly as written there, or say it without the number. Never add a number that isn't in data.",
    "E3.9": "Add \"maan lo\" to the line, or MAAN LO / EXAMPLE to that shot's card.",
    "E3.13": "Write the voice text (tts) so it says exactly the caption's numbers, in Devanagari words.",
    "E3.14": ("Name only a form listed in brand/epfo-forms.json, for what it's for there. If the reel needs another form, "
              "tell the person: they add it to brand/epfo-forms.json with its official source."),
    "E4.11": ("Name only a form listed in brand/epfo-forms.json. If the shot needs another form, tell the person: they "
              "add it to brand/epfo-forms.json with its official source."),
    "E3.15": ("Use only numbers from data in the other hooks, written the way data has them (₹ and Indian commas), or "
              "write that hook without the number."),
    "E3": "Change the line as the message says, keeping its meaning. Script changes need the person's OK before the next step.",
    "E4.3": "Use only numbers from that shot's data (uses), written with ₹ and Indian commas.",
    "E4": "Fix the shots in episode.json as the message says.",
    "E10": "Fix the post text as the message says.",
    "E11.1": ("Don't change the topic on your own: the person chose it. Tell the person it repeats {other} (see TOPICS.md) "
              "and suggest 3 topics that aren't in TOPICS.md, or a clearly new angle. Change the topic only to the one they "
              "pick. If they decide it's different enough, they record that: "
              "`python3 tools/approve.py repeat-ok {ep} {other} topic --by NAME --note \"why\"`."),
    "E11.2": ("Write a new line that doesn't echo {other}'s, keeping this reel's numbers and meaning. A new hook, first "
              "line or cover needs the person's OK."),
    "E11.3": ("Rewrite the lines it lists in new words for this reel's own topic: never copy lines from another reel. "
              "Same numbers, same meaning; the person approves the script again."),
    "E11.4": ("Make a new photo from a new prompt that shows a different scene (another person, place or angle) and save "
              "it under the same file name. Never reuse a photo or a prompt from another reel."),
    "E11.5": ("Every episode has its own number, and its folder is episodes/<id>-<slug>. Take the next free number from "
              "TOPICS.md, put the episode's files in the right folder and delete the wrong one."),
    "E11.6": ("Fill brief.repeat_check: in 'closest', the reel in TOPICS.md nearest to this topic (the reel the message "
              "names, if it names one); in 'different_because', one sentence on how this reel's question, numbers or "
              "viewer differ from it."),
    "E11.7": ("Correct posted.json: url = the post's Instagram link, posted_on = the day it went live (YYYY-MM-DD), "
              "post_it_from = the name of the person who wrote \"post it\"."),
    "E11": "Make this reel its own, as the message says (TOPICS.md lists every reel).",
}


def how_for(cid):
    for key in (cid, cid.rsplit(".", 1)[0]):
        if key in HOW:
            return HOW[key]
    return "Do what the message says."


def area_for(cid):
    for key in (cid.split(".")[0], cid[:1]):
        if key in AREA:
            return AREA[key]
    return "Episode"


class Report:
    def __init__(self):
        self.fix, self.person, self.look, self.todo, self.passed, self.notes = [], [], [], [], [], []
        self.posted = None
        self.script = None          # where the script review stands (tools/script_review.py)

    def result(self):
        if self.posted:
            return "POSTED"
        if self.fix:
            return "FIX"
        if self.person:
            return "WAITING"
        return "PASS"


# ---------------------------------------------------------------- the checks

def episode_file(ep_dir, rep):
    r, ep, status = validate.validate_episode(ep_dir, dc.brand())
    for it in r.of("fail"):
        cid = it["id"]
        if cid.startswith(("G", "B")):
            rep.person.append({"area": area_for(cid), "where": it.get("step") or "", "what": it["msg"],
                               "how": "A person looks at this: approvals and brand settings are theirs."})
        else:
            how = how_for(cid)
            if cid.startswith("E11"):
                m = re.search(r"\b(ep\d{2,3}-[a-z0-9-]+|old-\d+)\b", it["msg"].replace(ep_dir.name, ""))
                how = how.format(ep=dc.rel(ep_dir), other=m.group(1) if m else "the other reel")
            rep.fix.append({"area": area_for(cid), "where": cid, "what": it["msg"], "how": how})
    for it in r.of("pending"):
        m = re.search(r"\b(fact|rule) '([a-z0-9_]+)'", it["msg"])
        kind, fid = (m.group(1), m.group(2)) if m else ("fact", "<data id>")
        rep.person.append({"area": kind.capitalize(), "where": fid, "what": it["msg"],
                           "how": "A person opens the source, finds the {} and records it with "
                                  "`python3 tools/approve.py fact {} {} --by NAME`. Muse never marks a {} checked.".format(
                                      "number" if kind == "fact" else "rule", dc.rel(ep_dir), fid, kind)})
    for it in r.of("warn") + [i for i in r.of("info") if i["id"].startswith("E11")]:
        rep.notes.append({"area": area_for(it["id"]), "where": it["id"], "what": it["msg"]})
    if not r.of("fail"):
        rep.passed.append("Episode file: brief, data, script, shots and post")
    if not any(i["id"].startswith("E11") for i in r.of("fail")):
        rep.passed.append("Not a repeat: topic, hook, script and photos are this reel's own (TOPICS.md)")
    return ep, status


def script_gate(ep_dir, rep):
    """A new reel's script and hook go to a person before anything else is made (tools/script_review.py).
    Returns True when what comes after the script may be checked."""
    try:
        st = rep.script = script_review.status(ep_dir)
    except Exception:  # noqa: BLE001  (an episode.json that can't be read is already reported)
        return True
    state, v, rec = st["state"], st["version"], st["record"] or {}
    page = script_review.link(Path(ep_dir) / script_review.PAGE)
    if state in ("not needed", "posted"):
        return True
    if state == "approved":
        rep.passed.append("Script review: {} approved version {} on {}".format(rec["approved_by"], v, rec["approved_on"]))
        return True
    if state == "no script":
        rep.todo.append("the script and hook (MUSE.md → N3): a person reviews them before anything else is made")
        return False
    if state == "wrong file":
        rep.fix.append({"area": "Script review", "where": script_review.APPROVAL, "what": "; ".join(st["problems"]),
                        "how": "Write script-approved.json only after a person writes that the script is OK, exactly as "
                               "MUSE.md → N3 shows: version (the code on the script page they approved), approved_by (their "
                               "name), approved_on (YYYY-MM-DD) and their_words (what they wrote). If no person has "
                               "approved this script, delete the file and send them the script page."})
        return False
    if state == "not an approver":
        approvers = dc.brand().get("approvers") or []
        rep.person.append({"area": "Script review", "where": "version " + v,
                           "what": "{} approved the script, but isn't one of the approvers in brand/brand.json ({}).".format(
                               rec.get("approved_by"), ", ".join(approvers)),
                           "how": "An approver reads the script page, {}, and replies; or a person adds {} to approvers in "
                                  "brand/brand.json.".format(page, rec.get("approved_by"))})
        return False
    if state == "changed":
        what = ("The script changed after {} approved version {}. It's version {} now, and nothing new is made until a "
                "person approves it.".format(rec.get("approved_by"), script_review.clean(rec.get("version")), v))
    else:
        what = ("The script and hook (version {}) wait for a person to read and approve them. Nothing else is made until "
                "then: no shots or reel.json, photos, screenshots or voice lines.".format(v))
    rep.person.append({"area": "Script review", "where": "version " + v, "what": what,
                       "how": "Muse sends the person the script page, {}, and waits. The person replies with changes, or "
                              "writes that the script is OK. Muse makes exactly the changes they ask for and sends them the "
                              "new page; after their OK, Muse uploads script-approved.json with the version on the page they "
                              "approved (MUSE.md → N3).".format(page)})
    return False


def made_already(ep_dir, ep):
    """What has been made from the script already, for an episode whose script isn't approved (yet, or again)."""
    ep_dir = Path(ep_dir)
    made = []
    if (ep or {}).get("shots"):
        made.append("shots")
    if (ep_dir / "reel.json").exists():
        made.append("reel.json")
    for sub, what in (("media/photos", "photo"), ("media/screens", "screenshot")):
        n = len([f for f in (ep_dir / sub).glob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")])
        if n:
            made.append("{} {}{}".format(n, what, "s" if n > 1 else ""))
    n = len(list((ep_dir / "media" / "audio" / "lines").glob("S*")))
    if n:
        made.append("{} voice line{}".format(n, "s" if n > 1 else ""))
    if (ep_dir / "media" / "final" / "{}.mp4".format(ep_dir.name)).exists():
        made.append("the reel")
    return made


def reel_file(ep_dir, rep):
    if not (ep_dir / "reel.json").exists():
        rep.todo.append("reel.json (MUSE.md → N4)")
        return
    try:
        import build_reel
        reel = build_reel.Reel(ep_dir, use_voice=False)
    except ImportError:
        rep.notes.append({"area": "Reel file", "where": "", "what": "not checked here: needs Pillow and numpy"})
        return
    except SystemExit as e:          # e.g. an "on" word that isn't in the line
        rep.fix.append({"area": "Reel file", "where": "reel.json", "what": str(e),
                        "how": "Use a word that is in that shot's voice line (vo), copied exactly."})
        return
    bad = 0
    for p in reel.check_texts():
        if "placeholder" in p and p.startswith("screen "):
            m = re.search(r"screen (\S+) \((\S+)\)", p)
            rep.todo.append("screenshot {} at {} (a person takes it: prompts.md → 1 · Screenshots)".format(
                *(m.groups() if m else ("", ""))))
        elif "placeholder" in p:
            m = re.search(r"photo (\S+)", p)
            rep.todo.append("photo {} (prompts.md → 1 · Photos)".format(m.group(1) if m else ""))
        elif "logo" in p and "is missing" in p:
            rep.person.append({"area": "Reel file", "where": p.split(" ")[0].rstrip(":"), "what": p,
                               "how": "A person puts the logo back: python3 tools/make_logo.py, then "
                                      "node tools/render_assets.js logo, and commits brand/assets/logo/."})
        else:
            bad += 1
            rep.fix.append({"area": "Reel file", "where": p.split(" ")[0].rstrip(":"), "what": p,
                            "how": "Copy the text from that shot's card_text exactly. Text that leaves before the shot "
                                   "ends goes in motion_text. Never change card_text to match reel.json."})
    if not bad:
        rep.passed.append("Reel file: every word on screen comes from that shot's card text")


def voice(ep_dir, rep, model):
    lines_dir = ep_dir / "media" / "audio" / "lines"
    if not lines_dir.exists() or not any(lines_dir.glob("S*")):
        rep.todo.append("voice lines (MUSE.md → Step 2)")
        return
    import verify_voice
    results = verify_voice.check_lines(ep_dir, model_size=model, cache_path=ep_dir / "checks" / "voice-heard.json")
    ok = 0
    for r in results:
        heard = "should say: {} · heard: {}".format(r["should"], r["heard_hi"] + (" / " + r["heard_en"] if r["heard_en"] else ""))
        if r["status"] == "MISSING":
            rep.todo.append("voice line {} (MUSE.md → Step 2)".format(r["sid"]))
        elif r["status"] == "FAIL":
            text = "; ".join(r["problems"])
            if "older version" in text:
                how = ("The line's text changed after this file was made. Make the line again from its voice text (tts in "
                       "episode.json), with the series voice on the same model and settings as the reel's other lines, and "
                       "upload it under the same name.")
            elif "trimmed" in text or "cut off" in text:
                how = ("Make this line again from its voice text and save it exactly as the voice tool made it, "
                       "silence included. Upload it under the same name.")
            else:
                how = ("Compare \"should say\" with \"heard\". If they're the same words and only spelled differently, the "
                       "check misheard it: don't change anything, send it to the person to listen. If a word really comes "
                       "out wrong, rewrite just that word in this line's tts in episode.json so the voice says it clearly "
                       "(same number and meaning: say the number in English if it isn't (ट्वेंटी फ़ाइव हंड्रेड for पच्चीस सौ), add रुपीज़ after it, or add a comma "
                       "before it), make this one line again from the new text, and upload the line and episode.json.")
            rep.fix.append({"area": "Voice", "where": r["sid"], "what": text, "how": how, "detail": heard})
        elif r["status"] == "CHECK BY EAR":
            rep.person.append({"area": "Voice", "where": r["sid"], "what": "; ".join(r["notes"]),
                               "how": "A person listens to this line.", "detail": heard})
        else:
            ok += 1
    if ok:
        rep.passed.append("Voice: {} of {} lines say every number and word".format(ok, len(results)))


def screenshots(ep_dir, rep, use_ocr):
    """The portal screenshots show the menus and buttons the voice names (tools/verify_media.py)."""
    if not use_ocr:
        return
    import verify_media
    res = verify_media.check_screens(ep_dir)
    if res is None:
        return
    bad = 0
    for line in res.lines:
        if line.startswith("- FAIL · ") and " doesn't show " not in line:
            bad += 1
            msg = line[len("- FAIL · "):]
            rep.fix.append({"area": "Screenshot", "where": msg.split(" ")[0], "what": msg,
                            "how": "Copy the numbers the report gives into reel.json exactly where it says (a crop goes "
                                   "on the screenshot in screens; a box goes on that mark, in shares of the part of the "
                                   "screenshot the reel shows), and upload reel.json."})
        elif line.startswith("- FAIL · "):
            bad += 1
            msg = line[len("- FAIL · "):]
            rep.person.append({"area": "Screenshot", "where": msg.split(" ")[0], "what": msg,
                               "how": "A person takes this screenshot again on their own member portal login, showing "
                                      "these words, with every personal detail covered (prompts.md → 1 · Screenshots). "
                                      "If the portal really says something else now, the script and its voice line "
                                      "must change first."})
    if not bad and any(l.startswith("- PASS · ") for l in res.lines):
        rep.passed.append("Screenshots: each one shows the menus and buttons the voice names, and every mark sits on its words")


def final_reel(ep_dir, rep, use_ocr):
    video = ep_dir / "media" / "final" / "{}.mp4".format(ep_dir.name)
    if not video.exists():
        rep.todo.append("the reel (GitHub builds it once reel.json is uploaded)")
        return
    import verify_media
    res = verify_media.check_final(ep_dir, video, use_ocr=use_ocr)
    if res.out_of_date:
        rep.todo.append("the reel is out of date: GitHub rebuilds it after this upload, then checks it")
        return
    ends = {}
    tl = ep_dir / "build" / "timeline.json"
    if tl.exists():
        ends = {s["id"]: s["end"] for s in dc.load_json(tl).get("shots", [])}
    bad = 0
    for line in res.lines:
        if line.startswith("- FAIL · "):
            bad += 1
            msg = line[len("- FAIL · "):]
            m = re.match(r"(S\d+)\b", msg)
            if m:
                at = ends.get(m.group(1))
                rep.fix.append({"area": "Reel", "where": m.group(1), "what": msg,
                                "how": "Look at {} in the reel{}. If the words are right but hard to read, give them room "
                                       "in reel.json: move whatever overlaps them, or make them bigger. If they're wrong, "
                                       "copy them from card_text exactly. Then upload reel.json.".format(
                                           m.group(1), " at {:.1f} s".format(at - 0.4) if at else "")})
            elif msg.startswith("length"):
                rep.fix.append({"area": "Reel", "where": "length", "what": msg,
                                "how": "The script is too long or too short for {}–{} s. Propose a change to the person "
                                       "(the script needs their OK), then make the changed voice lines again.".format(
                                           *dc.brand().get("rules", {}).get("duration_seconds", [60, 95]))})
            elif "no sound" in msg:
                rep.todo.append("voice lines (MUSE.md → Step 2)")
            else:
                rep.person.append({"area": "Reel", "where": "", "what": msg,
                                   "how": "The build makes this, not Muse: tell the person."})
        elif line.startswith("- CHECK BY EYE · "):
            rep.look.append(line[len("- CHECK BY EYE · "):])
        elif line.startswith("- WARN · "):
            rep.notes.append({"area": "Reel", "where": "", "what": line[len("- WARN · "):]})
    if not bad:
        rep.passed.append("Reel: every card read back exactly, and the length, size and sound are right")


# ---------------------------------------------------------------- the report

def commit_id():
    sha = os.environ.get("GITHUB_SHA")
    if not sha:
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=dc.ROOT).stdout.strip()
        except OSError:
            sha = ""
    return sha[:7] or "?"


def render(ep_dir, rep, status):
    res = rep.result()
    live = rep.posted or {}
    say = {"FIX": "Muse has something to fix (below). Fix it all, upload, and wait for the next report.",
           "WAITING": "Nothing for Muse to fix. A person's part is left (below).",
           "PASS": "Everything made so far is right.",
           "POSTED": "This reel is live{}{}. Never post it again, and don't change its files: anything below is for a "
                     "person.".format(": " + live["url"] if live.get("url") else "",
                                      " (posted {})".format(live["on"]) if live.get("on") else "")}[res]
    out = ["# Check report · {}".format(ep_dir.name), "",
           "Checked commit `{}` on {} UTC. GitHub writes a new report after every upload.".format(
               commit_id(), datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")), "",
           "**RESULT: {}** · {}".format(res, say), ""]
    if rep.fix:
        out += ["## To fix (Muse)", ""]
        for i, f in enumerate(rep.fix, 1):
            out.append("{}. **{} · {}** · {}".format(i, f["area"], f["where"], f["what"]))
            out.append("   - Fix: {}".format(f["how"]))
            if f.get("detail"):
                out.append("   - {}".format(f["detail"]))
        out.append("")
    if rep.person:
        out += ["## For a person", ""]
        for i, f in enumerate(rep.person, 1):
            out.append("{}. **{} · {}** · {}".format(i, f["area"], f["where"], f["what"]))
            out.append("   - {}".format(f["how"]))
            if f.get("detail"):
                out.append("   - {}".format(f["detail"]))
        out.append("")
    if rep.look:
        out += ["## To look at (Muse, not blocking)", "",
                "OCR can't read symbols, lone digits or handwriting. Look at these in the reel and say in your report that they're right."]
        out += ["- " + x for x in rep.look]
        out.append("")
    if rep.todo and not rep.posted:
        out += ["## Still to make", ""] + ["- " + x for x in dict.fromkeys(rep.todo)] + [""]
    waiting = [k for k, v in (status or {}).get("steps", {}).items() if (v or {}).get("state") == "needs_human"]
    if rep.script and rep.script["state"] not in ("not needed", None):
        waiting = [k for k in waiting if k != "03-script"]       # the script review is the script's approval
    if waiting:
        out += ["## Approvals", "", "Steps waiting for a person's approval (recorded with `tools/approve.py step`): "
                + ", ".join(waiting) + ".", ""]
    if rep.notes:
        out += ["## Notes", ""] + ["- {} {}: {}".format(n["area"], n["where"], n["what"]).replace("  ", " ") for n in rep.notes] + [""]
    if rep.passed:
        out += ["## Passed", ""] + ["- " + x for x in rep.passed] + [""]
    if not rep.posted:
        out += ["## Posting", "", "Not posted yet. Post only after a person writes \"post it\", and only if `{}/posted.json` "
                "doesn't exist. Right after posting, upload posted.json (MUSE.md → Step 6).".format(dc.rel(ep_dir)), ""]
    return "\n".join(out)


def check(ep_dir, use_voice=True, use_ocr=True, model="medium"):
    ep_dir = Path(ep_dir)
    rep = Report()
    ep, status = episode_file(ep_dir, rep)
    if script_gate(ep_dir, rep):
        reel_file(ep_dir, rep)
        if use_voice:
            voice(ep_dir, rep, model)
        screenshots(ep_dir, rep, use_ocr)
        final_reel(ep_dir, rep, use_ocr)
    else:
        rep.todo.append("everything after the script waits for its review: the shots and reel.json (MUSE.md → N4), "
                        "photos, screenshots, voice lines and the reel")
        made = made_already(ep_dir, ep)
        if made:
            rep.notes.append({"area": "Script review", "where": "",
                              "what": "already made: {}. They're checked again once a person approves the script, and "
                                      "anything made from a line the person changes is made again.".format(", ".join(made))})
    rep.posted = topics.posted_record(ep_dir)
    if rep.posted:  # a live reel isn't changed: whatever the checks found is a person's call
        for f in rep.fix:
            f["how"] = "The reel is already live, so a person decides whether anything changes. (" + f["how"] + ")"
        rep.person, rep.fix = rep.fix + rep.person, []
    return rep, render(ep_dir, rep, status)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("episode")
    ap.add_argument("--no-voice", action="store_true", help="skip listening to the voice lines")
    ap.add_argument("--no-ocr", action="store_true", help="skip reading the cards in the reel")
    ap.add_argument("--model", default="medium", help="speech model for the voice check")
    ap.add_argument("--write", action="store_true", help="save the report as EPISODE/checks/report.md")
    a = ap.parse_args()
    rep, text = check(a.episode, not a.no_voice, not a.no_ocr, a.model)
    print(text)
    if a.write:
        out = Path(a.episode) / "checks" / "report.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    sys.exit({"FIX": 1, "WAITING": 0, "PASS": 0, "POSTED": 0}[rep.result()])


if __name__ == "__main__":
    main()
