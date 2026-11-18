#!/usr/bin/env python3
"""Listen to every voice line and compare it with the script.

    python3 tools/verify_voice.py episodes/ep01-claim-reject
    python3 tools/verify_voice.py episodes/ep01-claim-reject S08 S16     # only these lines

For each file in media/audio/lines/ it writes down what it hears (in Hindi and in English, with
Whisper) and checks:
- every number in the line is heard: ₹2,500 must not come out as "pachaas sau" (₹5,000);
- the brand name is heard, in lines that say it;
- the file wasn't trimmed: a line needs its natural pause before and after, and must not
  stop in the middle of a sound;
- the file was made from the line as it is now: the first time a file is heard, the check notes the
  voice text it was checked against, and a file whose line has changed since must be made again.
It also warns about numbers it hears that aren't in the line, which usually means a word was misread.

It only reports. To fix a line, make it again from its voice text, with the same voice.
Needs ffmpeg and faster-whisper (pip install -r requirements-voice.txt).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402

SR = 16000

# ---------------------------------------------------------------- spoken numbers (tools/spoken.py)

from spoken import (SOUND_ALIKE, _plain, expected_numbers, spoken_numbers, word_numbers)  # noqa: E402,F401


# ---------------------------------------------------------------- brand

# How each word of the brand is written in a Hindi transcript. Transcripts are folded before comparing
# (nukta dropped, long ū read as short u, spaces removed), so गुरू जी, गुरुजी and पी एफ all count.
BRAND_WORD_HI = {"pf": "पीएफ", "guru": "गुरु", "ji": "जी"}


def _fold(w):
    return w.replace("\u093c", "").replace("\u0942", "\u0941").strip("।,.?!\"'")


def brand_heard(brand, hi_text, en_text):
    """Every word of the brand is in what Whisper heard, in English letters or in Hindi. A mangled or missing
    word isn't the brand: "PF Kuru Ji", or "PF Guru" without the Ji."""
    hindi = _fold("".join(hi_text.split()))
    latin = re.sub(r"[^a-z]", "", (en_text + " " + hi_text).lower())
    for word in brand.lower().split():
        if word in latin:
            continue
        want = BRAND_WORD_HI.get(word)
        if not (want and _fold(want) in hindi):
            return False
    return True


# ---------------------------------------------------------------- audio

def said(text):
    """A voice text without its punctuation and spacing, to tell whether a line's words have changed."""
    return " ".join(re.sub(r"[\u0964\u0965\u2026,.?!:;\"'\u2018\u2019\u201c\u201d\u2013\u2014-]", " ", text).split())


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def edges(a):
    """(silence before, silence after, how loud the last 30 ms is below the speech level, in dB)."""
    hop = SR // 100
    n = len(a) // hop
    if n < 5:
        return 0.0, 0.0, 0.0
    rms = np.sqrt(np.mean(a[:n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    speech = np.percentile(db, 90)
    on = np.where(db > speech - 30)[0]
    before = on[0] * hop / SR
    after = (n - 1 - on[-1]) * hop / SR
    tail = 20 * np.log10(np.sqrt(np.mean(a[-int(0.03 * SR):] ** 2)) + 1e-9)
    return before, after, speech - tail


# ---------------------------------------------------------------- the check

def listen(model, audio, lang):
    segs, _ = model.transcribe(audio, language=lang, beam_size=5, condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segs)


def check_lines(ep_dir, only=None, model_size="medium", cache_path=None):
    """One result per script line: {"sid", "status" (PASS, CHECK BY EAR, FAIL, MISSING), "problems", "notes",
    "should", "heard_hi", "heard_en"}. Transcripts are kept in cache_path by the audio file's fingerprint,
    so a file that hasn't changed isn't transcribed again."""
    import hashlib
    ep = dc.load_json(Path(ep_dir) / "episode.json")
    brand = dc.brand().get("brand", "")
    lines_dir = Path(ep_dir) / "media" / "audio" / "lines"
    files = {f.stem.upper(): f for f in lines_dir.glob("*.*") if f.suffix.lower() in
             (".mp3", ".wav", ".m4a", ".aac", ".ogg")} if lines_dir.exists() else {}
    cache = {}
    if cache_path and Path(cache_path).exists():
        cache = json.loads(Path(cache_path).read_text(encoding="utf-8"))
    model = None

    def entry_for(f):
        return cache.setdefault(hashlib.sha256(f.read_bytes()).hexdigest()[:20], {"file": f.name})

    def heard_for(f, audio, lang):
        nonlocal model
        entry = entry_for(f)
        if lang not in entry:
            if model is None:
                from faster_whisper import WhisperModel
                model = WhisperModel(model_size, device="cpu", compute_type="int8")
            entry[lang] = listen(model, audio, lang)
        return entry[lang]

    results = []
    for line in ep.get("script", []):
        sid = line["shot"]
        if only and sid not in only:
            continue
        res = {"sid": sid, "should": line.get("tts", ""), "heard_hi": "", "heard_en": "", "problems": [], "notes": []}
        f = files.get(sid)
        if not f:
            res["status"] = "MISSING"
            results.append(res)
            continue
        made_for = entry_for(f).setdefault("tts", line.get("tts", ""))    # the text this file was first checked against
        a = decode(f)
        res["heard_hi"] = heard_for(f, a, "hi")
        want = expected_numbers(line["vo"])
        says_brand = bool(brand) and brand.lower() in line["vo"].lower()
        got_hi = spoken_numbers(res["heard_hi"])
        if any(n not in got_hi for n in want) or (says_brand and not brand_heard(brand, res["heard_hi"], "")):
            res["heard_en"] = heard_for(f, a, "en")    # a second opinion only when the first one misses something
        got_en = spoken_numbers(res["heard_en"])
        problems, notes = res["problems"], res["notes"]
        if said(made_for) != said(line.get("tts", "")):
            problems.append("this file was made for an older version of the line (\"{}\"): make it again from the "
                            "voice text".format(made_for))
        missing = [n for n in want if n not in got_hi and n not in got_en]
        words_heard = {_plain(w) for w in (res["heard_hi"] + " " + res["heard_en"]).split()}
        for n in missing:
            alike = SOUND_ALIKE.get(n, set()) & words_heard
            if alike:
                notes.append("{} may have been heard as \"{}\", which sounds the same: listen to it".format(
                    dc.indian(n), "/".join(sorted(alike))))
            else:
                problems.append("number {} not heard".format(dc.indian(n)))
        allowed = set(want) | word_numbers(line["vo"]) | dc.form_numbers(line["vo"])
        extra = sorted({n for n in got_hi if n not in allowed and n > 10})
        if extra:
            notes.append("heard {}, which isn't in the line, so a word may be misread".format(
                ", ".join(dc.indian(n) for n in extra)))
        if says_brand and not brand_heard(brand, res["heard_hi"], res["heard_en"]):
            problems.append("\"{}\" not heard clearly".format(brand))
        before, after, tail_gap = edges(a)
        if tail_gap < 10:
            problems.append("the file stops in the middle of a sound: the end was cut off")
        if before < 0.03 and after < 0.05:
            problems.append("no pause before or after the words, so the file was trimmed")
        elif before < 0.03 or after < 0.05:
            notes.append("almost no pause at the {}: check the {} word isn't clipped".format(
                "start" if before < 0.03 else "end", "first" if before < 0.03 else "last"))
        res["status"] = "FAIL" if problems else ("CHECK BY EAR" if notes else "PASS")
        results.append(res)
    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return results


def render(results, name):
    report = ["# Voice check · {}".format(name), "",
              "Each line is written down as heard, in Hindi (and again in English when the first pass misses something). "
              "Every number and the brand name must be heard, and the file must not be trimmed. The transcripts are "
              "a machine's guess, so a person still listens before approving.", ""]
    failed = False
    for r in results:
        if r["status"] == "MISSING":
            report.append("- MISSING · **{}** · no voice file yet".format(r["sid"]))
            continue
        failed = failed or r["status"] == "FAIL"
        report.append("- {} · **{}** · {}".format(r["status"], r["sid"], "; ".join(r["problems"] + r["notes"]) or "numbers and words heard"))
        report.append("  - should say: {}".format(r["should"]))
        report.append("  - heard (Hindi): {}".format(r["heard_hi"] or "—"))
        if r["heard_en"]:
            report.append("  - heard (English): {}".format(r["heard_en"]))
    report += ["", "**Result: {}**".format("FAIL" if failed else "PASS")]
    return "\n".join(report), failed


def check(ep_dir, only=None, model_size="medium", cache_path=None):
    return render(check_lines(ep_dir, only, model_size, cache_path), Path(ep_dir).name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("episode")
    ap.add_argument("shots", nargs="*", help="only these lines, for example S08 S16")
    ap.add_argument("--model", default="medium", help="Whisper model (default medium; small is faster but misses more)")
    ap.add_argument("--write", action="store_true", help="also save the report in EPISODE/checks/voice.md")
    a = ap.parse_args()
    text, failed = check(a.episode, set(s.upper() for s in a.shots) or None, a.model,
                         cache_path=Path(a.episode) / "checks" / "voice-heard.json")
    print(text)
    if a.write:
        out = Path(a.episode) / "checks" / "voice.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
