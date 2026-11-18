# Step 00 · Capability test (once)

| | |
|---|---|
| Goal | Find out what Muse does reliably. The results choose the routes for steps 05 and 06. |
| Who | A person runs the tests in Muse |
| Reads | `MUSE-TEST-KIT.md` |
| Writes | `brand/capabilities.json` |
| Checks | SELF (Muse's self-check) · AUTO (OCR on every test image and clip) · HUMAN (scorecard) |
| Gate | Results recorded with `tools/approve.py capability` |

## Do

1. Run the tests in `MUSE-TEST-KIT.md`: Tests 0–5b and 7 in one new Muse chat, Test 6 in a chat of its own.
2. Check every test image with OCR. Test 2 is the S04 card and Test 3 is the S01 layout:

```bash
python3 tools/verify_media.py keyframe episodes/ep01-claim-reject S04 path/to/test2.png
```

3. Check the Test 4 clip. This catches numbers that change while things move:

```bash
python3 tools/verify_media.py clip episodes/ep01-claim-reject S04 path/to/test4.mp4
```

4. Record the results. Use `yes` only for a test that passed three times in a row:

```bash
python3 tools/approve.py capability background_look=yes image_edit_keeps_background=no image_to_video=no code_render=yes max_clip_seconds=10 resolution="704x1248, 24 fps" vertical_9_16=yes --by "Your Name"
```

5. Regenerate the prompt files so they follow the new routes:

```bash
python3 tools/build_prompts.py
```

## What each result switches

| Result | `yes` | `no` or `unknown` |
|---|---|---|
| `code_render` | Steps 05 and 06: Muse builds every shot frame by frame in Python with the brand fonts (exact text and timing). Overrides the next two rows | The next two rows decide |
| `image_text_exact` and `image_edit_keeps_background` | Step 05: Muse renders the card text | Step 05: clean plate, text typed in Canva |
| `image_to_video` and `motion_keeps_text` | Step 06: Muse image-to-video clips | Step 06: animate in Canva |
| `voice_consistent` | Muse voice may be tried for short lines | Step 07: one recorded voice track |
| `reads_website` and `no_invented_numbers` | Muse may draft briefs and data from the site | A person drafts the data in step 02 |

## Re-verify

Run the kit again when Meta updates Muse, every two months, and after any surprising failure in step 05 or 06. Record the new results the same way.
