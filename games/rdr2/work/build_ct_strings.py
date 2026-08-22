#!/usr/bin/env python3
r"""build_ct_strings.py — emit the RDR2 corpus as the community `/translate` upload.

Source of truth = `extract/en_corpus.json` (217,758 keys that have real English, joined from
the public hash-keyed dump via joaat(label); see FEASIBILITY.md). `string_key` is the Ko Games
LML key VERBATIM, so an approved line drops straight back into the override file at build time
with no remapping — the contract the pool requires.

Categories (`section`) are Hebrew and ordered by VISIBILITY, per the community-pool rule: a
partial pass must cover what players actually see. Ambient barks are the biggest bucket by far
(148k) and the least valuable per line, so they sort near the end; RDR Online sorts last since
a story-complete ship can skip it entirely.

GENDER: English drops the gender Hebrew needs, so every line carries the game's OWN Arabic in
`context` as the source a translator reads (Ko Games' professional Arabic ≈ Hebrew: أنتَ/أنتِ =
אתה/את). It is stored VISUAL + presentation-form, so it is NFKC-normalized and re-reversed to
logical order first. A short auto-hint (`נמען=נקבה/רבים`) is added ONLY where
`gender_oracle.ar_addressee_strict` is unambiguous — a closed set of pronouns/suffixes — because
a WRONG hint creates exactly the debt it exists to prevent.

    python build_ct_strings.py            (writes extract/ct_upload.json + report)
"""
import json
import os
import re
import sys
import unicodedata
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXTRACT = os.path.join(HERE, "..", "extract")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "universal"))
import rdr2_text as R                                   # noqa: E402
from gender_oracle import ar_addressee_strict           # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KO_GXT = os.path.join(
    os.environ.get("TEMP", r"C:\Users\NEHORA~1\AppData\Local\Temp"),
    "claude", "c--Users-Nehoray-Cohen-Projects-Game-translator",
    "e3138fa7-c56d-480e-a61b-3e5631a67d96", "scratchpad", "rdr2_ref",
    "lml", "tranar", "Ko Games Studio.gxt2")

CAT_UI     = "ממשק ותפריטים"
CAT_ITEMS  = "פריטים וציוד"
CAT_STORY  = "כתוביות עלילה"
CAT_DOCS   = "מסמכים ותוכן נוסף"
CAT_BARKS  = "דיבורי רקע"
CAT_ONLINE = "תוכן מקוון (RDR Online)"
CAT_ORDER = {CAT_UI: 0, CAT_ITEMS: 1, CAT_STORY: 2, CAT_DOCS: 3, CAT_BARKS: 4, CAT_ONLINE: 5}

# key prefixes -> category. Checked in order; first match wins.
UI_PREFIX = ("PM_", "PMNU", "PMHELP", "PMPLAYER", "UI_", "TITLE_", "MENU_", "PAUSE_", "SETTING",
             "OPT_", "HUD_", "FE_", "SP_MENU", "HELP_", "TUT_", "HINT_", "TIP_", "CTRL_",
             "INPUT_", "ACT_", "MISSION_", "OBJ_", "GUIDE_", "JOURNAL", "QUEST", "LEGAL_",
             "WARNING_", "ALERT_", "EXIT_", "SG_", "REPLAY_", "CHAPTER_", "MC_", "BLIP",
             "MAP", "AWARD", "SHORTDESC", "CHAR_")
ITEM_PREFIX = ("CLOTHING", "PROVISION", "HORSE", "COMPONENT", "CONSUMABLE", "WEAPON", "CATALOG",
               "ITEM_", "SHOP", "WHEEL_", "SATCHEL", "AMMO_", "SADDLE", "TONIC", "PELT", "CRAFT",
               "TF_", "CMPNDM")
DOC_PREFIX = ("DOCUMENT", "SPEAKER", "FETCH", "DISCOVERABLE", "NM_", "MO_", "GFH", "POS", "PRES",
              "MGPKR", "W_")
ONLINE_PREFIX = ("MP", "MPAC", "MPGC", "MPPT", "NET", "FME", "PXPT", "MPHUD", "MPMENU", "NG_")

_TOKEN = re.compile(r"~[^~]*~")


def strip_tokens(v):
    return _TOKEN.sub("", v)


def has_letter(s):
    return any(c.isalpha() for c in s)


def is_translatable(key, val):
    """Drop only what genuinely cannot be translated: no letters at all (pure numbers, symbols,
    token-only strings) or empty. Everything with a real word is kept — a name/code passthrough
    is a TRANSLATOR decision, not ours."""
    core = strip_tokens(val).strip()
    return bool(core) and has_letter(core)


def _first_prefix(key, prefixes):
    return any(key.startswith(p) for p in prefixes)


def category(key, val):
    is_hash = key.startswith("0x")
    if not is_hash and _first_prefix(key, ONLINE_PREFIX):
        return CAT_ONLINE
    if "~z~" in val:                       # spoken line
        return CAT_STORY if "~sl:" in val else CAT_BARKS
    if not is_hash:
        if _first_prefix(key, UI_PREFIX):
            return CAT_UI
        if _first_prefix(key, ITEM_PREFIX):
            return CAT_ITEMS
        if _first_prefix(key, DOC_PREFIX):
            return CAT_DOCS
    return CAT_DOCS                        # hash-only + unclassified content


def to_logical_arabic(v):
    """Ko Games' Arabic is stored VISUAL + presentation-form. Reverse it back to readable
    logical order.

    ⚠️ Each ~n~/~sl: SEGMENT must be reversed on its OWN, with segment order preserved.
    Stripping the tokens first and reversing the whole string concatenates the segments and
    flips their order, so a two-part subtitle comes out with its second half first (seen on
    `045_EXIT_DAY_1`). Same rule as the build path (`rdr2_rtl._SEP`), for the same reason.
    """
    parts = re.split(r"(~n~|~sl:[^~]*~)", v)
    segs = [p for p in parts if p and not re.fullmatch(r"~n~|~sl:[^~]*~", p)]
    out = []
    for s in segs:
        s = unicodedata.normalize("NFKC", strip_tokens(s)).strip()
        if s:
            out.append(s[::-1])
    return " ".join(out)


def load_arabic():
    if not os.path.isfile(KO_GXT):
        print(f"WARNING: Ko Games Arabic not found at {KO_GXT} — no gender source", file=sys.stderr)
        return {}
    raw = R.to_map(R.parse(open(KO_GXT, encoding="utf-8").read()))
    out = {}
    for k, v in raw.items():
        lg = to_logical_arabic(v)
        if lg:
            out[k] = lg
    return out


def main():
    with open(os.path.join(EXTRACT, "en_corpus.json"), encoding="utf-8") as f:
        en = json.load(f)
    ar = load_arabic()

    rows, dropped, hinted, with_ar = [], 0, 0, 0
    ordered = sorted(en.items(), key=lambda kv: (CAT_ORDER[category(*kv)], kv[0]))
    idx = 0
    for key, val in ordered:
        if not is_translatable(key, val):
            dropped += 1
            continue
        ctx = [f"מפתח: {key}"]
        a = ar.get(key, "")
        if a:
            with_ar += 1
            g = ar_addressee_strict(a)
            if g:
                hinted += 1
                ctx.append("נמען=" + {"f": "נקבה", "m": "זכר", "pl": "רבים"}.get(g, g))
            ctx.append("ערבית (מקור מגדר): " + a[:220])
        rows.append({
            "string_key": key,
            "source_en": val,
            "current_he": "",
            "section": category(key, val),
            "context": " · ".join(ctx),
            "order_index": idx,
        })
        idx += 1

    out = os.path.join(EXTRACT, "ct_upload.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)

    cats = Counter(r["section"] for r in rows)
    lines = ["Red Dead Redemption 2 — EN corpus for /translate", "=" * 50,
             f"corpus entries with English : {len(en):>7,}",
             f"kept (translatable)         : {len(rows):>7,}",
             f"dropped (no letters at all) : {dropped:>7,}",
             f"with Arabic gender source   : {with_ar:>7,}",
             f"with auto gender hint       : {hinted:>7,}", "-" * 50]
    for c in sorted(cats, key=lambda x: CAT_ORDER[x]):
        lines.append(f"  {CAT_ORDER[c]}. {c}: {cats[c]:,}")
    rep = "\n".join(lines)
    with open(os.path.join(EXTRACT, "ct_report.txt"), "w", encoding="utf-8") as f:
        f.write(rep + "\n")
    print(rep)
    print(f"\n-> {out} ({len(rows):,} rows, {os.path.getsize(out):,} B)")


if __name__ == "__main__":
    main()
