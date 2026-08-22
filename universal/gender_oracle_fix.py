# -*- coding: utf-8 -*-
"""
gender_oracle_fix.py — apply the gender fixes the game's Arabic proves are needed
(gender_oracle scan → suspects). CP2077 femaleVariant is shown when the player V is
FEMALE, so an NPC addressing V must use FEMININE forms there. Our English-derived
Hebrew often left it MASCULINE (proven by the Arabic femaleVariant using أنتِ/تسألين).

Fix per suspect (AR addressee = feminine, our HE femaleVariant = masculine):
  * maleVariant := (current masculine femaleVariant) if maleVariant is EMPTY
    (so MALE V keeps the masculine text; an empty maleVariant falls back to female)
  * femaleVariant := to_feminine(femaleVariant)   (deterministic masc→fem morphology)
Result: femaleVariant feminine (female V) + maleVariant masculine (male V) — the split.

`to_feminine` is the MIRROR of dualgender_inflect.inflect (which does fem→masc): an
inverted word map + אתה→את. Every result is re-validated (classify_fill: scaffold
preserved, a real gender change, no niqqud/internal-edit) AND must actually flip the
addressee to feminine. A line that doesn't cleanly flip is LEFT UNTOUCHED and written
to a delegate worklist — never corrupted.

CLI: python gender_oracle_fix.py            # dry-run (sample + stats, no writes)
     python gender_oracle_fix.py --apply     # apply to the spine (backup+lock+atomic)
"""
from __future__ import annotations
import argparse, json, os, shutil, sys, time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gender_oracle as go
from dualgender_inflect import FEM2MASC, PREF, HEBRUN
from dualgender_verify_agents import classify_fill
from dualgender_fix import acquire_lock, release_lock, atomic_write_json, _entry_key

ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "תרגום_משחקים", "source", "resources")
SPINE = {"base": os.path.join(RES, "localization_translated.json"),
         "dlc": os.path.join(RES, "dlc_ep1_translated.json")}
SUSPECTS = os.path.join(ROOT, "games", "cyberpunk2077", "gender_oracle_suspects.jsonl")
DELEGATE = os.path.join(ROOT, "games", "cyberpunk2077", "gender_oracle_delegate.jsonl")

# masc→fem = the inverse of the fem→masc map (skip ktiv-invariant no-ops where key==val)
MASC2FEM = {}
for fem, masc in FEM2MASC.items():
    if fem != masc and masc not in MASC2FEM:
        MASC2FEM[masc] = fem


# words that RESET the 2nd-person window (a different subject/pronoun starts)
_RESET = {"אני", "אנחנו", "הוא", "היא", "הם", "הן", "אנו", "אתם", "אתן",
          "לך", "לו", "לה", "להם", "לכם"}   # + prepositions that are homographs
# present participles ONLY (agree with the subject; safe to flip after אתה).
# Exclude imperative/future inversions (ambiguous, homograph-prone) from the window flip.
_SAFE_FLIP = {m: f for m, f in MASC2FEM.items()
              if not m.startswith("ת")}       # drop ת-future (3rd-fem homograph)


def to_feminine(he_male: str):
    """TIGHT masc→fem: flip אתה→את and ONLY the present-participle it governs (within
    2 Hebrew words, before another subject resets). Returns (result, flipped_bool).
    Never touches 1st/3rd-person words, prepositions, or nouns → no over-flip."""
    runs = [(m.start(), m.end(), m.group(0)) for m in HEBRUN.finditer(he_male)]
    if not runs:
        return he_male, False
    stems = [w.lstrip("".join(PREF)) for _, _, w in runs]
    out, prev = [], 0
    window = 0          # >0 → we are inside an אתה-governed span
    flipped = False
    for i, (s, e, word) in enumerate(runs):
        out.append(he_male[prev:s]); prev = e
        pl = 0
        for k in (2, 1):
            if len(word) > k and word[k - 1] in PREF:
                pl = k; break
        stem = word[pl:]
        if stem == "אתה":
            out.append(word[:pl] + "את"); flipped = True; window = 2
            continue
        if stem in _RESET:
            window = 0
        if window > 0 and stem in _SAFE_FLIP:
            out.append(word[:pl] + _SAFE_FLIP[stem]); flipped = True; window = 0
            continue
        if window > 0:
            window -= 1
        out.append(word)
    out.append(he_male[prev:])
    return "".join(out), flipped


def _load_suspects():
    return [json.loads(l) for l in open(SUSPECTS, encoding="utf-8") if l.strip()]


def plan():
    """Return (fixes, delegate, stats). fixes = list of dicts to apply."""
    fixes, delegate = [], []
    stats = dict(total=0, kiroshi=0, mv_fem=0, no_flip=0, not_fem=0, ok=0)
    for s in _load_suspects():
        stats["total"] += 1
        if s["ar_gender"] != "f":          # this pass fixes the fem-addressee case only
            continue
        fv, mv = s["he_female"], (s.get("he_male") or "")
        if fv.strip().startswith("<kiroshi") and " o=" in fv:
            stats["kiroshi"] += 1
            continue
        if mv.strip() and mv.strip() != fv.strip() and go.he_addressee(mv) == "f":
            stats["mv_fem"] += 1          # maleVariant already feminine → skip (odd)
            continue
        fv_new, flipped = to_feminine(fv)
        if not flipped or fv_new == fv:
            stats["no_flip"] += 1
            delegate.append(s)
            continue
        if go.he_addressee(fv_new) != "f":
            stats["not_fem"] += 1
            delegate.append(s)
            continue
        val, why = classify_fill(fv_new, fv, "")   # scaffold preserved + real gender change
        if why:
            stats["no_flip"] += 1
            delegate.append(s)
            continue
        mv_new = mv if mv.strip() else fv          # keep masculine for male V
        stats["ok"] += 1
        fixes.append({"src": s["src"], "section": s["section"], "pk": s["pk"],
                      "fv_old": fv, "fv_new": val, "mv_old": mv, "mv_new": mv_new})
    return fixes, delegate, stats


def apply(fixes) -> dict:
    st = dict(written=0, guard_skip=0, missing=0)
    by_src = {}
    for f in fixes:
        by_src.setdefault(f["src"], []).append(f)
    for src, rows in by_src.items():
        path = SPINE[src]
        spine = json.load(open(path, encoding="utf-8"))
        idx = {}
        for sec, lst in spine.items():
            if isinstance(lst, list):
                idx[sec] = {_entry_key(e): e for e in lst if isinstance(e, dict)}
        # section key in suspects is "src:section"
        dirty = 0
        for f in rows:
            sec = f["section"].split(":", 1)[1] if ":" in f["section"] else f["section"]
            e = idx.get(sec, {}).get(str(f["pk"]))
            if e is None:
                st["missing"] += 1
                continue
            # guard: only write if the spine still holds exactly what we scanned
            if (e.get("femaleVariant") or "") != f["fv_old"] or \
               (e.get("maleVariant") or "") != f["mv_old"]:
                st["guard_skip"] += 1
                continue
            e["maleVariant"] = f["mv_new"]
            e["femaleVariant"] = f["fv_new"]
            dirty += 1
        if dirty:
            bak = f"{path}.bak.goracle.{time.strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(path, bak)
            atomic_write_json(path, spine)
            st["written"] += dirty
            print(f"  wrote {os.path.basename(path)}: {dirty:,}  (backup {os.path.basename(bak)})")
    return st


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gender_oracle_fix")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--samples", type=int, default=12)
    a = p.parse_args(argv)
    fixes, delegate, stats = plan()
    print("gender_oracle_fix — plan:")
    print(f"    suspects (fem-addressee): {stats['total']:,}")
    print(f"    kiroshi foreign (skip)  : {stats['kiroshi']:,}")
    print(f"    maleVariant already fem : {stats['mv_fem']:,}")
    print(f"    ✅ clean deterministic fix: {stats['ok']:,}")
    print(f"    → delegate (no clean flip): {len(delegate):,}")
    print("\n  sample fixes (fv: masc→fem):")
    for f in fixes[:a.samples]:
        print(f"    OLD fv: {f['fv_old'][:60]}")
        print(f"    NEW fv: {f['fv_new'][:60]}")
        print()
    with open(DELEGATE, "w", encoding="utf-8") as fo:
        for s in delegate:
            fo.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"  delegate worklist → {os.path.basename(DELEGATE)} ({len(delegate):,})")
    if a.apply:
        if not acquire_lock("gender_oracle_fix"):
            return 1
        try:
            st = apply(fixes)
        finally:
            release_lock()
        print(f"\nAPPLIED: written {st['written']:,}  guard-skip {st['guard_skip']:,}  "
              f"missing {st['missing']:,}")
        print("  reaches the game on the next bake.")
    else:
        print("\n  (dry-run — re-run with --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
