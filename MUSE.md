# Muse: make a PF Guru Ji story reel

This is the one file Muse follows. For a new reel, a person pastes the prompt in **A new episode** below; to finish a reel whose script is approved, the one here. Everything else is in this repo.

## Paste this into Muse

```text
You make Instagram story reels for PF Guru Ji, a channel that explains EPFO in plain Hinglish through short stories told with paper cut-outs. Your GitHub connection gives you the repo aniket007dc/PF_stories. Open MUSE.md in that repo and follow "Making the reel" for the episode episodes/<EPISODE FOLDER> (its script must already be approved). Work one step at a time. After each step, tell me exactly what you made and where you saved it, then wait for my OK before the next step. Never post anything to Instagram until I write "post it".
```

## What we're making

A vertical reel of about 60 to 75 seconds (1080×1920, 30 fps) that tells a short story: Shivam (or someone else from the cast) runs into a PF problem, and the story shows what he does about it, the right way. Everything is a paper cut-out on one crumpled sheet of paper: the people as jointed paper puppets that walk, wave and react, the places and things (the mill, the PF office, a phone, a form) as paper props, speech bubbles for what they say, and the series' yellow, white and black cards with huge numbers and red rubber stamps above them. Everything moves in stop motion. A header with the brand name and a running timecode, a torn caption strip whose words darken as they're spoken, and torn-paper sheets between chapters, all in the PF Guru Ji colours.

- **What it looks like:** [`brand/assets/style-frames/cutout-demo.mp4`](brand/assets/style-frames/cutout-demo.mp4), a 21-second style test (its `reel.json` is in `brand/assets/style-frames/cutout-demo/`), and [`cutout-demo-sheet.jpg`](brand/assets/style-frames/cutout-demo-sheet.jpg).
- **The cast:** `brand/brand.json` → `cast`: Shivam (the hero), Priya (HR), Ravi (his friend) and Papa. The build draws each of them the same way in every reel.
- **Two themes:** this paper cut-out story is **Kahani**, the default. The other is **Focus** (`"style": "focus"` in `episode.json`): how to do one EPFO task on the screen itself, the member portal's pages drawn from the newest official pages and videos and opened in a MacBook on a clean white page, the cursor clicking each button as the voice names it (`styles/focus/STYLE.md`; a sample: `styles/focus/ep00-focus-sample/`). Kahani shows what happened to Shivam; Focus shows how to do it on the portal. **Focus for a Focus reel** below says what changes.
- **The finished reel:** `episodes/<episode>/media/final/<episode>.mp4`, which GitHub builds once the voice lines are uploaded.
- **What PF Guru Ji is:** a channel that explains EPFO. It isn't EPFO and doesn't speak for it: every rule a reel states comes from EPFO's own pages, and a person checks each one.
- **Every reel so far:** [`TOPICS.md`](TOPICS.md). A new reel never repeats one of them.

## Who does what

| Who | Does |
|---|---|
| **Muse** | Writes new episodes (the story script, then the scenes in `reel.json`), makes the voice lines, and uploads them. No photos: the build draws every person and thing |
| **The build** (`tools/build_reel.py`, `tools/cutout.py`; GitHub runs it by itself) | Draws everything you see and hear apart from the voice: paper, the cut-out people and things and how they move, header, speech bubbles, cards, numbers, stamps, charts, captions, wipes, sound effects, the mix, and the cover |
| **A person** | Checks every fact and rule against EPFO's own pages, reads and approves each new reel's script and hook before anything else is made, takes the member portal screenshots a reel needs (on their own login, every personal detail covered), approves the finished reel, and says when to post |

Why it's split this way: in Muse's first test (12 Nov 2026), its video model kept the numbers but ignored the timing and the layout. So no word or number is ever drawn by AI. The build draws them from the episode file with real fonts, and a check reads every card back with OCR. The cut-outs are drawn from shapes for the same reason: Shivam looks the same in every shot of every reel.

## The rules

1. **No writing in AI pictures.** Photos have no text, numbers, logos or labels at all, and never show a form, an ID card, a passbook, the EPFO logo or any government emblem. If one comes back with any of that, make it again.
2. **Never change a number, a rule or what a line means.** Everything on screen comes from `episode.json`, and every EPFO rule in it comes from a `rule` or `fact` item with an official source. The one change you may make on your own is how a word is spelled in a voice text (`tts`), when the check report asks for it; the checks make sure its numbers stay the same.
3. **One voice, always the same: Bunty.** Use it for every line of every episode, with the same model and settings for every line of a reel, and name the model in your upload message. One exception: ep06's lines were made on a computer with `tools/make_voice.py` (a native Hindi voice, its `voice-takes.json` sits next to them). Never make or upload an ep06 line yourself: if the report asks for one, send the person that item.
4. **Only write where this file says.** Never edit `tools/`, `brand/`, `pipeline/`, `.github/`, `tests/`, `status.json` or `TOPICS.md`, or the pages GitHub writes for an episode (`prompts.md`, `prompts-writing.md`, `script.md`, `checks/`): change `episode.json` and they follow. Never put a token or password in any file.
5. **Nothing goes live without a person.** Post only after a person writes "post it".
6. **Never sign anything off.** Checking a fact, approving a step and posting are a person's. Never write your name (or "Muse") as the one who checked or approved something. When a person approves a script or writes "post it", you record their name and their words (`script-approved.json`, `posted.json`), never your own.
7. **Never ask for personal details.** No reel, caption or reply asks anyone for their UAN, password, OTP, Aadhaar, PAN or bank details, and none sends people to an agent or a paid service.
8. **Never repeat a reel.** Every reel has its own topic, hook, script and photos. [`TOPICS.md`](TOPICS.md) lists every reel made so far, and the checks compare each new one with all of them. Every reel is posted once: when its folder has a `posted.json`, it's live, so never post it again.
9. **Screenshots come from a person.** A reel that shows the member portal uses screenshots a person takes on their own login. Never log in to any EPFO site, and never ask anyone for a UAN, password or OTP. Before you upload a screenshot a person gives you, look at it: if a name, anything from someone's account (UAN, member ID, Aadhaar, PAN, bank account, mobile, email, amounts, claim numbers) or the EPFO logo or a government emblem shows, don't upload it: send it back to the person to cover or crop.
10. **The script comes first.** From episode 05 on, a new reel's script and hook go to a person before anything else is made. Make no shots, `reel.json`, photos, screenshots or voice lines until the person has written that the script is OK and you've uploaded `script-approved.json` for that version (N3). If the script changes after that, it goes back to them.
11. **The cast stays the cast.** Use only the people in `brand/brand.json` → `cast`, by their names, as puppets. Never make a photo or an AI picture of a person for a story reel: the build draws everyone as a paper cut-out, the same in every reel.

## The check-and-fix loop

Every upload is checked on GitHub. About 5 to 10 minutes later, **Build reel** commits the result as `episodes/<episode>/checks/report.md`. Its first lines name the commit it checked: make sure that's your latest upload. Then act on its **RESULT**:

- **FIX:** fix every item under "To fix (Muse)", each exactly as its "Fix:" line says. Upload the changed files, wait for the next report, and read it again. Repeat until the result is no longer FIX.
- **WAITING:** there's nothing left for you to fix. Send the person the items under "For a person" and stop. If one is **Script review**, send them the script page it links, as N3 says.
- **PASS:** everything made so far is right. Report it, and go on to the next step after the person's OK.
- **POSTED:** the reel is live. Never post it again and don't change its files. Send anything the report lists to the person.

While you fix:

1. Fix only what the report lists, the way it says. Never change a number, a fact or what a line means to make a check pass, and never edit a check.
2. Never upload a file that hasn't changed: it changes nothing and wastes a check.
3. If the same item is still there after you've fixed it twice, stop fixing it and send it to the person with the report.
4. "To look at" items don't block anything: look at them in the reel and say in your report that they're right.

The report also lists what's still to make (photos, voice lines) and the steps waiting for a person's approval.

## Making the reel (Steps 1–6)

For an episode whose script a person has approved and whose `reel.json` is written (N1–N4 below). Every prompt you need is in its `episodes/<episode>/prompts.md`. Use them exactly as written.

### Step 1 · Photos (only if prompts.md lists any)

A story reel usually has none: `prompts.md` → **1 · Photos** says so. If it lists some:

1. Make every photo that isn't in `media/photos/` yet (the check report lists them under "Still to make").
2. For each one, use its prompt exactly. Make three options and pick the one with the clearest subject in the middle of the frame and **no writing anywhere**.
3. Save each under the file name shown, for example `episodes/<episode>/media/photos/street_morning.webp`. JPG, PNG or WEBP are all fine, but keep the name.
4. Check: black and white, landscape, the subject in the middle (the top and bottom edges get torn off), no letters or numbers, no documents, no logos, no watermark.
5. Every photo is made new for this reel. Never reuse a photo from another reel, even one that would fit: the check compares them.

Report: the file names, and a one-line description of each photo.

### Step 1b · Screenshots (only if prompts.md has them)

1. Send the person the list in `prompts.md` → **1 · Screenshots**: what each one shows, its file name, and the words it must show. A person takes them on their own login; you never do.
2. When the person gives you the files, look at each one as rule 9 says, then upload each to its path, one file per call. Upload nothing that shows anything personal.
3. The report reads every screenshot back. If one doesn't show the words its line names, it goes to the person (the portal may have changed). If a ring or highlight in `reel.json` isn't on its words, the report gives the box to use: copy it into that mark and upload `reel.json`.

Report: the file names, and anything you sent back to the person.

### Step 2 · Voice

1. Open `prompts.md` → **2 · Voice**. Give your voice tool the voice description there, with the series voice, **Bunty**. Make every line of the reel with the same model and settings: when you re-make one line, use the model the other lines were made with (your upload messages name it, such as "Turbo v2.5, speed 1.1").
2. For each line, S01 to the last one, give the voice tool **only** the text in the "Say exactly" column, copied exactly, and the feeling in its "How to say it" column (when the table has one): with an emotion-tag voice model such as ElevenLabs v3, put the mood as a tag before the text (`[curious] …`); a tag is never read aloud. It's in Devanagari on purpose; English words, numbers and form names are already spelled the way they're said in India (क्लेम, केवाईसी, एट पॉइंट टू फ़ाइव परसेंट, फ़ॉर्म नाइनटीन, पीएफ गुरु जी): numbers are said in English. Don't retype it in English letters, don't add the shot number, and don't "correct" anything.
3. Make **one file per line**. Your voice tool gives the same audio for the same text every time, so a second take changes nothing.
4. Save each file **exactly as the voice tool made it**. Don't trim the silence before or after it, and don't cut, speed up, slow down, normalise or join files: the pause before and after each line must stay. Save as `episodes/<episode>/media/audio/lines/S01.mp3`, `S02.mp3` and so on, one file per line (MP3 or WAV).
5. If the voice tool can't read Devanagari (it stays silent, or speaks another language), stop and report it. Never switch to English letters to get around it.

You can't listen to the files, so GitHub does it for you after you upload them (Step 4): it writes down what each line says and checks it against the "Listen for" column. Report: the voice's name and the file names.

### Step 3 · Upload

Upload the voice files (and any photos) to those paths in `aniket007dc/PF_stories`, on `main`, one file per call. Upload nothing else.

### Step 4 · The build (automatic)

Each upload starts **Build reel** on GitHub (repo → **Actions**). About 5 to 10 minutes after the last file, it has:

- built the reel, timing every shot to its voice line, and saved `episodes/<episode>/media/final/<episode>.mp4` and `cover.jpg`;
- checked everything (`tools/check_episode.py`): the episode file, `reel.json`, every voice line (each number and the brand name must be heard, nothing trimmed, and each file made from its line as the line is now: change a line's text and its file must be made again) and every card in the reel (read back with OCR);
- committed the result as `episodes/<episode>/checks/report.md`.

If you'd rather build it yourself: download the repo in one request (GitHub API `GET /repos/aniket007dc/PF_stories/tarball/main`), unpack it, then run this from its top folder (needs Python, Pillow, numpy and ffmpeg):

```bash
python3 tools/build_reel.py episodes/<episode>
```

### Step 5 · Check the reel

1. Run **the check-and-fix loop** on `checks/report.md` until its RESULT is PASS or WAITING. Two things to know about voice fixes:
   - Your voice tool makes the same audio from the same text, so making a line again without changing anything gives an identical file. A voice fix always changes something: the text the report tells you to respell, or the file's untrimmed silence.
   - If "heard" shows the same words as "should say", only spelled differently, the check misheard a correct line: don't change it, send it to the person to listen.
2. Download the reel and watch it with sound. Check:
   - every card arrives as its words are spoken;
   - every person and thing is a paper cut-out that stands on the ground, walks and reacts on its words, and nothing is cut off at the edges;
   - no bubble, card or stamp covers a face;
   - the voice is the same all the way through, and every line ends cleanly, with nothing cut off;
   - the torn sheets sweep across between chapters;
   - it ends on the PF Guru Ji end card: the logo, then the FOLLOW @PFGURUJI button as the voice says "Follow karo PF Guru Ji".

Report: the link to the reel, the report's RESULT, the "To look at" items you checked, and anything that looked or sounded wrong.

### Step 6 · Approval, then posting

1. Send the person the reel link, `cover.jpg`, the voice check result, and the post text from `episode.json` → `post`: the caption with its 5 hashtags, and the pinned comment. Ask them to listen to the whole reel, especially the numbers in the "Listen for" column and any line marked CHECK BY EAR.
2. Wait. The person checks the facts, watches the reel and records approvals in the repo.
3. Only after they write **"post it"**, first look for `episodes/<episode>/posted.json`. If it's there, the reel is already live: don't post, send the person the link in it, and stop.
4. Post the reel to Instagram with that caption, use `cover.jpg` as the cover, and pin the comment.
5. Right after posting, upload `episodes/<episode>/posted.json`, so the reel is never posted twice:

   ```json
   {"url": "https://www.instagram.com/reel/<the post's code>/", "posted_on": "2026-11-20", "post_it_from": "<the name of the person who wrote post it>"}
   ```

   Then send the person the post link. From then on the report says POSTED, `TOPICS.md` shows the link, and GitHub never rebuilds that reel.

## A new episode

### Paste this into Muse

Use this for every new reel: a new topic, a new script, new photos.

```text
You make Instagram story reels for PF Guru Ji from the GitHub repo aniket007dc/PF_stories: short stories about Shivam and the cast in brand/brand.json, told with paper cut-outs. Open MUSE.md and follow "A new episode" from step N1.

Topic: <TOPIC, or "suggest 3">
Who it's for: <VIEWER, or "you suggest">
Sources I already have: <EPFO PAGES OR CIRCULARS, or "none: find them on EPFO's own pages">

Before anything else, read TOPICS.md: it lists every reel we've made. Never make a reel that repeats one of them (the same question, even in other words), and never reuse a script line, a photo or a photo prompt from another reel. If my topic repeats one, tell me which one and suggest 3 new topics.
Every rule, limit, time and number comes from EPFO's own pages or circulars, with the link; never from a news site or a video. Never ask anyone for personal details.
Work one step at a time. After every upload, read the episode's checks/report.md and follow the check-and-fix loop in MUSE.md until its RESULT is PASS or WAITING. After each step, tell me exactly what you made and where you saved it, then wait for my OK before the next step.
When the script and hook are written (N3), send me the script page and stop: make nothing else until I write "script OK".
Never post anything to Instagram until I write "post it", and never post an episode that already has a posted.json.
```

Fill in the three `<…>` parts. Example: topic "UAN activate kaise karein?", viewer "someone starting their first job who has a UAN but has never logged in", sources "none: find them on EPFO's own pages". To let Muse pick the topic, write `suggest 3`.

### N1 · A new topic, then the folder

1. Open [`TOPICS.md`](TOPICS.md). It lists every reel made so far (its topic, hook, what it covers and its photos) and the next free episode number.
2. If the person wrote "suggest 3": suggest 3 topics that PF members ask about (the topic bank in `pipeline/01-brief.md` has ideas) and that aren't in TOPICS.md. For each, give the question in one line, who it's for, and the reel in TOPICS.md that's closest with how this one is different. Wait for the person to pick one.
3. If the person gave a topic: compare it with every reel in TOPICS.md. If it asks the same question as one of them (even in other words), don't start: tell the person which reel it repeats and suggest 3 new topics.
4. Take the next free number from TOPICS.md (`ep02`, `ep03` …; never one a folder already has). Choose a slug: 2 to 5 lowercase words joined by hyphens that name the topic, such as `uan-activate`.
5. Copy `templates/episode.template.json` to `episodes/<id>-<slug>/episode.json`. Fill in:
   - `id`, `slug`, `title` (the topic as a Hinglish question), `tag` (`PF GURU JI #02 · ` plus 2 to 4 words in capitals) and `created` (today, as YYYY-MM-DD). Keep `"route": "build"`.
   - `brief.topic`: the question this reel answers.
   - `brief.repeat_check`: in `closest`, the folder name of the reel in TOPICS.md nearest to this one (such as `ep01-claim-reject`); in `different_because`, one sentence on how this reel's question, steps or viewer are different.
6. Upload `episode.json`. GitHub compares the topic with every earlier reel and writes `checks/report.md`. Run **the check-and-fix loop** until its RESULT is PASS or WAITING. If the report says the topic repeats a reel, don't change the topic on your own: tell the person and suggest 3 new ones, as its "Fix:" line says.

Report: the folder name, the title, the closest reel and how this one is different. The person approves the topic before you go on.

### N2 · Brief and data

1. **Brief:** fill every field of `brief`, as `pipeline/01-brief.md` describes: topic, viewer, hook, problem, why (1 to 3 reasons), steps (2 to 5, in order), check, help, share_target and why_now.
2. **Data:** list every number the reel will use, and every EPFO rule or step it relies on, one item each, as `pipeline/02-data.md` describes (examples of every kind are in `templates/data-item-examples.json`):
   - `fact`: a number EPFO or the law publishes. Give `source`, `source_url` and `check_note`, and leave `checked_by` empty: a person checks it. Use EPFO's own pages and circulars, and link the exact page.
   - `rule`: an EPFO rule or step without a number, in one plain `statement`, with `source`, `source_url` and `check_note`. A person checks it too.
   - `input`: a number we choose for the episode's premise.
   - `assumption`: an example number. The script must say "maan lo" the first time it's used.
   - `derived`: worked out from other items, with its `formula`. The check recalculates it.
   Never use a number or a rule that isn't one of these, and name only the forms in `brand/epfo-forms.json`.
3. Upload `episode.json`. GitHub prepares the folder (`status.json`, the prompt files) and writes `checks/report.md`. Run **the check-and-fix loop** until its RESULT is PASS or WAITING (the facts you found wait for the person).

Report: the brief in 5 lines and the data list with every source link. The person checks every fact and rule before you go on.

### N3 · Script and hook, then the person's review

1. Open the episode's `prompts-writing.md` → **Step 3** (GitHub filled in your topic, viewer and data) and follow it exactly.
2. Put its `script`, `hook_options` and `post` into `episode.json`. Every line has a caption text (`vo`, English letters) and a voice text (`tts`, Devanagari, numbers spelled the way they're said), as the prompt explains. `hook_options` holds two other first lines the person can pick instead of yours.
   - Write every line new for this topic. Never copy a line, a hook or a cover from another reel, even a good one: the check compares them. Only the share line and the sign-off follow the series format in every reel.
3. Upload `episode.json`. The report tests every number against the data (the other hooks' numbers too), every form against `brand/epfo-forms.json`, the voice text's numbers against the caption's, the length (150 to 175 words), the chapters, the share line and the sign-off. Run **the check-and-fix loop** until its RESULT is no longer FIX.
4. **Send the script to the person, then stop.** GitHub writes the script page, `episodes/<episode>/script.md`: the hook and the other hooks, every line and how it's said, every number and rule with its source, the cover and the caption, and a **version** code at the top. The report's **Script review** item links it. Send the person the link and the page's text as it is. Then make nothing else: no shots, `reel.json`, photos, screenshots or voice lines.
5. The person reads it and replies:
   - **Changes** (a line's new words, "Hook B", a new cover): make exactly those changes and nothing else, keeping every number from data. Write the voice text (`tts`) and how it's said (`delivery`) for any changed line. A hook they pick becomes S01, and the old S01 goes into `hook_options`. Upload `episode.json`, run the check-and-fix loop, and send them the new page (its version changes with every change). Repeat until they're happy.
   - **OK** ("script OK", "approved", "theek hai, aage badho"): upload `episodes/<episode>/script-approved.json`, with the version on the page they approved:

     ```json
     {"version": "3fa9c1", "approved_by": "<the person's name>", "approved_on": "2026-11-16", "their_words": "<what they wrote, exactly>"}
     ```

     Write it only after their OK, only with the version on the page they read, and never with your own name. If you changed anything after sending that page, send the new page and wait for their OK on it.
6. The next report lists "Script review: … approved version …" under Passed. Only then go on to N4. If the script changes later (say the person asks for another change after the voice is made), it goes back to them the same way, and nothing new is made or built until they approve the new version.

Report: the script page's link and version, and the person's answer.

### N4 · Shots and reel.json

1. Start only when the report lists the script review under Passed. Open `prompts-writing.md` → **Step 4** and follow it exactly. It uses the approved script.
2. Put its `shots` and `breaks` into `episode.json`, and write `reel.json` as the prompt says: every shot a cut-out scene (ground, place, people, what they do and say on the line's words), following each line's `scene`. If the reel shows the member portal, list each screenshot under `screens` with what it shows and the words it must show; a person takes them later (Step 1b).
3. Upload both. GitHub builds a **draft reel** without the voice (`media/final/`), checks that every word on screen is in that shot's `card_text` and reads every card back. Run **the check-and-fix loop** until its RESULT is PASS or WAITING.
4. Watch the draft: the story reads without sound, each person does what their line says on its words, each card matches its line, nothing covers a face, every word is readable.

Report: the draft reel's link. The person approves it.

### Focus for a Focus reel

When the topic is "how to do it on the portal" (Mark Exit, a claim, a transfer, KYC, the passbook, a nominee), suggest the Focus theme to the person; they pick. For Focus, the steps above change like this:

- **N1:** write `"style": "focus"` in `episode.json`, next to `"route": "build"`.
- **N2:** the brief is `topic`, `viewer`, `hook`, `app` (the member portal, the passbook site or UMANG, and on a laptop or a phone), `steps` (3 to 12, in the portal's order), `check` (how the viewer sees it worked) and `share_target`. The data lists only the rules and numbers the reel says; a how-to needs few.
- **N3:** `prompts-writing.md` → Step 3 is the Focus prompt. Before writing, open EPFO's newest page for the task and one or two videos from the last 60 days that do it on screen (EPFO's pages often refuse automated reading: open them in a browser), and write the steps, with every menu and button name exactly as the portal shows it, in `research.md` → Steps on screen. 100 to 220 words; the chapters are the how-to's own (hook, why, route, steps, mistake, fix, check, list, share, signoff).
- **N4:** `prompts-writing.md` → Step 4 is the Focus reel prompt. You describe every screen in `reel.json` → `screens` (no screenshots, and nobody's details: masked numbers only), with two sources each, one of them EPFO's own, each with the day you read it. The walk starts on the page the viewer sees after logging in, and every later page is opened on screen by the click that leads there. The draft shows every screen drawn.
- **Steps 1 and 1b** don't apply: a Focus reel has no photos and no screenshots. Step 2 (voice) is the same.

### Then Steps 1–6

Do Steps 1–6 above for the new episode: the voice lines (and any photos its `prompts.md` lists), upload, build, check, and approval and posting (Step 6 ends with `posted.json`).

### reel.json building blocks

Positions are in pixels on the 1080×1920 frame. `x` is the centre (540 is the middle) and `y` is the top. Stamps, notes and bubbles use their centre; people and props stand on the ground line (`y` is where their feet or bottom are, 1170 by default). Everything goes between y = 400 and 1240: the scene below (y 640–1240), one card, stamp or bubble above the heads (y 400–640). The build places the header above and the captions below by itself.

Timing: `"at": 1.2` means 1.2 s after the shot starts. `"on": "KYC"` means "as this word of the shot's voice line is spoken", and it follows the real voice. Entrances (`"in"`): `rise` (default for cards), `drop`, `slide_left`, `slide_right`, `slam` (stamps), `pop` (headlines), `write` (notes), `none`.

| Type | Looks like | Main fields | Example |
|---|---|---|---|
| `ground` | The torn paper strip the scene stands on: first in every scene shot | `color`, `y` | `{"type": "ground"}` |
| `puppet` | A person from the cast as a jointed paper puppet: walks, changes pose and mood, jumps, nods, shakes on the line's words | `who`, `x`, `scale` (0.8), `facing`, `pose`, `mood`, `moves` (`do`: walk `to`, pose, mood, turn, jump, nod, shake; `on` or `at`) | `{"type": "puppet", "who": "shivam", "x": -140, "moves": [{"do": "walk", "to": 330}, {"do": "jump", "on": "pehli"}]}` |
| `prop` | A thing cut from paper: factory, office, bank, home, phone, document, coins, calendar, laptop, tick, cross, clock, suitcase, cloud, sun, desk, skyline | `kind`, `x`, `y`, `scale`, `variant`, `label` (a sign's words), `tab`, `idle` (sway, bob, buzz, spin) | `{"type": "prop", "kind": "office", "x": 760, "label": "PF OFFICE"}` |
| `bubble` | A speech (or thought) bubble with what someone says, 2 to 6 words | `text`, `x`, `y`, `tail`, `thought` | `{"type": "bubble", "text": "PURANA UAN HAI?", "x": 690, "y": 600, "tail": "down-right", "on": "poocha"}` |
| `photo` | Rarely: a halftone photo with torn top and bottom, optional black tab | `src` (id in `photos`), `tab`, `y`, `h` | `{"type": "photo", "src": "street_morning", "tab": "SUBAH", "y": 400, "h": 560}` |
| `card` | White, yellow or black card: tab, big number, label on the right, small line at the bottom right | `style`, `tab`, `prefix` (÷ × = ≈ +), `big`, `label`, `foot`, `size` | `{"type": "card", "style": "yellow", "tab": "ATKA HUA PAISA", "big": "₹2,50,000", "foot": "MAAN LO", "y": 430}` |
| `stamp` | Red (or `"color": "ink"`) rubber stamp | `text`, `sub`, `x`, `y`, `rot`, `size` | `{"type": "stamp", "text": "REJECT!", "x": 890, "y": 770, "rot": 8, "on": "reject"}` |
| `headline` | Huge black words straight on the paper | `lines`, `x`, `y`, `size`, `underline` | `{"type": "headline", "lines": ["CLAIM", "REJECT?"], "x": 80, "y": 520}` |
| `note` | Handwritten note, red by default | `text`, `x`, `y`, `size`, `rot`, `color` | `{"type": "note", "text": "us dost ko", "x": 320, "y": 1110, "on": "dost"}` |
| `tag` | Yellow slap-on label | `text`, `x`, `y`, `rot`, `size` | `{"type": "tag", "text": "SHARE ↗", "x": 770, "y": 905, "on": "abhi"}` |
| `funnel` | Graph-paper card with bars that grow | `tab`, `rows` (`text`, `width` 0–1, `style`, `on`) | `brand/prompts/reel-writer.txt` |
| `line_chart` | Graph-paper card with a red line drawing itself | `tab`, `start` / `end` (`value`, `sub`) | `brand/prompts/reel-writer.txt` |
| `arrow_card` | Card with a drawn arrow, a title and a small line | `arrow` (→ ↗ ↘), `title`, `sub`, `style` | ep01 S06 |
| `timeline` | Bar that fills in segments, with ticks and a key | `tab`, `segments`, `ticks`, `foot` | `brand/prompts/reel-writer.txt` |
| `typewriter` | Card that types itself, with a highlighter swipe | `tab`, `lines`, `highlight`, `highlight_on` | ep01 S11 |
| `screen` | A member portal screenshot on a white card, with a red ring (or a yellow highlight) landing on the menu or button the line names | `src` (id in `screens`), `tab`, `crop`, `marks` (`box`, `text`, `on`, `style`) | `brand/prompts/reel-writer.txt` |
| `endcard` | The logo, the tagline, the follow line (a red note over a FOLLOW @PFGURUJI button that pops in on `cta_on`) and small print | `tagline`, `small`, `cta_on`; `logo_file`, `cta`, `cta_note` to change the defaults in `brand/brand.json` | ep01 S15 |

The whole demo, shot by shot: `brand/assets/style-frames/cutout-demo/reel.json`. Photos, if any, are listed once under `"photos"`, each with an `id` (P1, P2 …), its `file`, a short `alt` and the full image `prompt`. Chapter breaks (the torn sheets) come from `breaks` in `episode.json`: `tear-lemon`, `tear-paper` or `tear-black`.

## If something goes wrong

| What you see | What to do |
|---|---|
| The build says `S06 draws "…", which isn't in its card_text` | `reel.json` has a text that isn't in the episode. Copy it from `card_text` exactly. Never change `card_text` to make it fit |
| The check says FAIL on a card | Look at that shot in the reel. If the card is right, tell the person (it can be OCR); if it's wrong, fix `reel.json` |
| The voice check fails a line | Follow its "Fix:" line in the report. If "heard" is the same words as "should say", only spelled differently, the check misheard it: send it to the person. Never edit the audio, and never upload an unchanged file |
| The voice check says "trimmed" | Make the line again and save it exactly as the voice tool made it, silence included |
| A photo has writing in it | Make it again; add "absolutely no text" to the prompt |
| A placeholder says PHOTO P2 GOES HERE | That photo's file is missing or misnamed: check the path in Step 1 |
| The reel is longer than 95 s | Tell the person: the script needs to be shorter, so don't speed up the voice |
| The report says the script changed after it was approved | A line's words, the cover or the trial hook changed. Send the person the new script page and wait for their OK, then upload `script-approved.json` with the new version. Spelling a word differently in `tts`, or changing how a line is said, doesn't need a new approval |
| The person asks for a change after the voice is made | Make the change, send them the new script page, and after their OK upload `script-approved.json` with the new version. Then make the changed lines again: the report lists them |
| The report says `script-approved.json` isn't filled in right | Fix it as the report says: the version on the page the person approved, their name, the date and their words. If no person has approved the script, delete the file and send them the page |
| The report says the topic repeats a reel | Don't change the topic on your own. Tell the person which reel it repeats (TOPICS.md) and suggest 3 new topics. If the person decides it's different enough, they record that, and the next report shows it as a note |
| The report says a line, the hook, the cover or a photo repeats another reel's | Do what its "Fix:" line says: new words for the line, a new photo from a new prompt. Keep this reel's numbers and meaning |
| The report says a form isn't in `brand/epfo-forms.json` | Don't add it yourself. Tell the person which form the reel needs and link EPFO's page for it: they add it to `brand/epfo-forms.json` |
| The person asks you to post a reel that has a `posted.json` | It's already live. Don't post it again: send them the link in `posted.json` |
