# Summarization Fidelity & Cost Improvement Plan

Implementation plan for improving the book-summarization pipeline. Written to be executed
by a coding agent (Codex) with no prior context on this conversation.

## Goals, in priority order

1. **Fidelity to the author.** The single most important property of a summary is that it
   represents what the author actually said, in the author's own framing and strength of
   claim — especially for controversial, heterodox, or politically charged texts, where
   LLMs tend to sanitize, hedge, or reframe. Wrong-spin paraphrase and silent omission are
   the failure modes to defend against.
2. **Cheaper or equal cost per book.** Improvements must not raise per-book cost. The
   Anthropic Batch API (50% discount on all tokens) funds a model upgrade: **the new
   default is `claude-opus-4-8` in batch mode**, which lands at roughly the same per-book
   cost as today's Sonnet 4.6 sequential runs (Opus batched: $2.50/$12.50 per MTok vs
   Sonnet 4.6 full-price $3/$15; Opus 4.7+'s newer tokenizer counts ~1.0–1.35× more
   tokens for the same text, which eats most of the nominal savings).
3. **Provider parity for prompts.** The user may switch to Codex/GPT. All prompt changes
   go in the shared prompt (`get_unified_analysis_prompt()` in `app/config.py`), which is
   already used by every provider. Provider-specific work (model swap, batch mode,
   structured outputs) targets the Anthropic path; the Codex path already has a JSON
   schema.

## Architecture context (current state)

- `app/config.py` — `get_unified_analysis_prompt()` builds the single shared prompt (~5k
  tokens) that produces the unified JSON (book metadata + chapters + key_points +
  sub_points + concepts + entities). Model IDs, pricing, chunking constants live here too.
- `app/core/manifest.py` — builds Messages API requests; TOC-driven chunking; attaches the
  shared prompt as a cached `system` block on Anthropic; per-chunk continuity guidance is
  in the user message.
- `app/core/monitor.py` — sequential API calls per provider (`anthropic`, `gemini`,
  `openai`, `codex`), truncation retries, JSON extraction + regex "repair"
  (`_extract_json`, `_repair_unescaped_quotes`), results cache in `app/logs/`.
- `app/core/exporter.py` — merges chunk results, renders `notes/{book}.md` and
  `index/{book}.json`, embeddings.
- The Codex path (`Monitor._call_codex`) already enforces `_codex_output_schema()` via
  `codex exec --output-schema`.

---

## Phase 0 — Switch the default model to `claude-opus-4-8`

The default Anthropic model changes from `claude-sonnet-4-6` to `claude-opus-4-8`
(stronger on knowledge work and long-document comprehension, and notably more literal
instruction following — which makes the Phase 1 fidelity rules more effective). Combined
with batch mode (Phase 3), per-book cost stays at or below today's baseline.

### 0.1 Model constant and pricing

In `app/config.py`:

- `ANTHROPIC_MODEL_ID = "claude-opus-4-8"`. Use this exact string — no date suffix.
- Add to `MODEL_PRICING_USD_PER_MILLION`:
  `{"input": 5.0, "cache_write_input": 6.25, "cache_read_input": 0.50, "output": 25.0}`.
  Keep the `claude-sonnet-4-6` entry for historical cost reporting.

### 0.2 Replace the string-prefix model gate with a tier lookup

`is_anthropic_long_context_model()` currently returns True only for IDs starting with
`claude-sonnet-4-6`, and everything model-specific (single-request limit, smart-chunk
settings, max output tokens, chunk planning) keys off it. Replace it with a check that
treats both `claude-opus-4-8` and `claude-sonnet-4-6` (and future 1M-context Anthropic
models) as long-context — e.g. a set/prefix-list of known long-context Anthropic IDs.
Opus 4.8 has a 1M-token context window and 128K max output, so the existing
`ANTHROPIC_LONG_CONTEXT_*` constants carry over as valid defaults.

### 0.3 Re-baseline tokenizer-sensitive constants

Opus 4.7/4.8 use a newer tokenizer: the same text counts as roughly 1.0–1.35× more tokens
than under Sonnet 4.6. The pipeline's `estimate_tokens()` heuristic (chars/4-style) feeds
chunk sizing, so:

- Review the chars-per-token ratio in `app/core/epub_processor.py::estimate_tokens` and
  make it slightly more conservative (e.g. if it assumes ~4 chars/token, use ~3.4) so
  chunks don't overshoot the request budget.
- The `ANTHROPIC_LONG_CONTEXT_*` env-overridable constants need no change (they're
  already conservative relative to a 1M window), but note in comments that they were
  re-baselined for the Opus 4.8 tokenizer.

### 0.4 Sampling and thinking parameters — what NOT to send

- **Do not send `temperature`, `top_p`, or `top_k` to `claude-opus-4-8`** — they return a
  400. (See Phase 1.4: the temperature fix applies only to pre-4.7 models.)
- **Do not send a `thinking` parameter.** Omitting it runs Opus 4.8 without thinking,
  which is the right cost baseline for a single-pass summarization call. (Optional
  later experiment, not part of this plan: `thinking: {"type": "adaptive"}` may improve
  synthesis on dense theoretical books at an output-token premium.)

### 0.5 Prompt caching note

The shared system prompt (~5k tokens) stays cached via the existing `cache_control`
block. Opus 4.8's minimum cacheable prefix is 4096 tokens, so it still qualifies — do not
shrink the prompt below that. Cache reads bill at $0.50/MTok (half that in batch mode).
Under batch processing cache hits are best-effort (requests may run concurrently), so
treat cache savings as a bonus, not a budget line.

---

## Phase 1 — Prompt fixes for fidelity (free; applies to all providers)

All edits go in `get_unified_analysis_prompt()` in `app/config.py`.

### 1.1 Add a "Descriptive fidelity" section to the prompt

Add a new top-level section (place it prominently, right after the OUTPUT FORMAT section)
along these lines — adapt wording, keep the substance:

```
## DESCRIPTIVE FIDELITY (CRITICAL)

You are producing an archival scholarly record of what this book argues. Every claim in
your output is ATTRIBUTED TO THE BOOK, not asserted by you. Your accuracy is judged by how
faithfully a reader of the original would recognize the author's argument — not by whether
the argument is correct, palatable, or acceptable.

- Represent the author's claims in the author's own framing, at the author's own strength.
  If the author asserts X causes Y, write "X causes Y" — do not weaken to "may be
  associated with" or "the author suggests a possible link."
- Do not sanitize, soften, hedge, or euphemize controversial, offensive, heterodox, or
  politically charged claims. A summary that launders the author's meaning into something
  more comfortable is a FAILED summary.
- Do not add disclaimers, counterpoints, "balance," modern context, or moral commentary
  that the author does not provide. Do not note that a claim is disputed unless the author
  does.
- Do not swap the author's loaded or evaluative vocabulary for neutral synonyms when the
  loading carries the argument. Preserve the author's terms (in quotes if needed).
- Match the author's modality exactly: is/may be, all/most/some, causes/correlates,
  should/must. Modality drift is a fidelity failure.
- If a chapter's argument makes you reluctant to state it plainly, that is precisely the
  chapter where plain statement matters most. State what the author says; the attribution
  to the book is your neutrality.
```

Rationale: attribution framing ("this is a record of what the book says") measurably
reduces model reluctance and editorializing on charged material, and modality-matching
targets the subtle claim-weakening failure mode.

### 1.2 Reinforce the existing "state claims directly" rule

In the KEY POINT REQUIREMENTS section, the prompt already says to avoid "The author
argues..." framing. Add one clarifying line: distancing language ("controversially,"
"provocatively," "it is claimed that") counts as meta framing and must not be used.

### 1.3 Strengthen omission defense in chapter coverage

In the CHAPTER COVERAGE section, add:

- A rule that consolidation must never remove an argumentative move entirely: "Merging
  points is allowed; dropping a distinct argument, counterexample the author treats as
  important, or a chapter's stated conclusion is not."
- A rule that the density guidance (1-3 / 2-5 / 3-6 points) is a floor-shaping heuristic,
  not a cap that justifies omitting a genuinely separate argument.

### 1.4 Temperature on the Anthropic path — pre-4.7 models only

With the Phase 0 default of `claude-opus-4-8`, **no sampling parameters may be sent** —
`temperature`/`top_p`/`top_k` return a 400 on Opus 4.7+, Sonnet 5, and Fable 5. Behavior
is steered by prompting only (which Phase 1.1–1.3 provide).

If anyone runs the pipeline with an older model (e.g. `claude-sonnet-4-6` via an env
override), add `"temperature": 0.2` to `request_kwargs` in `Monitor._call_model`
(anthropic branch, `app/core/monitor.py` ~line 440) **gated on the model ID being a
pre-4.7 model**. The Gemini and OpenAI paths already use 0.2 and are unchanged.

### 1.5 Give continuation chunks book-level context

In `Manifest._create_chunked_requests` (`app/core/manifest.py`), chunks 2..N currently
receive only "this is part i of N" plus their own TOC slice. Add to each continuation
chunk's user content a short context block (cheap — a few hundred tokens):

- Book title and author (available from `file_data["source_metadata"]` / staged metadata
  when present).
- The list of chapter titles covered by *earlier* chunks (derivable from the chunk specs /
  TOC), stated as "already summarized elsewhere — do not re-cover."

This prevents framing drift in later chapters and reduces duplicate/misplaced claims that
the exporter currently has to dedupe.

---

## Phase 2 — Structured outputs on the Anthropic path (free; removes a fidelity hazard)

The current pipeline parses raw text and runs `_repair_unescaped_quotes`, a heuristic
scanner that rewrites bytes inside JSON strings. It can silently corrupt exactly the
verbatim quotes the pipeline is supposed to preserve. Eliminate the need for it.

### 2.1 Use `output_config.format` with a JSON schema

In the Anthropic branch of `Monitor._call_model`, pass:

```python
request_kwargs["output_config"] = {
    "format": {"type": "json_schema", "schema": SUMMARY_SCHEMA}
}
```

where `SUMMARY_SCHEMA` is the existing `Monitor._codex_output_schema()` — move it to a
shared location (e.g. `app/core/schema.py` or `app/config.py`) and reference it from both
the Codex and Anthropic paths so there is exactly one schema definition.

Schema constraints to respect (Anthropic structured outputs): every object needs
`additionalProperties: false` and `required` (the existing schema already does this);
recursive schemas and min/max constraints are not supported (not used here). Note the
schema compiles on first use with a one-time latency cost, then is cached server-side for
24h.

### 2.2 Runtime capability check with graceful fallback

Structured-output support varies by model. At Monitor init (Anthropic provider only),
check once via the Models API:

```python
caps = client.models.retrieve(model_id).capabilities
use_structured = caps["structured_outputs"]["supported"]
```

If unsupported (or the call fails), fall back to the current text-parse path unchanged.

### 2.3 Bypass JSON repair when structured outputs are active

When a response was produced under `output_config.format`, parse with plain `json.loads`
(still strip markdown fences defensively) and **skip** `_repair_unescaped_quotes` and the
trailing-comma/quotes-array regex fixes. Keep the repair path intact for Gemini and for
the fallback, and keep `_salvage_cached_parse_failures` working for old caches.

### 2.4 Note on prompt

Keep the "You must respond with valid JSON only" instruction in the shared prompt (other
providers still need it); it is harmless under structured outputs.

---

## Phase 3 — Batch API as the default Anthropic mode (−50% cost)

The Message Batches API charges 50% of standard prices on all tokens and supports
everything this pipeline uses (system blocks, prompt caching markers, structured outputs).
Most batches complete well within an hour. The user has approved batch-by-default.

Batch is what makes the Phase 0 Opus upgrade affordable: Opus 4.8 batched is
$2.50/$12.50 per MTok — below Sonnet 4.6's full-price $3/$15 — so the combined change
holds per-book cost at or under the previous baseline.

### 3.1 Implement batch submission in Monitor

Add a batch path to `Monitor.submit_job` for `provider == "anthropic"`:

1. Build the same per-chunk request payloads as today.
2. Submit one batch: `client.messages.batches.create(requests=[{custom_id, params}, ...])`
   with `custom_id = f"chunk-{index}"`. (Python SDK: wrap as
   `Request(custom_id=..., params=MessageCreateParamsNonStreaming(...))`.)
3. Poll `client.messages.batches.retrieve(batch_id).processing_status` until `"ended"`,
   printing status + `request_counts` every ~30-60s so the user still gets progress
   feedback.
4. Stream `client.messages.batches.results(batch_id)` and **key results by `custom_id`,
   never by position** — results arrive in arbitrary order.
5. Feed each result through the existing parse/validate logic (`_parse_unified_response`)
   and the existing results-cache format so `--retry`, salvage, and the exporter work
   unchanged.

### 3.2 Handling truncation/parse failures under batch

The current per-request "retry with more max_tokens" loop can't run mid-batch. Instead:
after the batch completes, collect chunks whose result is TRUNCATED / PARSE_FAILED /
errored, bump their `max_tokens` (same `+8192, cap 65536` policy), and submit a second,
smaller batch for just those. Two rounds max; anything still failing lands in the results
cache as FAILED for the existing `--retry` flow.

### 3.3 CLI flags

- Batch is the **default** for the Anthropic provider.
- Add `--sequential` (or `--live`) to force the current per-request mode for debugging /
  interactive runs.
- Non-Anthropic providers are unaffected (Batch API is Anthropic-first-party only).

### 3.4 Update the pricing/cost reporting

`MODEL_PRICING_USD_PER_MILLION` and any cost-estimation code should apply the 0.5×
multiplier when the run used batch mode, so logs/reports stay accurate.

---

## Phase 4 — Local fidelity verification (zero API cost; all providers)

New module `app/core/verifier.py`, run after parsing and before export. Everything here is
pure-Python string matching against the source chunk text — no API calls.

### 4.1 Make source text available to the verifier

The results cache stores responses but not the chunk source text. Thread the chunk's user
content (or just the source text between the `---` markers) through to verification —
either verify inline in the ingest flow while the request objects are still in memory
(simplest), or store a reference/hash in the cache entry.

### 4.2 Checks

For each successfully parsed chunk, against that chunk's source text:

1. **Quote verification.** Every `sub_points` entry with `type == "quote"` and every
   non-null `pull_quote`: normalize (collapse whitespace, unify curly/straight quotes and
   dashes, casefold) and require either an exact substring match or a fuzzy match
   (`difflib.SequenceMatcher` over a sliding window, ratio ≥ 0.85 — quotes are allowed to
   be "near-verbatim"). Failures are flagged as `QUOTE_NOT_IN_SOURCE`.
2. **Entity grounding.** For each named person/place/work in `entities`: check the surface
   form (and a last-name-only fallback for people) appears in the chunk text. Flag misses
   as `ENTITY_NOT_IN_SOURCE`. This is a hallucination tripwire, not a hard error — TOC
   spillover and inflected forms cause benign misses, so report, don't block.
3. **Chapter coverage.** Compare the chapter titles in the output against the TOC titles
   expected for this chunk (the chunk specs already carry `chapter_titles` when planned;
   otherwise use `_extract_chunk_toc`). Flag `CHAPTER_MISSING` and `CHAPTER_UNEXPECTED`.
4. **Thin-chapter heuristic.** Estimate each chapter's source length (split chunk text on
   the chapter headings); flag chapters with > ~4k words of source but ≤ 1 key_point as
   `POSSIBLY_UNDERSUMMARIZED` — the omission tripwire.

### 4.3 Reporting and action

- Write `app/logs/{book}_fidelity.json` with all findings, and print a concise console
  summary (counts by type, worst offenders).
- Exit-status style summary at the end of `python3 -m app.main`: e.g.
  `Fidelity: 2 quote failures, 0 missing chapters, 3 ungrounded entities — see log`.
- If a chunk has hard failures (any `QUOTE_NOT_IN_SOURCE` or `CHAPTER_MISSING`), mark it
  so the existing `--retry` flow can regenerate just that chunk. Do **not** auto-retry by
  default (cost control) — print the suggestion.
- `app/cli/evaluate.py` should surface the fidelity report for a book if present.

---

## Phase 5 — Small bug fixes (do these while in the code)

1. **`Monitor.submit_job_retry` NameError** (`app/core/monitor.py` ~line 1055):
   `state = "SUCCEEDED" if still_failed == 0 else "PARTIAL" if successful > 0 else "FAILED"`
   references `successful`, which is undefined in that scope — crashes whenever retried
   chunks still contain failures. Compute successes from `merged_results` (or reuse
   `_summarize_results`).
2. **Hallucination heuristic** in `validate_response` only runs on the legacy
   (non-unified) path and keys off file size — Phase 4 supersedes it; leave it but note it
   in a comment, or route unified results through the verifier instead.

---

## Explicitly out of scope / deferred

- **LLM-based fidelity audit pass** (re-reading source + claims with a second model):
  costs +~100% input; revisit only if Phase 4's free checks prove insufficient. If added
  later, run it through the Batch API and only on flagged chapters.
- **Adaptive thinking on Opus 4.8** (`thinking: {"type": "adaptive"}`): possible quality
  gain on dense theoretical books, but thinking tokens bill as output ($12.50/MTok
  batched). Test on one book before adopting; not part of this plan.
- **`claude-sonnet-5` as a cheaper alternative** (intro pricing $2/$10 per MTok through
  2026-08-31 → ~$1/$5 batched, near-Opus quality on many tasks; adaptive thinking on by
  default when `thinking` is omitted — would need `thinking: {"type": "disabled"}` for
  the cost baseline). Once Phase 0.2's tier lookup exists, trying it is a one-line model
  swap plus that thinking override; a `--test` comparison run against Opus 4.8 would
  settle it empirically.
- Gemini-path structured outputs (`responseSchema`) — the user's likely providers are
  Claude and Codex; Gemini keeps the current JSON-mime mode.

## Acceptance criteria

- Re-running an already-processed book (from `books/@staging/`) on `claude-opus-4-8` in
  batch mode completes and costs no more than the previous Sonnet 4.6 sequential run for
  the same book (verify from usage logs — expect roughly parity, since the batch discount
  offsets Opus's higher rates and larger token counts), producing notes/index of
  comparable or better depth.
- No Anthropic request contains `temperature`, `top_p`, `top_k`, or a `thinking` field
  when the model is `claude-opus-4-8` (a stray sampling param is an immediate 400).
- Prompt changes: spot-check a charged/heterodox book already in `notes/` by reprocessing
  in `--test`-style comparison and confirming claims read at the author's strength without
  hedging or added balance.
- Fidelity report generated for every run; a deliberately corrupted quote injected into a
  cached response is caught by the verifier.
- All existing tests in `app/tests/` pass; add tests for the verifier (quote matching,
  normalization, coverage) and for batch result ordering by `custom_id`.
