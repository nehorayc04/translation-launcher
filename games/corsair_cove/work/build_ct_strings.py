"""Build the Corsair Cove upload for the public /translate pool ("תרגמו איתנו").

KEY CONTRACT
    string_key = "<namespace>|<key>"  -- byte-identical to the key `cc_locres` returns and
    `build_hebrew.py` consumes, so an approved export drops straight onto the build with no
    remapping. This is the §17 rule 4 requirement.

🔴 NO DEDUP BY THE ENGLISH STRING -- measured, not assumed. 600 duplicate-English groups
(1,507 keys) diverge in the game's OWN professional locales at fr 14.8% / pl 11.5% /
es 6.3% / de 6.2% / ru 1.5%. Collapsing them would silently put one wrong Hebrew on ~90
groups, so the pool is keyed per (namespace, key) exactly like the build.

CATEGORIES -- ordered by VISIBILITY, split by the engine's OWN metadata (a non-empty
`Audio Filename` column = a recorded VO line), never by a length heuristic:
    1. ממשק ותפריטים    everything the player reads on a menu/HUD
    2. כתוביות עלילה    recorded dialogue

CONTEXT -- Corsair Cove is the richest case in the project: the developers shipped a
localisation kit, so each row carries the real `Context` note, the speaker/addressee, a
normalised gender, and the game's own translations in up to 7 languages. That is the
New-Era panel and the gender oracle handed over as first-class data.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = pathlib.Path(__file__).resolve().parent
GAME = HERE.parent
CORPUS = GAME / "extract" / "context_source.json"
OUT = GAME / "extract" / "ct_upload.json"

UI = "ממשק ותפריטים"
SUBS = "כתוביות עלילה"
ORDER = [UI, SUBS]

PANEL = ("ru", "pl", "de", "fr", "it", "es", "pt-BR")
GENDER_HE = {"male": "זכר", "female": "נקבה", "plural": "רבים"}

# token-only / no-real-letter rows carry nothing to translate
TOKEN = re.compile(r"<[^<>]{1,80}>|\{[^{}]{0,80}\}|&[a-zA-Z#0-9]{1,10};|[\d\W_]+")

# Dev scaffolding, dropped with EVIDENCE rather than by a name hunch: this row's English is
# an instruction to a developer ("Have {1} loca key defined in code") and the shipped German
# leaves it byte-identical to the English. It is the ONLY such row in the corpus.
# ⚠️ Deliberately NOT dropped: ST_ECPrincipleCompassNodeType|* (CrossPolicyNode, SimpleNode…).
# They look like code identifiers and German leaves them -- but the professional RUSSIAN
# TRANSLATES all four (Перекрёстный ориентир…), so they may well be displayed. Uploading them
# with that Russian in the context lets a human decide; dropping them would be a guess.
DEV_KEYS = {"DummyTable|DummyKey"}


def has_word(en: str) -> bool:
    return bool(re.search(r"[A-Za-z]{2,}", TOKEN.sub(" ", en or "")))


def norm_gender(v: str) -> str:
    """Map the dev kit's DIRTY gender column onto a CLOSED set, and refuse to guess.

    The shipped values are mixed-case and include a `Variable`/`various` bucket (the
    addressee is the PLAYER, whose captain may be either gender) and plural addressees
    written as a group NAME (`Pirate Crew`). An open-class guess here manufactures
    confident garbage -- [[gender-hint-needs-closed-set]] -- so anything outside the closed
    set becomes `named:<X>` or is dropped.
    """
    s = (v or "").strip().lower()
    if not s:
        return ""
    if s in ("m", "male", "man"):
        return "male"
    if s in ("f", "female", "woman"):
        return "female"
    if s in ("plural", "group", "many", "mixed"):
        return "plural"
    if s in ("variable", "various", "any", "either", "n/a", "-", "player"):
        return ""            # genuinely unknown at translation time
    return "named:" + (v or "").strip()


def build_context(v: dict) -> str:
    """One compact Hebrew-facing hint line: what the string IS + who says it to whom +
    the gender the English drops + the game's own translations (the New-Era panel)."""
    bits = []
    if v.get("context"):
        bits.append(str(v["context"]).strip())
    who = []
    if v.get("speaker"):
        who.append("דובר: " + str(v["speaker"]).strip())
    if v.get("addressee"):
        who.append("נמען: " + str(v["addressee"]).strip())
    if who:
        bits.append(" · ".join(who))
    g = []
    sg = norm_gender(v.get("speaker_gender", ""))
    ag = norm_gender(v.get("addressee_gender", ""))
    if sg in GENDER_HE:
        g.append("מגדר דובר=" + GENDER_HE[sg])
    if ag in GENDER_HE:
        g.append("מגדר נמען=" + GENDER_HE[ag])
    if g:
        bits.append(" · ".join(g))
    refs = v.get("refs") or {}
    panel = [f"{L.upper()}: {refs[L]}" for L in PANEL if refs.get(L)]
    if panel:
        bits.append(" | ".join(panel))
    return "\n".join(bits)


def main() -> int:
    d = json.load(open(CORPUS, encoding="utf-8"))
    rows, dropped = [], 0
    buckets = {UI: [], SUBS: []}
    for key, v in d.items():
        en = (v.get("en") or "").strip()
        if key in DEV_KEYS or not en or not has_word(en):
            dropped += 1
            continue
        # the engine's OWN metadata decides the surface: a recorded VO line is dialogue
        cat = SUBS if v.get("vo") else UI
        buckets[cat].append((key, v, en))

    idx = 0
    for cat in ORDER:                       # contiguous order_index blocks per category
        for key, v, en in buckets[cat]:
            rows.append({
                "string_key": key,
                "source_en": en,
                "current_he": "",           # fresh game
                "context": build_context(v),
                "section": cat,
                "order_index": idx,
            })
            idx += 1

    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  wrote {OUT.name}: {len(rows):,} rows  (dropped {dropped} token-only)")
    for cat in ORDER:
        print(f"    {cat:<18} {len(buckets[cat]):,}")
    withctx = sum(1 for r in rows if r["context"])
    withpanel = sum(1 for r in rows if "RU:" in r["context"] or "DE:" in r["context"])
    print(f"  context on {withctx:,} rows · reference panel on {withpanel:,}")

    # round-trip: every key must resolve back onto the real corpus (§17 rule 9)
    bad = [r["string_key"] for r in rows if r["string_key"] not in d]
    mism = [r["string_key"] for r in rows
            if r["string_key"] in d and (d[r["string_key"]].get("en") or "").strip() != r["source_en"]]
    print(f"  round-trip: unresolvable={len(bad)}  source_en mismatches={len(mism)}")
    return 1 if (bad or mism) else 0


if __name__ == "__main__":
    raise SystemExit(main())
