"""把 Game8 英文攻略整理成的資料庫（Rico0319/Fortunes-Weave-Helper 的 data/fwe.db）
合併進本站資料，輸出簡體中文 JSON。

共創表／姊妹站已有的中文資料（招募、送禮、兵種考試、外傳日期、血印名稱）優先；
Game8 補上共創表待完善的部分：成長率、兵種成長加成、支援關係、個人技能、爆炎技、
魔法習得、喜歡的禮物、武器與魔法數值、新角色。

英文專有名詞經 source/i18n/*.json 對照成中文，每個名稱帶 status：
official／sheet／community／provisional（暫譯）。對照表裡沒有的詞會列在
「未翻譯」清單並保留英文，不會讓建置失敗——定期更新時看這份清單補詞即可。

用法：python3 tools/import_game8.py --db ../rico0319/fortunes-weave-helper/data/fwe.db
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source"
I18N = SRC / "i18n"
ASSETS = ROOT / "assets"
DEFAULT_DB = ROOT.parent / "rico0319" / "fortunes-weave-helper" / "data" / "fwe.db"
SISTER = ROOT.parent / "fe-guide-wanlvqiansi"
GAME8 = "https://game8.co/games/Fire-Emblem-Fortunes-Weave/archives/"
HELPER = "https://github.com/Rico0319/Fortunes-Weave-Helper"

STATS = ["HP", "Str", "Mag", "Spd", "Dex", "Def", "Res", "Lck", "Cha"]
ROUTE_KEYS = {"Riberia Wind": "kai", "Ribeira Winds": "kai", "House Lamine": "dietrich", "Megaira": "theodora", "Rose Tempest": "leda"}

# 姊妹站沒有立繪對應的新角色：取姊妹站素材庫裡未使用的立繪編號（立繪卡上的日文名已逐一核對）
NEW_PORTRAITS = {"Orchel": "26", "Nathan": "38", "Creek": "39", "Hong Hua": "40", "Troy": "41", "Centurio": "42", "Inyoni": "60"}

# 共創表／姊妹站沒有招募資料的角色：依 Game8 招募頁整理的加入方式（中文摘要）
JOIN_NOTES = {
    "Eshmel": "真主角。序章起即在队伍中，于「未来」时间线出击；对过去的伙伴则通过白鸟时间提升支援。",
    "Hong Hua": "序章「降临」起自动加入，与伊修玛尔一同在未来时间线出击。",
    "Troy": "序章「降临」起自动加入，与伊修玛尔一同在未来时间线出击。",
    "Orchel": "第一部各路线完成「奥尔赫尔外传」（10/18 起），第三部救世篇第一区段自动加入。",
    "Creek": "第一部于迪托利希篇或蕾达篇完成委托「亡妹的饰品」（寻找紫色胸针），第二部战争篇第2章击败齐利科后加入。跳过战争篇则无法招募。",
    "Nathan": "须先招入齐利科，并在第二部第3章让齐利科出击、由他击败内森。",
    "Centurio": "第三部救世篇第二区段起，完成委托「救出盛托利翁」后在鞑古席翁与他交谈即可招募。",
    "Aswan": "第三部救世篇第五区段自动加入。第二部第3章以客将身份登场，需让她存活。",
    "Tahonia": "阿斯旺的侍从。第三部救世篇第五区段自动加入；第二部第3章以客将身份登场，需让她存活。",
}


# 兵種特技與精通（Game8 英文 → 中文）。sheet＝共創表已有的寫法
CLASS_ABILITIES = {
    "Black-Magic Seeker": ("黑魔术的探究", "sheet"), "White-Magic Seeker": ("白魔术的探究", "sheet"),
    "Combat Arts +2": ("战技装备+2", "sheet"), "Combat Arts +3": ("战技装备+3", "sheet"), "Mount/Dismount": ("乘降术", "sheet"),
    "War-Elephant Boots": ("战象之靴", "provisional"), "Astra": ("流星", "provisional"), "Makeshift": ("物尽其用", "provisional"),
    "Elephant Vanguard": ("战象先锋", "provisional"), "Hunter's Cross": ("猎人十字", "provisional"), "Fierce Shield": ("猛盾", "provisional"),
    "Dark Moon": ("暗月", "provisional"), "Song of Calm": ("平静之歌", "provisional"),
}


def skill_bonus(text: str, core: dict) -> str:
    """「Sword +2, Spear +1」→「剑术+2、枪术+1」（複數寫法 Swords 也接受）。"""
    out = []
    for part in text.split(","):
        if "+" not in part:
            continue
        name, val = part.split("+", 1)
        name = name.strip()
        zh = core["skills"].get(name) or core["skills"].get(name.rstrip("s")) or name
        out.append(f"{zh}+{val.strip()}")
    return "、".join(out)


def load_i18n(name: str) -> dict:
    return json.loads((I18N / f"{name}.json").read_text(encoding="utf-8"))


class Tx:
    """英→中查表，記錄缺漏。"""

    def __init__(self) -> None:
        self.missing: dict[str, set[str]] = defaultdict(set)

    def name(self, table: dict, en: str, kind: str) -> dict:
        en = (en or "").strip()
        v = table.get(en)
        if v is None:
            self.missing[kind].add(en)
            return {"name": en, "en": en, "status": "untranslated"}
        if isinstance(v, str):
            return {"name": v, "en": en, "status": "provisional"}
        return {"name": v[0], "en": en, "status": v[1]}

    def text(self, table: dict, en: str, kind: str) -> str:
        en = (en or "").strip()
        if not en:
            return ""
        if en in table:
            return table[en]
        self.missing[kind].add(en)
        return en


def tg(db, pid: str, idx: int) -> list[list[str]]:
    row = db.execute("select rows from tables_generic where page_id=? and idx=?", (pid, idx)).fetchone()
    return json.loads(row[0]) if row else []


def dedup(s: str) -> str:
    """Game8 表格常把圖示替代文字與名稱重複一次：「Cai Cai」→「Cai」。"""
    w = s.split(" ")
    n = len(w) // 2
    return " ".join(w[:n]) if len(w) % 2 == 0 and w[:n] == w[n:] else s


def slug(en: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", en.lower()).strip("-")


def save_img(src: Path, dst: Path, size=None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    im = Image.open(src)
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    if size:
        im.thumbnail(size, Image.LANCZOS)
    im.save(dst, "WEBP", quality=82, method=6)


def write(name: str, obj) -> None:
    (SRC / f"{name}.json").write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--sister", default=str(SISTER))
    args = ap.parse_args()
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    sister_assets = Path(args.sister) / "docs" / "assets"
    tx = Tx()
    core, ab, bl, se, wp, gf = (load_i18n(n) for n in ("core", "abilities", "blaze", "seals", "weapons", "gifts"))
    pages = {r["id"]: r["url"] for r in db.execute("select id, url from pages")}

    # ── 共創表／姊妹站既有資料 ──────────────────────────────
    base = SRC / "base"
    sheet_chars = {c["name"]: c for c in json.loads((base / "characters.json").read_text(encoding="utf-8"))["items"]}
    sheet_classes = json.loads((base / "classes.json").read_text(encoding="utf-8"))
    sheet_paras = json.loads((base / "paralogues.json").read_text(encoding="utf-8"))
    sheet_seals = json.loads((base / "seals.json").read_text(encoding="utf-8"))
    (SRC / "blessings.json").write_text((base / "blessings.json").read_text(encoding="utf-8"), encoding="utf-8")
    fac_keys = {en: v[2] for en, v in core["factions"].items()}

    # ── 角色 ─────────────────────────────────────────────
    units = []
    rows = db.execute("select * from characters order by name").fetchall()
    supports = defaultdict(dict)
    for r in db.execute("select name, partner, rank from char_supports"):
        supports[r["name"]][r["partner"]] = r["rank"]
    gifts_by = defaultdict(list)
    for r in db.execute("select name, gift from char_gifts"):
        gifts_by[r["name"]].append(r["gift"])
    prefs = defaultdict(lambda: {"preferred": [], "non_ideal": []})
    for r in db.execute("select name, kind, skill from char_skill_prefs"):
        prefs[r["name"]][r["kind"]].append(r["skill"].replace(" Skill", ""))
    spells = defaultdict(list)
    for r in db.execute("select name, skill_level, magic, spell from char_spells"):
        spells[r["name"]].append(r)
    blaze = defaultdict(list)
    for r in db.execute("select name, art, effect, range, blaze, learned from char_blaze"):
        blaze[r["name"]].append(r)

    for r in rows:
        en = r["name"]
        nm = tx.name(core["units"], en, "units")
        zh = nm["name"]
        sc = sheet_chars.get(zh) or next((c for c in sheet_chars.values() if zh in c.get("aliases", [])), None)
        if en == "Inyoni":
            sc = sheet_chars.get("伊尼奥尼") or sc
        uid = slug(en)
        # 圖像：沿用共創表角色卡的編號；新角色取對應立繪
        img = sc["id"] if sc else NEW_PORTRAITS.get(en)
        portrait = avatar = None
        if img:
            psrc = sister_assets / "portrait" / f"{img}.jpg"
            asrc = sister_assets / "avatar" / f"{img}.jpg"
            if img == "hero":
                psrc = sister_assets / "avatar" / "hero_m.jpg"
                asrc = sister_assets / "avatar" / "hero_m.jpg"
            if psrc.exists():
                portrait = f"portrait/{img}.webp"
                save_img(psrc, ASSETS / portrait)
            if asrc.exists():
                avatar = f"avatar/{img}.webp"
                save_img(asrc, ASSETS / avatar, (160, 160))
        growth = {s: r[f"growth_{s.lower()}"] for s in STATS}
        fac_en = r["faction"] or "Neutral"
        unit = {
            "id": uid, "en": en, "name": zh, "name_status": nm["status"],
            "jp": (sc or {}).get("jp") or core["unit_jp"].get(en, ""),
            "aliases": [a for a in (sc or {}).get("aliases", []) if a != zh],
            "faction": fac_keys.get(fac_en, "free"),
            "portrait": portrait, "avatar": avatar,
            "lead": en in ("Cai", "Dietrich", "Theodora", "Leda", "Eshmel"),
            "desc": ab["descriptions"].get(en, ""),
            "ability": None,
            "growth": growth, "growth_total": sum(growth.values()),
            "prefs": {k: [core["skills"].get(s, s) for s in v] for k, v in prefs[en].items()},
            "likes": (sc or {}).get("likes", ""), "hobbies": (sc or {}).get("hobbies", ""),
            "gift_note": (sc or {}).get("gifts", ""),
            "gifts": [tx.name(gf["names"], g, "gifts") for g in gifts_by.get(en, [])],
            "recruit": (sc or {}).get("recruit"),
            "join": JOIN_NOTES.get(en, ""),
            "supports": sorted(([slug(p), rk] for p, rk in supports[en].items()), key=lambda x: ("ABC".index(x[1]), x[0])),
            "blaze": [],
            "spells": [],
            "source": GAME8 + r["page_id"] if r["page_id"] else "",
        }
        if r["ability"]:
            a = tx.name(ab["names"], r["ability"], "abilities")
            a["effect"] = tx.text(ab["effects"], r["ability_effect"], "ability_effects")
            unit["ability"] = a
        for b in blaze.get(en, []):
            art = tx.name(bl["names"], b["art"], "blaze")
            art.update({"effect": tx.text(bl["effects"], b["effect"], "blaze_effects"),
                        "range": {"Self": "自身"}.get(b["range"], b["range"]) if b["range"] not in ("-", "") else "", "cost": b["blaze"] if b["blaze"] not in ("-", "Grants") else "",
                        "learned": bl["learned"].get(b["learned"], b["learned"])})
            unit["blaze"].append(art)
        for s in spells.get(en, []):
            sp = tx.name(wp["names"], s["spell"], "spells")
            unit["spells"].append({"level": s["skill_level"], "magic": "black" if s["magic"].startswith("Black") else "white", **sp})
        if not unit["likes"] and r["likes"]:
            unit["likes_en"] = r["likes"]
        if not unit["hobbies"] and r["interests"]:
            unit["hobbies_en"] = r["interests"]
        units.append(unit)

    # 共創表有、Game8 沒列為可用角色的（安娜）
    known = {u["name"] for u in units}
    for zh, c in sheet_chars.items():
        if zh in known or zh == "伊尼奥尼":
            continue
        units.append({
            "id": slug(next((en for en, v in core["units"].items() if v[0] == zh), c["id"])), "en": next((en for en, v in core["units"].items() if v[0] == zh), ""),
            "name": zh, "name_status": "sheet", "jp": c.get("jp", ""), "aliases": c.get("aliases", []),
            "faction": c.get("faction", "free"), "portrait": c.get("portrait"), "avatar": c.get("avatar"),
            "lead": False, "desc": "", "ability": None, "growth": None, "growth_total": None, "prefs": {},
            "likes": c.get("likes", ""), "hobbies": c.get("hobbies", ""), "gift_note": c.get("gifts", ""), "gifts": [],
            "recruit": c.get("recruit"), "join": "", "supports": [], "blaze": [], "spells": [], "source": "",
        })

    # ── 血印 ─────────────────────────────────────────────
    sheet_by_name = {s["name"]: s for s in sheet_seals["items"]}
    seals = []
    for item, rest in tg(db, "624378", 0):
        en = dedup(item)
        nm = tx.name(se["names"], en, "seals")
        key = se["names"].get(en, [None, None, slug(en)])[2]
        m = re.match(r"(.*?)(Grants|Multiplies|Restores|Unit cannot)(.*)Trigger % = (\d+)\.", rest)
        # 持有者欄是「Cai Cai Theodora Theodora …效果」：按已知角色名（含兩個字的英文名）逐一比對
        head = m.group(1) if m else ""
        holders_en = []
        for name in sorted(core["units"], key=len, reverse=True):
            if f"{name} {name}" in head:
                holders_en.append((head.index(f"{name} {name}"), name))
                head = head.replace(f"{name} {name}", " " * (2 * len(name) + 1))
        holders_en = [n for _, n in sorted(holders_en)]
        effect_en = (m.group(2) + m.group(3)).strip() if m else rest
        chance = int(m.group(4)) if m else None
        old = sheet_by_name.get(nm["name"])
        holders = list(old["holders"]) if old else []
        for h in holders_en:
            z = core["units"].get(h, [h])[0]
            if z not in holders:
                holders.append(z)
        seals.append({
            "id": key, **nm,
            "chance": old["chance"] if old else chance,
            "effect": old["effect"] if old else tx.text(se["effects"], effect_en.replace(" when attacking", " when attacking").rstrip("."), "seal_effects"),
            "holders": holders,
            "holders_sheet": old["holders"] if old else [],
            "icon": old["icon"] if old else None,
        })
    seals.sort(key=lambda s: [x["id"] for x in sheet_seals["items"]].index(s["id"]) if s["id"] in [x["id"] for x in sheet_seals["items"]] else 99)
    write("seals", {"_source": [*sheet_seals["_source"], {"label": "Game8 · 血印一览（经 Fortunes-Weave-Helper 整理）", "url": GAME8 + "624378"}],
                    "items": seals})

    # ── 兵種 ─────────────────────────────────────────────
    cg = defaultdict(lambda: {"growth": {}, "bonus": {}})
    for r in db.execute("select class, stat, kind, value from class_growths"):
        cg[r["class"]][r["kind"]][r["stat"]] = r["value"]
    by_zh = {k["name"]: k for k in sheet_classes["items"]}
    db_classes = {r["name"]: r for r in db.execute("select * from classes")}
    tier_zh = {"Beginner": "初级", "Specialty": "中级", "Advanced": "上级与高级", "Master": "最上级", "Divine": "神将"}
    next_id = len(sheet_classes["items"]) + 1
    for en, (zh, status) in core["classes"].items():
        k = by_zh.get(zh)
        g = cg.get(en)
        if k is None:
            r = db_classes.get(en)
            if r is None:
                continue
            types = [core["unit_types"].get(t, t) for t in re.findall(r"Heavy Armor|Infantry|Cavalry|Flier", r["type"] or "")]
            k = {
                "id": f"c{next_id:02d}", "name": zh, "tier": tier_zh.get(r["tier"], r["tier"]), "movement": r["movement"] or "",
                "exam": "、".join(x for x in [f"建议 Lv{r['ideal_lv']}" if r["ideal_lv"] else "", f"名声 Lv{r['renown_lv']}" if r["renown_lv"] else ""] if x),
                "unlock": "", "training": skill_bonus(r["skill_exp_bonus"] or "", core),
                "features": " · ".join(types) + (f"，【{CLASS_ABILITIES.get(r['class_ability'], (r['class_ability'],))[0]}】" if r["class_ability"] else ""),
                "mastery": f"【{CLASS_ABILITIES.get(r['master_ability'], (r['master_ability'],))[0]}】" if r["master_ability"] else "",
                "mastery_status": CLASS_ABILITIES.get(r["master_ability"], ("", "untranslated"))[1] if r["master_ability"] else "",
                "restriction": "", "phase": "", "icon": None,
                "added_from": "game8",
            }
            next_id += 1
            sheet_classes["items"].append(k)
            by_zh[zh] = k
        k["en"] = en
        k["name_status"] = status
        r = db_classes.get(en)
        if r:
            wk = {"Sword": "剑", "Spear": "枪", "Axe": "斧", "Bow": "弓", "Gauntlet": "护手", "Black Magic": "黑魔法", "White Magic": "白魔法"}
            k["weapons"] = [wk.get(w.strip(), w.strip()) for w in (r["weapons"] or "").split(",") if w.strip()]
            # 共創表留空或待核對的欄位，以 Game8 補上並註明
            filled = []
            if not re.fullmatch(r"\d+", str(k.get("movement", ""))) and r["movement"]:
                k["movement"] = r["movement"]
                filled.append("移动")
            if k.get("training") in ("", "尚未收录", None) and r["skill_exp_bonus"]:
                k["training"] = skill_bonus(r["skill_exp_bonus"], core)
                filled.append("训练加成")
            if (not k.get("mastery") or "待核对" in k.get("mastery", "")) and r["master_ability"]:
                ma = CLASS_ABILITIES.get(r["master_ability"], (r["master_ability"], "untranslated"))
                exp = re.search(r"(\d+)", k.get("mastery", "") or "")
                k["mastery"] = f"【{ma[0]}】" + (f"（{exp.group(1)}）" if exp else "")
                k["mastery_status"] = ma[1]
                filled.append("精通")
            if filled:
                k["filled_from_game8"] = filled
            k["source"] = GAME8 + r["page_id"]
        if g:
            k["growth"] = {s: g["growth"].get(s, 0) for s in STATS}
            k["bonus"] = {s: g["bonus"].get(s, 0) for s in STATS}
        elif en in ("Commoner", "Noble"):  # 基礎兵種不加成長率（Game8 成長率說明）
            k["growth"] = {s: 0 for s in STATS}
    sheet_classes["_source"] = [s for s in sheet_classes["_source"] if "Game8" not in s["label"]] + [
        {"label": "Game8 · 兵种成长率（经 Fortunes-Weave-Helper 整理）", "url": GAME8 + "618974"}]
    write("classes", sheet_classes)

    # ── 外傳：補 Game8 的接取窗口與奧爾赫爾外傳 ─────────────────
    avail = tg(db, "624240", 0)
    hdr = avail[0]
    g8 = {}
    for row in avail[1:]:
        person = core["units"].get(row[0], [row[0]])[0]
        wins = {}
        for col, cell in zip(hdr[1:], row[1:]):
            rk = ROUTE_KEYS.get(col)
            spans = re.findall(r"(\d+/\d+)(?:\s*-\s*(\d+/\d+))?(\*)?", cell)
            if rk and spans:
                wins[rk] = [{"start": a, "end": b or a, "note": "*" if star else ""} for a, b, star in spans]
        g8[person] = wins
    for p in sheet_paras["items"]:
        p["game8"] = g8.get(p["person"], {})
    if not any(p["person"] == "奥尔赫尔" for p in sheet_paras["items"]):
        wins = g8.get("奥尔赫尔", {})
        chap = {"kai": "11", "dietrich": "11", "theodora": "12", "leda": "11"}
        sheet_paras["items"].append({
            "id": "orchel", "person": "奥尔赫尔", "title": "奥尔赫尔的遗憾", "title_status": "provisional",
            "place": "", "reward": "", "people": "奥尔赫尔",
            "routes": {rk: [{"chapter": chap.get(rk, ""), "start": w["start"], "end": w["end"], "deadline": None} for w in ws] for rk, ws in wins.items()},
            "steps": "", "consequence": "完成后，奥尔赫尔会在第三部救世篇第一区段自动加入。", "game8": wins, "added_from": "game8",
        })
    sheet_paras["_source"] = [s for s in sheet_paras["_source"] if "Game8" not in s["label"]] + [
        {"label": "Game8 · 外传开放日期（经 Fortunes-Weave-Helper 整理）", "url": GAME8 + "624240"}]
    write("paralogues", sheet_paras)

    # ── 武器與魔法 ─────────────────────────────────────────
    weapons = []
    for pid, kind in [("621071", "sword"), ("621072", "spear"), ("621073", "axe"), ("621074", "bow"), ("621076", "gauntlet"),
                      ("621078", "black"), ("621077", "white")]:
        rows_ = tg(db, pid, 2)
        for row in rows_[1:]:
            if row[0].startswith("Description:"):
                weapons[-1]["desc"] = tx.text(wp["descriptions"], row[0][len("Description:"):].strip(), "weapon_desc")
                continue
            nm = tx.name(wp["names"], row[0], "weapons")
            cells = dict(zip(["might", "uses", "range", "hit", "crit", "weight"], row[1:7]))
            for key, val in cells.items():
                cells[key] = "" if val in ("-", "TBD", "") else val
            req = re.findall(r"(Sword|Spear|Axe|Bow|Gauntlet) ([A-ES])", row[7])
            weapons.append({"id": slug(row[0]), "kind": kind, **nm, **cells,
                            "rank": "、".join(f"{core['skills'][w]} {lv}" for w, lv in req), "desc": "", "source": GAME8 + pid})
    write("weapons", {"_source": [{"label": "Game8 · 武器与魔法一览（经 Fortunes-Weave-Helper 整理）", "url": GAME8 + "621071"}], "items": weapons})

    # ── 禮物 ─────────────────────────────────────────────
    gifts = []
    likers = defaultdict(list)
    for u in units:
        for g in u["gifts"]:
            likers[g["en"]].append(u["id"])
    for item, desc in tg(db, "621535", 1):
        en = dedup(re.sub(r"^Fire Emblem Fortunes Weave ", "", item)).replace("Trader Trader's", "Trader's")
        nm = tx.name(gf["names"], en, "gifts")
        who = ""
        m = re.search(r"\bP\w*\s*\w*joyed by\s*(.+?)\.?$", desc or "")
        body = desc
        if m:
            who = gf["likers"].get(m.group(1).strip().replace("ehtusiasts", "enthusiasts").replace("bythose", "those"), m.group(1))
            body = desc[: m.start()].strip()
        gifts.append({"id": slug(en), **nm, "for": who, "desc": "" if desc == "TBA" else tx.text(gf["descriptions"], body, "gift_desc"),
                      "liked_by": likers.get(en, [])})
    known_g = {g["en"] for g in gifts}
    for en, ids in likers.items():
        if en not in known_g:
            gifts.append({"id": slug(en), **tx.name(gf["names"], en, "gifts"), "for": "", "desc": "", "liked_by": ids})
    write("gifts", {"_source": [{"label": "Game8 · 礼物一览与各角色喜好（经 Fortunes-Weave-Helper 整理）", "url": GAME8 + "621535"}], "items": gifts})

    write("units", {"_source": [
        {"label": "共创表／姊妹站：招募条件、喜好与推荐礼物", "url": "https://github.com/EltonQ3/fe-guide-wanlvqiansi"},
        {"label": "Game8 · 角色资料、成长率、支援、技能（经 Fortunes-Weave-Helper 整理）", "url": HELPER}], "items": units})

    report = {k: sorted(v) for k, v in tx.missing.items()}
    (SRC / "i18n" / "_missing.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"units {len(units)} · classes {len(sheet_classes['items'])} · seals {len(seals)} · weapons {len(weapons)} · gifts {len(gifts)}"
          f" · paralogues {len(sheet_paras['items'])}")
    if report:
        print("未翻译：", {k: len(v) for k, v in report.items()}, "→ source/i18n/_missing.json")


if __name__ == "__main__":
    main()
