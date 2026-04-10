# Book Summarizer

A PDF/EPUB book summarizer that generates detailed chapter outlines with structured claims for cross-book querying. Publishes as a static Hugo blog on Vercel.

## TL;DR Workflow

```bash
# Best results: add one book, run smoke checks, repair vectors, publish, push, and sync Postgres
python3 scripts/workflow.py add "book-name"
python3 scripts/workflow.py smoke
python3 scripts/workflow.py ship --reconcile full --sync-vectors

# Batch ingest: process multiple books in one run from a manifest
python3 scripts/workflow.py add --batch-manifest books/batch-ingest.json
python3 scripts/workflow.py smoke
python3 scripts/workflow.py ship

# Fast common case on main: add one book, then publish + push
python3 scripts/workflow.py add "book-name"
python3 scripts/workflow.py ship

# Feature branch preview-only push
python3 scripts/workflow.py ship --allow-preview

# Feature branch production deploy
python3 scripts/workflow.py ship --deploy-production

# Optional: run local smoke checks before ship
python3 scripts/workflow.py smoke

# Optional: local publish only (build/update locally, do not push)
python3 scripts/workflow.py publish

# Optional: periodic semantic maintenance (local repair)
python3 scripts/reconcile_vectors.py --apply-all

# Optional: sync repaired vectors to Postgres
python3 scripts/migrate-vectors.py
```

## Stack

- **Summarization**: Anthropic Claude (`claude-sonnet-4-6`), Gemini (`gemini-3-flash-preview`), or OpenAI (`gpt-5.2`)
- **OCR**: Granite-Docling-258M via MLX (local, Apple Silicon)
- **Embeddings**: OpenAI (`text-embedding-3-small`)
- **Vector Store**: Neon Postgres with pgvector (production), SQLite (local)
- **Search**: Pagefind (text) + Semantic search API (natural language)
- **Publishing**: Hugo static site on Vercel

## Architecture Contract

This repo now has one deployment boundary and one build contract.

- **Vercel project root**: repo root
- **Vercel config**: `vercel.json`
- **Node package boundary**: root `package.json`
- **Hugo source**: `blog/`
- **Vercel API runtime**: `api/`
- **Build output**: `blog/public`

### Source of Truth

- `notes/` is the canonical human-readable output
- `index/` is the canonical machine-readable output
- `books/@staging/` is transient ingest input for the backward-compatible single-book path
- batch ingest uses one source folder per book, for example `books/batches/digital-cash/`
- Canonical book renames must keep the `notes/` stem and `index/` stem aligned; publish and Pagefind both derive `/books/<slug>/` from that shared slugified stem

### Derived Artifacts

- `blog/content/books/` is generated from `notes/`
- `blog/data/` contains derived site data such as stats and related books
- `blog/public/` is build output only
- `blog/public/pagefind/` is generated search index output

### Deployment Path

Vercel builds from the repo root with:

```bash
npm run vercel-build
```

That command:

1. builds Hugo from `blog/` into `blog/public`
2. uses the active Vercel deployment URL for preview builds and the production domain for production builds
3. builds Pagefind into `blog/public/pagefind`

The semantic search runtime is served by:

```text
api/search.js
```

### Operational Rule

If you change deployment behavior, update these files together:

- `vercel.json`
- `package.json`
- `scripts/build-search-index.mjs`

Do not reintroduce a separate `blog/package.json` or a second Vercel root unless you intentionally want a monorepo-style split.

### Service Boundaries

The Python app now follows a consistent direction:

- `app/cli/` and `app/main.py` parse args and render operator output
- `app/services/` owns workflow orchestration and service-level decisions
- `app/core/` owns low-level processing, storage, and transformations

Key service groups:
- ingest: `ingest_service.py`, `ingest_runtime.py`, `ingest_validation_service.py`, `ingest_reporting.py`
- publish: `publish_service.py`, `content_service.py`, `site_service.py`, `maintenance_service.py`
- operator utilities: `query_service.py`, `evaluation_service.py`, `book_management_service.py`

Ingest interaction decisions are now typed in `app/services/ingest_interaction.py`; do not reintroduce raw string/tuple prompt contracts.

## Setup

```bash
# Create venv (Python 3.14 recommended, arm64 required for MLX on Apple Silicon)
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt

# Configure API keys in app/.env
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
OPENAI_API_KEY=sk-...
```

## Usage

Start with the **TL;DR Workflow** above. The sections below are detailed options and troubleshooting.

### Processing Books

```bash
# Single-book path: place PDF/EPUB in books/@staging/, then:
python3 scripts/workflow.py add "book-name"           # Recommended wrapper (defaults to --toc)
python3 scripts/workflow.py add "book-name" --no-toc  # Skip manual TOC and rely on extracted structure
python3 scripts/workflow.py add "book-name" --yes     # Wrapper + auto-accept reviewed prompts
python3 scripts/workflow.py add "book-name" --non-interactive  # Wrapper for unattended runs
python3 scripts/workflow.py add "book-name" --gpt --test  # Wrapper for throwaway QA/model comparison
python3 app/main.py "book-name"                       # Core ingest (fast default: notes + index, no embeddings)
python3 app/main.py "book-name" --toc                 # Use manual TOC from books/toc.txt
python3 app/main.py "book-name" --retry               # Retry failed chunks from previous run
python3 app/main.py "book-name" --enrich              # Full ingest (includes embeddings/vector updates)
python3 app/main.py "book-name" --ocr                 # VLM OCR for scanned/degraded PDFs
python3 app/main.py "book-name" --split               # Split two-page spreads into single pages
python3 app/main.py "book-name" --split --ocr --toc   # Combine for scanned two-page-spread books
python3 app/main.py "book-name" --gem                 # Use Gemini 3 Flash Preview
python3 app/main.py "book-name" --gpt                 # Use GPT-5.2
python3 app/main.py "book-name" --toc --yes           # Auto-accept prompts after reviewing TOC/input
python3 app/main.py "book-name" --toc --non-interactive  # Never prompt; abort if judgment is required
python3 app/main.py "book-name" --gem --test          # Benchmark/throwaway QA only (notes-only, no concepts/index updates)
python3 app/main.py "book-name" --gpt --test          # Benchmark/throwaway QA only (notes-only, no concepts/index updates)
```

`python3 scripts/workflow.py add` forwards to `app/main.py`, but it defaults to `--toc`. Use `--no-toc` if you want the wrapper without manual TOC guidance.

### Batch Processing Books

Batch ingest processes multiple books in one run while keeping each book's source files and TOC separate.

Use one folder per book:

```text
books/
  batches/
    digital-cash/
      Digital Cash.epub
      toc.txt
    mirror-worlds/
      Mirror Worlds.pdf
      toc.txt
```

Create a manifest that points each book slug to its folder:

```json
[
  {
    "book": "digital cash",
    "source_dir": "books/batches/digital-cash"
  },
  {
    "book": "mirror worlds",
    "source_dir": "books/batches/mirror-worlds"
  }
]
```

Then run either:

```bash
python3 scripts/workflow.py add --batch-manifest books/batch-ingest.json
python3 app/main.py --batch-manifest books/batch-ingest.json --toc
```

Notes:
- `source_dir` should contain only the files for that one book plus an optional `toc.txt`
- the wrapper defaults to `--toc`, so it will automatically use `source_dir/toc.txt` when present
- `app/main.py` only infers `source_dir/toc.txt` when you pass `--toc`
- if you want to override the inferred TOC path, add `"toc_path": "relative/or/absolute/path.txt"` to a manifest entry
- batch runs process books in manifest order and serialize writes to `notes/`, `index/`, concepts, and vectors

**When to use `--ocr`:** For scanned or degraded PDFs where standard text extraction produces garbled output. Uses Granite-Docling VLM running locally via MLX (~6 sec/page on Apple Silicon).

**PDF extractor default:** Standard PDF extraction now prefers `PyMuPDF4LLM` on macOS/Apple Silicon because standard Docling extraction can crash in the local MLX/Metal stack on that platform. You can override the order with `SUMMARIZER_PDF_EXTRACTOR=docling` or `SUMMARIZER_PDF_EXTRACTOR=pymupdf`.

**When to use `--split`:** For PDFs where each page contains two book pages side by side (common with scanned old books). Crops each PDF page into left and right halves before extraction.

**When to use `--yes`:** When you have already reviewed the input conditions yourself, such as after updating `books/toc.txt` for a single-book run or `toc.txt` inside a batch book folder, and want the run to continue without confirmation prompts.

**When to use `--non-interactive`:** For automation, agents, or strict unattended runs. Safe confirmations proceed automatically, but cases requiring human judgment abort instead of prompting.

**Output:**
- `notes/book-name.md` - Human-readable chapter outlines
- `index/book-name.json` - Structured claims with concepts/entities
- `index/_concepts.json` - Global concept registry

In core mode (default), embeddings are skipped for speed/cost. Populate or repair vectors later with:

```bash
python3 scripts/reconcile_vectors.py --apply-all
```

Performance tuning env vars:

```bash
INGEST_CONCURRENCY=2                 # Optional parallel chunk processing (default: 1)
SMART_CHUNK_MIN_TOKENS=25000         # Lower bound for smart text chunking
SMART_CHUNK_MAX_TOKENS=60000         # Upper bound for smart text chunking
SMART_CHUNK_TARGET_OUTPUT_TOKENS=12000  # Target output budget used by smart chunking
ANTHROPIC_LONG_CONTEXT_SINGLE_REQUEST_TOKENS=350000   # Sonnet 4.6 single-request budget
ANTHROPIC_LONG_CONTEXT_SMART_CHUNK_MAX_TOKENS=150000  # Sonnet 4.6 chunk cap for dense books
ANTHROPIC_LONG_CONTEXT_TARGET_OUTPUT_TOKENS=16000     # Sonnet 4.6 output target per chunk
ANTHROPIC_LONG_CONTEXT_PLANNING_MIN_TOKENS=400000     # Whole-book planning pass threshold
ANTHROPIC_LONG_CONTEXT_PLANNING_MAX_OUTPUT_TOKENS=4096  # Planner output budget
```

Recommendation: start with `INGEST_CONCURRENCY=2` on large books. This preserves ordering and content fidelity while reducing total elapsed time on multi-chunk runs.

For extra-long Sonnet 4.6 books with a usable TOC, ingest now runs a whole-book planning pass before chunked summarization. The planner asks Sonnet to group consecutive chapters and emit exact boundary anchors, then the real chunk requests are built from that plan. If the plan cannot be parsed or the anchors cannot be applied locally, ingest falls back to the normal chapter-aware chunker.

In `--test` mode, output is notes-only and written to `notes/book-name.gem.md` (for `--gem`), `notes/book-name.gpt.md` (for `--gpt`), or `notes/book-name.test.md` (default provider).

Important: `--test` is not a cheap preflight for a book you intend to keep. It still pays almost the full extraction + model cost, but skips canonical outputs like `index/book-name.json`, concept updates, and vector/embedding work. Use it for model comparison, throwaway QA, or debugging questionable inputs, not as the default step before a normal ingest.

Each run prints a `Cost Estimate` section at the end using API-reported token usage and configured per-model pricing in `app/config.py`. Anthropic chunked runs now report prompt-cache writes/reads separately when the API returns them.

### Model Comparison Tests

Use `--test` for model benchmarking or throwaway QA runs when you explicitly do not want to touch canonical outputs.

```bash
# Baseline (Sonnet default provider)
python3 app/main.py "book-name" --test

# Gemini test
python3 app/main.py "book-name" --gem --test

# GPT test
python3 app/main.py "book-name" --gpt --test
```

Test outputs:
- `notes/book-name.test.md` (default/Sonnet)
- `notes/book-name.gem.md`
- `notes/book-name.gpt.md`

Quick text comparison examples:

```bash
wc -l notes/book-name.test.md notes/book-name.gem.md notes/book-name.gpt.md
diff -u notes/book-name.test.md notes/book-name.gpt.md | less
```

Do not use `--test` as the normal preflight for a book you intend to publish unless you are willing to rerun the expensive model pass afterward. Successful `--test` runs are not currently promotable into canonical `notes/` + `index/` outputs.

To refresh test models or pricing later, update `ANTHROPIC_MODEL_ID`, `GEMINI_MODEL_ID`, `GPT_MODEL_ID`, and `MODEL_PRICING_USD_PER_MILLION` in `app/config.py`.

### Integrity Checks and Low-Cost Repairs

Use this workflow to repair vector/index drift without rerunning full summarization.

```bash
# 1) Integrity gate (fails on structural issues)
python3 scripts/check_integrity.py

# 2) Audit vector/index parity (no writes)
python3 scripts/reconcile_vectors.py

# 3) Apply low-cost repair (reuses existing embeddings; no LLM summarization)
python3 scripts/reconcile_vectors.py --apply

# 4) One-command full repair (recommended if you don't want to remember extra flags)
python3 scripts/reconcile_vectors.py --apply-all

# 5) Target one book (substring match on slug/title)
python3 scripts/reconcile_vectors.py --apply-all --book "reality of being"
```

What `reconcile_vectors.py --apply` does:
- Rebuilds claim rows from `index/*.json` with current IDs + metadata
- Reuses existing claim/quote vectors from `index/vectors.db` when possible
- Replaces per-book slices to prevent silent duplicate accumulation
- Rebuilds concept registry coverage from indexed claim concepts
- Removes stale concept book references for deleted/renamed books

What `reconcile_vectors.py --apply-all` adds:
- Everything in `--apply`
- Generates embeddings for unmatched claims/quotes so books are less likely to be skipped

When to rerun `app/main.py` for a book:
- Reconcile reports unmatched claims and you do not use `--apply-all`
- The source summary itself is low quality or structurally broken
- You intentionally want fresh summaries/concepts, not just vector/data repair

If you want to discard a problematic legacy book entirely:

```bash
python3 app/cli/delete_book.py "book-slug" --dry-run
python3 app/cli/delete_book.py "book-slug"
python3 app/main.py "book-slug"
```

After local repair/re-index, sync to Neon Postgres:

```bash
python3 scripts/migrate-vectors.py
```

### Publishing

```bash
python3 scripts/workflow.py smoke                      # Recommended pre-ship integration check
python3 scripts/workflow.py publish                    # Fast publish (includes integrity + backlog report)
python3 scripts/workflow.py publish --reconcile reuse  # Publish + reuse-only repair
python3 scripts/workflow.py publish --reconcile full   # Publish + full repair (--apply-all)
python3 scripts/workflow.py publish --sync-vectors     # Publish + sync vectors to Postgres
python3 scripts/workflow.py publish --skip-integrity   # Skip integrity gate before build
python3 scripts/workflow.py ship                       # Publish, then commit/push from main
python3 scripts/workflow.py ship --allow-preview       # Publish, then commit/push a non-main branch for preview only
python3 scripts/workflow.py ship --deploy-production   # Publish, then commit/push and deploy current worktree to Vercel production
python3 scripts/workflow.py ship --no-gpg-sign         # Publish, commit without GPG signing, then ship
python3 scripts/workflow.py ship --reconcile full      # Repair, publish, then ship
python3 app/cli/publish.py publish                     # Direct publish CLI
python3 app/cli/publish.py publish --reconcile reuse   # Direct CLI with vector repair
python3 app/cli/publish.py publish --sync-vectors      # Direct CLI with Postgres sync
python3 app/cli/publish.py publish --skip-integrity    # Direct CLI without integrity gate
python3 app/cli/publish.py serve                       # Local dev at http://localhost:1313/
python3 app/cli/publish.py serve --port 1314           # Local dev on a custom port
```

Default `publish` tolerates expected vector lag from core ingest and still blocks on structural data issues.

Wrapper flags:

- `python3 scripts/workflow.py publish --reconcile {none,reuse,full}` runs vector/index repair before the build
- `python3 scripts/workflow.py publish --sync-vectors` migrates local vectors to Postgres after the build
- `python3 scripts/workflow.py publish --skip-integrity` bypasses `scripts/check_integrity.py`
- `python3 scripts/workflow.py ship ...` accepts the same publish flags, then stages, commits, and pushes
- `python3 scripts/workflow.py ship` refuses to run silently from non-`main` branches unless you choose `--allow-preview` or `--deploy-production`
- `python3 scripts/workflow.py ship --allow-preview` explicitly ships a preview deployment from a non-production branch
- `python3 scripts/workflow.py ship --deploy-production` pushes the branch, then runs `npx vercel deploy --prod --yes` from the linked repo
- `python3 scripts/workflow.py ship --no-gpg-sign` bypasses Git commit signing when local pinentry/GPG is unavailable

Direct CLI flags:

- `python3 app/cli/publish.py publish --reconcile {none,reuse,full}` matches the wrapper repair modes
- `python3 app/cli/publish.py publish --sync-vectors` syncs vectors after a successful build
- `python3 app/cli/publish.py publish --skip-integrity` skips the pre-build integrity gate
- `python3 app/cli/publish.py serve --port 1314` changes the local Hugo dev port

Push to `main` for automatic Vercel production deployment. Preview deployments now keep their own deployment URL for internal navigation instead of pointing back at production.

### Smoke Test

Run this before pushing structural changes:

```bash
python3 scripts/workflow.py smoke
```

It verifies:

- ingest/publish/workflow CLIs still load
- `api/search.js` still parses
- `publish` succeeds on current data
- `npm run vercel-build` succeeds from repo root
- expected outputs still exist in `blog/public/`

### Semantic Search

The site includes a semantic search API for natural language queries:

```
GET /api/search?q=how+were+stories+preserved+before+writing
GET /api/search?q=your+query&limit=20&book=orality-and-literacy
```

**Setup (one-time):**
1. Add Neon Postgres via Vercel Marketplace (auto-adds `POSTGRES_URL`)
2. Run schema in Neon console (see `scripts/migrate-vectors.py` for SQL)
3. Add `OPENAI_API_KEY` to Vercel env vars
4. Optional but recommended: set `ALLOWED_ORIGINS` to a comma-separated list of trusted site origins for `/api/search`
5. Migrate vectors: `python scripts/migrate-vectors.py`

## Project Structure

```
Summarizer/
├── app/
│   ├── core/           # Processing modules
│   │   ├── stager.py           # File discovery, PDF/EPUB routing, page splitting
│   │   ├── manifest.py         # Claude API request generation
│   │   ├── monitor.py          # API calls, response validation
│   │   ├── exporter.py         # Dual output: notes + index
│   │   ├── embedder.py         # OpenAI embeddings
│   │   ├── vector_store.py     # SQLite vector storage
│   │   └── concept_registry.py # Concept normalization
│   ├── cli/            # Thin CLI entrypoints and report rendering
│   ├── services/       # Workflow orchestration + service-layer helpers
│   ├── main.py         # Ingest entry point
│   └── config.py       # Model config, prompts
├── api/
│   └── search.js       # Semantic search serverless function
├── scripts/
│   ├── build-search-index.mjs  # Pagefind index builder
│   ├── check_integrity.py      # Integrity gate for index/vectors/concepts consistency
│   ├── reconcile_vectors.py    # Low-cost vector/metadata repair without full re-summarization
│   └── migrate-vectors.py      # SQLite → Neon migration
├── books/@staging/     # Backward-compatible single-book input
├── books/batches/      # Optional batch ingest folders (one folder per book)
├── notes/              # Generated markdown
├── index/              # Structured data + vectors
├── blog/               # Hugo source + derived public output
└── vercel.json         # Vercel project config
```

## Manual TOC

If automatic TOC extraction fails (<50% match), provide a manual TOC:

```
Part One: Title
    Chapter Name
    Another Chapter
Part Two: Title
    More Chapters
```

Rules: Parts at start of line with "Part", chapters indented 2+ spaces.

Single-book runs read manual TOC from `books/toc.txt` when you pass `--toc`.

Batch runs should put `toc.txt` inside each book folder referenced by `source_dir`, for example:

```text
books/batches/digital-cash/toc.txt
```

If needed, a batch manifest entry can override that default with `toc_path`.

In interactive runs, low-match TOC review now uses typed decisions internally:
- proceed
- provide manual TOC
- retry after correcting input
- abort

From the operator side, the CLI behavior is unchanged; this note matters if you change the ingest interaction code.

## Security

- Book names validated: `[a-zA-Z0-9\s_-]{1,100}`, no path traversal
- API keys from env vars only, never committed
- `/api/search` only serves browser origins explicitly allowed by `ALLOWED_ORIGINS` or the active Vercel deployment URLs
- Local editor/agent settings and deployment logs are kept out of version control
- GitHub Actions runs scheduled dependency audits, CodeQL analysis, and PR dependency review
- Static site output = minimal attack surface

## Public release checklist

- Removed tracked local-only artifacts before publication, including Claude local settings and a Vercel build log
- Removed unused upstream theme example content that carried sample contact info and local filesystem paths
- Kept runtime credentials out of git and standardized the public release on documented env vars only
- Replaced owner-specific site metadata with generic public-release defaults
- Published the public repository from a fresh-history snapshot so private repo history is not exposed
