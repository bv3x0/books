import os
import shutil

# Configuration Constants
ANTHROPIC_MODEL_ID = "claude-sonnet-4-6"
GEMINI_MODEL_ID = "gemini-3-flash-preview"
GPT_MODEL_ID = "gpt-5.2"
CODEX_MODEL_ID = os.getenv("SUMMARIZER_CODEX_MODEL", "gpt-5.5")
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

2. **key_points**: Use the fewest synthesis-level points that preserve the chapter's real argumentative moves
   - Short/simple chapters (~500-1500 words): usually 1-3 points
   - Standard chapters (~1500-3500 words): usually 2-5 points
   - Long/dense chapters (~3500+ words): usually 3-6 points
   - Exceptionally dense, archival, technical, or anthology-like chapters may use up to 10 points if the chapter truly contains that many separate argumentative moves
   - Use 6+ points only when the chapter cannot be faithfully represented by merging related material into larger synthesis claims
   - Prefer 3-4 richer synthesis claims over 5 thinner claims when the argument can be naturally consolidated
   - A long chapter with one repeated method, case-study arc, interview profile, theoretical thesis, or narrative through-line should still use fewer stronger points; do not create extra points merely because the source contains many incidents or terms
   - Dense theoretical chapters are not automatically five-point chapters; if the chapter develops one compact conceptual move, use fewer stronger points
   - Do not pad thin chapters to hit a quota, and do not compress dense chapters just to match other books

   Each key_point includes:
   - **point**: A synthesis-level argument, interpretive move, episode, mechanism, taxonomy, method, or distinctive claim (standalone - see requirements below)
   - **sub_points**: 0-5 typed evidence packets as objects with "type", "text", and "speaker" fields; use the smallest set that preserves the claim's decisive source anchors
   - **concepts**: 0-3 reusable concept tags in snake_case (see tagging guidelines)
   - **entities**: Named people, places, events, works mentioned

**CONSOLIDATION PRIORITIES** (when condensing, preserve in this order):
1. **Core argument** (never skip): The chapter's main thesis
2. **Load-bearing evidence** (essential): The examples, scenes, experiments, case studies, names, dates, images, incidents, numbers, or terms that carry the chapter's causal logic, distinctiveness, scale, contradiction, or reader trust
3. **Source texture** (essential for dense/theoretical books): The exact terms, strange formulations, named symbols, slogans, ritual phrases, technical vocabulary, and quoted formulas that the author uses to think
4. **Key entities** (important): Names, dates, places that enable cross-referencing
5. **Key distinctions** (important): Definitions, typologies, contrasts, methods, or terms of art that carry the author's reasoning
6. **Counterarguments** (important when present): Objections, reversals, caveats, and rival views central to the chapter's logic
7. **Supporting details** (nice-to-have): Additional examples if space allows
8. **Preserved wording** (selective): Exact phrases or quotes when wording carries meaning that paraphrase would flatten

**CONSOLIDATION RULES:**
- A key_point is an editorial synthesis unit, not a paragraph-by-paragraph outline item. It should be the kind of claim a careful reader would keep as one durable note.
- A key_point may be one polished sentence or two tightly linked sentences. A richer two-sentence synthesis claim is better than splitting one idea into two thin sibling claims.
- Merge adjacent facts, scenes, biographical stages, examples, and numbers when they support the same mechanism, lesson, or episode. Put the best anchors in sub_points rather than creating separate sibling claims.
- Split claims only when the chapter shifts to a genuinely different mechanism, contradiction, method, turning point, counterargument, or consequence.
- Keep every key_point inside the current chapter's actual scope. Do not import a vivid detail, symbol, or argument from an adjacent chapter merely to create continuity or add source texture.
- For dense theoretical, symbolic, religious, philosophical, or literary-critical chapters, do not paraphrase away the author's technical vocabulary or strange decisive formulations. Preserve the vocabulary that makes the thought recognizable.
- Preserve 1-2 exact or near-exact source phrases per dense chapter when the wording carries the argument's force, especially terms of art, ritual formulas, named symbols, doctrinal distinctions, and memorable formulations.
- Multiple examples making the same point -> keep the examples that change the reader's understanding of the claim; do not preserve examples merely because they are specific, and do not omit the concrete layer entirely
- Extended anecdotes -> preserve the key insight and memorable details in 1-3 sentences
- Preserve specific names, data points, and quotes when they make arguments concrete, distinguish this case from nearby cases, convey scale, reveal causality, or expose a tension/caveat
- Where a chapter builds on prior argument, include a brief connective clause; where chapters are independent, do not invent continuity
- Do not normalize every claim into the same number of sub_points. A strong claim with one decisive number may need one evidence packet; a self-contained synthesis claim may need none; four or five packets should be exceptional, not the new default.
- Vary the evidence packet mix by source material. Prefer fewer, sharper packets over a uniform row of generic supports, but do not mistake brevity for judgment.
- The support layer is editorial selection, not a secondary outline. Prefer the one example, number, contrast, mechanism, or quote that changes the reader's understanding; omit adjacent examples that play the same evidentiary role.
- Specificity is not the goal by itself. A detail is worth preserving when it is load-bearing: it helps explain why something happened, why this chapter/person/case is distinctive, how large or rare something was, what changed, what failed, or what would be lost in a generic paraphrase.
- After drafting a chapter, perform a silent merge pass: if two key_points would naturally sit under the same heading in a professional reader's notebook, merge them and keep only the load-bearing evidence. Prefer one stronger synthesis claim to two parallel claims.
- If a chapter has exactly five key_points, silently ask whether the same material would read more professionally as three or four richer synthesis claims. Keep five only when the fifth point is a genuinely separate move.
- Then perform a silent source-texture pass: if a dense chapter has become a clean paraphrase that no longer sounds like the source, restore the minimum exact terms, phrases, symbols, or quotes needed to preserve the author's intellectual texture.
- Then perform a silent chapter-scope pass: remove or relocate any claim whose decisive evidence belongs mainly to another chapter, even if the claim is thematically related.

The goal is natural condensation through smart consolidation, NOT aggressive cutting that loses the book's character.
"""

    return f"""Analyze this book and produce a structured JSON response containing both a human-readable summary and machine-readable structured data.

## OUTPUT FORMAT

You must respond with valid JSON only. No markdown, no explanations outside the JSON.

{{
  "book": {{
    "title": "string - exact title, including subtitle if present in the source",
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
            {{"type": "example", "text": "case, scene, event, or concrete instance", "speaker": null}},
            {{"type": "number", "text": "important figure, scale, date, comparison, or performance metric", "speaker": null}},
            {{"type": "quote", "text": "exact quote from someone", "speaker": "Name of speaker"}}
          ],
          "concepts": ["0-3 reusable concept tags in snake_case"],
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

For chapters with 6 or more key_points, select one sentence from the source text as a pull_quote - the sentence that best captures the section's central insight, most consequential claim, or most distinctive formulation. This should be the sentence a reader would underline.

- Must be verbatim or near-verbatim from the source text
- Must represent the section's core thrust, not a tangential detail
- Should be a complete, self-contained thought
- Null for chapters with fewer than 6 key_points

## KEY POINT REQUIREMENTS

Each key_point's "point" field must be a standalone claim:

Every point should reconstruct argument logic: what is claimed and why/how, not just what topic is discussed.
- Prefer mechanism statements (X leads to Y because Z) over topical description
- For narrative history, biography, literary criticism, religious texts, aphoristic works, manuals, and anthologies, a point may instead preserve a consequential episode, interpretive distinction, method, taxonomy, example, or source tradition
- For interview, biography, case-study, or profile chapters, compress related life events, training choices, methods, failures, and later reflections into larger arc-level claims when they share one causal lesson. Do not make every stage of a person's story its own point.
- For dense theoretical or symbolic chapters, a point should often preserve both the conceptual move and the author's distinctive vocabulary. Do not turn technical, esoteric, theological, philosophical, or literary-critical terms into bland paraphrase.
- Every point must be grounded in the chapter it appears under; do not place a claim under a chapter unless that chapter itself develops the claim.
- State claims directly; avoid meta framing like "The author argues..." or "This chapter shows..."
- Prefer concrete actors and actions over abstract framing language
- Every point must include at least one concrete anchor (named person, place, event, work, date, or explicit mechanism)
- Avoid under-specified one-liners; include enough detail to be useful out of context
- A good point often contains the conclusion and the main mechanism inside the sentence itself. Sub_points should anchor, qualify, or exemplify the claim; they should not be needed to understand what the claim means.
- Do not make points artificially short. If one more sentence is needed to carry the synthesis with professional clarity, include it in the point rather than offloading the whole meaning into sub_points.

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

Treat sub_points as typed evidence packets, not a fixed bullet quota. Each sub_point is an object with:
- **type**: one of "example", "number", "mechanism", "quote", "contrast", "caveat", or "source_detail"
- **text**: The content (supporting detail, evidence, example, number, mechanism, contrast, caveat, source detail, or quote)
- **speaker**: Name of who said it (for quotes), or null (for non-quotes)

If speaker is non-null, the text is a direct quote. If speaker is null, it's supporting material.
In sub_points, prefer explicit names when they carry argumentative weight (thinkers, works, institutions, events) over vague pronouns or abstractions.

**Evidence packet rules:**
- Use 0-5 sub_points per key_point. Do not default to 2, 3, or 4.
- Most key_points should have 1-3 packets. Use 4-5 only when a claim depends on multiple examples, numbers, stages, or caveats.
- Use 0 packets only when the point itself already contains the decisive source anchor and extra bullets would be redundant.
- Every packet must add a distinct kind of value: an example, number, mechanism, quote, contrast, caveat, or source detail. Do not use packets as generic restatement.
- If two packets would merely give parallel examples of the same mechanism, keep the stronger or more source-distinctive one unless the comparison itself matters.
- A note can be richly faithful with fewer packets when the selected packets are decisive. Do not fill out a claim for visual symmetry, chapter balance, or because another claim nearby has more support.
- Evidence packets are subordinate to the synthesis claim. Do not create a new key_point just to house a vivid detail; either attach it to the larger claim it supports or omit it if it does not change the reader's understanding.
- Preserve concrete details when they carry causal logic, distinctiveness, scale, contradiction, or reader trust. Do not include details merely because they are numbers, names, or tickers.
- For dense theoretical books, prefer "source_detail" for exact terms, titles, ritual phrases, symbolic objects, or technical vocabulary that would be too book-specific for concept tags but too important to omit.
- Before finalizing a claim, ask whether removing its evidence packets would make the claim generic, ungrounded, or interchangeable with another chapter. If yes, restore the minimum load-bearing evidence needed.

Use sub_points to preserve source anchors, not just generic support. Good source anchors include:
- named examples, case studies, experiments, historical incidents, scenes, dates, institutions, source texts, images, diagrams, terms of art, and memorable formulations
- the concrete object or event the author uses to make an abstraction vivid
- the caveat, objection, or reversal that prevents a claim from becoming too smooth

## QUOTE PRESERVATION

Most chapters need few quotes, but exact wording is valuable when it carries conceptual force, preserves a term of art, or captures the author's distinctive formulation. Aim for 0-2 quotes per chapter unless the source is aphoristic, dialogic, scriptural/commentarial, or quote-driven.

**REASONS TO PRESERVE A QUOTE OR SHORT PHRASE:**
- It articulates a thesis, argument, or position more precisely or succinctly than paraphrase.
- It preserves the author's vocabulary, term of art, or conceptual distinction.
- It is a primary-source formulation that later interpretation depends on.
- It is a ritual, doctrinal, legal, poetic, aphoristic, or symbolic phrase whose force would be lost if smoothed into generic prose.
- PRESERVE: "I no longer believe that freedom and democracy are compatible" (Thiel) - this IS the argument
- PRESERVE: "Schools teach students to confuse process with substance" (Illich) - sharper than any paraphrase
- PRESERVE SHORT PHRASES when they are the author's key vocabulary, even if embedded inside paraphrase
- SKIP: conversational color, attitude, decoration, or famous sayings that do not advance the source's argument

**THE TEST:** If you can paraphrase it into a sub_point without losing meaning, vocabulary, or source texture, do that instead. Quote when the wording itself is part of the intellectual content.

**DO NOT QUOTE:**
- Material that is only personality, humor, or atmosphere
- Conversational remarks or narrative beats that do not carry meaning beyond local color
- Famous sayings used as decoration
- Anything that works equally well as paraphrase

**HOW TO FORMAT (when a quote passes the test):**
- Set "type" to "quote"
- Set "speaker" to who said it
- Set "text" to the exact or near-exact wording

## CONCEPTS vs ENTITIES

These are complementary - the same content often needs BOTH:

**CONCEPTS** = Reusable academic categories that connect ideas across books (snake_case)
- Ask: "Could this concept appear in a completely different book on a different topic?"
- Use 0-3 concepts per claim; most claims need 1-2
- Use an empty concepts array when there is no honest reusable tag beyond the named entities, source_detail packets, or claim text
- Prefer broad, reusable categories over book-specific terminology
- If a tag would only make sense inside this single book, do NOT make it a concept. Preserve that specificity as an entity, source_detail, or in the claim text instead.

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
- For esoteric, religious, philosophical, and literary-critical works, terms of art often belong in entities or source_detail rather than concepts when they are local vocabulary.

## CATEGORY SELECTION

Select 1-3 categories from this list:
{categories}

Prefer more specific categories over general ones when both fit.

## IMPORTANT RULES

1. Follow the book's actual chapter structure - use real chapter titles and assign claims only to the chapter that develops them
2. Use exact book metadata from the source when visible. Do not shorten the title or drop a subtitle/year if the source provides it.
3. Do not invent content not in the source
4. Do not include publisher info, copyright pages, or promotional material
5. Ensure JSON is valid - properly escape quotes, no trailing commas
6. Cover all chapters present in the provided text/chunk - do not stop partway through
7. Conclusions, epilogues, afterwords, and final chapters are not optional - when present in the provided text/chunk, cover them with the same depth as regular chapters
8. Before finalizing the JSON, silently re-scan each chapter for omitted concrete examples, named entities, counterarguments, definitions, exact terms, source phrases, distinctive formulations, and misplaced adjacent-chapter claims. Revise the JSON to restore important omissions and remove misplaced claims, but do not output the audit.

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
    elif provider == "codex":
        if not shutil.which("codex"):
            print("Missing codex executable on PATH.")
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
