# Daily Perspective: Horoscope Flow V1

## Purpose

Build a small daily pipeline that turns one external signal (a horoscope entry) into a short, grounded perspective brief drawn from the existing book corpus.

This is not a wiki feature.
It is a perspective engine:

`daily signal -> retrieve relevant material -> synthesize a readable brief`

## Why This Fits The Repo

The current repo already has the right substrate:

- `notes/` for readable source material
- `index/*.json` for structured claims, concepts, entities, and sub-points
- vector search for semantic candidate retrieval

V1 should treat the vector layer as candidate generation, not as the final product.
The product is the daily brief.

## V1 Goal

Each day, generate one private brief that:

- starts from the horoscope text
- finds 2-4 genuinely resonant passages or claims from the corpus
- turns them into a short, reader-friendly reflection
- stays under 500 words
- saves enough metadata to inspect why it chose what it chose

## Non-Goals

V1 should not try to:

- build a general personal wiki
- summarize "everything relevant" from the corpus
- do agent swarms or heavy autonomous research
- ingest personal journal data yet
- expose public APIs or sharing flows

## Primary Risks

Without extra guardrails, this flow will fail in predictable ways:

- it will force deep meaning from a very thin signal
- it will keep picking the same familiar books every day
- it will produce pure confirmation instead of perspective
- it will slide into faux-prophetic or overly prescriptive language

V1 should explicitly defend against these failure modes.

## Storage

Add two new durable directories:

```text
signals/horoscope/
briefs/horoscope/
```

Suggested files per day:

```text
signals/horoscope/2026-04-05.json
signals/horoscope/2026-04-05.analysis.json
briefs/horoscope/2026-04-05.md
briefs/horoscope/2026-04-05.context.json
```

### `signals/horoscope/YYYY-MM-DD.json`

Raw intake record:

```json
{
  "date": "2026-04-05",
  "source": "rss",
  "feed_name": "Daily Horoscope",
  "sign": "aries",
  "title": "Aries Horoscope for April 5, 2026",
  "raw_text": "Today asks for patience in love and restraint in speech...",
  "fetched_at": "2026-04-05T06:00:00Z"
}
```

### `signals/horoscope/YYYY-MM-DD.analysis.json`

Interpretation layer created by the LLM:

```json
{
  "date": "2026-04-05",
  "sign": "aries",
  "signal_summary": "A day about restraint, timing, and refusing reactive speech.",
  "literal_topics": ["speech", "conflict", "relationships"],
  "symbolic_themes": ["restraint", "timing", "patience"],
  "moods": ["tense", "reflective"],
  "stance": "cautionary",
  "tensions": [
    "impulse vs restraint",
    "clarity vs conflict"
  ],
  "query_modes": {
    "literal": [
      "restraint in speech under pressure",
      "how to avoid escalating conflict"
    ],
    "symbolic": [
      "patience before action",
      "timing and prudence"
    ],
    "practical": [
      "how to avoid saying too much in relationships"
    ]
  }
}
```

### `briefs/horoscope/YYYY-MM-DD.context.json`

Grounding record used for composition:

```json
{
  "date": "2026-04-05",
  "retrieval_confidence": "medium",
  "final_angle": "Restraint today is less about silence than about timing.",
  "selected_claims": [
    {
      "claim_id": "book-001",
      "book": "fooled by randomness",
      "chapter": "Chapter 3",
      "score": 0.82,
      "role": "anchor",
      "selection_reason": "specific and practically usable",
      "claim_text": "...",
      "sub_points": ["...", "..."]
    }
  ],
  "counterweight_claim": {
    "claim_id": "book-145",
    "book": "orthodoxy",
    "role": "counterweight",
    "selection_reason": "prevents the brief from collapsing into pure caution"
  },
  "recent_books_penalized": ["orthodoxy"],
  "rejected_claims": [
    {
      "claim_id": "book-212",
      "reason": "too generic"
    }
  ],
  "books_considered": ["fooled by randomness", "orthodoxy"],
  "generation_notes": {
    "selection_strategy": "high relevance, high specificity, cross-book diversity, novelty penalty"
  }
}
```

### `briefs/horoscope/YYYY-MM-DD.md`

Final brief plus compact frontmatter:

```yaml
---
date: 2026-04-05
sign: aries
kind: horoscope-brief
source_books:
  - fooled by randomness
  - orthodoxy
claim_ids:
  - book-001
  - book-145
themes:
  - restraint
  - patience
confidence: medium
status: generated
---
```

Then the brief body, under 500 words.

## Pipeline

### 1. Intake

Fetch the daily horoscope from RSS and write one raw signal file.

Requirements:

- one item per day
- immutable raw signal record
- no prompt logic here

### 2. Interpret The Signal

Run one LLM pass to turn the horoscope into a usable search object.

Output:

- one-sentence summary
- 2-4 literal topics
- 2-4 symbolic themes
- 1-3 tensions
- a stance such as cautionary, expansive, reflective, or opportunistic
- a small set of queries grouped by mode

Important rule:
The analysis step should not write prose for the user.
It should only prepare retrieval.

Second important rule:
The analysis step should preserve both a literal reading and a symbolic reading.
This keeps retrieval from becoming too vague or too credulous.

### 3. Retrieve Candidate Material

Use the existing semantic retrieval stack over `index/`.

Suggested V1 retrieval strategy:

1. Run a literal lane using the raw horoscope text and `literal` queries.
2. Run a symbolic lane using `symbolic` queries.
3. Run a practical lane using `practical` queries.
4. Search one compact paraphrase of the horoscope.
5. Merge and deduplicate results by `claim_id`.

Initial target:

- 30-60 raw candidate claims

Then rerank with these heuristics:

- semantic relevance to the signal
- specificity over vagueness
- diversity across books
- readability of the underlying passage
- preference for claims with strong sub-points
- novelty against the last 3-7 daily briefs
- at least one result that complicates the dominant reading

Hard constraints:

- final evidence bundle should usually use 2-4 books
- do not take more than 2 anchors from one book unless the corpus is thin
- prefer claims that can become advice, framing, or perspective
- do not let one favorite book dominate the week unless it is clearly the best fit

### 4. Choose The Angle

Before writing, run a small selection pass over the top candidates.

Output:

- one sentence describing the main angle of the brief
- one optional counterweight or tension
- one confidence label: `high`, `medium`, or `low`
- a final shortlist of 3-6 evidence anchors

This is important.
Without an explicit angle-selection step, the brief will read like a bag of semantically similar fragments.

### 5. Expand Into Usable Evidence

Claims alone may be too atomic.
For each top candidate, attach:

- book title
- chapter title
- claim text
- top 1-3 sub-points

This gives the writing step enough local context to sound grounded.

V1 does not need full-passage retrieval from `notes/`.
Claim + sub-points is enough to start.

### 6. Compose The Brief

Run one writing pass with:

- the raw horoscope
- the signal analysis
- the chosen angle
- the 3-6 best evidence anchors
- the confidence label

Prompt target:

- 250-450 words
- warm, intelligent, readable prose
- not mystical in an overblown way
- not generic self-help
- grounded in the books without sounding academic
- willing to include tension instead of only confirmation

Suggested structure:

1. Opening frame: what the day seems to be asking for
2. Core perspective: 2-3 ideas from the corpus
3. Counterweight: one sentence that complicates or tempers the main reading
4. Closing line: one practical attitude, question, or caution to carry today

Hard rules:

- no fabricated claims
- no mention of books not present in the evidence bundle
- no more than one direct quote unless clearly useful
- do not present the horoscope as fact or destiny
- keep advice soft and orienting, not commanding
- never exceed 500 words

### 7. Low-Confidence Path

If retrieval confidence is `low`, do not force a profound brief.

Instead:

- use only 1-2 books
- keep the brief shorter
- make the prose lighter and more tentative
- prefer "one useful angle for today" over "this is what the day means"

The system should never hallucinate depth just to satisfy the daily cadence.

### 8. Save And Surface

Persist both:

- final brief
- context bundle explaining why it was generated that way

The frontend should show:

- the brief
- the raw horoscope text
- the source books used
- an optional "why these books" expander backed by `context.json`

## Repetition Control

Because this runs daily, repetition is a core product risk.

V1 should keep a tiny working memory of recent outputs:

- books used in the last 3-7 days
- dominant themes used recently
- whether a book is becoming overrepresented

This does not need a separate system.
It can be derived from recent `briefs/horoscope/*.context.json` files.

The goal is not novelty for its own sake.
The goal is to stop the brief from becoming the same essay every morning.

## Writing Lens

The writing style matters as much as retrieval quality.
V1 should use one stable lens:

"Treat the horoscope as a prompt for reflection, not a prediction.
Use the corpus to add texture, depth, and useful orientation."

That keeps the system from becoming either:

- too credulous about astrology
- too embarrassed about astrology
- too generic and therapeutic

## Quality Bar

A good brief should feel:

- unexpectedly apt
- anchored in real books
- compact enough to read quickly
- more like a thoughtful marginal note than an essay

A bad brief will usually fail in one of these ways:

- obvious semantic matches but no real insight
- too many weakly related books
- the same books appearing over and over
- bland universal advice
- overwritten mystical tone
- false certainty about the day
- academic summary instead of personal orientation

## Minimal Feedback Loop

Add one tiny feedback field later, even in V1:

```json
{
  "reaction": "resonant"
}
```

Useful values:

- `resonant`
- `too-generic`
- `too-abstract`
- `wrong-books`
- `too-dark`
- `repetitive`
- `too-confirming`

This matters because the real upgrade path is ranking and tone tuning, not more data plumbing.

## Repo Shape

If this becomes code, the likely shape is:

```text
app/services/signal_service.py
app/services/perspective_service.py
app/cli/perspective.py
signals/horoscope/
briefs/horoscope/
```

The new services should reuse:

- `app/services/query_service.py`
- canonical `index/*.json`
- existing vector infrastructure

## V1 Success Criteria

V1 is successful if, after 2-3 weeks of daily runs:

- the briefs are usually worth reading
- the selected books feel meaningfully chosen
- the output is inspectable when it feels wrong
- the briefs vary from day to day without becoming random
- low-confidence days fail gracefully instead of bluffing
- the system reveals missing retrieval features clearly

## Likely V2 Upgrades

Only after V1 works:

- retrieve full note passages, not just claims
- support multiple lenses like horoscope, news, theology, or market mood
- add a "counterpoint" mode so the brief can include tension instead of pure confirmation
- learn taste preferences from your reactions
- generate a weekly digest from the daily briefs

## One Sentence Summary

Do not build a horoscope wiki.
Build a daily signal-to-perspective pipeline that uses the existing corpus as a source of resonance, context, and counsel.
