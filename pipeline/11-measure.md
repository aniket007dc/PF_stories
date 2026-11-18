# Step 11 · Measure

| | |
|---|---|
| Goal | Learn what worked, and feed it into the next brief |
| Who | Anyone on the team |
| Reads | Instagram Insights for the reel |
| Writes | `status.json` → `metrics` |
| Gate | The 7-day numbers are recorded (the step then passes by itself) |

## Do

At 24 hours, 72 hours and 7 days, record what Insights shows:

```bash
python3 tools/approve.py metrics episodes/ep02-uan-activate 24h reach=1800 views=2600 skip_rate=0.41 avg_watch_s=21 shares=46 saves=31 follows=9 comments=12
```

| Number | What it tells you |
|---|---|
| `skip_rate`, `avg_watch_s` | Is the hook working? Does the middle hold? |
| `shares` ÷ `reach` | Is the share line working? |
| `saves` | Are the steps useful enough to keep? |
| `follows`, comments asking for help | Is the channel earning trust? |

Compare each reel with your own average, not with other accounts. After five episodes, keep the hook pattern with the best hold and the share line with the most sends, and cut whatever chapter loses people. Write the lesson in the next episode's brief under `why_now`.
