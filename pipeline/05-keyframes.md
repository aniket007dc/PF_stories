# Step 05 · Keyframes

> **With a `reel.json`, the build does this step:** `tools/build_reel.py` draws every shot and assembles the reel (see MUSE.md). `--stills` saves one still per shot in `media/keyframes/` for shot-by-shot approval.

| | |
|---|---|
| Goal | One approved still image per shot |
| Who | Muse generates · OCR re-checks · a person approves each shot |
| Reads | `episodes/EP/prompts.md` · `brand/assets/style-frames/` as style references · A01 background |
| Writes | `episodes/EP/media/keyframes/S01.png` … |
| Checks | SELF · AUTO · HUMAN |
| Gate | Every shot approved; the step then passes by itself |

## Route

`prompts.md` says which route applies, based on `brand/capabilities.json`:

- **Code** (when `code_render` is `yes`; it overrides the others): Muse builds the shot frame by frame in Python, with the fonts in `brand/fonts/` on the paper in `brand/assets/plates/`, following `brand/prompts/code-build.txt`. The same script makes the keyframe (its last frame) and the clip, so steps 05 and 06 are done together. The image model makes only pictures without writing, such as halftone photos.
- **Muse with text:** Muse renders the cards, numbers included.
- **Clean plate:** Muse renders the layout with blank cards (add the Clean plate block), and the text is typed in Canva. Export the finished frame from Canva as the keyframe. This is the default until the capability test says otherwise.

## Do, for each shot

1. Attach A01 and paste the shot's keyframe prompt from `prompts.md`. You can also attach a style frame from `brand/assets/style-frames/` as a look reference.
2. **SELF:** paste the shot's self-check prompt. If Muse says FAIL, use a fix-it prompt.
3. Save the image as `episodes/EP/media/keyframes/S01.png` (vertical, ideally 1080×1920).
4. **AUTO + HUMAN:** a person looks at it and approves. Approving runs the OCR check first and refuses a failing image. Commit keyframes only after they're approved; GitHub re-checks every committed keyframe.

```bash
python3 tools/approve.py shot episodes/ep02-uan-activate S01 keyframe --file episodes/ep02-uan-activate/media/keyframes/S01.png --mode muse --by "Your Name"
```

5. If it fails, record the try, fix and try again:

```bash
python3 tools/approve.py try episodes/ep02-uan-activate S01 keyframe --mode muse --note "₹50,000 came out as ₹56,000"
```

After two failed tries, switch that shot to the clean-plate route and approve with `--mode clean-plate`.

Code route: approve the last frame the build script saved, with `--mode code`. Check that the script is committed next to it (`episodes/EP/build/S01.py`):

```bash
python3 tools/approve.py shot episodes/ep02-uan-activate S01 keyframe --file episodes/ep02-uan-activate/media/keyframes/S01.png --mode code --by "Your Name"
```

## What the OCR check does

- Reads the text inside the card band only (17–68% of the height), so captions or headers can't stand in for a card.
- Every number must match digit for digit. A near-miss (₹58,000 for ₹50,000) fails.
- Words may differ by a letter or two, because OCR isn't perfect.
- Arrows and single symbols are listed for a person to check by eye.
- Text above or below the card band is flagged as a warning: the header and caption zones must stay plain paper in a keyframe.

## What the person checks

The paper looks like A01. The style matches the style frames. Nothing in the top or bottom zones. No logos, watermarks or real faces. The card the numbers are on is the right colour.

## If it fails

Two tries per shot, then the clean-plate route. If a shot keeps failing on the clean-plate route too, the prompt is the problem: fix it in `episode.json` (step 04), regenerate, and approve 04 again.
