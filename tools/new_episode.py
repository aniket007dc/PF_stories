#!/usr/bin/env python3
"""Start a new episode folder from the templates.

  python3 tools/new_episode.py ep02 uan-activate "UAN activate kaise karein?"

Creates episodes/ep02-uan-activate/ with episode.json, status.json, empty media
folders and the generated prompt files. Then follow pipeline/01-brief.md.

  python3 tools/new_episode.py --prepare episodes/ep02-uan-activate
Muse can't run this; GitHub does, whenever an episode.json is uploaded. It adds
status.json (if missing), the media folders, fresh prompt files and, for a reel whose
script a person reviews (tools/script_review.py), the script page, script.md.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402


def create(ep_id, slug, title, base=None):
    base = Path(base) if base else dc.EPISODES_DIR
    if not re.fullmatch(r"ep\d{2,3}", ep_id):
        raise SystemExit("episode id must look like ep02")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug):
        raise SystemExit("slug must be lowercase words joined by hyphens, like uan-activate")
    folder = base / "{}-{}".format(ep_id, slug)
    if folder.exists():
        raise SystemExit("{} already exists".format(folder))
    ep = dc.load_json(dc.ROOT / "templates" / "episode.template.json")
    ep.update({"id": ep_id, "slug": slug, "title": title, "created": dc.today(),
               "tag": "{} #{} · {}".format(dc.brand().get("brand", "").upper(), ep_id[2:].zfill(2),
                                           slug.replace("-", " ").upper())})
    ep["brief"]["topic"] = title
    status = dc.load_json(dc.ROOT / "templates" / "status.template.json")
    status["episode"] = folder.name
    status["log"].append({"at": dc.now(), "by": "new_episode.py", "event": "episode created"})
    for sub in ("checks", "media/keyframes", "media/clips", "media/audio", "media/final"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
        (folder / sub / ".gitkeep").touch()
    dc.save_json(folder / "episode.json", ep)
    dc.save_json(folder / "status.json", status)
    import build_prompts
    (folder / "prompts.md").write_text(build_prompts.render(folder), encoding="utf-8")
    (folder / "prompts-writing.md").write_text(build_prompts.render_writing(folder), encoding="utf-8")
    return folder


def prepare(folder):
    """Fill in what an episode folder needs around the files Muse writes (episode.json, reel.json):
    status.json if it's missing, the media folders, fresh prompt files and the script page (script.md, for a reel
    whose script a person reviews). Never touches approvals."""
    folder = Path(folder)
    if not (folder / "episode.json").exists():
        raise SystemExit("{} has no episode.json".format(folder))
    made = []
    if not (folder / "status.json").exists():
        status = dc.load_json(dc.ROOT / "templates" / "status.template.json")
        status["episode"] = folder.name
        status["log"].append({"at": dc.now(), "by": "new_episode.py --prepare", "event": "episode folder prepared"})
        dc.save_json(folder / "status.json", status)
        made.append("status.json")
    # every shot needs a "to do" entry for its keyframe and motion (added only; approvals are never touched)
    status = dc.load_json(folder / "status.json")
    shots = status.setdefault("shots", {})
    added = []
    for sh in dc.load_json(folder / "episode.json").get("shots", []):
        if sh.get("id") and sh["id"] not in shots:
            shots[sh["id"]] = {kind: {"state": "todo", "tries": 0, "mode": None, "file": None, "approval": None}
                               for kind in ("keyframe", "motion")}
            added.append(sh["id"])
    if added:
        status["log"].append({"at": dc.now(), "by": "new_episode.py --prepare", "event": "added shots " + ", ".join(added)})
        dc.save_json(folder / "status.json", status)
        made.append("status.json shots " + ", ".join(added))
    for sub in ("checks", "media/photos", "media/audio/lines", "media/final"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
        if not any((folder / sub).iterdir()):
            (folder / sub / ".gitkeep").touch()
    import build_prompts
    for name, fn in (("prompts.md", build_prompts.render), ("prompts-writing.md", build_prompts.render_writing)):
        text = fn(folder)
        path = folder / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            made.append(name)
    import script_review
    if script_review.write(folder):
        made.append(script_review.PAGE)
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prepare", metavar="EPISODE_FOLDER",
                    help="add status.json, media folders and prompt files to a folder that has an episode.json")
    ap.add_argument("id", nargs="?")
    ap.add_argument("slug", nargs="?")
    ap.add_argument("title", nargs="?")
    a = ap.parse_args()
    if a.prepare:
        made = prepare(a.prepare)
        print("Prepared {}: {}".format(a.prepare, ", ".join(made) or "nothing to change"))
        return
    if not (a.id and a.slug and a.title):
        ap.error("give an id, a slug and a title, or --prepare EPISODE_FOLDER")
    folder = create(a.id, a.slug, a.title)
    print("Created {}. Next: fill the brief (pipeline/01-brief.md).".format(dc.rel(folder)))


if __name__ == "__main__":
    main()
