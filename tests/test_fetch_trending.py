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


def make_row(repo="octo/demo", desc="A demo", lang="Python",
             stars="1,234", forks="56", week="789 stars this week"):
    """One synthetic <article class="Box-row">; pass None to leave a part out."""
    parts = [f'<article class="Box-row"><h2><a href="/{repo}">{repo}</a></h2>']
    if desc is not None:
        parts.append(f"<p>\n  {desc}\n</p>")
    if lang is not None:
        parts.append(f'<span itemprop="programmingLanguage">{lang}</span>')
    if stars is not None:
        parts.append(f'<a href="/{repo}/stargazers">{stars}</a>')
    if forks is not None:
        parts.append(f'<a href="/{repo}/forks">{forks}</a>')
    if week is not None:
        parts.append(f"<span>{week}</span>")
    parts.append("</article>")
    return "".join(parts)


def page(*rows):
    return "<html><body>" + "".join(rows) + "</body></html>"


def test_parse_fixture():
    rows = ft.parse_trending(FIXTURE.read_text(encoding="utf-8"))

    assert len(rows) == 18
    assert [r["rank"] for r in rows] == list(range(1, 19))
    assert rows[0] == {
        "rank": 1,
        "repo": "anthropics/financial-services",
        "description": None,
        "language": "Python",
        "stars": 38002,
        "forks": 5478,
        "stars_this_week": 2606,
        "url": "https://github.com/anthropics/financial-services",
    }
    assert rows[1]["repo"] == "paperclipai/paperclip"
    assert rows[1]["description"] == "The open-source app everyone uses to manage agents at work"
    assert rows[1]["stars_this_week"] == 7364


def test_parse_synthetic_row():
    rows = ft.parse_trending(page(make_row()))
    assert rows == [{
        "rank": 1,
        "repo": "octo/demo",
        "description": "A demo",
        "language": "Python",
        "stars": 1234,
        "forks": 56,
        "stars_this_week": 789,
        "url": "https://github.com/octo/demo",
    }]


def test_missing_optional_fields_are_none():
    rows = ft.parse_trending(page(make_row(desc=None, lang=None, forks=None)))
    assert rows[0]["description"] is None
    assert rows[0]["language"] is None
    assert rows[0]["forks"] is None
    assert rows[0]["stars"] == 1234
    assert rows[0]["stars_this_week"] == 789


def test_one_star_this_week():
    rows = ft.parse_trending(page(make_row(week="1 star this week")))
    assert rows[0]["stars_this_week"] == 1


def test_empty_page_raises():
    with pytest.raises(ft.ParseError):
        ft.parse_trending(page())


@pytest.mark.parametrize("missing", [{"stars": None}, {"week": None}])
def test_missing_required_field_raises(missing):
    with pytest.raises(ft.ParseError):
        ft.parse_trending(page(make_row(), make_row(repo="octo/two", **missing)))


def test_missing_repo_link_raises():
    with pytest.raises(ft.ParseError):
        ft.parse_trending(page('<article class="Box-row"><span>5 stars this week</span></article>'))
