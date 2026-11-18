# PF Guru Ji logo

A claim form with its corner folded down, PF on it and a lemon tick (the claim goes through), over GURU JI on a lemon highlighter swipe, like every reel's end card. The letters are outlines, so the SVGs look the same in any app, with or without the fonts.

| File | Use it for |
|---|---|
| `pfguruji-avatar.png` | The Instagram profile picture: 1080 × 1080, lemon, and a round crop keeps all of it. Also WhatsApp and YouTube |
| `pfguruji-logo.png` · `.svg` | The main logo, on light backgrounds: the reels' end card, covers, posts, documents |
| `pfguruji-logo-on-dark.png` · `.svg` | The same, on dark or black backgrounds |
| `pfguruji-logo-horizontal.png` · `.svg` | Wide spaces: banners, page headers, a letterhead |
| `pfguruji-mark.png` · `.svg` | The mark alone, where the name is already there or the space is small: a watermark, an icon |

The PNGs are transparent (except the avatar) and large enough to shrink: the logo is 1600 px wide, the horizontal logo 2400 px and the mark 1024 px. Use the SVG wherever an app takes one, such as Canva or a printer.

## Rules

- Leave clear space around it, at least the height of the tick on every side.
- Don't stretch it, recolour it, add effects or redraw the letters. On a busy photo, put it on a paper or black panel first.
- Never put it next to, or mix it with, the EPFO logo or any government emblem: PF Guru Ji is not an official EPFO channel.

## Changing it

`tools/make_logo.py` draws the SVGs from the colours in `brand/brand.json` and the Anton font in `brand/fonts/`; `node tools/render_assets.js logo` renders the PNGs from them. The reels' end card uses the PNG named by `logo_file` in `brand/brand.json`.

```bash
python3 tools/make_logo.py
```

```bash
node tools/render_assets.js logo
```
