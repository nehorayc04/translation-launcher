r"""Build the community `/translate` pool upload for FAR CRY 5.

Contract ([[community-pool-by-category]] + CLAUDE.md §17):

  * `string_key` = **`{sectionCRC:08x}:{id}`** — byte-identical to the key the BUILD consumes
    (`fc5_oasis.flat()` returns `(sectionCRC, id)` tuples, and `build_menu_he.PLAN` addresses
    lines by exactly that pair), so an approved export drops onto the build with no remapping.

  * **NO dedup by English.** Measured on this corpus: 31,664 records / 25,095 unique EN /
    2,300 duplicate-EN groups — and **27% of those groups get DIFFERENT translations in the
    game's OWN professional Arabic AND French AND 35% in Russian**. The divergence is real and
    contextual (`US Auto` -> `Garage US Auto` on the map but `US Auto` in the shop;
    `Gardenview Packing Facility` -> a shortened form where the label is width-limited), so a
    dedup would collapse a quarter of them onto one wrong Hebrew.

  * `section` = the Hebrew VISIBILITY category, contiguous `order_index` blocks so a partial
    pass covers what players see first.

  * `context` carries the game's OWN **Arabic** for every line ([[gender-oracle-from-game-langs]]) —
    English drops the gender Hebrew needs, and FC5 ships Arabic at 100% key parity, stored
    LOGICAL with 0 presentation forms (verified), so it is readable as-is. An auto-hint
    (`נמען=נקבה/רבים`) is added ONLY where `ar_addressee_strict` is unambiguous
    ([[gender-hint-needs-closed-set]]).

    python build_ct_strings.py            -> extract/ct_upload.json (+ report)
"""
import sys
import os
import re
import json
import collections

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, os.path.join(ROOT, "universal"))

from fc5_fat import Fat                       # noqa: E402
from fc5_crc64 import name_hash               # noqa: E402
import fc5_oasis as O                         # noqa: E402
from gender_oracle import ar_addressee_strict  # noqa: E402

GAME = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
PC = os.path.join(GAME, "data_final", "pc")
OUT = os.path.join(HERE, "..", "extract")
UI = "languages/{lang}/oasisstrings.oasis.bin"
SUB = "languages/{lang}/oasisstrings_subtitles.oasis.bin"

# --- what counts as an engine TOKEN --------------------------------------------------------
# `[STYLE_ZETA_{0}]` / `[ACTION_PLANE_SHOOT]` / `[Quest_Generic]` are tokens; `[heavy sigh]`
# and `[coughing while getting up in the middle of debris]` are STAGE DIRECTIONS the player
# reads. Stripping every bracket would report those lines as empty and silently drop them
# (the AC2 lesson: an overloaded bracket syntax makes a structural filter delete content).
_TOKEN_BR = re.compile(r"\[[A-Za-z0-9_.\-{}]+\]")
_BRACE = re.compile(r"\{[^}]{0,60}\}")
_TAG = re.compile(r"<[^>]{0,60}>")
_SPEC = re.compile(r"%[-+ #0-9.]*[a-zA-Z]")
_ENT = re.compile(r"&[a-zA-Z#0-9]{1,10};")


def visible(s):
    """The text a player actually reads, with engine tokens removed."""
    for rx in (_TOKEN_BR, _BRACE, _TAG, _SPEC, _ENT):
        s = rx.sub(" ", s)
    return s


def translatable(en):
    """Drop rows with no real word once the tokens are gone — weapon model codes (`M60`,
    `A.J.M.9`, `P226`), pure icon rows, empty strings. A name/code passthrough is a
    TRANSLATOR decision, so anything with a real word stays in."""
    return bool(re.search(r"[A-Za-z]{2,}", visible(en)))


def junk(en):
    """`(PH) …` are dev placeholders that never render — the game's own Arabic leaves 94% of
    them byte-identical to the English, which is the signal that they are not content."""
    s = en.strip()
    return s.startswith("(PH)") or s in ("ENTER_TEXT_HERE", "TBD", "TODO")


# --- categories, in VISIBILITY order --------------------------------------------------------
UI_SHORT, QUEST, SUBS, UI_LONG = (
    "ממשק ותפריטים", "משימות ויעדים", "כתוביות עלילה", "תיאורים ופריטים")
CAT_ORDER = [UI_SHORT, QUEST, SUBS, UI_LONG]
SHORT_MAX = 40          # stripped chars — a label/button vs a description/lore block


def categorise(en, is_sub):
    if is_sub:
        return SUBS
    if "[Quest_" in en:
        return QUEST
    return UI_SHORT if len(visible(en).strip()) <= SHORT_MAX else UI_LONG


def load(arch, lang, rel):
    f = Fat(os.path.join(PC, arch))
    e = f.by_hash.get(name_hash(rel.format(lang=lang)))
    return O.flat(O.parse(f.read_data(e))[1]) if e else {}


def effective(lang, rel):
    """patch.fat OVERRIDES common.fat — the union with patch winning is what the engine
    resolves ([[patch-every-copy-verify-winner]])."""
    m = load("common.fat", lang, rel)
    m.update(load("patch.fat", lang, rel))
    return m


def main():
    en_ui = effective("english", UI)
    en_sub = effective("english", SUB)
    ar = effective("arabic", UI)
    ar.update(effective("arabic", SUB))
    print(f"english: ui={len(en_ui):,}  subs={len(en_sub):,}  "
          f"overlap={len(set(en_ui) & set(en_sub))}")
    print(f"arabic : {len(ar):,}  covers {len(set(ar) & (set(en_ui) | set(en_sub))):,} of the "
          f"english keys")

    rows_by_cat = collections.defaultdict(list)
    dropped = collections.Counter()
    for src, is_sub in ((en_ui, False), (en_sub, True)):
        for (sec, sid), en in src.items():
            if junk(en):
                dropped["dev placeholder"] += 1
                continue
            if not translatable(en):
                dropped["no real word (code/icon/empty)"] += 1
                continue
            rows_by_cat[categorise(en, is_sub)].append((f"{sec:08x}:{sid}", en, (sec, sid)))

    hinted = 0
    rows, idx = [], 0
    for cat in CAT_ORDER:
        for key, en, k in sorted(rows_by_cat[cat], key=lambda r: r[0]):
            a = ar.get(k, "")
            ctx = a
            g = ar_addressee_strict(a) if a else None
            if g in ("f", "pl", "m"):
                ctx = a + "  ·  נמען=" + {"f": "נקבה", "pl": "רבים", "m": "זכר"}[g]
                hinted += 1
            rows.append({"string_key": key, "source_en": en, "current_he": "",
                         "context": ctx, "section": cat, "order_index": idx})
            idx += 1

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "ct_upload.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

    print(f"\n=== ct_upload.json : {len(rows):,} rows ===")
    for cat in CAT_ORDER:
        n = len(rows_by_cat[cat])
        print(f"  {cat:16s} {n:>7,}")
    for k, v in dropped.most_common():
        print(f"  dropped: {k:32s} {v:>6,}")
    ln = [len(r["source_en"]) for r in rows]
    print(f"  chars {sum(ln):,}  median {sorted(ln)[len(ln) // 2]}  max {max(ln):,}")
    print(f"  arabic gender source on {sum(1 for r in rows if r['context']):,} rows, "
          f"auto-hint on {hinted:,}")
    print(f"  unique EN {len({r['source_en'] for r in rows}):,} "
          f"(NOT deduped — the pro localisations diverge on 27% of duplicates)")
    print(f"\nwrote {path}")
    print("next: python universal/community_translate.py import farcry5 "
          "games/farcry5/extract/ct_upload.json")


if __name__ == "__main__":
    main()
