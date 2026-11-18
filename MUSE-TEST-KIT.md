# Muse test kit: first video test

Run this before you automate anything. It answers six questions, in order:

1. Can Muse make the PF Guru Ji paper look?
2. Can it spell numbers exactly?
3. Can it animate a card without breaking the text?
4. Can it make a whole scene from one prompt?
5. Can it read EPFO's own site and write a script without inventing a rule or a number?
6. Can it build a shot with code, so every word and number is exact by construction?

It takes about an hour. Every number below is known in advance, so you can check each result digit by digit. Until you've run it, `brand/capabilities.json` says `unknown` for every test, and the pipeline takes the safe route.

## Before you start

- Open Muse. If your account says it isn't available in your country, run the same prompts in any image and image-to-video generator. Nothing here is Muse-specific.
- Write down what Muse offers: video lengths, vertical 9:16, whether you can attach an image to animate, and whether it adds sound.
- Use one new chat for Tests 0–5b and 7, and a separate new chat for Test 6. Paste the setup message first.
- Tests 4 and 5 test Muse's own video model. If a clip comes back wrong, keep it and note what's wrong. Don't let Muse rebuild it another way: building with code is a different route, tested on its own in Test 7.
- Don't connect Instagram posting yet, and post nothing from these tests.

## The correct answers (test data)

| Item | Value |
|---|---|
| Your share in the passbook (example) | ₹1,50,000 |
| The company's share (example) | ₹50,000 |
| The PF that's stuck | ₹2,00,000 |
| Brand | PF Guru Ji |
| Episode tag | PF GURU JI #01 · CLAIM REJECT |
| Tagline | PF samjho, claim pao. |
| Colours | paper #E4DFD6 · ink #1A1A1A · lemon #F5EE30 · red #C8443A |

The amounts are examples, labelled MAAN LO or EXAMPLE wherever they appear.

## Test 0 · Setup message (paste first)

```text
You are the visual designer for my Instagram Reels channel PF Guru Ji, which explains EPFO in plain Hinglish: PF claims, how to fill the claim forms, and the problems people run into. Each reel is 85–95 seconds, vertical, built scene by scene. Remember the style below as PF GURU JI PAPER STYLE and apply it to every image and video I ask for in this chat.

PF GURU JI PAPER STYLE
• Format: vertical 9:16 (1080×1920), flat top-down view, static locked camera. No zoom, pan, tilt or 3D perspective.
• Background: one sheet of warm off-white paper (#E4DFD6), crumpled and flattened, soft crease shadows, soft window light from the top-left, slightly darker toward the bottom. The same background in every scene.
• Objects on the paper: printed cards with soft drop shadows rotated 1–3°; black-and-white halftone newspaper photos with torn deckled edges; red rubber-stamp labels in rounded rectangles rotated 4–8°; graph-paper chart cards; small black label tabs with white letter-spaced monospace caps; handwritten marker notes.
• Colours only: paper off-white, ink black #1A1A1A, lemon yellow #F5EE30 for the key number and highlights, stamp red #C8443A for stamps, warnings and notes, and greys. No other colours, gradients or glows.
• Type: tall condensed heavy sans-serif for numbers and headlines (like Anton), letter-spaced monospace caps for labels (like IBM Plex Mono), handwritten marker for notes (like Caveat). Indian rupee sign ₹ and Indian digit grouping (1,00,000).
• Layout: keep the top 17% and the bottom 35% of the frame plain paper; I add a header and captions there. All cards sit in the middle band.
• Mood: calm, tactile, premium newsroom explainer. No clutter, emojis, logos (never the EPFO logo or any government emblem), brand marks or watermarks, and no words beyond the ones I give you.

Workflow
1. Images: when I attach the background, edit it. Keep the paper exactly the same and add only what I ask.
2. Spell every word and number exactly as I write it. Check each digit before you show me the result.
3. Videos: use my attached images as the start and the target layout. Keep the camera static, keep all text sharp and unchanged, and make the clip silent.

Reply only "PF GURU JI PAPER STYLE locked" and wait for my first scene.
```

Muse should reply "PF GURU JI PAPER STYLE locked".

## Test 1 · Background (image)

```text
Top-down photograph that fills a vertical 9:16 frame: one sheet of warm off-white paper (#E4DFD6) that was crumpled into a ball and flattened out again. Soft, irregular creases with gentle shadows, matte fibrous texture, soft window light from the top-left, and a slightly darker vignette toward the bottom edge. Nothing on the paper: no objects, no marks, no text. Even exposure, sharp detail, realistic.
```

**Pass:** crumpled off-white paper fills a vertical frame, seen from straight above, with no objects, marks or text.
Save it as **A01**. Tests 2 and 3 are edits of this exact image.

## Test 2 · Exact numbers, one card (image)

Attach A01, then paste:

```text
Edit the attached background and keep the paper exactly as it is.
A large lemon-yellow card, about 87% of the frame width and 24% of the frame height, its top edge at 22% of the frame height, rotated −1°, soft shadow.
A black tab at its top-left with white monospace caps "ATKA HUA PF", huge black condensed "₹2,00,000" in the middle, and small black monospace caps "EXAMPLE" at the bottom-right.
Below the card, a red rubber stamp "WAPAS!" rotated +6°.

Style: PF GURU JI PAPER STYLE. Vertical 9:16, flat top-down view, static camera. Warm off-white crumpled-paper background (#E4DFD6) with soft crease shadows, slightly darker toward the bottom; keep it identical to the attached background. Paper-collage editorial look: printed cards with soft drop shadows rotated 1–3°, black-and-white halftone photos with torn deckled edges, red rubber stamps, graph-paper cards, small black label tabs with white monospace caps. Colours only: paper off-white, ink black #1A1A1A, lemon yellow #F5EE30, stamp red #C8443A, greys. Tall condensed heavy sans-serif for numbers and headlines, letter-spaced monospace caps for labels, handwritten marker for notes. Keep the top 17% and the bottom 35% of the frame plain paper. No logos, no brand marks, no watermarks, no extra words. Spell every word and number exactly as written, including the ₹ sign and Indian comma style (1,00,000).
```

**Check each string exactly:** `ATKA HUA PF` · `₹2,00,000` · `EXAMPLE` · `WAPAS!`
**Also check:** the paper matches A01, the card sits in the middle band, and the top and bottom of the frame are empty.

## Test 3 · Exact text, busy layout (image)

Attach A01, then paste:

```text
Edit the attached background and keep the paper exactly as it is. In the middle band add:
(1) A black-and-white halftone newspaper photo, landscape 4:3, about 85% of the frame width, its top edge at 21% of the frame height, rotated −1°, with torn deckled top and bottom edges and a soft shadow. It shows a man in his thirties in a plain work shirt sitting on a bench outside a small workshop in an Indian town, looking worried at the phone in his hands; the screen faces away. A tiny black tab at the photo's bottom-left with white monospace caps "CLAIM STATUS".
(2) Overlapping the photo's upper half, a red rubber-stamp label rotated −5°: rounded red border on white, tall condensed red capitals "REJECTED".
(3) Overlapping the photo's bottom edge, a little right of centre, a black card with small letter-spaced lemon-yellow monospace caps "AAPKA PF" and below them huge white condensed capitals "ATKA?".

Style: PF GURU JI PAPER STYLE. Vertical 9:16, flat top-down view, static camera. Warm off-white crumpled-paper background (#E4DFD6) with soft crease shadows, slightly darker toward the bottom; keep it identical to the attached background. Paper-collage editorial look: printed cards with soft drop shadows rotated 1–3°, black-and-white halftone photos with torn deckled edges, red rubber stamps, graph-paper cards, small black label tabs with white monospace caps. Colours only: paper off-white, ink black #1A1A1A, lemon yellow #F5EE30, stamp red #C8443A, greys. Tall condensed heavy sans-serif for numbers and headlines, letter-spaced monospace caps for labels, handwritten marker for notes. Keep the top 17% and the bottom 35% of the frame plain paper. No logos, no brand marks, no watermarks, no extra words. Spell every word and number exactly as written, including the ₹ sign and Indian comma style (1,00,000).
```

**Check each string exactly:** `CLAIM STATUS` · `REJECTED` · `AAPKA PF` · `ATKA?`
**Also check:** the photo is black and white with visible halftone dots and torn top and bottom edges, and shows no writing or documents.

## Test 4 · Animate it (image-to-video)

Attach your Test 2 image. If Muse lets you choose a start frame, use A01 as the start frame and the Test 2 image as the reference. Then paste:

```text
Build the attached layout on the empty paper.
0.1 s: the yellow card drops in with a small bounce.
2.8 s: the red stamp "WAPAS!" slams down from 150% to 100% size with a short jolt.
Hold until 5 s.

Motion rules: camera locked (no zoom, pan, tilt or shake unless asked). Objects move as solid flat paper: quick move, small overshoot, then hold still. Every letter and number stays sharp and identical once it lands; no morphing, no new text, no new objects. The final frame must match the attached keyframe. Vertical 9:16. Silent: no music, no voice.

Use your video model for this. If the clip comes out wrong, send it anyway and tell me what's wrong. Don't rebuild it with code.
```

**Check:**
- The camera never moves.
- The card drops in at the start and the stamp hits at about 2.8 s.
- No letter or digit changes shape in any frame. Pause and scrub through the clip to check.
- The clip is vertical. Note its length and resolution.

## Test 5 · A whole scene from one prompt (text-to-video)

This is the autopilot test. Attach nothing.

```text
Make a 10-second vertical 9:16 video in PF GURU JI PAPER STYLE. Flat top-down view of one sheet of warm off-white crumpled paper (#E4DFD6) filling the frame; the camera never moves. Keep the top 17% and the bottom 35% of the frame plain paper.
0.0 s: empty paper.
0.1 s: a black-and-white halftone newspaper photo (4:3, torn top and bottom edges, soft shadow) of a worried man on a bench outside a small workshop, looking at his phone, drops onto the paper with a tiny bounce.
1.2 s: a red rubber stamp reading "REJECTED" slams onto the upper half of the photo.
2.0 s: a black card slides up over the photo's bottom edge, with small lemon-yellow (#F5EE30) monospace caps "AAPKA PF" and huge white condensed capitals "ATKA?".
4.0 s: everything slides up and out of the frame.
4.4 s: huge black condensed capitals "PEHLE" pop in on the left. 4.8 s: "WAJAH" pops in below it. 5.3 s: a lemon-yellow marker underline with one small loop draws itself under "WAJAH". Hold until 10 s.
Every letter and number must be spelled exactly as written and stay sharp in every frame. Objects move like flat paper cut-outs: quick move, small overshoot, then still. No logos, no extra words. Silent.

Use your video model for this. If the clip comes out wrong, send it anyway and tell me what's wrong. Don't rebuild it with code.
```

**Check:** everything from Test 4, plus whether both scenes appear, in order, with the right words.

### Test 5b · Voice

```text
Make a voiceover: one male Indian narrator speaking natural Hinglish, calm, close-mic and dry, no music. Use the same voice for both lines and keep every pause under half a second. Read exactly these words; the numbers are spelled the way they must be spoken:
Line 1: "पीएफ क्लेम रिजेक्ट हो गया? पैसा अटका है?"
Line 2: "मान लो, पासबुक में आपका हिस्सा डेढ़ लाख रुपये, कंपनी का पचास हज़ार।"
Put line 1 under the part of the Test 5 video with the photo and the ATKA? card, starting at 0.3 s. Put line 2 under PEHLE WAJAH, starting at 4.0 s. Send the video and the two audio files, and tell me the voice's name.
```

**Check:**
- Listen to line 2: it must say "dedh lakh rupaye" (₹1,50,000) and "pachaas hazaar" (₹50,000). The voice only ever gets the spoken spelling, never digits: a voice given digits guesses, and has read "₹500" as "paanch rupaye" (₹5). Step 07 does the same with the script's `tts` column.
- Line 1 plays while the ATKA? card is on screen.
- Write down the voice's name. Every reel uses that one voice.

## Test 6 · Official site to script (agent)

New chat. Paste:

```text
Open https://www.epfo.gov.in and find EPFO's own page about claims (how to file them online, or why they are rejected). Quote that page's main heading back to me, with its link, so I know you opened it.

Then write a script using the rules below. Use only (a) rules from EPFO's own pages, each with its link, and (b) the numbers in this data sheet. Do not use any other number, rule, limit or time. If you need one, write [NEED DATA: what to find].

Data sheet (these are examples; say "maan lo" whenever you use one):
- Your share in the passbook: ₹1,50,000
- The company's share: ₹50,000
- Together: ₹2,00,000

Write a Hinglish (Roman script) Instagram Reel voiceover for PF Guru Ji. Topic: PF claim reject kyun hota hai, aur kaise theek karein? Viewer: someone who left a job, filed for their PF online, and saw the claim come back rejected.

Rules, follow exactly:
1. 150–175 words (about 60–70 seconds at a brisk pace). Sentences of 3–9 words. Sound like a patient friend, not an ad or a notice.
2. Chapters in this order: HOOK, PROBLEM, WHY ("Ek: … Do: … Teen: …"), STEPS (the real menus on the member portal), CHECK (one thing before filing again), HELP (an official channel only), SHARE ("… abhi bhejo."), SIGN-OFF: "PF samjho, claim pao. EPFO ki har jankari chahiye? Follow karo PF Guru Ji."
3. Every rule must come from an EPFO page I can open, and every number from the data sheet. Never ask the viewer for personal details, never send them to an agent, and never promise a result or a date.
4. Output a table with columns: # | Chapter | VO line | TTS spelling (Devanagari, numbers as spoken words, form names in English) | Caption highlight words | On-screen element (choose from: halftone photo, red stamp, black card, yellow card, white card stack, graph-paper bar/line/funnel chart, kinetic headline, arrow cards, timeline bar, typewriter card, handwritten note, share photo) | Exact card text | Source link.
5. After the table: the Instagram caption (the hook, one line of what to check, the share line, 5 hashtags), a cover headline of max 5 words, and a pinned comment that invites a question without asking for personal details.
```

**Check:**
- The heading it quotes is really on the page it links (open the link yourself).
- Every rule in the script is on an EPFO page it links, and every number is from the data sheet.
- Assumptions say "maan lo".
- The script is 150–175 words of Roman Hinglish and ends with "PF samjho, claim pao. EPFO ki har jankari chahiye? Follow karo PF Guru Ji."

## Test 7 · Build a shot with code

> Now done for every episode by `tools/build_reel.py` (see MUSE.md), so this test is optional. It's still a good check that Muse can run Python if you want it to build reels itself.

Muse can run Python. This route draws every word with the brand fonts, so the text is exact by construction, and the timing is exact to the frame. Muse needs the GitHub connection, or attach `brand/assets/plates/paper-a01.webp` and the files in `brand/fonts/` yourself.

```text
Build shot S04 with code, not with the image or video model. First read these from the GitHub repo aniket007dc/PF-Uncle-: brand/prompts/code-build.txt (the rules: follow every one), brand/assets/plates/paper-a01.webp (the paper) and the fonts in brand/fonts/.
Text, exactly: "ATKA HUA PF", "₹2,00,000", "EXAMPLE", "WAPAS!"
Layout: a large lemon-yellow card, about 87% of the frame width and 24% of the frame height, its top edge at 22% of the frame height, rotated −1°, soft shadow. A black tab at its top-left with white monospace caps "ATKA HUA PF", huge black condensed "₹2,00,000" in the middle, and small black monospace caps "EXAMPLE" at the bottom-right. Below the card, a red rubber stamp "WAPAS!" rotated +6°.
Motion: 0.1 s: the yellow card drops in with a small bounce. 2.8 s: the stamp "WAPAS!" slams down from 150% to 100% size. Hold until 5.0 s.
Save the clip, its last frame and the script in episodes/ep01-claim-reject/test/test-7/ as S04.mp4, S04.png and S04.py.
```

**Check:**
- OCR on `S04.png` and `S04.mp4` passes (commands under *Record the results*).
- The paper never changes during the clip, and nothing sits in the top 17% or bottom 35%.
- The script uses only paths inside the repo, so running `python3 episodes/ep01-claim-reject/test/test-7/S04.py` from the repo root makes the same clip again.

## Scorecard

| Test | What to check | Pass / fail | Notes |
|---|---|---|---|
| 1 Background | Paper look, no objects or text | | |
| 2 Simple card | 4 strings exact | | |
| 3 Busy layout | 4 strings exact, halftone photo, no writing in it | | |
| 4 Animate | Camera still, text never warps, stamp timing | | |
| 5 One-prompt scene | Both scenes, right words, text stable | | |
| 5b Voice | "Dedh lakh" and "pachaas hazaar" said right, each line under its card, voice name noted | | |
| 6 Script | Opened EPFO's page, no invented rule or number, no personal details asked | | |
| 7 Code build | 4 strings exact, paper steady, script runs again | | |

Also note: clip lengths offered, resolution, whether 9:16 works, whether image-to-video works, and any visible watermark or label.

## Reading the results

- **Tests 1–3 pass, Test 4 warps the text:** this is the likely result. Use Muse for images only, and animate in Canva as `pipeline/06-motion.md` describes.
- **Tests 1–4 pass:** Muse can make individual shots. Still check every digit before posting.
- **Test 5 passes:** one prompt per scene could work. Keep a human review before posting anyway.
- **5b voice changes between clips:** record one voiceover track for the whole reel instead.
- **Test 6 uses a rule or number that isn't on EPFO's page or the sheet:** never let it post without your approval.
- **Test 7 passes:** record `code_render=yes`. Steps 05 and 06 then switch to the code route: Muse builds every shot with code, and the image model makes only pictures without writing. This beats every other route on exact numbers and timing.

## Record the results

This kit is step 00 of the pipeline (`pipeline/00-capability-test.md`). Re-check each image and clip with OCR, then record what passed so the pipeline picks the right routes:

```bash
python3 tools/verify_media.py keyframe episodes/ep01-claim-reject S04 path/to/test2.png
```

```bash
python3 tools/verify_media.py clip episodes/ep01-claim-reject S04 path/to/test4.mp4
```

```bash
python3 tools/approve.py capability background_look=yes image_edit_keeps_background=no image_to_video=no code_render=yes max_clip_seconds=10 resolution="704x1248, 24 fps" vertical_9_16=yes --by "Your Name"
```

Write `yes` only for a test that passed three times in a row. Two exceptions: the background is made once and reused, so one good plate is enough for `background_look`; and code builds the same output every time, so one clean pass is enough for `code_render`. The command above is only an example of the format: record what your own run shows, and leave anything you haven't tested as `unknown`.

## Before you automate (repo and Instagram)

- **GitHub:** I found no confirmed built-in GitHub connector for Muse; third-party connectors exist. The simplest route is to let Muse read this file by link, which needs the repo to be public or a connector with read access.
- **Instagram:** Muse's built-in Instagram connection reads posts and messages. Posting and scheduling go through third-party posting connectors. Set Muse's connector permission to "Always ask" so nothing goes live without your approval.
- **Review step:** for a channel about people's money and their EPFO claims, keep one human check before every post. One wrong rule costs more trust than one missed day.

## Sources

- Meta AI, Introducing Muse Image and Muse Video: https://ai.meta.com/blog/introducing-muse-image-muse-video-msl/
- IBTimes India, Muse not available in India: https://www.ibtimes.co.in/meta-muse-not-available-india-instagram-shows-ai-agent-icon-users-see-not-available-your-907188
- Postiz, Muse connectors and scheduling posts: https://postiz.com/blog/meta-muse-ai-connectors-schedule-social-media-posts
- Built with Muse, Instagram connector: https://builtwithmuse.com/blog/muse-instagram-connector
- anythingmcp, connecting GitHub to Muse: https://anythingmcp.com/guides/connect-github-to-muse
