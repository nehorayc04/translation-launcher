#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""qa_scan.py — QA the community-compute Hogwarts hebrew.json BEFORE it ships.

Classifies every line into four buckets and writes actionable artifacts. It NEVER
translates (delegate-all-translation) — it recovers ONLY deterministically-safe
panel leaks, and lists everything else for a fleet RE-QUEUE.

Buckets:
  OK            — has Hebrew, no reference-panel leak. ship as-is.
  SAFE_RECOVER  — a leaked panel where, after stripping every "XX:" label line,
                  the ENTIRE remainder is Hebrew (no Latin/Arabic run, no residual
                  label). deterministic strip -> clean Hebrew. applied with --fix.
  RETRANS       — needs the fleet to redo it: an unrecoverable panel leak, an
                  untranslated Arabic-prose line (arAE skeleton passthrough), or an
                  untranslated English-prose line. -> requeue_keys.json
  PASSTHROUGH   — legit no-Hebrew: pure token/tag line, a keyboard-key label, an
                  italic spell name, a bare brand/acronym. the game's own Arabic
                  keeps these Latin too. leave untouched, do NOT requeue.

Usage:
  python qa_scan.py            # report + write requeue_keys.json + recover_preview.json
  python qa_scan.py --fix      # + apply SAFE_RECOVER into hebrew.json (backup first)
"""
import argparse, json, re, shutil, time
from pathlib import Path
from collections import Counter

HERE = Path(__file__).resolve().parent
EX = HERE.parent / "extract"
HE_PATH = HERE / "hebrew.json"

# HARD engine tokens that must survive verbatim (excluding [[dialogue choice]], which
# is translatable). A mismatch vs the English source = a broken/translated token.
_HARD = re.compile(r"\{[^}]*\}|<[^>]+>|%[#0-9.\*\-\+ ]*[a-zA-Z]|&[a-z]+;|\[[^\]]+\]")
_CHOICE = re.compile(r"\[\[.*?\]\]", re.S)
def _toks(s):
    return Counter(_HARD.findall(_CHOICE.sub(" ", s)))
try:
    _EN_MAIN = json.loads((EX / "main_en.json").read_text(encoding="utf-8"))
    _EN_SUB = json.loads((EX / "sub_en.json").read_text(encoding="utf-8"))
except Exception:
    _EN_MAIN = _EN_SUB = {}
def _en(k):
    p, b = k.split(":", 1)
    return (_EN_MAIN if p == "MAIN" else _EN_SUB).get(b)
def token_broken(k, hv):
    ev = _en(k)
    return ev is not None and _toks(ev) != _toks(hv)

HEB = re.compile(r"[֐-׿]")
ARB = re.compile(r"[؀-ۿ]")
LAT = re.compile(r"[A-Za-z]")
LABEL_LINE = re.compile(r"(?im)^\s*(EN|AR|RU|PL|DE|FR|ES|IT|PT|CS|NL)\s*:\s*")
# tokens/tags/placeholders the game keeps verbatim
TOK = re.compile(r"<[^>]+>|\{[^}]*\}|\[[^\]]*\]|\|[A-Za-z0-9_]+|&[a-z]+;|%[sd]")
KEYNAME = re.compile(r"_Pronunciation$")

def core(s):
    return TOK.sub(" ", s)

def has_any_letter(s):
    return bool(re.search(r"[A-Za-z֐-׿؀-ۿ]", core(s)))

def try_recover(v):
    """Deterministically recover a leaked panel, or None if unsafe.

    Split on label-line boundaries into label-stripped bodies. SAFE when:
      (a) exactly one pure-Hebrew body (no Latin/Arabic run) and NO foreign prose
          -> return that Hebrew; or
      (b) no Hebrew bodies and no foreign prose but >=1 token-only body (a leaked
          panel around a pure token like `<img .../>`, which needs no translation)
          -> return that token body.
    Anything with a nested label, or competing foreign prose, is UNSAFE (-> None).
    """
    if not LABEL_LINE.search(v):
        return None
    segs = re.split(r"(?im)(?=^\s*(?:EN|AR|RU|PL|DE|FR|ES|IT|PT|CS|NL)\s*:)", v)
    heb_bodies, token_bodies, foreign_prose = [], [], 0
    for seg in segs:
        m = re.match(r"(?is)^\s*(?:EN|AR|RU|PL|DE|FR|ES|IT|PT|CS|NL)\s*:\s*(.*)$", seg)
        body = (m.group(1) if m else seg).strip()
        if not body:
            continue
        if LABEL_LINE.search(body):   # nested label -> unsafe
            return None
        if not has_any_letter(body):
            token_bodies.append(body)
        elif HEB.search(body) and not LAT.search(core(body)) and not ARB.search(body):
            heb_bodies.append(body)
        else:
            foreign_prose += 1
    if foreign_prose:
        return None
    if len(heb_bodies) == 1:
        return heb_bodies[0]
    if not heb_bodies and token_bodies:
        return token_bodies[0]
    return None

def is_passthrough(k, v):
    if KEYNAME.search(k):                     # keyboard-key pronunciation label
        return True
    if not has_any_letter(v):                 # pure token/tag/glyph
        return True
    stripped = re.sub(r"</?i>", "", v).strip()
    # bare italic spell name (Latin, one/two words) — game keeps it Latin
    if re.fullmatch(r"[A-Za-z][A-Za-z '!\.]{0,30}", stripped):
        return True
    # brand / tech / acronym label with NO lowercase prose (AMD FSR 3, FidelityFX CAS,
    # DLSS, XeSS 1.0) — the game's own Arabic keeps these Latin
    if re.search(r"[A-Za-z]", stripped) and not re.search(r"[a-z]", stripped):
        return True
    return False

def main(fix):
    he = json.loads(HE_PATH.read_text(encoding="utf-8"))
    buckets = {"OK": 0, "SAFE_RECOVER": [], "RETRANS": [], "PASSTHROUGH": 0}
    retrans_reason = {"panel_leak": 0, "arabic": 0, "english": 0}
    for k, v in he.items():
        if not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False)
        leak = bool(LABEL_LINE.search(v))
        if HEB.search(v) and not leak:
            buckets["OK"] += 1
            continue
        if leak:
            rec = try_recover(v)
            if rec is not None:
                buckets["SAFE_RECOVER"].append((k, rec))
            else:
                buckets["RETRANS"].append(k); retrans_reason["panel_leak"] += 1
            continue
        # no Hebrew, no leak
        if is_passthrough(k, v):
            buckets["PASSTHROUGH"] += 1
        elif ARB.search(v):
            buckets["RETRANS"].append(k); retrans_reason["arabic"] += 1
        elif LAT.search(v):
            buckets["RETRANS"].append(k); retrans_reason["english"] += 1
        else:
            buckets["PASSTHROUGH"] += 1

    print(f"total lines           {len(he)}")
    print(f"  OK (has Hebrew)     {buckets['OK']}")
    print(f"  SAFE_RECOVER        {len(buckets['SAFE_RECOVER'])}  (deterministic strip -> clean Hebrew)")
    print(f"  RETRANS (re-queue)  {len(buckets['RETRANS'])}"
          f"   [panel-leak {retrans_reason['panel_leak']} | arabic {retrans_reason['arabic']}"
          f" | english {retrans_reason['english']}]")
    print(f"  PASSTHROUGH (legit) {buckets['PASSTHROUGH']}")
    tb = sum(1 for k, v in he.items() if isinstance(v, str) and token_broken(k, v))
    print(f"  TOKEN-BROKEN        {tb}   (run token_fix.py: {{...}}/<tag> mismatch vs EN source)")

    (HERE / "requeue_keys.json").write_text(
        json.dumps(sorted(buckets["RETRANS"]), ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "recover_preview.json").write_text(
        json.dumps(dict(buckets["SAFE_RECOVER"]), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwrote requeue_keys.json ({len(buckets['RETRANS'])}) + recover_preview.json ({len(buckets['SAFE_RECOVER'])})")

    if fix and buckets["SAFE_RECOVER"]:
        bak = HE_PATH.with_suffix(f".json.bak.qa.{time.strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(HE_PATH, bak)
        for k, rec in buckets["SAFE_RECOVER"]:
            he[k] = rec
        HE_PATH.write_text(json.dumps(he, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"FIXED {len(buckets['SAFE_RECOVER'])} lines into hebrew.json (backup {bak.name})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    main(ap.parse_args().fix)
