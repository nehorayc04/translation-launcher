"""
fix_ingame_defects.py
=====================
Targeted deterministic fixes for the in-game defects the user reported
after a play session on v1.0.1:

  1. CUERPO  — LM translated English "melee" → Spanish "cuerpo a cuerpo"
              instead of Hebrew. Search-and-replace all variants with
              the correct Hebrew equivalent.
  2. V_TO_V  — LM transliterated the protagonist's name "V" → "וי".
              Only fix when the English source uses standalone "V"
              (not "VIP", "AV", "V for victory", etc.).
  3. KAMYON  — Creole "kamyonèt" (truck) is in the English source too;
              CDPR keeps Voodoo-Boys dialogue Creole-laced intentionally.
              We **transliterate** to Hebrew so it reads naturally in
              an RTL line: kamyonèt → קמיונט (instead of leaving Latin
              mid-Hebrew).

No LM calls — everything is deterministic. Writes both spine JSONs
atomically. Does NOT bake (deferred until v1.0.2 release).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import translate_queue_fast as tqf

RES = os.path.join(HERE, "תרגום_משחקים", "source", "resources")
BASE_TR  = os.path.join(RES, "localization_translated.json")
BASE_EN  = os.path.join(RES, "localization_export.json")
DLC_TR   = os.path.join(RES, "dlc_ep1_translated.json")
DLC_EN   = os.path.join(RES, "dlc_ep1_text.json")
REPORT   = os.path.join(HERE, "fix_ingame_defects_report.json")

# ── 1. CUERPO → קרב פנים אל פנים ────────────────────────────────────────────
# The LM produced Spanish for the English word "melee". Three forms appear:
#   "cuerpo a cuerpo"   "cuerpo-a-cuerpo"   "cuerpo a cuerpo,"
# Case-insensitive. Replacement keeps surrounding punctuation untouched.
CUERPO_RE = re.compile(r"\bcuerpo[- ]a[- ]cuerpo\b", re.IGNORECASE)
CUERPO_REPL = "פנים אל פנים"


# ── 2. V → V (protagonist name) ─────────────────────────────────────────────
# Standalone Hebrew "וי" surrounded by space or punctuation, when the
# corresponding English source contains a standalone "V" (NOT VIP, AV, etc.).
VEY_RE = re.compile(r"(^|[\s.,:;!?\"'(\[])וי([\s.,:;!?\"')\]]|$)")
SOURCE_HAS_STANDALONE_V = re.compile(r"(^|[\s.,:;!?\"'(\[])V([\s.,:;!?\"')\]]|$)")
# Words in the EN source that mean "וי" should be left as-is (legitimate
# transliterations): VIP, AV, VFX, VR, V8, V12 (engine), V/T (vert/T), etc.
NEGATIVE_EN_CONTEXTS = re.compile(
    r"\b(V[\.]?I[\.]?P|A\.?V|V[\.]?F[\.]?X|V\.?R|V\d|V/[A-Z]|"
    r"V[- ]?for[- ]?Victory|VTOL|VHS|VPN|V8|V12)\b", re.IGNORECASE)


# ── 3. KAMYONÈT (Creole "truck") → קמיונט ──────────────────────────────────
# Leave the Creole flavor (it's authored that way), but transliterate so
# the bidi renderer can flow the line cleanly.
KAMYON_MAP = {
    "kamyonèt": "קמיונט",
    "kamyonet":  "קמיונט",
    "kamyon":    "קמיון",
}
KAMYON_RE = re.compile(r"\bkamyon(?:èt|et)?\b", re.IGNORECASE)
def kamyon_repl(m):
    word = m.group(0).lower()
    return KAMYON_MAP.get(word, word)


# ── core ────────────────────────────────────────────────────────────────────

def apply_cuerpo(s: str) -> tuple[str, int]:
    n = len(CUERPO_RE.findall(s or ""))
    return (CUERPO_RE.sub(CUERPO_REPL, s) if n else s, n)


def apply_v_fix(he: str, en: str) -> tuple[str, int]:
    """Replace standalone Hebrew 'וי' with Latin 'V' only when the EN source
    contains a standalone 'V' AND no negative-context disambiguator."""
    if not he or not en:
        return (he, 0)
    if NEGATIVE_EN_CONTEXTS.search(en):
        return (he, 0)
    if not SOURCE_HAS_STANDALONE_V.search(en):
        return (he, 0)
    n_before = len(VEY_RE.findall(he))
    if not n_before:
        return (he, 0)
    new = VEY_RE.sub(lambda m: f"{m.group(1)}V{m.group(2)}", he)
    return (new, n_before)


def apply_kamyon(s: str) -> tuple[str, int]:
    n = len(KAMYON_RE.findall(s or ""))
    return (KAMYON_RE.sub(kamyon_repl, s) if n else s, n)


def fix_pair(tr_path: str, en_path: str, project: str) -> dict:
    with open(tr_path, "r", encoding="utf-8") as f:
        tr = json.load(f)
    with open(en_path, "r", encoding="utf-8") as f:
        en = json.load(f)
    en_idx = {}
    for sec, rows in en.items():
        if not isinstance(rows, list):
            continue
        d = {}
        for e in rows:
            if not isinstance(e, dict):
                continue
            for key in ("primaryKey", "stringId"):
                v = e.get(key)
                if v not in (None, ""):
                    d[str(v)] = e
        en_idx[sec] = d

    counts = Counter()
    for sec, rows in tr.items():
        if not isinstance(rows, list):
            continue
        ek = en_idx.get(sec, {})
        for e in rows:
            if not isinstance(e, dict):
                continue
            src_e = (ek.get(str(e.get("primaryKey", ""))) or
                     ek.get(str(e.get("stringId", ""))) or {})
            for fld in ("femaleVariant", "maleVariant"):
                he = e.get(fld) or ""
                if not he:
                    continue
                en_v = src_e.get(fld) or e.get("secondaryKey") or ""
                changed = False

                he2, n = apply_cuerpo(he)
                if n:
                    counts["cuerpo"] += n
                    counts["cuerpo_entries"] += 1
                    he = he2
                    changed = True

                he2, n = apply_v_fix(he, en_v)
                if n:
                    counts["v_to_V"] += n
                    counts["v_to_V_entries"] += 1
                    he = he2
                    changed = True

                he2, n = apply_kamyon(he)
                if n:
                    counts["kamyon"] += n
                    counts["kamyon_entries"] += 1
                    he = he2
                    changed = True

                if changed:
                    e[fld] = he

    tqf._atomic_write_json(tr_path, tr)
    counts["project"] = project
    return dict(counts)


def main() -> int:
    print("[*] Applying deterministic in-game defect fixes (no LM)…")
    base = fix_pair(BASE_TR, BASE_EN, "base")
    dlc  = fix_pair(DLC_TR, DLC_EN, "dlc")
    print(f"  BASE: {base}")
    print(f"  DLC : {dlc}")
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"base": base, "dlc": dlc}, f, ensure_ascii=False, indent=2)
    print(f"[*] report -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
