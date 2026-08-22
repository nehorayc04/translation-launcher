"""Extract interface/translate_<lang>.txt for every language Skyrim actually ships it in.

The UI table (main menu / settings / HUD) is a SEPARATE surface from the .STRINGS tables and
build_corpus.py never touched it beyond English. Skyrim ships it in 6 other languages -- NOT
Japanese (`translate_japanese.txt` does not exist in the BSA; the JP client falls back to
English for this surface). Written keyed by the raw `$key`, same convention as
`translate_txt.load()`, so the New-Era adapter can build the UI panel's reference languages.

out: extract/ui_langs/<lang>.json   {"$key": "value"}
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))

from bsa import Bsa            # noqa: E402
import translate_txt as TT     # noqa: E402

GAME = Path(os.environ.get("SKYRIM_GAME",
                           r"D:\Games\TES - Skyrim - Anniversary Edition"))
DATA = GAME / "Data"
OUT = ROOT / "extract" / "ui_langs"

LANGS = ("english", "french", "german", "italian", "spanish", "polish", "russian")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    found = {}
    for p in sorted(glob.glob(str(DATA / "*.bsa"))):
        try:
            b = Bsa(p)
        except Exception as e:                          # noqa: BLE001
            continue
        for f in b.files:
            if not f.path.startswith("interface/translate_"):
                continue
            lang = os.path.basename(f.path)[len("translate_"):-len(".txt")]
            if lang not in LANGS:
                continue
            found[lang] = TT.parse(b.read(f))
    for lang, entries in found.items():
        (OUT / f"{lang}.json").write_text(
            json.dumps(entries, ensure_ascii=False), encoding="utf-8")
        print(f"  {lang:<10} {len(entries)} keys")
    missing = [la for la in LANGS if la not in found]
    if missing:
        print(f"  (not shipped: {missing})")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
