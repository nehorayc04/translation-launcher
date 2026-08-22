#!/usr/bin/env python3
"""build_ct_strings.py — build the community /translate pool payload for GTA V.

Emits `extract/ct_strings.json` in the normalized shape
`universal/community_translate.py import gtav <file>` expects.

Key contract (CLAUDE.md §17 rule 4): `string_key` == the key the BUILD consumes.
`build_full_gxt2.load_translations()` is keyed by the **English source string**,
so the pool is keyed by it too -> an approved export is literally `hebrew.json`
and drops straight into the builder with ZERO glue.
  (Max EN length measured = 2,103 chars, under Postgres' ~2,704-byte btree index
   limit; the builder asserts on anything longer instead of failing the batch.)

Source of truth:
  * agent_handoff_full/occurrences.json  {EN: [[file, hash], ...]}  197,223 uniques
  * agent_handoff_full/skip.json         51,920 non-translatable (codes/URLs/labels)
  * build_full_gxt2.load_translations()  the SAME merge the bake uses -> pool and
                                         build can never disagree.

Hebrew is stored LOGICAL (contributors read/write logical); `visual_line` is
applied at BUILD time only.

Categories, ordered by VISIBILITY (CLAUDE.md §17 rule 5):
  1. ממשק ותפריטים  — anything present in global.gxt2 (menus/HUD/settings/names)
  2. כתוביות עלילה  — per-mission tables (objectives, help, cutscene text)
  3. דיבורי רקע     — *aud.gxt2 only (spoken conversation / ambient banter)

    python build_ct_strings.py            # write extract/ct_strings.json + report
"""
import json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_full_gxt2 as B  # noqa: E402  (reuse the bake's own translation merge)

GTAV = os.path.normpath(os.path.join(HERE, ".."))
AH = os.path.join(GTAV, "agent_handoff_full")
OUT_DIR = os.path.join(GTAV, "extract")
OUT = os.path.join(OUT_DIR, "ct_strings.json")

CAT_UI = "ממשק ותפריטים"
CAT_MISSION = "כתוביות עלילה"
CAT_AMBIENT = "דיבורי רקע"
CAT_ORDER = [CAT_UI, CAT_MISSION, CAT_AMBIENT]

MAX_KEY = 2400  # Postgres btree index headroom
LAT = re.compile("[A-Za-z]")
TOK = re.compile(r"~[^~]*~|</?[A-Za-z][^>]*>|%[0-9]*[sdifx%]|\[[A-Z_]+\]")


def is_translatable(en):
    """Belt-and-braces on top of skip.json: a row must still carry a real letter
    once the engine tokens are stripped (kills `~z~`-only / number-only rows)."""
    if not en or not en.strip():
        return False
    return bool(LAT.search(TOK.sub(" ", en)))


def category(files):
    if "global.gxt2" in files:
        return CAT_UI
    if all(f.endswith("aud.gxt2") for f in files):
        return CAT_AMBIENT
    return CAT_MISSION


def main():
    occ = json.load(open(os.path.join(AH, "occurrences.json"), encoding="utf-8"))
    skip = set(json.load(open(os.path.join(AH, "skip.json"), encoding="utf-8")))
    tr = B.load_translations()

    rows, dropped = [], collections.Counter()
    for en, places in occ.items():
        if en in skip:
            dropped["skip-list (codes/labels/URLs)"] += 1
            continue
        if not is_translatable(en):
            dropped["no real letter after tokens"] += 1
            continue
        if len(en) > MAX_KEY:
            dropped["over key length"] += 1
            continue
        files = sorted({f for f, _ in places})
        cat = category(files)
        shown = files[0] if len(files) == 1 else f"{files[0]} +{len(files) - 1}"
        ctx = f"{shown} · {len(places)} מופעים" if len(places) > 1 else shown
        # show what SHIPS: the bake strips the agent-added "(English)" glosses,
        # so the pool must too — otherwise contributors review text the game
        # never renders (and a re-import would re-seed the glosses).
        he = tr.get(en, "")
        if he:
            he = B.strip_gloss(he, en)
        rows.append({
            "en": en, "he": he, "section": cat,
            "context": ctx, "sort": (CAT_ORDER.index(cat), files[0], places[0][1]),
        })

    rows.sort(key=lambda r: r["sort"])
    out = [{
        "string_key": r["en"],          # == the build key (EN source)
        "source_en": r["en"],
        "current_he": r["he"],
        "context": r["context"],
        "section": r["section"],
        "order_index": i,
    } for i, r in enumerate(rows)]

    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

    per = collections.Counter(r["section"] for r in rows)
    done = collections.Counter(r["section"] for r in rows if r["he"])
    print(f"\npool rows: {len(out):,}   translated: {sum(done.values()):,}"
          f"   open: {len(out) - sum(done.values()):,}")
    for c in CAT_ORDER:
        print(f"  {c:<16} {per[c]:>7,}  translated {done[c]:>7,}")
    print("\ndropped:")
    for k, v in dropped.most_common():
        print(f"  {k:<32} {v:>7,}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
