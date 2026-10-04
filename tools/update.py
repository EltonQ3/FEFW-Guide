"""一鍵更新：拉取上游資料 → 合併 → 建置 → 檢查。可交給排程定期執行。

上游：
  1. 姊妹站 EltonQ3/fe-guide-wanlvqiansi（共創表轉錄、招募、送禮、素材）
  2. Rico0319/Fortunes-Weave-Helper 的 data/fwe.db（Game8 英文攻略整理）
  3. 共創表本身（加 --sheet；需要能連到 docs.qq.com，並裝好 Playwright）

用法：
  python3 tools/update.py            # 拉取 1、2，重建並檢查
  python3 tools/update.py --sheet    # 另外嘗試直接讀取共創表
  python3 tools/update.py --offline  # 不拉取，只用本機現有資料重建

結束時列出：資料檔的變動、仍未翻譯的新名稱（source/i18n/_missing.json）、連結檢查結果。
有未翻譯名稱不會中止；連結檢查失敗會以非零狀態結束，方便排程判斷是否要發佈。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARENT = ROOT.parent
UPSTREAMS = [
    ("https://github.com/EltonQ3/fe-guide-wanlvqiansi", PARENT / "fe-guide-wanlvqiansi", "main"),
    ("https://github.com/Rico0319/Fortunes-Weave-Helper", PARENT / "rico0319" / "fortunes-weave-helper", "main"),
]


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check, text=True)


def sync(url: str, dest: Path, branch: str) -> None:
    if (dest / ".git").exists():
        run(["git", "fetch", "--depth", "1", "origin", branch], cwd=dest)
        run(["git", "reset", "--hard", f"origin/{branch}"], cwd=dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "--branch", branch, url, str(dest)], cwd=PARENT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", action="store_true", help="嘗試直接讀取騰訊文檔共創表")
    ap.add_argument("--offline", action="store_true", help="不拉取上游")
    args = ap.parse_args()
    py = sys.executable

    if not args.offline:
        for url, dest, branch in UPSTREAMS:
            sync(url, dest, branch)
    if args.sheet:
        r = run([py, "tools/fetch_sheet.py"], check=False)
        raws = sorted((ROOT / "source" / "sheet" / "raw").glob("*.tsv"))
        if r.returncode == 0 and raws:
            run([py, "tools/ingest_sheet.py", *map(str, raws)])
        else:
            print("共創表讀取失敗，沿用現有資料。", flush=True)

    run([py, "tools/import_seed.py", "--sister", str(UPSTREAMS[0][1])])
    run([py, "tools/import_game8.py", "--db", str(UPSTREAMS[1][1] / "data" / "fwe.db"), "--sister", str(UPSTREAMS[0][1])])
    run([py, "tools/build.py"])
    check = run([py, "tools/check_site.py"], check=False)

    missing = json.loads((ROOT / "source" / "i18n" / "_missing.json").read_text(encoding="utf-8"))
    if missing:
        print("\n未翻譯的新名稱（請補進 source/i18n/*.json）：")
        for kind, items in missing.items():
            print(f"  {kind}: {len(items)} 項，例如 {items[:3]}")
    run(["git", "status", "--short", "--", "source", "assets"], check=False)
    return check.returncode


if __name__ == "__main__":
    sys.exit(main())
