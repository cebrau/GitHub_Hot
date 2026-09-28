"""Fetch GitHub's weekly trending repositories and store them in SQLite.

Usage: python fetch_trending.py
"""
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

TRENDING_URL = "https://github.com/trending?since=weekly"
DB_PATH = Path(__file__).parent / "data" / "github_trending.db"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)
# Seconds to wait before the 2nd and 3rd attempt.
RETRY_DELAYS = (5, 10)

SCHEMA = """
CREATE TABLE IF NOT EXISTS weekly_trending (
    snapshot_date   TEXT    NOT NULL,
    rank            INTEGER NOT NULL,
    repo            TEXT    NOT NULL,
    description     TEXT,
    language        TEXT,
    stars           INTEGER NOT NULL,
    forks           INTEGER,
    stars_this_week INTEGER NOT NULL,
    url             TEXT    NOT NULL,
    fetched_at      TEXT    NOT NULL,
    PRIMARY KEY (snapshot_date, repo)
)
"""


class ParseError(Exception):
    """The trending page does not look the way we expect (probably redesigned)."""


def parse_count(text):
    """'1,234' or '1,234 stars this week' -> 1234."""
    match = re.search(r"\d[\d,]*", text)
    if not match:
        raise ParseError(f"no number in {text!r}")
    return int(match.group(0).replace(",", ""))


def _text(element):
    """Whitespace-collapsed text of element, or None if missing or empty."""
    if element is None:
        return None
    return " ".join(element.get_text().split()) or None


def parse_trending(html):
    """Parse the trending page into one dict per repo, in page order.

    Raises ParseError if there are no repos, or a repo lacks its name,
    total stars or stars this week. description, language and forks may be None.
    """
    articles = BeautifulSoup(html, "html.parser").select("article.Box-row")
    if not articles:
        raise ParseError("no repositories found on the trending page")

    rows = []
    for rank, article in enumerate(articles, start=1):
        link = article.select_one("h2 a[href]")
        stars = article.select_one('a[href$="/stargazers"]')
        forks = article.select_one('a[href$="/forks"]')
        # Separator " " keeps adjacent numbers (forks, stars this week) apart.
        week = re.search(r"([\d,]+) stars? this week", article.get_text(" "))
        if link is None or stars is None or week is None:
            raise ParseError(f"row {rank} is missing repo, stars or stars this week")

        repo = link["href"].strip("/")
        rows.append({
            "rank": rank,
            "repo": repo,
            "description": _text(article.select_one("p")),
            "language": _text(article.select_one('[itemprop="programmingLanguage"]')),
            "stars": parse_count(stars.get_text()),
            "forks": parse_count(forks.get_text()) if forks is not None else None,
            "stars_this_week": parse_count(week.group(1)),
            "url": f"https://github.com/{repo}",
        })
    return rows


def save_snapshot(db_path, snapshot_date, rows):
    """Store rows as the snapshot for snapshot_date, replacing any earlier one.

    Delete + insert happen in one transaction, so repos that dropped off the
    list since an earlier run the same day do not linger.
    """
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        with con:
            con.execute(SCHEMA)
            con.execute("DELETE FROM weekly_trending WHERE snapshot_date = ?", (snapshot_date,))
            con.executemany(
                """
                INSERT INTO weekly_trending (
                    snapshot_date, rank, repo, description, language,
                    stars, forks, stars_this_week, url, fetched_at
                ) VALUES (
                    :snapshot_date, :rank, :repo, :description, :language,
                    :stars, :forks, :stars_this_week, :url, :fetched_at
                )
                """,
                [{**row, "snapshot_date": snapshot_date, "fetched_at": fetched_at} for row in rows],
            )
    finally:
        con.close()


def fetch_html(url=TRENDING_URL):
    """GET url and return the body; 3 tries in total, waiting RETRY_DELAYS between."""
    for attempt, delay in enumerate((*RETRY_DELAYS, None), start=1):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as error:
            if delay is None:
                raise
            print(f"attempt {attempt} failed: {error}; retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)


def main():
    """Fetch, parse and save today's (UTC) snapshot. Returns the exit code."""
    snapshot_date = datetime.now(timezone.utc).date().isoformat()
    try:
        rows = parse_trending(fetch_html())
    except (requests.RequestException, ParseError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    save_snapshot(DB_PATH, snapshot_date, rows)
    print(f"{snapshot_date}: saved {len(rows)} repositories to {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
