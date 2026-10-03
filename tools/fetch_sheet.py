"""用 Chromium 打開騰訊文檔共創表，逐個分頁複製儲存格內容，存成 TSV。

做法與人手操作一樣：切到分頁 → 點一下表格 → 全選 → 複製 → 讀剪貼簿。
不需要登入；若表格作者關閉了複製，請改用「導出為 → 本地 Excel」再交給 ingest_sheet.py。

用法：
  python3 tools/fetch_sheet.py                 # 全部分頁
  python3 tools/fetch_sheet.py --tab BB08J2    # 指定分頁
  python3 tools/ingest_sheet.py source/sheet/raw/*.tsv
  python3 tools/build.py

輸出：source/sheet/raw/<分頁名>.tsv，以及 debug/ 下的截圖（出錯時方便判斷原因）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "source" / "sheet" / "raw"
DEBUG = ROOT / "debug"
DOC_ID = "DV0N0VUZLSXRmUWFq"
URL = f"https://docs.qq.com/sheet/{DOC_ID}"


async def list_tabs(page) -> list[dict]:
    """從頁面底部的分頁列讀出分頁名稱與代號。"""
    tabs = await page.evaluate(
        """() => {
          const out = [];
          const els = document.querySelectorAll('[class*="sheet-tab"] [class*="name"], [role="tab"], [class*="tab-item"]');
          els.forEach(el => {
            const host = el.closest('[data-id],[data-sheet-id],[id]');
            const id = host && (host.getAttribute('data-id') || host.getAttribute('data-sheet-id') || '');
            const name = (el.textContent || '').trim();
            if (name) out.push({id, name});
          });
          return out;
        }"""
    )
    seen, out = set(), []
    for t in tabs:
        if t["name"] not in seen:
            seen.add(t["name"])
            out.append(t)
    return out


async def copy_grid(page) -> str:
    await page.mouse.click(400, 300)
    mod = "Meta" if (await page.evaluate("navigator.platform")).startswith("Mac") else "Control"
    await page.keyboard.press(f"{mod}+A")
    await page.wait_for_timeout(400)
    await page.keyboard.press(f"{mod}+C")
    await page.wait_for_timeout(1200)
    return await page.evaluate("navigator.clipboard.readText()")


async def main(only: str | None, chromium: str | None, headed: bool) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    DEBUG.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=chromium, headless=not headed) if chromium else await p.chromium.launch(headless=not headed)
        ctx = await browser.new_context(viewport={"width": 1600, "height": 1000}, locale="zh-CN",
                                        permissions=["clipboard-read", "clipboard-write"])
        page = await ctx.new_page()
        await page.goto(URL + (f"?tab={only}" if only else ""), wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(8000)
        await page.screenshot(path=str(DEBUG / "sheet.png"))
        tabs = [{"id": only, "name": only}] if only else await list_tabs(page)
        (DEBUG / "tabs.json").write_text(json.dumps(tabs, ensure_ascii=False, indent=1), encoding="utf-8")
        if not tabs:
            print("讀不到分頁列，請看 debug/sheet.png；可改用匯出的 xlsx。")
        for t in tabs:
            if t.get("id"):
                await page.goto(f"{URL}?tab={t['id']}", wait_until="domcontentloaded", timeout=90000)
            else:
                await page.get_by_text(t["name"], exact=True).first.click()
            await page.wait_for_timeout(5000)
            text = await copy_grid(page)
            safe = re.sub(r'[\\/:*?"<>|]', "_", t["name"])
            await page.screenshot(path=str(DEBUG / f"{safe}.png"))
            if not text.strip():
                print(f"{t['name']}: 剪貼簿是空的（可能禁止複製），已存截圖")
                continue
            (RAW / f"{safe}.tsv").write_text(text, encoding="utf-8")
            print(f"{t['name']}: {text.count(chr(10)) + 1} 行 → source/sheet/raw/{safe}.tsv")
        await browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tab")
    ap.add_argument("--chromium")
    ap.add_argument("--headed", action="store_true")
    a = ap.parse_args()
    asyncio.run(main(a.tab, a.chromium, a.headed))
