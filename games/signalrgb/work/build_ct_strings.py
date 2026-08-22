# -*- coding: utf-8 -*-
"""Build the community /translate pool payload for SignalRGB.

Three surfaces, one pool.  `string_key` carries its TARGET SURFACE as a prefix
so an approved export maps straight back onto the right build file:

    ui:<context\\x1fsource\\x1fcomment>   the app UI (.qm), keyed as the build consumes it
    macro:<english>                       a Macroscripts Name/Description/label
    plugin:<english>                      a device-plugin label

`section` is the HEBREW category (the DB trigger passes a Hebrew section through
to `category` verbatim), ordered by VISIBILITY.  `current_he` is seeded with the
value the app really renders (the CLEAN hebrew.json, no layout NBSP).

    python work/build_ct_strings.py
    python universal/community_translate.py import signalrgb extract/ct_upload.json
"""
from __future__ import annotations
import json, os, sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import build_handoff as BH   # reuse the exact visibility buckets

UI_HE = json.load(open(os.path.join(ROOT, "agent_handoff", "hebrew.json"), encoding="utf-8"))
UI_SRC = json.load(open(os.path.join(ROOT, "agent_handoff", "to_translate.json"), encoding="utf-8"))
MACRO = json.load(open(os.path.join(HERE, "macros_he.json"), encoding="utf-8"))
PLUGIN = json.load(open(os.path.join(HERE, "plugins_he.json"), encoding="utf-8"))

# visibility bucket (1,2) -> UI menus ; 3 -> descriptions ; 4 -> dev
CAT_UI_CORE = "ממשק ותפריטים"
CAT_UI_DESC = "תיאורים והודעות"
CAT_UI_DEV = "כלי פיתוח"
CAT_MACRO = "מאקרו"
CAT_PLUGIN = "הגדרות התקנים"


def ui_category(key):
    ctx = UI_SRC.get(key, {}).get("context", "")
    b = BH.bucket(ctx)
    return CAT_UI_CORE if b in (1, 2) else (CAT_UI_DEV if b == 4 else CAT_UI_DESC)


def main():
    rows = []
    # ---- UI (.qm) ----
    for key, he in UI_HE.items():
        src = UI_SRC.get(key)
        en = src["en"] if src else key.split("\x1f")[1]
        rows.append({
            "string_key": "ui:" + key,
            "source_en": en,
            "current_he": he,
            "section": ui_category(key),
        })
    # ---- Macros ----
    for en, he in MACRO.items():
        rows.append({"string_key": "macro:" + en, "source_en": en,
                     "current_he": he, "section": CAT_MACRO})
    # ---- device plugins ----
    for en, he in PLUGIN.items():
        rows.append({"string_key": "plugin:" + en, "source_en": en,
                     "current_he": he, "section": CAT_PLUGIN})

    # order by visibility, and assert keys are unique + within the btree limit
    ORDER = [CAT_UI_CORE, CAT_MACRO, CAT_PLUGIN, CAT_UI_DESC, CAT_UI_DEV]
    rows.sort(key=lambda r: (ORDER.index(r["section"]), r["source_en"].lower()))
    seen = set()
    for r in rows:
        assert r["string_key"] not in seen, "dup key: " + r["string_key"]
        seen.add(r["string_key"])
        assert len(r["string_key"].encode("utf-8")) < 2400, "key too long"

    out = os.path.join(ROOT, "extract", "ct_upload.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(rows, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    import collections
    c = collections.Counter(r["section"] for r in rows)
    print("total rows :", len(rows))
    for cat in ORDER:
        print("  %-20s %d" % (cat, c[cat]))
    print("wrote      :", out)


if __name__ == "__main__":
    main()
