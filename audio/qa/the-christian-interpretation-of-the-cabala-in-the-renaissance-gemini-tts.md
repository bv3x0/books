# Gemini TTS Generation QA: The Christian Interpretation of the Cabala in the Renaissance

- source render: `audio/tts/gemini/the-christian-interpretation-of-the-cabala-in-the-renaissance.md`
- model: `gemini-3.1-flash-tts-preview`
- voice: `Schedar`
- API key source: `GOOGLE_API_KEY` from ignored local environment
- generated output directory: `audio/output/gemini/`
- generated audio format: WAV, PCM signed 16-bit little-endian, mono, 24 kHz

## Samples Generated

1. Intro sample
   - output: `audio/output/gemini/the-christian-interpretation-of-the-cabala-in-the-renaissance/chunk-001.wav`
   - transcript words: 433
   - duration: 178.92 seconds
   - average pace: about 145 words per minute
   - volume scan: mean `-18.7 dB`, max `-0.9 dB`

2. Pronunciation stress sample
   - output: `audio/output/gemini/the-christian-interpretation-of-the-cabala-in-the-renaissance-pronunciation-sample/chunk-002.wav`
   - transcript words: 390
   - duration: 170.40 seconds
   - average pace: about 137 words per minute
   - volume scan: mean `-21.8 dB`, max `-0.9 dB`
   - useful review terms include `En Soph`, `zimzum`, `keter`, `sephirah`, `malchuth`, `aziluth`, `beriah`, `yetzirah`, `asiyah`, `gematria`, `notarikon`, `themurah`, `Zohar`, `Moses ben Shem Tob de Leon`, and `Rabbi Simon ben Yochai`

## Technical Result

Pass. The local runner successfully loaded the ignored API key, called Gemini TTS with the `Schedar` voice, received audio data, wrote valid WAV files, and recorded manifests for both sample runs.

## Human Review Needed

Before generating a full book, listen for:

- whether `Schedar` has the right audiobook-lecture feel
- whether section pauses are long enough without feeling theatrical
- whether dense Hebrew and Latinized terms sound acceptable
- whether bracketed pause tags are silent rather than spoken
- whether the performance accidentally reads any director-note language aloud

## Production Notes

The full render currently splits into 14 available chunks at the 450-word setting. That chunk size produced roughly three-minute samples, which matches Google's guidance to avoid very long generated outputs where voice quality can drift.
