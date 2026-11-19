#!/usr/bin/env python3
"""Make an episode's voice lines in a native Hindi voice, on this computer: no ElevenLabs, no account.

    python3 tools/make_voice.py episodes/ep06-shivam-new-job                # every line
    python3 tools/make_voice.py episodes/ep06-shivam-new-job --lines S05,S12

Reads each line's voice text (tts) from episode.json and writes media/audio/lines/SNN.mp3, plus voice-takes.json
(which take of each part was kept, and what Whisper heard in it).

The voice is F5-Hindi (SPRINGLab, IIT Madras; CC BY 4.0), a voice model trained on native speakers' Hindi. It speaks
in the voice and manner of a short reference clip from AI4Bharat's Rasa dataset (CC BY 4.0): brand/voices/narrator.wav
(a male speaker, for the narrator and Shivam) and brand/voices/priya.wav (a female speaker). Credits are in
brand/voices/README.md: keep them with anything published.

How a line is made:
- the narrator reads the line; a quoted part is read by whoever says it, from the line's "speakers" (the speaker of
  each quote, in order, such as ["priya", "narrator"]; without it, the narrator reads every quote);
- each part is made up to TAKES times and Whisper (the model the voice check uses) listens to every take. The first
  take that says every initialism (PF, UAN, EPFO, ...), every number and every word of the part, with nothing extra,
  is kept; else the one that comes closest;
- the model blurs or swallows the first sound it makes, so every part starts with a throwaway "हाँ।" (LEAD), cut off
  in the pause after it before Whisper listens; and a colon is read as a comma (the model says it like the
  visarga ः: "चेक:" came out "चेके");
- initialisms are said as one quick word (UAN, not U... A... N). Written apart (यू ए एन), each letter gets 0.1 s
  more than its characters suggest, so none is dropped (without it, यू ए एन came out as "यूएन"); written as one
  word (यूएएन), the model says it as one, with no extra time. Then the pauses between the
  letters are cut to 0.03 s and the initialism sped up, pitch kept, to about 0.17 s a letter (UAN in about half a
  second). A take keeps that only if Whisper still hears every letter, and a take still said letter by letter is
  the last choice;
- the pace: SPEED times the reference speaker's pace, a little quicker for an excited line and slower for a serious
  one (the line's "delivery"); pauses inside a part held to 0.25 s, a 0.32 s beat when the speaker changes;
- every part equally loud, the same peak on every line, 0.22 s of silence before the words and 0.4 s after.

Write initials as letters with spaces (यू ए एन, पी एफ़) and English words the way they sound (फ़ॉलो, सिक्सटी). Make
every line of a reel with the same voices, and run the voice check after (tools/verify_voice.py).

Needs (once): ffmpeg, and
    pip install --index-url https://download.pytorch.org/whl/cpu torch==2.11.0 torchaudio==2.11.1 torchcodec==0.11.1
    pip install f5-tts==1.1.22 faster-whisper==1.2.1
(torch, torchaudio and torchcodec must be versions made for each other.) The first run downloads the voice model
(630 MB, Hugging Face SPRINGLab/F5-Hindi-24KHz), its vocoder (charactr/vocos-mel-24khz, MIT) and Whisper medium.
It runs on the CPU: about a minute per take.
"""
import argparse
import contextlib
import difflib
import io
import json
import re
import subprocess
import sys
import tempfile
from collections import namedtuple
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spoken import PUNCT, letter_words, spell, spelled_count, spoken_numbers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = ROOT / "brand" / "voices"
MODEL = ("SPRINGLab/F5-Hindi-24KHz", "model_2500000.safetensors", "vocab.txt")
SR = 24000
Word = namedtuple("Word", "start end word")          # a word Whisper heard, and when (seconds into the take)
# Who reads with which reference clip (brand/voices/<name>.wav, its words in <name>.txt)
VOICES = {"narrator": "narrator", "shivam": "narrator", "priya": "priya", "ravi": "narrator", "papa": "narrator"}
SPEED, TAKES, MAX_GAP, TURN, REF_PAUSE = 1.15, 6, 0.25, 0.32, 0.4
# Initialisms: each letter gets LETTER_TIME more to be said in (so none is dropped), then the pauses between
# letters are cut to LETTER_GAP and the whole initialism sped up to about LETTER_SEC a letter (at most MAX_QUICK)
LETTER_TIME, LETTER_GAP, LETTER_SEC, MAX_QUICK = 0.1, 0.03, 0.17, 1.4
# Said before every part and cut off: the model blurs or swallows the first sound it makes after the reference
LEAD = "हाँ। "
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


# ---------------------------------------------------------------- what a take must say

def fold(w):
    """A Devanagari word without nukta, nasal marks, halant or vowel length, so Whisper's spelling meets the
    script's: पुराना and पूराना, फ़ॉलो and फॉलो, चाहिए and चाहिये, नौकरी and नौक्री, फ़ॉर्म and फौम are the same word,
    and so are ठीक, थीक and तीक, or आधार and आदार: Whisper mixes up ट ठ त थ, and ड ढ द ध, even in a native
    speaker's clear Hindi (it wrote तीक for ठीक and धंग for ढंग in the narrator's own reference clip)."""
    w = w.strip(PUNCT + " ")
    for a, b in (("\u093c", ""), ("ँ", ""), ("ं", ""), ("्", ""), ("ी", "ि"), ("ू", "ु"), ("ई", "इ"), ("ऊ", "उ"),
                 ("ये", "ए"), ("ौ", "ो"), ("ॉ", "ो"), ("ऑ", "ओ"), ("ट", "त"), ("ठ", "त"), ("थ", "त"), ("ड", "द"), ("ढ", "द"), ("ध", "द")):
        w = w.replace(a, b)
    return w.lower()


# Words Whisper writes as another word even when a native speaker says them clearly (it heard नहीं in six of six
# Rasa recordings of नई and नए), so a take isn't marked down for them
HEARD_AS = {"नइ": {"नहि"}, "नए": {"नहि"}, "नयि": {"नहि"}}


def _runs(text):
    """[(letters, words)] for each initialism a text spells out. A lone letter name is an ordinary word (के, जी),
    so an initialism has two letters or more, and a comma or a stop ends it."""
    out, letters, words = [], "", []
    for raw in text.split():
        s = spell(raw)
        if s:
            letters, words = letters + s, words + [raw.strip(PUNCT)]
        if not s or raw[-1] in PUNCT:
            if len(letters) >= 2:
                out.append((letters, words))
            letters, words = "", []
    if len(letters) >= 2:
        out.append((letters, words))
    return out


def initialisms(text):
    """The initialisms a voice text spells out, in English letters: "नया यू ए एन, पुराना पी एफ़" -> ["uan", "pf"]."""
    return [k for k, _ in _runs(text)]


def _tokens(text):
    return [t for t in re.split(r"[\s" + re.escape(PUNCT) + r"]+", text.replace(".", " ")) if t]


def initialism_count(key, heard):
    """How many times Whisper wrote the initialism as letters (UAN, U.A.N., यू ए एन, यूएएन). EPFO is not PF: the
    letters must make up whole words."""
    return spelled_count(key, letter_words(heard))


def _spelled_words(keys, heard):
    """Whisper's words, and which of them spell out one of keys (EPF IGMS for "epfigms")."""
    toks = [t.strip(PUNCT) for t in re.sub(r"(?<=\b[A-Za-z])\.", "", heard).replace("-", " ").split()]
    sp = [t.lower() if re.fullmatch(r"[A-Za-z]+", t) else spell(t) for t in toks]
    used = set()
    for key in set(keys):
        i = 0
        while i < len(sp):
            acc, j = "", i
            while j < len(sp) and sp[j] and key.startswith(acc + sp[j]) and acc != key:
                acc, j = acc + sp[j], j + 1
            if acc == key:
                used.update(range(i, j))
                i = j
            else:
                i += 1
    return toks, used


def _similar(a, b, at_least):
    return difflib.SequenceMatcher(None, a, b).ratio() >= at_least


def judge(text, heard, vo=""):
    """How well a take says a part: (misses, missing words, extra words). misses are initialisms and numbers not
    heard; a word Whisper writes in English letters counts when the line's Hinglish (vo) has it."""
    keys = initialisms(text)
    misses = ["initialism " + k.upper() for k in sorted(set(keys))
              for _ in range(max(0, keys.count(k) - initialism_count(k, heard)))]
    heard = re.sub(r"(?<=\b[A-Za-z])\.", "", heard)                 # P.F. is PF
    got = spoken_numbers(heard)
    misses += ["number {}".format(n) for n in spoken_numbers(text) if n >= 4 and n not in got]

    def plain_words(t):          # not an initialism's letters, nor a number the misses already check
        spelled = {w for _, ws in _runs(t) for w in ws}
        return [w for w in _tokens(t) if w not in spelled and not [n for n in spoken_numbers(w) if n >= 4]]

    def close(x, y):             # the same word, or two run together, but not a word with a sound stuck on it
        d = abs(len(x) - len(y))
        return _similar(x, y, 0.75) and (d <= max(1, len(x) // 3) or (d <= 2 and _similar(x, y, 0.8)))

    want = [fold(w) for w in plain_words(text) if not re.search(r"[0-9]", w)]
    vo_words = {w.lower() for w in _tokens(vo) if re.fullmatch(r"[A-Za-z]+", w)}
    dev = [fold(w) for w in plain_words(heard) if not re.search(r"[A-Za-z]", w)]
    toks, spelled = _spelled_words(keys, heard)
    latin = [w.lower() for k, w in enumerate(toks) if k not in spelled and re.fullmatch(r"[A-Za-z]+", w)]
    used, i, j, found = set(), 0, 0, 0
    while j < len(want):                   # in order, each heard word used once
        w, hit = want[j], None
        said = [str(n) for n in spoken_numbers(w)]                     # एक written as 1
        for k in range(i, len(dev)):
            if close(w, dev[k]) or dev[k] in HEARD_AS.get(w, ()) or dev[k] in said:
                hit = (k + 1, 1, {k})
            elif k + 1 < len(dev) and close(w, dev[k] + dev[k + 1]) and close(dev[k], w[:len(dev[k])]):
                hit = (k + 2, 1, {k, k + 1})                                  # जन्मतिथि heard as जन्म तिथि
            elif j + 1 < len(want) and close(w + want[j + 1], dev[k]) and close(w, dev[k][:len(w)]):
                hit = (k + 1, 2, {k})                                         # दो ना heard as दोना
            if hit:
                break
        if hit:
            i, step, ks = hit
            used |= ks
            found, j = found + step, j + step
        else:
            j += 1
    english = [w for w in latin if any(_similar(w, v, 0.8) for v in vo_words) and w not in keys]
    missing = max(0, len(want) - found - len(english))
    extra = len(dev) - len(used)
    extra += sum(1 for w in latin if not any(_similar(w, v, 0.8) for v in vo_words) and w not in keys)
    return misses, missing, extra


# ---------------------------------------------------------------- sound

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


def trim(a, before=0.03, after=0.08):
    """The take without the silence around its words (keeping a little, so no sound is cut)."""
    n = int(0.01 * SR)
    rms = np.array([np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a) - n, n)])
    if not len(rms):
        return a
    on = np.where(20 * np.log10(rms + 1e-9) > 20 * np.log10(rms.max() + 1e-9) - 40)[0]
    s0 = max(0, on[0] * n - int(before * SR))
    s1 = min(len(a), (on[-1] + 1) * n + int(after * SR))
    out = a[s0:s1].copy()
    fade = min(len(out) // 4, int(0.01 * SR))
    if fade:
        out[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        out[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return out


def spoken(text):
    """The text as the model is given it. A colon reads like the visarga (ः) to it, an echo sound after the word
    ("चेक:" came out "चेके है" in every take), so it gets a comma's pause instead."""
    return text.replace(":", ",")


def initialism_spans(words, keys):
    """[(key, start, end)] for each of keys Whisper wrote, from its words' times (Word tuples)."""
    sp = []
    for w in words:
        t = re.sub(r"(?<=\b[A-Za-z])\.", "", w.word).strip(PUNCT + " ")
        sp.append(t.lower() if re.fullmatch(r"[A-Za-z]+", t) else spell(t))
    out = []
    for key in sorted(set(keys)):
        i = 0
        while i < len(words):
            acc, j = "", i
            while j < len(words) and sp[j] and key.startswith(acc + sp[j]) and acc != key:
                acc, j = acc + sp[j], j + 1
            if acc == key:
                out.append((key, words[i].start, words[j - 1].end))
                i = j
            else:
                i += 1
    return out


def tighten_spans(a, spans, floor=-35):
    """Spans moved in to where there's sound: Whisper starts a take's first word before it's said, and can end a word
    in the pause after it."""
    n = int(0.01 * SR)
    rms = np.array([np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a) - n, n)]) + 1e-9
    loud = 20 * np.log10(rms / rms.max()) > floor
    out = []
    for key, t0, t1 in spans:
        k0, k1 = max(0, int(t0 * 100)), min(len(loud), int(t1 * 100))
        on = np.where(loud[k0:k1])[0]
        out.append((key, (k0 + on[0]) / 100, (k0 + on[-1] + 1) / 100) if len(on) else (key, t0, t1))
    return out


def letter_gaps(a, spans, floor=-38):
    """[(start, end)] of the pauses between an initialism's letters: quiet 10 ms frames (floor dB under the take's
    peak) inside its span, not at its edges, where the pause belongs to the words around it."""
    n = int(0.01 * SR)
    rms = np.array([np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a) - n, n)]) + 1e-9
    db = 20 * np.log10(rms / rms.max())
    out = []
    for _, t0, t1 in spans:
        k, k1 = max(0, int((t0 + 0.05) * 100)), min(len(db), int((t1 - 0.05) * 100))
        while k < k1:
            if db[k] < floor:
                j = k
                while j < k1 and db[j] < floor:
                    j += 1
                if j < k1:                                   # speech of the same initialism after it
                    out.append((k / 100, j / 100))
                k = j
            else:
                k += 1
    return out


def close_gaps(a, gaps, keep=None):
    """The take with every pause in gaps cut down to keep seconds, from its middle, crossfaded: UAN said as one
    word, not U... A... N."""
    f, keep = int(0.005 * SR), LETTER_GAP if keep is None else keep
    for g0, g1 in sorted(gaps, reverse=True):
        if g1 - g0 <= keep:
            continue
        mid, half = (g0 + g1) / 2 * SR, (g1 - g0 - keep) / 2 * SR
        s0, s1 = int(mid - half), int(mid + half)
        if s0 < f or s1 + f > len(a):
            continue
        head, tail = a[:s0].copy(), a[s1:].copy()
        head[-f:] = head[-f:] * np.linspace(1, 0, f) + tail[:f] * np.linspace(0, 1, f)
        a = np.concatenate([head, tail[f:]])
    return a


def stretch(x, factor, win=0.03, search=0.008):
    """x played factor times faster with its pitch kept: overlapping 30 ms pieces, each nudged (within 8 ms) to
    where it joins the last one most smoothly (WSOLA)."""
    n, tol = int(win * SR), int(search * SR)
    hop = n // 2
    w = np.hanning(n).astype(np.float32)
    out, norm = np.zeros(int(len(x) / factor) + 2 * n, np.float32), np.zeros(int(len(x) / factor) + 2 * n, np.float32)
    pos_in, pos_out, prev = 0.0, 0, None
    while True:
        c = int(pos_in)
        if prev is None:
            start = c
        else:
            want = x[prev + hop:prev + hop + n]
            lo, hi = max(0, c - tol), min(len(x) - n, c + tol)
            if len(want) < n or hi < lo:
                break
            start = lo + int(np.argmax([np.dot(x[k:k + n], want) for k in range(lo, hi + 1)]))
        if start + n > len(x) or pos_out + n > len(out):
            break
        out[pos_out:pos_out + n] += x[start:start + n] * w
        norm[pos_out:pos_out + n] += w
        prev, pos_out, pos_in = start, pos_out + hop, pos_in + hop * factor
    end = pos_out + hop
    tail = x[prev + hop:] if prev is not None else x
    out, norm = out[:end], np.maximum(norm[:end], 1e-3)
    out = out / norm
    return np.concatenate([out[:max(0, end - hop)], tail[:hop]]) if len(tail) >= hop else out


def quicken(a, spans):
    """Each initialism said as one quick word: its span sped up (pitch kept) to about LETTER_SEC a letter, at most
    MAX_QUICK times, joined back with 5 ms crossfades."""
    f = int(0.005 * SR)
    for key, t0, t1 in sorted(spans, key=lambda sp: -sp[1]):
        s0, s1 = max(f, int(t0 * SR)), min(len(a) - f, int(t1 * SR))
        factor = min(MAX_QUICK, (s1 - s0) / SR / (LETTER_SEC * len(key)))
        if s1 - s0 < 4 * f or factor < 1.08:
            continue
        seg = stretch(a[s0:s1], factor)
        head, tail = a[:s0].copy(), a[s1:].copy()
        seg[:f] = head[-f:] * np.linspace(1, 0, f) + seg[:f] * np.linspace(0, 1, f)
        seg[-f:] = seg[-f:] * np.linspace(1, 0, f) + tail[:f] * np.linspace(0, 1, f)
        a = np.concatenate([head[:-f], seg, tail[f:]])
    return a


def is_lead(word):
    """Whisper heard the lead word (हाँ, हां, उहाँ, Haan)."""
    return bool(re.fullmatch(r"[अआउ]?हा?न?|[अआउ]?हान|हम", fold(word))) or \
        re.sub(r"[^a-z]", "", word.lower()) in ("haan", "haa", "han", "ha", "uhaan", "aha")


def cut_lead(a, words):
    """The take without its lead word (LEAD). Cut in the quietest 10 ms between the lead and the next word, by
    Whisper's word times; or, when Whisper didn't write the lead, in the pause after a short first sound. A cut that
    takes a real word is caught when the cut take is heard again."""
    n = int(0.01 * SR)
    rms = np.array([np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a) - n, n)]) + 1e-9
    if len(words) >= 2 and is_lead(words[0].word):
        lo = int(max(words[0].start, words[0].end - 0.1) * 100)
        # the pause right after the lead: when Whisper skipped words, the next word it wrote can be a sentence later
        hi = max(lo + 1, int(min(words[1].start + 0.05, words[0].end + 0.5) * 100))
        k = lo + int(np.argmin(rms[lo:hi]))
        return a[k * n + n // 2:]
    db = 20 * np.log10(rms / rms.max())
    loud = np.where(db > -35)[0]
    if not len(loud):
        return a
    on, quiet = loud[0], 0
    for k in range(on, min(len(db), on + 60)):        # a short sound, then a pause of 0.12 s or more
        quiet = quiet + 1 if db[k] <= -35 else 0
        if quiet >= 12:
            start = k - quiet + 1
            if start - on > 40:
                break
            end = k
            while end + 1 < len(db) and db[end + 1] <= -35:
                end += 1
            return a[(start + end + 1) // 2 * n:]               # the middle of the pause
    return a


def mp3(a):
    """The samples as they come back from an mp3 like the line's file (44.1 kHz, 160 kbit/s)."""
    enc = subprocess.run(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                          "-ar", "44100", "-codec:a", "libmp3lame", "-b:a", "160k", "-f", "mp3", "-"],
                         input=np.asarray(a, np.float32).tobytes(), capture_output=True, check=True).stdout
    dec = subprocess.run(["ffmpeg", "-v", "error", "-i", "-", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-"],
                         input=enc, capture_output=True, check=True).stdout
    b = np.frombuffer(dec, np.float32)[int(1105 / 44100 * SR):]     # the encoder's and decoder's delay (1105 samples)
    return np.pad(b, (0, max(0, len(a) - len(b))))[:len(a)]      # same length, so word times still match


def level(seg):
    loud = seg[np.abs(seg) > 0.02 * (np.abs(seg).max() or 1)]
    return seg * (0.12 / (np.sqrt(np.mean(loud ** 2)) or 1))


# ---------------------------------------------------------------- the voice

class Voice:
    def __init__(self, model_dir=None, takes=TAKES, speed=SPEED, refs=None):
        from f5_tts.api import F5TTS
        from faster_whisper import WhisperModel
        if model_dir:
            ckpt, vocab = Path(model_dir) / MODEL[1], Path(model_dir) / MODEL[2]
        else:
            from huggingface_hub import hf_hub_download
            ckpt, vocab = (hf_hub_download(MODEL[0], f) for f in MODEL[1:])
        self.tts = F5TTS(model="F5TTS_Small", ckpt_file=str(ckpt), vocab_file=str(vocab), device="cpu")
        self.asr = WhisperModel("medium", device="cpu", compute_type="int8")
        self.takes, self.speed = takes, speed
        self.refs = {name: Path(p) for name, p in (refs or {}).items()}
        self._refs, self._refs_len, self._tmp = {}, {}, tempfile.TemporaryDirectory()

    def ref(self, who):
        """The reference clip for a speaker, with a pause after it (the model swallows a part's first words when
        the clip ends right on a word), and its words."""
        wav = self.refs.get(who) or VOICE_DIR / (VOICES.get(who, "narrator") + ".wav")
        if wav not in self._refs:
            import soundfile as sf
            a, sr = sf.read(wav, dtype="float32")
            a = a if a.ndim == 1 else a.mean(axis=1)
            padded = Path(self._tmp.name) / "{}-{}.wav".format(len(self._refs), wav.stem)
            sf.write(padded, np.concatenate([a, np.zeros(int(REF_PAUSE * sr), np.float32)]), sr)
            self._refs[wav] = (padded, wav.with_suffix(".txt").read_text(encoding="utf-8").strip() + " ")
            self._refs_len[padded] = len(a) / sr + REF_PAUSE
        return self._refs[wav]

    def listen(self, a, words=False):
        """What Whisper hears in a take, how sure it is, and (words=True) when each word is said."""
        from scipy.signal import resample_poly
        pad = np.zeros(int(0.3 * SR), np.float32)                       # Whisper skips words said right at the start
        x = resample_poly(np.concatenate([pad, a, pad]), 2, 3).astype(np.float32)    # 24 kHz to Whisper's 16 kHz
        segs = list(self.asr.transcribe(x, language="hi", beam_size=5, condition_on_previous_text=False,
                                        word_timestamps=words)[0])
        heard = " ".join(s.text.strip() for s in segs)
        conf = float(np.mean([s.avg_logprob for s in segs])) if segs else -9.0
        if not words:
            return heard, conf
        return heard, conf, [Word(w.start - 0.3, w.end - 0.3, w.word) for s in segs for w in (s.words or [])]

    @staticmethod
    def slow(spans):
        """How many initialisms are said slowly, letter by letter: longer than 1.3 times LETTER_SEC a letter."""
        return sum(1 for key, t0, t1 in spans if t1 - t0 > 1.3 * LETTER_SEC * len(key))

    def part(self, who, text, speed, vo, seed0):
        """The best of up to self.takes takes of one part: (samples, seed, heard, misses)."""
        from f5_tts.infer.utils_infer import infer_process
        from f5_tts.model.utils import seed_everything
        ref_wav, ref_text = self.ref(who)
        # The model gives a part as much time as its characters, at the reference speaker's pace. A spelled letter
        # takes longer to say than its one or two characters (यू ए एन came out as "यूएन"), so each gets LETTER_TIME more.
        letters = sum(len(k) for k, ws in _runs(text) if len(ws) > 1)       # written apart: यू ए एन, not यूएएन
        ref_sec = self._refs_len[ref_wav]
        length = (ref_sec + ref_sec / len(ref_text.encode("utf-8")) * len((LEAD + text).encode("utf-8")) / speed
                  + LETTER_TIME * letters) if letters else None
        best = None
        for k in range(self.takes):
            seed = seed0 + k
            seed_everything(seed)
            with contextlib.redirect_stdout(io.StringIO()):             # the model prints every text it reads
                wav, sr, _ = infer_process(str(ref_wav), ref_text, LEAD + spoken(text), self.tts.ema_model, self.tts.vocoder,
                                           self.tts.mel_spec_type, show_info=lambda *a, **kw: None, progress=None,
                                           nfe_step=32, speed=speed, fix_duration=length, device="cpu")
            a = np.asarray(wav, np.float32)
            a = trim(cut_lead(a, self.listen(a, words=True)[2]))
            # Whisper judges the take as it will be saved (mp3): a sound said faintly can be lost in the mp3
            heard, conf, words = self.listen(mp3(a), words=True)
            misses, missing, extra = judge(text, heard, vo)
            keys = initialisms(text)
            spans = tighten_spans(a, initialism_spans(words, keys))
            slow = self.slow(spans)
            if keys and slow:   # say each initialism as one quick word; keep that only if Whisper still hears it all
                b = close_gaps(a, letter_gaps(a, spans))
                b = quicken(b, tighten_spans(b, initialism_spans(self.listen(mp3(b), words=True)[2], keys)))
                heard_b, conf_b, words_b = self.listen(mp3(b), words=True)
                judged = judge(text, heard_b, vo)
                if len(judged[0]) <= len(misses) and judged[1] + judged[2] <= missing + extra:
                    a, heard, conf, (misses, missing, extra) = b, heard_b, conf_b, judged
                    slow = self.slow(tighten_spans(b, initialism_spans(words_b, keys)))
            score = (-len(misses), -(missing + extra), -slow, conf)
            print("   {} take {} · {:.2f} s · {}{} · {}".format(
                who, seed, len(a) / SR, "ok" if score[:2] == (0, 0) else
                "misses {} · {} words off".format(misses or "none", missing + extra),
                " · {} said letter by letter".format(slow) if slow else "", heard), flush=True)
            if best is None or score > best[0]:
                best = (score, a, seed, heard, misses)
            if score[:3] == (0, 0, 0) and conf > -0.35:
                break
        return best[1:]

    def line(self, line, seed0=1000):
        """One line as 24 kHz mono samples and a record of the takes kept."""
        mood = (line.get("delivery") or "").split("·")[0].strip()
        speed = round(self.speed * MOOD.get(mood, 1.0), 3)
        out, kept = [np.zeros(int(0.22 * SR), np.float32)], []
        for i, (who, text) in enumerate(parts_of(line)):
            if i:
                out.append(np.zeros(int(TURN * SR), np.float32))      # a beat when the speaker changes
            a, seed, heard, misses = self.part(who, text, speed, line.get("vo", ""), seed0 + 100 * i)
            out.append(level(compact(a)))                              # every voice equally loud
            kept.append({"who": who, "text": text, "speed": speed, "seed": seed, "heard": heard, "misses": misses})
        out.append(np.zeros(int(0.40 * SR), np.float32))
        a = np.concatenate(out)
        return a / (np.abs(a).max() or 1) * 0.89, kept


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode")
    ap.add_argument("--lines", help="only these lines, such as S05,S12")
    ap.add_argument("--takes", type=int, default=TAKES, help="most takes of a part (default %(default)s)")
    ap.add_argument("--speed", type=float, default=SPEED, help="pace (default %(default)s)")
    ap.add_argument("--model-dir", help="a folder holding {} and {}, instead of downloading them".format(*MODEL[1:]))
    ap.add_argument("--ref", action="append", default=[], metavar="WHO=CLIP.wav",
                    help="read WHO's parts in this clip's voice (its words in CLIP.txt) instead of brand/voices")
    ap.add_argument("--out", help="write the lines here instead of the episode's media/audio/lines")
    a = ap.parse_args()
    import soundfile as sf
    ep_dir = Path(a.episode)
    script = json.loads((ep_dir / "episode.json").read_text(encoding="utf-8"))["script"]
    only = set(a.lines.split(",")) if a.lines else None
    voice = Voice(a.model_dir, a.takes, a.speed, dict(r.split("=", 1) for r in a.ref))
    out_dir = Path(a.out) if a.out else ep_dir / "media" / "audio" / "lines"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "voice-takes.json"
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
    with tempfile.TemporaryDirectory() as tmp:
        for n, line in enumerate(script):
            sid = line["shot"]
            if only and sid not in only:
                continue
            print(sid, line["tts"], flush=True)
            samples, kept = voice.line(line, seed0=1000 * (n + 1))
            raw = Path(tmp) / (sid + ".wav")
            sf.write(raw, samples, SR)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-ar", "44100", "-ac", "1",
                            "-codec:a", "libmp3lame", "-b:a", "160k", str(out_dir / (sid + ".mp3"))], check=True)
            log[sid] = {"voice": "F5-Hindi", "parts": kept}
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            print("made", out_dir / (sid + ".mp3"), flush=True)


if __name__ == "__main__":
    main()
