# 萬縷千絲 · 資料織錦

《Fire Emblem 萬縷千絲》（火焰紋章 萬縷千絲／ファイアーエムブレム 万紫千紅）的玩家圖鑑網站。

以社群[騰訊文檔共創表](https://docs.qq.com/sheet/DV0N0VUZLSXRmUWFq?tab=BB08J2)為本，把表中仍待完善的數值（成長率、支援、武器、禮物等）用 Game8 英文攻略補上，重新設計成手機和電腦都好讀的網站。繁體版在網站根目錄，簡體版在 `hans/`。

## 網站內容

| 頁面 | 內容 |
|---|---|
| 首頁 | 彩窗玫瑰窗主視覺、全站搜尋、各區入口、四條路線、成長之最、資料完成度 |
| 角色（63 位，每人一頁） | 陣營、個人技能、九項成長率（雷達圖＋長條）、擅長技能、爆炎技、血印、習得魔法、A／B／C 支援、喜好與禮物、四路線加入條件 |
| 招募規劃 | 選路線 → 按名聲門檻排出可挖角的同伴；可依「我的名聲」篩選、勾選已招募（存在瀏覽器） |
| 兵種（60 種） | 六階階梯、考試與訓練、特技、精通、成長率加成；「角色＋兵種」成長模擬 |
| 羈絆 | 支援輪盤：內圈 A、外圈 B／C，共 230 組 |
| 外傳 | 接取窗口日曆、各路線章節與日期；Game8 日期不同時另外註明 |
| 圖鑑 | 武器與魔法（90）、禮物（102）、血印（12）、爆炎技（42）、神之加護（7）、計算公式 |

其他功能：全站搜尋（`/` 或 Ctrl+K，簡繁都搜得到）、深淺色、繁簡切換、表格可排序、手機版版面。

## 資料來源與合併

```
共創表（經姊妹站轉錄）──→ tools/import_seed.py ──→ source/base/*.json
Game8 資料庫 fwe.db ─────┐
source/i18n/*.json（英→中）├→ tools/import_game8.py ─→ source/*.json ─→ tools/build.py ─→ docs/
source/base/*.json ──────┘
共創表匯出檔（xlsx／tsv）──→ tools/ingest_sheet.py ──→ source/sheet/*.json（通用分頁）
```

- **共創表優先**：招募條件、喜好、兵種考試、外傳日期、血印名稱以共創表（姊妹站 [fe-guide-wanlvqiansi](https://github.com/EltonQ3/fe-guide-wanlvqiansi) 的轉錄）為準。
- **Game8 補空缺**：成長率、兵種成長加成、支援、個人技能、爆炎技、魔法、武器、禮物，以及共創表尚未收錄的 8 位第二、三部角色與 6 種兵種，取自開源專案 [Fortunes-Weave-Helper](https://github.com/Rico0319/Fortunes-Weave-Helper) 整理的 Game8 資料庫。共創表欄位寫著「尚未收錄」「待核對」時，以 Game8 補上並在頁面註明。
- **衝突時**以共創表為準，Game8 的不同記載另外標示（外傳日期、血印持有者）。

### 譯名

每個名稱都帶依據：`official`（任天堂官方）、`sheet`（共創表／戰術手帖）、`community`（中文攻略站摘要）、`provisional`（本站暫譯）。暫譯與社群譯名在頁面上以虛線標示，滑鼠停留可看英文原名。

- 英→中對照：`source/i18n/core.json`（角色、陣營、兵種、能力值）、`abilities.json`、`blaze.json`、`seals.json`、`weapons.json`、`gifts.json`
- 繁體官方名：`source/glossary.json`（例如「蒂亚拉」→「媞雅拉」），其餘以 OpenCC `s2tw` 轉字形
- 新資料出現對照表沒有的英文名時，匯入不會失敗，會保留英文並列在 `source/i18n/_missing.json`

## 本機建置與預覽

需要 Python 3.11+、npm（第一次建置時下載思源宋體與 Cinzel 到 `.cache/`），以及上游資料：

```sh
python3 -m pip install -r requirements.txt
python3 tools/update.py            # 拉取姊妹站與 Fortunes-Weave-Helper，合併、建置、檢查
cd docs && python3 -m http.server 8770
```

只改了模板或樣式時，`python3 tools/build.py` 即可；`python3 tools/check_site.py` 檢查站內連結、圖片與錨點。

## 定期更新

`tools/update.py` 一次完成「拉取上游 → 合併 → 建置 → 檢查」，結束時列出資料變動與未翻譯的新名稱；連結檢查失敗時以非零狀態結束。可以交給排程（例如 GitHub Actions 的 cron、或 Claude 的定期任務）每天執行，有變動再提交。

加上 `--sheet` 會用 Chromium 直接讀取騰訊文檔共創表（`tools/fetch_sheet.py`，需要能連到 docs.qq.com；這部分尚未在可連線的環境實測）。也可以手動匯出：

```sh
python3 tools/ingest_sheet.py 共創表.xlsx   # 每個工作表登記到 source/sheet/tabs.json
python3 tools/build.py
```

特技、戰技、道具等沒有專門版面的分頁會自動生成可搜尋、可篩選的頁面，並列進圖鑑；`tabs.json` 可設定標題欄、分組欄、篩選欄等。

## 發佈

`docs/` 是完整靜態網站：

- **GitHub Pages**：Settings → Pages → Deploy from a branch → `main` / `docs`，網址 `https://eltonq3.github.io/FEFW-Guide/`
- **Cloudflare Pages**：Build output directory 填 `docs`。換網域時改 `tools/build.py` 的 `SITE["base_url"]` 與 `base_path` 再建置。

## 美術與授權

人物立繪、頭像、兵種與血印圖示來自姊妹站素材；遊戲內容與圖像版權屬於 Nintendo / INTELLIGENT SYSTEMS。數值資料參考 Game8，經 Fortunes-Weave-Helper 整理，本站只取用數值與簡短說明並譯為中文。字型（思源宋體、Cinzel，SIL OFL 1.1）按頁面用字裁切後自託管。本站為非官方玩家整理。
