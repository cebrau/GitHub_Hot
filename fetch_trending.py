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
