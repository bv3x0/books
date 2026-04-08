# Summarizer Agent Guide

This file exists to make work in this repo maximally effective for Codex/GPT-class coding agents.

Use these rules as the repo-specific operating contract. Prefer them over generic habits when they conflict.

## Mission

This repo is a book-ingest, publishing, and search system.

Core responsibilities:
- ingest PDF/EPUB books into canonical outputs
- maintain canonical note/index data
- publish those outputs into a Hugo site
- support semantic search via Vercel + Neon/Postgres

The main goal is not just to make code changes. It is to preserve the integrity of the data pipeline and deploy contract.

## Architecture Contract

There is one deploy boundary and one build contract.

- Vercel project root: repo root
- Vercel config: `vercel.json`
- Node package boundary: root `package.json`
- Hugo source: `blog/`
- Vercel runtime API: `api/`
- Build output: `blog/public`

Do not reintroduce:
- `blog/package.json`
- `blog/vercel.json`
- `blog/api/search.js`
- alternate deploy scripts like `vercel-build.sh`
- a second Vercel root unless the repo is intentionally being converted into a split app/monorepo structure

If deployment behavior changes, update these together:
- `vercel.json`
- `package.json`
- `scripts/build-search-index.mjs`
- the relevant README sections

## Source Of Truth

Canonical data:
- `books/@staging/` = transient ingest input only
- `notes/` = canonical human-readable outputs
- `index/` = canonical machine-readable outputs

Derived artifacts:
- `blog/content/books/` = generated from `notes/`
- `blog/data/` = derived site data such as stats and related books
- `blog/public/` = build output only
- `blog/public/pagefind/` = generated search index output

Never treat derived artifacts as the primary source of truth when canonical data exists elsewhere.

## Preferred Workflow

Use the wrapper commands unless there is a clear reason not to.

Primary commands:
```bash
python3 scripts/workflow.py add "book-name"
python3 scripts/workflow.py smoke
python3 scripts/workflow.py publish
python3 scripts/workflow.py ship
```

Use these checks before or after structural changes:
```bash
python3 -m unittest app.tests.test_services
python3 scripts/workflow.py smoke
```

For direct CLIs:
- ingest: `python3 app/main.py ...`
- publish: `python3 app/cli/publish.py publish`
- local serve: `python3 app/cli/publish.py serve`

## Ingest Rules

The ingest pipeline is:

`books/@staging/ -> app/main.py -> notes/ + index/ -> publish -> blog/`

Current ingest structure:
- `app/main.py` = CLI entrypoint only
- `app/services/ingest_service.py` = top-level orchestration
- `app/services/ingest_runtime.py` = provider/bootstrap + core component construction
- `app/services/ingest_validation_service.py` = TOC + chunking validation
- `app/services/ingest_reporting.py` = configuration, export summary, cost reporting
- `app/services/ingest_interaction.py` = typed operator decision contracts

Current long-context policy:
- Sonnet 4.6 is no longer treated like a 200k-context model; ingest uses model-specific single-request and chunk budgets
- extra-long Sonnet 4.6 markdown books with a usable TOC may run a whole-book planning pass before chunked summarization
- the planning pass emits exact boundary anchors and consecutive chapter groups, then local code slices the book from that plan
- if the plan cannot be parsed or anchors cannot be applied, ingest must fall back to the normal chapter-aware chunker
- chunked Sonnet 4.6 runs may use Anthropic prompt caching for the shared unified prompt; keep cache-aware cost reporting aligned with API usage fields
- do not enable planning during `--retry`; retries must reuse the original chunk layout from cached results

Important flags:
- `--toc`: use `books/toc.txt`
- `--yes`: auto-accept prompts after the operator has already reviewed the input
- `--non-interactive`: never prompt; proceed on safe confirmations and abort when human judgment is required
- `--test`: notes-only comparison run; do not treat as canonical publishable output
- `--enrich`: enable embedding/vector enrichment during ingest

Prompting rules:
- use `--yes` for attended runs when the operator already trusts the TOC/input
- use `--non-interactive` for automation, agent-driven runs, or tests where hanging on prompts is unacceptable
- keep ingest decision contracts typed; do not return raw string/tuple action values from new code

Test outputs:
- `notes/*.test.md`
- `notes/*.gem.md`
- `notes/*.gpt.md`

These are comparison artifacts, not canonical publish targets.

## PDF Extraction Rules

On macOS/Apple Silicon, standard Docling extraction can crash in the MLX/Metal stack.

Current repo policy:
- standard PDF extraction prefers `PyMuPDF4LLM` by default on Apple Silicon
- `--ocr` explicitly uses Granite-Docling VLM for scanned/degraded PDFs
- `SUMMARIZER_PDF_EXTRACTOR=docling` can force Docling
- `SUMMARIZER_PDF_EXTRACTOR=pymupdf` can force PyMuPDF

Do not revert this default casually. A native crash path is worse than a slower extractor.

## Publish Rules

Publish is a workflow, not just a Hugo build.

Current publish structure:
- `app/services/content_service.py`
- `app/services/site_service.py`
- `app/services/maintenance_service.py`
- `app/services/publish_service.py`
- `app/services/step_result.py`

`publish_service` should remain orchestration-heavy only.
Concrete work should stay in the focused services above.

Publish/build/maintenance outcomes now distinguish:
- `SUCCESS`
- `WARNING`
- `SKIPPED`
- `FAILED`

Do not collapse these back into raw booleans in new service code unless compatibility specifically requires a wrapper.

Do not move terminal prompting or CLI concerns into service orchestration.

## Utility Service Rules

The remaining operator CLIs should stay thin as well.

Current utility service structure:
- `app/services/query_service.py`
- `app/services/evaluation_service.py`
- `app/services/book_management_service.py`

Do not move data access, DB mutation, or metric computation back into:
- `app/cli/query.py`
- `app/cli/evaluate.py`
- `app/cli/delete_book.py`
- `app/cli/rename_book.py`

## Search Runtime Rules

The semantic search runtime lives at:
- `api/search.js`

It assumes:
- Vercel runtime environment
- Neon/Postgres with pgvector
- OpenAI embeddings for query embedding

When changing it:
- preserve the public API contract unless intentionally versioning it
- do not leak raw internal errors in responses
- keep env-var handling aligned with migration tooling
- validate query inputs defensively

## Testing Expectations

This repo now has two levels of protection:

1. Targeted boundary tests
```bash
python3 -m unittest app.tests.test_services
```

2. Integration smoke test
```bash
python3 scripts/workflow.py smoke
```

Use targeted tests for:
- orchestration behavior
- command construction
- non-interactive decision handling

Use smoke tests for:
- CLI health
- publish/build health
- Vercel-root build health
- search runtime syntax

When changing architecture, build, deploy, ingest, or publish behavior, run both.

## Repo Hygiene

Avoid duplicate truth sources.

Do not add or restore:
- legacy deploy scripts
- alternate package roots
- duplicate API files under `blog/`
- stale build helpers that encode old architecture

If a deleted legacy file resurfaces locally, treat it as suspicious until proven otherwise.

Keep the worktree clean when possible. If local git metadata is broken or stale, fix it rather than routing around it.

## Frontend/UI Rules

When working on the Hugo frontend or any UI in this repo, follow these rules.

### Interactions

#### Keyboard

- MUST: Full keyboard support per [WAI-ARIA APG](https://www.w3.org/WAI/ARIA/apg/patterns/)
- MUST: Visible focus rings (`:focus-visible`; group with `:focus-within`)
- MUST: Manage focus (trap, move, return) per APG patterns
- NEVER: `outline: none` without visible focus replacement

#### Targets & Input

- MUST: Hit target >=24px (mobile >=44px); if visual <24px, expand hit area
- MUST: Mobile `<input>` font-size >=16px to prevent iOS zoom
- NEVER: Disable browser zoom (`user-scalable=no`, `maximum-scale=1`)
- MUST: `touch-action: manipulation` to prevent double-tap zoom
- SHOULD: Set `-webkit-tap-highlight-color` to match design

#### Forms

- MUST: Hydration-safe inputs (no lost focus/value)
- NEVER: Block paste in `<input>`/`<textarea>`
- MUST: Loading buttons show spinner and keep original label
- MUST: Enter submits focused input; in `<textarea>`, Cmd/Ctrl+Enter submits
- MUST: Keep submit enabled until request starts; then disable with spinner
- MUST: Accept free text, validate after - don't block typing
- MUST: Allow incomplete form submission to surface validation
- MUST: Errors inline next to fields; on submit, focus first error
- MUST: `autocomplete` + meaningful `name`; correct `type` and `inputmode`
- SHOULD: Disable spellcheck for emails/codes/usernames
- SHOULD: Placeholders end with `…` and show example pattern
- MUST: Warn on unsaved changes before navigation
- MUST: Compatible with password managers & 2FA; allow pasting codes
- MUST: Trim values to handle text expansion trailing spaces
- MUST: No dead zones on checkboxes/radios; label+control share one hit target

#### State & Navigation

- MUST: URL reflects state (deep-link filters/tabs/pagination/expanded panels)
- MUST: Back/Forward restores scroll position
- MUST: Links use `<a>`/`<Link>` for navigation (support Cmd/Ctrl/middle-click)
- NEVER: Use `<div onClick>` for navigation

#### Feedback

- SHOULD: Optimistic UI; reconcile on response; on failure rollback or offer Undo
- MUST: Confirm destructive actions or provide Undo window
- MUST: Use polite `aria-live` for toasts/inline validation
- SHOULD: Ellipsis (`…`) for options opening follow-ups ("Rename…") and loading states ("Loading…")

#### Touch & Drag

- MUST: Generous targets, clear affordances; avoid finicky interactions
- MUST: Delay first tooltip; subsequent peers instant
- MUST: `overscroll-behavior: contain` in modals/drawers
- MUST: During drag, disable text selection and set `inert` on dragged elements
- MUST: If it looks clickable, it must be clickable

### Animation

- MUST: Honor `prefers-reduced-motion` (provide reduced variant or disable)
- SHOULD: Prefer CSS > Web Animations API > JS libraries
- MUST: Animate compositor-friendly props (`transform`, `opacity`) only
- NEVER: Animate layout props (`top`, `left`, `width`, `height`)
- NEVER: `transition: all` - list properties explicitly

### Content & Accessibility

- MUST: Skeletons mirror final content to avoid layout shift
- MUST: `<title>` matches current context
- MUST: No dead ends; always offer next step/recovery
- MUST: Accessible names exist even when visuals omit labels
- MUST: Use `…` character (not `...`)
- MUST: `scroll-margin-top` on headings; "Skip to content" link; hierarchical `<h1>`-`<h6>`
- MUST: Accurate `aria-label`; decorative elements `aria-hidden`
- MUST: Icon-only buttons have descriptive `aria-label`
- MUST: Prefer native semantics (`button`, `a`, `label`, `table`) before ARIA

### Performance

- MUST: Prevent CLS (explicit image dimensions)
- MUST: Avoid unwanted scrollbars and overflow bugs
- MUST: Profile with CPU/network throttling for meaningful changes

### Design

- MUST: Meet contrast requirements
- MUST: Increase contrast on `:hover`/`:active`/`:focus`
- SHOULD: Avoid generic, boilerplate-looking layouts when doing significant design work
