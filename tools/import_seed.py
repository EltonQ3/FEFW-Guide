"""從姊妹站 fe-guide-wanlvqiansi 匯入種子資料與美術素材。

共創表（騰訊文檔）暫時無法直接讀取時，用姊妹站已從同一張表轉錄的
兵種、外傳、血印，以及角色招募／送禮資料建立 source/*.json。
表格可讀取後，由 tools/fetch_sheet.py 取得的分頁資料優先。

用法：python3 tools/import_seed.py --sister ../fe-guide-wanlvqiansi
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source"
ASSETS = ROOT / "assets"

SHEET_URL = "https://docs.qq.com/sheet/DV0N0VUZLSXRmUWFq"

# 姊妹站的派系字串 → 本站派系鍵
FACTION_KEYS = {
    "利贝拉之风（凯伊篇）": "ribeira",
    "拉弥努家族（迪托利希篇）": "lamine",
    "美盖拉的灯火（赛奥朵拉篇）": "megaira",
    "蔷薇风暴（蕾达篇）": "rose",
    "炎之鬃（贝特朗队）": "mane",
    "月之谎": "moon",
    "利纳利亚朝露": "linaria",
    "白鸦新娘团": "crow",
    "无派系 / 其他": "free",
    "四位主角 + 真主角": "savior",
}
# 姊妹站把這四人歸在「月之谎 / 白鸦新娘团 / 其他」混合欄。
# 貝特朗是「炎之鬃（贝特朗队）」隊長；譚利穆恩、愛娜特莉亞依繁中玩家站的陣營分組歸入；
# 安娜無可靠分組，歸入其他。
MIXED = "月之谎 / 白鸦新娘团 / 其他"
FACTION_OVERRIDE = {"62": "mane", "63": "moon", "29": "crow", "64": "free"}

ROUTES = [("kai", "凯伊线"), ("dietrich", "迪托利希线"), ("theodora", "赛奥朵拉线"), ("leda", "蕾达线")]

SEAL_KEYS = {
    "预言者之冠": "prophet",
    "使徒之天冠": "apostle",
    "永远之天冠": "eternity",
    "魂魄之天冠": "soul",
    "大地之天冠": "earth",
    "勇气之天冠": "courage",
    "天秤之天冠": "libra",
    "孤高之天冠": "solitude",
    "束缚之天冠": "bind",
    "再生之天冠": "rebirth",
}

GODS = [
    ("aurora", "奥罗拉", "アウロラ"),
    ("mars", "玛尔斯", "マーズ"),
    ("smyrnos", "斯米尔诺斯", "スミルノス"),
    ("jurah", "茱拉", "ジュラ"),
    ("kalla", "卡拉", "カーラ"),
    ("credna", "库莱尔", "クレール"),
    ("fortuna", "芙托娜", "フォトナ"),
]


def load_data_js(sister: Path) -> dict:
    s = (sister / "docs" / "data.js").read_text(encoding="utf-8")
    return json.loads(s[s.index("{"): s.rindex("}") + 1])


def md_table(md: str, heading: str) -> list[list[str]]:
    """讀出某個標題下的第一個 Markdown 表格（去掉粗體記號）。"""
    start = md.index(heading)
    rows = []
    for line in md[start:].splitlines()[1:]:
        line = line.strip()
        if not line:
            if rows:
                break
            continue
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [c.strip().replace("**", "") for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        rows.append(cells)
    return rows


def parse_recruit(text: str) -> dict:
    """「3S / 5R ・条件」→ 支援、名聲、附加條件；其餘保留原文。"""
    text = (text or "").strip()
    if not text or text == "—":
        return {"kind": "none"}
    m = re.match(r"(\d)S\s*/\s*(\d+)R\s*(?:・\s*(.*))?$", text)
    if m:
        cond = [c.strip() for c in (m.group(3) or "").split("・") if c.strip()]
        return {"kind": "scout", "support": int(m.group(1)), "renown": int(m.group(2)), "needs": cond}
    if "主角" in text:
        return {"kind": "lead", "text": text}
    if "自动加入" in text:
        return {"kind": "auto", "text": text}
    return {"kind": "note", "text": text}


def save_webp(src: Path, dst: Path, size: tuple[int, int] | None = None, quality: int = 82) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(src)
    im = im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    if size:
        im.thumbnail(size, Image.LANCZOS)
    im.save(dst, "WEBP", quality=quality, method=6)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sister", default=str(ROOT.parent / "fe-guide-wanlvqiansi"))
    args = ap.parse_args()
    sister = Path(args.sister)
    data = load_data_js(sister)
    manual = (sister / "source" / "火焰纹章万缕千丝_完全攻略手册.md").read_text(encoding="utf-8")
    i18n = json.loads((sister / "docs" / "data" / "i18n.json").read_text(encoding="utf-8"))
    sdocs = sister / "docs"

    # ── 角色 ─────────────────────────────────────────────
    en_names = {}
    for group in ("protagonists", "recruitable", "npcs_official"):
        for e in i18n.get(group, []):
            if e.get("en") and e["en"] != "—":
                en_names[e["zhs"]] = e["en"]
    # 送禮表中「名字 English」的英文名
    for row in re.findall(r"^\| \*\*(\S+) ([A-Z][A-Za-z' ]+?)(?:（[^）]*）)?\*\* \|", manual, flags=re.M):
        en_names.setdefault(row[0], row[1].strip())

    chars = []
    for c in data["characters"]:
        cid = c["id"]
        if not re.fullmatch(r"\d+|hero", cid):
            continue  # 沒有圖像的文字條目不建立角色卡
        faction = c.get("faction", "")
        fkey = FACTION_KEYS.get(faction, "free")
        if faction == MIXED:
            fkey = "free"
        fkey = FACTION_OVERRIDE.get(cid, fkey)
        img_id = "hero" if cid == "hero" else cid
        portrait_src = sdocs / (c.get("portrait") or f"assets/avatar/hero_m.jpg")
        avatar_src = sdocs / c["avatar"]
        portrait = f"portrait/{img_id}.webp"
        avatar = f"avatar/{img_id}.webp"
        if portrait_src.exists():
            save_webp(portrait_src, ASSETS / portrait)
        else:
            portrait = None
        save_webp(avatar_src, ASSETS / avatar, (160, 160))
        gifts = c.get("gifts") or {}
        recruit = {key: parse_recruit((c.get("recruit") or {}).get(label, "")) for key, label in ROUTES}
        chars.append({
            "id": img_id,
            "name": c["name"],
            "aliases": [a for a in c.get("aliases", []) if a != c["name"]],
            "jp": c.get("jp") or "",
            # 英文名只保留官方公布的（四主角與伊修瑪爾），社群自擬的英文名不收
            "en": en_names.get(c["name"], "") if cid in ("2", "3", "4", "5", "hero") else "",
            "faction": fkey,
            "portrait": portrait,
            "avatar": avatar,
            "likes": gifts.get("喜欢的东西", ""),
            "hobbies": gifts.get("兴趣", ""),
            "gifts": gifts.get("推荐礼物", ""),
            "recruit": recruit,
        })
    # 主角排在最前，依官方介紹順序
    order = {"2": 0, "3": 1, "4": 2, "5": 3, "hero": 4}
    chars.sort(key=lambda x: (order.get(x["id"], 9), int(x["id"]) if x["id"].isdigit() else 999))
    write(SRC / "characters.json", {
        "_source": [
            {"label": "姊妹站角色资料（招募表、送礼表）", "url": "https://github.com/EltonQ3/fe-guide-wanlvqiansi"},
        ],
        "items": chars,
    })

    # ── 兵種 ─────────────────────────────────────────────
    classes = json.loads((sister / "source" / "classes.json").read_text(encoding="utf-8"))
    out = []
    for i, k in enumerate(classes, 1):
        icon_src = sdocs / "assets" / "icon" / "class" / f"{k['name']}.png"
        icon = None
        if icon_src.exists():
            icon = f"class/{i:02d}.webp"
            save_webp(icon_src, ASSETS / icon, (128, 128), quality=90)
        item = {
            "id": f"c{i:02d}",
            "name": k["name"],
            "tier": k["tier"],
            "movement": k.get("movement", ""),
            "exam": k.get("exam", ""),
            "unlock": k.get("unlock", ""),
            "training": k.get("training", ""),
            "features": k.get("features", ""),
            "mastery": k.get("mastery", ""),
            "restriction": k.get("restriction", ""),
            "phase": k.get("phase", ""),
            "icon": icon,
        }
        out.append(item)
    write(SRC / "classes.json", {
        "_source": [{"label": "共创表 · 02-兵种职业信息（经姊妹站转录）", "url": SHEET_URL}],
        "items": out,
    })

    # ── 外傳 ─────────────────────────────────────────────
    paras = json.loads((sister / "source" / "paralogues.json").read_text(encoding="utf-8"))
    out = []
    for p in paras:
        out.append({
            "id": p["id"],
            "person": p["person"],
            "title": p["title"],
            "place": p.get("place", ""),
            "reward": p.get("reward", ""),
            "routes": {r: [{k: w.get(k) for k in ("chapter", "start", "end", "deadline")} for w in ws]
                       for r, ws in p.get("routes", {}).items()},
            "people": p.get("people", ""),
            "steps": p.get("steps", ""),
            "consequence": p.get("consequence", ""),
        })
    write(SRC / "paralogues.json", {
        "_source": [{"label": "共创表 · 03-全外传信息（经姊妹站转录）", "url": SHEET_URL}],
        "items": out,
    })

    # ── 血印 ─────────────────────────────────────────────
    rows = md_table(manual, "## 5.8 血印")
    seals = []
    for name, effect, holders in rows[1:]:
        key = SEAL_KEYS[name]
        src = sdocs / "assets" / "icon" / "crest" / f"{name}.png"
        icon = f"seal/{key}.webp"
        save_webp(src, ASSETS / icon, quality=90)
        m = re.match(r"攻击时\s*(\d+)%\s*发动，(.*)", effect)
        seals.append({
            "id": key,
            "name": name,
            "chance": int(m.group(1)) if m else None,
            "effect": m.group(2) if m else effect,
            "holders": [h.strip() for h in holders.split("、") if h.strip()],
            "icon": icon,
        })
    write(SRC / "seals.json", {
        "_source": [{"label": "共创表 · 血印分页（经姊妹站转录）", "url": SHEET_URL}],
        "items": seals,
    })

    # ── 神之加護 ─────────────────────────────────────────
    rows = md_table(manual, "## 3.2 七神加护效果全表")
    gods = []
    by_name = {r[0]: r for r in rows[1:]}
    for key, zh, jp in GODS:
        r = by_name[zh]
        cost = re.findall(r"\d+", r[4])
        gods.append({
            "id": key,
            "name": zh,
            "jp": jp,
            "levels": [x.replace("（剧情解锁，不可侍奉）", "") for x in r[1:4] if x and x != "—"],
            "cost": {"normal": int(cost[0]), "hard": int(cost[1])} if len(cost) >= 2 else None,
            "note": "剧情解锁，不可侍奉" if key == "fortuna" else "",
        })
    write(SRC / "blessings.json", {
        "_source": [{"label": "姊妹站手册 3.2 七神加护效果全表", "url": "https://fe-guide.pages.dev/"}],
        "items": gods,
    })

    # ── 品牌素材 ─────────────────────────────────────────
    (ASSETS / "brand").mkdir(parents=True, exist_ok=True)
    shutil.copy(sdocs / "assets" / "game-logo.webp", ASSETS / "brand" / "game-logo.webp")
    print("characters", len(chars), "classes", len(classes), "paralogues", len(paras), "seals", len(seals))


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
