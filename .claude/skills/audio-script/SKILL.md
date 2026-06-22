---
name: audio-script
description: Create faithful single-narrator audio-script adaptations from canonical Summarizer notes, preserving all substantive content while making prose listenable aloud.
---

Use this skill when asked to adapt a canonical summary in `notes/` into an audio-friendly script.

Read and follow `prompts/audio-script.md` before taking action. Treat that prompt file as the canonical workflow for this skill.

The expected user input is a source note path such as `notes/the-book.md` and, optionally, an output slug. If no slug is provided, derive one from the source filename.

Use the existing blog slug convention when deriving slugs: lowercase the filename stem, remove punctuation, trim whitespace, and convert spaces or underscores to hyphens.

Only create or edit files under `audio/scripts/`, `audio/qa/`, and, when the user explicitly asks for Gemini-ready TTS input, `audio/tts/gemini/`, unless the user explicitly requests a workflow implementation change.
