# GitHub 每週熱門排行抓取 — 設計

日期:2026-09-29

## 目標

每週自動抓一次 GitHub 官方「本週熱門」榜(<https://github.com/trending?since=weekly>,全部語言),
存進 SQLite 長期累積,由 GitHub Actions 排程執行。

**不做**:分語言的榜、圖卡/影片產出、中文簡介翻譯、過去週次的回補(熱門頁沒有歷史,只能從上線起往後存)。

## 資料來源

爬 `https://github.com/trending?since=weekly` 的 HTML。GitHub 沒有熱門榜的官方 API。

- 每個專案是一個 `article.Box-row`,頁面上通常 10〜25 筆(2026-09-29 實測 18 筆)。
- 榜單順序是 GitHub 自己的熱門排序,**不是**依本週星數大小排。名次照頁面順序記。
- 放棄的替代方案:GitHub Search API(`created:>一週前`,依星數排)。它較穩定,但只找得到「本週新建」的專案,老專案本週爆紅抓不到,不是同一份榜。

## 元件

一支腳本 `fetch_trending.py`,分三個函式,各自可單獨測試:

| 函式 | 做什麼 | 輸入 → 輸出 |
|---|---|---|
| `fetch_html()` | 抓熱門頁 | 無 → HTML 字串 |
| `parse_trending(html)` | 解析出每個專案 | HTML 字串 → `list[dict]` |
| `save_snapshot(db_path, snapshot_date, rows)` | 寫入資料庫 | 路徑、日期、rows → 無 |

`main()` 串起這三步。執行方式:`python fetch_trending.py`,不帶參數。

套件:`requests` 抓網頁、`beautifulsoup4`(內建 `html.parser`)解析。不用 Scrapy——只抓一頁,Scrapy 太重。

## 資料表

`data/github_trending.db` 中的 `weekly_trending` 表:

| 欄位 | 型別 | 說明 |
|---|---|---|
| `snapshot_date` | TEXT | 抓取當天(UTC),如 `2026-10-05` |
| `rank` | INTEGER | 名次,1 起算,照頁面順序 |
| `repo` | TEXT | `owner/name`,如 `anthropics/financial-services` |
| `description` | TEXT | 專案簡介,可為 NULL |
| `language` | TEXT | 主要程式語言,可為 NULL |
| `stars` | INTEGER | 總星數 |
| `forks` | INTEGER | fork 數,頁面沒顯示時為 NULL |
| `stars_this_week` | INTEGER | 本週新增星數 |
| `url` | TEXT | `https://github.com/owner/name` |
| `fetched_at` | TEXT | 抓取時間(UTC ISO 8601) |

主鍵 `(snapshot_date, repo)`。

**同一天重抓 = 整批取代**:先刪掉該 `snapshot_date` 的所有列,再寫入新的,包在同一個 transaction 裡。
不用逐筆 upsert,因為重抓時可能有專案掉出榜,upsert 會留下已不在榜上的舊列。

數字欄位解析:`"1,234"` → `1234`;`"1,234 stars this week"` → `1234`。

## 排程

`.github/workflows/weekly.yml`:

- 每週一 00:17 UTC(台灣 08:17)。避開整點,GitHub 整點排程常延遲。
- 抓到的榜約等於前 7 天(上週一〜週日)。
- 另有 `workflow_dispatch`,可手動按一下跑。
- 跑完把 `data/github_trending.db` commit 回 repo;沒變動就不 commit。
- repo 權限 `contents: write`。不需要任何 secret(熱門頁是公開的)。

## 錯誤處理

原則:**寧可失敗,不要存進壞資料。** workflow 失敗時 GitHub 會寄信通知。

| 狀況 | 行為 |
|---|---|
| 網路錯誤或非 200 | 重試共 3 次(間隔 5、10 秒),仍失敗就 exit 1 |
| 解析出 0 筆 | exit 1,不寫資料庫(多半是網頁改版) |
| 某筆缺必要欄位(`repo`、`stars`、`stars_this_week`) | exit 1,不寫資料庫 |
| 某筆沒有 `description`、`language` 或 `forks` | 正常,存 NULL |

請求帶一般瀏覽器的 `User-Agent`,timeout 30 秒。

## 測試

pytest,不連網路。樣本頁 `tests/fixtures/trending_weekly.html`(2026-09-29 實際抓下的頁面)。

- 解析樣本頁:筆數正確;第 1 筆每個欄位都對。
- 數字含逗號能正確轉成整數。
- 缺 `description` / `language` / `forks` 的專案 → `None`(樣本頁第 1 筆 `anthropics/financial-services` 本來就沒有簡介)。
- 空頁面(沒有 `Box-row`)→ 丟錯。
- 缺必要欄位 → 丟錯。
- `save_snapshot` 同一天寫兩次 → 只留第二次的內容(舊的、掉出榜的列被刪掉)。
- `save_snapshot` 不同天 → 兩天的資料都在。

## 檔案

```
fetch_trending.py
requirements.txt              # requests, beautifulsoup4, pytest
tests/test_fetch_trending.py
tests/fixtures/trending_weekly.html
.github/workflows/weekly.yml
data/github_trending.db       # 由腳本產生,commit 進 repo
README.md
.gitignore
```

## 上線

push 到 GitHub 新 repo `cebrau/GitHub_Hot`(公開或私人,上線時跟使用者確認),
到 Actions 頁手動跑一次驗證,確認 bot 有 commit 資料庫回來。

## 風險

- **GitHub 改網頁結構** → 解析失敗、workflow 報錯寄信。修 `parse_trending` 的選擇器並更新樣本頁即可。
- **公開 repo 60 天沒活動,排程會被 GitHub 停用。** 每週 bot commit 應能維持活動;若仍被停用,到 Actions 頁重新啟用。
