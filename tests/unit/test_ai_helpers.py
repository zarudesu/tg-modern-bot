"""
Tests for AI callback helper functions.

Source: app/handlers/ai_callbacks.py
"""

import pytest

# Import the function directly (it's a module-level function, not a method)
from app.handlers.ai_callbacks import _edit_distance_ratio


class TestEditDistanceRatio:
    """Tests for _edit_distance_ratio() — simple char-level distance."""

    def test_identical_strings(self):
        assert _edit_distance_ratio("hello", "hello") == 0.0

    def test_completely_different(self):
        assert _edit_distance_ratio("aaa", "bbb") == 1.0

    def test_empty_both(self):
        assert _edit_distance_ratio("", "") == 0.0

    def test_empty_first(self):
        assert _edit_distance_ratio("", "hello") == 1.0

    def test_empty_second(self):
        assert _edit_distance_ratio("hello", "") == 1.0

    def test_none_both(self):
        assert _edit_distance_ratio(None, None) == 0.0

    def test_none_first(self):
        assert _edit_distance_ratio(None, "hello") == 1.0

    def test_none_second(self):
        assert _edit_distance_ratio("hello", None) == 1.0

    def test_partial_match(self):
        # "hello" vs "hallo" — 4/5 match = 0.2 distance
        result = _edit_distance_ratio("hello", "hallo")
        assert 0.1 < result < 0.3

    def test_different_lengths(self):
        # "ab" vs "abc" — 2/3 match = ~0.33 distance
        result = _edit_distance_ratio("ab", "abc")
        assert 0.2 < result < 0.5

    def test_returns_float(self):
        result = _edit_distance_ratio("test", "tost")
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_symmetric(self):
        """Distance should be the same regardless of argument order."""
        d1 = _edit_distance_ratio("hello", "world")
        d2 = _edit_distance_ratio("world", "hello")
        assert d1 == d2

    def test_minor_edit(self):
        """Small edit should give small distance."""
        result = _edit_distance_ratio(
            "Fix server connection issue",
            "Fix server connection problem",
        )
        assert result < 0.5  # mostly the same
