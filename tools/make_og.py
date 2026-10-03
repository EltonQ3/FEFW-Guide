"""產生社群分享縮圖 assets/og.jpg（1200×630）。需要 Playwright 與 Chromium；建置後執行一次即可。

用法：python3 tools/build.py && python3 tools/make_og.py [--chromium /path/to/chrome]
"""
import argparse
import asyncio
import http.server
import threading
from functools import partial
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

HTML = """<!doctype html><html lang="zh-Hant" data-theme="dark"><head><meta charset="utf-8">
<link rel="stylesheet" href="static/fonts-tc.css"><link rel="stylesheet" href="static/site.css">
<style>
body{margin:0;width:1200px;height:630px;overflow:hidden;display:grid;grid-template-columns:580px 1fr;align-items:center}
.l{padding:0 0 0 70px}.l h1{font-size:104px;letter-spacing:.08em;margin:6px 0;white-space:nowrap}
.l .k{font-family:var(--latin);letter-spacing:.32em;font-size:17px;color:var(--gold-ink)}
.l p{font-size:25px;color:var(--ink-2);margin-top:22px;letter-spacing:.08em}
.r{display:flex;gap:16px;padding-right:60px}.r .banner{width:136px}
</style></head><body><div class="l"><div class="k">FIRE EMBLEM · FORTUNE'S WEAVE</div><h1 class="gold-text">萬縷千絲</h1>
<p>社群共創資料表 · 圖鑑版</p></div><div class="r">
<div class="banner" style="--c:var(--azure)"><div class="rod"></div><div class="cloth"><img src="assets/portrait/2.webp"></div></div>
<div class="banner" style="--c:var(--violet);margin-top:40px"><div class="rod"></div><div class="cloth"><img src="assets/portrait/3.webp"></div></div>
<div class="banner" style="--c:var(--amber);margin-top:12px"><div class="rod"></div><div class="cloth"><img src="assets/portrait/4.webp"></div></div>
<div class="banner" style="--c:var(--crimson);margin-top:52px"><div class="rod"></div><div class="cloth"><img src="assets/portrait/5.webp"></div></div>
</div></body></html>"""


async def main(chromium: str | None) -> None:
    tmp = DOCS / "_og.html"
    tmp.write_text(HTML, encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        async with async_playwright() as p:
            b = await p.chromium.launch(executable_path=chromium) if chromium else await p.chromium.launch()
            pg = await b.new_page(viewport={"width": 1200, "height": 630})
            await pg.goto(f"http://127.0.0.1:{srv.server_port}/_og.html", wait_until="networkidle")
            await pg.wait_for_timeout(500)
            out = ROOT / "assets" / "og.jpg"
            await pg.screenshot(path=str(out), type="jpeg", quality=86)
            await b.close()
        print("wrote", out.relative_to(ROOT))
    finally:
        srv.shutdown()
        tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--chromium")
    asyncio.run(main(ap.parse_args().chromium))
