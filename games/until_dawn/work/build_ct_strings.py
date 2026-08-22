#!/usr/bin/env python3
r"""
build_ct_strings.py - extract the Until Dawn EN corpus from the live pak and
emit the community `/translate` upload file.

The single StringTable namespace `ST_Localized` in en/Game.locres holds ALL
text (UI, story dialogue, making-of captions), classified here by key-name
prefix into three Hebrew visibility categories (per the community-pool-by-
category rule). string_key = the raw game key (unique per row → maps back
1:1 at Phase-2 build, source_en+current_he both from the same authoritative
locres so no mis-pairing). current_he='' (fresh game).

Light filter: drop no-letter / pure-timestamp / settings-value junk and the
single `.HOWTO` developer note.

Outputs (games/until_dawn/):
  extract/en.json           {key: en}   raw authoritative English
  extract/ct_upload.json    the /translate upload  [{string_key, source_en,
                            current_he:"", section:<Hebrew category>, context, order_index}]
  extract/report.txt        counts

    python build_ct_strings.py
"""
import os
import re
import sys
import json
import subprocess
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import ud_locres as L  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPAK = os.path.join(HERE, "..", "..", "hogwarts_legacy", "tools", "repak.exe")
GAME_PAK = r"F:\Games\Until Dawn\Windows\Bates\Content\Paks\Bates-Windows.pak"
EN_REL = "Bates/Content/Localization/Game/en/Game.locres"
EXTRACT = os.path.join(HERE, "..", "extract")
CACHE_EN = os.path.join(HERE, "_proof_cache", "en_Game.locres")

# raw category -> Hebrew community category (shown on the /translate site).
# Ordered UI -> story -> bonus (most-leverage/most-visible first).
CAT_UI = "ממשק ותפריטים"
CAT_STORY = "כתוביות עלילה"
CAT_BONUS = "חומרי רקע (מאחורי הקלעים)"
CAT_ORDER = {CAT_UI: 0, CAT_STORY: 1, CAT_BONUS: 2}

_JUNK_VALUE = [
    re.compile(r'^\s*\d{2,5}\s*[xX×]\s*\d{2,5}\s*(\(.*\))?\s*$'),   # 1920x1080
    re.compile(r'^\s*\d+\s*FPS\s*$', re.I),
    re.compile(r'^\s*\d+\s*Hz\s*$', re.I),
    re.compile(r'^\s*\d+\s*:\s*\d+\s*$'),                          # 16:9 aspect / 19:11 time
    re.compile(r'^\s*\d+\s*%\s*$'),
    re.compile(r'^\s*[-+]?\d+([.,]\d+)?\s*$'),
    re.compile(r'^\s*\d+([.,]\d+)?\s*(ms|px|dpi|GB|MB|KB|nits?|bit|K|p)\s*$', re.I),
]


def has_letter(s):
    return any(c.isalpha() for c in s)


def is_translatable(key, val):
    if key == ".HOWTO":                       # developer note, not game text
        return False
    if not val.strip() or not has_letter(val):
        return False
    if any(p.match(val) for p in _JUNK_VALUE):
        return False
    return True


def category(key):
    if re.match(r'^SMG\d+_\d+', key) or key.startswith("epilogue_"):
        return CAT_STORY
    if key.startswith("Bonus_Material") or key.startswith("bts_video"):
        return CAT_BONUS
    return CAT_UI          # BATES_*, PSPC_*, BM_*, msgid_*, PC_LOADING, misc


def _repak_get(rel, out):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        r = subprocess.run([REPAK, "get", GAME_PAK, rel], stdout=f, stderr=subprocess.PIPE)
    if r.returncode != 0:
        sys.exit(f"repak get failed: {r.stderr.decode(errors='replace')}")


def main():
    os.makedirs(EXTRACT, exist_ok=True)
    if not os.path.isfile(CACHE_EN):
        _repak_get(EN_REL, CACHE_EN)
    parsed = L.load(CACHE_EN)

    en_map = {}
    for ns in parsed["namespaces"]:
        for e in ns["entries"]:
            en_map[e["key"]] = e["value"]
    with open(os.path.join(EXTRACT, "en.json"), "w", encoding="utf-8") as f:
        json.dump(en_map, f, ensure_ascii=False)

    upload = []
    dropped = 0
    # order by (category rank, then original locres order) so UI-first
    ordered = sorted(en_map.items(), key=lambda kv: CAT_ORDER[category(kv[0])])
    idx = 0
    for key, en in ordered:
        if not is_translatable(key, en):
            dropped += 1
            continue
        cat = category(key)
        upload.append({
            "string_key": key,
            "source_en": en,
            "current_he": "",
            "section": cat,
            "context": key,          # raw game key (SMG### = story, BATES_ = UI)
            "order_index": idx,
        })
        idx += 1

    with open(os.path.join(EXTRACT, "ct_upload.json"), "w", encoding="utf-8") as f:
        json.dump(upload, f, ensure_ascii=False)

    cats = Counter(r["section"] for r in upload)
    lines = ["Until Dawn (2024) - EN corpus for /translate", "=" * 44,
             f"total locres entries:  {len(en_map)}",
             f"kept (translatable):   {len(upload)}",
             f"dropped (junk/note):   {dropped}", "-" * 44]
    for c in sorted(cats, key=lambda x: CAT_ORDER[x]):
        lines.append(f"  {c}: {cats[c]}")
    rep = "\n".join(lines)
    with open(os.path.join(EXTRACT, "report.txt"), "w", encoding="utf-8") as f:
        f.write(rep + "\n")
    print(rep)
    print(f"\n-> extract/ct_upload.json ({len(upload)} rows)")


if __name__ == "__main__":
    main()
