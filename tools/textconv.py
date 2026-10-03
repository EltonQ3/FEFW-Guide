"""簡體 → 繁體轉換。

整頁 HTML 以簡體撰寫與渲染，繁體版在輸出前轉換：
1. 保護不應轉換的片段：<script>/<style>、href/src/srcset 屬性、lang="ja" 元素、
   <!--noconv-->…<!--/noconv--> 區塊（日文漢字、網址、檔名不能被改字）。
2. 先套用 source/glossary.json 的官方譯名（最長詞優先），用私用區字元佔位，
   避免 OpenCC 再改動。
3. 其餘交給 OpenCC s2tw（只換字形，不改兩岸用語，港台讀者都能接受）。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import opencc

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "source" / "glossary.json"

_PROTECT = [
    re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.S),
    re.compile(r"<!--noconv-->.*?<!--/noconv-->", re.S),
    re.compile(r"<(span|small|em|b|i|p|div|dd|dt|td|th|li|h[1-6])\b[^>]*\blang=\"ja\"[^>]*>.*?</\1>", re.S),
    re.compile(r"\b(?:href|src|srcset|data-src|data-url|data-alt)=\"[^\"]*\""),
]


@lru_cache(maxsize=1)
def _cc() -> opencc.OpenCC:
    return opencc.OpenCC("s2tw")


@lru_cache(maxsize=1)
def glossary_pairs() -> tuple[tuple[str, str], ...]:
    if not GLOSSARY.exists():
        return ()
    data = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    pairs = {}
    for entry in data.get("terms", []):
        zhs, zht = entry.get("zhs"), entry.get("zht")
        if zhs and zht:
            pairs[zhs] = zht
        for alias in entry.get("zhsAlt", []):
            if zht:
                pairs.setdefault(alias, zht)
    return tuple(sorted(pairs.items(), key=lambda kv: -len(kv[0])))


def text_to_hant(text: str) -> str:
    """純文字（非 HTML）轉繁體，用於 JSON 搜尋索引等。"""
    return _convert(text, protect_html=False)


def html_to_hant(html: str) -> str:
    return _convert(html, protect_html=True)


def _convert(s: str, protect_html: bool) -> str:
    kept: list[str] = []

    def keep(m: re.Match) -> str:
        kept.append(m.group(0))
        return f"{len(kept) - 1}"

    if protect_html:
        for pat in _PROTECT:
            s = pat.sub(keep, s)
    terms: list[str] = []
    for zhs, zht in glossary_pairs():
        if zhs in s:
            terms.append(zht)
            s = s.replace(zhs, f"{len(terms) - 1}")
    s = _cc().convert(s)
    s = re.sub("(\\d+)", lambda m: terms[int(m.group(1))], s)
    # 被保護的片段裡可能還有佔位（例如 lang=ja 裡又含有 href），反覆還原
    while "" in s:
        s = re.sub("(\\d+)", lambda m: kept[int(m.group(1))], s)
    return s
