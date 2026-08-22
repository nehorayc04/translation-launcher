"""Build the community /translate upload for Skyrim SE / AE.

string_key = EXACTLY what the build consumes, so an approved export drops straight
onto the build with no remapping:
    "<plugin>|<id>|<kind>"   the .STRINGS/.DLSTRINGS/.ILSTRINGS tables
    "ui:<$key>"              interface/translate_english.txt
    "launcher:<id>"          SkyrimSELauncher.exe RT_STRING

NO dedup by English. Measured against the game's OWN professional locales, 8,004
duplicate-English groups exist and **6.8-18.6% of them get DIFFERENT translations**
(pl 18.6% · ru 14.9% · fr 8.5% · de 6.8%) -- e.g. "Reduced Health" is predicative in
one place and attributive in another. Collapsing them would silently put one wrong
Hebrew on ~1,200 groups, so the 21% row redundancy is the cheaper mistake.

Categories are the engine's OWN surface metadata (file kind), never a length
heuristic, ordered by VISIBILITY so a partial pass covers what players see first.

context carries the game's own RUSSIAN line -- 100% key parity, and Russian past
tense marks SPEAKER *and* ADDRESSEE gender, which English drops. An auto-hint is
added only where the oracle is unambiguous; the raw sentence is the real value.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT.parents[1] / "universal"))

import launcher_res as LR      # noqa: E402
import translate_txt as TT     # noqa: E402

try:
    from gender_oracle import ru_addressee, ru_speaker
except Exception:                                   # noqa: BLE001
    ru_addressee = ru_speaker = lambda _s: None     # noqa: E731

E = ROOT / "extract"
RAW = E / "raw"
LAUNCHER = Path(r"D:\Games\TES - Skyrim - Anniversary Edition\SkyrimSELauncher.exe.he_backup")

# surface -> (hebrew category, visibility rank)
CATS = {
    "launcher": ("ממשק המשגר", 0),
    "ui":       ("ממשק ותפריטים", 1),
    "strings":  ("שמות ופריטים", 2),
    "ilstrings": ("כתוביות עלילה", 3),
    "dlstrings": ("תיאורים וספרים", 4),
}

_TOK = re.compile(r"<[^<>\n]{1,80}>|\[[A-Za-z][A-Za-z0-9 _/]{0,30}\]|%[sdi]")
_LETTER = re.compile(r"[A-Za-z\u00C0-\u024F]")


def translatable(en: str) -> bool:
    """Drop only what CANNOT be translated: no letter survives once the engine's
    own tokens, digits and punctuation are removed. A bare proper noun is a
    TRANSLATOR decision, not ours, so it stays in the pool."""
    if not en.strip():
        return False
    return bool(_LETTER.search(_TOK.sub(" ", en)))


def gender_bits(ru: str) -> str:
    if not ru:
        return ""
    a, s = ru_addressee(ru), ru_speaker(ru)
    out = []
    if a:
        out.append("נמען=" + {"f": "נקבה", "m": "זכר", "pl": "רבים"}.get(a, a))
    if s:
        out.append("דובר=" + {"f": "נקבה", "m": "זכר", "pl": "רבים"}.get(s, s))
    return (" · מגדר: " + ", ".join(out)) if out else ""


def main() -> int:
    en_all = json.loads((E / "en_all.json").read_text(encoding="utf-8"))
    ru = json.loads((E / "langs" / "russian.json").read_text(encoding="utf-8"))

    rows: list[dict] = []
    dropped = {"empty_or_tokens": 0}

    # --- 0. launcher (already 100% translated -> improve mode)
    sys.path.insert(0, str(HERE))
    from build_launcher_he import REAL_STRINGS                       # noqa: E402
    en_launcher = {k: v for k, v in LR.read_strings(LAUNCHER).items()
                   if 10000 <= k <= 10063}
    for sid, e in sorted(en_launcher.items()):
        if not translatable(e):
            dropped["empty_or_tokens"] += 1
            continue
        rows.append({"k": f"launcher:{sid}", "en": e,
                     "he": REAL_STRINGS.get(sid, ""), "ctx": "SkyrimSELauncher",
                     "surface": "launcher"})

    # --- 1. the UI table (menus / settings / HUD labels)
    ui = TT.load(RAW / "interface" / "translate_english.txt")
    for key, e in ui.items():
        if not translatable(e):
            dropped["empty_or_tokens"] += 1
            continue
        rows.append({"k": f"ui:{key}", "en": e, "he": "",
                     "ctx": "translate_english.txt", "surface": "ui"})

    # --- 2..4 the game string tables
    for k, e in en_all.items():
        plug, sid, kind = k.split("|")
        if not translatable(e):
            dropped["empty_or_tokens"] += 1
            continue
        r = ru.get(k, "")
        ctx = f"{plug}·{kind}"
        if r and r != e:
            ctx += f" · RU: {r[:220]}" + gender_bits(r)
        rows.append({"k": k, "en": e, "he": "", "ctx": ctx, "surface": kind})

    # --- order by VISIBILITY, then stable within a surface
    rows.sort(key=lambda r: (CATS[r["surface"]][1], r["k"]))
    out = []
    for i, r in enumerate(rows):
        out.append({"string_key": r["k"], "source_en": r["en"],
                    "current_he": r["he"], "context": r["ctx"],
                    "section": CATS[r["surface"]][0], "order_index": i})

    dst = E / "ct_upload.json"
    dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    import collections
    per = collections.Counter(r["section"] for r in out)
    seeded = sum(1 for r in out if r["current_he"])
    hinted = sum(1 for r in out if "מגדר:" in r["context"])
    ructx = sum(1 for r in out if " · RU: " in r["context"])
    print(f"rows {len(out)}  dropped {dropped}  -> {dst}")
    print(f"seeded with Hebrew (improve mode): {seeded}")
    print(f"context carries the game's Russian: {ructx}   auto gender hint: {hinted}")
    for s, _rank in sorted(CATS.values(), key=lambda t: t[1]):
        print(f"  {s:<18} {per.get(s, 0)}")
    # keys must be unique or the upsert silently collapses rows
    ks = [r["string_key"] for r in out]
    assert len(ks) == len(set(ks)), "duplicate string_key"
    # the UI table keys BY the English sentence ($key), so a few keys are long.
    # Postgres btree tops out near 2704 bytes; stay well under it.
    assert max(len(k.encode()) for k in ks) < 2000, "string_key too long for the index"
    print("string_key: unique, max len", max(len(k) for k in ks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
