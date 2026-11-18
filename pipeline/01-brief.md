# Step 01 · Brief

| | |
|---|---|
| Goal | One clear angle: the viewer's exact EPFO problem, why it happens, the steps that fix it, the one thing to check before filing, where to get help, and one kind of friend to send it to |
| Who | Muse drafts · a person approves |
| Reads | `TOPICS.md` (every reel made so far: a new one never repeats them), `brand/brand.json`, `brand/epfo-forms.json`, the topic bank below, EPFO's own pages (epfo.gov.in and the member portal) |
| Writes | `episode.json` → `brief` · `status.json` → `01-brief` set to `drafted` |
| Checks | AUTO · HUMAN |
| Gate | `python3 tools/approve.py step EP 01-brief --by NAME` |

## Do

1. A person starts the episode:

```bash
python3 tools/new_episode.py ep02 uan-activate "UAN activate kaise karein?"
```

2. Send Muse the prompt below and paste its JSON into `brief` in the new `episode.json`.
3. Set `01-brief` to `drafted` in `status.json`, then run `python3 tools/validate.py episodes/ep02-uan-activate`.

| Field | What goes in |
|---|---|
| `topic` | The episode question, in Hinglish. It must not repeat a reel in `TOPICS.md` |
| `repeat_check` | `closest`: the folder name of the reel in `TOPICS.md` nearest to this one; `different_because`: one sentence on how this one's question, steps or viewer differ. Needed once any reel exists |
| `viewer` | Who it is for, in one sentence |
| `hook` | The first line: the viewer's situation or the message they saw, in their words |
| `problem` | What goes wrong and what it costs the viewer, in one sentence |
| `why` | 1 to 3 reasons it happens, most common first, each one EPFO itself gives |
| `steps` | 2 to 5 steps that fix it, in the order the viewer does them |
| `check` | The one thing to check before filing (again) |
| `help` | Where to go if it's still stuck: an official channel only |
| `share_target` | The kind of friend to send it to |
| `why_now` | Why this week (optional) |

## Prompt for Muse

```text
Read TOPICS.md in the repo (every reel we've made), brand/epfo-forms.json, this topic, and EPFO's own pages on it (epfo.gov.in, the member portal's help pages, EPFO circulars). Propose 3 angles for one PF Guru Ji reel and recommend one. Never propose an angle that repeats a reel in TOPICS.md, even with other words.
Topic: [TOPIC]
For each angle give: a hook of at most 10 words in the viewer's own words; the problem and what it costs them; 1 to 3 reasons (only ones EPFO itself gives); 2 to 5 steps that fix it, in order; the one thing to check before filing; where to get help (official channels only); and who to send it to ("… dost ko abhi bhejo").
Every rule, limit, time or number you mention needs an official source I can check (name and link). Don't invent anything, and never ask viewers for personal details.
Reply with the recommended angle as JSON only:
{"topic": "", "repeat_check": {"closest": "", "different_because": ""}, "viewer": "", "hook": "", "problem": "", "why": [""], "steps": ["", ""], "check": "", "help": "", "share_target": "", "why_now": ""}
```

## Topic bank

Questions PF members ask. Each one still needs its facts from EPFO's own pages before it becomes a reel, and `TOPICS.md` says which are made.

- Claim reject kyun hota hai, aur kaise theek karein?
- UAN activate kaise karein?
- KYC mein bank account kaise jodein?
- Naam ya date of birth galat hai: kaise theek karein?
- Naukri chhodi: exit date kaun daalta hai?
- Kaunsa form kab: final settlement, pension, advance?
- PF se advance kis kaam ke liye mil sakta hai?
- Purani company ka PF nayi mein kaise transfer karein?
- Pension (EPS) ka paisa kab mil sakta hai?
- Claim status kaise dekhein?
- PF nikalne pe TDS kab katta hai?
- Nominee kaise jodein?
- Member nahi rahe: family claim kaise kare?
- Claim atka hai: shikayat kahan karein?
- Passbook mein balance kaise dekhein?

## Checks

| ID | Check | Who |
|---|---|---|
| E1.1 | Every field filled | AUTO |
| E1.2 | `why` lists 1 to 3 reasons and `steps` 2 to 5 steps | AUTO |
| E11.1 | The topic doesn't repeat a reel in `TOPICS.md` (a close one is a note) | AUTO |
| E11.2 | The hook isn't the same line as another reel's hook, first line or cover | AUTO |
| E11.5 | The folder is `episodes/<id>-<slug>` and no other folder has its number | AUTO |
| E11.6 | `repeat_check` names a reel in `TOPICS.md` (the nearest one the check finds) and says how this one is different | AUTO |
| — | Is it really a new question for our viewers, not an old reel in new words? | HUMAN |
| — | Useful to a PF member this week? Does every reason and step come from EPFO's own pages? Could any of it send someone to the wrong form, or to an agent? | HUMAN |

## If it fails

Ask Muse for the next angle, or write the brief yourself. Don't move on with a vague hook: every later step is built on it.

If E11 flags a repeat that a person decides is fine (a deliberate part 2, say), they record it, and it lapses if the topic changes:

```bash
python3 tools/approve.py repeat-ok episodes/ep02-uan-activate ep01 topic --by "Your Name" --note "Part 2 on purpose: the follow-up question"
```
