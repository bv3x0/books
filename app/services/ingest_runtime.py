"""
Bootstrap helpers for ingest workflows.
"""

from __future__ import annotations

import os
import re
import shutil

from dotenv import load_dotenv

from app.config import (
    ANTHROPIC_MODEL_ID,
    CODEX_MODEL_ID,
    CONCEPTS_PATH,
    GEMINI_MODEL_ID,
    GPT_MODEL_ID,
)
from app.services.ingest_models import (
    IngestOptions,
    IngestRuntime,
    IngestSourcePaths,
    ProviderSettings,
)


def validate_book_name(name: str) -> str:
    """Validate book name to prevent path traversal and unsafe filenames."""
    if not name or not name.strip():
        raise ValueError("Book name cannot be empty.")

    name = name.strip()
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError("Book name cannot contain path separators or '..'")
    if not re.match(r"^[a-zA-Z0-9\s_-]+$", name):
        raise ValueError(
            "Invalid book name. Only letters, numbers, spaces, hyphens, and underscores are allowed."
        )
    if len(name) > 100:
        raise ValueError("Book name too long (max 100 characters).")
    return name


def resolve_provider_settings(options: IngestOptions) -> ProviderSettings:
    """Resolve provider/model selection and output suffixes from CLI options."""
    selected_providers = [
        bool(options.use_gemini),
        bool(options.use_gpt),
        bool(options.use_codex),
    ]
    if sum(selected_providers) > 1:
        raise ValueError("--gem, --gpt, and --codex are mutually exclusive.")

    if options.use_codex:
        provider = "codex"
        model_id = CODEX_MODEL_ID
    elif options.use_gpt:
        provider = "openai"
        model_id = GPT_MODEL_ID
    elif options.use_gemini:
        provider = "gemini"
        model_id = GEMINI_MODEL_ID
    else:
        provider = "anthropic"
        model_id = ANTHROPIC_MODEL_ID

    notes_suffix = ""
    if options.test_mode and provider == "gemini":
        notes_suffix = ".gem"
    elif options.test_mode and provider == "openai":
        notes_suffix = ".gpt"
    elif options.test_mode and provider == "codex":
        notes_suffix = ".codex"
    elif options.test_mode:
        notes_suffix = ".test"

    cache_suffix = f".{provider}"
    if options.test_mode:
        cache_suffix += ".test"

    require_openai = (provider == "openai") or options.enable_enrichment
    return ProviderSettings(
        provider=provider,
        model_id=model_id,
        notes_suffix=notes_suffix,
        cache_suffix=cache_suffix,
        require_openai=require_openai,
    )


def load_ingest_env() -> None:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


def initialize_client(provider: str):
    """Initialize provider client and return (client, google_api_key)."""
    client = None
    google_api_key = None

    print("\nLoading API client...", flush=True)
    if provider == "anthropic":
        print("  - Importing anthropic module...", flush=True)
        import anthropic

        print("  - Module imported", flush=True)
        print("  - Initializing Anthropic client...", flush=True)
        api_key = os.getenv("ANTHROPIC_API_KEY")
        client = anthropic.Anthropic(api_key=api_key, timeout=3600.0)
        print("  - Client initialized", flush=True)
    elif provider == "gemini":
        google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        print("  - Gemini mode selected (using direct REST calls)", flush=True)
    elif provider == "codex":
        if not shutil.which("codex"):
            raise RuntimeError("Missing codex executable on PATH")
        print("  - Codex mode selected (using local codex exec)", flush=True)
    else:
        print("  - Importing OpenAI module...", flush=True)
        from openai import OpenAI

        print("  - Module imported", flush=True)
        print("  - Initializing OpenAI client...", flush=True)
        api_key = os.getenv("OPENAI_API_KEY")
        client = OpenAI(api_key=api_key, timeout=3600.0)
        print("  - Client initialized", flush=True)

    return client, google_api_key


def initialize_runtime(
    book_name: str,
    options: IngestOptions,
    settings: ProviderSettings,
    source_paths: IngestSourcePaths,
) -> IngestRuntime:
    """Initialize provider client plus per-book processing components."""
    client, google_api_key = initialize_client(settings.provider)
    print("Book Summarizer App Initialized.", flush=True)
    print("  - Loading core modules...", flush=True)

    from app.core.manifest import Manifest
    from app.core.monitor import Monitor
    from app.core.stager import Stager

    print("  - Core modules loaded", flush=True)

    stager = Stager(
        client,
        use_manual_toc=bool(source_paths.toc_path),
        use_vlm=options.use_vlm,
        split_pages=options.split_pages,
        input_dir=source_paths.source_dir,
        toc_path=source_paths.toc_path,
    )
    manifest = Manifest(client, use_unified=True, model_id=settings.model_id)
    monitor = Monitor(
        client,
        book_name=book_name,
        provider=settings.provider,
        google_api_key=google_api_key,
        cache_suffix=settings.cache_suffix,
    )

    return IngestRuntime(
        client=client,
        google_api_key=google_api_key,
        stager=stager,
        manifest=manifest,
        monitor=monitor,
    )


def initialize_concept_registry(options: IngestOptions):
    """Initialize shared concept registry state for the serialized write phase."""
    if options.test_mode:
        print("  - Test mode: skipping concept registry initialization", flush=True)
        return None, False

    from app.core.concept_registry import ConceptRegistry

    enable_semantic_merge = options.enable_semantic_merge
    semantic_merge_max_registry = int(os.getenv("SEMANTIC_MERGE_MAX_REGISTRY", "5000"))

    print("  - Initializing concept registry...", flush=True)
    concept_registry = ConceptRegistry(CONCEPTS_PATH)
    print(
        f"  - Concept registry loaded ({len(concept_registry.concepts)} existing concepts)",
        flush=True,
    )

    if enable_semantic_merge and len(concept_registry.concepts) > semantic_merge_max_registry:
        enable_semantic_merge = False
        print(
            "  - Semantic merge auto-disabled "
            f"(registry {len(concept_registry.concepts):,} > limit {semantic_merge_max_registry:,})",
            flush=True,
        )
        print(
            "    Set SEMANTIC_MERGE_MAX_REGISTRY higher to re-enable for large registries.",
            flush=True,
        )

    if enable_semantic_merge and not options.enable_enrichment:
        enable_semantic_merge = False
        print(
            "  - Semantic merge disabled in core mode (use --enrich to enable embedding-based merge)",
            flush=True,
        )

    if not enable_semantic_merge:
        print(
            "  - Concept registry semantic merge disabled (exact/alias matching only)",
            flush=True,
        )

    return concept_registry, enable_semantic_merge


def initialize_exporter(
    book_name: str,
    options: IngestOptions,
    settings: ProviderSettings,
    source_paths: IngestSourcePaths,
    concept_registry,
    enable_semantic_merge: bool,
):
    """Initialize exporter for the serialized write phase."""
    from app.core.exporter import Exporter

    exporter = Exporter(
        client=None,
        output_dir=source_paths.source_dir,
        book_name=book_name,
        summary_mode="quick",
        concept_registry=concept_registry,
        use_unified=True,
        enable_embeddings=options.enable_enrichment,
        model_id=settings.model_id,
        export_index=not options.test_mode,
        update_concepts=not options.test_mode,
        notes_suffix=settings.notes_suffix,
        cache_suffix=settings.cache_suffix,
    )

    if (
        enable_semantic_merge
        and concept_registry
        and exporter.embedder
        and not concept_registry.embedder
    ):
        concept_registry.embedder = exporter.embedder
        print("  - Concept registry semantic merge enabled (embedder attached)", flush=True)

    return exporter


def submit_requests(runtime: IngestRuntime, requests: list, retry_mode: bool):
    """Submit batch requests, optionally reusing cached failures."""
    if retry_mode:
        cached_results = runtime.monitor.load_cached_results()
        if not cached_results:
            print("No cached results found. Run without --retry first.", flush=True)
            return None
        failed_indices = runtime.monitor.get_failed_chunk_indices(cached_results)
        if not failed_indices:
            print("No failed chunks to retry. All chunks succeeded previously.", flush=True)
        else:
            print(
                f"Found {len(failed_indices)} failed chunk(s) to retry: {[i + 1 for i in failed_indices]}",
                flush=True,
            )
        return runtime.monitor.submit_job_retry(requests, cached_results)

    return runtime.monitor.submit_job(requests)
