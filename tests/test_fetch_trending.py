import sqlite3
from pathlib import Path

import pytest
import requests

import fetch_trending as ft

FIXTURE = Path(__file__).parent / "fixtures" / "trending_weekly.html"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("1,234", 1234),
        ("\n        92,067", 92067),
        ("7,364 stars this week", 7364),
        ("1 star this week", 1),
        ("0", 0),
    ],
)
def test_parse_count(text, expected):
    assert ft.parse_count(text) == expected


def test_parse_count_without_number_raises():
    with pytest.raises(ft.ParseError):
        ft.parse_count("stars this week")
