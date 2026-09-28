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
