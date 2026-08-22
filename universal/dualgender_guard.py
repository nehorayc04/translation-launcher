# -*- coding: utf-8 -*-
"""
dualgender_guard.py — QA guard for CP2077 male/female (V-gender) variant pairs.

The live dual-gender run translates each spine entry's femaleVariant + maleVariant.
~95% are textbook gender inflections (differ ONLY in the gendered morpheme —
קחי/קח, דברי/דבר). But ~4-5% were translated INDEPENDENTLY and diverged in WORD
CHOICE or NUMBER, not just gender — the real defect class:
    Wait Here -> חכו / חכה   (female is PLURAL, should be חכי)
    Reach     -> טווח / הגעה  (two different words, neither a gender pair)
    Drink     -> לשתות / שתייה (infinitive vs noun — not a gender pair at all)

This guard scans every f != m pair (both non-empty, both Hebrew) and flags the ones
that are NOT a clean gender inflection, worst-first, into a worklist. It does NOT
translate — per the standing rule the guard IDENTIFIES; a delegated agent/LM pass
re-inflects M as the masculine form of F (the worklist carries EN + both variants).

Checks:
  token_mismatch  placeholders/tags multiset differs between f and m (structural)
  low_similarity  SequenceMatcher(f,m) ratio < THRESH  -> different word choice
  number_morph    female imperative ends in plural vav while male doesn't (חכו/חכה)
  niqqud          vowel points in either variant
  foreign         a real non-Hebrew/Latin script leak (punctuation/RLM excluded)
  length_anomaly  len ratio far from 1 (truncated source / divergent expansion)

CLI:
  python dualgender_guard.py selftest
  python dualgender_guard.py scan            # scan base+DLC spine, write worklist
  python dualgender_guard.py scan --thresh 0.55 --limit-samples 30
"""
from __future__ import annotations
import argparse, json, os, re, sys, difflib
from collections import Counter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "visual_bridge"))
try:
    from gender_filter import classify as _classify   # is the EN even gender-ambiguous?
except Exception:
    _classify = None
ROOT = os.path.dirname(HERE)
RES = os.path.join(ROOT, "תרגום_משחקים",
                   "source", "resources")
HE_BASE = os.path.join(RES, "localization_translated.json")
HE_DLC = os.path.join(RES, "dlc_ep1_translated.json")
EN_BASE = os.path.join(ROOT, "Game Lab", "Cyberpunk 2077", "localization_export.json")
EN_DLC = os.path.join(RES, "dlc_ep1_text.json")
OUT = os.path.join(HERE, "cp2077_dualgender_suspects.jsonl")

TOKEN = re.compile(r"\{[^}]*\}|<[^>]+>|%[sd%]|&rlm;|&[a-z]+;|\\n")
NIQQUD = re.compile("[֑-ׇ]")
HEB = re.compile("[א-ת]")
_VAV = "ו"   # final letter of a plural imperative (חכו)

# a "foreign" char is anything NOT: whitespace, ASCII printable (incl. Latin),
# the Hebrew block, or a handful of common typographic marks (dash/quote/…/RLM).
_ALLOWED_CP = {0x2013, 0x2014, 0x2011, 0x2018, 0x2019, 0x201c, 0x201d,
               0x2026, 0x2022, 0x200e, 0x200f, 0x00a0, 0x2212, 0x2122, 0x00ae}


def _is_allowed(c: str) -> bool:
    if c.isspace():
        return True
    o = ord(c)
    if 0x20 <= o <= 0x7e:        # ASCII printable (Latin, digits, punctuation)
        return True
    if 0x0590 <= o <= 0x05ff:    # Hebrew block
        return True
    if 0x00a1 <= o <= 0x00ff and o not in (0x00d7, 0x00f7):
        return True              # Latin-1 accented letters (ñ é ó — legit names)
    return o in _ALLOWED_CP


def toks(s: str) -> list:
    return sorted(TOKEN.findall(s))


def foreign_chars(s: str) -> list:
    # strip tags/placeholders first — a <kiroshi o="日本語"> tag legitimately holds
    # foreign audio text; we only care about a leak in the VISIBLE Hebrew.
    visible = TOKEN.sub(" ", s)
    return sorted({c for c in visible if not _is_allowed(c)})


def first_heb_word(s: str) -> str:
    for w in s.split():
        h = "".join(c for c in w if 0x05d0 <= ord(c) <= 0x05ea)
        if h:
            return h
    return ""


_ENG = re.compile(r"[A-Za-z]{3,}")


def _english_words(s: str) -> int:
    return len(_ENG.findall(TOKEN.sub(" ", s)))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\\n", " ").replace("\n", " ")).strip()


def categorize(en: str, f: str, m: str, reasons: list) -> str:
    """Bucket a suspect into a concrete ACTION.

    stale_english_m — the male variant still holds untranslated English → redo M
    newline_norm    — the only real difference is \\n-vs-newline/whitespace → deterministic
    long_divergent  — a document/letter/lore split into two independent translations;
                      it does NOT depend on V's gender → COLLAPSE to one (no translation)
    gender_redo     — a short line whose gender inflection genuinely diverged → re-inflect M
    token_only      — only a dropped/added tag wrapper differs → structural fix
    review          — anything else
    """
    kinds = {r[0] for r in reasons}
    if _english_words(m) - _english_words(f) >= 3:
        return "stale_english_m"
    # ONLY when identical after newline/whitespace normalization — otherwise a real
    # gender diff (מוכן/מוכנה) hides under the formatting diff and must NOT be collapsed.
    if _norm(f) == _norm(m):
        return "newline_norm"
    if kinds == {"token_mismatch"}:
        return "token_only"
    # principled split: is the ENGLISH even gender-ambiguous?
    #   neutral  -> it should NEVER have been differentiated -> COLLAPSE (M = F)
    #   ambiguous-> the split is legit but diverged -> re-inflect M from F
    amb = _classify(en).ambiguous if (_classify and en) else True
    if not amb:
        return "collapse"
    return "gender_redo" if len(f.split()) <= 6 else "gender_redo_long"


def check_pair(f: str, m: str, thresh: float = 0.5) -> list:
    """Return a list of (reason, detail, weight) for a differentiated pair."""
    reasons = []
    if toks(f) != toks(m):
        reasons.append(("token_mismatch", f"{toks(f)} != {toks(m)}", 100))
    fc = foreign_chars(m) + foreign_chars(f)
    if fc:
        reasons.append(("foreign", "".join(fc), 80))
    if NIQQUD.search(m) or NIQQUD.search(f):
        reasons.append(("niqqud", "", 70))
    ratio = difflib.SequenceMatcher(None, f, m).ratio()
    if ratio < thresh:
        reasons.append(("low_similarity", f"{ratio:.2f}",
                        60 + int((thresh - ratio) * 40)))
    else:
        # number-morphology: short pair, female first word ends in plural vav
        # while male doesn't — the חכו/חכה class not caught by low_similarity.
        if len(f.split()) <= 3 and len(m.split()) <= 3:
            fw, mw = first_heb_word(f), first_heb_word(m)
            if fw.endswith(_VAV) and not mw.endswith(_VAV) and fw[:-1] and mw:
                reasons.append(("number_morph", f"{fw}/{mw}", 50))
    lf, lm = len(f), len(m)
    if lf and lm:
        r = max(lf, lm) / min(lf, lm)
        if r > 1.6 and "token_mismatch" not in [x[0] for x in reasons]:
            reasons.append(("length_anomaly", f"{lf}/{lm}", 40))
    return reasons


# ── spine / EN loading ───────────────────────────────────────────────────────
def _jl(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception as e:
        print(f"  load-fail {os.path.basename(p)}: {e}")
        return {}


def _entry_key(e):
    pk = e.get("primaryKey")
    return str(pk) if pk is not None else str(e.get("stringId"))


def _en_index(d):
    idx = {}
    for sec, rows in d.items():
        if not isinstance(rows, list):
            continue
        m = {}
        for e in rows:
            if isinstance(e, dict):
                v = (e.get("femaleVariant") or e.get("maleVariant") or "").strip()
                m[_entry_key(e)] = v
        idx[sec] = m
    return idx


def scan(thresh: float, limit_samples: int) -> int:
    print("loading spine + EN sources...")
    spines = [("base", _jl(HE_BASE)), ("dlc", _jl(HE_DLC))]
    en = _en_index(_jl(EN_BASE))
    end = _en_index(_jl(EN_DLC))

    def en_for(sec, kid, entry):
        v = en.get(sec, {}).get(kid) or end.get(sec, {}).get(kid)
        if v:
            return v
        return (entry.get("secondaryKey") or "").strip()

    total_pairs = clean = 0
    suspects = []
    reason_counts = Counter()
    for tag, spine in spines:
        for sec, rows in spine.items():
            if not isinstance(rows, list):
                continue
            if sec.split("/")[-1] == "onscreens.json":
                continue  # dedup mirror (keep onscreens_final)
            for e in rows:
                if not isinstance(e, dict):
                    continue
                f = (e.get("femaleVariant") or "").strip()
                m = (e.get("maleVariant") or "").strip()
                if not f or not m or f == m:
                    continue
                if not (HEB.search(f) and HEB.search(m)):
                    continue
                total_pairs += 1
                rs = check_pair(f, m, thresh)
                if not rs:
                    clean += 1
                    continue
                kid = _entry_key(e)
                score = sum(w for _, _, w in rs)
                for name, _, _ in rs:
                    reason_counts[name] += 1
                en_src = en_for(sec, kid, e)
                suspects.append({
                    "src": tag, "section": sec, "key": kid,
                    "secondaryKey": e.get("secondaryKey", ""),
                    "en": en_src,
                    "he_female": f, "he_male": m,
                    "bucket": categorize(en_src, f, m, rs),
                    "reasons": [{"kind": n, "detail": d} for n, d, _ in rs],
                    "score": score,
                })
    suspects.sort(key=lambda x: -x["score"])
    bucket_counts = Counter(s["bucket"] for s in suspects)
    with open(OUT, "w", encoding="utf-8") as fh:
        for s in suspects:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    pct = 100.0 * len(suspects) / max(total_pairs, 1)
    print("=" * 60)
    print(f"differentiated pairs scanned (f != m) : {total_pairs:,}")
    print(f"clean gender inflections              : {clean:,}  ({100-pct:.1f}%)")
    print(f"SUSPECT (need re-do)                  : {len(suspects):,}  ({pct:.1f}%)")
    print("\nby reason (a pair can trip several):")
    for k, v in reason_counts.most_common():
        print(f"    {k:16s}: {v:,}")
    print("\nby ACTION bucket:")
    _desc = {
        "collapse": "EN is gender-NEUTRAL -> should never be split -> set M = F",
        "gender_redo": "short gendered line diverged -> re-inflect M from F (delegate)",
        "gender_redo_long": "long gendered text diverged -> re-inflect M from F (delegate)",
        "stale_english_m": "male variant still English -> redo M (delegate)",
        "newline_norm": "identical except \\n-vs-newline -> deterministic normalize",
        "token_only": "dropped/added tag wrapper -> structural fix (deterministic)",
        "review": "other -> manual look",
    }
    for k, v in bucket_counts.most_common():
        print(f"    {k:16s}: {v:,}   ({_desc.get(k,'')})")
    print(f"\nworklist -> {OUT}")
    print(f"\n===== TOP {limit_samples} SUSPECTS (worst first) =====")
    for s in suspects[:limit_samples]:
        kinds = ",".join(r["kind"] for r in s["reasons"])
        print(f"  EN : {s['en'][:70]}")
        print(f"  F  : {s['he_female'][:70]}")
        print(f"  M  : {s['he_male'][:70]}")
        print(f"  ->  [{kinds}]  score={s['score']}\n")
    return 0


# ── selftest ─────────────────────────────────────────────────────────────────
def selftest() -> int:
    cases = [
        ("קחי", "קח", False, "kchi/kach clean"),
        ("דברי", "דבר", False, "dabri/daber clean"),
        ("חכו כאן", "חכה פה",
         True, "wait: plural-vav vs sing"),
        ("לשתות", "שתייה",
         True, "drink infinitive vs noun"),
        ("פתחי {0}", "פתח {1}",
         True, "token mismatch"),
        ("סגרי", "סגור", False, "sigri/sgor clean"),
    ]
    ok = True
    for f, m, expect, note in cases:
        rs = check_pair(f, m)
        got = bool(rs)
        st = "OK" if got == expect else "FAIL"
        if got != expect:
            ok = False
        kinds = ",".join(r[0] for r in rs) or "-"
        print(f"[{st}] {note:28s} suspect={got!s:5s} [{kinds}]")
    print("\nSELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dualgender_guard")
    p.add_argument("command", nargs="?", default="selftest", choices=["selftest", "scan"])
    p.add_argument("--thresh", type=float, default=0.5, help="min f~m similarity")
    p.add_argument("--limit-samples", type=int, default=25)
    a = p.parse_args(argv)
    if a.command == "selftest":
        return selftest()
    return scan(a.thresh, a.limit_samples)


if __name__ == "__main__":
    raise SystemExit(main())
