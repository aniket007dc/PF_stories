# Step 09 · Final QA

| | |
|---|---|
| Goal | An independent last look before anything goes public |
| Who | A second person, not the one who approved step 08 |
| Reads | the exported reel · `episode.json` · `checks/` |
| Writes | `episodes/EP/checks/09-final-qa.md` |
| Checks | AUTO · HUMAN |
| Gate | `python3 tools/approve.py file EP 09-final-qa --file PATH --by NAME` |

## Do

1. Run every check and save the reports:

```bash
python3 tools/validate.py episodes/ep02-uan-activate --write
```

```bash
python3 tools/verify_media.py final episodes/ep02-uan-activate episodes/ep02-uan-activate/media/final/ep02.mp4 --write
```

2. Watch the reel twice, muted and with sound, against this list:

- [ ] Every number matches the data sheet, and every example says "maan lo" or EXAMPLE
- [ ] Captions are spelled right, in Roman Hinglish
- [ ] The end card has the PF Guru Ji logo, the FOLLOW @PFGURUJI button (it pops in on "Follow") and the disclaimer lines
- [ ] Nothing important in the top 220 px, the bottom 360 px or the right-hand buttons
- [ ] Voice clear on a phone speaker; music only felt; a sound on every landing
- [ ] Nothing that could embarrass a client or break a platform rule

3. Write what you checked in `checks/09-final-qa.md` and approve.

## Four eyes

If `brand/brand.json` lists two or more approvers, the tool refuses a final QA signed by the person who approved the assembly.
