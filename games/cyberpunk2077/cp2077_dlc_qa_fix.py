"""
cp2077_dlc_qa_fix.py
====================
Targeted quality fixer for dlc_ep1_translated.json — only attacks defects
that are *real* failures, not heuristic noise. The DLC scout flagged
several thousand false positives (translated brand names like 'BARGHEST'
→ 'ברגסט', status labels like 'FAILED' → 'נכשל'); those are correct and
left alone.

Three real-defect classes (in priority order):

  UNTRANSLATED      English source, English value still in place (the
                    translator hit 3× validation failure → returned the
                    source unchanged). Re-attempted with a more permissive
                    validator: accepts ANY Hebrew-containing result.
  GARBLED           Hebrew translation but contains a clearly garbled token
                    — e.g. 'מוחBPS' (Hebrew immediately followed by Latin
                    without separator). The LM corrupted the token.
  DOUBLE_LANG       2+ word English run mid-Hebrew that's not a brand —
                    surgical fix: re-translate that fragment with the full
                    line as context, splice back in.
  LENGTH_ANOMALY    translation length < 0.30× or > 2.50× source length —
                    likely truncation or hallucination; full re-translate.

Reuses translate_queue_fast's translate_one + the existing OpenAI client.
Runs against the dlc_ep1_translated.json + dlc_ep1_text.json pair.
Atomic checkpoint every CHECKPOINT_EVERY entries. Writes
`dlc_qa_fix_report.json` with before/after counts.

Run: python cp2077_dlc_qa_fix.py [--dry-run] [--only kinds]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

_HERE = os.path.dirname(os.path.abspath(__file__))

_REPO_ROOT = os.path.dirname(os.path.dirname(_HERE))   # games/<game>/ -> repo root
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import translate_queue_fast as tqf
from openai import OpenAI

RES = os.path.join(_REPO_ROOT, "תרגום_משחקים", "source", "resources")
DLC_FILE = os.path.join(RES, "dlc_ep1_translated.json")
ENG_FILE = os.path.join(RES, "dlc_ep1_text.json")
REPORT_FILE = os.path.join(_HERE, "dlc_qa_fix_report.json")
LOG_FILE = os.path.join(_HERE, "cp2077_dlc_qa_fix.log")
MONITOR_LOG = os.path.join(_HERE, "fix_missing_translations.log")

HEB     = re.compile(r"[֐-׿]")
LATIN   = re.compile(r"[A-Za-z]")
HEB_THEN_LAT = re.compile(r"[֐-׿][A-Za-z]")           # 'מוחB...'
LAT_THEN_HEB = re.compile(r"[A-Za-z][֐-׿]")           # 'Bמוח'
RUN_OF_LATIN = re.compile(r"(?:[A-Za-z]{2,}\s+){1,}[A-Za-z]{2,}")

# Light common-EN set — words whose presence inside a Hebrew line strongly
# suggests the English fragment was left untranslated (real prose words).
COMMON_EN = {
    "the","and","you","your","for","with","from","this","that","they",
    "have","not","but","are","was","were","what","when","where","who",
    "all","one","out","can","get","got","make","made","like","want",
    "need","just","know","time","into","over","than","then","more",
    "some","said","very","much","take","give","come","look","find",
    "back","good","still","only","way","right","left","first","last",
    "next","other","every","after","before","under","about","against",
    "between","through","should","would","could","will","because","since",
    "until","people","life","work","place","thing","things","really",
    "never","always","again","also","there","here","being","done","going",
    "tell","told","ask","asked","try","tried",
}
BRAND_OK = {
    "night","city","arasaka","militech","kang","tao","kiroshi","netwatch",
    "trauma","team","zetatech","biotechnica","petrochem","delamain","afterlife",
    "samurai","johnny","silverhand","alt","rogue","kerry","panam","judy",
    "river","takemura","hanako","yorinobu","saburo","evelyn","dexter","jackie",
    "misty","viktor","regina","padre","wakako","placide","brigitte","adam",
    "smasher","blackwall","relic","ncpd","watson","kabuki","japantown",
    "westbrook","pacifica","heywood","santo","domingo","rancho","coronado",
    "phantom","liberty","dogtown","songbird","solomon","reed","myers",
    "rosalind","hansen","kurt","alex","slider","aurore","cassel","bree",
    "tucker","nele","barghest","nuance","longshore","blackline","fia",
    "luther","horatio","milko","stranger","ware","maxtac","scav","scavs",
    "stranded","jinguji","aldecaldos","wraith","wraiths","valentino",
    "valentinos","maelstrom","tyger","claw","claws","voodoo","boys","animals",
    "moxes","clouds","lizzie","corpo","corpos","fixer","fixers","gonk",
    "netrunner","netrunners","ripperdoc","ripperdocs","output","preem",
}

LM_URL = "http://127.0.0.1:1234/v1"
CHECKPOINT_EVERY = 25
PARALLEL = 4
_save_lock = __import__("threading").Lock()
_log_lock  = __import__("threading").Lock()


def log(msg: str, monitor: bool = True) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with _log_lock:
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
            if monitor:
                with open(MONITOR_LOG, "a", encoding="utf-8") as f:
                    f.write(msg + "\n")
        except OSError:
            pass
        try:
            print(msg, flush=True)
        except Exception:
            pass


# ── defect detection ──────────────────────────────────────────────────────────
def is_untranslated(src: str, trans: str) -> bool:
    """English source, no Hebrew in translation — equals or echoes source."""
    if not src or not LATIN.search(src):
        return False
    # source has at least one real word (not a code)
    real_words = [w for w in re.findall(r"[A-Za-z]{3,}", src)
                  if w.lower() in COMMON_EN]
    if not real_words:
        return False
    return not HEB.search(trans or "")


def is_garbled(src: str, trans: str) -> bool:
    """Hebrew translation whose tokens clearly mix scripts without space —
    e.g. 'מוחBPS' (Hebrew letters then Latin with no break)."""
    if not trans or not HEB.search(trans):
        return False
    # tag/placeholder content is allowed to abut Hebrew (it's a tag, not Latin
    # mid-Hebrew prose). Strip tags/placeholders before the abut-check.
    bare = re.sub(r"<[^<>]+>|\{[^{}]+\}|%[a-zA-Z]", "", trans)
    return bool(HEB_THEN_LAT.search(bare) or LAT_THEN_HEB.search(bare))


def english_run(trans: str) -> str | None:
    """Returns the offending English run inside a Hebrew translation, or None."""
    if not trans or not HEB.search(trans):
        return None
    for m in RUN_OF_LATIN.finditer(trans):
        words = [w.lower() for w in m.group(0).split()]
        if all(w in BRAND_OK for w in words):
            continue
        if any(w in COMMON_EN for w in words):
            return m.group(0)
    return None


def length_off(src: str, trans: str) -> bool:
    if not src or not trans or len(src) < 20:
        return False
    r = len(trans) / max(1, len(src))
    return r < 0.30 or r > 2.50


def classify(src: str, trans: str) -> str | None:
    if is_untranslated(src, trans):
        return "UNTRANSLATED"
    if is_garbled(src, trans):
        return "GARBLED"
    if english_run(trans):
        return "DOUBLE_LANG"
    if length_off(src, trans):
        return "LENGTH_ANOMALY"
    return None


# ── re-translation strategies ─────────────────────────────────────────────────
def lenient_valid(orig: str, result: str) -> bool:
    """Permissive: result must contain Hebrew, must not be identical to source,
    must preserve tags. Used for UNTRANSLATED rescue."""
    if not result or result == orig:
        return False
    if not HEB.search(result):
        return False
    if not tqf.check_tags_preserved(orig, result):
        return False
    return True


def garbled_clean(orig: str, result: str) -> bool:
    """Strict gate on garbled output: result must (a) pass normal validation
    AND (b) not be itself garbled (no Hebrew-Latin or Latin-Hebrew abuts after
    stripping tags). Otherwise the 'fix' just reproduces the bug."""
    if not tqf.is_valid_translation(orig, result):
        return False
    bare = re.sub(r"<[^<>]+>|\{[^{}]+\}|%[a-zA-Z]", "", result)
    return not (HEB_THEN_LAT.search(bare) or LAT_THEN_HEB.search(bare))


def auto_pad_script_seams(s: str) -> str:
    """Insert a single space at every Hebrew↔Latin seam outside tags. Cheap
    deterministic patch — turns 'וreed' into 'ו reed' so the bidi renderer
    can break the run cleanly."""
    out = []
    i = 0
    while i < len(s):
        out.append(s[i])
        if i + 1 < len(s):
            a, b = s[i], s[i + 1]
            if (HEB.match(a) and b.isascii() and b.isalpha()) or \
               (a.isascii() and a.isalpha() and HEB.match(b)):
                out.append(" ")
        i += 1
    return "".join(out)


def retranslate_strict(text: str, retries: int = 3) -> str | None:
    """Up to `retries` passes; accept only when normal-valid AND not garbled.
    Final fallback: auto-pad the script seams on the last attempt."""
    last = None
    for _ in range(retries):
        try:
            out = tqf.translate_one(text)
        except Exception:                                   # noqa: BLE001
            continue
        if not out or out == text:
            continue
        last = out
        if garbled_clean(text, out):
            return out
    if last and tqf.is_valid_translation(text, last):
        padded = auto_pad_script_seams(last)
        if garbled_clean(text, padded):
            return padded
    return None


def retranslate_lenient(text: str) -> str | None:
    """Up to 3 passes; accept anything with Hebrew that preserves tags and
    has no garbled script seams."""
    for _ in range(3):
        try:
            out = tqf.translate_one(text)
        except Exception:                                   # noqa: BLE001
            continue
        if lenient_valid(text, out) and garbled_clean(text, out):
            return out
    return None


def fix_double_lang(src: str, trans: str, run: str) -> str | None:
    """Translate the offending English fragment in context, splice back."""
    prompt = (
        f"In the following Hebrew sentence, only the English fragment "
        f'"{run}" is left untranslated. Translate ONLY that fragment to '
        f"Hebrew. Output the Hebrew translation of that fragment alone, "
        f"with no extra words.\n\nFull line: {trans}"
    )
    try:
        fix = tqf.translate_one(prompt)
    except Exception:                                       # noqa: BLE001
        return None
    if not fix or not HEB.search(fix):
        return None
    # guard against prompt-echo: if the LM returned a string containing our
    # own meta-text (it sometimes parrots the instruction), reject it.
    if "following Hebrew sentence" in fix or "Translate ONLY" in fix:
        return None
    spliced = trans.replace(run, fix.strip(), 1)
    if not tqf.is_valid_translation(src, spliced):
        return None
    return spliced if garbled_clean(src, spliced) else auto_pad_script_seams(spliced)


def fix_one(kind: str, src: str, trans: str) -> tuple[str, str | None]:
    """Returns (kind, new_trans_or_None_if_unfixable)."""
    if kind == "GARBLED":
        # Auto-pad the Hebrew↔Latin seams. ALWAYS accept the padded result
        # for a GARBLED entry — the only change is inserting spaces between
        # adjacent letters of different scripts; it never deletes or
        # reorders text, and the bidi renderer needs the space to break the
        # run cleanly. This is dramatically cheaper than an LM round-trip
        # and never regresses an already-flagged entry.
        padded = auto_pad_script_seams(trans)
        if padded == trans:
            return (kind, None)        # nothing to pad — should not happen
        return (kind, padded)
    if kind == "UNTRANSLATED":
        return (kind, retranslate_strict(src) or retranslate_lenient(src))
    if kind == "LENGTH_ANOMALY":
        return (kind, retranslate_strict(src))
    if kind == "DOUBLE_LANG":
        run = english_run(trans)
        return (kind, fix_double_lang(src, trans, run) if run else None)
    return (kind, None)


# ── pipeline ──────────────────────────────────────────────────────────────────
def load_pair() -> tuple[dict, dict]:
    with open(DLC_FILE, "r", encoding="utf-8") as f:
        dlc = json.load(f)
    with open(ENG_FILE, "r", encoding="utf-8") as f:
        eng = json.load(f)
    eng_idx: dict = {}
    for sec, rows in eng.items():
        if not isinstance(rows, list):
            continue
        idx = {}
        for e in rows:
            if isinstance(e, dict):
                pk = str(e.get("primaryKey", ""))
                if pk:
                    idx[pk] = e
        eng_idx[sec] = idx
    return dlc, eng_idx


def collect_defects(dlc: dict, eng_idx: dict, only: set | None) -> list:
    """[(section, entry, field, src, trans, kind)] for every flagged entry."""
    out = []
    for sec, rows in dlc.items():
        if not isinstance(rows, list):
            continue
        ek = eng_idx.get(sec, {})
        for e in rows:
            if not isinstance(e, dict):
                continue
            src_e = ek.get(str(e.get("primaryKey", "")), {})
            for fld in ("femaleVariant", "maleVariant"):
                trans = e.get(fld) or ""
                src   = src_e.get(fld) or e.get("secondaryKey") or ""
                if not trans:
                    continue
                kind = classify(src, trans)
                if kind and (not only or kind in only):
                    out.append((sec, e, fld, src, trans, kind))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Detect + report only; no LM calls, no writes.")
    ap.add_argument("--only", default="",
                    help="Comma-separated kinds to fix "
                         "(UNTRANSLATED,GARBLED,DOUBLE_LANG,LENGTH_ANOMALY). "
                         "Default: all four.")
    args = ap.parse_args()
    only = {k.strip() for k in args.only.split(",") if k.strip()} or None

    log("=" * 70, monitor=False)
    log(f"cp2077_dlc_qa_fix starting{'  (DRY)' if args.dry_run else ''}",
        monitor=False)

    log("[*] loading DLC + English source", monitor=False)
    dlc, eng_idx = load_pair()

    defects = collect_defects(dlc, eng_idx, only)
    # process GARBLED first (deterministic auto-pad, instant), then LM-based
    # kinds. Otherwise the slow LM calls block the worker pool and the
    # instant fixes wait for hours behind them.
    _ORDER = {"GARBLED": 0, "DOUBLE_LANG": 1, "LENGTH_ANOMALY": 2, "UNTRANSLATED": 3}
    defects.sort(key=lambda d: _ORDER.get(d[5], 9))
    by_kind = Counter(d[5] for d in defects)
    log(f"[*] {len(defects):,} defects: " +
        " ".join(f"{k}={v}" for k, v in by_kind.items()))
    if args.dry_run or not defects:
        report = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dry_run": args.dry_run,
            "by_kind": dict(by_kind),
            "fixed": 0,
            "samples": [
                {"section": d[0], "pk": d[1].get("primaryKey"),
                 "field": d[2], "kind": d[5],
                 "src": (d[3] or "")[:120],
                 "trans": (d[4] or "")[:120]}
                for d in defects[:200]
            ],
        }
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        log(f"report -> {REPORT_FILE}")
        return 0

    # Live LM client (matches the translator's setup)
    client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=600)
    tqf.lm_client = client
    tqf.TEMPERATURE = tqf.DEFAULT_TEMP

    log("[*] Using LM Studio (Gemma-2-27b)", monitor=True)
    log(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]", monitor=True)
    log("[*] Preflight …", monitor=False)
    try:
        tqf.translate_one("Apply")
    except Exception as e:                                  # noqa: BLE001
        log(f"FATAL: cannot reach LM Studio — {e}")
        return 1
    log("[*] Preflight OK", monitor=False)

    fixed = 0
    failed_per_kind = Counter()

    def _job(item):
        sec, e, fld, src, trans, kind = item
        return (item, fix_one(kind, src, trans))

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        futs = [pool.submit(_job, it) for it in defects]
        for fut in as_completed(futs):
            (sec, entry, fld, src, trans, kind), (_, new) = fut.result()
            if new and new != trans:
                with _save_lock:
                    entry[fld] = new
                fixed += 1
                log(f"  dlc-qa[{kind[:4]}] {src[:30]!r} → {new[:46]!r}")
            else:
                failed_per_kind[kind] += 1
            if (fixed + sum(failed_per_kind.values())) % CHECKPOINT_EVERY == 0:
                with _save_lock:
                    tqf._atomic_write_json(DLC_FILE, dlc)
                log(f"  [~] Saved — {fixed:,} fixed, "
                    f"{sum(failed_per_kind.values()):,} unfixable so far")

    with _save_lock:
        tqf._atomic_write_json(DLC_FILE, dlc)

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dry_run": False,
        "by_kind_before": dict(by_kind),
        "fixed": fixed,
        "unfixable_by_kind": dict(failed_per_kind),
    }
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"[*] Done. Fixed {fixed:,} entries. report -> {REPORT_FILE}")
    log("=" * 70, monitor=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
