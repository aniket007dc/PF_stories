# Step 08 · Assembly

> **With a `reel.json`, the build does this step:** `tools/build_reel.py` draws every shot and assembles the reel (see MUSE.md). `--stills` saves one still per shot in `media/keyframes/` for shot-by-shot approval.

| | |
|---|---|
| Goal | The finished reel: animated shots, header, captions, voice, music and sound effects |
| Who | An editor (Canva + Instagram Edits) · a person approves |
| Reads | approved keyframes and clips · `episodes/EP/assets/hud-overlay.png` · `brand/assets/overlays/caption-strip.png` · `brand/assets/guides/safe-zones.png` · a music bed (optional) |
| Writes | `episodes/EP/media/final/EP.mp4` (keep large video out of git) |
| Checks | AUTO · HUMAN |
| Gate | `python3 tools/approve.py file EP 08-assembly --file PATH --by NAME` |

## Do

1. In Canva, one page per shot at the shot's length. Put the header overlay on every page and the safe-zone guide on a hidden layer.
2. Add the two torn-paper wipes at the chapter breaks (A08 and A09, or Canva's Color wipe).
3. In Edits, add the voice, music 15–18 dB under it, sound effects on every landing and stamp, and captions in Roman Hinglish with the numbers highlighted.
4. Export 1080×1920, 30 fps, with the last 3 s music only.

## Checks

| Check | Who |
|---|---|
| 1080×1920, 30 fps, 80–100 s, has sound, loudness −16 to −12 LUFS | AUTO |
| Every shot's card text is on screen just before the shot ends, digit for digit (read from the card band only, so captions can't stand in) | AUTO |
| Watch it muted (do captions carry it?) and with sound | HUMAN |

## If it fails

The report names the shot and the number. Fix that page and export again. Approval is locked to the exact file, so any re-export needs a new approval.
