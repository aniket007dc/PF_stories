#!/usr/bin/env python3
"""Re-check generated media against episode.json, without trusting the generator.

It reads the text in images and video frames with OCR and compares it with the
shot's card text. Numbers must match digit for digit; words may differ by a
letter or two (OCR isn't perfect). It also checks size, length and loudness.

  python3 tools/verify_media.py keyframe EP SHOT IMAGE     one keyframe image
  python3 tools/verify_media.py clip EP SHOT VIDEO         one shot's video clip
  python3 tools/verify_media.py voice EP AUDIO             the voiceover track
  python3 tools/verify_media.py final EP VIDEO             the finished reel
  python3 tools/verify_media.py all EP                     every file found in EP/media/

Needs ffmpeg and ffprobe. For text checks it needs an OCR engine:
  pip install rapidocr-onnxruntime      (recommended)   or the tesseract command.
Add --write to save the report in EP/checks/. Exit code 1 means a check failed.
"""
import argparse
import difflib
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402

_OCR = None


def clean(text):
    """OCR text in plain characters. RapidOCR sometimes returns full-width letters and digits (ＡＴＫＡ, ２):
    NFKC folds them to ATKA and 2, so a card that is right isn't read as wrong. ₹ and arrows stay as they are."""
    return unicodedata.normalize("NFKC", text)


def ocr_engine():
    """Return (function(path) -> list of {"text", "cy", "cx", "box"}, name), or (None, None).

    cy and cx are the centre of the text as shares of the image height and width (0 = top, left), and box
    its [x0, y0, x1, y1] in the same shares; None when the engine can't say where the text is.
    """
    global _OCR
    if _OCR is not None:
        return _OCR
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
        engine = RapidOCR()

        def run(path):
            result, _ = engine(str(path))
            w, h = image_size(path)
            out = []
            for box, text, _conf in (result or []):
                cy = sum(p[1] for p in box) / len(box) / h if h else None
                cx = sum(p[0] for p in box) / len(box) / w if w else None
                xs, ys = [p[0] for p in box], [p[1] for p in box]
                frame = [min(xs) / w, min(ys) / h, max(xs) / w, max(ys) / h] if w and h else None
                out.append({"text": clean(text), "cy": cy, "cx": cx, "box": frame})
            return out
        _OCR = (run, "RapidOCR")
    except Exception:  # noqa: BLE001
        if shutil.which("tesseract"):
            def run(path):
                proc = subprocess.run(["tesseract", str(path), "stdout", "--psm", "11"],
                                      capture_output=True, text=True)
                return [{"text": clean(line), "cy": None, "cx": None, "box": None}
                        for line in proc.stdout.splitlines() if line.strip()]
            _OCR = (run, "tesseract")
        else:
            _OCR = (None, None)
    return _OCR


# Cards live between 17% and 65% of the frame height (brand.json safe zones);
# a little slack either side for rotated cards and stamps.
BAND = (0.17, 0.68)


def outside_screens(lines, boxes, crop_top, crop_h, width):
    """The OCR lines that aren't on a screenshot. A screenshot's own words (the portal's menus and buttons)
    aren't card text, so the check leaves them out. boxes are frame pixels (timeline.json "screens");
    a line's cx and cy are shares of the crop that starts crop_top pixels down and is crop_h tall."""
    out = []
    for l in lines:
        if boxes and l.get("cx") is not None and l.get("cy") is not None:
            x, y = l["cx"] * width, crop_top + l["cy"] * crop_h
            if any(x0 - 10 <= x <= x1 + 10 and y0 - 10 <= y <= y1 + 10 for x0, y0, x1, y1 in boxes):
                continue
        out.append(l)
    return out


def split_band(lines):
    """Lines inside the card band, and lines outside it."""
    inside = [l["text"] for l in lines if l["cy"] is None or BAND[0] <= l["cy"] <= BAND[1]]
    outside = [l["text"] for l in lines if l["cy"] is not None and not (BAND[0] <= l["cy"] <= BAND[1])]
    return inside, outside


# ---------------------------------------------------------------- text matching

def letters(s):
    return re.sub(r"[^A-Z]", "", s.upper())


def number_tokens(text):
    """Numbers read by OCR, with commas and dots removed. O and I next to digits count as 0 and 1."""
    t = re.sub(r"(?<=\d)[Oo]|[Oo](?=\d)", "0", text)
    t = re.sub(r"(?<=\d)[Il|]|[Il|](?=\d)", "1", t)
    return [re.sub(r"[,.]", "", m) for m in re.findall(r"\d[\d,.]*\d|\d", t)]


def expected_numbers(s):
    return [re.sub(r"[,.]", "", m) for m in re.findall(r"\d[\d,.]*\d|\d", s)]


def rupee_numbers(s):
    """The numbers s writes with the ₹ sign in front: {'100000'} for 'HAR ₹1,00,000 PE'."""
    return {re.sub(r"[,.]", "", m) for m in re.findall(r"₹\s?(\d[\d,.]*\d|\d)", s)}


def rupee_misread(token, n, with_rupee):
    """OCR read the ₹ sign in front of n as a digit: as a 7 or a 2, and in the small type of a card's tab also as
    a 5 ('5100000' for ₹1,00,000). The 5 counts only when the card writes n with ₹ (with_rupee)."""
    return len(token) == len(n) + 1 and token.endswith(n) and (token[0] in "72" or (with_rupee and token[0] == "5"))


def best_ratio(needle, hay):
    if not needle:
        return 1.0
    if needle in hay:
        return 1.0
    n, best = len(needle), 0.0
    for i in range(0, max(1, len(hay) - n + 1)):
        r = difflib.SequenceMatcher(None, needle, hay[i:i + n]).ratio()
        if r > best:
            best = r
    return best


def joined_runs(expected):
    """For each expected string with two or more numbers, its digits run together.

    OCR often drops the sign between two numbers: '₹15,000 ÷ 30' comes back as '1500030'.
    A run like that proves every digit is right and in order, but not the sign between them.
    """
    runs = {}
    for s in expected:
        nums = expected_numbers(s)
        if len(nums) >= 2:
            runs["".join(nums)] = nums
    return runs


def run_match(token, runs):
    """The joined run this OCR token is (the ₹ sign may be read as a 7 or 2 in front), or None."""
    for j in runs:
        if token == j or (len(token) == len(j) + 1 and token.endswith(j) and token[0] in "72"):
            return j
    return None


def match_strings(expected, ocr_lines):
    """Compare each expected string with what OCR read. Returns a list of result dicts."""
    stream = " ".join(ocr_lines)
    hay_letters = letters(stream)
    found_numbers = number_tokens(stream)
    runs = joined_runs(expected)
    found_runs = {run_match(t, runs) for t in found_numbers} - {None}
    ocr_words = [letters(w) for line in ocr_lines for w in re.split(r"[\s·•:|/]+", line) if letters(w)]
    results = []
    for s in expected:
        want_letters, want_nums, rupee = letters(s), expected_numbers(s), rupee_numbers(s)
        if len(want_letters) + sum(len(n) for n in want_nums) < 2:
            results.append({"text": s, "result": "eye", "detail": "too short or only symbols; check by eye"})
            continue
        problems, sign_unread, digit_unread = [], False, []
        for n in want_nums:
            if n in found_numbers:
                continue
            # the ₹ sign is sometimes read as a digit in front of the number
            if any(rupee_misread(t, n, n in rupee) for t in found_numbers):
                continue
            if "".join(want_nums) in found_runs:
                sign_unread = True
                continue
            if len(n) == 1 and not [t for t in found_numbers if len(t) == 1 and t != n and t not in want_nums]:
                digit_unread.append(n)      # OCR often drops a lone digit; a different lone digit still fails
                continue
            near = [t for t in found_numbers if len(t) == len(n)]
            problems.append("number {} not found{}".format(
                n, " (read: {})".format(", ".join(near)) if near else ""))
        if want_letters:
            ratio = 1.0 if (len(want_letters) <= 4 and want_letters in hay_letters) else best_ratio(want_letters, hay_letters)
            if ratio < (1.0 if len(want_letters) <= 4 else 0.8) and not words_found(s, hay_letters, ocr_words):
                problems.append("words not found (best match {:.0%})".format(ratio))
        if problems:
            results.append({"text": s, "result": "fail", "detail": "; ".join(problems)})
        elif digit_unread:
            results.append({"text": s, "result": "eye", "detail": "the words match, but OCR didn't read the single digit {}; check it by eye".format(
                " and ".join(digit_unread))})
        elif sign_unread:
            results.append({"text": s, "result": "eye", "detail": "OCR read the numbers as one run, {}: every digit matches and is in order, but the sign between them can't be read; check it by eye".format(
                "".join(want_nums))})
        else:
            results.append({"text": s, "result": "pass", "detail": ""})
    return results


def words_found(expected_text, hay_letters, ocr_words):
    """Every word of the expected text is there, in any order: OCR splits tilted or letter-spaced
    labels into pieces and sorts them by height, so the letters don't always come out in sequence."""
    need = [letters(w) for w in expected_text.split() if len(letters(w)) >= 2]
    if not need:
        return False
    for w in need:
        if w in hay_letters:
            continue
        if len(w) >= 4 and any(difflib.SequenceMatcher(None, w, o).ratio() >= 0.8 for o in ocr_words):
            continue
        return False
    return True


def unexpected_numbers(expected, ocr_lines):
    allowed, rupee = set(), set()
    for s in expected:
        allowed.update(expected_numbers(s))
        rupee.update(rupee_numbers(s))
    runs = joined_runs(expected)
    extra = []
    for t in number_tokens(" ".join(ocr_lines)):
        if t in allowed or len(t) <= 1 or run_match(t, runs):
            continue
        if any(rupee_misread(t, a, a in rupee) for a in allowed):
            continue
        extra.append(t)
    return sorted(set(extra))


def one_edit_apart(a, b):
    if abs(len(a) - len(b)) != 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    return any(b[:i] + b[i + 1:] == a for i in range(len(b)))


def near_miss(token, expected):
    """The expected number this token looks like a wrong copy of (₹15,800 for ₹15,000), or None."""
    if len(token) < 3:
        return None
    best, best_d = None, 3
    for n in expected:
        if len(n) < 3 or n == token:
            continue
        if len(n) == len(token):
            d = sum(x != y for x, y in zip(n, token))
        elif one_edit_apart(n, token):
            d = 1
        else:
            continue
        if d < best_d:
            best, best_d = n, d
    return best


# ---------------------------------------------------------------- media helpers

def probe(path):
    proc = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                           "stream=codec_type,width,height,r_frame_rate:format=duration",
                           "-of", "default=noprint_wrappers=1", str(path)], capture_output=True, text=True)
    info = {"video": False, "audio": False}
    for line in proc.stdout.splitlines():
        k, _, v = line.partition("=")
        if k == "codec_type":
            info[v] = True
        elif k in ("width", "height") and v.isdigit():
            info[k] = int(v)
        elif k == "r_frame_rate" and "/" in v and "fps" not in info:
            a, b = v.split("/")
            if float(b) and float(a):
                info["fps"] = round(float(a) / float(b), 2)
        elif k == "duration":
            try:
                info["duration"] = float(v)
            except ValueError:
                pass
    return info


def loudness(path):
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                          capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?\d+(?:\.\d+)?) LUFS", proc.stderr)
    return float(m[-1]) if m else None


def frame_at(video, t, out, crop=None):
    vf = ["scale=iw:ih"]
    if crop:
        vf = [crop]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "{:.3f}".format(max(0.0, t)), "-i", str(video),
                    "-frames:v", "1", "-vf", ",".join(vf), str(out)], check=True)
    return out


def image_size(path):
    info = probe(path)
    return info.get("width"), info.get("height")


# ---------------------------------------------------------------- checks

class Result:
    def __init__(self, title):
        self.title = title
        self.lines = []
        self.failed = False
        self.out_of_date = False

    def ok(self, msg):
        self.lines.append("- PASS · " + msg)

    def bad(self, msg):
        self.failed = True
        self.lines.append("- FAIL · " + msg)

    def warn(self, msg):
        self.lines.append("- WARN · " + msg)

    def note(self, msg):
        self.lines.append("- " + msg)

    def text(self):
        head = "## {} · {}".format(self.title, "FAIL" if self.failed else "PASS")
        return head + "\n\n" + "\n".join(self.lines) + "\n"


def load_episode(ep_dir):
    ep = dc.load_json(Path(ep_dir) / "episode.json")
    return ep, {s["id"]: s for s in ep.get("shots", [])}


def text_check(res, expected, ocr_lines, label, outside=None, handwritten=()):
    """ocr_lines: text read inside the card band. outside: text read elsewhere in the frame.
    handwritten: strings drawn in handwriting, which OCR often can't read; if one isn't found and has
    no numbers, it's left for a person to check by eye instead of failing."""
    for m in match_strings(expected, ocr_lines):
        if m["result"] == "fail" and m["text"] in handwritten and not expected_numbers(m["text"]):
            m = dict(m, result="eye", detail="handwriting, which OCR can't read reliably; check it by eye")
        if m["result"] == "pass":
            res.ok("{} `{}`".format(label, m["text"]))
        elif m["result"] == "eye":
            res.note("CHECK BY EYE · `{}` ({})".format(m["text"], m["detail"]))
        else:
            res.bad("{} `{}`: {}".format(label, m["text"], m["detail"]))
    want = [n for s in expected for n in expected_numbers(s)]
    extra = unexpected_numbers(expected, ocr_lines)
    wrong = [(t, near_miss(t, want)) for t in extra if near_miss(t, want)]
    for t, n in wrong:
        res.bad("{} shows {}, which looks like a wrong copy of {}".format(label, t, n))
    other = [t for t in extra if not near_miss(t, want)]
    if other:
        res.warn("{}: numbers on the cards that aren't in the card text: {}".format(label, ", ".join(other)))
    if outside:
        res.warn("{}: text outside the card band (top 17% / bottom 35% should be plain paper): {}".format(
            label, " | ".join(outside[:6]) + (" …" if len(outside) > 6 else "")))


def check_aspect(res, w, h, label="frame"):
    if not w or not h:
        res.bad("can't read the {} size".format(label))
        return
    ratio = w / h
    if abs(ratio - 9 / 16) <= 0.01:
        res.ok("{} is vertical 9:16 ({}×{})".format(label, w, h))
    else:
        res.bad("{} is {}×{}, not 9:16".format(label, w, h))
    if h < 1280:
        res.warn("{} is only {} px tall; text will look soft at 1080×1920".format(label, h))


def check_keyframe(ep_dir, shot_id, image):
    _, shots = load_episode(ep_dir)
    shot = shots[shot_id]
    res = Result("Keyframe {} · {}".format(shot_id, dc.rel(image)))
    w, h = image_size(image)
    check_aspect(res, w, h, "image")
    run, name = ocr_engine()
    if not run:
        res.bad("no OCR engine: pip install rapidocr-onnxruntime (or install tesseract), or check the text by eye and approve with --no-ocr")
        return res
    res.note("OCR engine: " + name)
    inside, outside = split_band(run(image))
    text_check(res, shot.get("card_text", []), inside, "text", outside)
    return res


def check_clip(ep_dir, shot_id, video):
    _, shots = load_episode(ep_dir)
    shot = shots[shot_id]
    res = Result("Clip {} · {}".format(shot_id, dc.rel(video)))
    info = probe(video)
    check_aspect(res, info.get("width"), info.get("height"), "clip")
    dur = info.get("duration") or 0
    want = shot["end"] - shot["start"]
    if dur < want - 0.5:
        res.warn("clip is {:.1f} s; the shot needs {:.1f} s (it can be slowed or held in the edit)".format(dur, want))
    else:
        res.ok("clip is {:.1f} s (shot needs {:.1f} s)".format(dur, want))
    run, name = ocr_engine()
    if not run:
        res.bad("no OCR engine: pip install rapidocr-onnxruntime (or install tesseract)")
        return res
    res.note("OCR engine: " + name)
    expected = shot.get("card_text", [])
    want_nums = [n for s in expected for n in expected_numbers(s) if len(n) >= 2]
    all_want = [n for s in expected for n in expected_numbers(s)]
    with tempfile.TemporaryDirectory() as tmp:
        last = frame_at(video, max(0.0, dur - 0.1), Path(tmp) / "last.png")
        inside, outside = split_band(run(last))
        text_check(res, expected, inside, "last frame", outside)
        # numbers must never change into different numbers while the clip plays
        samples, t = [], 0.5
        while t < dur - 0.2 and len(samples) < 30:
            samples.append(t)
            t += 0.5
        runs = joined_runs(expected)
        seen, morphs, gaps = {}, [], {}
        for i, t in enumerate(samples):
            inside, _ = split_band(run(frame_at(video, t, Path(tmp) / "f{}.png".format(i))))
            toks = number_tokens(" ".join(inside))
            present = set(toks)
            for tok in toks:
                j = run_match(tok, runs)
                if j:
                    present.update(runs[j])
                    continue
                n = near_miss(tok, all_want) if tok not in all_want else None
                if n:
                    morphs.append("{} shows as {} at {:.1f} s".format(n, tok, t))
            for n in want_nums:
                if n in present:
                    seen.setdefault(n, t)
                    continue
                if n in seen and not any(near_miss(x, [n]) for x in toks):
                    gaps[n] = gaps.get(n, 0) + 1
        for m in sorted(set(morphs)):
            res.bad("number changed while playing: " + m)
        for n, first in seen.items():
            later = [t for t in samples if t > first]
            if later and gaps.get(n, 0) / len(later) > 0.3:
                res.warn("{} disappears or blurs in {} of {} frames after it lands".format(n, gaps[n], len(later)))
        if not morphs:
            res.ok("numbers stay the same in {} sampled frames".format(len(samples)))
    return res


def check_voice(ep_dir, audio):
    ep, _ = load_episode(ep_dir)
    rules = dc.brand().get("rules", {})
    res = Result("Voice · {}".format(dc.rel(audio)))
    info = probe(audio)
    if not info.get("audio"):
        res.bad("no audio stream")
        return res
    dur = info.get("duration") or 0
    words = sum(len(l.get("vo", "").split()) for l in ep.get("script", []))
    voice_slot = ep["shots"][-1]["end"] - rules.get("tail_seconds", 3) if ep.get("shots") else 0
    res.note("{} words in {:.1f} s = {:.2f} words/s".format(words, dur, words / dur if dur else 0))
    if voice_slot and abs(dur - voice_slot) > 5:
        res.warn("the voice is {:.1f} s; the shot plan leaves {:.1f} s for it. Re-time the shots in step 8.".format(dur, voice_slot))
    else:
        res.ok("length {:.1f} s fits the plan ({:.1f} s)".format(dur, voice_slot))
    lufs = loudness(audio)
    if lufs is not None:
        res.note("loudness {:.1f} LUFS (the final mix should be about −14)".format(lufs))
    res.note("CHECK BY EAR · every number is said correctly: " + ", ".join(
        "{} ({})".format(l["shot"], ", ".join(n["raw"] for n in dc.extract_numbers(l.get("vo", ""))))
        for l in ep.get("script", []) if dc.extract_numbers(l.get("vo", ""))))
    return res


def check_final(ep_dir, video, use_ocr=True):
    ep, _ = load_episode(ep_dir)
    b = dc.brand()
    rules, canvas = b.get("rules", {}), b.get("canvas", {})
    res = Result("Final reel · {}".format(dc.rel(video)))
    tl = Path(ep_dir) / "build" / "timeline.json"
    built_from = dc.load_json(tl).get("inputs") if tl.exists() else None
    if built_from and built_from != dc.reel_inputs_hash(ep_dir):
        res.note("OUT OF DATE · this reel was built from older episode files; GitHub rebuilds it after the upload "
                 "(Build reel) and checks it then")
        res.out_of_date = True
        return res
    info = probe(video)
    w, h = info.get("width"), info.get("height")
    if (w, h) == (canvas.get("width", 1080), canvas.get("height", 1920)):
        res.ok("size {}×{}".format(w, h))
    else:
        res.bad("size is {}×{}; export at {}×{}".format(w, h, canvas.get("width", 1080), canvas.get("height", 1920)))
    fps = info.get("fps")
    if fps and abs(fps - canvas.get("fps", 30)) <= 0.5:
        res.ok("{} fps".format(fps))
    else:
        res.warn("frame rate is {}; export at {} fps".format(fps, canvas.get("fps", 30)))
    dur = info.get("duration") or 0
    lo, hi = rules.get("duration_seconds", [85, 95])
    if lo - 5 <= dur <= hi + 5:
        res.ok("length {:.1f} s".format(dur))
    else:
        res.bad("length {:.1f} s is far from the {}–{} s target".format(dur, lo, hi))
    if info.get("audio"):
        res.ok("has sound")
        lufs = loudness(video)
        llo, lhi = rules.get("loudness_lufs", [-16, -12])
        if lufs is None:
            res.warn("couldn't measure loudness")
        elif llo <= lufs <= lhi:
            res.ok("loudness {:.1f} LUFS".format(lufs))
        else:
            res.warn("loudness {:.1f} LUFS; aim for about −14 ({} to {})".format(lufs, llo, lhi))
    else:
        res.bad("no sound")
    if not use_ocr:
        res.note("text checks skipped (--no-ocr)")
        return res
    run, name = ocr_engine()
    if not run:
        res.bad("no OCR engine: pip install rapidocr-onnxruntime (or install tesseract), or run with --no-ocr and check by eye")
        return res
    res.note("OCR engine: {} · each shot's cards are read just before the shot ends (card band only, so captions can't stand in for cards)".format(name))
    scale = dur / ep["shots"][-1]["end"] if ep.get("shots") and dur else 1.0
    built, hand, screens = {}, {}, {}
    tl = Path(ep_dir) / "build" / "timeline.json"
    if tl.exists():
        timeline = dc.load_json(tl)
        if abs(timeline.get("length", 0) - dur) < 0.5:
            built = {s["id"]: s["end"] for s in timeline.get("shots", [])}
            hand = {s["id"]: s.get("handwritten", []) for s in timeline.get("shots", [])}
            screens = {s["id"]: s.get("screens", []) for s in timeline.get("shots", [])}
            res.note("shot times from build/timeline.json (written by tools/build_reel.py)")
    if not built and abs(scale - 1) > 0.03:
        res.note("the reel is {:.1f} s and the plan is {:.1f} s, so shot times are scaled by {:.2f}".format(
            dur, ep["shots"][-1]["end"], scale))
    crop = "crop=iw:ih*0.485:0:ih*0.175"   # the cards only: below the header and its timecode, above the captions
    with tempfile.TemporaryDirectory() as tmp:
        for sh in ep.get("shots", []):
            t = (built[sh["id"]] if sh["id"] in built else sh["end"] * scale) - 0.35
            read = run(frame_at(video, t, Path(tmp) / "{}.png".format(sh["id"]), crop))
            if screens.get(sh["id"]):
                fw, fh = w or canvas.get("width", 1080), h or canvas.get("height", 1920)
                read = outside_screens(read, screens[sh["id"]], fh * 0.175, fh * 0.485, fw)
            lines = [l["text"] for l in read]
            sub = Result(sh["id"])
            text_check(sub, sh.get("card_text", []), lines, sh["id"], handwritten=hand.get(sh["id"], ()))
            res.lines.extend(sub.lines)
            res.failed = res.failed or sub.failed
    return res


def check_screens(ep_dir):
    """The portal screenshots in reel.json "screens", read with OCR:
    - each shows the words in its "must_show" (the menus and buttons the voice names), in the part the reel
      shows, so a screenshot of the wrong page, or a portal that has renamed a menu, is caught;
    - each mark that names its "text" sits on that text; if it doesn't, the report gives the box to use.
    None when the reel has no screenshots."""
    path = Path(ep_dir) / "reel.json"
    reel = dc.load_json(path) if path.exists() else {}
    screens = reel.get("screens", {})
    if not screens:
        return None
    res = Result("Screenshots")
    run, name = ocr_engine()
    read = {}
    for key, sc in screens.items():
        label = sc.get("id", key)
        f = dc.ROOT / sc["file"]
        if not f.exists():
            res.note("{} isn't there yet ({}): a person takes it".format(label, sc["file"]))
            continue
        if not run:
            res.note("{}: no OCR engine, so a person checks it by eye".format(label))
            continue
        read[key] = run(f)
        crop = sc.get("crop", [0, 0, 1, 1])
        if "crop" not in sc:
            iw, ih = image_size(f)
            tip = _crop_for(sc.get("must_show", []), read[key], iw, ih)
            if tip:
                res.bad("{} · no crop, so the reel would show the whole page, too small to read: add \"crop\": "
                        "[{}] to it in reel.json screens".format(label, ", ".join("{:.2f}".format(v) for v in tip)))
        inside = [l for l in read[key] if l.get("box") and _in(l, crop)]
        for want in sc.get("must_show", []):
            if _shows(want, inside):
                res.ok("{} shows `{}`".format(label, want))
            else:
                best = _best_line(want, inside, 0.0)
                res.bad("{} doesn't show `{}` (closest: {}): take it again, or if the portal now says something else, "
                        "the script must change".format(label, want, "`{}`".format(best["text"]) if best else "nothing"))
    for sid, els in reel.get("shots", {}).items():
        for el in els:
            if el.get("type") != "screen" or el.get("src") not in read:
                continue
            sc = screens[el["src"]]
            crop = el.get("crop", sc.get("crop", [0, 0, 1, 1]))
            for mk in el.get("marks", []):
                if not mk.get("text") or not mk.get("box"):
                    continue
                area = _to_image(mk["box"], crop, pad=0.02)
                near = [l for l in read[el["src"]] if l.get("box") and _in(l, area)]
                if _shows(mk["text"], near):
                    res.ok("{} · the mark on {} sits on `{}`".format(sid, sc.get("id", el["src"]), mk["text"]))
                    continue
                best = _best_line(mk["text"], [l for l in read[el["src"]] if l.get("box") and _in(l, crop)])
                where = (": put it at \"box\": [{}]".format(", ".join("{:.2f}".format(v) for v in _to_crop(best["box"], crop)))
                         if best else ": the screenshot doesn't show it in the part the reel uses")
                res.bad("{} · the mark on {} isn't on `{}`{}".format(sid, sc.get("id", el["src"]), mk["text"], where))
    return res


def _crop_for(words, lines, iw, ih):
    """For a tall screenshot without a crop: the full-width band round the lines that show words, at
    least 0.7 of the width tall. None when the screenshot isn't tall or none of the words is found."""
    if not (iw and ih) or ih < iw:
        return None
    hits = [l for l in lines if l.get("box") and any(_best_line(t, [l]) for t in words)]
    if not hits:
        return None
    y0, y1 = min(l["box"][1] for l in hits) - 0.04, max(l["box"][3] for l in hits) + 0.04
    least = 0.7 * iw / ih
    if y1 - y0 < least:
        c = (y0 + y1) / 2
        y0, y1 = c - least / 2, c + least / 2
    shift = max(0.0, -y0) - max(0.0, y1 - 1)
    return [0.0, round(max(0.0, y0 + shift), 2), 1.0, round(min(1.0, y1 + shift), 2)]


def _in(line, box):
    """Whether an OCR line's centre is inside box ([x0, y0, x1, y1], shares of the image)."""
    return box[0] <= line["cx"] <= box[2] and box[1] <= line["cy"] <= box[3]


def _to_image(box, crop, pad=0.0):
    """A box in shares of a crop, as shares of the whole image, padded by pad (shares of the crop)."""
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    return [crop[0] + (box[0] - pad) * cw, crop[1] + (box[1] - pad) * ch,
            crop[0] + (box[2] + pad) * cw, crop[1] + (box[3] + pad) * ch]


def _to_crop(box, crop):
    """A box in shares of the whole image, as shares of the crop."""
    cw, ch = crop[2] - crop[0], crop[3] - crop[1]
    return [(box[0] - crop[0]) / cw, (box[1] - crop[1]) / ch, (box[2] - crop[0]) / cw, (box[3] - crop[1]) / ch]


def _alnum(s):
    """Letters and digits only, in order: how a screenshot's label is compared, so OCR's spacing and punctuation
    (31,19 for "31, 19") don't matter, but a different word or number does."""
    return re.sub(r"[^A-Z0-9]", "", clean(s).upper())


def _shows(want, lines, at_least=0.85):
    """Whether OCR lines read like want: inside one line or two neighbours, or close enough to one of them."""
    w = _alnum(want)
    if not w:
        return True
    texts = [_alnum(l["text"]) for l in lines]
    if any(w in t for t in texts + [a + b for a, b in zip(texts, texts[1:])]):
        return True
    return any(difflib.SequenceMatcher(None, w, t).ratio() >= at_least for t in texts if t)


def _best_line(text, lines, at_least=0.6):
    """The OCR line that reads most like text, if one is close enough."""
    want = _alnum(text)
    scored = [(difflib.SequenceMatcher(None, want, _alnum(l["text"])).ratio(), i) for i, l in enumerate(lines)
              if _alnum(l["text"])]
    if not scored:
        return None
    ratio, i = max(scored)
    return lines[i] if ratio >= at_least else None


def find_media(ep_dir):
    media = Path(ep_dir) / "media"
    jobs = []
    for p in sorted((media / "keyframes").glob("S*.*")):
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            jobs.append(("keyframe", p.stem.split("_")[0], p))
    for p in sorted((media / "clips").glob("S*.*")):
        if p.suffix.lower() in (".mp4", ".mov", ".webm"):
            jobs.append(("clip", p.stem.split("_")[0], p))
    for p in sorted((media / "audio").glob("*.*")):
        if p.suffix.lower() in (".wav", ".mp3", ".m4a", ".aac"):
            jobs.append(("voice", None, p))
    for p in sorted((media / "final").glob("*.*")):
        if p.suffix.lower() in (".mp4", ".mov"):
            jobs.append(("final", None, p))
    return jobs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["keyframe", "clip", "voice", "final", "all"])
    ap.add_argument("episode")
    ap.add_argument("args", nargs="*", help="SHOT and FILE for keyframe/clip, FILE for voice/final")
    ap.add_argument("--no-ocr", action="store_true", help="final: skip the text checks")
    ap.add_argument("--write", action="store_true", help="save the report in EPISODE/checks/")
    a = ap.parse_args()
    ep_dir = Path(a.episode).resolve()
    if a.mode == "all":
        jobs = find_media(ep_dir)
        if not jobs and check_screens(ep_dir) is None:
            print("No media found in {}/media/. Nothing to check.".format(dc.rel(ep_dir)))
            return 0
    elif a.mode in ("keyframe", "clip"):
        if len(a.args) != 2:
            ap.error("{} needs SHOT and FILE".format(a.mode))
        jobs = [(a.mode, a.args[0], Path(a.args[1]))]
    else:
        if len(a.args) != 1:
            ap.error("{} needs FILE".format(a.mode))
        jobs = [(a.mode, None, Path(a.args[0]))]
    results = []
    for mode, shot, path in jobs:
        if not path.exists():
            r = Result("{} · {}".format(mode, path))
            r.bad("file not found")
        elif mode == "keyframe":
            r = check_keyframe(ep_dir, shot, path)
        elif mode == "clip":
            r = check_clip(ep_dir, shot, path)
        elif mode == "voice":
            r = check_voice(ep_dir, path)
        else:
            r = check_final(ep_dir, path, use_ocr=not a.no_ocr)
        results.append(r)
    if a.mode == "all":
        r = check_screens(ep_dir)
        if r is not None:
            results.append(r)
    report = "# Media checks · {}\n\n".format(ep_dir.name) + "\n".join(r.text() for r in results)
    print(report)
    if a.write:
        (ep_dir / "checks").mkdir(exist_ok=True)
        name = "media-{}{}.md".format(a.mode, "-" + jobs[0][1] if a.mode in ("keyframe", "clip") else "")
        (ep_dir / "checks" / name).write_text(report, encoding="utf-8")
    return 1 if any(r.failed for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
