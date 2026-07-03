import os
import sys
import argparse

# Add project root to Python path to enable app package imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config import (
    ANTHROPIC_MODEL_ID,
    CODEX_MODEL_ID,
    GEMINI_MODEL_ID,
    GPT_MODEL_ID,
)
from app.cli.ingest_prompter import (
    AutoYesIngestPrompter,
    NonInteractiveIngestPrompter,
    TerminalIngestPrompter,
)
from app.services.ingest_service import IngestOptions, load_batch_request, run_batch_ingest, run_ingest

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Book Summarizer - Generate chapter outlines')
    parser.add_argument('book', nargs='?',
                        help='Name for the book (used for output filename in notes/)')
    parser.add_argument('--batch-manifest',
                        help='Path to JSON manifest describing multiple books and source folders')
    parser.add_argument('--toc', action='store_true',
                        help='Use manual TOC from books/toc.txt for chapter guidance')
    parser.add_argument('--retry', action='store_true',
                        help='Retry only failed chunks from previous run (uses cached results)')
    parser.add_argument('--ocr', action='store_true',
                        help='Use Granite-Docling VLM for PDF extraction (better for scanned/degraded PDFs)')
    parser.add_argument('--split', action='store_true',
                        help='Split two-page spreads (each PDF page cropped into left/right halves)')
    parser.add_argument('--gem', action='store_true',
                        help=f'Use Gemini model ({GEMINI_MODEL_ID}) instead of Anthropic')
    parser.add_argument('--gpt', action='store_true',
                        help=f'Use OpenAI model ({GPT_MODEL_ID}) instead of Anthropic')
    parser.add_argument('--codex', action='store_true',
                        help=f'Use local Codex exec model ({CODEX_MODEL_ID}) instead of Anthropic')
    parser.add_argument('--test', action='store_true',
                        help='Benchmark/QA mode: save notes-only output with provider suffix; skip canonical index, embeddings, and concept updates')
    parser.add_argument('--enrich', action='store_true',
                        help='Enable embedding/vector enrichment during this run (slower; core mode skips this)')
    parser.add_argument('--no-semantic-merge', action='store_true',
                        help='Disable embedding-based concept semantic merge (keeps exact/alias concept matching only)')
    parser.add_argument('--yes', action='store_true',
                        help='Auto-accept ingest prompts (useful when TOC/chunking has already been reviewed)')
    parser.add_argument('--non-interactive', action='store_true',
                        help='Never prompt; proceed on safe confirmations and abort when human judgment would be required')
    return parser


def main():
    """CLI entry point for the book summarizer."""
    print("Starting Book Summarizer...", flush=True)
    parser = build_parser()
    args = parser.parse_args()
    if bool(args.book) == bool(args.batch_manifest):
        parser.error('provide either a single book name or --batch-manifest')
    if args.yes and args.non_interactive:
        parser.error('--yes and --non-interactive are mutually exclusive')
    options = IngestOptions(
        book=args.book or "",
        use_manual_toc=args.toc,
        retry_mode=args.retry,
        use_vlm=args.ocr,
        split_pages=args.split,
        use_gemini=args.gem,
        use_gpt=args.gpt,
        use_codex=args.codex,
        test_mode=args.test,
        enable_enrichment=args.enrich and not args.test,
        enable_semantic_merge=not args.no_semantic_merge,
    )
    if args.yes:
        prompter = AutoYesIngestPrompter()
    elif args.non_interactive:
        prompter = NonInteractiveIngestPrompter()
    else:
        prompter = TerminalIngestPrompter()
    if args.batch_manifest:
        try:
            batch_request = load_batch_request(args.batch_manifest, options)
        except ValueError as e:
            parser.error(str(e))
        success = run_batch_ingest(batch_request, prompter=prompter)
    else:
        success = run_ingest(options, prompter=prompter)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
