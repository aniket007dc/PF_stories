#!/usr/bin/env python3
"""Make an episode's voice lines with Kokoro, an open voice model (Apache-2.0) that runs on this computer:
no ElevenLabs, no account, no internet after the first download.

    python3 tools/make_voice.py episodes/ep06-shivam-new-job                # every line
    python3 tools/make_voice.py episodes/ep06-shivam-new-job --lines S05,S12

Reads each line's voice text (tts) from episode.json and writes media/audio/lines/SNN.mp3. The narrator reads the
line; a quoted part is read by whoever says it, from the line's "speakers" (the speaker of each quote, in order,
such as ["priya", "narrator"]; without it, the narrator reads every quote). How it sounds:

- the voices: the narrator is Kokoro's Hindi male voice hm_omega; Priya, hf_alpha (VOICES below);
- the pace: made at a clear speed (1.25, a little quicker for an excited line and slower for a serious one, from
  the line's "delivery"), pauses inside a speaker's part held to 0.2 s, a 0.32 s beat when the speaker changes,
  then the whole line sped up 1.12 times with its pitch kept (ffmpeg atempo): brisk, without swallowing sounds;
- every part equally loud, the same peak on every line, 0.22 s of silence before the words and 0.4 s after.

Spell initials as letters (यू ए एन, पी एफ़) and English sounds with the dot (फ़): Kokoro reads पीएफ as "pee-eph"
and runs यूएएन together. Make every line of a reel with the same settings, and run the voice check after.

Needs (once): espeak-ng (apt-get install espeak-ng), ffmpeg, and
    pip install --index-url https://download.pytorch.org/whl/cpu torch
    pip install scipy soundfile huggingface_hub loguru transformers phonemizer-fork espeakng-loader
    pip install --no-deps kokoro misaki
"""
import argparse
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import numpy as np

SR = 24000
VOICES = {"narrator": "hm_omega", "shivam": "hm_omega", "priya": "hf_alpha", "ravi": "hm_psi", "papa": "hm_psi"}
SPEED, TEMPO, MAX_GAP, TURN = 1.25, 1.12, 0.20, 0.32
MOOD = {"excited": 1.06, "playful": 1.04, "surprised": 1.05, "happy": 1.03, "curious": 1.0, "proud": 1.0,
        "warm": 0.97, "concerned": 0.95, "serious": 0.95}


def parts_of(line):
    """[(speaker, text)] for a line: the narrator outside quotes, each quote's speaker inside them; a speaker's
    neighbouring parts are read together."""
    speakers = line.get("speakers") or []
    out = []
    for k, text in enumerate(line["tts"].split('"')):
        if not text.strip():
            continue
        q = k // 2
        who = "narrator" if k % 2 == 0 else (speakers[q] if q < len(speakers) else "narrator")
        if out and out[-1][0] == who:
            out[-1] = (who, out[-1][1] + " " + text.strip())
        else:
            out.append((who, text.strip()))
    return out


def compact(a, frame=0.01, floor=0.012):
    """Hold every pause inside a part to MAX_GAP seconds, cutting from its middle with short fades."""
    n = int(frame * SR)
    peak = np.abs(a).max() or 1
    quiet = [np.sqrt(np.mean(a[i:i + n] ** 2)) < floor * peak for i in range(0, len(a), n)]
    keep, i = [], 0
    while i < len(quiet):
        j = i
        while j < len(quiet) and quiet[j] == quiet[i]:
            j += 1
        s0, s1 = i * n, min(len(a), j * n)
        seg = a[s0:s1]
        if quiet[i] and 0 < i and j < len(quiet) and (s1 - s0) > MAX_GAP * SR:
            half = int(MAX_GAP * SR / 2)
            fade = np.linspace(1, 0, min(120, half), dtype=np.float32)
            head, tail = seg[:half].copy(), seg[-half:].copy()
            head[-len(fade):] *= fade
            tail[:len(fade)] *= fade[::-1]
            seg = np.concatenate([head, tail])
        keep.append(seg)
        i = j
    return np.concatenate(keep)


def speak(pipeline, line, voices):
    """One line as 24 kHz mono samples, before the speed-up."""
    mood = (line.get("delivery") or "").split("·")[0].strip()
    speed = round(SPEED * MOOD.get(mood, 1.0), 3)
    out = [np.zeros(int(0.22 * SR), np.float32)]
    for i, (who, text) in enumerate(parts_of(line)):
        if i:
            out.append(np.zeros(int(TURN * SR), np.float32))      # a beat when the speaker changes
        seg = compact(np.concatenate([np.asarray(r.audio, np.float32)
                                      for r in pipeline(text, voice=voices[who], speed=speed)]))
        loud = seg[np.abs(seg) > 0.02 * (np.abs(seg).max() or 1)]
        out.append(seg * (0.12 / (np.sqrt(np.mean(loud ** 2)) or 1)))   # every voice equally loud
    out.append(np.zeros(int(0.40 * SR), np.float32))
    a = np.concatenate(out)
    return a / (np.abs(a).max() or 1) * 0.89


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--lines", help="only these lines, such as S05,S12")
    a = ap.parse_args()
    sys.modules.setdefault("spacy", types.ModuleType("spacy"))   # only Kokoro's English front end needs spacy
    import soundfile as sf
    from kokoro import KPipeline
    ep_dir = Path(a.episode)
    script = json.loads((ep_dir / "episode.json").read_text(encoding="utf-8"))["script"]
    only = set(a.lines.split(",")) if a.lines else None
    pipeline = KPipeline(lang_code="h")
    out_dir = ep_dir / "media" / "audio" / "lines"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for line in script:
            sid = line["shot"]
            if only and sid not in only:
                continue
            raw = Path(tmp) / (sid + ".wav")
            sf.write(raw, speak(pipeline, line, VOICES), SR)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-filter:a", "atempo={}".format(TEMPO),
                            "-ar", "44100", "-ac", "1", "-codec:a", "libmp3lame", "-b:a", "160k",
                            str(out_dir / (sid + ".mp3"))], check=True)
            print("made", out_dir / (sid + ".mp3"))


if __name__ == "__main__":
    main()
