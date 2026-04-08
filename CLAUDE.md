# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A PDF/EPUB book summarization system that generates detailed chapter outlines with structured claims for cross-book querying. Uses Anthropic Claude for summarization and OpenAI for embeddings. Publishes as a Hugo static site on Vercel.

## Commands

### Processing Books
```bash
# Setup (Python 3.14 recommended, requires arm64 for MLX on Apple Silicon)
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt

# Process a book (place PDF/EPUB in books/@staging/ first)
python3 -m app.main "book-name"                      # Process book
python3 -m app.main "book-name" --toc                 # Use manual TOC from books/toc.txt
python3 -m app.main "book-name" --retry               # Retry only failed chunks from previous run
python3 -m app.main "book-name" --ocr                 # VLM OCR for scanned/degraded PDFs
python3 -m app.main "book-name" --split               # Split two-page spreads into single pages
python3 -m app.main "book-name" --split --ocr --toc   # Combine flags as needed
python3 -m app.main "book-name" --gem                 # Use Gemini 3 Flash Preview
python3 -m app.main "book-name" --gpt                 # Use GPT-5.2
python3 -m app.main "book-name" --gem --test          # Notes-only Gemini comparison run
python3 -m app.main "book-name" --gpt --test          # Notes-only GPT comparison run
```

### Publishing
```bash
python3 app/cli/publish.py publish     # Sync notes to blog posts
python3 app/cli/publish.py serve       # Local dev server at http://localhost:1313/
```

### Book Management
```bash
python3 app/cli/delete_book.py "book-name"             # Remove book from notes + index
python3 app/cli/rename_book.py "old-name" "new-name"   # Rename book across all files
python3 app/cli/evaluate.py "book-name"                # Analyze index quality/stats
```

## Architecture

### Data Flow Pipeline (v2.1)
```
books/@staging/ (PDF/EPUB)
       │
       ▼
    Stager → Manifest → Monitor → Exporter
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              notes/*.md      index/*.json    index/vectors.db
                    │                │                │
                    ▼                │                ▼
           Publisher → blog/         │         Neon Postgres
                    │                │         (pgvector)
                    ▼                ▼                │
            Vercel (auto-deploy)                     │
                    │                                │
                    └──────── /api/search ◄──────────┘
```

### Core Modules (app/core/)

| Module | Purpose |
|--------|---------|
| `stager.py` | Discovers files, routes to PDF/EPUB processors, estimates tokens |
| `epub_processor.py` | Extracts semantic structure from EPUB, parses TOC, chunks by chapters |
| `pdf_processor.py` | PDF text extraction via Docling (IBM) or PyMuPDF4LLM, VLM OCR via Granite-Docling for scanned PDFs, falls back to base64 |
| `manifest.py` | Creates Claude API requests with unified prompt, smart chunking based on chapter density |
| `monitor.py` | Sequential API calls, validates JSON responses, auto-repairs malformed JSON, detects hallucinations |
| `exporter.py` | Dual output: markdown notes + JSON index, deduplicates chapters, generates embeddings |
| `concept_registry.py` | Normalizes concept tags across books, tracks usage |
| `embedder.py` | OpenAI text-embedding-3-small for claims and concepts |
| `vector_store.py` | SQLite storage for embeddings (local development) |
| `publisher.py` | Converts notes to Hugo posts, generates Pagefind search index |

### Search System

Two search modes available on the site:

| Type | Technology | Use Case |
|------|------------|----------|
| **Text Search** | Pagefind | Exact keyword matching across claims |
| **Semantic Search** | OpenAI + pgvector | Natural language queries (e.g., "how were stories preserved before writing") |

**Semantic Search Architecture:**
- `api/search.js` - Vercel serverless function
- Neon Postgres with pgvector extension (via Vercel Marketplace)
- OpenAI `text-embedding-3-small` for query embedding
- Cosine similarity search with `<=>` operator

**API Usage:**
```
GET /api/search?q=your+query           # Basic search (10 results)
GET /api/search?q=your+query&limit=20  # Custom limit (max 50)
GET /api/search?q=your+query&book=slug # Filter by book
```

**Migration:** Run `scripts/migrate-vectors.py` to sync local SQLite vectors to Neon Postgres.

### Key Design Decisions

- **Unified Pipeline (v2.1)**: Single Claude call produces both human-readable outlines and machine-readable claims with concepts/entities
- **Sequential Processing**: Uses Claude Messages API sequentially (not batch) for real-time feedback
- **Smart Chunking**: Adapts chunk size based on chapter density (more chapters = smaller chunks to prevent output truncation)
- **Token Optimization**: Combines small files into single requests; chunks large files at 180k tokens
- **Two Content Types**: EPUB → Markdown (cheaper), PDF → text extraction with base64 fallback
- **VLM OCR Pipeline**: `--ocr` uses Granite-Docling-258M via MLX for scanned/degraded PDFs (~6 sec/page on Apple Silicon), processes large PDFs in 50-page chunks with progress logging
- **PDF extractor default**: On macOS/Apple Silicon, standard PDF extraction prefers PyMuPDF4LLM by default because standard Docling extraction can crash in the MLX/Metal stack. Override with `SUMMARIZER_PDF_EXTRACTOR=docling` if needed.
- **Page Splitting**: `--split` crops two-page-per-page scanned PDFs into single pages before extraction (temp file auto-cleaned)
- **Incremental Embeddings**: Only embeds new concepts, skips already-embedded ones
- **Deduplication**: Merges duplicate chapters during export, combining unique bullet points
- **JSON Auto-repair**: Iteratively fixes unescaped quotes in LLM JSON responses

### Configuration

- **Python**: 3.14 (recommended for MLX Apple Silicon support)
- **Summarization Models**: `claude-sonnet-4-6` (default), `gemini-3-flash-preview` (`--gem`), or `gpt-5.2` (`--gpt`)
- **VLM OCR Model**: Granite-Docling-258M via MLX (local, `--ocr` flag)
- **Embedding Model**: `text-embedding-3-small` (OpenAI, 1536 dimensions)
- **Token limit**: 180,000 tokens per request
- **Local API Keys**: Load from `app/.env` as `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` (for `--gem`), and `OPENAI_API_KEY`
- **Vercel Env Vars**: `POSTGRES_URL` (Neon integration), `OPENAI_API_KEY` (manual)

## Key Locations

- `books/@staging/` - Input files (PDF/EPUB)
- `notes/` - Generated markdown summaries
- `index/` - Structured JSON index + vectors.db (gitignored)
- `index/_concepts.json` - Global concept registry
- `blog/content/books/` - Hugo posts
- `blog/layouts/` - Custom Hugo templates (Shibui theme)
- `api/` - Vercel serverless functions (search.js)
- `scripts/` - Build and migration scripts
- `app/logs/` - Processing logs

## Output Schema (v2.1)

Each book produces:
1. **`notes/{book}.md`** - Human-readable chapter outlines
2. **`index/{book}.json`** - Structured claims with concepts, entities, sub_points
3. **`index/_concepts.json`** - Updated global concept registry
4. **`index/vectors.db`** - Claim/concept embeddings (SQLite, gitignored)

## Input Validation

Book names are restricted to `[a-zA-Z0-9\s_-]{1,100}` with path traversal prevention (blocks `..`, `/`, `\\`).
