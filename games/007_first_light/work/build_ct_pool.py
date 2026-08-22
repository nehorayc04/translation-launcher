"""
build_ct_pool.py — categorise the 007 corpus by VISIBILITY and build the community /translate
upload file (dedup-by-EN, md5 key — the TLOU2 pattern).

Categories (most-visible -> least):
  ממשק ותפריטים   UI / menus / HUD            (LOCR)
  כתוביות עלילה    story dialogue subtitles    (DLGE, named speakers)
  דיבורי רקע       ambient / combat barks      (DLGE, generic coded NPCs)
"""
import os, sys, re, json, hashlib, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRACT = os.path.join(HERE, "..", "extract")

CAT_UI = "ממשק ותפריטים"
CAT_STORY = "כתוביות עלילה"
CAT_BARK = "דיבורי רקע"
ORDER = {CAT_UI: 0, CAT_STORY: 1, CAT_BARK: 2}

# generic crowd/combat NPC speaker codes (SECUKM02, MERCUKM03, SECEEM03, MERCMRM04, ...) => bark
_GENERIC = re.compile(r"\d")


def is_bark(speaker):
    return bool(speaker) and bool(_GENERIC.search(speaker))


def key_of(en):
    return "en:" + hashlib.md5(en.encode("utf-8")).hexdigest()


def main():
    locr = json.load(open(os.path.join(EXTRACT, "locr_en.json"), encoding="utf-8"))
    dlge = json.load(open(os.path.join(EXTRACT, "dlge_en.json"), encoding="utf-8"))

    # per-EN category (priority: UI > story > bark) + a representative context
    cat = {}         # en -> category
    ctx = {}         # en -> context hint
    ui_total = story_total = bark_total = 0

    for en in locr.values():
        ui_total += 1
        if en not in cat:
            cat[en] = CAT_UI
            ctx[en] = "ממשק"

    for d in dlge:
        en = d["en"]
        c = CAT_BARK if is_bark(d["speaker"]) else CAT_STORY
        if c == CAT_BARK:
            bark_total += 1
        else:
            story_total += 1
        cur = cat.get(en)
        if cur is None or ORDER[c] < ORDER[cur]:
            cat[en] = c
            ctx[en] = f"דובר: {d['speaker']}" if d["speaker"] else "כתובית"

    # build upload rows (one per unique EN)
    rows = []
    for en, c in cat.items():
        rows.append({
            "string_key": key_of(en),
            "source_en": en,
            "current_he": "",
            "section": c,
            "context": ctx.get(en, ""),
            "order_index": ORDER[c],
        })
    rows.sort(key=lambda r: (r["order_index"], r["source_en"]))
    json.dump(rows, open(os.path.join(EXTRACT, "ct_upload.json"), "w", encoding="utf-8"),
              ensure_ascii=False)

    # unique-by-category counts
    uc = collections.Counter(r["section"] for r in rows)
    print("=== 007 First Light — line counts by category (visible -> not) ===\n")
    print(f"{'קטגוריה':<20} {'סה\"כ (raw)':>12} {'ייחודי (pool)':>14}")
    print(f"{CAT_UI:<20} {ui_total:>12} {uc[CAT_UI]:>14}   ← ממשק, הכי נראה")
    print(f"{CAT_STORY:<20} {story_total:>12} {uc[CAT_STORY]:>14}   ← כתוביות עלילה")
    print(f"{CAT_BARK:<20} {bark_total:>12} {uc[CAT_BARK]:>14}   ← דיבורי רקע, הכי פחות נראה")
    print(f"{'—'*46}")
    tot_raw = ui_total + story_total + bark_total
    print(f"{'TOTAL':<20} {tot_raw:>12} {len(rows):>14}")
    print(f"\nupload file: extract/ct_upload.json  ({len(rows)} unique rows)")


if __name__ == "__main__":
    main()
