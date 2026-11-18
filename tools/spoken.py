"""How numbers are said: read numbers out of Hindi, Hinglish or digit text.

Used by tools/validate.py (the voice text must say the caption's numbers) and tools/verify_voice.py
(what Whisper heard must contain them). Standard library only.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dc  # noqa: E402

# ---------------------------------------------------------------- spoken numbers

_HI = ("एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस बीस "
       "इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस "
       "छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस छियालीस सैंतालीस "
       "अड़तालीस उनचास पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ साठ इकसठ बासठ "
       "तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर "
       "छिहत्तर सतहत्तर अठहत्तर उन्यासी अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी "
       "नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे").split()
_HI_EXTRA = {"छः": 6, "छे": 6, "पंदरा": 15, "पन्द्रह": 15, "अट्ठारह": 18, "अठ्ठारह": 18, "पचीस": 25, "पच्यिस": 25,
             "पचिस": 25, "पच्चिस": 25, "उन्नीस": 19}
_ROMAN = {"ek": 1, "do": 2, "teen": 3, "tin": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "pach": 5,
          "chhah": 6, "chhe": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "gyaarah": 11,
          "barah": 12, "baarah": 12, "terah": 13, "chaudah": 14, "pandrah": 15, "pandra": 15, "solah": 16,
          "satrah": 17, "atharah": 18, "athaarah": 18, "attharah": 18, "unnees": 19, "unnis": 19, "bees": 20,
          "bis": 20, "pachchees": 25, "pachees": 25, "pachis": 25, "tees": 30, "tis": 30, "chalees": 40,
          "pachaas": 50, "pachas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90}
_MULT = {"सौ": 100, "हज़ार": 1000, "हजार": 1000, "लाख": 100000, "लाक": 100000, "करोड़": 10 ** 7, "करोड": 10 ** 7,
         "sau": 100, "hazaar": 1000, "hazar": 1000, "hajar": 1000, "lakh": 100000, "lac": 100000, "crore": 10 ** 7}


def _plain(w):
    """Lower case, without nukta, chandrabindu or anusvara, so हजार meets हज़ार and पाच meets पाँच.
    Vowel signs stay: पचास (50) and पचीस (25), or ने and नौ (9), must never become the same word."""
    w = w.replace("़", "").replace("ँ", "").replace("ं", "")
    return re.sub(r"[\s.,!?।|:;\"'()\[\]%₹–—-]", "", w.lower())


UNITS = {_plain(w): i + 1 for i, w in enumerate(_HI)}
UNITS.update({_plain(k): v for k, v in _HI_EXTRA.items()})
UNITS.update(_ROMAN)
# Numbers said in English, in Devanagari (how the voice text writes them: एट पॉइंट टू फ़ाइव परसेंट is 8.25%)
# and in English letters (how Whisper may write them). Never "फ़ॉर" (for) or "to": they are ordinary words.
_EN = {0: ("ज़ीरो", "जीरो", "zero"), 1: ("वन", "one"), 2: ("टू", "two"), 3: ("थ्री", "three"), 4: ("फ़ोर", "four"),
       5: ("फ़ाइव", "फ़ाईव", "five"), 6: ("सिक्स", "six"), 7: ("सेवन", "seven"), 8: ("एट", "एइट", "eight"),
       9: ("नाइन", "nine"), 10: ("टेन", "ten"), 11: ("इलेवन", "eleven"), 12: ("ट्वेल्व", "ट्वेल्भ", "twelve"),
       13: ("थर्टीन", "thirteen"), 14: ("फ़ोर्टीन", "fourteen"), 15: ("फ़िफ़्टीन", "fifteen"), 16: ("सिक्सटीन", "sixteen"),
       17: ("सेवनटीन", "सेवेनटीन", "seventeen"), 18: ("एटीन", "ऐटीन", "eighteen"), 19: ("नाइनटीन", "nineteen"),
       20: ("ट्वेंटी", "ट्वेन्टी", "twenty"), 30: ("थर्टी", "thirty"), 40: ("फ़ोर्टी", "forty"), 50: ("फ़िफ़्टी", "fifty"),
       60: ("सिक्सटी", "sixty"), 70: ("सेवेंटी", "सेवन्टी", "seventy"), 80: ("एटी", "ऐटी", "eighty"),
       90: ("नाइंटी", "नाइन्टी", "ninety")}
EN_UNITS = {_plain(w): v for v, words in _EN.items() for w in words}
EN_TENS = {w for w, v in EN_UNITS.items() if v in (20, 30, 40, 50, 60, 70, 80, 90)}
EN_ONES = {w for w, v in EN_UNITS.items() if 1 <= v <= 9}
UNITS.update(EN_UNITS)
_MULT.update({"हंड्रेड": 100, "हन्ड्रेड": 100, "hundred": 100, "थाउज़ेंड": 1000, "थाउजंड": 1000, "थाउज़ंड": 1000,
              "thousand": 1000, "मिलियन": 10 ** 6, "million": 10 ** 6})
MULTS = {_plain(k): v for k, v in _MULT.items()}
# डेढ़ (1½) and ढाई (2½) work like numbers before a multiplier: ढाई हज़ार = 2,500, डेढ़ लाख = 1,50,000.
# Whisper writes डेढ़ as डेड.
UNITS.update({_plain(k): v for k, v in {"डेढ़": 1.5, "डेड": 1.5, "ढाई": 2.5, "dedh": 1.5, "dhai": 2.5, "dhaai": 2.5}.items()})
# A number in digits before a multiplier word is one number: "2 लाक" is 2,00,000 and "Rs. 1.5 lakh" 1,50,000
_DIGIT_MULT = re.compile(r"(\d+(?:\.\d+)?)\s*(" + "|".join(sorted(map(re.escape, _MULT), key=len, reverse=True)) +
                         r")(?![\u0900-\u0963A-Za-z])", re.IGNORECASE)
# How Whisper sometimes spells sau: only counted right after a number word ("pachis saw" = 2,500)
SAU_AFTER_NUMBER = {_plain(w) for w in ("सो", "सौप", "सोउ", "so", "saw", "sow", "sau")}
# Words that sound like a number but are also ordinary words: if the line's number isn't heard and one of these
# is, a person listens instead of the line failing (सात 7 vs साथ "with" sound the same to Whisper)
SOUND_ALIKE = {7: {_plain(w) for w in ("साथ", "साठ", "saath", "sath", "saat")}}


# A decimal is said as a number, the word for point, then one word per digit: आठ पॉइंट दो पाँच is 8.25
POINT = {_plain(w) for w in ("पॉइंट", "प्वाइंट", "पोइंट", "पॉइन्ट", "प्वॉइंट", "दशमलव", "point")}
DIGITS = {_plain(w): d for d, words in {0: ("शून्य", "ज़ीरो", "जीरो", "zero", "shunya")}.items() for w in words}
DIGITS.update({w: v for w, v in UNITS.items() if isinstance(v, int) and 1 <= v <= 9})
# A quick "two" after the point comes back from Whisper as टॉ, टो or टु: "एट पॉइंट टॉ 5%" is 8.25%.
# Only after the point: anywhere else they aren't numbers.
DIGITS.update({_plain(w): 2 for w in ("टॉ", "टो", "टु")})
# सवा, साढ़े and पौने before a number: सवा आठ is 8.25, साढ़े सात हज़ार 7,500, पौने दो लाख 1,75,000, सवा लाख 1,25,000
FRACTIONS = {_plain(k): v for k, v in {"सवा": 0.25, "साढ़े": 0.5, "साढे": 0.5, "साड़े": 0.5, "पौने": -0.25,
                                        "sawa": 0.25, "sava": 0.25, "sadhe": 0.5, "saadhe": 0.5, "paune": -0.25}.items()}
_SAID_POINT = re.compile(r"(\d+)\s*(?:पॉइंट|प्वाइंट|पोइंट|दशमलव|point)\s*(\d+)", re.IGNORECASE)


def _num(x):
    x = round(x, 6)
    return int(x) if float(x).is_integer() else x


def spoken_numbers(text):
    """Numbers in a transcript, written as digits or as Hindi or Hinglish words, decimals included."""
    text = re.sub(r"(\d)\s+,(\d)", r"\1,\2", text)
    text = _SAID_POINT.sub(r"\1.\2", text)
    text = _DIGIT_MULT.sub(lambda m: str(int(round(float(m.group(1)) * MULTS[_plain(m.group(2))]))), text)
    out = [_num(float(m.replace(",", ""))) for m in re.findall(r"\d[\d,]*(?:\.\d+)?", text) if m.replace(",", "")]
    total, cur, active, last, frac, decimals = 0, 0, False, None, 0.0, None

    def close():
        value = total + cur
        if decimals:
            value += float("0." + decimals)
        out.append(_num(value))

    t, src, end = None, text.replace(". ", " "), 0
    for m in re.finditer(r"[^\s,!?।:;\-–—]+", src):
        tok, gap, end = m.group(), src[end:m.start()], m.end()
        prev, t = t, _plain(tok)
        if decimals is not None:                 # after "point": one word per digit
            if t in DIGITS:
                decimals += str(DIGITS[t])
                continue
            # Whisper may write the last digits as digits: "एट पॉइंट टू 5%" is 8.25%. Not across a comma or a stop.
            if re.fullmatch(r"[0-9]+%?", tok) and not re.search(r"[,!?।:;]", gap):
                decimals += tok.rstrip("%")
                if _num(float(tok.rstrip("%"))) in out:     # part of this number, not a number of its own
                    out.remove(_num(float(tok.rstrip("%"))))
                continue
            close()
            total, cur, active, last, decimals = 0, 0, False, None, None
        if t in POINT and active and last == "unit":
            decimals = ""
            continue
        if t in FRACTIONS and not active:
            frac = FRACTIONS[t]
            continue
        if t in UNITS:
            if active and last == "unit" and not (prev in EN_TENS and t in EN_ONES):
                close()
                total, cur = 0, 0
            cur += UNITS[t] + frac
            frac = 0.0
            active, last = True, "unit"
        elif t in MULTS or (t in SAU_AFTER_NUMBER and active and last == "unit"):
            m = MULTS.get(t, 100)
            base = (cur or 1) + (frac if not cur else 0)
            frac = 0.0
            if m == 100:
                cur = base * 100
            else:
                total += base * m
                cur = 0
            active, last = True, "mult"
        else:
            if active:
                close()
            total, cur, active, last, frac, decimals = 0, 0, False, None, 0.0, None
    if active:
        close()
    return out


def expected_numbers(vo):
    """The numbers a line's caption shows, decimals included (8.25% is 8.25)."""
    return sorted({_num(float(n["value"])) for n in dc.extract_numbers(vo)})


def word_numbers(vo):
    """Numbers the line says in words ("Sau mein ek…"): allowed to be heard, not required."""
    return set(spoken_numbers(re.sub(r"\d[\d,]*(?:\.\d+)?", " ", vo)))
