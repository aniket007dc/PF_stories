# Kem Cho Club · Taali

Gujarati taught on a garba beat, in rhyme, for the Kem Cho Club Instagram account. This folder is self-contained: its own tools, font, account profile, style guide and sample reel. It is separate from the rest of this repo (PF Guru Ji) and shares nothing with it.

- **The style guide:** [`styles/taali/STYLE.md`](styles/taali/STYLE.md) covers the idea, the cast (Sawaj the Gir lion on the dhol, Lali the Kutch flamingo with her dandiya), the music, the lesson file and the rules.
- **The sample:** [`styles/taali/ep00-taali-sample`](styles/taali/ep00-taali-sample), *Tame, Ame, Mane Game!* (6 words, 2 rhymes, 52 s). The reel is in `media/final/`, the cue sheet in `build/lyrics.md` and the voice sheet in `build/voice.md`.
- **The account:** [`clients/kem-cho-club/client.json`](clients/kem-cho-club/client.json), including the two voices (`cast`).
- **A new lesson:** [`brand/prompts/taali-lesson-writer.txt`](brand/prompts/taali-lesson-writer.txt).

## Setup (once per computer)

You need Python 3.9 or newer and ffmpeg. Then, from inside `kem-cho-club/`:

```bash
pip install -r requirements.txt
```

## Commands (run from inside `kem-cho-club/`)

```bash
python3 tools/build_taali.py styles/taali/ep00-taali-sample --check
```

```bash
python3 tools/build_taali.py styles/taali/ep00-taali-sample
```

The first checks the lesson and writes the voice sheet; the second builds the reel (1 to 3 minutes).

## Paste this into Muse: the vocals

```
You make the vocals for a Kem Cho Club reel. Your GitHub connection gives you the repo aniket007dc/PF_stories (branch main). Everything for this job is in its kem-cho-club/ folder, which is separate from the rest of that repo: never change anything outside kem-cho-club/. Read kem-cho-club/README.md and kem-cho-club/styles/taali/STYLE.md first.

Set up your computer: download the repo, make sure python3 (3.9 or newer) and ffmpeg are installed, then, inside the kem-cho-club folder, run: pip install -r requirements.txt
Run every command below from inside the kem-cho-club folder. The episode is styles/taali/ep00-taali-sample.

You make the voice on elevenlabs.io, in your browser, logged in to our account. If it asks you to log in, stop and tell me: never log in to another account.

Step 1 · Pick the two voices. On elevenlabs.io → Voice Library, filter by language Hindi, and choose:
- Sawaj (the lion cub, on the dhol): a young male voice, warm, cheerful and full of energy, that can sound sing-song.
- Lali (the flamingo, with her dandiya): a young female voice, bright, playful and quick.
Add both to My Voices. Write each voice's voice_id and voice_name (exactly as the Voice Library shows it) into clients/kem-cho-club/client.json → cast → sawaj and cast → lali. Change nothing else in that file. Tell me the two names, with a link to each voice's preview, and wait for my OK.

Step 2 · The voice sheet. Run: python3 tools/build_taali.py styles/taali/ep00-taali-sample --check
It writes styles/taali/ep00-taali-sample/build/voice.md: every take to make, in whose voice, the exact text to paste and the file name to save it as.

Step 3 · Make every take on voice.md. For each row:
1. elevenlabs.io → Text to Speech. Model: Eleven v3. Voice: the row's voice. Speed and stability: as the table at the top of voice.md says.
2. Paste the row's text exactly, tags included. Never press Enhance, and never add or change a word or tag.
3. Generate and listen. It must sound sung and bouncy, like a garba chant, not read out. Every Gujarati word must be clear and said the Gujarati way: tame (tuh-MAY), ame (uh-MAY), game (guh-MAY, never the English "game"), mane (muh-NAY), maaru (MAA-roo), taaru (TAA-roo), saaru (SAA-roo), badhu (buh-DHOO), kem cho, aavjo (AAV-joh), tamaro vaaro. No tag may be said out loud, and nothing may be cut off. Make up to 3 takes and keep the best.
4. If a Gujarati word still comes out wrong after 3 takes, give that line a "tts" in styles/taali/ep00-taali-sample/episode.json: the same words, with the wrong word written in Gujarati script (game → ગમે, tame → તમે) or spelled how it sounds (gamay). Run the --check from step 2 again (voice.md then shows the new text) and make that line again. Never change "say": it's what the screen shows.
5. Download the take as MP3 and save it in styles/taali/ep00-taali-sample/media/audio/lines/ under the row's "Save as" name exactly (L01.mp3, L08.sawaj.mp3 …). A "both" line is two takes, one in each voice. Never trim, join, speed up or edit a file in any way: the build lines every take up on its beat itself.
When all are made, run the --check again: every row of voice.md must say "yes".

Step 4 · Build the reel. Run: python3 tools/build_taali.py styles/taali/ep00-taali-sample
Watch styles/taali/ep00-taali-sample/media/final/ep00-taali-sample.mp4 from start to end, with sound. Each line starts on its beat, the highlighted word follows the voice, the two voices of a "both" line sing together, and the music stays under the voice. The build prints RUSHED for any line it had to speed up a lot: make that line again with speed 1.2 and build again. Tell me what you see and hear, and wait for my OK.

Step 5 · Upload. Upload these files, one per call, to the same paths in aniket007dc/PF_stories on main (every path starts with kem-cho-club/): kem-cho-club/clients/kem-cho-club/client.json; kem-cho-club/styles/taali/ep00-taali-sample/episode.json (only if you changed it); every file in kem-cho-club/styles/taali/ep00-taali-sample/media/audio/lines/; and from kem-cho-club/styles/taali/ep00-taali-sample: media/final/ep00-taali-sample.mp4, media/final/cover.jpg, media/audio/beat.m4a, build/lyrics.md, build/voice.md, checks/storyboard.jpg. Never upload anything in kem-cho-club/tools/ or outside kem-cho-club/, and never put a key or password in any file.

After each step, tell me exactly what you made and where you saved it, then wait for my OK before the next step. Never post anything to Instagram until I write "post it".
```
