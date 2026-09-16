"""Testes de parsing de timeframe."""

from __future__ import annotations

import pytest

from mt5_ea.timeframes import parse_timeframe, timeframe_label


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("M15", 15),
        ("m15", 15),
        ("15", 15),
        (15, 15),
        ("H1", 60),
        ("H4", 240),
        ("D1", 1440),
        ("W1", 10080),
        (None, 15),
    ],
)
def test_parse_timeframe(raw, expected) -> None:
    assert parse_timeframe(raw) == expected


def test_timeframe_label() -> None:
    assert timeframe_label(15) == "M15"
    assert timeframe_label(60) == "H1"


def test_parse_timeframe_invalid() -> None:
    with pytest.raises(ValueError):
        parse_timeframe("M99")
