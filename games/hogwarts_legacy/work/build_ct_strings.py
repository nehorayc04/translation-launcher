#!/usr/bin/env python3
"""Build the community `/translate` pool file for Hogwarts Legacy.

Reads the extracted EN corpus (`extract/main_en.json` + `extract/sub_en.json`,
produced by the recon extraction) and emits `extract/ct_strings.json`, the
normalized array `universal/community_translate.py import hogwarts` expects:
  [{"string_key","source_en","current_he","context","section","order_index"}, ...]

Key routing: MAIN and SUB share NO keys (verified 0 overlap), but the build/apply
step needs to know which .bin a key belongs to, so string_key is prefixed
`MAIN:<key>` / `SUB:<key>` (section carries the same info; the Phase-2 apply
strips the prefix). current_he='' — no existing Hebrew (fresh game).

Light filter only (the user asked to upload ALL lines): drop a source with no
alphabetic character at all (pure numbers/symbols/empty — untranslatable).
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTRACT = HERE.parent / "extract"

# Non-translatable VALUE patterns (settings values that stay identical in any language).
_JUNK_VALUE = [
    re.compile(r'^\s*\d{2,5}\s*[xX×]\s*\d{2,5}\s*(\(.*\))?\s*$'),  # resolution 1920x1080 [ (4K) ]
    re.compile(r'^\s*\d+\s*FPS\s*$', re.I),                             # 120 FPS
    re.compile(r'^\s*\d+\s*Hz\s*$', re.I),                              # 60 Hz
    re.compile(r'^\s*\d+\s*:\s*\d+\s*$'),                               # 16:9 aspect
    re.compile(r'^\s*\d+\s*%\s*$'),                                     # 100%
    re.compile(r'^\s*[-+]?\d+([.,]\d+)?\s*$'),                          # bare number
    re.compile(r'^\s*\d+([.,]\d+)?\s*(ms|px|dpi|GB|MB|KB|nits?|bit|K|p)\s*$', re.I),
]
# NOTE: the `cbi_Keyboard_*_Pronunciation` accessibility block (194 key-name TTS strings —
# "Backspace"/"Left arrow"/…) is INTENTIONALLY KEPT (user decision 2026-07-04): they are real
# translatable words, so they stay in the pool. Only settings VALUES identical in every language
# are dropped (see _JUNK_VALUE).


def has_letter(s: str) -> bool:
    return any(c.isalpha() for c in s)


def is_translatable(key: str, val: str) -> bool:
    if not val.strip() or not has_letter(val):
        return False
    if any(p.match(val) for p in _JUNK_VALUE):
        return False
    return True


def build():
    main_en = json.loads((EXTRACT / "main_en.json").read_text(encoding="utf-8"))
    sub_en = json.loads((EXTRACT / "sub_en.json").read_text(encoding="utf-8"))

    rows = []
    dropped = 0
    idx = 0
    for section, data in (("MAIN", main_en), ("SUB", sub_en)):
        for key, en in data.items():
            en = en if isinstance(en, str) else ""
            if not is_translatable(key, en):
                dropped += 1
                continue
            rows.append({
                "string_key": f"{section}:{key}",
                "source_en": en,
                "current_he": "",
                "context": key,        # raw game key (SUB keys encode the speaker)
                "section": section,
                "order_index": idx,
            })
            idx += 1

    out = EXTRACT / "ct_strings.json"
    out.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    n_main = sum(1 for r in rows if r["section"] == "MAIN")
    n_sub = sum(1 for r in rows if r["section"] == "SUB")
    print(f"MAIN kept {n_main} / {len(main_en)}")
    print(f"SUB  kept {n_sub} / {len(sub_en)}")
    print(f"dropped (no-letter/empty): {dropped}")
    print(f"total rows: {len(rows)} -> {out}")


if __name__ == "__main__":
    build()
