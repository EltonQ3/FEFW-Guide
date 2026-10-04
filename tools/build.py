"""建置萬縷千絲資料織錦站（v2）。

source/*.json（簡體）→ docs/（繁體，網站根目錄）與 docs/hans/（簡體）。
資料來源與合併方式見 tools/import_seed.py、tools/import_game8.py。
用法：python3 tools/build.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textconv import html_to_hant, text_to_hant  # noqa: E402
import fonts  # noqa: E402
import opencc  # noqa: E402

_t2s = opencc.OpenCC("t2s")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source"
WEB = ROOT / "web"
OUT = ROOT / "docs"
ASSETS = ROOT / "assets"

SITE = {
    "base_url": "https://eltonq3.github.io/FEFW-Guide",
    "base_path": "/FEFW-Guide/",
    "sheet_url": "https://docs.qq.com/sheet/DV0N0VUZLSXRmUWFq?tab=BB08J2",
    "updated": "",
}

LANGS = {
    "hant": {"prefix": "", "html_lang": "zh-Hant", "font": "tc"},
    "hans": {"prefix": "hans/", "html_lang": "zh-Hans", "font": "sc"},
}

ROUTES = [
    {"key": "kai", "name": "凯伊篇", "short": "凯伊", "en": "CAI", "cid": "cai", "color": "var(--r-kai)", "faction": "ribeira"},
    {"key": "dietrich", "name": "迪托利希篇", "short": "迪托利希", "en": "DIETRICH", "cid": "dietrich", "color": "var(--r-dietrich)", "faction": "lamine"},
    {"key": "theodora", "name": "赛奥朵拉篇", "short": "赛奥朵拉", "en": "THEODORA", "cid": "theodora", "color": "var(--r-theodora)", "faction": "megaira"},
    {"key": "leda", "name": "蕾达篇", "short": "蕾达", "en": "LEDA", "cid": "leda", "color": "var(--r-leda)", "faction": "rose"},
]

FACTIONS = [
    ("savior", "救世军", "真主角与未来的伙伴", "var(--pearl)"),
    ("ribeira", "利贝拉之风", "凯伊篇", "var(--azure)"),
    ("lamine", "拉弥努家族", "迪托利希篇", "var(--violet)"),
    ("megaira", "美盖拉的灯火", "赛奥朵拉篇", "var(--amber)"),
    ("rose", "蔷薇风暴", "蕾达篇", "var(--crimson)"),
    ("mane", "炎之鬃", "贝特朗队", "var(--ember)"),
    ("moon", "月之谎", "", "var(--moon)"),
    ("linaria", "利纳利亚朝露", "", "var(--jade)"),
    ("crow", "白鸦新娘团", "", "var(--rose-pale)"),
    ("temple", "奥罗拉神殿", "", "var(--gold)"),
    ("arago", "阿拉戈精锐部队", "", "var(--steel)"),
    ("braganca", "布拉甘萨同胞团", "", "var(--rust)"),
    ("harhali", "哈尔哈利", "", "var(--olive)"),
    ("brigid", "布里吉德军", "", "var(--teal)"),
    ("bandits", "盗贼", "", "var(--stone)"),
    ("free", "无所属", "", "var(--stone)"),
]
FAC = {k: {"key": k, "name": n, "note": note, "color": c} for k, n, note, c in FACTIONS}

STATS = [("HP", "HP"), ("Str", "力量"), ("Mag", "魔力"), ("Spd", "速度"), ("Dex", "技巧"),
         ("Def", "守备"), ("Res", "魔防"), ("Lck", "幸运"), ("Cha", "魅力")]
TIERS = [
    ("基础", "base", "I", "初始兵种，不加成长率"),
    ("初级", "beginner", "II", "建议 Lv5 · 名声 Lv1 · 初级考试票证"),
    ("中级", "specialty", "III", "建议 Lv20 · 名声 Lv4 · 中级考试票证"),
    ("上级与高级", "advanced", "IV", "建议 Lv35 · 名声 Lv8"),
    ("最上级", "master", "V", "建议 Lv45 · 第三部第二区段起"),
    ("神将", "divine", "VI", "天冠神殿的神将许可 · 每种限一人"),
]
FAMILY_COLORS = {"斗士系": "var(--crimson)", "猎兵系": "var(--jade)", "士兵系": "var(--amber)", "魔道系": "var(--violet)", "飞行系": "var(--azure)"}
WEAPON_KINDS = [("sword", "剑"), ("spear", "枪"), ("axe", "斧"), ("bow", "弓"), ("gauntlet", "护手"), ("black", "黑魔法"), ("white", "白魔法")]
GOD_STYLE = {"aurora": ("var(--amber)", "曙"), "mars": ("var(--crimson)", "战"), "smyrnos": ("var(--violet)", "智"),
             "jurah": ("var(--jade)", "护"), "kalla": ("var(--azure)", "风"), "credna": ("var(--moon)", "视"), "fortuna": ("var(--gold)", "命")}
STATUS = {"official": "官方", "sheet": "共创表", "community": "社群", "provisional": "暂译", "ingame-tc": "游戏内繁中", "untranslated": "原文"}

NAV = [
    ("index.html", "首页"), ("units.html", "角色"), ("recruit.html", "招募"), ("classes.html", "兵种"),
    ("bonds.html", "羁绊"), ("paralogues.html", "外传"), ("codex.html", "图鉴"), ("about.html", "关于"),
]


def load(name: str) -> dict:
    return json.loads((SRC / f"{name}.json").read_text(encoding="utf-8"))


def doy(md: str | None) -> int | None:
    if not md:
        return None
    m, d = (int(x) for x in md.split("/"))
    return (dt.date(2025, m, d) - dt.date(2025, 1, 1)).days


def md_label(n: int) -> str:
    d = dt.date(2025, 1, 1) + dt.timedelta(days=n)
    return f"{d.month}/{d.day}"


def radar(growth: dict, color: str, size: int = 240, peak: int = 80) -> Markup:
    """九角成長率雷達圖（SVG）。"""
    c = size / 2
    r = size / 2 - 34
    n = len(STATS)
    pt = lambda i, v: (c + r * v / peak * math.sin(2 * math.pi * i / n), c - r * v / peak * math.cos(2 * math.pi * i / n))  # noqa: E731
    rings = "".join(
        f'<polygon points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, lv) for i in range(n)))}" class="ring{" outer" if lv == peak else ""}"/>'
        for lv in (20, 40, 60, 80))
    spokes = "".join(f'<line x1="{c}" y1="{c}" x2="{pt(i, peak)[0]:.1f}" y2="{pt(i, peak)[1]:.1f}"/>' for i in range(n))
    shape = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, min(growth[k], peak)) for i, (k, _) in enumerate(STATS)))
    dots = "".join(f'<circle cx="{pt(i, min(growth[k], peak))[0]:.1f}" cy="{pt(i, min(growth[k], peak))[1]:.1f}" r="3"/>' for i, (k, _) in enumerate(STATS))
    labels = ""
    for i, (k, zh) in enumerate(STATS):
        x, y = pt(i, peak + 17)
        labels += f'<text x="{x:.1f}" y="{y:.1f}">{zh}</text>'
    return Markup(f'<svg class="radar" viewBox="0 0 {size} {size}" role="img" aria-label="成长率雷达图" style="--c: {color}">'
                  f'<g class="grid">{rings}{spokes}</g><polygon class="shape" points="{shape}"/><g class="dots">{dots}</g>'
                  f'<g class="labels">{labels}</g></svg>')


def prepare() -> dict:
    units = load("units")["items"]
    classes_doc, paras_doc, seals_doc, gods_doc = load("classes"), load("paralogues"), load("seals"), load("blessings")
    weapons_doc, gifts_doc, units_doc = load("weapons"), load("gifts"), load("units")
    classes, paras, seals, gods = classes_doc["items"], paras_doc["items"], seals_doc["items"], gods_doc["items"]
    weapons, gifts = weapons_doc["items"], gifts_doc["items"]
    by_id = {u["id"]: u for u in units}
    by_name = {}
    for u in units:
        by_name[u["name"]] = u
        for a in u.get("aliases", []):
            by_name.setdefault(a, u)

    # ── 角色 ─────────────────────────────────────────────
    stat_max = {k: max((u["growth"] or {}).get(k, 0) for u in units) for k, _ in STATS}
    totals = sorted((u["growth_total"] for u in units if u["growth_total"]), reverse=True)
    order = [f[0] for f in FACTIONS]
    units.sort(key=lambda u: (order.index(u["faction"]), not u["lead"], u["name"]))
    for u in units:
        for g in u["gifts"]:
            g["id"] = re.sub(r"[^a-z0-9]+", "-", g["en"].lower()).strip("-")
        f = FAC[u["faction"]]
        u["fac"] = f
        u["color"] = f["color"]
        u["url"] = f"unit/{u['id']}.html"
        rec = u.get("recruit") or {}
        u["routes_ok"] = [r["key"] for r in ROUTES if rec.get(r["key"], {}).get("kind", "none") != "none"]
        u["parts"] = "1" if u["routes_ok"] else "3"
        u["aliases_hant"] = [a for a in u.get("aliases", []) if text_to_hant(a) != text_to_hant(u["name"])]
        u["aliases_hans"] = [a for a in u.get("aliases", []) if _t2s.convert(a) != u["name"]]
        u["seal_list"] = [s for s in seals if u["name"] in s["holders"]]
        u["para_list"] = [p for p in paras if p["person"] == u["name"]]
        u["para_unlocks"] = [p for p in paras if u["name"] in (p.get("people") or "") and p["person"] != u["name"]]
        u["support_list"] = [{"unit": by_id[i], "rank": rk} for i, rk in u.get("supports", []) if i in by_id]
        u["support_groups"] = [(rk, [s["unit"] for s in u["support_list"] if s["rank"] == rk]) for rk in "ABC"]
        if u["growth"]:
            u["growth_rows"] = [{"key": k, "label": zh, "value": u["growth"][k], "best": u["growth"][k] == stat_max[k]} for k, zh in STATS]
            u["radar"] = radar(u["growth"], f["color"])
            u["total_rank"] = totals.index(u["growth_total"]) + 1
        spells = defaultdict(lambda: {"black": [], "white": []})
        for s in u.get("spells", []):
            spells[s["level"]][s["magic"]].append(s)
        u["spell_rows"] = [(lv, spells[lv]) for lv in "DCBAS" if lv in spells]
        needs = " ".join(" ".join(v.get("needs", [])) + " " + v.get("text", "") for v in rec.values())
        u["search"] = " ".join(filter(None, [u["name"], *u.get("aliases", []), u["jp"], u["en"], u["likes"], u["hobbies"], u["gift_note"],
                                             f["name"], needs, (u.get("ability") or {}).get("name", ""), " ".join(g["name"] for g in u["gifts"])]))
    factions_present = [{**FAC[k], "members": [u for u in units if u["faction"] == k]} for k in order]
    factions_present = [f for f in factions_present if f["members"]]
    for f in factions_present:
        ms = f["members"]
        for i, u in enumerate(ms):
            u["prev"] = ms[i - 1] if len(ms) > 1 else None
            u["next"] = ms[(i + 1) % len(ms)] if len(ms) > 1 else None

    # 成長之最
    highlights = []
    for k, zh in STATS:
        best = max((u for u in units if u["growth"]), key=lambda u: u["growth"][k])
        highlights.append({"label": zh, "unit": best, "value": best["growth"][k]})

    # ── 招募（按路線） ─────────────────────────────────────
    recruit = []
    for r in ROUTES:
        rows = []
        for u in units:
            rc = (u.get("recruit") or {}).get(r["key"])
            if not rc or rc.get("kind") == "none":
                continue
            rows.append({"unit": u, "rc": rc, "renown": rc.get("renown") if rc.get("kind") == "scout" else 0,
                         "support": rc.get("support") if rc.get("kind") == "scout" else None})
        rows.sort(key=lambda x: (x["rc"]["kind"] != "lead", x["rc"]["kind"] != "auto", x["renown"] or 0, x["unit"]["name"]))
        recruit.append({**r, "rows": rows, "scout": sum(1 for x in rows if x["rc"]["kind"] == "scout"),
                        "auto": sum(1 for x in rows if x["rc"]["kind"] in ("auto", "lead"))})
    later = [u for u in units if not u["routes_ok"] and u["join"]]

    # ── 兵種 ─────────────────────────────────────────────
    tier_info = {t[0]: t for t in TIERS}
    for k in classes:
        head, _, rest = (k.get("features") or "").partition("，")
        parts = [p.strip() for p in head.split("·") if p.strip()]
        unit_kinds = ("步兵", "骑兵", "重装", "飞行")
        if not parts:
            fam, kinds = "通用", []
        elif parts[0] in unit_kinds:
            fam, kinds = "通用", parts
        else:
            fam, kinds = parts[0], parts[1:]
        if k.get("added_from") == "game8":
            fam = "未分系"  # 共創表沒有、只見於 Game8 的兵種，系統分類待核對
        k["family"], k["kind"], k["kind_label"] = fam, " ".join(kinds), " · ".join(kinds)
        k["skills"] = re.findall(r"【([^】]+)】", rest)
        m = re.match(r"【([^】]+)】\s*[（(](\d+)[)）]", k.get("mastery", ""))
        k["mastery_name"], k["mastery_exp"] = (m.group(1), m.group(2)) if m else (k.get("mastery", "").strip("【】"), "")
        k["tier_key"] = tier_info[k["tier"]][1]
        k["color"] = FAMILY_COLORS.get(fam, "var(--stone)")
        if k.get("growth"):
            k["growth_rows"] = [{"label": zh, "value": k["growth"][s], "bonus": (k.get("bonus") or {}).get(s, 0)} for s, zh in STATS]
            k["growth_sum"] = sum(k["growth"].values())
        k["search"] = " ".join(filter(None, [k["name"], k.get("en", ""), k["tier"], fam, k["kind"], k.get("exam", ""), k.get("unlock", ""),
                                             k.get("training", ""), " ".join(k["skills"]), k["mastery_name"], " ".join(k.get("weapons", []))]))
    tiers_present = []
    for name, key, numeral, note in TIERS:
        members = [k for k in classes if k["tier"] == name]
        if members:
            tiers_present.append({"name": name, "key": key, "numeral": numeral, "note": note, "members": members})
    families = [f for f in FAMILY_COLORS if any(k["family"] == f for k in classes)] + [f for f in ("通用", "未分系") if any(k["family"] == f for k in classes)]
    kinds = [x for x in ("步兵", "骑兵", "重装", "飞行") if any(x in k["kind"].split() for k in classes)]
    calc = {
        "units": [{"id": u["id"], "n": u["name"], "a": u["avatar"], "g": [u["growth"][s] for s, _ in STATS], "c": u["color"]}
                  for u in units if u["growth"]],
        "classes": [{"id": k["id"], "n": k["name"], "t": k["tier"], "g": [k["growth"][s] for s, _ in STATS]} for k in classes if k.get("growth")],
        "stats": [zh for _, zh in STATS],
    }

    # ── 外傳 ─────────────────────────────────────────────
    starts, ends = [], []
    for p in paras:
        for ws in p["routes"].values():
            for w in ws:
                starts.append(doy(w["start"]))
                ends.append(doy(w.get("end") or w["start"]))
    d0, d1 = min(starts), max(ends) + 1
    days = max(14, d1 - d0)
    route_idx = {r["key"]: i for i, r in enumerate(ROUTES)}
    for p in paras:
        person = by_name.get(p["person"])
        p["unit"] = person
        p["color"] = person["color"] if person else "var(--gold)"
        p["route_keys"] = list(p["routes"].keys())
        bars = []
        for rk, ws in p["routes"].items():
            r = ROUTES[route_idx[rk]]
            for w in ws:
                s, e = doy(w["start"]), doy(w.get("end") or w["start"])
                bars.append({"row": route_idx[rk], "color": r["color"], "left": round((s - d0) / days * 100, 3),
                             "width": round((e - s + 1) / days * 100, 3), "title": f"{r['name']} 第{w['chapter']}章 {w['start']}–{w.get('end') or w['start']}"})
        p["bars"] = bars
        diffs = []
        for rk, ws in (p.get("game8") or {}).items():
            mine = [(w["start"], w.get("end") or w["start"]) for w in p["routes"].get(rk, [])]
            theirs = [(w["start"], w["end"]) for w in ws]
            if mine != theirs:
                diffs.append({"route": ROUTES[route_idx[rk]], "spans": " / ".join(f"{a}–{b}" if a != b else a for a, b in theirs)})
        p["diffs"] = diffs
        p["search"] = " ".join(filter(None, [p["person"], p["title"], p.get("place", ""), p.get("reward", ""), p.get("people", ""),
                                             p.get("steps", ""), p.get("consequence", "")]))
    ticks = [{"pct": round((t - d0) / days * 100, 3), "label": md_label(t)} for t in range(d0, d0 + days + 1, 7)]
    cal = {"first": md_label(d0), "last": md_label(d1 - 1), "days": days, "ticks": ticks}

    # ── 血印、神、武器、禮物 ──────────────────────────────────
    for s in seals:
        s["holder_units"] = [by_name.get(h) or {"name": h} for h in s["holders"]]
    for g in gods:
        g["color"], g["glyph"] = GOD_STYLE[g["id"]]
    for w in weapons:
        w["kind_label"] = dict(WEAPON_KINDS)[w["kind"]]
        w["search"] = " ".join(filter(None, [w["name"], w["en"], w["kind_label"], w.get("rank", ""), w.get("desc", "")]))
    gift_groups = defaultdict(list)
    for g in gifts:
        g["likers"] = [by_id[i] for i in g.get("liked_by", []) if i in by_id]
        gift_groups[g.get("for") or "其他"].append(g)
        g["search"] = " ".join(filter(None, [g["name"], g["en"], g.get("for", ""), g.get("desc", ""), " ".join(u["name"] for u in g["likers"])]))
    gift_cats = sorted(gift_groups, key=lambda c: (c == "其他", -len(gift_groups[c])))
    blaze = [{"unit": u, "arts": u["blaze"]} for u in units if u.get("blaze")]

    support_data = {
        "units": [{"id": u["id"], "n": u["name"], "a": u["avatar"], "c": u["color"], "f": u["fac"]["name"], "s": u.get("supports", [])} for u in units],
    }
    support_rank = sorted(units, key=lambda u: (-len(u.get("supports", [])), u["name"]))[:8]

    status_counts = Counter()
    for u in units:
        status_counts[u.get("name_status")] += 1
        for x in [u.get("ability")] + u["blaze"]:
            if x:
                status_counts[x.get("status")] += 1
    for x in classes:
        status_counts[x.get("name_status", "sheet")] += 1
    for x in weapons + gifts + seals:
        status_counts[x.get("status")] += 1

    coverage = [
        {"label": "角色资料", "value": len(units), "unit": "位", "note": "含 8 位共创表尚未收录的第二、三部角色"},
        {"label": "成长率", "value": sum(1 for u in units if u["growth"]), "unit": "位", "note": "九项个人成长率与总和"},
        {"label": "支援关系", "value": sum(len(u.get("supports", [])) for u in units) // 2, "unit": "组", "note": "可达到的 A／B／C 支援"},
        {"label": "兵种", "value": len(classes), "unit": "种", "note": f"{sum(1 for k in classes if k.get('growth'))} 种附成长率加成"},
        {"label": "武器与魔法", "value": len(weapons), "unit": "件", "note": "威力、命中、射程、重量与说明"},
        {"label": "礼物", "value": len(gifts), "unit": "件", "note": "用途与喜欢的角色"},
        {"label": "血印", "value": len(seals), "unit": "枚", "note": "发动率、效果与持有者"},
        {"label": "外传", "value": len(paras), "unit": "篇", "note": "各路线接取窗口"},
    ]

    return {
        "units": units, "by_id": by_id, "factions_present": factions_present, "highlights": highlights,
        "recruit": recruit, "later": later, "routes": ROUTES,
        "classes": classes, "tiers_present": tiers_present, "families": families, "kinds": kinds, "calc": calc,
        "paras": paras, "cal": cal, "seals": seals, "gods": gods, "weapons": weapons, "weapon_kinds": WEAPON_KINDS,
        "gifts": gifts, "gift_cats": gift_cats, "gift_groups": gift_groups, "blaze": blaze,
        "support_data": support_data, "support_rank": support_rank, "coverage": coverage, "status_counts": status_counts,
        "stats": STATS,
        "sources": {
            "units": units_doc["_source"], "classes": classes_doc["_source"], "paralogues": paras_doc["_source"],
            "seals": seals_doc["_source"], "blessings": gods_doc["_source"], "weapons": weapons_doc["_source"], "gifts": gifts_doc["_source"],
        },
    }


# ── 共創表通用分頁 ──────────────────────────────────────────

def sheet_tabs() -> list[dict]:
    meta = SRC / "sheet" / "tabs.json"
    return json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else []


def prepare_sheet_tab(tab: dict) -> dict:
    """把一個共創表分頁（欄位＋列）整理成通用頁面需要的結構。

    tabs.json 可設定：primary（標題欄）、group（分組欄）、filters（篩選欄）、
    badges（標籤欄）、hide（不在卡片上顯示的欄）、colorBy（依哪一欄上色）。
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
    options = {c: list(dict.fromkeys(r[ix[c]] for r in rows if r[ix[c]])) for c in filters}
    color_vals = list(dict.fromkeys(r[color_col] for r in rows if r[color_col])) if color_col is not None else []
    out_rows = []
    for n, r in enumerate(rows, 1):
        out_rows.append({
            "n": n, "title": r[primary], "cells": r,
            "facets": {f"f{i}": str(options[c].index(r[ix[c]])) if r[ix[c]] else "" for i, c in enumerate(filters)},
            "badges": [r[i] for i in badges if r[i]],
            "fields": [(cols[i], v) for i, v in enumerate(r) if v and i not in hide],
            "color": palette[color_vals.index(r[color_col]) % len(palette)] if color_col is not None and r[color_col] else None,
            "search": " ".join(r),
        })
    if group is not None:
        groups = [{"name": g, "rows": [r for r in out_rows if r["cells"][group] == g]} for g in dict.fromkeys(r["cells"][group] for r in out_rows)]
    else:
        groups = [{"name": "", "rows": out_rows}]
    filter_groups = [{"key": f"f{i}", "label": c, "options": [{"value": str(k), "label": v, "color": None} for k, v in enumerate(options[c])]}
                     for i, c in enumerate(filters) if 1 < len(options[c]) <= 24]
    return {**tab, "columns": cols, "rows": out_rows, "groups": groups, "filter_groups": filter_groups,
            "color": tab.get("color", "var(--gold)"), "intro": tab.get("intro", ""),
            "sources": [{"label": f"共创表 · {tab['name']}", "url": tab.get("url") or SITE["sheet_url"]}]}


# ── 搜尋索引 ───────────────────────────────────────────────

def search_index(d: dict) -> list[dict]:
    out = []
    for u in d["units"]:
        out.append({"t": u["name"], "s": f"{u['fac']['name']} · {u['jp'] or u['en']}", "u": u["url"], "i": f"assets/{u['avatar']}" if u["avatar"] else "",
                    "c": "角色", "k": u["search"], "f": u["lead"]})
    for k in d["classes"]:
        out.append({"t": k["name"], "s": f"{k['tier']} · {k['family']} · 移动 {k.get('movement', '')}", "u": f"classes.html#k-{k['id']}",
                    "i": f"assets/{k['icon']}" if k.get("icon") else "", "c": "兵种", "k": k["search"]})
    for p in d["paras"]:
        out.append({"t": p["title"], "s": f"{p['person']}的外传", "u": f"paralogues.html#p-{p['id']}",
                    "i": f"assets/{p['unit']['avatar']}" if p["unit"] and p["unit"]["avatar"] else "", "c": "外传", "k": p["search"]})
    for s in d["seals"]:
        out.append({"t": s["name"], "s": f"{s['chance']}% · {s['effect']}", "u": f"seals.html#s-{s['id']}", "i": f"assets/{s['icon']}" if s.get("icon") else "",
                    "c": "血印", "k": " ".join([s["effect"], *s["holders"]])})
    for w in d["weapons"]:
        out.append({"t": w["name"], "s": f"{w['kind_label']} · 威力 {w['might'] or '—'}", "u": f"weapons.html#w-{w['id']}", "i": "", "c": "武器", "k": w["search"]})
    for g in d["gifts"]:
        out.append({"t": g["name"], "s": g.get("for") or "礼物", "u": f"gifts.html#g-{g['id']}", "i": "", "c": "礼物", "k": g["search"]})
    for b in d["blaze"]:
        for a in b["arts"]:
            out.append({"t": a["name"], "s": f"{b['unit']['name']}的爆炎技", "u": f"blaze.html#b-{b['unit']['id']}", "i": "", "c": "爆炎技", "k": a["en"] + " " + a["effect"]})
    for g in d["gods"]:
        out.append({"t": g["name"], "s": " / ".join(g["levels"])[:60], "u": f"blessings.html#g-{g['id']}", "i": "", "c": "神之加护", "k": " ".join(g["levels"]) + " " + g["jp"]})
    return out


# ── 輸出 ─────────────────────────────────────────────────

def file_hash(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()[:10]


def tojson_attr(obj) -> Markup:
    return Markup(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))


def main() -> None:
    SITE["updated"] = dt.date.today().isoformat()
    data = prepare()
    glossary = json.loads((SRC / "glossary.json").read_text(encoding="utf-8"))["terms"]
    core = json.loads((SRC / "i18n" / "core.json").read_text(encoding="utf-8"))
    for g in glossary:
        g["status_label"] = STATUS.get(g.get("status"), g.get("status", ""))

    if OUT.exists():
        for child in OUT.iterdir():
            if child.name in ("CNAME",):
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    (OUT / "static").mkdir(parents=True, exist_ok=True)
    for name in ("site.css", "site.js"):
        shutil.copy(WEB / "static" / name, OUT / "static" / name)
    shutil.copy(WEB / "static" / "favicon.svg", OUT / "favicon.svg")
    shutil.copytree(ASSETS, OUT / "assets")
    (OUT / ".nojekyll").write_text("")

    env = Environment(loader=FileSystemLoader(WEB / "templates"), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    env.filters["json"] = tojson_attr
    env.globals["STATUS"] = STATUS
    env.globals["FAC"] = FAC

    fac_opts = [{"value": f["key"], "label": f["name"], "color": f["color"]} for f in data["factions_present"]]
    route_opts = [{"value": r["key"], "label": r["name"], "color": r["color"]} for r in ROUTES]
    stat_opts = [{"value": k, "label": zh} for k, zh in STATS]
    tier_opts = [{"value": t["key"], "label": t["name"], "color": None} for t in data["tiers_present"]]
    fam_opts = [{"value": f, "label": f, "color": FAMILY_COLORS.get(f)} for f in data["families"]]
    kind_opts = [{"value": k, "label": k, "color": None} for k in data["kinds"]]
    wkind_opts = [{"value": k, "label": zh, "color": None} for k, zh in WEAPON_KINDS]
    gift_opts = [{"value": str(i), "label": c, "color": None} for i, c in enumerate(data["gift_cats"])]
    for g in data["gifts"]:
        g["cat_index"] = str(data["gift_cats"].index(g.get("for") or "其他"))
    u_count, c_count = len(data["units"]), len(data["classes"])

    sections = [
        {"file": "units.html", "icon": "characters", "label": "角色", "en": "UNITS", "color": "var(--violet)", "count": u_count,
         "desc": "每位角色一页：成长率雷达、个人技能、支援、礼物与四线加入条件。"},
        {"file": "recruit.html", "icon": "recruit", "label": "招募规划", "en": "RECRUITMENT", "color": "var(--crimson)", "count": sum(1 for u in data["units"] if u["routes_ok"]),
         "desc": "选一条路线，按名声门槛排出能挖角的同伴，可勾选已招募。"},
        {"file": "classes.html", "icon": "classes", "label": "兵种", "en": "CLASSES", "color": "var(--azure)", "count": c_count,
         "desc": "六阶兵种阶梯与成长率加成，附角色×兵种成长模拟。"},
        {"file": "bonds.html", "icon": "bonds", "label": "羁绊", "en": "SUPPORTS", "color": "var(--rose-pale)", "count": sum(len(u.get("supports", [])) for u in data["units"]) // 2,
         "desc": "查任一角色能与谁结下 A／B／C 支援。"},
        {"file": "paralogues.html", "icon": "paralogues", "label": "外传", "en": "PARALOGUES", "color": "var(--amber)", "count": len(data["paras"]),
         "desc": "接取窗口日历：四条路线、游戏内日期，一眼看出何时会错过。"},
        {"file": "codex.html", "icon": "codex", "label": "图鉴", "en": "CODEX", "color": "var(--jade)", "count": len(data["weapons"]) + len(data["gifts"]) + len(data["seals"]) + len(data["gods"]) + sum(len(b["arts"]) for b in data["blaze"]),
         "desc": "武器与魔法、礼物、血印、爆炎技、神之加护。"},
    ]
    codex_items = [
        {"file": "weapons.html", "icon": "classes", "label": "武器与魔法", "en": "ARMORY", "color": "var(--azure)", "count": len(data["weapons"]),
         "desc": "剑、枪、斧、弓、护手与黑白魔法的数值和特性。"},
        {"file": "gifts.html", "icon": "gift", "label": "礼物", "en": "GIFTS", "color": "var(--rose-pale)", "count": len(data["gifts"]),
         "desc": "按用途分类，附上喜欢它的角色。"},
        {"file": "seals.html", "icon": "seals", "label": "血印", "en": "BLOOD SEALS", "color": "var(--crimson)", "count": len(data["seals"]),
         "desc": "天冠血印的发动率、效果与持有者。"},
        {"file": "blaze.html", "icon": "blaze", "label": "爆炎技", "en": "BLAZE ARTS", "color": "var(--ember)", "count": sum(len(b["arts"]) for b in data["blaze"]),
         "desc": "主角与特殊角色的爆炎技：射程、爆炎消耗与习得时机。"},
        {"file": "blessings.html", "icon": "blessings", "label": "神之加护", "en": "BLESSINGS", "color": "var(--jade)", "count": len(data["gods"]),
         "desc": "七神三阶加护效果与天刻的白沙消耗。"},
    ]

    generic = [prepare_sheet_tab(t) for t in sheet_tabs() if t.get("file")]
    for t in generic:
        codex_items.append({"file": f"{t['slug']}.html", "icon": t.get("icon", "codex"), "label": t["title"], "en": t.get("en", "FROM THE SHEET"),
                            "color": t.get("color", "var(--gold)"), "count": len(t["rows"]), "desc": t.get("intro", "")[:40] or f"共创表「{t['name']}」分页。"})

    pages = [
        ("index.html", "index", "", "社群《火焰纹章 万缕千丝》共创资料表的图鉴版：角色、招募、兵种、羁绊、外传与图鉴。",
         {"sections": sections}),
        ("units.html", "units", "角色", f"万缕千丝 {u_count} 位角色：阵营、成长率、个人技能与四路线加入条件。",
         {"faction_options": fac_opts, "route_options": route_opts, "stat_options": stat_opts}),
        ("recruit.html", "recruit", "招募规划", "按路线排列可挖角的同伴：支援、名声门槛与交涉条件，可勾选已招募。", {}),
        ("classes.html", "classes", "兵种", "万缕千丝兵种阶梯：考试条件、训练加成、特技、精通与成长率加成，附成长模拟。",
         {"tier_options": tier_opts, "family_options": fam_opts, "kind_options": kind_opts}),
        ("bonds.html", "bonds", "羁绊", "万缕千丝支援关系：每位角色可达到 A／B／C 支援的对象。", {}),
        ("paralogues.html", "paralogues", "外传", "万缕千丝外传接取窗口日历：各路线开放章节、日期、地点与报酬。", {"route_options": route_opts}),
        ("codex.html", "codex", "图鉴", "武器与魔法、礼物、血印、爆炎技与神之加护。", {"codex_items": codex_items}),
        ("weapons.html", "weapons", "武器与魔法", "万缕千丝武器与魔法一览：威力、命中、必杀、射程、重量、耐久与说明。", {"wkind_options": wkind_opts}),
        ("gifts.html", "gifts", "礼物", "万缕千丝礼物一览：用途分类与喜欢它的角色。", {"gift_options": gift_opts}),
        ("seals.html", "seals", "血印", "万缕千丝血印（天冠）一览：发动率、效果与持有角色。", {}),
        ("blaze.html", "blaze", "爆炎技", "万缕千丝爆炎技一览：射程、爆炎消耗、习得时机与效果。", {}),
        ("blessings.html", "blessings", "神之加护", "万缕千丝七神加护：各等级效果与天刻的白沙消耗。", {}),
        ("about.html", "about", "关于", "本站资料来源、译名依据与更新方式。", {"glossary": glossary, "core": core}),
    ]
    for t in generic:
        pages.append((f"{t['slug']}.html", "sheet", t["title"], t.get("intro") or f"万缕千丝共创表「{t['name']}」分页。", {"tab": t, "template": "sheet.html"}))
    for u in data["units"]:
        pages.append((u["url"], "unit", u["name"], f"{u['name']}（{u['fac']['name']}）：成长率、个人技能、支援、礼物与加入条件。",
                      {"u": u, "template": "unit.html"}))

    versions = {"css": file_hash(OUT / "static" / "site.css"), "js": file_hash(OUT / "static" / "site.js"), "fonts": "0"}
    rendered: dict[str, dict[str, str]] = {}
    for lang, cfg in LANGS.items():
        rendered[lang] = {}
        for path, key, title, desc, extra in pages:
            depth = path.count("/")
            up = "../" * depth
            root = up + ("../" if lang == "hans" else "")
            alt = root + ("hans/" if lang == "hant" else "") + path
            ctx = {**data, **extra, "site": SITE, "nav": NAV, "lang": lang, "up": up, "root": root, "html_lang": cfg["html_lang"],
                   "font_key": cfg["font"], "page": path, "page_key": key, "page_title": title, "description": desc, "alt_href": alt,
                   "v": versions, "stat_labels": STATS}
            html = env.get_template(extra.get("template", path)).render(**ctx)
            if lang == "hant":
                html = add_alt_text(html)
                html = html_to_hant(html)
            html = html.replace("<!--noconv-->", "").replace("<!--/noconv-->", "")
            rendered[lang][path] = html

    font_versions = fonts.build(rendered, OUT / "static")
    for lang, cfg in LANGS.items():
        out_dir = OUT / cfg["prefix"]
        for path, html in rendered[lang].items():
            html = html.replace(f"fonts-{cfg['font']}.css?v=0", f"fonts-{cfg['font']}.css?v={font_versions[cfg['font']]}")
            dest = out_dir / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(html, encoding="utf-8")
        idx = search_index(data)
        if lang == "hant":
            for e in idx:
                for k in ("t", "s", "c"):
                    e[k] = text_to_hant(e[k])
                e["k"] = text_to_hant(e["k"]) + " " + e["k"]
        (out_dir / "search.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    write_404()
    write_sitemap([p[0] for p in pages])
    print("built", sum(len(v) for v in rendered.values()), "pages →", OUT.relative_to(ROOT))


def add_alt_text(html: str) -> str:
    """繁體頁的 data-text 會被轉成繁體；另存一份簡體在 data-alt（受保護），讓兩種寫法都搜得到。"""
    return re.sub(r'data-text="([^"]*)"', lambda m: f'data-text="{m.group(1)}" data-alt="{m.group(1)}"', html)


def write_404() -> None:
    b = SITE["base_path"]
    html = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>找不到頁面 · 萬縷千絲</title><link rel="stylesheet" href="{b}static/site.css"><style>body{{display:grid;place-items:center;min-height:100vh;text-align:center;padding:24px}}</style></head>
<body><main><p class="kicker">LOST THREAD</p><h1 class="gold-text" style="font-size:44px">這條絲線斷了</h1><p style="color:var(--muted)">找不到這個頁面。</p>
<p><a class="btn primary" href="{b}">回到首頁</a></p></main></body></html>"""
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
