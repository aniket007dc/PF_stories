# Voices

`tools/make_voice.py` makes every voice line with **F5-Hindi**, a voice model trained on native speakers' Hindi, in
the voice and manner of one of these reference clips. Each clip's words are in the `.txt` file next to it: the model
needs them, so never change one without the other.

| File | Reads | Speaker | Rasa clip |
|---|---|---|---|
| `narrator.wav` | the narrator, Shivam and the other men | Rasa's Hindi male speaker (`hi_M`), conversational | `843cf1d0af449a52e5701c6a76b17d7a1f2a1e67fbc7e9aa9cc3457fcda4ac81` |
| `priya.wav` | Priya and the other women | Rasa's Hindi female speaker (`hi_F`), conversational | `965b58389d3e51fad4dc06a987d47714a6d9c980abbcc7c41c7622c8d0e7cbb3` |

A good reference clip is 6–10 s of one person speaking naturally and brightly, with nothing else in it. Keep a
series on the same clips, so the narrator and Priya sound the same in every reel.

## Credits

Both are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), which allows using them in reels, also
commercially, as long as they're credited. Keep this with anything published.

- **Voice clips:** AI4Bharat's Rasa dataset ([ai4bharat/Rasa](https://huggingface.co/datasets/ai4bharat/Rasa)),
  CC BY 4.0. Praveen Srinivasa Varadhan, Ashwin Sankar, Giri Raju and Mitesh M. Khapra, *Rasa: Building Expressive
  Speech Synthesis Systems for Indian Languages in Low-resource Settings*, INTERSPEECH 2024. Taken from the 24 kHz
  copy in [sulabhkatiyar/indic-tts-mini-24k](https://huggingface.co/datasets/sulabhkatiyar/indic-tts-mini-24k) and
  saved here as 16-bit WAV, otherwise unchanged. No endorsement by AI4Bharat is implied.
- **Voice model:** [SPRINGLab/F5-Hindi-24KHz](https://huggingface.co/SPRINGLab/F5-Hindi-24KHz), SPRING Lab, IIT
  Madras, CC BY 4.0, used unchanged. It runs on [F5-TTS](https://github.com/SWivid/F5-TTS) (MIT) with the Vocos
  vocoder [charactr/vocos-mel-24khz](https://huggingface.co/charactr/vocos-mel-24khz) (MIT).

The credit line at the end of a caption, before the hashtags (no "4.0": the caption check would read it as a
number the episode has no source for):

> Awaaz: AI voice, F5-Hindi model (SPRING Lab, IIT Madras) aur AI4Bharat Rasa voice clips se. Licence: CC BY.
