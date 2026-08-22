"""Build the community /translate pool upload for R&C Rift Apart.

Reuses the EXACT classify() from 10_counts_ui_vs_subtitle.py (so the pool matches
the reported UI 7,521 / subtitles 10,033 / skip 7,021 = 17,554 translatable), then
buckets into Hebrew categories ordered by VISIBILITY ([[community-pool-by-category]]):

  1. ממשק ותפריטים   — UI the player reads every session (menus/HUD/items/objectives)
  2. כתוביות עלילה   — spoken VO/cutscene lines (the <ts="a;b"> timed marker)
  3. קרדיטים          — the credit roll (mostly proper names, lowest priority)

Contract notes:
  • string_key = the RAW loc key (unique per entry) → an approved export maps
    straight back onto the build with no indirection.
  • source_en + current_he come from the SAME variant_00 mapping (current_he=''
    — R&C has no existing Hebrew) → the WD2 mis-pairing trap cannot occur.
  • context = speaker name for subtitles (resolved via NAME_SUBTITLE_<prefix>) —
    real, closed-set context; NO auto-derived gender hint ([[gender-hint-needs-closed-set]]).
  • order_index = category rank first, so a partial pass covers what players see.

Output: extract/ct_upload.json  (+ a summary printed).
"""
import os, sys, io, json, struct, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "games", "spiderman2", "tools", "ALERT"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import dat1lib, dat1lib.types.dat1

SRC = os.path.join(HERE, "..", "extracted", "loc_variants", "variant_00_idx87375.localization")
OUT = os.path.join(HERE, "..", "extract", "ct_upload.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# reuse the exact classifier used for the count report
spec = importlib.util.spec_from_file_location("rc_counts", os.path.join(HERE, "10_counts_ui_vs_subtitle.py"))
_c = importlib.util.module_from_spec(spec)
_c.__dict__["__RUN_MAIN__"] = False
try:
    spec.loader.exec_module(_c)          # it prints its report; harmless
except SystemExit:
    pass
classify, prefix = _c.classify, _c.prefix

TAG_VALUES, TAG_KEYS = 0x70A382B8, 0x4D73CEBD
TAG_TEXT_OFFSETS, TAG_KEY_OFFSETS, TAG_ENTRY_COUNT = 0xF80DEEB4, 0xA4EA55B2, 0xD540A903

raw = open(SRC, "rb").read(); pay = raw[36:]
d = dat1lib.types.dat1.DAT1(io.BytesIO(pay), None)
secs = {sh.tag:(sh.offset, sh.size) for sh in d.header.sections}
def sb(t): o,s = secs[t]; return pay[o:o+s]
cnt = struct.unpack("<I", sb(TAG_ENTRY_COUNT))[0]
kb, vb = sb(TAG_KEYS), sb(TAG_VALUES)
ko = list(struct.unpack(f"<{cnt}I", sb(TAG_KEY_OFFSETS)))
to = list(struct.unpack(f"<{cnt}I", sb(TAG_TEXT_OFFSETS)))
def cs(b,o): e=b.find(b"\x00",o); return b[o:(e if e>=0 else len(b))]

pairs = {}
for i in range(cnt):
    k = cs(kb,ko[i]).decode("utf-8","replace")
    v = cs(vb,to[i]).decode("utf-8","replace")
    if k and k not in pairs:
        pairs[k] = v

# speaker map: NAME_SUBTITLE_<PREFIX> -> display name (real in-game context)
speakers = {k[len("NAME_SUBTITLE_"):]: v for k, v in pairs.items()
            if k.startswith("NAME_SUBTITLE_") and v.strip()}

CAT_UI, CAT_SUB, CAT_CRED = "ממשק ותפריטים", "כתוביות עלילה", "קרדיטים"
CAT_ORDER = [CAT_UI, CAT_SUB, CAT_CRED]

# ⚠️ For the POOL we use a STRICTER subtitle rule than the count report's shape
# heuristic. "long prose" mis-routes long UI text (legal notices, activity-card and
# settings descriptions) into "subtitles", which would hand the translator a spoken
# register for legal text. R&C ships its own authoritative closed set of VO speakers
# (NAME_SUBTITLE_<PREFIX>), so: subtitle ⇔ the <ts="a;b"> timing tag OR a speaker
# prefix. Everything else is UI. (Uses the game's own data, not a length guess.)
TS = _c.TS_TAG
rows, stats = [], {c: 0 for c in CAT_ORDER}
skipped = 0
for k, v in pairs.items():
    cls = classify(k, v)
    if cls == "skip":
        skipped += 1
        continue
    p = prefix(k)
    if p == "CREDITS":
        cat = CAT_CRED
    elif TS.search(v) or p in speakers:
        cat = CAT_SUB
    else:
        cat = CAT_UI
    ctx = ""
    if cat == CAT_SUB and p in speakers:
        ctx = f"דובר: {speakers[p]}"
    elif cat == CAT_CRED:
        ctx = "רשימת יוצרים — שמות פרטיים נשארים באנגלית"
    rows.append({"string_key": k, "source_en": v, "current_he": "",
                 "context": ctx, "section": cat, "_cat": cat})
    stats[cat] += 1

# order by visibility: category rank, then key (stable)
rank = {c: i for i, c in enumerate(CAT_ORDER)}
rows.sort(key=lambda r: (rank[r["_cat"]], r["string_key"]))
for i, r in enumerate(rows):
    r["order_index"] = i
    del r["_cat"]

json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n=== community pool upload built ===")
for c in CAT_ORDER:
    print(f"  {c:16} {stats[c]:6}")
print(f"  {'skip (not uploaded)':16} {skipped:6}")
print(f"  {'TOTAL rows':16} {len(rows):6}  -> {OUT}")
print(f"\n  with speaker context: {sum(1 for r in rows if r['context'].startswith('דובר'))}")
print(f"  sample UI : {rows[0]['string_key']} = {rows[0]['source_en'][:60]!r}")
_s = next(r for r in rows if r['section']==CAT_SUB)
print(f"  sample SUB: {_s['string_key']} = {_s['source_en'][:60]!r}  ctx={_s['context']}")
