# Step 04 · Shot list and prompts

| | |
|---|---|
| Goal | One shot per script line, with exact card text, timing, data references and the keyframe and motion prompts |
| Who | Muse writes · the checks decide |
| Reads | `episodes/EP/prompts-writing.md` → "Step 4 · Shot prompt" |
| Writes | `episode.json` → `shots` and `breaks` · generated `prompts.md` · `04-shots` set to `drafted` |
| Checks | AUTO · SELF |
| Also | Write `reel.json` (what each shot shows) with the reel prompt: `prompts-writing.md` → Step 4, from `brand/prompts/reel-writer.txt`. Check it: `python3 tools/build_reel.py episodes/EP --check` |
| Gate | `python3 tools/approve.py step EP 04-shots` |

## Do

1. Send Muse the "Step 4 · Shot prompt" from `prompts-writing.md`.
2. Paste `shots` and `breaks` from its reply into `episode.json`.
3. Generate the production prompts, then check:

```bash
python3 tools/build_prompts.py episodes/ep02-uan-activate
```

```bash
python3 tools/validate.py episodes/ep02-uan-activate
```

4. When the checks pass, mark the step done (no person needed):

```bash
python3 tools/approve.py step episodes/ep02-uan-activate 04-shots
```

## Checks

| ID | Check | Who |
|---|---|---|
| E4.1, E4.2 | Shots start at 0, follow each other with no gaps, and add up to 60–95 s (aim for about 70) | AUTO |
| E4.3 | Every number on a card belongs to the shot's `uses`; Indian commas | AUTO |
| E4.4, E4.5 | Every card text appears inside quotes in the keyframe prompt (motion text in the motion prompt) | AUTO |
| E4.6, E4.7 | Data ids and asset ids exist | AUTO |
| E4.8 | At most one yellow element per shot (warning) | AUTO |
| E4.9 | Two chapter breaks, at real shot ends | AUTO |
| E4.10 | `prompts.md` and `prompts-writing.md` are up to date | AUTO |
| — | Muse confirms each card's text is quoted in its prompt | SELF |

## Re-timing later

If the real voice in step 07 runs longer or shorter, change `start` and `end` here, run `build_prompts.py`, and approve 04 again. Keyframe and motion approvals stay valid because they are locked to the card text and prompts, not the timing.
