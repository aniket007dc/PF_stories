"""How a line feels: one feeling per script line, the voice's audio tag for it, and what the reel shows.

Every script line has an "emotion", one of FEELINGS. The voice says the line with that feeling: Eleven v4 acts out
an audio tag such as [excited] put in front of the words, and never says it. The Host and Chatur Kauwa reels show it
a little: a mark by the speaker's head, the speech bubble's edge, a small move, and a pose when the line sets none.

A line's "tts" may also carry up to MAX_INLINE tags inside it, where the feeling changes ("[sighs]", "[laughs]",
another feeling's tag). INLINE lists the ones allowed. The captions ("vo") never have tags.

Episodes started on or after FROM give every line a feeling (tools/validate.py, E3.23 to E3.26). An older episode keeps
the voice it was made with: its lines carry no feeling, so nothing about them changes.
"""
import datetime
import re
from collections import namedtuple

FROM = "2026-11-14"                 # episodes started on or after this day give every line a feeling
MAX_INLINE = 2                      # tags inside one line's tts, on top of its feeling's own

Feeling = namedtuple("Feeling", "tag mark bubble move poses when")

FEELINGS = {
    "calm": Feeling("", "", "plain", "", (),
                    "plain explaining, no tag: the voice as it is"),
    "confident": Feeling("[confident]", "", "plain", "lean", (),
                         "sure and steady: the host's steps and answers"),
    "excited": Feeling("[excited]", "burst", "pop", "hop", ("celebrate", "thumbs_up", "clap"),
                       "good news, a big result, the twist that helps"),
    "happy": Feeling("[happy]", "notes", "pop", "hop", ("thumbs_up", "ok", "clap"),
                     "relief, a win, \"ho gaya!\""),
    "playful": Feeling("[playful]", "sparkle", "plain", "hop", ("ok", "thumbs_up"),
                       "a light tease or joke, the share line"),
    "surprised": Feeling("[surprised]", "bang", "pop", "jump", ("surprised",),
                         "\"kya?!\": a number or fact nobody expected"),
    "curious": Feeling("[curious]", "question", "plain", "lean", ("think",),
                       "a real question: \"matlab…?\", \"kaise?\""),
    "sarcastic": Feeling("[sarcastic]", "", "plain", "", ("shrug",),
                         "the dry \"wah, kya baat hai\" about a platform or a bad habit"),
    "warm": Feeling("[warmly]", "heart", "plain", "nod", ("open_hand", "wave"),
                    "kind and close: encouragement, the sign-off"),
    "urgent": Feeling("[urgently]", "pulse", "plain", "lean", ("point",),
                      "a deadline or a warning: \"abhi check karo\""),
    "worried": Feeling("[worried]", "sweat", "soft", "tremble", ("think",),
                       "the viewer's doubt, the fear of losing money"),
    "sad": Feeling("[sad]", "cloud", "soft", "droop", ("shrug",),
                   "disappointment: the money's gone, the result wasn't real"),
    "frustrated": Feeling("[frustrated]", "scribble", "spiky", "shake", ("facepalm", "arms_crossed"),
                          "fed up: \"phir se?!\", the same problem again"),
    "angry": Feeling("[angry]", "vein", "spiky", "shake", ("arms_crossed", "facepalm"),
                     "real anger, rarely: at a scam or a loss, never at the viewer"),
    "whisper": Feeling("[whispers]", "", "dashed", "lean", (),
                       "a secret or an insider tip, said low"),
}
CALM = FEELINGS["calm"]

# How each feeling sounds: pitch, pace and how the line ends. Eleven v4 has no pitch or speed setting: the feeling's
# tag, the words, the punctuation and these inline tags make the voice go up or down, faster or slower.
SOUNDS_LIKE = {
    "calm": "middle pitch, even pace, a gentle fall at the end",
    "confident": "middle pitch, steady and firm, the line ends low and sure",
    "excited": "high and bright, fast, the key word pushed up",
    "happy": "bright and a little higher, lively, smiling",
    "playful": "light and bouncy, up and down, a smile in it",
    "surprised": "jumps high on the surprising word, then a beat",
    "curious": "rises at the end, like a real question",
    "sarcastic": "flat, the key word drawn out, then a drop",
    "warm": "a little lower, unhurried, soft and close",
    "urgent": "a little higher, quick and firm, short clipped sentences",
    "worried": "higher and tense, a little rushed, hesitant",
    "sad": "low and slow, soft, falling at the end",
    "frustrated": "tight and clipped, pushed harder on the key words",
    "angry": "lower and louder, hard stresses, short",
    "whisper": "low and quiet, close, slower",
}

SOUNDS = ("[laughs]", "[chuckles]", "[sighs]", "[exhales]", "[gasps]", "[clears throat]")
PAUSES = ("[short pause]", "[pause]", "[long pause]")
DELIVERY = ("[softly]", "[dramatically]", "[slowly]", "[cautiously]", "[mischievously]", "[nervous]")
INLINE = SOUNDS + PAUSES + DELIVERY + tuple(f.tag for f in FEELINGS.values() if f.tag)

# a hook (S01) is the reel's highest point: these feelings start it too low
LOW_FOR_A_HOOK = ("calm", "warm", "sad", "whisper")
# What makes the voice stop or slow down: in the hook, where the thumb decides within about 3 seconds, none of it
STOPS_IN_A_HOOK = PAUSES + ("[sighs]", "[exhales]", "[clears throat]", "[slowly]")
STOP_MARKS = ("…", "...", ":", ";")


def sounds_like(name):
    """How a feeling sounds, in a few words (pitch, pace, the end of the line)."""
    return SOUNDS_LIKE.get(str(name or "").strip().lower(), SOUNDS_LIKE["calm"])

# the sign-off and the share line are the account's ask: they never sound angry, upset or afraid
ASK_CHAPTERS = ("share", "signoff")
NOT_FOR_THE_ASK = ("worried", "sad", "frustrated", "angry")

# models that act out [tags]; every other model reads them out loud
TAG_MODELS = ("eleven_v4", "eleven_v3")
NO_SPEED = TAG_MODELS               # and have no speed, style or speaker-boost setting: only stability and similarity
NOT_ON_TAG_MODELS = ("speed", "style", "use_speaker_boost")

TAG = re.compile(r"\[([^\[\]\n]{1,40})\]")

MODEL_NAMES = {"eleven_v4": "Eleven v4", "eleven_v3": "Eleven v3", "eleven_multilingual_v2": "Eleven Multilingual v2",
               "eleven_turbo_v2_5": "Eleven Turbo v2.5", "eleven_flash_v2_5": "Eleven Flash v2.5"}


def model_name(model_id):
    """A voice model as elevenlabs.io names it in its model menu."""
    return MODEL_NAMES.get(str(model_id or ""), str(model_id or "Eleven Multilingual v2"))

# How a tag sounds when a voice reads it out loud, as the consonants a Hindi transcript writes for it
# (tools/verify_voice.py hears एक्साइटेड: क स ट ड). Read with skeleton() below.
READ_ALOUD = {
    "[excited]": ("कसटड",), "[surprised]": ("सरपरजड", "सपरजड"), "[sarcastic]": ("सरकसटक", "सकसटक"),
    "[confident]": ("कनफडनट", "कनफडट"), "[frustrated]": ("फरसटरटड",), "[worried]": ("वरड",),
    "[urgently]": ("रजनटल", "रजटल"), "[warmly]": ("वरमल",), "[curious]": ("कयरयस", "करयस"),
    "[playful]": ("पलफल",), "[whispers]": ("वहसपरस", "वसपरस"), "[angry]": ("नगर",), "[happy]": ("हपप", "हप"),
    "[sad]": ("सड",), "[laughs]": ("लफस",), "[chuckles]": ("चकलस",), "[sighs]": ("सस", "सज"),
    "[gasps]": ("गसपस",), "[dramatically]": ("डरमटकल",), "[softly]": ("सफटल",), "[pause]": ("पज",),
    "[short pause]": ("शरटपज",), "[exhales]": ("कसहलस",), "[clears throat]": ("कलयरसथरट",),
    "[long pause]": ("लनगपज", "लगपज"), "[slowly]": ("सलल",), "[cautiously]": ("कशयसल",),
    "[mischievously]": ("मसचवयसल", "मसचवसल"), "[nervous]": ("नरवस",),
}


def skeleton(w):
    """A Devanagari word's consonants, the way it sounds: nukta dropped, anusvara as न (एंग्री → न ग र)."""
    w = w.replace("़", "").replace("ं", "न")
    return "".join(ch for ch in w if "क" <= ch <= "ह")


def feeling(line):
    """The line's feeling: its "emotion", or calm when it has none."""
    return str((line or {}).get("emotion") or "calm").strip().lower()


def spec(line_or_name):
    """The Feeling for a line (or a feeling's name). An unknown name counts as calm."""
    name = line_or_name if isinstance(line_or_name, str) else feeling(line_or_name)
    return FEELINGS.get(str(name).strip().lower(), CALM)


def tags_in(text):
    """Every [tag] in a text, lower case, as written: ["[sighs]", "[excited]"]."""
    return ["[{}]".format(m.group(1).strip().lower()) for m in TAG.finditer(str(text or ""))]


def clean(text):
    """The words alone, without any [tag]. A text with no tag comes back exactly as it was (only stripped)."""
    text = str(text or "")
    if "[" not in text:
        return text.strip()
    out = TAG.sub(" ", text)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r" ([,।.!?…])", r"\1", out)
    return out.strip()


def takes_tags(model_id):
    """True for the voice models that act out [tags] (and never say them)."""
    return str(model_id or "").startswith(TAG_MODELS)


def say_text(line, model_id):
    """Exactly what the voice tool is given for a line. A model that acts out tags gets the feeling's tag in front of
    the words, and the line's own tags where they are; any other model gets the words alone, since it would read a
    tag out loud. A calm line with no tags is its tts as it is."""
    tts = str((line or {}).get("tts") or "").strip()
    if not takes_tags(model_id):
        return clean(tts)
    tag = spec(line).tag
    if tag and not tts.lower().startswith(tag):
        return "{} {}".format(tag, tts)
    return tts


def uses_feelings(ep):
    """True when an episode's script gives its lines a feeling (or puts a tag in one): it's then voiced with the
    feeling model (brand.json → voice → emotion)."""
    return any(isinstance(l, dict) and ("emotion" in l or TAG.search(str(l.get("tts") or "")))
               for l in (ep or {}).get("script", []))


def required(ep):
    """True for an episode started on or after FROM: every line needs a feeling."""
    try:
        return datetime.date.fromisoformat(str((ep or {}).get("created") or "")) >= datetime.date.fromisoformat(FROM)
    except ValueError:
        return True


def voice(v, ep):
    """The voice settings an episode is made with: when its lines have feelings, the feeling model and its settings
    (voice → emotion) on top of the series voice, without the settings that model doesn't have."""
    v = dict(v or {})
    extra = v.pop("emotion", None)
    if not extra or not uses_feelings(ep):
        return v
    v.update({k: val for k, val in extra.items() if k != "about"})
    if v.get("model_id", "").startswith(NO_SPEED):
        for k in NOT_ON_TAG_MODELS:
            v.pop(k, None)
    return v


def read_aloud(line, heard):
    """The tags a voice seems to have said as words, from what it was heard saying (the Hindi transcript): the
    feeling's tag among the first words heard, a tag inside the line anywhere, in Devanagari or in English letters.
    A sound the line says itself never counts."""
    heard = str(heard or "")
    words = [skeleton(w) for w in re.findall(r"[ऀ-ॿ]+", heard)]
    pairs = ["".join(words[k:k + 2]) for k in range(len(words))]
    latin = [w.lower() for w in re.findall(r"[A-Za-z]+", heard)]
    line = line or {}
    own = {skeleton(w) for w in re.findall(r"[ऀ-ॿ]+", clean(line.get("tts")))}
    own_latin = {w.lower() for w in re.findall(r"[A-Za-z]+", str(line.get("vo") or ""))}
    found = []
    lead = spec(line).tag
    for tag in ([lead] if lead else []) + tags_in(line.get("tts")):
        if tag in found:
            continue
        lead_only = tag == lead and tag not in tags_in(line.get("tts"))
        names = tag[1:-1].split()
        if all(n in latin[:4] if lead_only else n in latin for n in names) and not set(names) & own_latin:
            found.append(tag)
            continue
        for sound in READ_ALOUD.get(tag, ()):
            if sound in own:
                continue
            pool = pairs if len(names) > 1 else words          # a two-word tag is heard as two words
            if sound in (pool[:3] if lead_only else pool):
                found.append(tag)
                break
    return found


def problems(ep):
    """[(level, check id, shot, message)] for the feelings and tags in an episode's script: level is "fail" or "warn".
    E3.23 every line's feeling, E3.24 the tags, E3.25 a script that sounds flat, E3.26 the ask never sounds upset."""
    out = []
    script = [l for l in (ep or {}).get("script", []) if isinstance(l, dict)]
    need = required(ep)
    names = ", ".join(FEELINGS)
    for line in script:
        sid = line.get("shot") or "script"
        name = line.get("emotion")
        if name is None:
            if need:
                out.append(("fail", "E3.23", sid, "the line has no \"emotion\": give it one of {}".format(names)))
        elif str(name).strip().lower() not in FEELINGS:
            out.append(("fail", "E3.23", sid, "\"emotion\": \"{}\" isn't one of {}".format(name, names)))
        if TAG.search(str(line.get("vo") or "")):
            out.append(("fail", "E3.24", sid, "the caption (vo) has a [tag]: tags only go in tts, the voice's text"))
        tags = tags_in(line.get("tts"))
        unknown = [t for t in tags if t not in INLINE]
        if unknown:
            out.append(("fail", "E3.24", sid, "tts has {}, which isn't a tag the voice knows: use one of {}".format(
                ", ".join(unknown), ", ".join(INLINE))))
        if len(tags) > MAX_INLINE:
            out.append(("fail", "E3.24", sid, "tts has {} tags: at most {} inside a line (its feeling already sets the "
                                              "tone)".format(len(tags), MAX_INLINE)))
        if tags and str(line.get("tts") or "").strip().startswith("["):
            out.append(("warn", "E3.24", sid, "tts starts with {}: put the line's feeling in \"emotion\" (the voice gets "
                                              "its tag in front), and keep tags inside the line for where the feeling "
                                              "changes".format(tags[0])))
        if line.get("chapter") in ASK_CHAPTERS and feeling(line) in NOT_FOR_THE_ASK:
            out.append(("fail", "E3.26", sid, "the {} line is our ask, so it never sounds {}: make it warm, playful, "
                                              "happy, confident or excited".format(line.get("chapter"), feeling(line))))
    # where the voice goes up and down (brand/prompts/voice-curve.txt)
    if need and script and script[0].get("emotion") is not None and feeling(script[0]) in LOW_FOR_A_HOOK:
        out.append(("warn", "E3.29", script[0].get("shot") or "S01",
                    "the hook is {}: it's the reel's highest point, where the thumb decides, so it starts higher. Most "
                    "hooks land better urgent, surprised, curious, excited or worried".format(feeling(script[0]))))
    if script:                                      # any reel: what a hook's voice text says, the voice does
        tts = str(script[0].get("tts") or "")
        stops = [x for x in tags_in(tts) if x in STOPS_IN_A_HOOK] + [m for m in STOP_MARKS if m in tts]
        if stops:
            out.append(("fail", "E3.31", script[0].get("shot") or "S01",
                        "the hook's voice text (tts) has {}: the voice stops or slows there, and the viewer decides in "
                        "about 3 seconds whether to stay. Take it out: a comma is enough where a speaker breathes, and "
                        "the hook's feeling sets the tone".format(" and ".join(dict.fromkeys(stops)))))
    for line in script if need else []:
        asks = [x for x in re.split(r"(?<=[.?!])\s+", str(line.get("vo") or "")) if x.strip().endswith("?")]
        if asks and "?" not in str(line.get("tts") or ""):
            out.append(("warn", "E3.30", line.get("shot") or "script",
                        "the caption asks a question (\"{}\") but the voice text (tts) has no \"?\", so the voice won't "
                        "rise like a question: end that sentence with ? in tts too".format(asks[0].strip())))
    felt = [feeling(l) for l in script if l.get("emotion") is not None]
    if len(felt) >= 8:
        kinds = set(felt)
        top = max(felt.count(f) for f in kinds)
        if len(kinds) < 3:
            out.append(("warn", "E3.25", "script", "only {} feeling(s) in the whole script ({}): a real conversation "
                                                   "moves, so give the lines at least 3".format(
                                                       len(kinds), ", ".join(sorted(kinds)))))
        elif top > 0.6 * len(felt):
            same = max(sorted(kinds), key=felt.count)
            out.append(("warn", "E3.25", "script", "{} of {} lines are {}: the voice will sound flat. Let the hook, the "
                                                   "problem and the proof feel different".format(top, len(felt), same)))
    return out
