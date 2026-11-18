# Step 06 · Motion

> **With a `reel.json`, the build does this step:** `tools/build_reel.py` draws every shot and assembles the reel (see MUSE.md). `--stills` saves one still per shot in `media/keyframes/` for shot-by-shot approval.

| | |
|---|---|
| Goal | Each shot animated: cards drop, slide, stamp and stack, with a still camera |
| Who | Muse or Canva · OCR re-checks clips · a person approves each shot |
| Reads | `prompts.md` (motion prompts, Canva lines) · the approved keyframes |
| Writes | `episodes/EP/media/clips/S01.mp4` …, or the animated pages in Canva |
| Checks | AUTO · HUMAN |
| Gate | Every shot approved; the step then passes by itself |

## Route

- **Canva** (default): build the shot's page in the Canva template and animate it with the shot's Canva line (Rise, Pop, Stomp, Wipe, Typewriter). Approve with `--canva`. The text is re-checked in the finished reel at step 09.
- **Muse:** attach the approved keyframe, paste the motion prompt with the Motion Lock, save the clip as `media/clips/S01.mp4`.
- **Code** (when `code_render` is `yes`): the shot's build script from step 05 already made `media/clips/S01.mp4`. If the keyframe needed a fix, run the script again so the clip and the keyframe come from the same build.

## Do, for each shot

Muse route. Approving runs the clip check first:

```bash
python3 tools/approve.py shot episodes/ep02-uan-activate S01 motion --file episodes/ep02-uan-activate/media/clips/S01.mp4 --mode muse --by "Your Name"
```

Code route:

```bash
python3 tools/approve.py shot episodes/ep02-uan-activate S01 motion --file episodes/ep02-uan-activate/media/clips/S01.mp4 --mode code --by "Your Name"
```

Canva route:

```bash
python3 tools/approve.py shot episodes/ep02-uan-activate S01 motion --canva --by "Your Name"
```

## What the clip check does

- The last frame must show every card text, digit for digit.
- It samples a frame every half second. If any number turns into a near-miss of itself (₹50,000 showing as ₹58,000 at 2.0 s), the clip fails.
- It warns if a number disappears or blurs after it lands, or if the clip is shorter than the shot.

## What the person checks

The camera never moves. Each element arrives on its spoken word. Stamps hit hard and stop. Nothing warps or melts. No sound in the clip (sound comes in step 08).

## If it fails

Two tries per shot with Muse, then animate that shot in Canva. On the code route, a failing clip means the script is wrong: fix the script, not the check, and build again.
