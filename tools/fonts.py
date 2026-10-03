"""依網站實際用字裁切思源宋體（Noto Serif TC / SC 可變字重），輸出自託管字型。

來源是 npm 上的 @fontsource-variable 套件：它已把字型按 Google Fonts 的分組切成
約一百個 woff2 分塊。這裡只保留網站用得到的字，每個分塊另存一個小檔，
@font-face 的 unicode-range 也只列這些字，瀏覽器只下載當頁需要的分塊。
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "fontsource"
PACKAGES = {
    "tc": ("@fontsource-variable/noto-serif-tc", "5.3.0", "noto-serif-tc"),
    "sc": ("@fontsource-variable/noto-serif-sc", "5.3.0", "noto-serif-sc"),
    "latin": ("@fontsource-variable/cinzel", "5.3.0", "cinzel"),
}
# 一律收入的字：標點、數字、拉丁字母（標題裡也會出現）
ALWAYS = set(range(0x20, 0x7F)) | {ord(c) for c in "，。、：；！？「」『』（）《》〈〉·・—…–／～％"}


def package_dir(key: str) -> Path:
    name, ver, _ = PACKAGES[key]
    dest = CACHE / f"{name.replace('/', '__')}-{ver}"
    if (dest / "package").exists():
        return dest / "package"
    dest.mkdir(parents=True, exist_ok=True)
    out = subprocess.run(["npm", "pack", f"{name}@{ver}", "--silent", "--pack-destination", str(dest)],
                         check=True, capture_output=True, text=True).stdout.strip().splitlines()[-1]
    with tarfile.open(dest / out) as tf:
        tf.extractall(dest, filter="data")
    return dest / "package"


def parse_ranges(spec: str) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip().upper().removeprefix("U+")
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.update(range(int(a, 16), int(b, 16) + 1))
        else:
            out.add(int(part, 16))
    return out


def to_ranges(cps: set[int]) -> str:
    items = sorted(cps)
    out, start, prev = [], None, None
    for cp in items:
        if start is None:
            start = prev = cp
        elif cp == prev + 1:
            prev = cp
        else:
            out.append((start, prev))
            start = prev = cp
    if start is not None:
        out.append((start, prev))
    return ",".join(f"U+{a:X}" if a == b else f"U+{a:X}-{b:X}" for a, b in out)


def visible_text(page: str) -> str:
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S)
    page = re.sub(r"<[^>]+>", " ", page)
    return htmllib.unescape(page)


def build(rendered: dict[str, dict[str, str]], out_static: Path) -> dict[str, str]:
    fonts_dir = out_static / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    versions = {}

    latin = package_dir("latin")
    shutil.copy(latin / "files" / "cinzel-latin-wght-normal.woff2", fonts_dir / "latin.woff2")
    shutil.copy(latin / "LICENSE", fonts_dir / "LICENSE-Cinzel.txt")
    latin_face = ("@font-face{font-family:'FW Latin';font-style:normal;font-display:swap;font-weight:400 900;"
                  "src:url(fonts/latin.woff2) format('woff2-variations'),url(fonts/latin.woff2) format('woff2');"
                  "unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20AC,U+2122,U+2212;}\n")

    for lang, key in (("hant", "tc"), ("hans", "sc")):
        pkg = package_dir(key)
        stem = PACKAGES[key][2]
        shutil.copy(pkg / "LICENSE", fonts_dir / f"LICENSE-NotoSerif{key.upper()}.txt")
        used: set[int] = set(ALWAYS)
        for page in rendered[lang].values():
            used.update(ord(ch) for ch in visible_text(page))
        unicode_map = json.loads((pkg / "unicode.json").read_text(encoding="utf-8"))
        faces = [latin_face]
        h = hashlib.sha1()
        for chunk, spec in unicode_map.items():
            idx = chunk.strip("[]")
            cps = parse_ranges(spec) & used
            if not cps:
                continue
            src = pkg / "files" / f"{stem}-{idx}-wght-normal.woff2"
            font = TTFont(src)
            cps &= set(font.getBestCmap())
            if not cps:
                continue
            opts = subset.Options()
            opts.flavor = "woff2"
            opts.layout_features = ["*"]
            opts.name_IDs = [0, 1, 2, 3, 4, 5, 6]
            sub = subset.Subsetter(opts)
            sub.populate(unicodes=cps)
            sub.subset(font)
            font.flavor = "woff2"
            name = f"{key}-{idx}.woff2"
            font.save(fonts_dir / name)
            h.update((fonts_dir / name).read_bytes())
            faces.append(f"@font-face{{font-family:'FW Serif';font-style:normal;font-display:swap;font-weight:200 900;"
                         f"src:url(fonts/{name}) format('woff2-variations'),url(fonts/{name}) format('woff2');"
                         f"unicode-range:{to_ranges(cps)};}}\n")
        css = "".join(faces)
        (out_static / f"fonts-{key}.css").write_text(css, encoding="utf-8")
        versions[key] = h.hexdigest()[:10]
    return versions
