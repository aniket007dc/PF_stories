#!/usr/bin/env python3
"""Make a Taali reel's vocals with ElevenLabs: one file per line, in each singer's own voice (styles/taali/STYLE.md →
The voice).

    python3 tools/taali_voice.py styles/taali/ep00-taali-sample --dry-run    what would be made, and its characters
    python3 tools/taali_voice.py styles/taali/ep00-taali-sample              make the lines that are missing or changed
    python3 tools/taali_voice.py styles/taali/ep00-taali-sample --only L02   make one line (again)
    python3 tools/taali_voice.py EP --all                                    make every line again
    python3 tools/taali_voice.py --find-voices hi                            Voice Library voices for the cast

Sawaj's lines in his voice, Lali's in hers, and "both" lines in both voices, sung together. The voices, the model and
how they sing are in the account's profile: clients/<client>/client.json → cast (sawaj, lali: voice_id, tags, speed,
stability; model). The tags go in front of every line (Eleven v3 acts them out and never says them), so the lines
come out sung and bouncy, not read.

Each line is asked for with its word timings (the with-timestamps endpoint), saved next to it as <id>.json, so the
build places the line with its first word on the line's first beat, and the captions and the mouths follow the real
voice. A line's text can differ from what's on screen: "tts" on the line (for example the Gujarati script, for a
truer accent); otherwise its "say", with a blank (___) left as a pause for the viewer.

Keys come from the environment only, never a file: ELEVENLABS_API_KEY, then ELEVENLABS_API_KEY_2, _3 and _4 when one
is out of credits, blocked, rate-limited or refused. A fingerprint of what made each line is kept in
media/audio/lines/voice.json, so an unchanged line never costs credits twice.
"""
import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.elevenlabs.io"
KEY_NAMES = ["ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY_2", "ELEVENLABS_API_KEY_3", "ELEVENLABS_API_KEY_4"]
DEFAULT_CAST = {
    "model": "eleven_v3",
    "sawaj": {"voice_id": "", "tags": "[cheerful] [sing-song, on the beat]", "speed": 1.1, "stability": 0.5},
    "lali": {"voice_id": "", "tags": "[playful] [sing-song, bright]", "speed": 1.1, "stability": 0.5},
}


class KeyProblem(Exception):
    """A problem another key could fix: out of credits, blocked, rate-limited, refused, the voice not on its account."""


def keys():
    return [(n, os.environ[n].strip()) for n in KEY_NAMES if os.environ.get(n, "").strip()]


def call(method, path, key, body=None, query=None):
    url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"xi-api-key": key, "Content-Type": "application/json",
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:400]
        if e.code in (401, 402, 403, 429) or "quota" in msg or "voice_not_found" in msg:
            raise KeyProblem("{} {}".format(e.code, msg))
        raise SystemExit("ElevenLabs refused the request ({}): {}".format(e.code, msg))
    except urllib.error.URLError as e:
        raise SystemExit("Couldn't reach ElevenLabs: {}".format(e.reason))


def with_any_key(fn):
    ks = keys()
    if not ks:
        raise SystemExit("No ElevenLabs key: set ELEVENLABS_API_KEY (and optionally _2, _3, _4) in the environment, "
                         "or make the lines by hand on elevenlabs.io (build/voice.md lists them).")
    last = None
    for name, k in ks:
        try:
            return fn(k)
        except KeyProblem as e:
            print("  {} can't: {}; trying the next key".format(name, str(e)[:160]))
            last = e
    raise SystemExit("Every key failed. The last said: {}".format(last))


# ---------------------------------------------------------------- the cast and the lines
def load(ep_dir):
    ep = json.loads((Path(ep_dir) / "episode.json").read_text())
    client = {}
    if ep.get("client"):
        f = ROOT / "clients" / ep["client"] / "client.json"
        if f.exists():
            client = json.loads(f.read_text())
    cast = dict(DEFAULT_CAST)
    for k, v in (client.get("cast") or {}).items():
        cast[k] = dict(cast.get(k) or {}, **v) if isinstance(v, dict) else v
    return ep, client, cast


def text_of(line):
    t = line.get("tts") or line["say"]
    return re.sub(r"_{2,}", "...", t).strip()


def singers(line):
    return ["sawaj", "lali"] if line["who"] == "both" else [line["who"]]


def request_for(line, who, cast):
    c = cast[who]
    tags = (line.get("tags") or {}).get(who) if isinstance(line.get("tags"), dict) else line.get("tags")
    text = "{} {}".format(tags or c.get("tags", ""), text_of(line)).strip()
    body = {"text": text, "model_id": cast.get("model", "eleven_v3"),
            "voice_settings": {"stability": float(c.get("stability", 0.5)),
                               "similarity_boost": float(c.get("similarity", 0.8)),
                               "style": float(c.get("style", 0.6)), "use_speaker_boost": True,
                               "speed": float(c.get("speed", 1.0))}}
    if cast.get("language_code"):
        body["language_code"] = cast["language_code"]
    return c.get("voice_id", ""), body


def fingerprint(line, cast):
    parts = [request_for(line, w, cast) for w in singers(line)]
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:16]


def words_from(alignment):
    """[{w, start, end}] from ElevenLabs' character timings, leaving out the [tags]."""
    if not alignment:
        return []
    chars = alignment.get("characters") or []
    st = alignment.get("character_start_times_seconds") or []
    en = alignment.get("character_end_times_seconds") or []
    out, cur, depth = [], None, 0
    for ch, a, b in zip(chars, st, en):
        if ch == "[":
            depth += 1
            continue
        if ch == "]":
            depth = max(0, depth - 1)
            continue
        if depth:
            continue
        if ch.isspace() or ch in ".…":
            if cur:
                out.append(cur)
                cur = None
            continue
        if cur is None:
            cur = {"w": ch, "start": a, "end": b}
        else:
            cur["w"] += ch
            cur["end"] = b
    if cur:
        out.append(cur)
    return [dict(w, start=round(w["start"], 3), end=round(w["end"], 3)) for w in out
            if re.search(r"\w", w["w"])]


def speak(voice_id, body, out_mp3):
    """One voice, one line: the mp3 and its word timings (none if this model can't give them)."""
    def go(k):
        try:
            r = call("POST", "/v1/text-to-speech/{}/with-timestamps".format(voice_id), k, body,
                     {"output_format": "mp3_44100_128"})
            out_mp3.write_bytes(base64.b64decode(r["audio_base64"]))
            return words_from(r.get("alignment") or r.get("normalized_alignment"))
        except SystemExit as e:
            if "timestamps" not in str(e) and "not supported" not in str(e).lower():
                raise
        # this model has no timings: the plain endpoint, and the build spreads the words over the line
        req = urllib.request.Request(API + "/v1/text-to-speech/{}?output_format=mp3_44100_128".format(voice_id),
                                     data=json.dumps(body).encode(), method="POST",
                                     headers={"xi-api-key": k, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                out_mp3.write_bytes(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:400]
            if e.code in (401, 402, 403, 429):
                raise KeyProblem("{} {}".format(e.code, msg))
            raise SystemExit("ElevenLabs refused the request ({}): {}".format(e.code, msg))
        return []
    return with_any_key(go)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def make_line(line, cast, lines_dir):
    files, timings = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for who in singers(line):
            vid, body = request_for(line, who, cast)
            f = Path(tmp) / "{}.mp3".format(who)
            timings.append(speak(vid, body, f))
            files.append(f)
        out = lines_dir / "{}.mp3".format(line["id"])
        if len(files) == 1:
            out.write_bytes(files[0].read_bytes())
        else:
            # both of them, together: each line lined up on its first word, then mixed
            starts = [t[0]["start"] if t else 0.0 for t in timings]
            lead = max(starts)
            ins, filt = [], []
            for i, (f, s0) in enumerate(zip(files, starts)):
                ins += ["-i", str(f)]
                delay = int(round((lead - s0) * 1000))
                filt.append("[{}:a]adelay={}|{}[a{}]".format(i, delay, delay, i))
            filt.append("".join("[a{}]".format(i) for i in range(len(files))) +
                        "amix=inputs={}:normalize=0,volume=0.8[out]".format(len(files)))
            subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins + ["-filter_complex", ";".join(filt), "-map", "[out]",
                            "-c:a", "libmp3lame", "-b:a", "160k", str(out)], check=True)
            # the timings of the voice that starts last, shifted to where it now sits
            k = starts.index(lead)
            timings = [timings[k]]
    words = timings[0] if timings else []
    (lines_dir / "{}.json".format(line["id"])).write_text(json.dumps(
        {"line": line["id"], "who": line["who"], "duration": round(duration(out), 3), "words": words},
        ensure_ascii=False, indent=1) + "\n")
    return out, words


# ---------------------------------------------------------------- finding voices
def find_voices(language, gender=None):
    def go(k):
        q = {"page_size": 30, "language": language}
        if gender:
            q["gender"] = gender
        return call("GET", "/v1/shared-voices", k, query=q)
    r = with_any_key(go)
    print("Voice Library voices in '{}'{} (add one to your account on elevenlabs.io → Voice Library, then put its "
          "voice_id in client.json → cast):".format(language, " ({})".format(gender) if gender else ""))
    for v in r.get("voices") or []:
        print("  {:22} {:28} {:8} {:8} {}".format(v.get("voice_id"), (v.get("name") or "")[:28], v.get("gender") or "",
                                                 v.get("age") or "", (v.get("descriptive") or v.get("use_case") or "")))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("episode", nargs="?")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true", help="make every line again")
    ap.add_argument("--only", action="append", help="make only this line (repeatable)")
    ap.add_argument("--find-voices", metavar="LANG", help="list Voice Library voices in a language (hi, gu, en)")
    ap.add_argument("--gender", choices=["male", "female"])
    a = ap.parse_args()
    if a.find_voices:
        find_voices(a.find_voices, a.gender)
        return
    if not a.episode:
        ap.error("give an episode folder")
    ep_dir = Path(a.episode)
    ep, client, cast = load(ep_dir)
    if ep.get("style") != "taali":
        raise SystemExit("{} isn't a Taali episode: this tool only voices Taali episodes".format(ep_dir))
    missing = [w for w in ("sawaj", "lali") if not (cast.get(w) or {}).get("voice_id")]
    lines = ep["lesson"]["lines"]
    lines_dir = ep_dir / "media" / "audio" / "lines"
    lines_dir.mkdir(parents=True, exist_ok=True)
    rec_f = lines_dir / "voice.json"
    try:
        rec = json.loads(rec_f.read_text())
    except (OSError, ValueError):
        rec = {}
    todo = []
    for ln in lines:
        if a.only and ln["id"] not in a.only:
            continue
        fp = fingerprint(ln, cast)
        have = (lines_dir / "{}.mp3".format(ln["id"])).exists()
        if a.all or a.only or not have or rec.get(ln["id"]) != fp:
            todo.append((ln, fp))
    chars = sum(len(request_for(ln, w, cast)[1]["text"]) for ln, _ in todo for w in singers(ln))
    print("{}: {} of {} lines to make, about {} characters of credits (model {})".format(
        ep_dir.name, len(todo), len(lines), chars, cast.get("model")))
    for ln, _ in todo:
        print("  {} {:6} {}".format(ln["id"], ln["who"], text_of(ln)))
    if a.dry_run or not todo:
        return
    if missing:
        raise SystemExit("No voice yet for {}: put a voice_id in clients/{}/client.json → cast → {} (find one with "
                         "python3 tools/taali_voice.py --find-voices hi --gender {})".format(
                             " and ".join(missing), ep.get("client", "<client>"), missing[0],
                             "male" if missing[0] == "sawaj" else "female"))
    for ln, fp in todo:
        out, words = make_line(ln, cast, lines_dir)
        rec[ln["id"]] = fp
        rec_f.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
        print("  made {} ({:.2f} s, {} word timings)".format(out.name, duration(out), len(words)))
    print("Done. Build the reel with: python3 tools/build_taali.py {}".format(ep_dir))


if __name__ == "__main__":
    main()
