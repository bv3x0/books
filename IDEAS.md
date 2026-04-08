# Future Ideas

Ideas for features to consider building.

---

## Key Figures (Homepage Feature)

**Concept**: Display a "Key Figures" section on the homepage showing people who appear across multiple books, helping readers discover unexpected connections.

**Why it's interesting**: The entities data surfaces real through-lines in the collection - Jung's outsized presence (50 mentions across 3 books), the Plato-Homer-Hesiod oral tradition thread, Nietzsche connecting philosophy to acceleration theory, and unexpected figures like Ronald Reagan bridging political violence to global history.

**Data source**: `entities.people` field in each book's `index/{book}.json`

**Implementation notes**:
- Aggregate people mentions across all book JSON files
- Rank by book diversity (appears in N different books), not raw mention count
- Deduplicate overlapping names (Christ/Jesus, biblical David vs. other Davids)
- Consider filtering out deities (God, Apollo, Zeus) vs. historical figures
- Link each person to the books where they appear

**Top candidates from current data**:
| Person | Books | Mentions |
|--------|-------|----------|
| Jung | 3 | 50 |
| Plato | 4 | 24 |
| Nietzsche | 4 | 7 |
| Homer | 3 | 9 |
| René Girard | 3 | 3 |

---

## Key Concepts (Homepage Feature)

**Concept**: Display top concepts that bridge multiple books, showing thematic connections across the collection.

**Why we deprioritized it**: The top concepts by book diversity turned out to be fairly generic academic terms ("Cultural Transformation", "Social Stratification", "Comparative Analysis") rather than compelling entry points.

**Data source**: `index/_concepts.json` - already tracks `books` array and `claim_count` per concept

**If revisiting**: Consider filtering out methodological terms, requiring both high book count AND high claim count, or manually curating from the top 15.

---

## Pull Quotes (Visual Break Feature)

**Concept**: Automatically insert prominent pull quotes mid-chapter to break up the monotony of long book notes. Quotes would be styled with a large decorative quotation mark, creating visual "handholds" for readers scrolling through dense content.

**Why it's interesting**: Book notes are structurally repetitive (claim → sub-points → claim → sub-points). Editorial pull quotes, common in magazines and longform articles, create breathing room and highlight memorable passages without requiring manual curation.

**Data source**: Sub-points already contain quotes in the format `"text" —Speaker`. These can be detected with regex: `^".*" —.+$`

**Implementation approach**:
1. Modify `_render_markdown()` in `app/core/exporter.py`
2. Scan each chapter's key_points for sub_points matching the quote pattern
3. Every N claims (4-5), if a suitable quote exists, render it as:
   ```html
   <blockquote class="pull-quote">"Quote text here."<span class="attribution">—Speaker</span></blockquote>
   ```
4. Add CSS styling (large faded `"` mark, italic text, generous whitespace)

**Design considerations**:
- Frequency: ~1 pull quote per 4-5 claims to avoid overuse
- Selection: Prefer quotes with named speakers over anonymous sources
- Duplication: Either skip the quote in its original sub-point location, or keep both (pull quote as highlight, original as citation)
- Fallback: Chapters without good quotes simply don't get pull quotes

**Mockup created**: `mockup-chapter-breaks.html` contains the "large quotation mark" style (Style 2 in Option B)

**Effort**: Medium — requires exporter changes + CSS. Existing books would need markdown regeneration from cached JSON (no re-processing via API).
