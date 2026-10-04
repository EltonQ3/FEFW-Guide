"""檢查建置結果：站內連結與圖片都指得到檔案、繁簡兩版頁面一一對應、錨點存在。

用法：python3 tools/check_site.py   （失敗時以非零狀態結束）
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
ATTR = re.compile(r'\b(?:href|src)="([^"]+)"')
IDS = re.compile(r'\bid="([^"]+)"')


def main() -> int:
    pages = sorted(p for p in DOCS.rglob("*.html") if p.name != "404.html")
    ids = {p: set(IDS.findall(p.read_text(encoding="utf-8"))) for p in pages}
    problems: dict[str, list[str]] = defaultdict(list)
    checked = 0
    for page in pages:
        html = page.read_text(encoding="utf-8")
        for raw in ATTR.findall(html):
            if raw.startswith(("http://", "https://", "mailto:", "data:", "javascript:")) or raw.startswith("#") and len(raw) == 1:
                continue
            parts = urlsplit(raw)
            if parts.scheme or parts.netloc:
                continue
            checked += 1
            target = (page.parent / unquote(parts.path)).resolve() if parts.path else page
            if parts.path and not target.exists():
                problems[str(page.relative_to(DOCS))].append(f"找不到 {raw}")
                continue
            if parts.fragment and target.suffix == ".html" and target in ids:
                if unquote(parts.fragment) not in ids[target]:
                    # 外傳、兵種等錨點由 JS 處理的不算錯，只檢查實際 id
                    problems[str(page.relative_to(DOCS))].append(f"錨點不存在 {raw}")
    hant = {p.relative_to(DOCS) for p in pages if not str(p.relative_to(DOCS)).startswith("hans/")}
    hans = {p.relative_to(DOCS / "hans") for p in pages if str(p.relative_to(DOCS)).startswith("hans/")}
    for p in sorted(hant ^ hans):
        problems["繁簡對應"].append(f"只有一個語言版本：{p}")
    total = sum(len(v) for v in problems.values())
    print(f"檢查 {len(pages)} 頁、{checked} 個站內連結與圖片：{'全部正常' if not total else f'{total} 個問題'}")
    for page, items in sorted(problems.items()):
        for it in items[:8]:
            print(f"  {page}: {it}")
        if len(items) > 8:
            print(f"  {page}: ……另有 {len(items) - 8} 個")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
