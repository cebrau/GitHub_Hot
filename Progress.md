# Progress — GitHub 每週熱門排行抓取

最後更新:2026-09-29

## 專案目標

每週自動抓 GitHub 官方「本週熱門」榜(`github.com/trending?since=weekly`,全部語言),存進 SQLite 長期累積。

起點是使用者給的一張截圖:某影片的「九月第一周 Github 开源热榜」圖卡(前 5 名、本週新增星數、總星數、中文一句話簡介)。
**這次只做資料**;圖卡是使用者選擇「以後再說」的部分,不是放棄。

## 路線與狀態

- [x] 設計規格:`docs/superpowers/specs/2026-09-29-github-weekly-trending-design.md`
- [x] 實作計畫:`docs/superpowers/plans/2026-09-29-github-weekly-trending.md`
- [x] `fetch_trending.py` + 22 個 pytest 全過(不連網,用 `tests/fixtures/trending_weekly.html` 樣本頁)
- [x] 本機真實抓取:2026-09-28(UTC)18 筆;同日重跑不重複
- [x] GitHub 上線:https://github.com/cebrau/GitHub_Hot(public、master、不需任何 secret)
- [x] Workflow 手動觸發成功,bot commit 了 2026-09-29 的 18 筆回 repo
- [ ] 觀察第一次自動排程:**2026-10-05(週一)台灣 08:17**,確認有 bot commit
- [ ] (可選)Codex review 全部程式碼 —— 已 commit 的東西 `/codex-review` 看不到,要用暫時 base branch 的變通法
- [ ] (以後)做成截圖那樣的圖卡:前 5 名 PNG、中文簡介(需要翻譯/摘要,可能要用 LLM)

## 關鍵決定

詳細理由見 `question-log.md`(本機檔,已被全域 gitignore 排除,不在 repo 裡)。

- 爬熱門頁 HTML,不用 GitHub Search API(後者只抓得到本週新建的專案,不是同一份榜)
- requests + BeautifulSoup 單支腳本,不用 Scrapy
- 同一天重抓 = 刪掉當天再整批寫入(不逐筆 upsert,避免掉出榜的專案殘留)
- 必要欄位 `repo`、`stars`、`stars_this_week` 缺一就整批失敗、不寫庫(讓 workflow 報錯寄信);`description`、`language`、`forks` 可為 NULL
- 排程每週一 00:17 UTC(避開整點延遲);job 上限 10 分鐘
- repo 公開:Actions 免費不限分鐘;代價是 60 天無活動會被停排程(每週 bot commit 應能維持)

## 環境備忘

- 本機看新資料前要先 `git pull`(雲端 bot 每週 commit)
- `snapshot_date` 是 UTC 日期,台灣早上跑會是前一天
- 新 repo 推上去後 GitHub 遲遲沒註冊 workflow(`gh workflow run` 回 404、Actions 頁左邊沒有它):改一下 workflow 檔再 push 就立刻註冊了(Product_Hunt 也遇過同樣狀況)
- 熱門頁沒有歷史,無法回補過去週次

## 下一步 / 待確認

- 2026-10-05 之後確認自動排程有跑(Actions 頁有綠勾、`git pull` 拿到新 snapshot)
- 若排程失敗寄信:多半是 GitHub 改版 → 修 `parse_trending`,並重存一份 `tests/fixtures/trending_weekly.html`
