"""The Taali style's music: a fast garba / dandiya groove made entirely in code (styles/taali/STYLE.md → The music).

Nothing is sampled or licensed: the dhol, the dandiya sticks, the manjira, the claps, the harmonium, the bansuri and
the temple bell are all synthesised here with numpy, so every reel has its own copy-free track, on the same beat grid
the pictures dance to.

    python3 tools/taali_music.py out.wav                 # a 24-bar demo at 128 BPM
    python3 tools/taali_music.py out.wav --bpm 132 --plan intro:2,verse:8,chorus:4,outro:2

The build (tools/build_taali.py) calls `render(plan, bpm, key)` with the reel's own sections.
"""
import argparse
import wave
from pathlib import Path

import numpy as np

SR = 44100
RNG = np.random.default_rng(7)

# Khamaj thaat, the scale of a lot of Gujarati folk: Sa Re Ga Ma Pa Dha komal-Ni
SWARA = {"S": 0, "R": 2, "G": 4, "M": 5, "P": 7, "D": 9, "n": 10, "N": 11}
KEYS = {"C": 261.63, "C#": 277.18, "D": 293.66, "D#": 311.13, "E": 329.63, "F": 349.23, "F#": 369.99,
        "G": 392.00, "G#": 415.30, "A": 440.00, "A#": 466.16, "B": 493.88}


# ---------------------------------------------------------------- small DSP helpers
def env_exp(n, rate):
    return np.exp(-np.arange(n) / SR * rate)


def onepole_lp(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    s = 0.0
    for i, v in enumerate(x):
        s = (1 - a) * v + a * s
        y[i] = s
    return y


def band(x, lo, hi):
    """A band-pass by FFT: fine for the short one-shots it's used on."""
    f = np.fft.rfft(x)
    fr = np.fft.rfftfreq(len(x), 1 / SR)
    f[(fr < lo) | (fr > hi)] = 0
    return np.fft.irfft(f, len(x))


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) or 1.0
    return x / m * peak


def noise(n):
    return RNG.uniform(-1, 1, n)


# ---------------------------------------------------------------- the instruments (one-shots)
def dhol_bass(v=1.0):
    """The dhol's big left head (dagga): a deep thump that falls in pitch, with a skin slap."""
    n = int(SR * 0.42)
    t = np.arange(n) / SR
    f = 52 + 70 * np.exp(-t * 22)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, 7.5)
    slap = band(noise(n), 200, 1800) * env_exp(n, 60) * 0.5
    return norm(body + slap) * v


def dhol_tilli(v=1.0):
    """The dhol's thin right head, hit with the cane: a dry, ringing crack."""
    n = int(SR * 0.16)
    t = np.arange(n) / SR
    ring = np.sin(2 * np.pi * 610 * t) * env_exp(n, 30) + 0.5 * np.sin(2 * np.pi * 1290 * t) * env_exp(n, 45)
    crack = band(noise(n), 1500, 6000) * env_exp(n, 70)
    return norm(ring * 0.6 + crack) * v


def dandiya(v=1.0, pitch=1.0):
    """Two wooden dandiya sticks hit together: a bright knock."""
    n = int(SR * 0.09)
    t = np.arange(n) / SR
    knock = (np.sin(2 * np.pi * 2150 * pitch * t) + 0.7 * np.sin(2 * np.pi * 3420 * pitch * t)
             + 0.35 * np.sin(2 * np.pi * 1180 * pitch * t)) * env_exp(n, 95)
    tick = band(noise(n), 2500, 9000) * env_exp(n, 220) * 0.8
    return norm(knock + tick) * v


def manjira(v=1.0, open_=False):
    """Small brass cymbals: an inharmonic shimmer, closed (short) or open (ringing)."""
    n = int(SR * (0.7 if open_ else 0.18))
    t = np.arange(n) / SR
    parts = [2960, 4433, 5870, 7741, 9120, 10850]
    x = sum(np.sin(2 * np.pi * p * t + RNG.uniform(0, 6)) / (i + 1) ** 0.6 for i, p in enumerate(parts))
    x = x * env_exp(n, 5 if open_ else 22) + band(noise(n), 6000, 14000) * env_exp(n, 40) * 0.4
    return norm(x) * v


def clap(v=1.0):
    """A taali: several hands clapping together."""
    n = int(SR * 0.25)
    x = np.zeros(n)
    for d in (0.0, 0.007, 0.015, 0.021):
        i = int(d * SR)
        m = n - i
        x[i:] += noise(m) * env_exp(m, 55 + RNG.uniform(-10, 10))
    return norm(band(x, 700, 5200)) * v


def bell(v=1.0, f=1180):
    """A small temple bell (ghanti), for the moment a new word appears."""
    n = int(SR * 1.6)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * f * t) * env_exp(n, 2.6) + 0.6 * np.sin(2 * np.pi * f * 2.76 * t) * env_exp(n, 4)
         + 0.35 * np.sin(2 * np.pi * f * 5.40 * t) * env_exp(n, 7) + 0.2 * np.sin(2 * np.pi * f * 8.93 * t) * env_exp(n, 11))
    x[: int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
    return norm(x) * v


def harmonium(freq, dur, v=1.0):
    """A harmonium reed: rich, nasal, two reeds a little apart for the chorus."""
    n = int(SR * (dur + 0.08))
    t = np.arange(n) / SR
    vib = 1 + 0.0025 * np.sin(2 * np.pi * 5.2 * t)
    x = np.zeros(n)
    for det in (1.0, 1.0035):
        ph = 2 * np.pi * freq * det * np.cumsum(vib) / SR
        for k in range(1, 14):
            amp = (1.0 / k ** 0.85) * (1.25 if k % 2 else 0.8)
            if freq * k > 9000:
                break
            x += amp * np.sin(k * ph)
    a = np.ones(n)
    att, rel = int(0.025 * SR), int(0.08 * SR)
    a[:att] = np.linspace(0, 1, att)
    a[-rel:] = np.linspace(1, 0, rel)
    return norm(x * a) * v


def bansuri(freq, dur, v=1.0):
    """A bamboo flute: a pure tone that blooms into vibrato, with breath."""
    n = int(SR * (dur + 0.06))
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.6 * t) * np.clip(t / 0.25, 0, 1)
    ph = 2 * np.pi * freq * np.cumsum(vib) / SR
    x = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
    x += band(noise(n), 1500, 6000) * 0.05
    a = np.ones(n)
    att, rel = int(0.04 * SR), int(0.06 * SR)
    a[:att] = np.linspace(0, 1, att) ** 2
    a[-rel:] = np.linspace(1, 0, rel)
    return norm(x * a) * v


def sub(freq, dur, v=1.0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(4 * np.pi * freq * t)
    return norm(x * env_exp(n, 3.5) * np.clip(t / 0.008, 0, 1)) * v


# ---------------------------------------------------------------- patterns
# one bar of 16 steps; the dandiya "chal" the dancers step to
GROOVE = {
    "bass":    [0, 6, 8, 11, 14],
    "tilli":   [2, 4, 7, 10, 12, 15],
    "dandiya": [4, 6, 12, 14],
    "manjira": [2, 6, 10, 14],
    "clap":    [4, 12],
}

# the melody, a 4-bar folk riff in 8ths: "-" holds the note, "." is a rest, ' goes an octave up, , down
RIFF = ["P P D P M G R G", "M - G R S - . .", "G M P D n D P M", "G - R - S - . .",
        "P P D P M G R G", "M - G R S - . .", "G M P D S' n D P", "M - G R S - - ."]
CHORUS_RIFF = ["S' - n D P - D n", "S' - . S' R' S' n D", "P - M G M P D n", "S' - - - . . . .",
               "S' - n D P - D n", "S' - . S' R' S' n D", "P D P M G R G M", "S - - - . . . ."]


def note_freq(tok, sa):
    up = tok.count("'")
    down = tok.count(",")
    base = tok.strip("',")
    return sa * 2 ** ((SWARA[base] + 12 * (up - down)) / 12)


def parse_riff(bars, sa, step):
    """[(start_seconds, freq, dur_seconds)] for a list of bars of 8 tokens."""
    out = []
    for b, bar in enumerate(bars):
        toks = bar.split()
        i = 0
        while i < len(toks):
            tok = toks[i]
            if tok in ("-", "."):
                i += 1
                continue
            j = i + 1
            while j < len(toks) and toks[j] == "-":
                j += 1
            out.append(((b * 8 + i) * step, note_freq(tok, sa), (j - i) * step))
            i = j
    return out


class Track:
    def __init__(self, seconds):
        self.x = np.zeros(int(SR * (seconds + 2.5)))
        self.duck = np.ones_like(self.x)

    def put(self, t, sig, pan=0.0):
        i = int(round(t * SR))
        if i >= len(self.x):
            return
        m = min(len(sig), len(self.x) - i)
        self.x[i:i + m] += sig[:m]

    def pump(self, t, depth=0.35, length=0.18):
        """Sidechain: the drone and harmonium dip under every bass hit, for the dance feel."""
        i = int(t * SR)
        n = int(length * SR)
        if i >= len(self.duck):
            return
        m = min(n, len(self.duck) - i)
        curve = 1 - depth * np.exp(-np.arange(m) / SR * 18)
        self.duck[i:i + m] = np.minimum(self.duck[i:i + m], curve)


# ---------------------------------------------------------------- the arrangement
def render(plan, bpm=128, key="D", bells=(), out=None):
    """plan: [(section, bars)] with section one of intro, verse, chorus, turn, outro (anything else plays as verse).
    bells: seconds at which a new word lands (a temple bell rings). Returns (stereo float array, beat grid info)."""
    beat = 60.0 / bpm
    step = beat / 4
    bar = beat * 4
    total_bars = sum(b for _, b in plan)
    seconds = total_bars * bar
    sa = KEYS.get(key, KEYS["D"])

    drums, music, extra = Track(seconds), Track(seconds), Track(seconds)

    # the one-shots, a few variants each so the groove breathes
    B = [dhol_bass(1.0), dhol_bass(0.85)]
    T = [dhol_tilli(0.55), dhol_tilli(0.42), dhol_tilli(0.48)]
    DA = [dandiya(0.55, 1.0), dandiya(0.5, 1.06), dandiya(0.6, 0.95)]
    MJ, MJO = manjira(0.16), manjira(0.22, open_=True)
    CL = clap(0.55)
    riff = parse_riff(RIFF, sa, beat / 2)
    criff = parse_riff(CHORUS_RIFF, sa, beat / 2)
    riff_len = 8 * bar

    t_bar = 0.0
    sections = []
    for name, nb in plan:
        sections.append({"part": name, "start": round(t_bar, 4), "bars": nb})
        for k in range(nb):
            t0 = t_bar + k * bar
            last_bar = k == nb - 1
            if name == "intro":
                # bar 1: harmonium swell and a bell; then the dhol rolls in, faster and louder
                if k < nb - 1:
                    for f in (sa / 2, sa * 2 ** (7 / 12) / 2, sa):
                        music.put(t0, harmonium(f, bar * 0.98, 0.18))
                    extra.put(t0, bell(0.35, 1180))
                    for s in (0, 6, 8, 14):
                        drums.put(t0 + s * step, B[1] * 0.6)
                else:
                    for s in range(16):
                        v = 0.25 + 0.75 * s / 15
                        drums.put(t0 + s * step, T[s % 3] * v)
                        if s in (0, 4, 8, 12, 14, 15):
                            drums.put(t0 + s * step, B[0] * v * 0.8)
                    drums.put(t0 + 12 * step, CL * 0.6)
                    drums.put(t0 + 14 * step, CL * 0.8)
                continue
            if name == "outro" and last_bar:
                # the big finish: three hits together, then everything rings out
                for s in (0, 3, 6):
                    drums.put(t0 + s * step, B[0] * 1.1)
                    drums.put(t0 + s * step, DA[0])
                    drums.put(t0 + s * step, CL * 0.7)
                drums.put(t0 + 6 * step, MJO * 1.4)
                for f in (sa / 2, sa, sa * 2 ** (4 / 12), sa * 2 ** (7 / 12)):
                    music.put(t0 + 6 * step, harmonium(f, bar * 1.2, 0.16))
                continue
            busy = name in ("chorus", "turn")
            for s in GROOVE["bass"]:
                drums.put(t0 + s * step, B[(s // 8) % 2])
                drums.pump(t0 + s * step)
            for i, s in enumerate(GROOVE["tilli"]):
                drums.put(t0 + s * step, T[(k + i) % 3])
            for i, s in enumerate(GROOVE["dandiya"]):
                drums.put(t0 + s * step, DA[(k + i) % 3])
            for s in range(0, 16, 2):
                drums.put(t0 + s * step, MJO if s in GROOVE["manjira"] and busy else MJ)
            if busy:
                for s in GROOVE["clap"]:
                    drums.put(t0 + s * step, CL)
                for s in (0, 8):
                    drums.put(t0 + s * step, sub(sa / 4, beat * 1.6, 0.55))
            # a dhol fill on the last bar of every section, into the next
            if last_bar and name != "outro":
                for s in (12, 13, 14, 15):
                    drums.put(t0 + s * step, T[s % 3] * 0.8)
                drums.put(t0 + 15 * step, B[0] * 0.7)
            # the drone, Sa and Pa, under everything
            for f in (sa / 2, sa * 2 ** (7 / 12) / 2):
                music.put(t0, harmonium(f, bar, 0.05))
        # the melody runs through the section, phrase-locked to its start
        sec_len = nb * bar
        if name in ("verse", "turn", "chorus", "outro") or name not in ("intro",):
            mel = criff if name in ("chorus", "turn") else riff
            vol = 0.13 if name == "verse" else 0.16
            reps = int(np.ceil(nb / 8.0))
            for r in range(reps):
                for st, f, d in mel:
                    tt = t_bar + r * riff_len + st
                    if tt >= t_bar + sec_len - (bar if name == "outro" else 0) - 1e-6:
                        continue
                    music.put(tt, harmonium(f, d * 0.92, vol))
                    if name in ("chorus", "turn"):
                        music.put(tt, bansuri(f * 2, d * 0.9, 0.09))
        t_bar += sec_len

    for t in bells:
        extra.put(t, bell(0.16, 1568))

    music.x *= drums.duck[: len(music.x)]
    # a little stereo: drums centre, harmonium a touch left, bansuri/bells a touch right (constant across a reel)
    mix_l = drums.x * 0.9 + music.x * 1.0 + extra.x * 0.8
    mix_r = drums.x * 0.9 + music.x * 0.85 + extra.x * 1.0
    st = np.stack([mix_l, mix_r], axis=1)
    st = np.tanh(st * 1.15) / np.tanh(1.15)          # gentle glue, like a warm desk
    st = st[: int(SR * (seconds + 2.0))]
    fade = int(SR * 1.5)
    st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    st = st / (np.max(np.abs(st)) or 1) * 0.89      # about -1 dB peak; the build's loudnorm sets the level
    if out:
        write_wav(out, st)
    return st, {"bpm": bpm, "beat": beat, "bar": bar, "bars": total_bars, "seconds": seconds, "sections": sections}


def write_wav(path, st):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out")
    ap.add_argument("--bpm", type=float, default=128)
    ap.add_argument("--key", default="D")
    ap.add_argument("--plan", default="intro:2,verse:8,verse:8,chorus:4,turn:4,outro:2")
    a = ap.parse_args()
    plan = [(p.split(":")[0], int(p.split(":")[1])) for p in a.plan.split(",")]
    _, info = render(plan, a.bpm, a.key, out=a.out)
    print("{} bars at {} BPM, {:.1f} s → {}".format(info["bars"], a.bpm, info["seconds"], a.out))


if __name__ == "__main__":
    main()
