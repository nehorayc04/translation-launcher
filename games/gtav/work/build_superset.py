#!/usr/bin/env python3
"""build_superset.py — assemble global_he_super.gxt2 from LOGICAL sources.

Superset = vanilla update2 global.gxt2 (69,209 EN keys, the REAL base text layer) with
two disjoint Hebrew overlays, both rebuilt FROM LOGICAL through the SAME current
visual_line (so the maqaf-boundary fix applies uniformly), and with agent-added
"(English gloss)" parentheticals stripped:
  * base run   — agent_handoff/hebrew.json      (21,575, keys 0x%08x)  -> strip -> visual
  * update2 run — agent_handoff_update2/merged_he_final.json (41,783, keys %x) -> strip -> visual
Keys not in either overlay (names/codes/untranslated, ~4,370) stay vanilla English.

Why rebuild from logical: the old global_he.gxt2 was visualised with a pre-fix
visual_line, so 'EXIT TO WINDOWS' = 'יציאה ל-WINDOWS' rendered with the maqaf on the
wrong side ('-WINDOWSל'). Regenerating every Hebrew entry through the current
visual_line (+ _split_boundary_maqaf) fixes it everywhere at once.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gtav_gxt2 as G

HERE = os.path.dirname(os.path.abspath(__file__))
GTAV = os.path.normpath(os.path.join(HERE, ".."))
VANILLA = os.path.join(GTAV, "_fonts_src", "american_rel.rpf", "global.gxt2")
BASE_HE = os.path.join(GTAV, "agent_handoff", "hebrew.json")
BASE_EN = os.path.join(GTAV, "agent_handoff", "to_translate.json")
MERGED = os.path.join(GTAV, "agent_handoff_update2", "merged_he_final.json")
MERGED_EN = os.path.join(GTAV, "agent_handoff_update2", "to_translate.json")
OUT = os.path.join(HERE, "global_he_super.gxt2")

HEB = re.compile("[א-ת]")
LAT = re.compile("[A-Za-z]")
PAR = re.compile(r"\s*\(([^()]+)\)")


def strip_gloss(he, en):
    """Remove agent-added Latin-only '(English)' glosses (the systematic
    'translation (source)' habit the user rejected). Keep legit source parens,
    tokens (~..~), tags (<..>), and %-specs. Reverts if the result loses all Hebrew
    (a name-only string like 'Pegassi (Infernus)')."""
    out = he
    # 1) whole-source gloss: the agent wrapped the ENTIRE English source in parens
    #    ("On Foot (Third Person)" -> "...(On Foot (Third Person))"). Literal removal
    #    handles the NESTED-paren case the regex below can't (it would keep the inner
    #    "(Third Person)" because that IS in the source).
    ens = (en or "").strip()
    if ens and HEB.search(out):
        for g in (" (" + ens + ")", "(" + ens + ")"):
            if g in out:
                out = out.replace(g, "")
    # 2) per-paren Latin-only glosses (non-nested partial glosses).
    def repl(m):
        inner = m.group(1)
        if any(c in inner for c in "~<>%"):
            return m.group(0)
        if not LAT.search(inner) or HEB.search(inner):
            return m.group(0)
        if ("(" + inner + ")") in en:                 # parenthetical present in source
            return m.group(0)
        return ""
    out = PAR.sub(repl, out)
    if not HEB.search(out):
        return he
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([.,!?:;])", r"\1", out)
    return out.strip()


def main():
    vanilla = G.read_gxt2(open(VANILLA, "rb").read())     # {int: EN}
    base_he = json.load(open(BASE_HE, encoding="utf-8"))  # {0xHHHH: logical HE}
    base_en = json.load(open(BASE_EN, encoding="utf-8"))
    merged = json.load(open(MERGED, encoding="utf-8"))    # {hex: logical HE}
    merged_en = json.load(open(MERGED_EN, encoding="utf-8"))

    superset = dict(vanilla)
    n_base = n_upd = n_gloss = 0
    for k, he in base_he.items():
        if not str(he).strip():
            continue
        clean = strip_gloss(he, base_en.get(k, ""))
        if clean != he:
            n_gloss += 1
        superset[int(k, 16) & 0xFFFFFFFF] = G.visual_line(clean)
        n_base += 1
    for k, he in merged.items():
        if not str(he).strip():
            continue
        clean = strip_gloss(he, merged_en.get(k, ""))
        if clean != he:
            n_gloss += 1
        superset[int(k, 16) & 0xFFFFFFFF] = G.visual_line(clean)
        n_upd += 1

    data = G.write_gxt2(superset)
    open(OUT, "wb").write(data)

    rt = G.read_gxt2(data)
    assert len(rt) == len(superset), (len(rt), len(superset))
    heb = sum(1 for v in rt.values() if HEB.search(v))
    print(f"vanilla={len(vanilla)} base_logical={n_base} update2_logical={n_upd} glosses_stripped={n_gloss}")
    print(f"superset keys={len(superset)} hebrew={heb} english={len(superset)-heb}")
    print(f"wrote {OUT} ({len(data):,} B), round-trip OK")


if __name__ == "__main__":
    main()
