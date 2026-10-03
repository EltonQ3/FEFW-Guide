# 萬縷千絲 · 資料織錦

《Fire Emblem 萬縷千絲》（火焰紋章 萬縷千絲／ファイアーエムブレム 万紫千紅）社群共創資料表的圖鑑版網站。

原表是[騰訊文檔共創表](https://docs.qq.com/sheet/DV0N0VUZLSXRmUWFq?tab=BB08J2)：資料齊全，但在手機上很難閱讀。本站把每個分頁重新排成專門的版面，可以搜尋、篩選，電腦和手機都好讀。

- 角色名鑑：依陣營排列的立繪卡片；點開看四條路線的挖角條件（支援、名聲、交涉）、喜好與推薦禮物
- 兵種職業：六個階級的兵種階梯，卡片或表格兩種檢視
- 外傳：接取窗口日曆，四條路線各一種顏色
- 血印：發動機率刻度環、效果、持有者
- 神之加護：七神三階效果與白沙消耗
- 全站搜尋（按 `/` 或 Ctrl+K）、深淺色切換、繁簡切換

繁體為主（網站根目錄），簡體在 `hans/`。

## 本機預覽

```sh
python3 -m pip install -r requirements.txt
python3 tools/build.py
cd docs && python3 -m http.server 8770
```

瀏覽器打開 <http://127.0.0.1:8770>。建置需要 Python 3.11+ 與 npm（第一次建置時用 `npm pack` 下載思源宋體與 Cinzel 字型到 `.cache/`）。讀者打開網站不需要任何伺服器程式。

## 發佈

`docs/` 是完整的靜態網站，已提交到倉庫：

- **GitHub Pages**：倉庫 Settings → Pages → Source 選「Deploy from a branch」，分支 `main`、資料夾 `/docs`。網址為 `https://eltonq3.github.io/FEFW-Guide/`。
- **Cloudflare Pages**：連接本倉庫，Build command 留空，Build output directory 填 `docs`。換網域時把 `tools/build.py` 的 `SITE["base_url"]` 改掉再重新建置（影響 canonical、sitemap、分享縮圖與 404 頁）。

## 資料流程

```
source/*.json（簡體）──┐
source/sheet/*.json ───┼─ tools/build.py ─→ docs/（繁體）＋ docs/hans/（簡體）
source/glossary.json ──┘
```

| 檔案 | 內容 |
|---|---|
| `source/characters.json` | 角色：陣營、四路線招募條件、喜好與禮物 |
| `source/classes.json` | 兵種：階級、移動、考試、訓練、特技、精通 |
| `source/paralogues.json` | 外傳：各路線章節與日期窗口、地點、報酬 |
| `source/seals.json` | 血印：發動機率、效果、持有者 |
| `source/blessings.json` | 神之加護：三階效果與白沙消耗 |
| `source/sheet/tabs.json` | 共創表分頁清單與通用版面設定 |
| `source/glossary.json` | 簡體 → 港台官方繁體譯名對照 |

目前這些資料由 `tools/import_seed.py` 從姊妹站 [fe-guide-wanlvqiansi](https://github.com/EltonQ3/fe-guide-wanlvqiansi) 匯入；兵種、外傳、血印原本就是該站從同一張共創表轉錄並交叉核對的。

### 接入共創表的其他分頁

在騰訊文檔選「導出為 → 本地 Excel」，然後：

```sh
python3 tools/ingest_sheet.py 共創表.xlsx
python3 tools/build.py
```

每個工作表會變成 `source/sheet/<代號>.json`，並登記到 `tabs.json`。特技、戰技、武器、道具等分頁會自動套用通用版面（卡片／表格切換、搜尋、篩選）。在 `tabs.json` 裡可以調整：

- `primary`：卡片標題用哪一欄（預設取第一個大多不重複的欄）
- `group`：依哪一欄分組
- `filters`：哪些欄做成篩選按鈕（選項超過 24 個的欄不會顯示）
- `badges`：哪些欄顯示成標籤；`hide`：卡片上不顯示的欄；`colorBy`：依哪一欄上色
- `title`、`en`、`intro`、`color`、`icon`：頁面標題與外觀

已有專門版面的分頁（兵種、外傳、血印、加護）只會更新資料檔，不會另外產生通用頁。

## 繁體譯名

共創表用的是簡體社群譯名，遊戲另有港台官方繁中版，部分名字不同（例如「蒂亚拉」在繁中版是「媞雅拉」，「利纳利亚朝露」是「姬金魚草的朝露」）。繁體頁面的處理順序：

1. 先套用 `source/glossary.json` 的對照（任天堂官方公布者優先，其次是多個繁中玩家站一致引用的遊戲內名稱）
2. 其餘用 OpenCC `s2tw` 只做字形轉換，不改兩岸用語
3. 日文（`lang="ja"`）、網址、檔名不轉換

新增對照時，在 `glossary.json` 加一筆並標明 `status` 與出處，重新建置即可。

## 美術與授權

人物立繪、頭像、兵種與血印圖示來自姊妹站素材；遊戲內容與圖像版權屬於 Nintendo / INTELLIGENT SYSTEMS。本站為非官方玩家整理。

字型按頁面用字裁切後自託管，不依賴第三方字型服務：思源宋體（Noto Serif TC / SC）與 Cinzel，皆為 SIL Open Font License 1.1，授權全文隨字型放在 `docs/static/fonts/`。
