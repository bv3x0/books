"""Regression tests for fidelity quote grounding.

These lock the hardening for false-positive QUOTE_NOT_IN_SOURCE failures caused
by EPUB->markdown extraction artifacts (markdown emphasis markers, inline
footnote digits), the brittle short-quote rule, and the distinctive-token
occurrence cap. Each faithful case uses a source snippet shaped like the real
extractor output; negative cases prove the guard is not weakened.
"""

import os
import sys
import unittest

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.core.verifier import _normalize_text, _quote_matches_source


class TestNormalizeText(unittest.TestCase):
    def test_strips_markdown_emphasis(self):
        self.assertEqual(_normalize_text("the *homo sacer* of _itself_"), "the homo sacer of itself")

    def test_strips_inline_footnote_digits(self):
        self.assertEqual(_normalize_text("the sound of water7"), "the sound of water")

    def test_preserves_standalone_numbers_and_years(self):
        self.assertEqual(_normalize_text("in 1984 there were 3 rules"), "in 1984 there were 3 rules")

    def test_preserves_mid_token_digits(self):
        # "h2o" must not lose its digit (only letter-then-trailing-digits go).
        self.assertEqual(_normalize_text("h2o molecule"), "h2o molecule")


class TestFaithfulQuotesGround(unittest.TestCase):
    """Quotes verbatim in the book that previously failed on artifacts."""

    def test_italics_wrapped_phrase(self):
        # palliative society: source wraps the phrase in markdown italics.
        src = "not the reception of something but a reception. *Pain is a gift*. ## Notes"
        self.assertTrue(_quote_matches_source("Pain is a gift.", src))

    def test_italics_inside_longer_quote(self):
        # topology of violence: italics on the tail of the sentence.
        src = (
            "turning itself into *homo sacer.* The sovereign of the achievement "
            "society is the *homo sacer of itself.* Ehrenberg's theory of depression"
        )
        self.assertTrue(
            _quote_matches_source(
                "The sovereign of the achievement society is the homo sacer of itself.", src
            )
        )

    def test_short_quote_with_trailing_punctuation_difference(self):
        # topology of violence: quote ends with a period, source with a comma;
        # only 18 chars, so the old length guard rejected it outright.
        src = 'For desire desires death also. "... death is its motor," he says of the machine.'
        self.assertTrue(_quote_matches_source("death is its motor.", src))

    def test_quote_with_inline_footnote_digit(self):
        # disappearance of rituals: haiku with a footnote digit glued to "water".
        src = "resist any kind of translation. old pond a frog jumps into the sound of water7 the intense"
        self.assertTrue(
            _quote_matches_source("old pond a frog jumps into the sound of water", src)
        )

    def test_italics_and_repeated_distinctive_token(self):
        # scent of time: italics on both key terms, in a chapter that repeats
        # "contemplativa" many times before the target sentence.
        filler = "The vita contemplativa endures. " * 60
        src = filler + (
            "Thus, a *vita contemplativa* without acting is blind, a *vita activa* "
            "without contemplation is empty. Heidegger continues."
        )
        self.assertTrue(
            _quote_matches_source(
                "A vita contemplativa without acting is blind, a vita activa without contemplation is empty.",
                src,
            )
        )

    def test_fuzzy_match_survives_repeated_token_cap(self):
        # Not an exact subsequence (one word differs), so it must fall through to
        # the fuzzy path. Placed after >30 occurrences of the distinctive token to
        # exercise the raised occurrence cap (item 4).
        filler = "A steady vita contemplativa persists here. " * 45
        src = filler + "A rare vita contemplativa without acting truly is blind indeed today."
        quote = "A rare vita contemplativa without acting really is blind indeed today."
        self.assertTrue(_quote_matches_source(quote, src))


class TestFabricatedQuotesStillFail(unittest.TestCase):
    """The guard must still reject quotes that are not in the source."""

    def test_unrelated_fabrication(self):
        src = "not the reception of something but a reception. Pain is a gift. Notes follow here."
        self.assertFalse(
            _quote_matches_source("The moon is a silent ledger of forgotten debts.", src)
        )

    def test_plausible_but_absent_quote(self):
        # Shares common words with the source but the assertion is not present.
        src = "not the reception of something but a reception. Pain is a gift. Notes follow here."
        self.assertFalse(
            _quote_matches_source("Pain is always a meaningless punishment imposed from outside.", src)
        )

    def test_empty_source_rejects_real_quote(self):
        self.assertFalse(_quote_matches_source("Pain is a gift.", ""))


if __name__ == "__main__":
    unittest.main()
