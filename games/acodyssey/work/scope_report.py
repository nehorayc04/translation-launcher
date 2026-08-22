#!/usr/bin/env python3
r"""
scope_report.py — the honest Phase-2 scope for AC Odyssey.

Reports THREE counts, never one (§17.1): records · per-file uniques · GLOBAL
uniques — only the last is the translation workload. Also runs the
dedup-safety measurement ([[dedup-safety-from-game-langs]]): before keying a
pool by the English string, MEASURE how often the game's OWN professional
locales give one English string two different translations.

    python work/scope_report.py [--out extract/scope.txt]
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "..", "acunity", "work"))

import aco_forge                                        # noqa: E402
import aco_cfd                                          # noqa: E402
import aco_loc                                          # noqa: E402
import aco_rtl                                          # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAME = os.environ.get("ACO_GAME", r"F:\Games\Assassin's Creed Odyssey")
PATCH = os.path.join(GAME, "DataPC_patch_01.forge")

# The authoritative copies live in the PATCH forge (it shadows the base).
PKGS = {
    "en_ui": "LocalizationPackage_English",
    "en_subs": "LocalizationPackage_English_Subtitles",
    "ar_ui": "LocalizationPackage_Arabic",
    "ar_subs": "LocalizationPackage_Arabic_Subtitles",
    "fr_ui": "LocalizationPackage_French",
    "fr_subs": "LocalizationPackage_French_Subtitles",
    "ru_ui": "LocalizationPackage_Russian",
    "ru_subs": "LocalizationPackage_Russian_Subtitles",
    "de_subs": "LocalizationPackage_German_Subtitles",
    "it_subs": "LocalizationPackage_Italian_Subtitles",
    "es_subs": "LocalizationPackage_Spanish_Subtitles",
    "pl_subs": "LocalizationPackage_Polish_Subtitles",
}


def load_all():
    fg = aco_forge.Forge(PATCH)
    od = aco_cfd.oodle()
    data = {}
    for tag, name in PKGS.items():
        try:
            p = aco_loc.find(fg, name, od)
            data[tag] = p.strings()
        except Exception as ex:
            print(f"[warn] {name}: {type(ex).__name__}", file=sys.stderr)
    fg.close()
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "extract", "scope.txt"))
    a = ap.parse_args()

    d = load_all()
    out = []

    def w(s=""):
        print(s)
        out.append(s)

    en_ui, en_subs = d["en_ui"], d["en_subs"]
    allen = {**en_ui, **en_subs}

    w("=== SCOPE (DataPC_patch_01.forge — the copy that shadows the base) ===")
    w(f"  records          UI {len(en_ui):>7,}   subtitles {len(en_subs):>7,}"
      f"   = {len(en_ui)+len(en_subs):,}")
    w(f"  id overlap UI/subs                    {len(set(en_ui)&set(en_subs)):>7,}")
    w(f"  GLOBAL unique ids                     {len(allen):>7,}   <-- key space")
    uniq = set(allen.values())
    w(f"  GLOBAL unique STRINGS                 {len(uniq):>7,}   <-- workload")
    w(f"  total EN chars                        {sum(len(v) for v in allen.values()):>7,}")
    L = sorted(len(v) for v in allen.values())
    w(f"  length  median {L[len(L)//2]}  p90 {L[int(len(L)*.9)]}  max {max(L)}"
      f"   <=25ch {sum(1 for x in L if x<=25):,}   >140ch {sum(1 for x in L if x>140):,}")

    w("")
    w("=== ORACLE PARITY (every locale is a strict SUBSET of English) ===")
    for tag in sorted(d):
        if tag.startswith("en_"):
            continue
        base = en_ui if tag.endswith("_ui") else en_subs
        o = set(d[tag])
        w(f"  {PKGS[tag]:<46} {len(o):>7,}  covered by EN: "
          f"{100*len(o&set(base))/max(1,len(o)):.1f}%")

    w("")
    w("=== TOKENS (measured over all EN strings) ===")
    pats = {
        "<tag>": r"<[^>]{1,120}>",
        "{PLACEHOLDER}": r"\{[^}\n]{1,60}\}",
        "[engine token]": r"\[(?:CT_[A-Za-z0-9_]+|[A-Z0-9_]{2,}|\d+)\]",
        "[prose bracket]": r"\[(?!CT_[A-Za-z0-9_]+\]|[A-Z0-9_]{2,}\]|\d+\])[^\]]{1,60}\]",
        "%spec": r"%[-0-9.]*[a-zA-Z]",
        "newline": r"\n",
    }
    for nm, p in pats.items():
        r = re.compile(p)
        c = collections.Counter()
        for v in allen.values():
            c.update(r.findall(v))
        w(f"  {nm:<16} occ={sum(c.values()):>7,}  distinct={len(c):>4}  "
          f"top={[k for k, _ in c.most_common(5)]}")

    w("")
    w("=== DEDUP SAFETY — is it safe to key a pool by the ENGLISH string? ===")
    w("  (for each English string used by >1 id, do the game's OWN professional")
    w("   locales give those ids DIFFERENT translations?)")
    groups = collections.defaultdict(list)
    for k, v in en_subs.items():
        groups[v].append(k)
    dup = {v: ks for v, ks in groups.items() if len(ks) > 1}
    w(f"  duplicate-English groups in subtitles: {len(dup):,} "
      f"(covering {sum(len(k) for k in dup.values()):,} ids)")
    for tag in ("ar_subs", "ru_subs", "fr_subs", "de_subs", "it_subs",
                "es_subs", "pl_subs"):
        if tag not in d:
            continue
        loc = d[tag]
        div = tot = 0
        for _v, ks in dup.items():
            vals = {loc[k] for k in ks if k in loc}
            if len(vals) >= 1:
                tot += 1
                if len(vals) > 1:
                    div += 1
        w(f"    {PKGS[tag]:<46} diverge on {div:,}/{tot:,} = "
          f"{100*div/max(1,tot):.1f}%")
    w("  -> a non-trivial divergence means DO NOT dedup by English; key by id.")

    w("")
    w("=== BIDI EVIDENCE (from the game's own shipped Arabic) ===")
    ar = {**d["ar_ui"], **d["ar_subs"]}
    pres = sum(1 for v in ar.values() for c in v if 0xFB50 <= ord(c) <= 0xFEFF)
    std = sum(1 for v in ar.values() for c in v if 0x0600 <= ord(c) <= 0x06FF)
    ctrl = sum(1 for v in ar.values() for c in v
               if ord(c) in (0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E))
    endp = sum(1 for v in ar.values() if v.strip().endswith((".", "!", "?", "،")))
    startp = sum(1 for v in ar.values() if v.strip()[:1] in ".!?،")
    w(f"  standard-block Arabic chars {std:>9,}")
    w(f"  presentation forms          {pres:>9,}   (0 => the engine shapes)")
    w(f"  bidi control chars          {ctrl:>9,}   (0 => the engine reorders)")
    w(f"  lines ending . ! ? ،        {endp:>9,}")
    w(f"  lines starting . ! ? ،      {startp:>9,}")
    w("  -> store LOGICAL (natural Hebrew, never pre-reversed, no &rlm;).")

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
