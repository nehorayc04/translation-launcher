"""deep_scan_deterministic.py — NO-AI deterministic defect sweep of the whole
corpus, reusing the project's battle-tested detectors. Finds real errors the
local qwen audit MISSED (calibration showed ~23% recall) without spending a
single AI token.

Reuses:
  cp2077_qa_defects.scan_all  -> 4 slot-aware classes: foreign / english_leak /
                                 missing / structural  (incl. niqqud via detect_scripts)
  + an inline V->וי check (protagonist's name must stay Latin 'V')

Read-only on the source JSONs. Writes universal/deterministic_defects.jsonl
+ a by-kind summary.
"""
import os, sys, json, re
from dataclasses import asdict

HERE = os.path.dirname(os.path.abspath(__file__))                 # games/cyberpunk2077
ROOT = os.path.dirname(os.path.dirname(HERE))                     # project root
UNIV = os.path.join(ROOT, "universal")
sys.path.insert(0, HERE)
sys.path.insert(0, UNIV)

import cp2077_qa_defects as Q          # scan_all + Defect
import get_next_audit_batch as G       # paths + build_corpus

OUT = os.path.join(UNIV, "deterministic_defects.jsonl")

# ── V->וי : protagonist name transliterated (calibration showed qwen misses it) ──
VI = re.compile(r"(?<![֐-׿])וי(?![֐-׿])")
V_EN = re.compile(r"(?<![A-Za-z0-9])V(?![A-Za-z0-9])")
V_NEG = re.compile(r"VIP|VTOL|VHS|VPN|V8|V12|V/T|\bAV\b")


def v_transliteration(en, he):
    return bool(VI.search(he or "") and V_EN.search(en or "") and not V_NEG.search(en or ""))


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    defects = []
    # 1) the project's deterministic 4-class scanner, base + DLC
    for tr_p, en_p, proj in ((G.BASE_TR, G.BASE_EN, "base"), (G.DLC_TR, G.DLC_EN, "dlc")):
        try:
            ds = Q.scan_all(load(tr_p), load(en_p))
        except Exception as e:                       # DLC mapping may differ; never abort base
            print(f"[warn] scan_all({proj}) failed: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        for d in ds:
            rec = asdict(d)
            rec["project"] = proj
            defects.append(rec)

    # 2) inline V->וי sweep over the audit's own corpus
    corpus, _b, _d = G.build_corpus()
    v_hits = 0
    for r in corpus:
        if v_transliteration(r.english, r.hebrew):
            v_hits += 1
            defects.append({"section": r.section, "pk": r.pk, "field": r.field,
                            "kind": "v_transliteration", "detail": "V rendered as וי",
                            "value": r.hebrew, "english": r.english, "is_markup": False,
                            "project": r.project})

    with open(OUT, "w", encoding="utf-8") as f:
        for d in defects:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    by_kind = {}
    by_proj = {}
    for d in defects:
        by_kind[d["kind"]] = by_kind.get(d["kind"], 0) + 1
        by_proj[d.get("project", "?")] = by_proj.get(d.get("project", "?"), 0) + 1
    print(f"DETERMINISTIC DEFECTS (no AI): {len(defects)}  -> {os.path.basename(OUT)}")
    print(f"  by kind   : {by_kind}")
    print(f"  by project: {by_proj}")
    print(f"  (V->וי inline hits: {v_hits})")


if __name__ == "__main__":
    main()
