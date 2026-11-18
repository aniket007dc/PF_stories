#!/usr/bin/env python3
"""Record checks and approvals in an episode's status.json.

Every approval re-runs the checks first and is locked to a fingerprint (hash) of
what was approved. If that content changes later, validate.py flags the step
and everything after it until someone approves it again.

  script     a person approves a new reel's script and hook, as its script page (script.md) shows them
             python3 tools/approve.py script EP --version 3fa9c1 --by NAME --words "script OK"
  step       approve a whole step (brief, data, script, shots, publish, measure)
             python3 tools/approve.py step EP 01-brief --by NAME
  fact       a person checked a fact's (or a rule's) source
             python3 tools/approve.py fact EP <data id> --by NAME --note "Seen on EPFO's own page, dated …"
  shot       approve one shot's keyframe or motion after looking at it
             python3 tools/approve.py shot EP S01 keyframe --file EP/media/keyframes/S01.png --by NAME
             python3 tools/approve.py shot EP S01 motion --canva --by NAME
  try        record a failed attempt (counts towards the two-tries rule)
             python3 tools/approve.py try EP S01 keyframe --note "₹50,000 came out as ₹56,000"
  file       approve the voice, the assembled reel or the final QA
             python3 tools/approve.py file EP 09-final-qa --file EP/media/final/ep01.mp4 --by NAME
  revoke     undo an approval
             python3 tools/approve.py revoke EP 03-script
  capability record Muse test-kit results
             python3 tools/approve.py capability image_text_exact=yes motion_keeps_text=no --by NAME
  repeat-ok  a person decides a flagged repeat of an earlier reel is fine (topic, hook, script or photos)
             python3 tools/approve.py repeat-ok EP ep01 topic --by NAME --note "Same form, but this one is about the pension part"
  posted     record the live post after publishing
             python3 tools/approve.py posted EP --url https://www.instagram.com/reel/... --by NAME
  metrics    record numbers at 24h, 72h or 7d
             python3 tools/approve.py metrics EP 24h views=1200 sends=40 saves=25
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402
import validate  # noqa: E402

NOT_PEOPLE = dc.NOT_PEOPLE


def die(msg, code=1):
    print("NOT RECORDED · " + msg)
    sys.exit(code)


def person(name, brand):
    name = (name or "").strip()
    if name.lower() in NOT_PEOPLE:
        die("this needs a person's name in --by (an AI can't approve its own work)")
    approvers = brand.get("approvers") or []
    if approvers and name not in approvers:
        die("'{}' is not in brand/brand.json approvers: {}".format(name, ", ".join(approvers)))
    return name


def load(ep_arg):
    ep_dir = Path(ep_arg).resolve()
    if not (ep_dir / "episode.json").exists():
        die("{} has no episode.json".format(ep_arg))
    return ep_dir, dc.load_json(ep_dir / "episode.json"), dc.load_json(ep_dir / "status.json")


def checks(ep_dir):
    brand = dc.brand()
    r, ep, status = validate.validate_episode(ep_dir, brand)
    return brand, r, ep, status


def log(status, by, event):
    status.setdefault("log", []).append({"at": dc.now(), "by": by, "event": event})


def require_previous(r, status, step_id):
    idx = dc.STEP_IDS.index(step_id)
    for prev in dc.STEP_IDS[:idx]:
        if (status["steps"].get(prev) or {}).get("state") != "passed":
            die("{} isn't passed yet. Steps go in order.".format(prev))
    if idx:
        bad = r.failures_through(dc.STEP_IDS[idx - 1])
        if bad:
            die("earlier steps have failing checks:\n  " + "\n  ".join("{} {}".format(i["id"], i["msg"]) for i in bad))


def finish(ep_dir, status, msg):
    dc.save_json(ep_dir / "status.json", status)
    _, r, _, _ = checks(ep_dir)
    print("RECORDED · " + msg)
    if r.of("fail"):
        print("But the checks now fail:\n  " + "\n  ".join("{} {}".format(i["id"], i["msg"]) for i in r.of("fail")))
        sys.exit(1)
    print("Next: " + (r.next_action or ""))


def cmd_step(a):
    ep_dir, _, _ = load(a.episode)
    brand, r, ep, status = checks(ep_dir)
    s = dc.step(a.step)
    if s["lock"] == "file":
        die("{} is approved with a file: python3 tools/approve.py file {} {} --file PATH --by NAME".format(a.step, a.episode, a.step))
    require_previous(r, status, a.step)
    if r.of("fail", a.step):
        die("{} has failing checks:\n  ".format(a.step) + "\n  ".join("{} {}".format(i["id"], i["msg"]) for i in r.of("fail", a.step)))
    if r.of("pending", a.step):
        die("{} is still waiting for:\n  ".format(a.step) + "\n  ".join(i["msg"] for i in r.of("pending", a.step)))
    by = person(a.by, brand) if s["human"] else (a.by or "auto-check")
    approval = {"by": by, "at": dc.now()}
    if s["lock"] == "section":
        approval["hash"] = dc.section_hash(dc.locked_content(ep, a.step))
    if s["lock"] == "shots":
        missing = [x["id"] for x in ep["shots"] if ((status["shots"].get(x["id"]) or {}).get(s["kind"]) or {}).get("state") != "passed"]
        if missing:
            die("these shots aren't approved yet: " + ", ".join(missing))
        approval["summary"] = "all {} shots approved".format(len(ep["shots"]))
    if a.note:
        approval["note"] = a.note
    status["steps"][a.step].update({"state": "passed", "approval": approval})
    log(status, by, "approved {}".format(a.step))
    finish(ep_dir, status, "{} passed, approved by {}".format(a.step, by))


def cmd_script(a):
    """Record that a person approved the script and hook of a reel whose script a person reviews
    (tools/script_review.py): script-approved.json, for the version on the page they read."""
    import script_review
    ep_dir, ep, _ = load(a.episode)
    by = person(a.by, dc.brand())
    if not script_review.reviewed(ep_dir):
        die("{} was made before script reviews began (brand.json → rules → script_review_from)".format(ep_dir.name))
    if not ep.get("script"):
        die("{} has no script yet".format(ep_dir.name))
    v = script_review.version(ep)
    if script_review.clean(a.version) != v:
        die("the page you read is version {}, but the script is version {} now: read its new page "
            "(python3 tools/script_review.py {} --write), then approve that".format(script_review.clean(a.version), v, a.episode))
    dc.save_json(ep_dir / script_review.APPROVAL,
                 {"version": v, "approved_by": by, "approved_on": dc.today(), "their_words": a.words})
    script_review.write(ep_dir)
    print("RECORDED · {} approved the script of {}, version {}. Next: the shots and reel.json (MUSE.md → N4).".format(
        by, ep_dir.name, v))


def cmd_fact(a):
    ep_dir, ep, status = load(a.episode)
    brand = dc.brand()
    by = person(a.by, brand)
    item = next((d for d in ep.get("data", []) if d.get("id") == a.fact), None)
    if not item:
        die("no data item called '{}'".format(a.fact))
    if item.get("kind") not in dc.SOURCED_KINDS:
        die("'{}' is a {}, not a fact or a rule".format(a.fact, item.get("kind")))
    item["checked_by"], item["checked_on"] = by, dc.today()
    if a.note:
        item["check_result"] = a.note
    dc.save_json(ep_dir / "episode.json", ep)
    if (status["steps"].get("02-data") or {}).get("state") == "passed":
        print("Note: 02-data was already approved; this edit means it must be approved again.")
    log(status, by, "checked the source of {} {}".format(item["kind"], a.fact))
    finish(ep_dir, status, "{} '{}' checked by {}".format(item["kind"], a.fact, by))


def cmd_shot(a):
    ep_dir, _, _ = load(a.episode)
    brand, r, ep, status = checks(ep_dir)
    shot = next((x for x in ep["shots"] if x["id"] == a.shot), None)
    if not shot:
        die("no shot {}".format(a.shot))
    step_id = "05-keyframes" if a.kind == "keyframe" else "06-motion"
    if (status["steps"].get("04-shots") or {}).get("state") != "passed":
        die("04-shots must be passed first")
    if a.kind == "motion" and ((status["shots"].get(a.shot) or {}).get("keyframe") or {}).get("state") != "passed":
        die("{} keyframe must be approved before its motion".format(a.shot))
    by = person(a.by, brand)
    entry = status["shots"].setdefault(a.shot, {}).setdefault(a.kind, {"state": "todo", "tries": 0})
    approval = {"by": by, "at": dc.now(), "spec_hash": dc.shot_spec_hash(shot, a.kind)}
    mode = a.mode or ("canva" if a.canva else None)
    if a.canva:
        if a.kind != "motion":
            die("--canva is only for motion")
        approval["ocr"] = "not run: animated in Canva; checked again at final QA"
    else:
        if not a.file:
            die("give --file (or --canva for motion made in Canva)")
        f = Path(a.file).resolve()
        if not f.exists():
            die("file not found: {}".format(a.file))
        approval["file"], approval["file_hash"] = dc.rel(f), dc.file_hash(f)
        if a.no_ocr:
            if not a.reason:
                die("--no-ocr needs --reason")
            approval["ocr"] = "skipped: " + a.reason
        else:
            import verify_media
            res = verify_media.check_keyframe(ep_dir, a.shot, f) if a.kind == "keyframe" else verify_media.check_clip(ep_dir, a.shot, f)
            print(res.text())
            if res.failed:
                entry["tries"] = entry.get("tries", 0) + 1
                entry.update({"state": "failed", "mode": mode or entry.get("mode")})
                log(status, by, "{} {} failed the media check (try {})".format(a.shot, a.kind, entry["tries"]))
                dc.save_json(ep_dir / "status.json", status)
                hint = " That's {} tries: switch to the clean-plate route.".format(entry["tries"]) if entry["tries"] >= brand["rules"].get("max_tries_per_shot", 2) else ""
                die("{} {} failed the check, so it isn't approved.{}".format(a.shot, a.kind, hint))
            approval["ocr"] = "pass"
    if a.note:
        approval["note"] = a.note
    entry.update({"state": "passed", "mode": mode or entry.get("mode"), "file": approval.get("file"), "approval": approval})
    log(status, by, "approved {} {}".format(a.shot, a.kind))
    pending = [x["id"] for x in ep["shots"] if ((status["shots"].get(x["id"]) or {}).get(a.kind) or {}).get("state") != "passed"]
    if not pending:
        status["steps"][step_id].update({"state": "passed", "approval": {"by": by, "at": dc.now(), "summary": "all {} shots approved".format(len(ep["shots"]))}})
        log(status, by, "{} passed: every shot approved".format(step_id))
    elif status["steps"][step_id].get("state") == "todo":
        status["steps"][step_id]["state"] = "in_progress"
    finish(ep_dir, status, "{} {} approved by {}{}".format(a.shot, a.kind, by, "" if pending else " · {} passed".format(step_id)))


def cmd_try(a):
    ep_dir, ep, status = load(a.episode)
    entry = status["shots"].setdefault(a.shot, {}).setdefault(a.kind, {"state": "todo", "tries": 0})
    entry["tries"] = entry.get("tries", 0) + 1
    entry["state"] = "failed"
    if a.mode:
        entry["mode"] = a.mode
    log(status, a.by or "team", "{} {} try {} failed: {}".format(a.shot, a.kind, entry["tries"], a.note or ""))
    dc.save_json(ep_dir / "status.json", status)
    limit = dc.brand()["rules"].get("max_tries_per_shot", 2)
    print("RECORDED · {} {} try {} failed.".format(a.shot, a.kind, entry["tries"]))
    if entry["tries"] >= limit:
        print("That's {} tries. Switch this shot to the clean-plate route (pipeline/05-keyframes.md).".format(entry["tries"]))


def cmd_file(a):
    ep_dir, _, _ = load(a.episode)
    brand, r, ep, status = checks(ep_dir)
    if a.step not in ("07-voice", "08-assembly", "09-final-qa"):
        die("file approvals are for 07-voice, 08-assembly and 09-final-qa")
    require_previous(r, status, a.step)
    by = person(a.by, brand)
    if a.step == "09-final-qa":
        editor = ((status["steps"].get("08-assembly") or {}).get("approval") or {}).get("by")
        if editor and editor == by:
            if len(brand.get("approvers") or []) >= 2:
                die("final QA must be signed off by someone other than {}, who approved the assembly".format(editor))
            print("Note: the same person approved the assembly and the final QA. Add a second approver to brand.json to require four eyes.")
    f = Path(a.file).resolve()
    if not f.exists():
        die("file not found: {}".format(a.file))
    import verify_media
    if a.step == "07-voice":
        res = verify_media.check_voice(ep_dir, f)
    else:
        if a.no_ocr and not a.reason:
            die("--no-ocr needs --reason")
        res = verify_media.check_final(ep_dir, f, use_ocr=not a.no_ocr)
    print(res.text())
    if res.failed:
        die("{} failed the check, so it isn't approved.".format(a.step))
    approval = {"by": by, "at": dc.now(), "file": dc.rel(f), "hash": dc.file_hash(f),
                "ocr": "skipped: " + a.reason if a.no_ocr else "pass"}
    if a.note:
        approval["note"] = a.note
    status["steps"][a.step].update({"state": "passed", "approval": approval})
    log(status, by, "approved {} with {}".format(a.step, dc.rel(f)))
    finish(ep_dir, status, "{} passed, approved by {}".format(a.step, by))


def cmd_revoke(a):
    ep_dir, ep, status = load(a.episode)
    if a.shot:
        entry = (status["shots"].get(a.shot) or {}).get(a.kind or "keyframe")
        if not entry:
            die("nothing to revoke")
        entry.update({"state": "todo", "approval": None})
        status["steps"]["05-keyframes" if (a.kind or "keyframe") == "keyframe" else "06-motion"]["state"] = "in_progress"
        what = "{} {}".format(a.shot, a.kind or "keyframe")
    else:
        if not a.step:
            die("say which step to revoke, or use --shot SHOT --kind keyframe|motion")
        s = dc.step(a.step)
        status["steps"][a.step].update({"state": "needs_human" if s["human"] else "drafted", "approval": None})
        what = a.step
    log(status, a.by or "team", "revoked {}".format(what))
    dc.save_json(ep_dir / "status.json", status)
    print("RECORDED · revoked {}".format(what))


def cmd_capability(a):
    brand = dc.brand()
    by = person(a.by, brand)
    path = dc.BRAND_DIR / "capabilities.json"
    cap = dc.load_json(path)
    for kv in a.pairs:
        k, _, v = kv.partition("=")
        if k in cap["results"]:
            if v not in ("yes", "no", "unknown"):
                die("{} must be yes, no or unknown".format(k))
            cap["results"][k] = v
        elif k in cap["specs"]:
            cap["specs"][k] = None if v in ("", "null") else (float(v) if v.replace(".", "", 1).isdigit() else v)
        else:
            die("unknown key {}. Results: {}. Specs: {}".format(k, ", ".join(cap["results"]), ", ".join(cap["specs"])))
    cap["tested_by"], cap["tested_on"] = by, dc.today()
    dc.save_json(path, cap)
    print("RECORDED · capabilities updated. Run python3 tools/build_prompts.py so prompts follow the new routes.")


def cmd_repeat_ok(a):
    ep_dir, ep, status = load(a.episode)
    by = person(a.by, dc.brand())
    import topics
    others = topics.earlier(ep_dir)
    other = topics.resolve(a.other, others)
    if not other:
        die("'{}' isn't an earlier reel. Earlier reels: {}".format(a.other, ", ".join(o["id"] for o in others) or "none"))
    if not (a.note or "").strip():
        die("say in --note why it's fine: it's shown in the report")
    me = topics.fingerprint(ep_dir)
    entry = {"other": other["id"], "what": a.what, "by": by, "at": dc.now(), "note": a.note.strip(),
             "lock": topics.lock(me, a.what)}
    keep = [x for x in status.get("repeat_ok") or [] if not (x.get("other") == other["id"] and x.get("what") == a.what)]
    status["repeat_ok"] = keep + [entry]
    log(status, by, "said the {} may stay close to {}: {}".format(a.what, other["id"], entry["note"]))
    finish(ep_dir, status, "{} next to {}: a person ({}) said it's fine. If the {} changes, this lapses.".format(
        a.what, other["id"], by, a.what))


def cmd_posted(a):
    ep_dir, ep, status = load(a.episode)
    by = person(a.by, dc.brand())
    if (status["steps"].get("10-publish") or {}).get("state") != "passed":
        die("10-publish must be approved before recording a post")
    status["post"] = {"url": a.url, "posted_at": dc.now(), "by": by}
    log(status, by, "posted {}".format(a.url))
    finish(ep_dir, status, "post recorded")


def cmd_metrics(a):
    ep_dir, ep, status = load(a.episode)
    values = {}
    for kv in a.pairs:
        k, _, v = kv.partition("=")
        try:
            values[k] = float(v) if "." in v else int(v)
        except ValueError:
            die("{} must be a number".format(kv))
    values["recorded_at"] = dc.now()
    status.setdefault("metrics", {})[a.when] = values
    if a.when == "7d" and status["steps"]["10-publish"].get("state") == "passed":
        status["steps"]["11-measure"].update({"state": "passed", "approval": {"by": a.by or "team", "at": dc.now()}})
    log(status, a.by or "team", "metrics {}".format(a.when))
    finish(ep_dir, status, "metrics {} recorded".format(a.when))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("script")
    p.add_argument("episode"); p.add_argument("--version", required=True, help="the version on the script page you read")
    p.add_argument("--by", required=True); p.add_argument("--words", default="script OK", help="what the person wrote")
    p.set_defaults(fn=cmd_script)
    p = sub.add_parser("step")
    p.add_argument("episode"); p.add_argument("step", choices=dc.STEP_IDS); p.add_argument("--by"); p.add_argument("--note")
    p.set_defaults(fn=cmd_step)
    p = sub.add_parser("fact")
    p.add_argument("episode"); p.add_argument("fact"); p.add_argument("--by", required=True); p.add_argument("--note")
    p.set_defaults(fn=cmd_fact)
    p = sub.add_parser("shot")
    p.add_argument("episode"); p.add_argument("shot"); p.add_argument("kind", choices=["keyframe", "motion"])
    p.add_argument("--file"); p.add_argument("--canva", action="store_true"); p.add_argument("--by", required=True)
    p.add_argument("--mode", choices=["muse", "clean-plate", "canva", "code"]); p.add_argument("--no-ocr", action="store_true")
    p.add_argument("--reason"); p.add_argument("--note")
    p.set_defaults(fn=cmd_shot)
    p = sub.add_parser("try")
    p.add_argument("episode"); p.add_argument("shot"); p.add_argument("kind", choices=["keyframe", "motion"])
    p.add_argument("--mode", choices=["muse", "clean-plate", "canva", "code"]); p.add_argument("--note"); p.add_argument("--by")
    p.set_defaults(fn=cmd_try)
    p = sub.add_parser("file")
    p.add_argument("episode"); p.add_argument("step"); p.add_argument("--file", required=True); p.add_argument("--by", required=True)
    p.add_argument("--no-ocr", action="store_true"); p.add_argument("--reason"); p.add_argument("--note")
    p.set_defaults(fn=cmd_file)
    p = sub.add_parser("revoke")
    p.add_argument("episode"); p.add_argument("step", nargs="?", choices=dc.STEP_IDS); p.add_argument("--shot")
    p.add_argument("--kind", choices=["keyframe", "motion"]); p.add_argument("--by")
    p.set_defaults(fn=cmd_revoke)
    p = sub.add_parser("capability")
    p.add_argument("pairs", nargs="+"); p.add_argument("--by", required=True)
    p.set_defaults(fn=cmd_capability)
    p = sub.add_parser("repeat-ok")
    p.add_argument("episode"); p.add_argument("other", help="the earlier reel: ep01, its folder name, or old-01")
    p.add_argument("what", choices=["topic", "hook", "script", "photos"]); p.add_argument("--by", required=True)
    p.add_argument("--note")
    p.set_defaults(fn=cmd_repeat_ok)
    p = sub.add_parser("posted")
    p.add_argument("episode"); p.add_argument("--url", required=True); p.add_argument("--by", required=True)
    p.set_defaults(fn=cmd_posted)
    p = sub.add_parser("metrics")
    p.add_argument("episode"); p.add_argument("when", choices=["24h", "72h", "7d"]); p.add_argument("pairs", nargs="+")
    p.add_argument("--by")
    p.set_defaults(fn=cmd_metrics)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
