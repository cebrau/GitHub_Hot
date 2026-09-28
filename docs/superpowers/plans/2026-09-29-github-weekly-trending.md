# GitHub Weekly Trending Fetcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Monday, scrape `https://github.com/trending?since=weekly` and store the list in SQLite, run by GitHub Actions.

**Architecture:** One script `fetch_trending.py` with three small functions (`fetch_html` → `parse_trending` → `save_snapshot`) glued by `main()`. Each run writes one "snapshot" (all rows for one UTC date); re-running the same day replaces that snapshot. A weekly GitHub Actions workflow runs the script and commits `data/github_trending.db` back to the repo.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4` (built-in `html.parser`), `sqlite3` (stdlib), `pytest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-29-github-weekly-trending-design.md`

**Conventions:**
- Work in `D:\ScrapyProject\GitHub_Hot`, branch `master`. Git is already initialised; the spec is committed.
- Run tests with `python -m pytest ...` from the project root (so `import fetch_trending` works without a conftest).
- Tests import the module as `import fetch_trending as ft`, so later tasks never have to edit the import line.
- Always `git add` explicit paths. Never `git add -A` — `prompt-log.md` and `question-log.md` in the root are the user's local logs and stay untracked.

**What the real page looks like** (from `tests/fixtures/trending_weekly.html`, saved 2026-09-29, 18 repos). Each repo is one `<article class="Box-row">`:

```html
<article class="Box-row">
  <h2 class="h3 lh-condensed"><a href="/paperclipai/paperclip">…</a></h2>
  <p class="col-9 color-fg-muted my-1 tmp-pr-4">
      The open-source app everyone uses to manage agents at work
  </p>
  <div class="f6 color-fg-muted mt-2">
    <span><span itemprop="programmingLanguage">TypeScript</span></span>
    <a href="/paperclipai/paperclip/stargazers"><svg/> 92,067</a>
    <a href="/paperclipai/paperclip/forks"><svg/> 15,835</a>
    <span>Built by …avatars…</span>
    <span class="d-inline-block float-sm-right"><svg/> 7,364 stars this week</span>
  </div>
</article>
```

Row 1 (`anthropics/financial-services`) has **no `<p>`** (no description). The trending order is GitHub's own and is **not** sorted by stars this week.

---

## File Structure

| File | Responsibility |
|---|---|
| `fetch_trending.py` | The whole fetcher: HTTP fetch with retry, HTML parsing, SQLite write, CLI entry |
| `tests/test_fetch_trending.py` | All tests; no network |
| `tests/fixtures/trending_weekly.html` | Real page saved 2026-09-29 (already on disk, not yet committed) |
| `requirements.txt` | `requests`, `beautifulsoup4`, `pytest` |
| `.gitignore` | Python caches |
| `data/.gitkeep` | Keeps `data/` in git before the first DB exists |
| `.github/workflows/weekly.yml` | Monday schedule + manual trigger, commits the DB |
| `README.md` | What it is, how to run, how to query |
| `data/github_trending.db` | Produced by the script, committed |

---

### Task 1: Project skeleton

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `data/.gitkeep`
- Commit: `tests/fixtures/trending_weekly.html` (already exists)

- [ ] **Step 1: Create `requirements.txt`**

```
requests>=2.31
beautifulsoup4>=4.12
pytest>=8.0
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

- [ ] **Step 3: Create empty `data/.gitkeep`**

Run (Bash): `mkdir -p data && touch data/.gitkeep`

- [ ] **Step 4: Install and check packages**

Run: `pip install -r requirements.txt`
Expected: ends with "Successfully installed …" or "Requirement already satisfied" for all three.

- [ ] **Step 5: Confirm the fixture is there**

Run: `python -c "print(open('tests/fixtures/trending_weekly.html', encoding='utf-8').read().count('class=\"Box-row\"'))"`
Expected: `18`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore data/.gitkeep tests/fixtures/trending_weekly.html
git commit -m "chore: project skeleton and sample trending page"
```

---

### Task 2: `parse_count` — turn "1,234" into 1234

**Files:**
- Create: `fetch_trending.py`
- Create: `tests/test_fetch_trending.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_fetch_trending.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'fetch_trending'`

- [ ] **Step 3: Write minimal implementation**

Create `fetch_trending.py` (all imports and constants go in now so later tasks only add functions):

```python
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


class ParseError(Exception):
    """The trending page does not look the way we expect (probably redesigned)."""


def parse_count(text):
    """'1,234' or '1,234 stars this week' -> 1234."""
    match = re.search(r"\d[\d,]*", text)
    if not match:
        raise ParseError(f"no number in {text!r}")
    return int(match.group(0).replace(",", ""))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add fetch_trending.py tests/test_fetch_trending.py
git commit -m "feat: parse_count for comma-separated numbers"
```

---

### Task 3: `parse_trending` — HTML to list of dicts

**Files:**
- Modify: `fetch_trending.py` (append after `parse_count`)
- Modify: `tests/test_fetch_trending.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fetch_trending.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: the 6 `parse_count` tests PASS; the new tests FAIL with `AttributeError: module 'fetch_trending' has no attribute 'parse_trending'`

- [ ] **Step 3: Write the implementation**

Append to `fetch_trending.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add fetch_trending.py tests/test_fetch_trending.py
git commit -m "feat: parse weekly trending page into rows"
```

---

### Task 4: `save_snapshot` — write one day's rows, replacing any earlier run that day

**Files:**
- Modify: `fetch_trending.py` (add `SCHEMA` constant after `RETRY_DELAYS`; append `save_snapshot`)
- Modify: `tests/test_fetch_trending.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fetch_trending.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: 14 PASS; 3 new FAIL with `AttributeError: module 'fetch_trending' has no attribute 'save_snapshot'`

- [ ] **Step 3: Write the implementation**

In `fetch_trending.py`, right after the `RETRY_DELAYS = (5, 10)` line, add:

```python

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
```

Append to the end of `fetch_trending.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: 17 passed

- [ ] **Step 5: Commit**

```bash
git add fetch_trending.py tests/test_fetch_trending.py
git commit -m "feat: save_snapshot replaces a day's rows atomically"
```

---

### Task 5: `fetch_html` — GET with 3 tries

**Files:**
- Modify: `fetch_trending.py` (append)
- Modify: `tests/test_fetch_trending.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fetch_trending.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: 17 PASS; 2 new FAIL with `AttributeError: module 'fetch_trending' has no attribute 'fetch_html'`

- [ ] **Step 3: Write the implementation**

Append to `fetch_trending.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add fetch_trending.py tests/test_fetch_trending.py
git commit -m "feat: fetch_html with retry"
```

---

### Task 6: `main` — glue + exit codes

**Files:**
- Modify: `fetch_trending.py` (append)
- Modify: `tests/test_fetch_trending.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fetch_trending.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_fetch_trending.py -v`
Expected: 19 PASS; 3 new FAIL with `AttributeError: module 'fetch_trending' has no attribute 'main'`

- [ ] **Step 3: Write the implementation**

Append to `fetch_trending.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/ -v`
Expected: 22 passed

- [ ] **Step 5: Commit**

```bash
git add fetch_trending.py tests/test_fetch_trending.py
git commit -m "feat: main entry point with exit codes"
```

---

### Task 7: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/weekly.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: Weekly GitHub trending

on:
  # Monday 00:17 UTC = 08:17 Taiwan. Off the hour: top-of-hour cron runs are often delayed.
  schedule:
    - cron: "17 0 * * 1"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"

      - run: pip install -r requirements.txt

      - name: Fetch trending
        run: python fetch_trending.py

      - name: Commit database
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/github_trending.db
          if git diff --cached --quiet; then
            echo "No changes"
          else
            git commit -m "data: weekly trending snapshot ($(date -u +%F))"
            git push
          fi
```

- [ ] **Step 2: Check the YAML parses**

Run: `python -c "import yaml, sys; d = yaml.safe_load(open('.github/workflows/weekly.yml', encoding='utf-8')); print(d['jobs']['fetch']['steps'][3]['run'])"`
Expected: `python fetch_trending.py`
(If `yaml` is not installed: `pip install pyyaml` first. It is only for this check, do not add it to `requirements.txt`.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/weekly.yml
git commit -m "ci: weekly trending workflow"
```

---

### Task 8: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

````markdown
# GitHub 每週熱門排行

每週自動抓取 GitHub 官方「本週熱門」榜(<https://github.com/trending?since=weekly>,全部語言),
寫入 SQLite 長期累積,由 GitHub Actions 每週一排程執行。

熱門頁沒有歷史紀錄,資料只能從上線那天起往後累積,無法回補過去的週次。

## 資料內容

`data/github_trending.db` 中的 `weekly_trending` 表,每次約 10〜25 筆:

| 欄位 | 說明 |
|---|---|
| `snapshot_date` | 抓取當天(UTC),如 `2026-10-05` |
| `rank` | 名次(1 起算),照 GitHub 頁面順序,不是依本週星數排 |
| `repo` | `owner/name` |
| `description` | 專案簡介,可能為空 |
| `language` | 主要程式語言,可能為空 |
| `stars` | 總星數 |
| `forks` | fork 數,可能為空 |
| `stars_this_week` | 本週新增星數 |
| `url` | 專案連結 |
| `fetched_at` | 抓取時間(UTC) |

主鍵為 `(snapshot_date, repo)`。同一天重抓會整批取代當天資料。

## 本機執行

```powershell
pip install -r requirements.txt
python fetch_trending.py
```

執行測試:

```
python -m pytest tests/
```

## GitHub 自動抓取

- 每週一 00:17 UTC(台灣 08:17)自動執行,抓完把資料庫 commit 回 repo。
- 到 **Actions** 頁籤 → **Weekly GitHub trending** → **Run workflow** 可手動跑。
- 不需要任何 token 或 secret。
- 若 workflow 失敗(GitHub 會寄信),多半是 GitHub 改了熱門頁的網頁結構:
  修 `fetch_trending.py` 的 `parse_trending`,並重新存一份 `tests/fixtures/trending_weekly.html`。
- 本機看新資料前要先 `git pull`。

## 查詢範例

```bash
# 最新一次的榜單
sqlite3 data/github_trending.db "SELECT rank, repo, stars_this_week FROM weekly_trending WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM weekly_trending) ORDER BY rank"

# 最常上榜的程式語言
sqlite3 data/github_trending.db "SELECT language, COUNT(*) FROM weekly_trending GROUP BY language ORDER BY 2 DESC LIMIT 10"

# 匯出成 CSV
sqlite3 -header -csv data/github_trending.db "SELECT * FROM weekly_trending" > trending.csv
```
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README"
```

---

### Task 9: Real run against GitHub

**Files:**
- Create (by running the script): `data/github_trending.db`

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: 22 passed

- [ ] **Step 2: Run the real fetch**

Run: `python fetch_trending.py`
Expected: exit code 0 and one line like `2026-09-29: saved 18 repositories to D:\ScrapyProject\GitHub_Hot\data\github_trending.db` (the count can be anything from about 10 to 25).

- [ ] **Step 3: Look at what was stored**

Run:

```bash
python -c "
import sqlite3
con = sqlite3.connect('data/github_trending.db')
for row in con.execute('SELECT snapshot_date, rank, repo, language, stars, forks, stars_this_week FROM weekly_trending ORDER BY rank LIMIT 5'):
    print(row)
print(con.execute('SELECT COUNT(*), SUM(description IS NULL), SUM(forks IS NULL) FROM weekly_trending').fetchone())
"
```

Expected: 5 rows with today's UTC date, ranks 1–5, real repo names, all numbers > 0. The last line is `(count, few_or_zero, 0_or_few)`. If every `description` or every `forks` is NULL, parsing is broken — stop and investigate.

- [ ] **Step 4: Run it again to prove the same-day rerun is safe**

Run: `python fetch_trending.py` then the Step 3 command again.
Expected: same count as before (no duplicates).

- [ ] **Step 5: Commit the first snapshot**

```bash
git add data/github_trending.db
git commit -m "data: first weekly trending snapshot"
```

---

### Task 10: Put it on GitHub

This task is outward-facing. **Ask the user before Step 2**: public or private repo? (Public: free Actions minutes, anyone can see the data. Private: 2,000 free minutes/month, far more than this needs.)

- [ ] **Step 1: Check `gh` is logged in**

Run: `gh auth status`
Expected: `Logged in to github.com account cebrau`. If not, ask the user to run `! gh auth login`.

- [ ] **Step 2: Create the repo and push** (after the user picked public/private)

Run: `gh repo create cebrau/GitHub_Hot --public --source . --push` (or `--private`)
Expected: prints the repo URL, and `git push` of `master` succeeds.

- [ ] **Step 3: Trigger the workflow once by hand**

Run: `gh workflow run weekly.yml`
If it says the workflow is not found, wait a minute and retry. (On the Product_Hunt repo, GitHub took several minutes to register a new workflow; editing the workflow file and pushing again fixed it.)

- [ ] **Step 4: Watch it finish**

Run: `gh run list --workflow weekly.yml --limit 1` to get the run id, then `gh run watch <id> --exit-status`
Expected: all steps green. The "Commit database" step prints either `No changes` or a commit.

- [ ] **Step 5: Pull the bot's commit**

Run: `git pull`
Expected: fast-forward that updates `data/github_trending.db`, or "Already up to date." if the bot had nothing new to commit.
