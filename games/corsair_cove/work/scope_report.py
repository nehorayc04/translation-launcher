#!/usr/bin/env python3
"""
scope_report.py - Corsair Cove Phase-1 scope + the Phase-2 ammunition.

Three outputs:

  1. THE SCOPE, reported as three separate numbers (records / per-file unique /
     GLOBAL unique) -- only the last is the translation workload.
  2. THE UI-vs-DIALOGUE SPLIT taken from the engine's OWN metadata (a row with a
     non-empty `Audio Filename` is a recorded VO line), never from a length or
     filename heuristic.
  3. `extract/context_source.json` -- the developer-authored localisation kit:
     Context on 100% of rows, plus Speaker / Addressee / SpeakerGender /
     AddresseeGender / conversation ordering. This is the gender oracle that we
     normally have to reverse-engineer out of the game's Russian/Polish/Arabic.

  4. THE DEDUP-SAFETY MEASUREMENT: for every English string that appears on more
     than one key, check whether the game's OWN professional locales translate
     those keys DIFFERENTLY. If they do, the pool must be keyed by (ns,key), not
     by the English string.
"""
import collections
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(GAME_DIR, "tools"))
import cc_locres  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PRISTINE = os.path.join(GAME_DIR, "extract", "pak0", "CorsairCove")
LOC = os.path.join(PRISTINE, "Content", "Localization", "CoveGame")
CSVDIR = os.path.join(PRISTINE, "Content", "StringTables")
OUT = os.path.join(GAME_DIR, "extract")

GENDER_LANGS = ["ru", "pl"]          # past tense marks speaker AND addressee
REFERENT_LANGS = ["fr", "it", "es", "pt-BR"]
REGISTER_LANGS = ["de"]

# The developer sheet's gender columns are REAL but DIRTY: mixed case, a
# "Variable"/"various" bucket (the addressee is the player, whose captain may be
# either gender), plural addressees written as a GROUP NAME ("Pirate Crew"), and
# a few rows where a Comment leaked one column to the left. Normalise to a closed
# set and never invent a gender from free text -- an open-class guess is exactly
# what manufactures confident garbage.
_PLURAL_WORDS = {"pirate crew", "captains", "crew", "everyone", "all", "players"}


def norm_gender(raw):
    v = (raw or "").strip().lower()
    if not v:
        return ""
    if v in ("male", "m", "masculine"):
        return "male"
    if v in ("female", "f", "feminine"):
        return "female"
    if v in ("variable", "various", "any", "either", "player"):
        return "variable"
    if v in _PLURAL_WORDS:
        return "plural"
    if len(v) > 24 or " the " in v:      # a leaked Comment, not a gender
        return ""
    return "named:" + raw.strip()        # a specific character -> keep, don't guess


def load_locres(culture):
    d = cc_locres.load(os.path.join(LOC, culture, "CoveGame.locres"))
    return {(ns["name"], e["key"]): e["value"]
            for ns in d["namespaces"] for e in ns["entries"]}


def load_csv_meta():
    """(namespace, key) -> the developer's localisation-kit row.
    The namespace is the CSV's own basename without the .csv (that is what the
    engine registers via +StringTableCSVs and what the locres namespaces use)."""
    meta = {}
    for p in sorted(glob.glob(os.path.join(CSVDIR, "**", "*.csv"), recursive=True)):
        ns = os.path.splitext(os.path.basename(p))[0]
        with open(p, encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                k = (row.get("Key") or "").strip()
                if not k:
                    continue
                meta[(ns, k)] = row
    return meta


def main():
    en = load_locres("en")
    meta = load_csv_meta()
    cultures = sorted(d for d in os.listdir(LOC) if os.path.isdir(os.path.join(LOC, d)))

    joined = sum(1 for k in en if k in meta)
    print("=== JOIN ===")
    print("  locres records        : %d" % len(en))
    print("  CSV rows              : %d" % len(meta))
    print("  joined on (ns,key)    : %d  (%.1f%%)" % (joined, 100 * joined / len(en)))

    # ---- scope -------------------------------------------------------------
    vals = list(en.values())
    print("\n=== SCOPE (report all three; translate only the GLOBAL unique) ===")
    print("  records               : %d" % len(vals))
    print("  GLOBAL unique strings : %d" % len(set(vals)))
    print("  characters            : %d" % sum(len(v) for v in vals))

    # ---- UI vs dialogue, from the engine's own metadata ---------------------
    vo, ui, unknown = [], [], []
    for k, v in en.items():
        m = meta.get(k)
        if m is None:
            unknown.append(k)
        elif (m.get("Audio Filename") or "").strip():
            vo.append(k)
        else:
            ui.append(k)
    print("\n=== SURFACE SPLIT (from `Audio Filename`, the engine's own metadata) ===")
    print("  recorded VO / dialogue: %6d records, %6d unique" % (len(vo), len({en[k] for k in vo})))
    print("  UI / content          : %6d records, %6d unique" % (len(ui), len({en[k] for k in ui})))
    print("  not in any CSV        : %6d" % len(unknown))

    # ---- developer localisation kit ----------------------------------------
    fields = ["Context", "Speaker", "Addressee", "SpeakerGender", "AddresseeGender",
              "Order in the Sequence", "Place of the Sequence", "Comment"]
    counts = {f: sum(1 for k in en if (meta.get(k, {}).get(f) or "").strip()) for f in fields}
    print("\n=== DEVELOPER LOCALISATION KIT (filled rows) ===")
    for f in fields:
        print("  %-24s %6d  (%.1f%%)" % (f, counts[f], 100 * counts[f] / len(en)))
    ag = collections.Counter(norm_gender(meta.get(k, {}).get("AddresseeGender")) for k in en)
    sg = collections.Counter(norm_gender(meta.get(k, {}).get("SpeakerGender")) for k in en)
    fmt = lambda c: {k or "(empty)": n for k, n in sorted(c.items(), key=lambda x: -x[1])}
    print("  AddresseeGender (normalised):", fmt(ag))
    print("  SpeakerGender   (normalised):", fmt(sg))

    # ---- New-Era reference panel -------------------------------------------
    print("\n=== NEW-ERA PANEL (key parity vs en) ===")
    others = {}
    for c in cultures:
        if c == "en":
            continue
        others[c] = load_locres(c)
        inter = sum(1 for k in en if k in others[c])
        role = ("gender(spk+addr)" if c in GENDER_LANGS else
                "referent" if c in REFERENT_LANGS else
                "register" if c in REGISTER_LANGS else "")
        print("  %-8s %6d keys  parity %5.1f%%  %s"
              % (c, len(others[c]), 100 * inter / len(en), role))

    # ---- dedup safety ------------------------------------------------------
    by_en = collections.defaultdict(list)
    for k, v in en.items():
        by_en[v].append(k)
    dup_groups = {v: ks for v, ks in by_en.items() if len(ks) > 1}
    print("\n=== DEDUP SAFETY (measured against the game's OWN locales) ===")
    print("  duplicate-English groups: %d  (covering %d keys)"
          % (len(dup_groups), sum(len(k) for k in dup_groups.values())))
    for c in ["ru", "pl", "de", "fr", "es"]:
        o = others.get(c)
        if not o:
            continue
        diverge = sum(1 for v, ks in dup_groups.items()
                      if len({o.get(k) for k in ks if k in o}) > 1)
        pct = 100 * diverge / len(dup_groups) if dup_groups else 0
        print("    %-8s %4d of %d groups get DIFFERENT translations  (%.1f%%)"
              % (c, diverge, len(dup_groups), pct))

    # ---- emit the Phase-2 context/gender source ----------------------------
    os.makedirs(OUT, exist_ok=True)
    ctx = {}
    for (ns, key), v in en.items():
        m = meta.get((ns, key), {})
        rec = {"en": v}
        for f, tag in [("Context", "context"), ("Speaker", "speaker"),
                       ("Addressee", "addressee"),
                       ("Place of the Sequence", "scene"),
                       ("Order in the Sequence", "order")]:
            val = (m.get(f) or "").strip()
            if val:
                rec[tag] = val
        for f, tag in [("SpeakerGender", "speaker_gender"),
                       ("AddresseeGender", "addressee_gender")]:
            val = norm_gender(m.get(f))
            if val:
                rec[tag] = val
        rec["vo"] = bool((m.get("Audio Filename") or "").strip())
        for c in GENDER_LANGS + REFERENT_LANGS + REGISTER_LANGS:
            o = others.get(c)
            if o and (ns, key) in o:
                rec.setdefault("refs", {})[c] = o[(ns, key)]
        ctx["%s|%s" % (ns, key)] = rec
    p = os.path.join(OUT, "context_source.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=0)
    print("\nwrote %s  (%d rows)" % (p, len(ctx)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
