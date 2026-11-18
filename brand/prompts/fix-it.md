# Fix-it prompts

Send one of these in the same Muse chat when a result breaks a rule. Two tries per shot, then use the clean-plate route.

## Wrong digits

```text
Some numbers are wrong. Redo it with exactly these characters: ₹15,000 (rupee sign, 1, 5, comma, 0, 0, 0). Change nothing else.
```

## The paper changed

```text
The background changed. Keep the attached paper exactly as it is and only add the cards I described.
```

## The camera moves

```text
Remove all camera movement. Lock the camera; only the paper cards move.
```

## Text warps in the video

```text
The text is warping while things move. Treat every card as a rigid printed object: its letters must not change shape in any frame.
```

## Too glossy or 3D

```text
Make it look like flat matte paper under soft daylight: no gloss, no reflections, no 3D bevels, no glow.
```

## Extra words appeared

```text
Remove every word except these: [list the exact words]. No other text anywhere in the image.
```

