# Step 02 · Data and sources

| | |
|---|---|
| Goal | Every number the reel will say or show, and every EPFO rule or step it relies on, each with an official source, a formula or an example label |
| Who | Muse researches and drafts · a person checks every fact's and rule's source |
| Reads | `episode.json` → `brief` · `templates/data-item-examples.json` · `brand/epfo-forms.json` |
| Writes | `episode.json` → `data` · `02-data` set to `drafted` |
| Checks | AUTO · SELF · HUMAN |
| Gate | Every fact and rule checked, then `python3 tools/approve.py step EP 02-data --by NAME` |

## The six kinds of data

| Kind | Use it for | Must have |
|---|---|---|
| `input` | The episode's premise, a number we choose | `note` |
| `fact` | A number EPFO (or the law) publishes: a limit, a time, a rate | `source`, `source_url`, `check_note`; a person fills `checked_by` and `checked_on` |
| `rule` | An EPFO rule or step without a number: what a menu does, who approves what, why a claim comes back | `statement` (the rule in one plain sentence), `source`, `source_url`, `check_note`; a person fills `checked_by` and `checked_on` |
| `assumption` | An example value, like a PF balance | `note` saying where the real number will come from. It must be labelled "maan lo" or EXAMPLE where it first appears |
| `derived` | Anything calculated | `formula` using data ids with `+ - * /` only. The checks recalculate it |
| `advice` | Our recommendation | `reason` |

Units: `INR`, `%`, `count`, `days`, `months`, `years`, `minutes`, `seconds`, `x`. Store percentages as fractions: 10% is `0.10`. A `rule` has no unit or value.

Sources are EPFO's own: epfo.gov.in (old epfindia.gov.in links redirect there) and its circulars, the member portal's help pages, the EPF Scheme, the Gazette of India, and PIB press releases. A news article, a blog or a video is never the source, only a pointer to one. Rules change: link the newest official page, and say its date in `check_note`.

Rules that changed recently (November 2026). Older pages and videos still give the old ones, so check each against its source before a reel uses it:

- The EPF Scheme, 2026 and the EPS, 2026 replaced the EPF Scheme, 1952 and the EPS, 1995 from 29 June 2026 ([G.S.R. 525(E)](https://egazette.gov.in/WriteReadData/2026/273957.pdf), [G.S.R. 527(E)](https://egazette.gov.in/WriteReadData/2026/273951.pdf)). The old paragraph numbers (such as 69 and 72(7)) no longer apply.
- Taking the whole PF after leaving a job needs 12 months without a job (it was 2), and the pension withdrawal benefit 36 months after the last contribution fell due (it was 2): EPF Scheme 2026 para 49(2), EPS 2026 para 13(1).
- The Income-tax Act, 2025 took effect on 1 April 2026 and renumbered the TDS sections (192A is now 392(7)); Form 121 replaced Forms 15G and 15H.
- A UAN is activated only in the UMANG app, with Aadhaar face authentication; the member portal no longer activates UANs.
- Bank KYC needs no cheque or passbook upload and no employer approval since April 2025 ([PIB](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2118168)).

Form names (Form 19, Form 10C) aren't data: a reel may name only the forms in `brand/epfo-forms.json`.

## Prompt for Muse

```text
For this brief, list every number the reel will need, and every EPFO rule or step it relies on, as JSON data items.
Kinds: input (the episode's premise); fact (a number EPFO or the law publishes: give "source", "source_url" and "check_note" saying what a person must look at; never use a fact you can't link to an official page); rule (an EPFO rule or step without a number: give "statement", "source", "source_url" and "check_note"); assumption (an example value: give "note" saying where the real number will come from); derived (give "formula" using other ids with + - * / only); advice (give "reason").
Units: INR, %, count, days, months, years, minutes, seconds, x. Store percentages as fractions (10% is 0.10). Ids are lowercase with underscores. A rule has no unit or value.
Sources: EPFO's own pages, circulars and notifications only. Never a news site, blog or video.
Brief: [paste the brief JSON]
Then re-verify: open every source_url again and quote the exact sentence that contains the number or the rule. If you can't find it, take the item out and say so.
Reply with JSON only: {"data": [...]}, then the quotes.
```

## Checks

| ID | Check | Who |
|---|---|---|
| E2.1 | Ids, kinds, units and values are valid; every rule has a statement | AUTO |
| E2.2 | Every derived value equals its formula | AUTO |
| E2.3 | Every fact and rule has a source and link, and a person checked it | AUTO + HUMAN |
| E2.4, E2.5 | Assumptions say where the real number comes from; advice gives a reason | AUTO |
| — | Muse quoted the sentence behind each fact and rule | SELF |

## Re-verify (a person, for every fact and rule)

Open the link, find the number or the rule, then record it:

```bash
python3 tools/approve.py fact episodes/ep02-uan-activate <data id> --by "Your Name" --note "What you saw, on which official page, and its date"
```

## If it fails

A fact or rule without a working official source comes out of the reel. A formula that doesn't match means one of the inputs is wrong: fix the input, not the formula.
