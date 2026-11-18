# Step 03 · Script

| | |
|---|---|
| Goal | A 150–175 word Hinglish voiceover, one line per shot, two other hooks to pick from, plus the post copy |
| Who | Muse writes · a person reads the script page, asks for changes, and approves it before anything else is made |
| Reads | `episodes/EP/prompts-writing.md` (generated from the brief and data) |
| Writes | `episode.json` → `script`, `hook_options` and `post` · `03-script` set to `drafted` · GitHub writes the script page, `script.md` |
| Checks | AUTO · SELF · HUMAN |
| Gate | From ep05: the person's OK on the script page, for its version: `script-approved.json` (Muse uploads it after the OK, or `python3 tools/approve.py script EP --version CODE --by NAME`). Nothing else is made, and GitHub builds no reel, until then. The step itself: `python3 tools/approve.py step EP 03-script --by NAME` |

## Do

1. Regenerate the writing prompts so they contain this episode's data:

```bash
python3 tools/build_prompts.py episodes/ep02-uan-activate
```

2. Send Muse the "Step 3 · Script prompt" from `prompts-writing.md`.
3. Paste the `script` lines and the `post` object from its reply into `episode.json`. Keep each line's `uses` and `delivery` (how the voice says it: a mood, then one cue, such as "curious · slow down on ek saal"; the voice table in `prompts.md` shows it, so the reel doesn't sound flat).
4. Set `03-script` to `drafted` and run `python3 tools/validate.py episodes/ep02-uan-activate`.
5. Write the script page and send it to the person. GitHub writes it on every upload; by hand:

```bash
python3 tools/script_review.py episodes/ep05-uan-activate --write
```

   The page (`script.md`) has the hook and the other hooks, every line and how it's said, every number and rule with its source, the cover and the caption, and a version code. The person replies with changes (make exactly those, then send the new page) or "script OK". Record the OK for the version they read: Muse uploads `script-approved.json` (MUSE.md → N3), or a person runs `python3 tools/approve.py script episodes/ep05-uan-activate --version CODE --by NAME`. The approval covers every line's words and part, the cover and the trial hook; respelling a word in `tts`, or changing `delivery`, doesn't need a new one.

## Checks

| ID | Check | Who |
|---|---|---|
| E3.1 | Every line has shot, chapter, vo, tts, highlights and uses | AUTO |
| E3.2 | All eight chapters, in order | AUTO |
| E3.3 | 150–175 words; estimated length 60–95 s at 2.6 words a second (a brisk voice), about 70 s for most scripts | AUTO |
| E3.4 | Sentences of 10 words or fewer (warning) | AUTO |
| E3.5 | Every number in a line belongs to that line's `uses`; Indian commas | AUTO |
| E3.6 | Highlights are copied exactly from the line | AUTO |
| E3.7, E3.8 | Share line says "… bhejo"; sign-off is exactly "PF samjho, claim pao. EPFO ki har jankari chahiye? Follow karo PF Guru Ji." (from `brand/brand.json`) | AUTO |
| E3.9 | The first appearance of every example number says "maan lo" (or EXAMPLE on its card) | AUTO |
| E3.10 | The TTS line spells numbers as words (it's written in Devanagari, the same words as the caption line) | AUTO |
| E3.13 | The TTS line says exactly the caption's numbers, in English (एट पॉइंट टू फ़ाइव परसेंट for 8.25%; form names too, like फ़ॉर्म नाइनटीन) | AUTO |
| E3.14 | Every form the line names is in `brand/epfo-forms.json` | AUTO |
| E3.15 | The other hooks (`hook_options`) use only numbers from data | AUTO |
| — | The person read the script page (`script.md`) and approved this version; until then nothing else is made (from ep05) | HUMAN |
| — | Muse listed every number with its data id (end of its reply) | SELF |
| — | Read it aloud briskly with a timer: about 60–75 s including a 3 s tail? Sounds like a friend, not an ad or a notice? | HUMAN |
| — | Does every reason and step match its rule's source? Is no one asked for personal details, sent to an agent, or promised a result? | HUMAN |

## If it fails

Fix the line, not the check. If a line needs a number or a rule that isn't in `data`, go back to step 02 and add it with a source; approving step 02 again is expected.
