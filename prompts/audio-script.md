# Audio Script Adaptation Prompt

Create a faithful audio-script adaptation for one canonical summary.

Source: `notes/<BOOK FILE>.md`
Output: `audio/scripts/<BOOK SLUG>.md`
QA report: `audio/qa/<BOOK SLUG>.md`
Optional Gemini TTS render: `audio/tts/gemini/<BOOK SLUG>.md`

Respect the Source of Truth and Repo Hygiene rules in `AGENTS.md`. Treat `notes/` as the canonical source of truth. Audio scripts are derived, committable artifacts; they do not replace or revise canonical notes. Do not modify the source note, `index/`, `blog/content/`, `blog/data/`, or `blog/public/`.

## Goal

Produce a single-narrator audio script that preserves the full substantive content of the source summary while making it easier to hear aloud.

The output should feel more like an audiobook lecture than a chatty podcast. Preserve density, but improve pacing. Use transitions sparingly. Prefer clarity over personality.

When a section introduces many unfamiliar names, technical terms, formulas, or compressed typologies, add a brief listener-orientation sentence that explains the structure to hold onto. These should be clarifying cushions, not new interpretation or banter.

Keep the main script engine-neutral. It should be readable, editable prose, not a model-specific TTS control file.

If the user explicitly asks for Gemini-ready, tagged, rendered, or TTS-input output, create a separate Gemini render in `audio/tts/gemini/<BOOK SLUG>.md`. Do not put Gemini audio tags, director notes, or API instructions into the base script.

## Optional Gemini TTS Render

The Gemini render is a downstream delivery artifact for audio generation. It may include:

- a style prompt or `DIRECTOR'S NOTES` block
- a transcript block
- minimal bracketed pacing tags

Use the style prompt or `DIRECTOR'S NOTES` to set the global performance, especially:

- single-narrator audiobook lecture
- calm, literate, mildly warm, and authoritative
- measured pace, with slightly slower articulation through dense names, foreign titles, sacred formulas, and technical typologies
- clear section transitions
- no banter, theatricality, hype, debate-host cadence, or casual podcast chatter

Use inline Gemini-style tags only for local pacing or delivery cues. Prefer:

- `[medium pause]` after the title and before or after section headings
- `[short pause]` where a dense list or clause boundary needs clearer separation

Avoid expressive tags such as emotional adjectives, jokes, non-speech sounds, whispers, shouting, or character acting unless the user explicitly asks for that style. Do not use untested creative tags in production scripts without flagging them in QA, because some tags may be spoken aloud or behave unpredictably.

Treat non-metadata `##` headings as chapter-like transitions in the Gemini render. Render them as plain spoken lines, with pause tags around them, rather than raw Markdown headings.

## Source Structure

Summarizer notes usually have this structure:

- `#` title
- `## Metadata`
- narrative section headings as `## ...`
- headline claims as bold bullet items
- supporting evidence as indented sub-bullets under each headline claim
- inline HTML claim anchors such as `<span id="book-slug-001"></span>`

Treat each non-metadata `##` heading as a script section. Treat each bold bullet as a claim and each indented sub-bullet as supporting evidence for that claim.

The supporting sub-bullets are not optional color. Every substantive figure, date, name, quote, example, caveat, causal link, and distinction in those sub-bullets must survive in the audio prose unless the QA report explicitly flags the omission as a fidelity concern.

## Slug Rule

If the user does not provide an output slug, derive it from the source filename using the existing blog slug convention: lowercase the filename stem, remove punctuation, trim whitespace, and convert spaces or underscores to hyphens.

Example: `notes/A Disease in the Public Mind.md` becomes `a-disease-in-the-public-mind`.

## Allowed Changes

- Split dense sentences.
- Convert bullets into spoken paragraphs.
- Add light transitions and signposting.
- Add brief listener-orientation cues before or after especially term-dense passages.
- Repeat referents where the written version relies on visual structure.
- Expand abbreviations, symbols, and compressed phrasing.
- Smooth abrupt section openings.
- Keep difficult phrases close to the source when rewriting would risk distortion.
- Strip inline `<span id="..."></span>` claim anchors. They are visual/citation scaffolding, not spoken content.
- Fold the title, author, year, and thesis metadata into a natural spoken opening.

## Forbidden Changes

- Do not add external knowledge.
- Do not add new examples.
- Do not remove caveats, distinctions, names, claims, or quoted concepts.
- Do not make the author/book sound more certain, moralized, casual, or simplistic than the source.
- Do not summarize the summary into a shorter version.
- Do not read metadata fields as database labels.
- Do not include `Topics`, `Categories`, or `Mode` as spoken content unless the user explicitly asks for them.
- Do not turn metadata topics into a catalog-like spoken list; use them only to shape a natural opening frame.
- Do not make the script chattier in the name of listenability.
- Do not include HTML anchors, raw claim IDs, QA comments, or implementation notes in the audio script.
- Do not publish, build, or regenerate derived site artifacts.

## Process

1. Read the full source note first.
2. Identify its section structure.
3. Derive or confirm the output slug using the Slug Rule.
4. Create `audio/scripts/` and `audio/qa/` if they do not already exist.
5. If either output file already exists and the user did not explicitly request overwrite, stop and report the existing path instead of overwriting it.
6. Rewrite section by section, preserving heading order.
7. Convert claim bullets and their supporting sub-bullets into TTS-ready paragraphs.
8. After drafting each section, compare it against the source section and fix omissions, added claims, and softened distinctions.
9. Write the finished script to `audio/scripts/<BOOK SLUG>.md`.
10. Write a QA report to `audio/qa/<BOOK SLUG>.md`.
11. Work incrementally in the filesystem. Do not attempt to produce the whole script as one chat response.

## Script Format

Use Markdown for the script:

- Keep the book title as `#`.
- Keep non-metadata section headings as `##`.
- Use prose paragraphs for spoken content.
- Do not include the source `## Metadata` block.
- Do not include bullets unless a list genuinely needs to be heard as a list.
- Do not include HTML anchors, claim IDs, or source-only scaffolding.
- Do not include the QA verdict or fidelity notes in the audio script.

For numbers and symbols, optimize for correct speech without changing meaning. For example:

- `$1,000` may become `one thousand dollars`.
- `6:1` may become `six to one`.
- `1501 and the 1880s` may stay as written if it will be pronounced clearly.
- `89%` may stay as `89%` or become `eighty-nine percent`; choose the clearer spoken form for the sentence.

For difficult names, acronyms, sacred formulas, transliterations, and foreign-language titles, preserve the source meaning in the script and list pronunciation/TTS risks in the QA report. Do not invent phonetic spellings unless the user asks for a pronunciation-prepped version.

## QA Report Format

The QA report should include:

- source file
- output file
- sections adapted
- approximate source word count
- approximate script word count
- script/source word-count ratio
- fidelity concerns, if any
- passages intentionally left close to the original because rewriting risked distortion
- pronunciation/TTS risks for names, acronyms, formulas, transliterations, and foreign-language titles
- existing output files encountered, if any
- final verdict: `pass`, `pass with concerns`, or `fail`

Use this verdict rubric:

- `pass`: all substantive source content appears preserved; no added claims; script is listenable; script length is plausibly faithful.
- `pass with concerns`: script is probably usable, but the QA report identifies passages a human should review before TTS.
- `fail`: missing claims, omitted supporting evidence, added claims, raw anchors/metadata, or major tone drift remain.

As a rough length guardrail, faithful audio scripts will often be about `1.0x` to `1.5x` the meaningful source word count after excluding raw anchors and source-only metadata. A script shorter than the meaningful source is a warning sign for dropped content and should not receive `pass` without a clear explanation.

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
