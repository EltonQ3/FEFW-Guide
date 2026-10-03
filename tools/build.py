"""建置萬縷千絲資料織錦站。

source/*.json（簡體）→ docs/（繁體，網站根目錄）與 docs/hans/（簡體）。
用法：python3 tools/build.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textconv import html_to_hant, text_to_hant, glossary_pairs  # noqa: E402
import fonts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source"
WEB = ROOT / "web"
OUT = ROOT / "docs"
ASSETS = ROOT / "assets"

SITE = {
    "base_url": "https://eltonq3.github.io/FEFW-Guide",
    "sheet_url": "https://docs.qq.com/sheet/DV0N0VUZLSXRmUWFq?tab=BB08J2",
    "updated": "",
}

LANGS = {
    "hant": {"prefix": "", "root": "", "html_lang": "zh-Hant", "font": "tc"},
    "hans": {"prefix": "hans/", "root": "../", "html_lang": "zh-Hans", "font": "sc"},
}

ROUTES = [
    {"key": "kai", "name": "凯伊篇", "short": "凯伊", "en": "CAI · RIBEIRA", "cid": "2", "color": "var(--r-kai)", "faction": "ribeira"},
    {"key": "dietrich", "name": "迪托利希篇", "short": "迪托利希", "en": "DIETRICH · LAMINE", "cid": "3", "color": "var(--r-dietrich)", "faction": "lamine"},
    {"key": "theodora", "name": "赛奥朵拉篇", "short": "赛奥朵拉", "en": "THEODORA · MEGAIRA", "cid": "4", "color": "var(--r-theodora)", "faction": "megaira"},
    {"key": "leda", "name": "蕾达篇", "short": "蕾达", "en": "LEDA · ROSE STORM", "cid": "5", "color": "var(--r-leda)", "faction": "rose"},
]

FACTIONS = [
    {"key": "ribeira", "name": "利贝拉之风", "short": "利贝拉之风", "note": "凯伊篇", "mark": "利", "color": "var(--azure)"},
    {"key": "lamine", "name": "拉弥努家族", "short": "拉弥努家族", "note": "迪托利希篇", "mark": "拉", "color": "var(--violet)"},
    {"key": "megaira", "name": "美盖拉的灯火", "short": "美盖拉的灯火", "note": "赛奥朵拉篇", "mark": "美", "color": "var(--amber)"},
    {"key": "rose", "name": "蔷薇风暴", "short": "蔷薇风暴", "note": "蕾达篇", "mark": "蔷", "color": "var(--crimson)"},
    {"key": "savior", "name": "真主角", "short": "真主角", "note": "伊修玛尔", "mark": "救", "color": "var(--pearl)"},
    {"key": "mane", "name": "炎之鬃", "short": "炎之鬃", "note": "贝特朗队", "mark": "炎", "color": "var(--ember)"},
    {"key": "moon", "name": "月之谎", "short": "月之谎", "note": "", "mark": "月", "color": "var(--moon)"},
    {"key": "linaria", "name": "利纳利亚朝露", "short": "利纳利亚朝露", "note": "", "mark": "露", "color": "var(--jade)"},
    {"key": "crow", "name": "白鸦新娘团", "short": "白鸦新娘团", "note": "", "mark": "鸦", "color": "var(--pearl)"},
    {"key": "free", "name": "无派系 / 其他", "short": "无派系", "note": "", "mark": "众", "color": "var(--stone)"},
]

TIERS = [
    ("基础", "base", "I", "初始兵种"),
    ("初级", "beginner", "II", "初级考试票证"),
    ("中级", "intermediate", "III", "中级考试票证"),
    ("上级与高级", "advanced", "IV", "第一部可开放"),
    ("最上级", "master", "V", "第三部第二区分起"),
    ("神将", "divine", "VI", "第三部第四区分起 · 每种限一人"),
]
FAMILY_COLORS = {
    "斗士系": "var(--crimson)", "猎兵系": "var(--jade)", "士兵系": "var(--amber)",
    "魔道系": "var(--violet)", "飞行系": "var(--azure)",
}
GOD_STYLE = {
    "aurora": ("var(--amber)", "曙"), "mars": ("var(--crimson)", "战"), "smyrnos": ("var(--violet)", "智"),
    "jurah": ("var(--jade)", "护"), "kalla": ("var(--azure)", "风"), "credna": ("var(--moon)", "视"),
    "fortuna": ("var(--gold)", "命"),
}

NAV = [
    {"file": "index.html", "label": "首页"},
    {"file": "characters.html", "label": "角色"},
    {"file": "classes.html", "label": "兵种"},
    {"file": "paralogues.html", "label": "外传"},
    {"file": "seals.html", "label": "血印"},
    {"file": "blessings.html", "label": "神之加护"},
    {"file": "about.html", "label": "来源与译名"},
]

STATUS_LABEL = {"official": "官方", "ingame-tc": "游戏内繁中", "converted": "字形转换"}


def load(name: str) -> dict:
    return json.loads((SRC / f"{name}.json").read_text(encoding="utf-8"))


# ── 資料整理 ───────────────────────────────────────────────

def doy(md: str | None) -> int | None:
    if not md:
        return None
    m, d = (int(x) for x in md.split("/"))
    return (dt.date(2025, m, d) - dt.date(2025, 1, 1)).days


def md_label(n: int) -> str:
    d = dt.date(2025, 1, 1) + dt.timedelta(days=n)
    return f"{d.month}/{d.day}"


def prepare() -> dict:
    chars = load("characters")["items"]
    classes_doc, paras_doc, seals_doc, gods_doc = load("classes"), load("paralogues"), load("seals"), load("blessings")
    classes, paras, seals, gods = classes_doc["items"], paras_doc["items"], seals_doc["items"], gods_doc["items"]
    by_name = {}
    for c in chars:
        by_name[c["name"]] = c
        for a in c.get("aliases", []):
            by_name.setdefault(a, c)
    fac = {f["key"]: f for f in FACTIONS}

    # 角色
    for c in chars:
        # 別名轉成繁體後若與本名相同（例如蒂亚拉／媞雅拉），不再重複列出
        c["aliases_hant"] = [a for a in c.get("aliases", []) if text_to_hant(a) != text_to_hant(c["name"])]
        c["routes_ok"] = [r["key"] for r in ROUTES if c["recruit"][r["key"]]["kind"] != "none"]
        c["is_lead"] = c["id"] in ("2", "3", "4", "5", "hero")
        c["lead_label"] = "真主角" if c["id"] == "hero" else "主角"
        c["seals"] = [s for s in seals if c["name"] in s["holders"]]
        c["paras"] = [p for p in paras if p["person"] == c["name"]]
        c["para_unlocks"] = [p for p in paras if c["name"] in (p.get("people") or "")]
        needs = " ".join(" ".join(v.get("needs", [])) + " " + v.get("text", "") for v in c["recruit"].values())
        c["search"] = " ".join([c["name"], *c.get("aliases", []), c["jp"], c["en"], c["likes"], c["hobbies"], c["gifts"],
                                fac[c["faction"]]["name"], needs])
    order = [f["key"] for f in FACTIONS]
    factions_present = []
    for f in FACTIONS:
        members = [c for c in chars if c["faction"] == f["key"]]
        if members:
            factions_present.append({**f, "members": members})
    chars.sort(key=lambda c: order.index(c["faction"]))

    # 兵種
    tier_info = {t[0]: t for t in TIERS}
    for k in classes:
        head, _, rest = k["features"].partition("，")
        parts = [p.strip() for p in head.split("·")]
        unit_kinds = ("步兵", "骑兵", "重装", "飞行")
        if parts[0] in unit_kinds:  # 「步兵」「重装 · 骑兵」這類只寫類型、沒有系統的
            k["family"], kinds = "通用", parts
        else:
            k["family"], kinds = parts[0], parts[1:]
        k["kind"] = " ".join(kinds)          # 篩選用，空格分隔可同時符合多個類型
        k["kind_label"] = " · ".join(kinds)
        k["skills"] = re.findall(r"【([^】]+)】", rest)
        m = re.match(r"【([^】]+)】\s*[（(](\d+)[)）]", k.get("mastery", ""))
        k["mastery_name"], k["mastery_exp"] = (m.group(1), m.group(2)) if m else (k.get("mastery", "").strip("【】"), "")
        k["tier_key"] = tier_info[k["tier"]][1]
        k["color"] = FAMILY_COLORS.get(k["family"], "var(--stone)")
        k["search"] = " ".join([k["name"], k["tier"], k["family"], k["kind"], k["exam"], k["unlock"], k["training"],
                                " ".join(k["skills"]), k["mastery_name"], k.get("restriction", "")])
    tiers_present = []
    for name, key, numeral, note in TIERS:
        members = [k for k in classes if k["tier"] == name]
        if members:
            phase = members[0].get("phase", "").split("；")[0]
            tiers_present.append({"name": name, "key": key, "numeral": numeral, "note": f"{note} · {phase}" if phase else note,
                                  "members": members})
    families = sorted({k["family"] for k in classes}, key=lambda f: list(FAMILY_COLORS).index(f) if f in FAMILY_COLORS else 99)
    kinds = [x for x in ("步兵", "骑兵", "重装", "飞行") if any(x in k["kind"].split() for k in classes)]

    # 外傳
    starts, ends = [], []
    for p in paras:
        for ws in p["routes"].values():
            for w in ws:
                starts.append(doy(w["start"]))
                ends.append(doy(w.get("end") or w["start"]))
    d0 = min(starts)
    d0 -= d0 % 7 if False else 0
    d1 = max(ends) + 1
    days = max(14, d1 - d0)
    route_idx = {r["key"]: i for i, r in enumerate(ROUTES)}
    for p in paras:
        person = by_name.get(p["person"])
        p["avatar"] = person["avatar"] if person else None
        p["portrait"] = person["portrait"] if person else None
        p["color"] = fac[person["faction"]]["color"] if person else "var(--gold)"
        p["route_keys"] = list(p["routes"].keys())
        bars = []
        for rk, ws in p["routes"].items():
            r = ROUTES[route_idx[rk]]
            for w in ws:
                s, e = doy(w["start"]), doy(w.get("end") or w["start"])
                bars.append({"row": route_idx[rk], "color": r["color"], "left": round((s - d0) / days * 100, 3),
                             "width": round((e - s + 1) / days * 100, 3),
                             "title": f"{r['name']} 第{w['chapter']}章 {w['start']}–{w.get('end') or w['start']}"})
        p["bars"] = bars
        p["search"] = " ".join([p["person"], p["title"], p["place"], p["reward"], p["people"], p["steps"], p["consequence"]])
    ticks = [{"pct": round((t - d0) / days * 100, 3), "label": md_label(t)} for t in range(d0, d0 + days + 1, 7)]
    cal = {"first": md_label(d0), "last": md_label(d1 - 1), "days": days, "ticks": ticks}

    # 血印
    for s in seals:
        s["color"] = "var(--gold)"
        s["holder_chars"] = [{"name": h, "id": by_name[h]["id"], "avatar": by_name[h]["avatar"]} if h in by_name else {"name": h, "id": None, "avatar": None}
                             for h in s["holders"]]
    # 神
    for g in gods:
        g["color"], g["glyph"] = GOD_STYLE[g["id"]]

    char_by_id = {c["id"]: c for c in chars}
    routes = []
    for r in ROUTES:
        routes.append({**r, "faction_name": fac[r["faction"]]["name"],
                       "recruitable": sum(1 for c in chars if r["key"] in c["routes_ok"] and c["id"] != r["cid"])})

    return {
        "chars": chars, "char_by_id": char_by_id, "factions_present": factions_present, "faction_by_key": fac,
        "classes": classes, "tiers_present": tiers_present, "families": families, "kinds": kinds,
        "paras": paras, "cal": cal, "seals": seals, "gods": gods, "routes": routes,
        "sources": {
            "characters": chars and load("characters")["_source"],
            "classes": classes_doc["_source"], "paralogues": paras_doc["_source"],
            "seals": seals_doc["_source"], "blessings": gods_doc["_source"],
        },
    }


def sheet_tabs() -> list[dict]:
    meta = SRC / "sheet" / "tabs.json"
    if meta.exists():
        return json.loads(meta.read_text(encoding="utf-8"))
    return []


def prepare_sheet_tab(tab: dict) -> dict:
    """把一個共創表分頁（欄位＋列）整理成通用頁面需要的結構。

    tabs.json 可設定：primary（標題欄）、group（分組欄）、filters（篩選欄）、
    badges（標籤欄）、hide（不在卡片上顯示的欄）、colors（某欄的值 → 顏色）。
    """
    doc = json.loads((SRC / "sheet" / tab["file"]).read_text(encoding="utf-8"))
    cols = doc["columns"]
    rows = [[("" if v is None else str(v)).strip() for v in r] + [""] * (len(cols) - len(r)) for r in doc["rows"]]
    rows = [r for r in rows if any(r)]
    ix = {c: i for i, c in enumerate(cols)}
    group = ix.get(tab.get("group")) if tab.get("group") else None
    if tab.get("primary") in ix:
        primary = ix[tab["primary"]]
    else:  # 沒指定標題欄時，取第一個大多不重複的欄（通常是名稱）
        def ratio(i: int) -> float:
            vals = [r[i] for r in rows if r[i]]
            return len(set(vals)) / len(vals) if vals else 0
        cands = [i for i in range(len(cols)) if i != group]
        primary = next((i for i in cands if ratio(i) >= 0.6), max(cands, key=ratio, default=0))
    filters = [c for c in tab.get("filters", []) if c in ix]
    badges = [ix[c] for c in tab.get("badges", []) if c in ix]
    hide = {ix[c] for c in tab.get("hide", []) if c in ix} | {primary} | set(badges) | ({group} if group is not None else set())
    color_col = ix.get(tab.get("colorBy")) if tab.get("colorBy") else None
    palette = ["var(--azure)", "var(--violet)", "var(--amber)", "var(--crimson)", "var(--jade)", "var(--ember)", "var(--moon)", "var(--pearl)"]
    options = {c: sorted({r[ix[c]] for r in rows if r[ix[c]]}, key=lambda v: [r[ix[c]] for r in rows].index(v)) for c in filters}
    color_vals = sorted({r[color_col] for r in rows if r[color_col]}, key=lambda v: [r[color_col] for r in rows].index(v)) if color_col is not None else []
    out_rows = []
    for n, r in enumerate(rows, 1):
        facets = {f"f{i}": str(options[c].index(r[ix[c]])) if r[ix[c]] else "" for i, c in enumerate(filters)}
        out_rows.append({
            "n": n, "title": r[primary], "cells": r, "facets": facets,
            "badges": [r[i] for i in badges if r[i]],
            "fields": [(cols[i], v) for i, v in enumerate(r) if v and i not in hide],
            "color": palette[color_vals.index(r[color_col]) % len(palette)] if color_col is not None and r[color_col] else None,
            "search": " ".join(r),
        })
    groups = []
    if group is not None:
        for name in dict.fromkeys(r["cells"][group] for r in out_rows):
            groups.append({"name": name, "rows": [r for r in out_rows if r["cells"][group] == name]})
    else:
        groups = [{"name": "", "rows": out_rows}]
    filter_groups = []
    for i, c in enumerate(filters):
        opts = [{"value": str(k), "label": v, "color": None} for k, v in enumerate(options[c])]
        if 1 < len(opts) <= 24:
            filter_groups.append({"key": f"f{i}", "label": c, "options": opts})
    return {**tab, "columns": cols, "rows": out_rows, "groups": groups, "filter_groups": filter_groups,
            "color": tab.get("color", "var(--gold)"), "intro": tab.get("intro", ""),
            "sources": [{"label": f"共创表 · {tab['name']}", "url": tab.get("url") or SITE["sheet_url"]}]}


# ── 搜尋索引 ───────────────────────────────────────────────

def search_index(d: dict) -> list[dict]:
    out = []
    for c in d["chars"]:
        out.append({"t": c["name"], "s": f"{d['faction_by_key'][c['faction']]['name']} · {c['jp']}", "u": f"characters.html#c-{c['id']}",
                    "i": f"assets/{c['avatar']}", "c": "角色", "k": c["search"], "f": c["is_lead"]})
    for k in d["classes"]:
        out.append({"t": k["name"], "s": f"{k['tier']} · {k['family']} · 移动 {k['movement']}", "u": f"classes.html#k-{k['id']}",
                    "i": f"assets/{k['icon']}" if k["icon"] else "", "c": "兵种", "k": k["search"]})
    for p in d["paras"]:
        out.append({"t": p["title"], "s": f"{p['person']}的外传 · {p['place']}", "u": f"paralogues.html#p-{p['id']}",
                    "i": f"assets/{p['avatar']}" if p["avatar"] else "", "c": "外传", "k": p["search"]})
    for s in d["seals"]:
        out.append({"t": s["name"], "s": f"{s['chance']}% · {s['effect']}", "u": f"seals.html#s-{s['id']}",
                    "i": f"assets/{s['icon']}", "c": "血印", "k": " ".join([s["effect"], *s["holders"]])})
    for g in d["gods"]:
        out.append({"t": g["name"], "s": " / ".join(g["levels"])[:60], "u": f"blessings.html#g-{g['id']}",
                    "i": "", "c": "神之加护", "k": " ".join(g["levels"]) + " " + g["jp"]})
    return out


# ── 輸出 ─────────────────────────────────────────────────

def file_hash(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()[:10]


def main() -> None:
    SITE["updated"] = dt.date.today().isoformat()
    data = prepare()
    tabs = sheet_tabs()
    glossary = json.loads((SRC / "glossary.json").read_text(encoding="utf-8"))["terms"]
    for g in glossary:
        g["status_label"] = STATUS_LABEL.get(g.get("status"), g.get("status", ""))

    if OUT.exists():
        for child in OUT.iterdir():
            if child.name in ("CNAME",):
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "static").mkdir(exist_ok=True)

    # 靜態檔
    for name in ("site.css", "site.js"):
        shutil.copy(WEB / "static" / name, OUT / "static" / name)
    shutil.copy(WEB / "static" / "favicon.svg", OUT / "favicon.svg")
    shutil.copytree(ASSETS, OUT / "assets")
    (OUT / ".nojekyll").write_text("")

    env = Environment(loader=FileSystemLoader(WEB / "templates"), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    fac_opts = [{"value": f["key"], "label": f["short"], "color": f["color"]} for f in data["factions_present"]]
    route_opts = [{"value": r["key"], "label": r["name"], "color": r["color"]} for r in data["routes"]]
    tier_opts = [{"value": t["key"], "label": t["name"], "color": None} for t in data["tiers_present"]]
    fam_opts = [{"value": f, "label": f, "color": FAMILY_COLORS.get(f)} for f in data["families"]]
    kind_opts = [{"value": k, "label": k, "color": None} for k in data["kinds"]]
    counts = {"characters": len(data["chars"]), "classes": len(data["classes"]), "paralogues": len(data["paras"]),
              "seals": len(data["seals"]), "blessings": len(data["gods"])}
    tiles = [
        {"file": "characters.html", "icon": "characters", "label": "角色名鉴", "en": "CHARACTERS", "color": "var(--violet)", "count": counts["characters"],
         "desc": "阵营、四路线挖角条件、喜好与推荐礼物，一张卡片看完。", "go": "翻阅名鉴"},
        {"file": "classes.html", "icon": "classes", "label": "兵种职业", "en": "CLASSES", "color": "var(--azure)", "count": counts["classes"],
         "desc": "六个阶级的兵种阶梯：考试条件、训练加成、特技与精通。", "go": "查看阶梯"},
        {"file": "paralogues.html", "icon": "paralogues", "label": "外传", "en": "PARALOGUES", "color": "var(--amber)", "count": counts["paralogues"],
         "desc": "接取窗口日历与各路线开放章节，避免错过关键外传。", "go": "打开日历"},
        {"file": "seals.html", "icon": "seals", "label": "血印", "en": "BLOOD SEALS", "color": "var(--crimson)", "count": counts["seals"],
         "desc": "十枚天冠血印的发动机率、效果与持有者。", "go": "查看血印"},
        {"file": "blessings.html", "icon": "blessings", "label": "神之加护", "en": "BLESSINGS", "color": "var(--jade)", "count": counts["blessings"],
         "desc": "七神三阶加护与白沙消耗，普通、困难分列。", "go": "参拜神殿"},
        {"file": "about.html", "icon": "about", "label": "来源与译名", "en": "SOURCES", "color": "var(--gold)", "count": "",
         "desc": "共创表分页收录情况、繁体译名依据与美术来源。", "go": "阅读说明"},
    ]
    home_stats = [(counts["characters"], "位角色"), (counts["classes"], "种兵种"), (counts["paralogues"], "篇外传"),
                  (counts["seals"], "枚血印"), (counts["blessings"], "位神祇")]
    tab_rows = tabs or default_tabs()

    pages = [
        ("index.html", "index", "", "社群《火焰纹章 万缕千丝》共创资料表的图鉴版：角色、兵种、外传、血印与神之加护。", {"tiles": tiles, "home_stats": home_stats}),
        ("characters.html", "characters", "角色名鉴", "万缕千丝全角色：阵营、四路线挖角条件（支援、名声、交涉）、喜好与推荐礼物。",
         {"faction_options": fac_opts, "route_options": route_opts, "sources": data["sources"]["characters"]}),
        ("classes.html", "classes", "兵种职业", "万缕千丝兵种阶梯：移动、考试条件、训练加成、兵种特技与精通技能。",
         {"tier_options": tier_opts, "family_options": fam_opts, "kind_options": kind_opts, "sources": data["sources"]["classes"]}),
        ("paralogues.html", "paralogues", "外传", "万缕千丝外传接取窗口日历：各路线开放章节、日期、地点与报酬。",
         {"route_options": route_opts, "sources": data["sources"]["paralogues"]}),
        ("seals.html", "seals", "血印", "万缕千丝血印（天冠）一览：发动机率、效果与持有角色。", {"sources": data["sources"]["seals"]}),
        ("blessings.html", "blessings", "神之加护", "万缕千丝七神加护：各等级效果与天刻的白沙消耗。", {"sources": data["sources"]["blessings"]}),
        ("about.html", "about", "来源与译名", "本站资料来源、共创表分页收录情况与繁体译名依据。", {"glossary": glossary, "sheet_tabs": tab_rows}),
    ]

    generic = [prepare_sheet_tab(t) for t in tabs if t.get("file")]
    for t in generic:
        pages.append((f"{t['slug']}.html", "sheet", t["title"], t.get("intro") or f"万缕千丝共创表「{t['name']}」分页。",
                      {"tab": t, "template": "sheet.html"}))
        tiles.insert(-1, {"file": f"{t['slug']}.html", "icon": t.get("icon", "about"), "label": t["title"], "en": t.get("en", "FROM THE SHEET"),
                          "color": t.get("color", "var(--gold)"), "count": len(t["rows"]), "desc": t.get("intro", "")[:40], "go": "打开"})
    data["generic_tabs"] = generic
    if generic:
        pages.append(("library.html", "library", "共创表分页", "万缕千丝共创表的全部分页目录。",
                      {"tiles": [t for t in tiles if t["file"] not in ("about.html",)]}))
        NAV.insert(-1, {"file": "library.html", "label": "更多资料"})

    versions = {"css": file_hash(OUT / "static" / "site.css"), "js": file_hash(OUT / "static" / "site.js"), "fonts": "0"}
    rendered: dict[str, dict[str, str]] = {}
    for lang, cfg in LANGS.items():
        rendered[lang] = {}
        for file, key, title, desc, extra in pages:
            alt = "hans/" + file if lang == "hant" else "../" + file
            ctx = {**data, **extra, "site": SITE, "nav": NAV, "lang": lang, "root": cfg["root"], "prefix": "",
                   "html_lang": cfg["html_lang"], "font_key": cfg["font"], "page": file, "page_key": key,
                   "page_title": title, "description": desc, "alt_href": alt, "v": versions}
            html = env.get_template(extra.get("template", file)).render(**ctx)
            if lang == "hant":
                html = add_alt_text(html)
                html = html_to_hant(html)
            html = html.replace("<!--noconv-->", "").replace("<!--/noconv-->", "")
            rendered[lang][file] = html

    # 字型：依實際用字裁切
    font_versions = fonts.build(rendered, OUT / "static")
    for lang, cfg in LANGS.items():
        out_dir = OUT / cfg["prefix"]
        out_dir.mkdir(parents=True, exist_ok=True)
        for file, html in rendered[lang].items():
            html = html.replace("fonts-%s.css?v=0" % cfg["font"], "fonts-%s.css?v=%s" % (cfg["font"], font_versions[cfg["font"]]))
            (out_dir / file).write_text(html, encoding="utf-8")
        idx = search_index(data)
        if lang == "hant":
            for e in idx:
                for k in ("t", "s", "c"):
                    e[k] = text_to_hant(e[k])
                e["k"] = text_to_hant(e["k"]) + " " + e["k"]
        (out_dir / "search.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    write_404(env, data, versions, font_versions)
    write_sitemap([p[0] for p in pages])
    print("built", sum(len(v) for v in rendered.values()), "pages →", OUT.relative_to(ROOT))


def add_alt_text(html: str) -> str:
    """繁體頁的 data-text 會被轉成繁體；另存一份簡體在 data-alt（受保護），讓兩種寫法都搜得到。"""
    return re.sub(r'data-text="([^"]*)"', lambda m: f'data-text="{m.group(1)}" data-alt="{m.group(1)}"', html)


def default_tabs() -> list[dict]:
    return [
        {"name": "02-兵种职业信息", "page": "classes.html", "page_label": "兵种职业", "status": "已收录（经姊妹站转录）"},
        {"name": "03-全外传信息", "page": "paralogues.html", "page_label": "外传", "status": "已收录（经姊妹站转录）"},
        {"name": "血印", "page": "seals.html", "page_label": "血印", "status": "已收录（经姊妹站转录）"},
        {"name": "神之加护", "page": "blessings.html", "page_label": "神之加护", "status": "已收录（姊妹站手册）"},
        {"name": "挖角名声 · 送礼", "page": "characters.html", "page_label": "角色名鉴", "status": "以姊妹站招募表、送礼表呈现"},
        {"name": "特技 · 战技 · 武器 · 道具", "page": None, "page_label": "", "status": "待接入共创表"},
        {"name": "军团兵 · 骑乘", "page": None, "page_label": "", "status": "待接入共创表"},
        {"name": "钓鱼 · 栽种 · 茶会 · 支援", "page": None, "page_label": "", "status": "待接入共创表"},
    ]


def write_404(env, data, versions, font_versions) -> None:
    html = """<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>找不到頁面 · 萬縷千絲</title><link rel="stylesheet" href="/FEFW-Guide/static/site.css"><style>body{display:grid;place-items:center;min-height:100vh;text-align:center;padding:24px}</style></head>
<body><main><p class="kicker latin">LOST THREAD</p><h1 class="gold-text" style="font-size:44px">這條絲線斷了</h1><p style="color:var(--muted)">找不到這個頁面。</p>
<p><a class="btn primary" href="/FEFW-Guide/">回到首頁</a></p></main></body></html>"""
    (OUT / "404.html").write_text(html, encoding="utf-8")


def write_sitemap(files: list[str]) -> None:
    urls = []
    for f in files:
        for prefix in ("", "hans/"):
            loc = f"{SITE['base_url']}/{prefix}{'' if f == 'index.html' else f}"
            urls.append(f"<url><loc>{loc}</loc></url>")
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                                     + "".join(urls) + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE['base_url']}/sitemap.xml\n", encoding="utf-8")


if __name__ == "__main__":
    main()
