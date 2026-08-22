"""Build the community /translate upload for Forza Horizon 6.

string_key = "<table>:<IDS>" -- EXACTLY the key `build_menu_he.py`'s `HE` dict uses
(`HE[(tbl, idn)]`), so an approved export drops straight onto the build with no
remapping: `for r in rows: HE[(table, ids)] = r["approved_text"]`.

Categories = the engine's OWN table-name grouping (the same SUBT keyword split
`scope.py` already reported: UI/content 31,094 vs dialogue/VO 11,474), never a
length heuristic, ordered by VISIBILITY so a partial pass covers menus first.

NO dedup by English -- same string can legitimately need different Hebrew in
different tables (a car description vs. a menu label sharing wording), and
dedup risk was never measured for this game -- key by (table, id) instead.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
E = ROOT / "extract"

# table name -> (hebrew category, visibility rank). Matches scope.py's own
# SUBT keyword classifier so the split is the engine's, not a guess.
SUBT = ("Dialogue", "Subtitle", "VO", "Anna", "Campaign", "Cutscene",
        "Narrative", "Story", "Radio", "DJ")
CAT_UI = ("ממשק ותפריטים", 0)
CAT_DIALOGUE = ("כתוביות ודיאלוג", 1)

_STRIP = re.compile(r"<[^>]+>|\{[^}]*\}|\[[^\]\s]+\]|%[\d.*]*[a-zA-Z]|&[A-Za-z#0-9]+;|\\n")
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


def translatable(en: str) -> bool:
    """Drop only what CANNOT be translated: no real word survives once the
    engine's own tokens/placeholders/digits/punctuation are removed. A bare
    proper noun (a car or driver name) is a TRANSLATOR decision, not ours."""
    if not en.strip():
        return False
    return bool(_LATIN_WORD.search(_STRIP.sub(" ", en)))


def category(table: str) -> tuple[str, int]:
    return CAT_DIALOGUE if any(s.lower() in table.lower() for s in SUBT) else CAT_UI


def main() -> int:
    en = json.loads((E / "en.json").read_text(encoding="utf-8"))

    rows: list[dict] = []
    dropped = 0
    for table, vals in en.items():
        cat, rank = category(table)
        for idn, e in vals.items():
            if not translatable(e):
                dropped += 1
                continue
            rows.append({
                "k": f"{table}:{idn}", "en": e, "cat": cat, "rank": rank,
                "ctx": table,
            })

    # order by VISIBILITY, then stable within a category
    rows.sort(key=lambda r: (r["rank"], r["k"]))
    out = []
    for i, r in enumerate(rows):
        out.append({
            "string_key": r["k"], "source_en": r["en"], "current_he": "",
            "context": r["ctx"], "section": r["cat"], "order_index": i,
        })

    dst = E / "ct_upload.json"
    dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    per = collections.Counter(r["section"] for r in out)
    print(f"rows {len(out)}  dropped(token/number/code-only) {dropped}  -> {dst}")
    for s, _rank in sorted({CAT_UI, CAT_DIALOGUE}, key=lambda t: t[1]):
        print(f"  {s:<20} {per.get(s, 0)}")

    ks = [r["string_key"] for r in out]
    assert len(ks) == len(set(ks)), "duplicate string_key"
    assert max(len(k.encode()) for k in ks) < 2000, "string_key too long for the index"
    print("string_key: unique, max len", max(len(k) for k in ks))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
