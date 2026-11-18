# START HERE

You are running the production pipeline for **PF Guru Ji**, Instagram reels that explain EPFO in plain Hinglish: PF claim settlement, how to fill the claim forms, and the problems members run into, with where to get help.

PF Guru Ji is not EPFO and doesn't speak for it. Its reels say what EPFO's own pages say, and send people only to EPFO's official channels.

> **Making a reel? Follow [MUSE.md](MUSE.md).** This file explains the rules, the checks and the approvals behind it.

The pipeline has 11 steps. Each step produces something, checks it, and stops at a gate. **You only move to the next step when the gate is passed.**

## The seven rules

1. **Never invent a number or a rule.** Every number in the voice, on a card or in the caption must be an item in the episode's `data`: a fact with a source, an input, an example marked "maan lo", or a value calculated from those. Every EPFO rule or step the reel relies on is a `rule` item with its official source, and every form it names is in `brand/epfo-forms.json`. If you need something you don't have, write `[NEED DATA: what to find]` and stop.
2. **The episode file is the truth.** `episodes/<episode>/episode.json` holds the brief, data, script, shots and post. The prompt files are generated from it. If anything disagrees with it, the episode file wins.
3. **Check, fix, recheck.** After every upload, read `checks/report.md`. Fix what it lists and upload again until nothing is left to fix; stop when a person must look.
4. **Two tries, then fall back.** If a generated image or clip fails a check, fix it and try once more. After two failed tries, use the fallback in that step's file.
5. **Only people approve.** Steps marked HUMAN need a named person from the team. An AI never approves its own work, and the tools refuse approvals signed "Muse", "Claude" or "AI".
6. **Nothing is published without a person.** Posting needs step 10 approved by a person, and Muse's Instagram connector set to "Always ask".
7. **Never ask for personal details.** No reel, caption or comment asks for a UAN, password, OTP, Aadhaar, PAN or bank details, and none sends people to an agent or a paid service.

## Who checks what

| Mark | Who | How |
|---|---|---|
| **AUTO** | A script | `python3 tools/validate.py` checks the episode files; `python3 tools/verify_media.py` reads the text in images and videos and compares it with the episode file. GitHub runs the file checks on every push. |
| **SELF** | Muse | Muse re-reads its own output against the spec and reports each item, using the self-check prompts. Useful, but never enough on its own. |
| **HUMAN** | A person on the team | Looks, listens, compares with the sources, then records an approval with `tools/approve.py`. |

Every approval is locked to a fingerprint of what was approved. If that content changes later, the checks fail until someone approves it again. Changing the script after approval breaks the chain on purpose.

From episode 05 on, the script comes first: GitHub writes each new reel's script page (`episodes/<episode>/script.md`, with a version code), a person reads it and replies with changes or "script OK", and only that OK (`script-approved.json`, for that version) lets the shots, photos and voice be made and the reel be built. A change to what the script says sends it back to the person (`tools/script_review.py`).

## The steps

| # | Step | Produces | Checks | Gate |
|---|---|---|---|---|
| 00 | [Capability test](pipeline/00-capability-test.md), once | `brand/capabilities.json` | SELF + HUMAN | Results recorded |
| 01 | [Brief](pipeline/01-brief.md) | `episode.json` → brief | AUTO + HUMAN | Person approves |
| 02 | [Data and sources](pipeline/02-data.md) | → data | AUTO + SELF + HUMAN | Every fact and rule checked, person approves |
| 03 | [Script](pipeline/03-script.md) | → script, other hooks, post; `script.md` to read | AUTO + SELF + HUMAN | A person reads the script page and approves it before anything else is made |
| 04 | [Shot list and prompts](pipeline/04-shots.md) | → shots, `prompts.md` | AUTO + SELF | Checks pass |
| 05 | [Keyframes](pipeline/05-keyframes.md) | `media/keyframes/Sxx.png` | SELF + AUTO + HUMAN | Every shot approved |
| 06 | [Motion](pipeline/06-motion.md) | clips or Canva animation | AUTO + HUMAN | Every shot approved |
| 07 | [Voice](pipeline/07-voice.md) | `media/audio/voice.wav` | AUTO + HUMAN | Person approves |
| 08 | [Assembly](pipeline/08-assembly.md) | `media/final/<episode>.mp4` | AUTO + HUMAN | Person approves |
| 09 | [Final QA](pipeline/09-final-qa.md) | the same file, re-checked | AUTO + HUMAN | A second person approves |
| 10 | [Publish](pipeline/10-publish.md) | the live post | HUMAN | Person approves, post recorded |
| 11 | [Measure](pipeline/11-measure.md) | numbers at 24 h, 72 h, 7 days | — | 7-day numbers recorded |

## How to work through it

1. Run `python3 tools/validate.py episodes/<episode>`. Its **Next** line says exactly what to do now.
2. Open that step's file in `pipeline/` and follow it.
3. Run the checks the step lists. Fix anything marked FAIL.
4. Write the check report (below), then stop for the gate.
5. A person approves with `python3 tools/approve.py …`, which re-runs the checks first and refuses if anything is wrong.

## Check report

You don't write check reports any more: after every upload GitHub checks the whole episode and commits `episodes/<episode>/checks/report.md` (`tools/check_episode.py`). It starts with one RESULT:

- **FIX:** something to fix; every item says what's wrong and how to fix it. Fix, upload, and read the next report.
- **WAITING:** only a person's part is left: a fact or rule to check, a line to listen to.
- **PASS:** everything made so far is right.
- **POSTED:** the reel is live (`posted.json`). Never post it again.

Keep going round this loop until the RESULT isn't FIX ([MUSE.md → The check-and-fix loop](MUSE.md)). Stop and ask the person if the same item is still there after two fixes.

## Writing to this repository

Muse writes through its GitHub connector, one file per commit. Every push runs the checks on GitHub, and the result shows on the repo's **Actions** tab.

- Write only inside the episode you're working on: `episodes/<episode>/` (`episode.json`, `reel.json`, `posted.json`, `checks/`, `media/`, `build/`, `test/`).
- Never repeat a reel: read `TOPICS.md` before choosing a topic. Its topic, hook, script and photos must all be new.
- Save media where the step file says, named by shot: `media/keyframes/S06.png`, `media/clips/S06.mp4`, `media/audio/voice.wav`, `media/final/<episode>.mp4`. GitHub re-checks every file saved there.
- To run the checks yourself before pushing, download the repo in one request (GitHub API: `GET /repos/aniket007dc/PF-Uncle-/tarball/main`), unpack it, and run the tools from its top folder. If you can't, push and let GitHub run them.
- After a push, tell the person what you pushed and that the checks are running. Don't call a step done until they pass.

If you can't write at all, put each output in a code block headed with its file path, for example `episodes/ep02-uan-activate/episode.json`, then stop. A person will commit it, and GitHub will run the checks.

## Never

- Never edit `brand/`, `tools/`, `tests/`, `pipeline/`, `templates/`, `.github/` or the files at the top of the repo while making an episode. Those are the rules, not the work.
- Never change a check, a test or a limit to make your work pass. If a check looks wrong, say so in the check report and stop.
- Never edit `status.json`. People record approvals and tries with `tools/approve.py`, which checks first.
- Never put a token, key or password in a file, a commit message or the chat.
- Never post, schedule or reply on Instagram without a recorded approval for step 10.
- Never post a reel twice. Once its folder has `posted.json`, it's live.
- Never put a real person's face, a member's details, the EPFO logo or any government emblem in a frame.

## Where things are

| Path | What it is |
|---|---|
| `brand/brand.json` | Colours, fonts, safe zones, chapters, rules and the list of approvers |
| `brand/epfo-forms.json` | The EPFO forms a reel may name, what each is for, and its official source |
| `brand/capabilities.json` | What Muse passed in the test kit; it picks the routes in steps 5 and 6 |
| `brand/prompts/` | The style lock, motion lock, clean-plate block, self-check, script and shot writer prompts, and the code build rules |
| `brand/fonts/` | The brand fonts: Anton, IBM Plex Mono, Archivo, Caveat, Courier Prime |
| `brand/assets/plates/` | The approved paper (A01) that every shot is built on |
| `brand/asset-prompts.json` | Prompts for the reusable assets A01–A10 |
| `brand/assets/` | Reference images: style frames, header overlay, caption strip, safe-zone guide, palette, type, marks |
| `brand/assets/logo/` | The logo: the Instagram profile picture, the main logo, dark and wide versions, the mark. Its README says which to use where |
| `episodes/<episode>/` | One folder per reel: `episode.json`, `status.json`, generated `prompts.md` and `prompts-writing.md`, `checks/`, `media/`, `assets/` |
| `pipeline/` | One file per step |
| `templates/` | Starting files for a new episode, and examples of every kind of data item |
| `tools/` | The checks and helpers |
| `MUSE-TEST-KIT.md` | Step 00, the capability test |
