# Brand fonts

`tools/build_reel.py` draws every word on screen with these files, so text is exact by construction, which no image or video model can promise. They match the reference reel's type: condensed numbers, mono labels, a bold grotesque for captions, a marker hand and a typewriter.

| File | Use | Has ₹ ≈ ÷ × · → |
|---|---|---|
| `Anton-Regular.ttf` | Big numbers, headlines, stamps, the header label | all (↗ ↘ are drawn as arrows) |
| `IBMPlexMono-SemiBold.ttf` | Black tabs, labels, the header tag | all, plus ↗ ↘ |
| `IBMPlexMono-Bold.ttf` / `IBMPlexMono-Medium.ttf` | Stamp subtitles, small print, the timecode | all, plus ↗ ↘ |
| `Archivo-Variable.ttf` | Karaoke captions (weight 800) | all |
| `Caveat-Variable.ttf` | Handwritten notes (weight 700) | all but → |
| `CourierPrime-Bold.ttf` / `CourierPrime-Regular.ttf` | Typewriter card | no ₹: the build falls back to IBM Plex Mono for it |

All are under the SIL Open Font License 1.1 (the `*-OFL.txt` files next to them), which allows using them in videos and keeping them in this repo.
