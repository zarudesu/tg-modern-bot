"""
Tests for duration parsing utilities.

Source: app/utils/duration_parser.py
"""

import pytest

from app.utils.duration_parser import (
    parse_duration_to_minutes,
    format_duration_display,
    format_duration_for_n8n,
)


class TestParseDurationToMinutes:
    """Tests for parse_duration_to_minutes()."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("1 час", 60),
            ("30 мин", 30),
            ("2 часа", 120),
            ("1.5 часа", 90),
            ("90 мин", 90),
            ("2ч 30м", 150),
            ("45", 45),
            ("90", 90),
            ("120", 120),
            ("1час 15мин", 75),
            ("2 часа 30 минут", 150),
        ],
    )
    def test_valid_durations(self, input_str, expected):
        assert parse_duration_to_minutes(input_str) == expected

    @pytest.mark.parametrize(
        "input_str",
        [
            None,
            "",
            "abc",
            "   ",
        ],
    )
    def test_invalid_returns_none(self, input_str):
        assert parse_duration_to_minutes(input_str) is None

    def test_non_string_returns_none(self):
        assert parse_duration_to_minutes(123) is None

    def test_case_insensitive(self):
        assert parse_duration_to_minutes("1 ЧАС") == 60

    def test_extra_whitespace(self):
        assert parse_duration_to_minutes("  30  мин  ") == 30


class TestFormatDurationDisplay:
    """Tests for format_duration_display()."""

    def test_under_60_minutes(self):
        assert format_duration_display("30") == "30 мин"

    def test_exact_hour(self):
        assert format_duration_display("60") == "60 мин (1 час)"

    def test_multiple_hours(self):
        assert format_duration_display("120") == "120 мин (2 часов)"

    def test_hours_and_minutes(self):
        result = format_duration_display("90")
        assert "90 мин" in result
        assert "1ч 30м" in result

    def test_unparseable_returns_original(self):
        assert format_duration_display("abc") == "abc"


class TestFormatDurationForN8n:
    """Tests for format_duration_for_n8n()."""

    def test_valid_duration(self):
        assert format_duration_for_n8n("2 часа") == 120

    def test_invalid_returns_zero(self):
        assert format_duration_for_n8n("abc") == 0
