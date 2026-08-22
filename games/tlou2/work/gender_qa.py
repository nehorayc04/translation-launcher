#!/usr/bin/env python3
r"""
gender_qa.py - TLOU Part II Remastered gender ORACLE scan (addressee axis).

The game has NO Arabic slot, so the gender source is the game's own gendered
localizations: Russian (`text2/rus.*`, addressee gender via past -л/-ла + short
adjectives). For every already-translated SID we compare our Hebrew's addressee
gender (`he_addressee`) to the Russian's (`ru_addressee`); a high-confidence
disagreement means the Hebrew guessed the wrong gender from genderless English.

Runs on the LOGICAL Hebrew (agents/hebrew_*.json), BEFORE the visual bake - the
oracle needs reading order, and to_visual is applied only at build.

    python gender_qa.py                 # scan; -> gender_suspects.jsonl

Deterministic, no LM. Nothing is modified - it only REPORTS ([[delegate-all-translation]]).
Emit is ranked; fix the flagged lines by re-inflecting only the gender morpheme.
"""
import os
import sys
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "universal"))
import tlou_loc                        # noqa: E402
import gender_oracle as go             # noqa: E402

EXTRACT = os.path.join(HERE, "..", "extract")
LANG = os.path.join(EXTRACT, "lang")
HANDOFF = os.path.join(HERE, "..", "agent_handoff")
SECTIONS = ["common", "subtitles", "subtitles-systemic"]
OUT = os.path.join(HERE, "..", "gender_suspects.jsonl")


def _load_hebrew():
    he = {}
    for p in [os.path.join(HANDOFF, "hebrew.json")] + sorted(glob.glob(os.path.join(HANDOFF, "hebrew_*.json"))):
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                he.update(json.load(f))
    with open(os.path.join(HANDOFF, "to_translate.json"), encoding="utf-8") as f:
        k2en = json.load(f)
    return {k2en[k]: v for k, v in he.items() if k in k2en}   # en -> he


def main():
    en2he = _load_hebrew()
    if not en2he:
        print("no translations yet (hebrew_*.json empty) - harness ready; 0 to scan.")
    rows = []
    checked = 0
    for sec in SECTIONS:
        en_map = tlou_loc.to_map(open(os.path.join(EXTRACT, f"eng.{sec}"), "rb").read())
        ru_map = tlou_loc.to_map(open(os.path.join(LANG, f"rus.{sec}"), "rb").read())
        for sid, en in en_map.items():
            he = en2he.get(en)
            if not he:
                continue
            ru = ru_map.get(sid, "")
            a = go.ru_addressee(ru)
            h = go.he_addressee(he)
            if a in ("m", "f") and h in ("m", "f"):
                checked += 1
                if a != h:
                    rows.append({"section": sec, "sid": sid,   # to_map keys are already 016x hex
                                 "ru_gender": a, "he_gender": h,
                                 "en": en, "he": he, "ru": ru})
    with open(OUT, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[gender-qa] checked (both sides determinable): {checked:,}")
    print(f"[gender-qa] addressee mismatches (Russian oracle vs Hebrew): {len(rows):,}")
    print(f"[gender-qa] -> {OUT}")
    for r in rows[:8]:
        print(f"    RU={r['ru_gender']} HE={r['he_gender']}  en={r['en'][:40]!r}")
        print(f"        he={r['he'][:44]!r}  ru={r['ru'][:44]!r}")


if __name__ == "__main__":
    main()
