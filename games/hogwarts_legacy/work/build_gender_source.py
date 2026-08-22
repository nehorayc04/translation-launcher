#!/usr/bin/env python3
r"""build_gender_source.py — Hogwarts Legacy gender-source builder (Phase-2 prep).

Per `universal/GENDER_ORACLE_ROLLOUT.md` scenario #3 (future / translate-with-gender):
English is the MEANING source; the game's own gendered localization is the GENDER
source. Hogwarts Legacy ships an OFFICIAL Arabic locale (`arAE`) — Arabic ≈ Hebrew
(أنتَ/أنتِ = אתה/את, gendered verbs) — so the Arabic `MAIN/SUB-arAE.bin` value for
each key IS the gender oracle (no playing, no screenshots).

This joins the already-extracted Arabic (`extract/main_ar.json` + `sub_ar.json`) to
the pool keys (`MAIN:<key>` / `SUB:<key>`) and emits `extract/gender_source.json`:

    { "<string_key>": {"ar": "<arabic value>", "hint": "נמען=נקבה|זכר|רבים"|""} }

Every line carries the raw Arabic (so a Phase-2 translator/agent reads gender from
it); `hint` is filled ONLY where `gender_oracle.ar_addressee` is UNAMBIGUOUS. The
build feeds this beside the English so the Hebrew has the correct gender from line 1
— no gender debt. Deterministic, read-only, no LM.

    python build_gender_source.py            # write extract/gender_source.json + stats
    python build_gender_source.py --prove    # show real EN|AR|derived-gender samples
"""
import sys
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXTRACT = HERE.parent / "extract"
sys.path.insert(0, str(HERE.parent.parent.parent / "universal"))
import gender_oracle as go  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_HINT = {"f": "נמען=נקבה", "m": "נמען=זכר", "pl": "נמען=רבים"}


def _load():
    main_ar = json.loads((EXTRACT / "main_ar.json").read_text(encoding="utf-8"))
    sub_ar = json.loads((EXTRACT / "sub_ar.json").read_text(encoding="utf-8"))
    return main_ar, sub_ar


def build():
    main_ar, sub_ar = _load()
    out = {}
    hinted = 0
    for section, data in (("MAIN", main_ar), ("SUB", sub_ar)):
        for key, ar in data.items():
            ar = ar if isinstance(ar, str) else ""
            # STRICT oracle: pronouns + vocalized ـكَ/ـكِ only (no noisy ت…ين verb heuristic
            # that false-fires on masdar/plural-nouns/object-suffixes). Every hint is trustworthy.
            g = go.ar_addressee_strict(ar) if ar else None
            hint = _HINT.get(g, "")
            if hint:
                hinted += 1
            out[f"{section}:{key}"] = {"ar": ar, "hint": hint}
    dst = EXTRACT / "gender_source.json"
    dst.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"gender_source rows: {len(out)}  (auto-hint on {hinted})")
    print(f"-> {dst}")


def prove(n=25):
    """Show real lines where BOTH the English has a 'you' and the Arabic gives a gender."""
    main_en = json.loads((EXTRACT / "main_en.json").read_text(encoding="utf-8"))
    sub_en = json.loads((EXTRACT / "sub_en.json").read_text(encoding="utf-8"))
    main_ar, sub_ar = _load()
    en = {**{f"MAIN:{k}": v for k, v in main_en.items()},
          **{f"SUB:{k}": v for k, v in sub_en.items()}}
    ar = {**{f"MAIN:{k}": v for k, v in main_ar.items()},
          **{f"SUB:{k}": v for k, v in sub_ar.items()}}
    shown = 0
    counts = {"f": 0, "m": 0, "pl": 0}
    for k, av in ar.items():
        g = go.ar_addressee(av) if isinstance(av, str) else None
        if not g:
            continue
        counts[g] += 1
        ev = en.get(k, "")
        if shown < n and isinstance(ev, str) and ("you" in ev.lower() or "your" in ev.lower()):
            print(f"[{g}] {k}")
            print(f"    EN: {ev[:90]!r}")
            print(f"    AR: {av[:90]!r}")
            shown += 1
    total = sum(counts.values())
    print(f"\nArabic addressee resolved on {total} lines  (f={counts['f']} m={counts['m']} pl={counts['pl']})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prove", action="store_true")
    a = ap.parse_args()
    if a.prove:
        prove()
    else:
        build()
