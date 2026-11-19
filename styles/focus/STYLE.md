# Focus · how to do it, on the screen itself

PF Guru Ji's how-to theme for one real EPFO task (`"style": "focus"` in `episode.json`): Mark Exit, a claim, a
transfer, KYC, the passbook, a nominee. The screen is the reel. One calm voice walks the viewer through it, click by
click, the way they'll do it themselves: every page opens on screen and is seen whole, the camera and the cursor (a
finger on a phone) travel across it to the part the line names, and the part being changed lifts out big and sharp
while the rest goes soft and dark, so the viewer always knows where they are and where to look.

The other theme is **Kahani**, the paper cut-out story (no `"style"`, or `"paper"`): a real situation told as a
story. Pick Focus when the reel is "how to do it on the portal"; Kahani when it's "what happened to Shivam".

- Example: [`ep00-focus-sample`](ep00-focus-sample/), "Exit date khali hai?": Mark Exit on the member portal. Its
  screens are a sample of the theme, drawn from what EPFO's pages have described: check them against the portal
  before reusing any of it in a real reel.
- Built by `tools/build_focus.py` on the Host engine of the dcvideo pipeline (`tools/build_host.py`), copied from
  [pr4dyuman/dcvideo](https://github.com/pr4dyuman/dcvideo) `styles/focus`. The screens are drawn by
  `tools/screens.py` from their description in `reel.json → screens`.

## Why draw the screens

Screenshots of the member portal show someone's account, so they need a person's login and covering every detail by
hand, and another creator's screenshot or video is theirs, not ours. So Muse reads EPFO's newest pages and the newest
videos of the task, and describes each screen the way the portal shows it today, part by part. The build draws it
clean, at two or three times the reel's size, so any zoom stays sharp, and it knows where every part is: the camera
can go to it, lift it out and tap it.

**Nobody's details, no logo.** A drawn screen shows only the cast's name (Shivam) and masked numbers, the way the
portal masks them (UAN `XXXX XXXX 1234`): the checks fail any full UAN, Aadhaar, mobile, PAN, bank account or member
ID on a screen (E4.28). The build draws no logos, so no screen carries the EPFO logo or the national emblem. An OTP
field shows `● ● ● ● ● ●`, never digits.

**Always the newest version.** Every screen names two sources at least, one of them EPFO's own (the member portal's
help, an FAQ, a circular, a PIB release, UMANG's EPFO help), each with the day it was read and the date it shows; one
of them must be from the last 60 days, and every one read in the last 30 (`brand/brand.json → styles → focus →
rules`: `source_days`, `seen_days`). EPFO's pages often refuse automated reading, so a person opens them in a browser.
The checks fail a screen without them (E4.23).

## The frame (1080 × 1920)

| Area | What's there |
|---|---|
| y 0 to 210 | Instagram's own top bar: background only |
| y 216 to 304 | the PF GURU JI wordmark, and the route's chips on the same row (MANAGE · MARK EXIT · OTP), each lighting up from the line where its step starts |
| y 316 to 1540 | **the screen**, as big as Instagram's buttons allow (on the hook, under the giant words, from y 660) |
| y 1560 to 1660 | the spoken words, one or two lines, left of Instagram's buttons; the highlighted words in lemon |
| x 930 to 1080, y 1100 to 1660 | Instagram's like, comment and share buttons: nothing that matters goes there, and no tap lands there |
| y 1660 to 1920 | Instagram's name, caption and audio: background only |

## What happens on the screen

| Part | What it does | Who makes it |
|---|---|---|
| **The screen** | A page that opens is shown whole for a second; then the camera moves in to each part as its line names it | Muse describes it (reel.json → screens); the build draws it |
| **The walk** | The steps start on the page the viewer sees first when they log in, and every page after it opens on screen: a click on a menu item, tab, link or button that goes there. Nothing jumps to a page nobody opened (E4.27) | Muse: `"go"` on the tap that opens each page |
| **Focus** | The camera travels to the part with a lemon ring round it; then a part that changes (typed words, a tick, a status) lifts out on a white card while the rest blurs and dims | The build, from each line's `focus` and touches |
| **The touch** | The cursor (laptop) or a finger (phone) travels to the part and taps beside its words, with a ripple; each new page is seen for a second and each change for half a second | Muse: `"do"` actions on their words; the build times them |
| **The screen answers** | A menu opens, a row picked in a list lights up with a tick, words type themselves, a status turns green, a message pops up | Muse: `open`, `close`, `show`, `toggle`, `write`, `label` … |
| **Route** | Before the first step: the whole path in 3 to 5 stops | Muse: `route` card, and `route` chips |
| **Flow** | What happens behind the screen: who sends what to EPFO, and the result: the mistake in red, then the fix in green | Muse: `flow` card |
| **Checklist** | The list worth a screenshot, ticked in item by item | Muse: `checklist` card |
| **The hook** | The hook's words in giant letters over the screen's first look, the end of them on a lemon block | Muse: `headline` card |

## The story

Real tasks, not three easy steps: 6 to 12 steps, the order, and the catch. 100 to 220 words, 40 to 120 seconds.

hook → why → route → steps (one line per action, each naming the button as the portal writes it) → mistake → fix →
check → list → share → signoff

The steps start where the viewer starts (the page they see after logging in) and say every click that opens the next
page, in order ("Upar Manage pe click karo, phir Mark Exit."). The script is written from the newest pages
(`brand/prompts/focus-script-writer.txt`: research.md → Steps on screen), and the shot prompt describes the screens
and what happens on them (`brand/prompts/focus-reel-writer.txt`). The voice is the series voice, one narrator.

## Checks

- **E4.20:** the first frame shows the hook's words in a headline (6 words at most), with the screen under it.
- **E4.22:** every screen can be drawn: known part kinds, icons and overlays, each id once.
- **E4.23:** two sources or more per screen, one official, every one with its link and the day it was read (in the
  last 30 days), one dated in the last 60. A sample in `styles/` and a posted reel don't go stale.
- **E4.24:** every card is a Focus card; every part, overlay and screen a line uses exists; every `on` word is in its
  line.
- **E4.25:** the route's chips: 5 at most, short, each starting on a real shot.
- **E4.27:** the walk is shown: a line never opens on a page the viewer wasn't taken to on screen, and a menu item
  that's clicked goes to its page.
- **E4.28:** no screen shows a person's number in full (UAN, Aadhaar, mobile, PAN, bank account, member ID).
- The build's own layout check: a part too small to read even lifted, a tap under Instagram's buttons, touches too
  close together, or a touch that comes before its page has been seen.
- The reel check reads every card back, lets the screen's own words be (they aren't cards), and listens for every
  shot's voice.
