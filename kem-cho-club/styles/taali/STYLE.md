# Taali · Gujarati on a garba beat

A new style, with its own look, cast, music and engine (`"style": "taali"`), made for **Kem Cho Club** (`clients/kem-cho-club`), the account that teaches Gujarati. *Taali* is the clap of garba, and the reel is a song: every word is taught on the beat, in rhyme, so it sticks the way a song sticks.

- Example: [`ep00-taali-sample`](ep00-taali-sample/media/final/ep00-taali-sample.mp4), *Tame, Ame, Mane Game!* (6 words, 2 rhymes, 52 s). Its cue sheet is [`build/lyrics.md`](ep00-taali-sample/build/lyrics.md), and its backing track is `media/audio/beat.m4a`.
- Built by `tools/build_taali.py`, which shares nothing with the other styles' engines. The music is made by `tools/taali_music.py` and the cast is drawn by `tools/taali_cast.py`.

```bash
python3 tools/build_taali.py styles/taali/ep00-taali-sample --check
```

```bash
python3 tools/build_taali.py styles/taali/ep00-taali-sample
```

Run every command from inside the `kem-cho-club/` folder: it is a self-contained copy, separate from the rest of this repo.

## The idea

A language reel works when the viewer **sings it back** without trying. So every reel is a tiny garba song:

1. **Sawaj sings the Gujarati word**: "Tame, tame, bolo TAME!" The card shows `તમે`, `TAME`, and `= ?`.
2. **Lali sings back what it means**: "Tame matlab AAP!" The `= ?` flips to `= AAP · YOU`, and a diya lights up at the top.
3. **The words rhyme**: tame, ame, game; maaru, taaru, saaru. The rhyming ending is in its group's colour in both scripts (ત**મે**, T**AME**), with a squiggle under it, so the eye sees the rhyme the ear hears.
4. **The chorus** puts them together: "Maaru, taaru, badhu saaru! Tame, ame, mane game!"
5. **Tamaro vaaro (your turn)**: the last word of each rhyme is a blank (`ગ__`, `mane ___`). The singers stop on the beat and the viewer fills it in, then the answer pops in. Then a comment question: *Tamne shu game?*
6. **Aavjo!**: the sign-off, and the follow.

## The cast

Both are drawn in code, so they look the same in every reel and cost nothing: `python3 tools/taali_cast.py sheet.png` draws a sheet of them.

| | Who | Gujarat's symbol | What they do |
|---|---|---|---|
| **Sawaj** (સાવજ, Kathiyawadi for lion) | A Gir lion cub: golden, with a big mane, a red **bandhani pagdi** with a mirror and a turra plume, and a white **kediyu** | The Asiatic lion of Gir, found nowhere else on earth | Plays the **dhol**: his sticks land on the dhol hits of the track. Sings the Gujarati word. Sways his head on every beat, and does a garba step |
| **Lali** (લાલી) | A flamingo in a green **chaniya** with a red hem and mirror-work, a red choli, a tikka and a bindi | The greater flamingo, Gujarat's state bird, from the Rann of Kutch ("Flamingo City") | Plays the **dandiya**: her sticks meet on every dandiya click of the track. Sings the meaning. Does garba steps, and twirls on the rhyme and chorus lines |

On stage they are joined by the **garbo** (the clay pot with a lamp inside that garba is named after) burning between them, a circle of dancers' silhouettes going round it, a **rangoli** on the floor, a **toran** of flags and mango leaves along the top, and string lights that chase on the beat.

The singer of each line gets a spotlight and their name above the words (SAWAJ, LALI, or BANNE, meaning both). Mouths open on every syllable; both of them blink. At the very end, both shut their eyes in a happy smile.

## The music

A fast **garba / dandiya groove made entirely in code** (`tools/taali_music.py`): no sample, no loop and no licence, so no Instagram music claim, and every reel's track is exactly as long as its song.

| Part | Sound |
|---|---|
| **Dhol** | The bass head (a deep, pitch-falling thump) on the dandiya *chal* (steps 1, 7, 9, 12, 15 of 16), and the treble head's cane crack between them. A dhol fill leads into every new part |
| **Dandiya** | Two wooden sticks knocking on the off-beats: what the dancers step to |
| **Manjira** | Small brass cymbals on every eighth note, opening up in the chorus |
| **Taali** | Claps on 2 and 4 in the chorus and the viewer's turn |
| **Harmonium** | A folk riff in **Khamaj** (Sa Re Ga Ma Pa Dha komal-Ni), the scale of a lot of Gujarati folk, with a Sa-Pa drone that dips under each dhol hit (the "pump" of dance music) |
| **Bansuri** | A flute doubling the riff an octave up in the chorus |
| **Ghanti** | A small temple bell each time a new word appears |

**Tempo:** 128 BPM by default (116–140 allowed), so one bar is 1.875 s. That's fast enough to dance to and slow enough for a learner to sing a word with the beat. **Key:** D by default (`lesson.key`).

The song's parts set the arrangement: `intro` (a harmonium swell, a bell, then a dhol roll), `verse` (the full groove, with the riff kept soft under the words), `chorus` and `turn` (claps, sub bass, bansuri, open manjira, marigold petals falling), and `outro` (three big hits together, then everything rings out).

## The voice

The words are sung or chanted **on the grid**: each line starts on its first beat and lasts its bars. There are three ways to voice a reel, from best to quickest:

1. **A real singer** (best: it's what makes folk feel folk). Give them `media/audio/beat.m4a` and `build/lyrics.md` (every line, who sings it, its bar and its second). They record one file per line, `media/audio/lines/L01.wav` …, starting on the line's first beat, and two voices (a deeper, cheerful one for Sawaj, a bright one for Lali) make the call and answer.
2. **ElevenLabs** (`tools/taali_voice.py`). It makes every line in its singer's own voice: Sawaj's lines in his, Lali's in hers, and "both" lines in both voices, lined up and mixed. It uses Eleven v3, with tags in front of each line (`[cheerful] [sing-song, on the beat]`) so the lines come out sung and bouncy, not read. It also asks ElevenLabs for each word's timing, so the build puts the first word exactly on the line's first beat, and the captions and mouths follow the real voice. A line that runs past its bars is sped up a little (at most 1.6×), and the music dips under every line. Only new or changed lines cost credits.
   - **Set up once:** pick two voices on elevenlabs.io → Voice Library: a warm, cheerful male voice for Sawaj and a bright female voice for Lali. Hindi voices handle the Hinglish best; to list some, run `python3 tools/taali_voice.py --find-voices hi --gender male` (or `female`). Add them to your account, and put their `voice_id`s in `clients/kem-cho-club/client.json` → `cast`. The tags, speed and stability live there too.
   - **On elevenlabs.io, by hand (Muse's way):** `build/voice.md` (written by every build, and by `--check`) lists every take: the voice, the exact text to paste (tags included) and the file name. A *both* line is two takes, `L08.sawaj.mp3` and `L08.lali.mp3`; the build finds where each take's first sound starts, lines them up on the beat and mixes them. After the build, a line marked **RUSHED** had to be sped up more than 1.25× to fit: make it again a little faster, or give it another bar.
   - **Through the API:** on any computer with an ElevenLabs key in the environment (`ELEVENLABS_API_KEY`), run `python3 tools/taali_voice.py <episode>` and then `python3 tools/build_taali.py <episode>`. Add `--dry-run` first to see the lines and the credits they'll take.
   - **A truer accent:** give a line `"tts"` with the words to send instead of what's on screen, for example the Gujarati script (`"tts": "તમે, તમે, બોલો તમે!"`). Give it `"tags"` to change how that one line is sung.
3. **No voice yet.** The reel still builds, with the music and the sing-along captions (the words light up one by one and a mirror bounces from word to word), as the sample does.

## The lesson file

A Taali episode's `episode.json` has a `lesson`. The build reads only this, so every word on screen comes from it.

| Field | What it is |
|---|---|
| `bpm`, `key` | The tempo (116–140) and the key (C to B) |
| `hook` | The first words on screen, 6 at most: "Gujarati seekho, taal pe!" |
| `title_gu`, `title` | The reel's title in Gujarati and in Roman: "તમે, અમે, મને ગમે!" |
| `rhymes` | The rhyme groups: `{"a": {"tail": "ame", "tail_gu": "મે", "color": "teal"}}` (colours: teal, pink, green, blue, orange, purple) |
| `words` | 4 to 8 words: `{"id": "W1", "gu": "તમે", "roman": "tame", "meaning": "aap", "en": "you", "rhyme": "a"}` |
| `turn`, `ask`, `bye` | The your-turn card, the comment question and the sign-off: each `{gu, roman, meaning}` |
| `lines` | The song, in order. Each line has an `id`, a `part` (intro, verse, chorus, turn or outro), `who` (sawaj, lali or both), `bars` (1 by default), `show` (what the card shows), `say` (the words sung) and, optionally, `on` (the beat each word lands on, counted from the line's start: `[0, 1, 2.5]`) |

**What a line can show:**

| Show | The card |
|---|---|
| `title` | The hook card: the title in both scripts and the hook |
| `word` | One word, big: Gujarati, Roman, and `= ?` (with `"word": "W1"`) |
| `meaning` | The same word, with its meaning and English: `= AAP · YOU` |
| `rhyme` | A rhyme group side by side; the word being sung lights up (`"rows": [["W1", "W2", "W3"]]`) |
| `chorus` | Two or more rhyme groups, a row each |
| `turn` | The your-turn card (`lesson.turn`) |
| `blank` | A rhyme group with its last word's rhyme left as a blank, then filled in on beat `reveal` (`"answer": "game"`). Write the blank in `say` as `___` |
| `ask` | The comment question (`lesson.ask`) |
| `bye` | The sign-off (`lesson.bye`), with the account's handle |

## Rules (the build checks them: `--check`)

- **Every taught word rhymes.** Each word belongs to a rhyme group of 2 or more, and ends in its group's rhyme in both Roman (`tail`) and Gujarati (`tail_gu`). The Gujarati rhyme is a whole syllable (`મે`, `રું`), never a lone vowel sign.
- **Word, then meaning.** Every word is sung (`show: word`), and then explained (`show: meaning`).
- **4 to 8 words per reel.** Fewer is a tease, and more won't be remembered.
- **Singable.** At most 2 words per beat. If `on` is given, it has one beat per word, going up, inside the line.
- **The shape.** The first line is the `title`, and the last is the sign-off (`bye`). A reel is 20 to 75 seconds; most land at 45 to 55 (about 24 to 30 bars at 128 BPM).
- **No dashes on screen,** as in every style.

A shape that works (the sample's):

| Part | Bars | What happens |
|---|---|---|
| intro | 2 | Hook: "Kem cho dosto! Gujarati seekho, taal pe, taali pe!" |
| verse | 8 | Rhyme group A: word/meaning × 3, then the group sung together, and its meanings together |
| verse | 8 | Rhyme group B, the same way |
| chorus | 4 | Both groups, twice, with everyone singing |
| turn | 4 | "Have tamaro vaaro!", two blanks for the viewer, then the comment question |
| outro | 2 | "Aavjo!" and the follow |

## Writing a lesson

Muse or a writer uses `brand/prompts/taali-lesson-writer.txt`: give it the theme (greetings, food, family, numbers, the market, Navratri…) and it returns the `lesson` block. Good themes have **natural rhymes** in Gujarati. Some to start from:

- **Pronouns and liking:** tame / ame / game (you, we, like) · maaru / taaru / saaru (mine, yours, good)
- **Questions:** kem / jem / tem (how, as, so) · shu / tu / hu (what, you, I)
- **Slang:** haalo / chaalo (let's go, come on)

A theme with no natural rhyme (food, family, numbers) still works: teach a phrase whose last word rhymes (*mane bhaave*, *tane bhaave*: I like it, you like it, to eat). The check refuses a word that doesn't rhyme.

## What would make it better still

- **A sung voice for each character,** from one singer or a licensed AI voice, so Sawaj and Lali sound the same in every reel.
- **More melodies.** `taali_music.py` has one verse riff and one chorus riff. A few more, picked per reel, would keep the series fresh; a *hinch* (6/8, slower) groove would suit gentler lessons.
- **Festival specials:** kites for Uttarayan (14 January), diyas for Diwali, and the Rann Utsav's white desert under a full moon as a second stage.

The prompt to give Muse is in `kem-cho-club/README.md`.
