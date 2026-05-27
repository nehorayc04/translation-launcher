"""
cp2077_qa_sweep.py
==================
One-shot QA pass over localization_translated.json: audit -> fix -> re-audit,
looping until the file is clean (or a sane iteration cap is hit).

Detection is delegated entirely to cp2077_qa_defects.scan_all() — the same
library the background watchdog uses, so both flag identically. Fixing reuses
the project's proven re-translators:
  * plain entries  -> patch_615_flagged.translate_clean()  (English-first,
                      sanitize-fallback, strict Cyberpunk prompt)
  * markup entries -> cp2077_markup_translate's FIXED/TRANS slot model
                      (re-translates only the TR slots; foreign o/m attributes
                      and the control byte can never be corrupted)

Every re-translation must re-pass cp2077_qa_defects.value_is_clean() before it
is written back, so a "fix" can never silently introduce a new defect.

Two independent stop conditions: a hard iteration cap, and a no-progress break
(a pass that fixes 0 entries stops immediately — genuinely unfixable strings
are reported in qa_sweep_report.json, never looped on forever).

Usage:
    python cp2077_qa_sweep.py              # real run
    python cp2077_qa_sweep.py --dry-run    # scan + report only, no LM, no write
    python cp2077_qa_sweep.py --max-iterations 8
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import audit_translations as _audit
import cp2077_qa_defects as qa
import cp2077_markup_translate as mk
import patch_615_flagged as p615

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ── paths ───────────────────────────────────────────────────────────────────
SCRIPTS_DIR     = qa._HERE
TRANSLATED_FILE = qa.TRANSLATED_FILE
EXPORT_FILE     = qa.EXPORT_FILE
REPORT_FILE     = os.path.join(SCRIPTS_DIR, "qa_sweep_report.json")
LOG_FILE        = os.path.join(SCRIPTS_DIR, "cp2077_qa_sweep.log")
MONITOR_LOG     = os.path.join(SCRIPTS_DIR, "fix_missing_translations.log")

MAX_ITERATIONS  = 5
SAVE_EVERY      = 50

_log_lines = 0


def log(msg: str, *, monitor: bool = True) -> None:
    """Console + private log, and (when monitor=True) the monitor-watched
    fix_missing_translations.log so the live TUI/website track the sweep."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(msg, flush=True)
    for path, line in (((LOG_FILE, f"[{ts}] {msg}"),) +
                       (((MONITOR_LOG, msg),) if monitor else ())):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


# ── fixing ──────────────────────────────────────────────────────────────────

def _retranslate_markup(value: str, english: str, client) -> str | None:
    """Re-translate a <kiroshi>/<mothertongue>/<Rich> entry. Preferred path:
    parse the English markup, translate its TR slots, reassemble — tags and the
    foreign o/m attributes are copied verbatim. Fallback: sanitize only the
    dirty TR slots of the current value in place."""
    if english and qa.is_markup(english):
        eng_slots = mk.parse_slots(english)
        if eng_slots is not None:
            tr_texts = [t for k, t in eng_slots if k == "TR"]
            if tr_texts:
                hebrew = mk.translate_pieces(tr_texts)
                rebuilt, hi = [], 0
                for kind, text in eng_slots:
                    if kind == "TR":
                        he = hebrew[hi] if hi < len(hebrew) else ""
                        hi += 1
                        rebuilt.append(("TR", he if mk.valid_piece(text, he) else text))
                    else:
                        rebuilt.append((kind, text))
                out = mk.reassemble(rebuilt)
                if qa.value_is_clean(out):
                    return out
    # fallback — sanitize the dirty TR slots of the existing value
    slots = mk.parse_slots(value)
    if slots is None:
        return None
    rebuilt = []
    for kind, text in slots:
        if kind == "TR" and (_audit.detect_scripts(text) or qa.english_leak(text)):
            res, _ = p615.translate_clean(client, english=None, contaminated=text)
            rebuilt.append(("TR", res if (res and mk.valid_piece(text, res)) else text))
        else:
            rebuilt.append((kind, text))
    return mk.reassemble(rebuilt)


ENGLISH_LEAK_PROMPT = (
    "You fix Cyberpunk 2077 Hebrew localization. The user gives ONE line of "
    "game text that is ALREADY mostly Hebrew but still contains a few "
    "untranslated English words. Translate ONLY those leftover English words "
    "into natural Hebrew so the whole line reads as fluent Hebrew.\n"
    "HARD RULES:\n"
    "  - Keep every existing Hebrew word, the word order and the meaning.\n"
    "  - Keep tags (<Rich ...>, <Input ...>), {placeholders}, %s, digits and "
    "punctuation EXACTLY as they are.\n"
    "  - Keep genuine proper nouns / brand names / acronyms (V, Johnny, "
    "Arasaka, NCPD, RAM, BD, FPS) unchanged.\n"
    "  - NEVER use Niqqud vowel-points.\n"
    "  - Output ONLY the corrected line — no quotes, no notes, no <think> tags."
)


_HEB_WORD_RE = re.compile(r"[א-ת]{2,}")


def _heb_word_set(text: str) -> set:
    return set(_HEB_WORD_RE.findall(text or ""))


CONTEXT_FRAGMENT_PROMPT = (
    "A line of Cyberpunk 2077 game text is already translated to Hebrew but "
    "still contains ONE untranslated English fragment. You are given the FULL "
    "line (for context) and that fragment. Using the meaning, context and "
    "grammar of the WHOLE line, output ONLY the Hebrew that should replace the "
    "fragment — just those few words, correctly inflected to fit the sentence.\n"
    "Output ONLY the replacement Hebrew — NOT the whole line, do not repeat the "
    "Hebrew already there, no quotes, no notes, no Niqqud. Keep proper nouns / "
    "brand names transliterated into Hebrew letters."
)


def _fix_english_leak(value: str, client) -> str | None:
    """Translate the leftover English words in an otherwise-Hebrew line.

    Stage 1 — re-fix the whole line (full context, best quality), GUARDED
    against hallucination: the result must keep >=60% of the original Hebrew
    words; on long inputs the LM rewrites the text, the overlap collapses, and
    the result is rejected.
    Stage 2 — fallback for long lines: for each leaked fragment, give the LM
    the FULL line as context but ask only for the fragment's Hebrew, then
    substitute it in place. The LM sees the whole sentence, so the fragment is
    translated to FIT the context (not in isolation), yet the surrounding
    Hebrew stays byte-identical — no hallucination is possible.
    Returns a clean line, or None."""
    orig = _heb_word_set(value)
    for _ in range(2):
        try:
            res = qa.strip_foreign(p615._lm_call(client, ENGLISH_LEAK_PROMPT,
                                                 value))
        except Exception:                                   # noqa: BLE001
            res = None
        if res and qa.value_is_clean(res) and orig and \
           len(orig & _heb_word_set(res)) / len(orig) >= 0.6:
            return res

    fixed = value
    for _ in range(5):
        tt = qa.translatable_text(fixed)
        if tt is None:
            return None
        leak = qa.english_leak(tt)
        if not leak:
            break
        if leak not in fixed:
            return None                       # cannot locate the fragment
        prompt = f"FULL LINE:\n{fixed}\n\nENGLISH FRAGMENT TO TRANSLATE:\n{leak}"
        try:
            heb = qa.strip_foreign(
                p615._lm_call(client, CONTEXT_FRAGMENT_PROMPT, prompt)).strip()
        except Exception:                                   # noqa: BLE001
            return None
        # the reply must be a fragment-sized replacement — if the LM echoed the
        # whole line back instead, it is far longer than the fragment: reject.
        if (not heb or any(c in heb for c in "<>{}") or qa.english_leak(heb)
                or len(heb) > len(leak) * 4 + 24):
            return None
        fixed = fixed.replace(leak, heb, 1)
    return fixed if qa.value_is_clean(fixed) else None


def _fix_one(item: dict, client, eng_index: dict) -> dict:
    """Worker: produce a clean replacement value for one (section, pk, field)."""
    section, pk, field = item["section"], item["pk"], item["field"]
    value = item["value"]
    eng_entry = eng_index.get((section, pk))
    english = ""
    if eng_entry:
        english = (eng_entry.get(field) or eng_entry.get("femaleVariant")
                   or eng_entry.get("maleVariant") or "")
    english = english or item["english"]

    if not item["is_markup"] and item.get("kind") == "foreign":
        # foreign-script contamination on a plain entry: usually no usable
        # English source and too long for the LM to sanitise reliably — strip
        # the stray foreign characters directly. Fast and 100% deterministic.
        stripped = qa.strip_foreign(value)
        result = stripped if qa.value_is_clean(stripped) else None
    elif not item["is_markup"] and item.get("kind") == "english_leak":
        # leftover English words in an otherwise-Hebrew line — ask the LM to
        # translate just those words in place (works with no English source).
        result = _fix_english_leak(value, client)
    elif item["is_markup"]:
        result = _retranslate_markup(value, english, client)
    else:
        result, _mode = p615.translate_clean(client, english=english or None,
                                             contaminated=value, retries=1)
        # last resort for foreign-script contamination on a plain entry: the
        # value is mostly good Hebrew with a few stray foreign chars the LM
        # will not reliably sanitise out of a long string — strip them.
        if not (result and qa.value_is_clean(result)):
            base = result if (result and qa._audit.has_hebrew(result)) else value
            stripped = qa.strip_foreign(base)
            if stripped != base and qa.value_is_clean(stripped):
                result = stripped
    ok = bool(result) and qa.value_is_clean(result)
    return {"section": section, "pk": pk, "field": field,
            "result": result if ok else None, "ok": ok, "value": value}


def fix_defects(defects: list, translated: dict, export: dict, client,
                *, workers: int = p615.PARALLEL_WORKERS) -> dict:
    """Re-translate every defect and write the clean results into `translated`
    (mutated in place). Shared by the sweep loop and the watchdog. Returns
    {fixed, failed, sections}."""
    mk.lm_client = client                       # the markup batch fns use this

    # one fix per (section, pk, field) — an entry flagged by several defect
    # classes is re-translated once.
    groups: dict[tuple, dict] = {}
    for d in defects:
        key = (d.section, d.pk, d.field)
        if key not in groups:
            groups[key] = {"section": d.section, "pk": d.pk, "field": d.field,
                           "value": d.value, "english": d.english,
                           "is_markup": d.is_markup, "kind": d.kind}

    tindex: dict[tuple, dict] = {}
    for section, rows in translated.items():
        if isinstance(rows, list):
            for e in rows:
                if isinstance(e, dict) and e.get("primaryKey") is not None:
                    tindex[(section, str(e["primaryKey"]))] = e
    eng_index = p615.build_english_index(export)

    fixed = failed = 0
    sections: set[str] = set()
    failed_keys: set = set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fix_one, it, client, eng_index)
                   for it in groups.values()]
        for fut in as_completed(futures):
            r = fut.result()
            entry = tindex.get((r["section"], r["pk"]))
            short = r["section"].split("/")[-1][:24]
            if r["ok"] and entry is not None:
                entry[r["field"]] = r["result"]
                fixed += 1
                sections.add(r["section"])
                log(f"  [OK] {short}:{r['pk']}  "
                    f"'{r['value'][:55]}' -> '{r['result'][:55]}'")
                if fixed % SAVE_EVERY == 0:
                    qa.atomic_write_json(TRANSLATED_FILE, translated)
                    log(f"  [~] Saved — {fixed:,} fixed")
            else:
                failed += 1
                failed_keys.add((r["section"], r["pk"], r["field"]))
                log(f"  [SKIP] {short}:{r['pk']} ({r['field']}) — unfixable",
                    monitor=False)
    return {"fixed": fixed, "failed": failed, "sections": sections,
            "failed_keys": failed_keys}


# ── report ──────────────────────────────────────────────────────────────────

def _section_buckets(sections) -> dict:
    return {
        "onscreens": sorted(s for s in sections if s.startswith("onscreens/")),
        "subtitles": sorted(s for s in sections if s.startswith("subtitles/")),
        "other":     sorted(s for s in sections
                            if not s.startswith(("onscreens/", "subtitles/"))),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="CP2077 Hebrew QA sweep.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Scan + report only — no LM, no writes.")
    ap.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    ap.add_argument("--only", default="",
                    help="Comma-separated defect kinds to fix "
                         "(foreign,english_leak,missing,structural). "
                         "Default: all kinds.")
    args = ap.parse_args()
    only_kinds = {k.strip() for k in args.only.split(",") if k.strip()}

    log("=" * 70, monitor=False)
    log(f"cp2077_qa_sweep starting{'  (DRY RUN)' if args.dry_run else ''}",
        monitor=False)

    for path in (TRANSLATED_FILE, EXPORT_FILE):
        if not os.path.exists(path):
            log(f"FATAL: missing {path}", monitor=False)
            return 1

    log(f"[*] loading {TRANSLATED_FILE}", monitor=False)
    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
        translated = json.load(f)
    log(f"[*] loading {EXPORT_FILE}", monitor=False)
    with open(EXPORT_FILE, "r", encoding="utf-8") as f:
        export = json.load(f)

    client = None
    if not args.dry_run:
        if OpenAI is None:
            log("FATAL: the 'openai' package is required for a real run.",
                monitor=False)
            return 1
        client = OpenAI(base_url=p615.LM_URL, api_key="lm-studio", timeout=600)
        log("[*] Preflight: pinging LM Studio …", monitor=False)
        try:
            p615._lm_call(client, p615.SYSTEM_PROMPT, "Apply")
        except Exception as e:                              # noqa: BLE001
            log(f"FATAL: cannot reach LM Studio at {p615.LM_URL} — {e}",
                monitor=False)
            return 1
        log("[*] Preflight OK", monitor=False)
        # monitor markers — let the live TUI/website track the sweep
        log("[*] Using LM Studio (Gemma-2-27b)")
        log(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]")

    if not args.dry_run:
        if not qa.acquire_lock("qa_sweep"):
            log("FATAL: another QA process holds qa.lock — exiting.",
                monitor=False)
            return 1
        atexit.register(qa.release_lock)

    initial_defects = 0
    initial_by_kind: dict = {}
    total_fixed = 0
    iterations_run = 0
    touched: set = set()

    for iteration in range(1, args.max_iterations + 1):
        defects = qa.scan_all(translated, export)
        if only_kinds:
            defects = [d for d in defects if d.kind in only_kinds]
        by_kind = Counter(d.kind for d in defects)
        if iteration == 1:
            initial_defects = len(defects)
            initial_by_kind = dict(by_kind)
            log(f"[*] iteration 1 — {len(defects):,} defects "
                f"(foreign={by_kind.get('foreign',0)} "
                f"english_leak={by_kind.get('english_leak',0)} "
                f"missing={by_kind.get('missing',0)} "
                f"structural={by_kind.get('structural',0)})", monitor=False)
        else:
            log(f"[*] iteration {iteration} — {len(defects):,} defects remain",
                monitor=False)

        if not defects:
            log("[*] clean — no defects.", monitor=False)
            break
        if args.dry_run:
            log("[*] DRY RUN — would re-translate the entries above. No writes.",
                monitor=False)
            break

        iterations_run = iteration
        res = fix_defects(defects, translated, export, client)
        total_fixed += res["fixed"]
        touched |= res["sections"]
        qa.atomic_write_json(TRANSLATED_FILE, translated)
        log(f"[~] Saved — {total_fixed:,} fixed, "
            f"~{max(0, len(defects) - res['fixed']):,} remaining")
        log(f"[*] iteration {iteration}: fixed {res['fixed']:,}, "
            f"failed {res['failed']:,}", monitor=False)
        if res["fixed"] == 0:
            log("[*] no progress this pass — remaining defects are unfixable.",
                monitor=False)
            break

    residual = qa.scan_all(translated, export)
    report = {
        "generated_at":    time.strftime("%Y-%m-%d %H:%M:%S"),
        "dry_run":         args.dry_run,
        "iterations_run":  iterations_run,
        "clean":           not residual,
        "initial_defects": initial_defects,
        "by_kind":         initial_by_kind,
        "fixed":           total_fixed,
        "failed":          len(residual),
        "residual": [
            {"section": d.section, "pk": d.pk, "field": d.field,
             "kind": d.kind, "detail": d.detail}
            for d in residual[:500]
        ],
        "patched_sections": _section_buckets(touched),
    }
    qa.atomic_write_json(REPORT_FILE, report)

    if not args.dry_run:
        log(f"[*] Done. QA sweep fixed {total_fixed:,} entries, "
            f"{len(residual):,} residual.")
    log("=" * 70, monitor=False)
    log(f"report -> {REPORT_FILE}", monitor=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
