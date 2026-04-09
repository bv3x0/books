import os

# Configuration Constants
ANTHROPIC_MODEL_ID = "claude-sonnet-4-6"
GEMINI_MODEL_ID = "gemini-3-flash-preview"
GPT_MODEL_ID = "gpt-5.2"
# Backward-compatible default model constant
MODEL_ID = ANTHROPIC_MODEL_ID

# Pricing table (USD per 1M tokens). Keep this updated if provider pricing changes.
MODEL_PRICING_USD_PER_MILLION = {
    ANTHROPIC_MODEL_ID: {
        "input": 3.0,
        "cache_write_input": 3.75,
        "cache_read_input": 0.30,
        "output": 15.0,
    },
    # Gemini 3 Flash Preview (standard paid tier, text/image/video)
    GEMINI_MODEL_ID: {"input": 0.50, "output": 3.00},
    # GPT-5.2 text pricing from OpenAI model page
    GPT_MODEL_ID: {"input": 1.75, "cached_input": 0.175, "output": 14.00},
    # Previous Gemini-lite experiment pricing
    "gemini-3.1-flash-lite-preview": {"input": 0.25, "output": 1.5},
}

# Token threshold for single-request vs chunked processing
# Legacy default assumes a 200k-class input limit. Budget 30k headroom for:
# - Prompt/instructions overhead (~5-8k tokens)
# - Token estimation error (heuristic can underestimate 10-15%)
MAX_TOKENS_SINGLE_REQUEST = 170000
SMART_CHUNK_MIN_TOKENS = int(os.getenv("SMART_CHUNK_MIN_TOKENS", "25000"))
SMART_CHUNK_MAX_TOKENS = int(os.getenv("SMART_CHUNK_MAX_TOKENS", "60000"))
SMART_CHUNK_TARGET_OUTPUT_TOKENS = int(
    os.getenv("SMART_CHUNK_TARGET_OUTPUT_TOKENS", "12000")
)
ANTHROPIC_LONG_CONTEXT_SINGLE_REQUEST_TOKENS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_SINGLE_REQUEST_TOKENS", "350000")
)
ANTHROPIC_LONG_CONTEXT_SMART_CHUNK_MIN_TOKENS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_SMART_CHUNK_MIN_TOKENS", "40000")
)
ANTHROPIC_LONG_CONTEXT_SMART_CHUNK_MAX_TOKENS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_SMART_CHUNK_MAX_TOKENS", "150000")
)
ANTHROPIC_LONG_CONTEXT_TARGET_OUTPUT_TOKENS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_TARGET_OUTPUT_TOKENS", "16000")
)
DEFAULT_REQUEST_MAX_OUTPUT_TOKENS = int(
    os.getenv("DEFAULT_REQUEST_MAX_OUTPUT_TOKENS", "24576")
)
ANTHROPIC_LONG_CONTEXT_REQUEST_MAX_OUTPUT_TOKENS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_REQUEST_MAX_OUTPUT_TOKENS", "32768")
)
ANTHROPIC_LONG_CONTEXT_PLANNING_MIN_TOKENS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_PLANNING_MIN_TOKENS", "400000")
)
ANTHROPIC_LONG_CONTEXT_PLANNING_MAX_TOKENS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_PLANNING_MAX_TOKENS", "900000")
)
ANTHROPIC_LONG_CONTEXT_PLANNING_MIN_CHAPTERS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_PLANNING_MIN_CHAPTERS", "12")
)
ANTHROPIC_LONG_CONTEXT_PLANNING_MAX_OUTPUT_TOKENS = int(
    os.getenv("ANTHROPIC_LONG_CONTEXT_PLANNING_MAX_OUTPUT_TOKENS", "4096")
)
INGEST_CONCURRENCY = max(1, int(os.getenv("INGEST_CONCURRENCY", "1")))
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
BOOKS_DIR = os.path.join(BASE_DIR, "books")
NOTES_DIR = os.path.join(BASE_DIR, "notes")
INDEX_DIR = os.path.join(BASE_DIR, "index")

# Backward-compatible default input folder for single-book ingest.
INPUT_DIR = os.path.join(BOOKS_DIR, "@staging")

# Index paths
VECTORS_DB_PATH = os.path.join(INDEX_DIR, "vectors.db")
CONCEPTS_PATH = os.path.join(INDEX_DIR, "_concepts.json")

# Embedding configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def get_notes_path(book_name):
    """Get the path for a book's summary in the notes directory."""
    return os.path.join(NOTES_DIR, f"{book_name}.md")


def get_index_path(book_name):
    """Get the path for a book's index JSON in the index directory."""
    return os.path.join(INDEX_DIR, f"{book_name}.json")


def get_model_pricing(model_id: str):
    """
    Return pricing dict for model_id as:
      {"input": float, "output": float}
    or None if unknown.
    """
    if not model_id:
        return None

    # Exact match first
    pricing = MODEL_PRICING_USD_PER_MILLION.get(model_id)
    if pricing:
        return pricing

    # Prefix fallback (for versioned model IDs)
    for known_model, known_pricing in MODEL_PRICING_USD_PER_MILLION.items():
        if model_id.startswith(known_model):
            return known_pricing

    return None


def is_anthropic_long_context_model(model_id: str | None) -> bool:
    """Return True for Sonnet 4.6-style long-context models."""
    return bool(model_id and model_id.startswith(ANTHROPIC_MODEL_ID))


def get_single_request_token_limit(model_id: str | None) -> int:
    """Return the safe single-request input budget for a model."""
    if is_anthropic_long_context_model(model_id):
        return ANTHROPIC_LONG_CONTEXT_SINGLE_REQUEST_TOKENS
    return MAX_TOKENS_SINGLE_REQUEST


def get_smart_chunk_settings(model_id: str | None) -> dict[str, int]:
    """Return model-specific chunking defaults."""
    if is_anthropic_long_context_model(model_id):
        return {
            "min_tokens": ANTHROPIC_LONG_CONTEXT_SMART_CHUNK_MIN_TOKENS,
            "max_tokens": ANTHROPIC_LONG_CONTEXT_SMART_CHUNK_MAX_TOKENS,
            "target_output_tokens": ANTHROPIC_LONG_CONTEXT_TARGET_OUTPUT_TOKENS,
        }

    return {
        "min_tokens": SMART_CHUNK_MIN_TOKENS,
        "max_tokens": SMART_CHUNK_MAX_TOKENS,
        "target_output_tokens": SMART_CHUNK_TARGET_OUTPUT_TOKENS,
    }


def get_request_max_output_tokens(model_id: str | None) -> int:
    """Return the default max output budget for ingest requests."""
    if is_anthropic_long_context_model(model_id):
        return ANTHROPIC_LONG_CONTEXT_REQUEST_MAX_OUTPUT_TOKENS
    return DEFAULT_REQUEST_MAX_OUTPUT_TOKENS


def get_chunk_planning_settings(model_id: str | None) -> dict[str, int | bool]:
    """Return planning-pass settings for extra-long books."""
    if is_anthropic_long_context_model(model_id):
        return {
            "enabled": True,
            "min_tokens": ANTHROPIC_LONG_CONTEXT_PLANNING_MIN_TOKENS,
            "max_tokens": ANTHROPIC_LONG_CONTEXT_PLANNING_MAX_TOKENS,
            "min_chapters": ANTHROPIC_LONG_CONTEXT_PLANNING_MIN_CHAPTERS,
            "max_output_tokens": ANTHROPIC_LONG_CONTEXT_PLANNING_MAX_OUTPUT_TOKENS,
        }

    return {
        "enabled": False,
        "min_tokens": 0,
        "max_tokens": 0,
        "min_chapters": 0,
        "max_output_tokens": 0,
    }


# =============================================================================
# UNIFIED ANALYSIS PROMPT - Integrated Pipeline (v2.0)
# =============================================================================
# This prompt produces a single JSON object containing both human-readable
# summary data and machine-readable structured data (claims, concepts, entities)
# in a single pass.


def _get_bisac_categories():
    """Get BISAC categories for the unified prompt."""
    try:
        from app.categories import get_categories_for_prompt

        return get_categories_for_prompt()
    except ImportError:
        return "history, philosophy, religion, political science, social science, psychology, science, biography & autobiography, education, art, literary criticism, economics, technology & engineering, nature, music, performing arts"


def get_unified_analysis_prompt():
    """
    Get the unified analysis prompt that produces JSON output.

    Returns:
        The unified prompt string
    """
    categories = _get_bisac_categories()

    coverage_guidance = """
## CHAPTER COVERAGE

**PHILOSOPHY: Consolidation, NOT omission**
Your goal is to create "enhanced reading notes" that preserve the book's richness while being more concise than raw transcription.

For each chapter:

1. **summary**: 1-2 sentences stating the chapter's central claim and its causal or explanatory logic (thesis statement, not a topic list)

2. **key_points**: 4-8 main points per chapter
   - Short chapters (~500-1500 words): aim for 4-5 points
   - Standard chapters (~1500-3500 words): aim for 5-7 points
   - Long/dense chapters (~3500+ words): aim for 7-8 points

   Each key_point includes:
   - **point**: The main argument (standalone claim - see requirements below)
   - **sub_points**: 2-3 supporting details as objects with "text" and "speaker" fields
   - **concepts**: 2-4 reusable concept tags in snake_case (see tagging guidelines)
   - **entities**: Named people, places, events, works mentioned

**CONSOLIDATION PRIORITIES** (when condensing, preserve in this order):
1. **Core argument** (never skip): The chapter's main thesis
2. **Distinctive evidence** (essential): The 1-2 strongest examples that make the point concrete
3. **Key entities** (important): Names, dates, places that enable cross-referencing
4. **Supporting details** (nice-to-have): Additional examples if space allows
5. **Counterarguments** (nice-to-have): Only if central to the chapter's logic
6. **Preserved quotes** (rare): Only when exact wording is more precise than paraphrase

**CONSOLIDATION RULES:**
- Multiple examples making the same point → keep the strongest 1-2, DON'T omit entirely
- Extended anecdotes → preserve the key insight and memorable details in 1-2 sentences
- Preserve specific names, data points, and quotes that make arguments concrete
- Where a chapter builds on prior argument, include a brief connective clause; where chapters are independent, do not invent continuity

The goal is natural condensation through smart consolidation, NOT aggressive cutting that loses the book's character.
"""

    return f"""Analyze this book and produce a structured JSON response containing both a human-readable summary and machine-readable structured data.

## OUTPUT FORMAT

You must respond with valid JSON only. No markdown, no explanations outside the JSON.

{{
  "book": {{
    "title": "string - exact title",
    "author": "string - author name(s)",
    "year": number or null,
    "thesis": "string - 1-2 sentence central argument",
    "topics": ["array of 5 key topics/themes"],
    "categories": ["1-3 categories from the provided list"]
  }},

  "chapters": [
    {{
      "part": "string or null - Part title if chapter belongs to a Part (e.g., 'Part One: WEATHERMAN')",
      "title": "string - chapter title from source",
      "summary": "string - 1-2 sentences stating the chapter's central claim and its causal or explanatory logic (thesis statement, not a topic list)",
      "pull_quote": "string or null",

      "key_points": [
        {{
          "point": "string - standalone claim (see requirements below)",
          "sub_points": [
            {{"text": "supporting detail, evidence, or example", "speaker": null}},
            {{"text": "exact quote from someone", "speaker": "Name of speaker"}}
          ],
          "concepts": ["2-4 reusable concept tags in snake_case"],
          "entities": {{
            "people": ["named individuals"],
            "places": ["locations, regions, institutions"],
            "events": ["named historical events with dates if given"],
            "works": ["books, papers, artworks cited"]
          }}
        }}
      ]
    }}
  ]
}}

{coverage_guidance}

## PULL QUOTES

For chapters with 6 or more key_points, select one sentence from the source text as a pull_quote — the sentence that best captures the section's central insight or most consequential claim. This should be the sentence a reader would underline.

- Must be verbatim or near-verbatim from the source text
- Must represent the section's core thrust, not a tangential detail
- Should be a complete, self-contained thought
- Null for chapters with fewer than 6 key_points

## KEY POINT REQUIREMENTS

Each key_point's "point" field must be a standalone claim:

Every point should reconstruct argument logic: what is claimed and why/how, not just what topic is discussed.
- Prefer mechanism statements (X leads to Y because Z) over topical description
- State claims directly; avoid meta framing like "The author argues..." or "This chapter shows..."
- Prefer concrete actors and actions over abstract framing language
- Every point must include at least one concrete anchor (named person, place, event, work, date, or explicit mechanism)
- Avoid under-specified one-liners; include enough detail to be useful out of context

1. **STANDALONE**: Understandable without reading the book. Include necessary context.
   - BAD: "This led to the system's collapse"
   - GOOD: "The Quakers' pacifist principles prevented them from defending Pennsylvania against Indian attacks, eventually forcing Quaker leaders to resign from government offices"

2. **SPECIFIC**: Name people, places, mechanisms, or concepts. Avoid vague generalities.
   - BAD: "Education has problems"
   - GOOD: "Schools teach students to confuse process with substance, so that receiving medical treatment becomes equated with health care and attending classes becomes equated with learning"

3. **ATTRIBUTABLE**: The author's argument or interpretation, not common knowledge.
   - BAD: "The American Revolution happened in 1776"
   - GOOD: "The American Revolution was not a unified national uprising but rather six separate regional wars, each fought according to different cultural values"

4. **UNIQUE**: Capture what makes THIS book's perspective distinctive.

5. **QUOTE-PRESERVED**: When a quote articulates a thesis or argument more succinctly than paraphrase could, preserve it with the speaker field set (see QUOTE PRESERVATION section).

## SUB_POINT STRUCTURE

Each sub_point is an object with:
- **text**: The content (supporting detail, evidence, example, or quote)
- **speaker**: Name of who said it (for quotes), or null (for non-quotes)

If speaker is non-null, the text is a direct quote. If speaker is null, it's supporting material.
In sub_points, prefer explicit names when they carry argumentative weight (thinkers, works, institutions, events) over vague pronouns or abstractions.

## QUOTE PRESERVATION

Most chapters need zero quotes. Aim for 0-1 per chapter — only when the quote contains a substantive claim or argument that would be *weaker* as paraphrase.

**THE ONLY REASON TO PRESERVE A QUOTE:** It articulates a thesis, argument, or position more precisely or succinctly than you could by paraphrasing.
- PRESERVE: "I no longer believe that freedom and democracy are compatible" (Thiel) — this IS the argument
- PRESERVE: "Schools teach students to confuse process with substance" (Illich) — sharper than any paraphrase
- SKIP: "Welcome to the schmattes factory" — flavor, no substance
- SKIP: "I should have told him to go fuck himself" — attitude, not argument
- SKIP: "Oh, my biographer is here. Be careful" — conversational color
- SKIP: "God does not play dice" — famous but not advancing the book's argument

**THE TEST:** If you can paraphrase it into a sub_point without losing any information, do that instead. Only quote when the exact wording IS the point.

**DO NOT QUOTE:**
- Personality, humor, or atmosphere (even if vivid)
- Conversational remarks or narrative beats
- Famous sayings used as decoration
- Anything that works equally well as paraphrase

**HOW TO FORMAT (when a quote passes the test):**
- Set "speaker" to who said it
- Set "text" to the exact or near-exact wording

## CONCEPTS vs ENTITIES

These are complementary - the same content often needs BOTH:

**CONCEPTS** = Reusable academic categories that connect ideas across books (snake_case)
- Ask: "Could this concept appear in a completely different book on a different topic?"
- Aim for 2-4 concepts per claim
- Prefer broad, reusable categories over book-specific terminology

**GOOD concepts** (reusable across many books):
- `oral_tradition`, `institutional_critique`, `colonial_economics`, `collective_memory`
- `social_hierarchy`, `religious_reform`, `technological_displacement`, `cultural_identity`
- `epistemic_authority`, `narrative_construction`, `political_legitimacy`

**BAD concepts** (too specific, will never match another book):
- `yankee_culture` → use `regional_culture` instead
- `plantation_economy` → use `colonial_economics` or `slave_economy` instead
- `homeric_composition` → use `oral_tradition` + entity `Homer` instead
- `puritan_education` → use `religious_education` + entity context instead

**ENTITIES** = Specific named instances (proper nouns)
- Ask: "Is this a unique, named thing?"
- **people**: "Einstein", "Thomas Jefferson", "Milman Parry"
- **places**: "Harvard", "Pennsylvania", "Ancient Greece"
- **events**: "World War II", "Eranos Conference 1956"
- **works**: "The Iliad", "Notes on Virginia", "Answer to Job"

**TAGGING THE SAME CONTENT:**
- Claim about Jefferson's slavery views → concept: `slave_economy` + entity: `Thomas Jefferson`
- Claim about Musk's childhood → concept: `childhood_trauma` + entity: `Elon Musk`
- Claim about oral poetry at Harvard → concept: `oral_tradition` + entities: `Harvard`, `Milman Parry`

**COMMON MISTAKES:**
- Don't create person-specific concepts like `einstein_physics` → use concept `theoretical_physics` + entity `Einstein`
- Don't put abstract ideas in entities → `democracy` is a concept, not an entity
- Don't create near-duplicates: pick ONE of `cultural_transformation` / `cultural_transition` / `social_transformation` — use `cultural_change` for all
- Don't make concepts so specific they can only match one book — specificity belongs in entities, not concepts

## CATEGORY SELECTION

Select 1-3 categories from this list:
{categories}

Prefer more specific categories over general ones when both fit.

## IMPORTANT RULES

1. Follow the book's actual chapter structure - use real chapter titles
2. Do not invent content not in the source
3. Do not include publisher info, copyright pages, or promotional material
4. Ensure JSON is valid - properly escape quotes, no trailing commas
5. Cover all chapters present in the provided text/chunk - do not stop partway through
6. Conclusions, epilogues, afterwords, and final chapters are not optional - when present in the provided text/chunk, cover them with the same depth as regular chapters

## ANTI-HALLUCINATION RULE

If the document contains ONLY front matter (title page, copyright, table of contents) with NO actual chapter content:
- Return a minimal JSON with book metadata and empty chapters array
- Do NOT generate content based on what you think chapters might contain

Begin your JSON response now:"""




def validate_config(
    provider: str = "anthropic",
    require_openai: bool = True,
    input_dir: str | None = None,
):
    """
    Validates that necessary environment variables and directories exist.
    """
    provider = (provider or "anthropic").lower()

    if provider == "gemini":
        google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not google_key:
            print("Missing GOOGLE_API_KEY (or GEMINI_API_KEY) in environment variables.")
            return False
    elif provider == "openai":
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            print("Missing OPENAI_API_KEY in environment variables.")
            return False
    else:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Missing ANTHROPIC_API_KEY in environment variables.")
            return False

    if require_openai:
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            print("Missing OPENAI_API_KEY in environment variables.")
            return False

    source_dir = input_dir or INPUT_DIR
    if not os.path.exists(source_dir):
        print(f"Input directory not found: {source_dir}")
        return False

    return True
