# Step 07 · Voice

| | |
|---|---|
| Goal | One continuous voiceover track for the whole reel |
| Who | A person records, or generates it with an AI voice · a person approves |
| Reads | `episode.json` → `script` (`tts`, in Devanagari, is what the voice reads; `vo` is the caption) · `brand/prompts/voice.txt` |
| Writes | `episodes/EP/media/audio/voice.wav` (committed, so GitHub can check it) |
| Checks | AUTO · HUMAN |
| Gate | `python3 tools/approve.py file EP 07-voice --file PATH --by NAME` |

## Do

With the build (MUSE.md), make one file per line instead: `media/audio/lines/S01.mp3` … from the `tts` text, saved exactly as the voice tool made it (never trimmed). The build times every shot to its line, and `python3 tools/verify_voice.py EP` checks that every number and the brand name are heard (GitHub runs it on every upload).

1. Record in one sitting, so the voice sounds the same throughout. Phone 15–20 cm from the mouth, a small soft room, about 120 words a minute, a short pause after every number.
2. With an AI voice, give it the description in `brand/prompts/voice.txt` and the `tts` lines exactly. They're in Devanagari because a Hindi voice reading Hinglish in English letters guesses: in Muse's runs "pachchees sau" came out as "pachaas sau" (₹5,000). Form names are written the way they're said, in English: फ़ॉर्म नाइनटीन. Use the series voice for every line of every reel. Don't use Muse Video's per-clip audio.
3. Clean it (voice enhancement in Edits), export WAV or M4A at 48 kHz.

## Checks

| Check | Who |
|---|---|
| Length fits the shot plan (warns if it's more than 5 s off) | AUTO |
| Loudness reported | AUTO |
| Every number is said correctly: the check prints the list to listen for | HUMAN |

## If it's longer or shorter than the plan

Re-time the shots in step 04 to the real voice. Image and motion approvals stay valid.
