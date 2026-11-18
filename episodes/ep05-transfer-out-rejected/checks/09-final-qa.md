# Final QA · ep05-transfer-out-rejected

Checked by Divyank Sharma on 2026-11-17. Reel watched twice — muted and with sound.

File approved: `episodes/ep05-transfer-out-rejected/media/final/ep05-transfer-out-rejected.mp4`
(67.7 s, 1080x1920, 30 fps, loudness −14.74 LUFS)

## Checks run

- `tools/validate.py` — PASS (report: `checks/validate.md`).
- `tools/verify_media.py final` — every card read back exactly (report: `checks/media-final.md`).
- `tools/check_episode.py` — RESULT PASS, 2026-11-17 09:28 UTC (report: `checks/report.md`).
- Voice: 16/16 lines say every number and word (Whisper medium, checker's settings).

## Checklist

- Numbers match the data sheet: 94% (S03, direct_share) and 17% (S04, grievance_share) — heard in the voice and on the cards. No example/assumption numbers in this reel.
- Captions in Roman Hinglish, spelled as in the approved script (version cbed20).
- End card: PF Guru Ji logo, FOLLOW @PFGURUJI, "NIYAM: EPFO.GOV.IN", "EPFO KA OFFICIAL CHANNEL NAHI" — frame-checked clean.
- Voice: Bunty, clear; 5 lines at speed 1.0, 11 at 1.1. No music bed in this build (voice-only mix, loudness on target); music, if any, is added at posting.
- No personal details, no UAN, no portal screenshots (Divyank has no UAN/PF account). All facts/rules from EPFO's own pages or circulars only.
- Nothing in the reel identifies a client or breaks a platform rule.

## Note

brand.json lists a single approver (Divyank Sharma), so the four-eyes rule does not apply — the same person approved the assembly (step 08) and this final QA.
