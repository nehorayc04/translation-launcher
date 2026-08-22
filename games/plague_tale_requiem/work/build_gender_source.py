#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_gender_source.py — GENDER ORACLE source for A Plague Tale: Requiem (per
universal/GENDER_ORACLE_ROLLOUT.md, scenario #3: future/translate-with-gender).

English drops gender/number, so translating from English GUESSES it. The game ships
a full professional ARABIC translation (the slot we hijack) — Arabic ≈ Hebrew (both
Semitic: أنتَ/أنتِ = אתה/את, gendered verbs, feminine ـة). We attach that Arabic to
every line as the GENDER source (English stays the MEANING source), so the Phase-2
handoff carries the answer and no gender debt is ever created.

Join key = KEY (shared across every tt file). Gender source = the PRISTINE original
Arabic `tt23.pc.he_backup` (NOT the live file — that may be a re-encoded proof build).
The Arabic is stored as presentation forms in logical order → NFKC-normalize to
standard Arabic so `universal/gender_oracle.py`'s Arabic parser matches.

Output: games/plague_tale_requiem/extract/gender_source.json
        { KEY: {"en": <english>, "ar": <normalized arabic>, "hint": <addressee gender/number|"" > } }

SAFETY: read-only (only writes the extract/ sidecar). Never touches a game file.
"""
from __future__ import annotations
import json, os, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "universal"))
import pt_text as T                       # noqa: E402
import gender_oracle as G                 # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT_DIR = os.path.join(HERE, "..", "extract")
EN_PATH = T.lang_path(T.SOURCE_ID)                              # tt01.pc (English source)
AR_PATH = T.lang_path(T.SLOT_ID) + ".he_backup"                 # PRISTINE Arabic
if not os.path.exists(AR_PATH):
    AR_PATH = T.lang_path(T.SLOT_ID)                            # fallback: live (warn)


def norm_ar(s: str) -> str:
    """presentation forms -> standard Arabic (logical); the gender parser needs standard."""
    return unicodedata.normalize("NFKC", s)


def main():
    if AR_PATH.endswith(".he_backup"):
        print(f"gender source = PRISTINE {os.path.basename(AR_PATH)}")
    else:
        print(f"[WARN] no .he_backup — using LIVE tt23.pc (may be a proof build): {AR_PATH}")
    en = {r.key: r.value for r in T.parse(EN_PATH)}
    ar = {r.key: norm_ar(r.value) for r in T.parse(AR_PATH)}
    print(f"EN keys={len(en)}  AR keys={len(ar)}  shared={len(set(en) & set(ar))}")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = {}
    hinted = 0
    ar_letters = 0
    for k, e in en.items():
        a = ar.get(k, "")
        if any("؀" <= c <= "ۿ" for c in a):
            ar_letters += 1
        # addressee gender only means something in DIALOGUE (VO); on UI nouns/credits
        # the parser false-fires on a feminine ـة noun ending -> gate the auto-hint to VO.
        # (the raw Arabic is attached to EVERY line regardless — the translator reads it.)
        hint = ""
        if a and k.startswith("VO"):        # addressee gender only meaningful in dialogue
            try:
                g = G.ar_addressee(a)      # -> addressee gender/number, or None/''
            except Exception:
                g = None
            if g:
                hint = g
                hinted += 1
        out[k] = {"en": e, "ar": a, "hint": hint}

    p = os.path.join(OUT_DIR, "gender_source.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"rows={len(out)}  with-Arabic-letters={ar_letters}  with-gender-hint={hinted}")
    print("wrote", os.path.abspath(p))

    # show a few real gendered lines as proof the oracle fires on this game's Arabic
    shown = 0
    for k, v in out.items():
        if v["hint"] and v["en"].strip():
            print(f"  [{v['hint']:>10}] {v['en'][:44]!r}  <-  {v['ar'][:36]}")
            shown += 1
            if shown >= 6:
                break


if __name__ == "__main__":
    main()
