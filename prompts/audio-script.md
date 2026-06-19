# Audio Script Adaptation Prompt

Create a faithful audio-script adaptation for one canonical summary.

Source: `notes/<BOOK FILE>.md`
Output: `audio/scripts/<BOOK SLUG>.md`
QA report: `audio/qa/<BOOK SLUG>.md`

Follow `AGENTS.md`. Treat `notes/` as the canonical source of truth. Do not modify the source note, `index/`, `blog/content/`, `blog/data/`, or `blog/public/`.

## Goal

Produce a single-narrator audio script that preserves the full substantive content of the source summary while making it easier to hear aloud.

The output should feel more like an audiobook lecture than a chatty podcast. Preserve density, but improve pacing. Use transitions sparingly. Prefer clarity over personality.

## Allowed Changes

- Split dense sentences.
- Convert bullets into spoken paragraphs.
- Add light transitions and signposting.
- Repeat referents where the written version relies on visual structure.
- Expand abbreviations, symbols, and compressed phrasing.
- Smooth abrupt section openings.
- Keep difficult phrases close to the source when rewriting would risk distortion.

## Forbidden Changes

- Do not add external knowledge.
- Do not add new examples.
- Do not remove caveats, distinctions, names, claims, or quoted concepts.
- Do not make the author/book sound more certain, moralized, casual, or simplistic than the source.
- Do not summarize the summary into a shorter version.
- Do not publish, build, or regenerate derived site artifacts.

## Process

1. Read the full source note first.
2. Identify its section structure.
3. Create `audio/scripts/` and `audio/qa/` if they do not already exist.
4. Rewrite section by section, preserving heading order.
5. After drafting each section, compare it against the source section and fix omissions, added claims, and softened distinctions.
6. Write the finished script to `audio/scripts/<BOOK SLUG>.md`.
7. Write a QA report to `audio/qa/<BOOK SLUG>.md`.
8. Work incrementally in the filesystem. Do not attempt to produce the whole script as one chat response.

## QA Report Format

The QA report should include:

- source file
- output file
- sections adapted
- approximate source word count
- approximate script word count
- fidelity concerns, if any
- passages intentionally left close to the original because rewriting risked distortion
- final verdict: `pass`, `pass with concerns`, or `fail`

If the verdict is not `pass`, explain what a human should review before using the script for TTS.

## Invocation Template

```text
Use the repo audio-script prompt to adapt this summary:

Source: notes/<BOOK FILE>.md
Output slug: <BOOK SLUG>

Create:
- audio/scripts/<BOOK SLUG>.md
- audio/qa/<BOOK SLUG>.md
```
