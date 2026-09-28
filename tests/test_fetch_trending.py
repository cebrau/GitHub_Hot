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


def rows_for(*repos):
    return [
        {"rank": i, "repo": r, "description": None, "language": None,
         "stars": 10, "forks": None, "stars_this_week": 5,
         "url": f"https://github.com/{r}"}
        for i, r in enumerate(repos, start=1)
    ]


def ranks_and_repos(db, snapshot_date):
    con = sqlite3.connect(db)
    try:
        return con.execute(
            "SELECT rank, repo FROM weekly_trending WHERE snapshot_date = ? ORDER BY rank",
            (snapshot_date,),
        ).fetchall()
    finally:
        con.close()


def test_save_creates_db_and_stores_all_columns(tmp_path):
    db = tmp_path / "data" / "t.db"  # parent folder does not exist yet
    row = {"rank": 1, "repo": "octo/demo", "description": "A demo", "language": "Python",
           "stars": 1234, "forks": 56, "stars_this_week": 789,
           "url": "https://github.com/octo/demo"}

    ft.save_snapshot(db, "2026-10-05", [row])

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        stored = dict(con.execute("SELECT * FROM weekly_trending").fetchone())
    finally:
        con.close()
    fetched_at = stored.pop("fetched_at")
    assert stored == {"snapshot_date": "2026-10-05", **row}
    assert fetched_at.endswith("+00:00")


def test_same_day_rerun_replaces_snapshot(tmp_path):
    db = tmp_path / "t.db"
    ft.save_snapshot(db, "2026-10-05", rows_for("a/one", "b/two"))
    ft.save_snapshot(db, "2026-10-05", rows_for("b/two", "c/three"))
    # a/one dropped off the list, so it must be gone.
    assert ranks_and_repos(db, "2026-10-05") == [(1, "b/two"), (2, "c/three")]


def test_different_days_are_both_kept(tmp_path):
    db = tmp_path / "t.db"
    ft.save_snapshot(db, "2026-10-05", rows_for("a/one"))
    ft.save_snapshot(db, "2026-10-12", rows_for("b/two"))
    assert ranks_and_repos(db, "2026-10-05") == [(1, "a/one")]
    assert ranks_and_repos(db, "2026-10-12") == [(1, "b/two")]


class FakeResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def fake_get(outcomes, calls):
    """requests.get stand-in: each call returns/raises the next outcome."""
    def get(url, headers, timeout):
        calls.append((url, headers, timeout))
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    return get


def test_fetch_retries_then_succeeds(monkeypatch):
    calls, sleeps = [], []
    outcomes = [FakeResponse(500), requests.ConnectionError("boom"), FakeResponse(200, "<html>ok</html>")]
    monkeypatch.setattr(ft.requests, "get", fake_get(outcomes, calls))
    monkeypatch.setattr(ft.time, "sleep", sleeps.append)

    assert ft.fetch_html() == "<html>ok</html>"
    assert len(calls) == 3
    assert sleeps == [5, 10]
    url, headers, timeout = calls[0]
    assert url == "https://github.com/trending?since=weekly"
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert timeout == 30


def test_fetch_gives_up_after_three_tries(monkeypatch):
    calls, sleeps = [], []
    outcomes = [FakeResponse(503), FakeResponse(503), FakeResponse(503)]
    monkeypatch.setattr(ft.requests, "get", fake_get(outcomes, calls))
    monkeypatch.setattr(ft.time, "sleep", sleeps.append)

    with pytest.raises(requests.HTTPError):
        ft.fetch_html()
    assert len(calls) == 3
    assert sleeps == [5, 10]


def test_main_saves_fixture(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(ft, "DB_PATH", db)
    monkeypatch.setattr(ft, "fetch_html", lambda: FIXTURE.read_text(encoding="utf-8"))

    assert ft.main() == 0

    con = sqlite3.connect(db)
    try:
        assert con.execute("SELECT COUNT(*) FROM weekly_trending").fetchone() == (18,)
    finally:
        con.close()


def test_main_bad_page_fails_without_writing(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(ft, "DB_PATH", db)
    monkeypatch.setattr(ft, "fetch_html", lambda: "<html><body>redesigned</body></html>")

    assert ft.main() == 1
    assert not db.exists()


def test_main_network_failure_fails_without_writing(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(ft, "DB_PATH", db)

    def down():
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(ft, "fetch_html", down)

    assert ft.main() == 1
    assert not db.exists()
