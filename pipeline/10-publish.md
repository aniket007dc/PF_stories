# Step 10 · Publish

| | |
|---|---|
| Goal | The reel goes live with exactly the approved caption, cover and pinned comment |
| Who | A person approves; a person or a connector posts |
| Reads | `episode.json` → `post` |
| Writes | `posted.json` (Muse, right after posting) or `status.json` → `post` (URL and time) |
| Checks | HUMAN |
| Gate | Approve before posting, then record the post |

## Do

1. A person approves the post copy. This locks the caption: any edit afterwards needs a new approval.

```bash
python3 tools/approve.py step episodes/ep02-uan-activate 10-publish --by "Your Name"
```

2. **Never post a reel twice.** If the episode folder has a `posted.json`, or its check report says POSTED, it's already live: stop.
3. Post with the caption and hashtags from `post.caption`, the cover from A07 or the S01 frame, and turn on "Upload at highest quality". If Muse posts through a connector, its connector permission must be "Always ask".
4. Pin `post.pinned_comment`. Share the reel to your Story.
5. **Re-verify the live post:** the caption matches `post.caption` exactly, the cover reads well in the 3:4 grid crop, and the first frame isn't cut off.
6. Record it straight away. Muse uploads `episodes/<episode>/posted.json`:

```json
{"url": "https://www.instagram.com/reel/…/", "posted_on": "2026-11-20", "post_it_from": "Your Name"}
```

or a person runs:

```bash
python3 tools/approve.py posted episodes/ep02-uan-activate --url https://www.instagram.com/reel/… --by "Your Name"
```

From then on the check report says POSTED, `TOPICS.md` shows the link, and GitHub never rebuilds the reel (E11.7 checks the link).

## Optional test

Post `post.trial_hook` as a Trial Reel to non-followers first, and keep the hook that holds attention better.
