"""
patch_615_flagged.py
====================
Surgical re-translation of audit-flagged entries in localization_translated.json.

NOTE ON THE NAME: the "615" is historical — an old CLAUDE.md figure. This
script is fully DYNAMIC: it patches whatever the CURRENT audit flags, which
may be 0, 615, or any other count. The filename is kept because the
orchestrator spec named it explicitly.

Flow:
  1. Scan localization_translated.json for foreign-script / Niqqud
     contamination by reusing audit_translations.detect_scripts(). Scanning
     directly (not parsing audit_translations_report.txt) avoids that
     report's 500-entries-per-script cap.
  2. For each flagged entry, look up the English source in
     localization_export.json and re-translate it via LM Studio using the
     strict Cyberpunk system prompt.
  3. Fallback — if no English source is found, run a "sanitize" LM pass on
     the contaminated Hebrew itself (strip foreign scripts, keep meaning).
  4. Validate every result is clean (re-run detect_scripts). Still dirty
     after one retry → leave the original untouched, count as failed.
  5. Atomically rewrite localization_translated.json and emit
     patch_615_report.json (consumed by the rebuild scripts / orchestrator).

Standalone usage:
    python patch_615_flagged.py            # real run
    python patch_615_flagged.py --dry-run  # scan + report only, no LM, no write

Exit code is 0 even when nothing is flagged.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# audit_translations lives next to this script — reused for the exact same
# contamination definition the project's QA already trusts.
import audit_translations  # noqa: E402

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # surfaced at preflight when an LM run is actually needed

# ── Paths ─────────────────────────────────────────────────────────────────
SCRIPTS_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
RESOURCES   = os.path.join(PROJECT, "source", "resources")

TRANSLATED_FILE = os.path.join(RESOURCES, "localization_translated.json")
EXPORT_FILE     = os.path.join(RESOURCES, "localization_export.json")
REPORT_FILE     = os.path.join(SCRIPTS_DIR, "patch_615_report.json")
LOG_FILE        = os.path.join(SCRIPTS_DIR, "patch_615.log")

# ── LM Studio — mirrors translate_cleanup_all.py ──────────────────────────
LM_URL       = "http://127.0.0.1:1234/v1"
LM_MODEL     = "local-model"
TEMPERATURE  = 0.3
MAX_TOKENS   = 512
PARALLEL_WORKERS = 4

# Verbatim strict prompt from translate_cleanup_all.py — English → Hebrew.
SYSTEM_PROMPT = (
    "You are a professional game localizer for Cyberpunk 2077. Translate the "
    "user's English text to Hebrew with a gritty, high-tech, Night City tone "
    "suitable for a psychological-thriller RPG.\n"
    "Output the Hebrew translation only — no explanations, notes, markdown, "
    "quotes, or 'Translation:' prefix. No <think> tags. Just the Hebrew text "
    "on a single line.\n"
    "\n"
    "HARD RULES (no exceptions):\n"
    "  • USE ONLY HEBREW AND ENGLISH ALPHABETS. DO NOT USE RUSSIAN, ARABIC, "
    "CYRILLIC, THAI, GREEK, CHINESE, JAPANESE, KOREAN, OR ANY OTHER LANGUAGES.\n"
    "  • NEVER use Hebrew Niqqud (vowel points like ַ ָ ֵ ֶ ִ ֹ ֻ ּ ׁ ׂ etc.). "
    "Use plain modern Hebrew letters only. NO marks above or below letters "
    "under any circumstance.\n"
    "  • Keep tags like <n>, <br>, <Rich color=\"...\">, {0}, {VALUE,...}, %s "
    "EXACTLY as written — do not translate or alter them.\n"
    "  • Keep proper nouns (V, Johnny, Arasaka, Night Corp, Trauma Team, etc.) "
    "transliterated naturally.\n"
    "  • Translate exactly what's there. NO hallucinations — if the input is a "
    "pure code, hex, placeholder, or number, return it unchanged.\n"
    "\n"
    "Cyberpunk 2077 glossary — use EXACTLY these Hebrew renderings whenever the term appears:\n"
    "  Night City -> נייט סיטי\n"
    "  Netrunner -> נטראנר\n"
    "  Ripperdoc -> ריפרדוק\n"
    "  Corpo -> קורפו\n"
    "  Choom / Choomba -> צ'ום\n"
    "  Braindance -> בריינדאנס   (keep the abbreviation 'BD' as 'BD')\n"
    "  Cyberware -> סייברוור\n"
    "  Shard -> שארד\n"
    "  Edgerunner -> אדג'ראנר"
)

# Fallback prompt — used when the English source can't be located. Operates
# on the contaminated Hebrew directly: strip the foreign script, keep meaning.
SANITIZE_PROMPT = (
    "You are a Hebrew proofreader for a Cyberpunk 2077 fan translation. The "
    "user gives you a Hebrew string that accidentally contains characters "
    "from another script (Cyrillic, Arabic, Greek, CJK, etc.) or Niqqud "
    "vowel-points.\n"
    "Rewrite it as clean, natural modern Hebrew that conveys the SAME meaning.\n"
    "HARD RULES:\n"
    "  • Output ONLY Hebrew letters, Latin letters, digits and punctuation. "
    "NO Cyrillic / Arabic / Greek / CJK / any other script.\n"
    "  • NO Niqqud vowel-points.\n"
    "  • Keep tags like <Rich color=\"...\">, {VALUE,...}, %s, {0} EXACTLY.\n"
    "  • Output the corrected Hebrew on a single line — no explanations."
)

_THINK_RE  = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX_RE = re.compile(r"^\s*(?:translation|תרגום|hebrew|output|answer)\s*[:\-]\s*",
                        re.IGNORECASE)
_HEBREW_RE = re.compile(r"[֐-׿]")


# ── Logging ───────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── LM helpers ────────────────────────────────────────────────────────────
def clean_response(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = _THINK_RE.sub("", raw).strip()
    s = re.sub(r"^\*+\s*(.+?)\s*\*+$", r"\1", s).strip()
    s = re.sub(r"^_+\s*(.+?)\s*_+$", r"\1", s).strip()
    s = _PREFIX_RE.sub("", s).strip()
    m = re.match(r"^\s*1\.\s*(.+)", s)
    if m:
        s = m.group(1).strip()
    return s


def is_clean_hebrew(text: str) -> bool:
    """A result is acceptable only if it has Hebrew AND carries no foreign
    script / Niqqud contamination (the exact audit definition)."""
    if not text or not _HEBREW_RE.search(text):
        return False
    return not audit_translations.detect_scripts(text)


def _lm_call(client, system_prompt: str, user_text: str) -> str:
    resp = client.chat.completions.create(
        model=LM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_text},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    return clean_response(resp.choices[0].message.content or "")


def translate_clean(client, *, english: str | None, contaminated: str,
                     retries: int = 2) -> tuple[str | None, str]:
    """Produce a clean-Hebrew replacement for one flagged entry.

    Strategy: translate from the English source when available; otherwise
    sanitize the contaminated Hebrew in place. Returns (result, mode) where
    result is None if every attempt still left contamination.
    """
    if english and english.strip():
        prompt, payload, mode = SYSTEM_PROMPT, english.strip(), "translate"
    else:
        prompt, payload, mode = SANITIZE_PROMPT, contaminated, "sanitize"

    for attempt in range(1, retries + 1):
        try:
            result = _lm_call(client, prompt, payload)
        except Exception as e:                            # noqa: BLE001
            log(f"      [!] LM error (attempt {attempt}, {mode}): {e}")
            time.sleep(2)
            continue
        if is_clean_hebrew(result):
            return result, mode
        # Second pass always sanitizes whatever the first pass produced.
        prompt, payload = SANITIZE_PROMPT, (result or contaminated)
    return None, mode


# ── Flagged-set discovery ─────────────────────────────────────────────────
def scan_flagged(translated: dict) -> list[dict]:
    """Return every contaminated variant as
    {section, pk, field, value, scripts}. Uses the exact same detector the
    project's audit_translations.py uses — but uncapped."""
    flagged: list[dict] = []
    for section, rows in translated.items():
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if not isinstance(entry, dict):
                continue
            for field in ("femaleVariant", "maleVariant"):
                val = entry.get(field) or ""
                if not val:
                    continue
                hits = audit_translations.detect_scripts(val)
                if hits:
                    flagged.append({
                        "section": section,
                        "pk":      entry.get("primaryKey"),
                        "field":   field,
                        "value":   val,
                        "scripts": sorted(hits),
                    })
    return flagged


def build_english_index(export: dict) -> dict[tuple[str, str], dict]:
    """{(section, str(primaryKey)): english_entry} for O(1) source lookup."""
    idx: dict[tuple[str, str], dict] = {}
    for section, rows in export.items():
        if not isinstance(rows, list):
            continue
        for entry in rows:
            if isinstance(entry, dict) and entry.get("primaryKey") is not None:
                idx[(section, str(entry["primaryKey"]))] = entry
    return idx


# ── Main ──────────────────────────────────────────────────────────────────
def _atomic_write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def main() -> int:
    ap = argparse.ArgumentParser(description="Surgical re-translation of audit-flagged entries.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Scan + report only — no LM calls, no file writes.")
    args = ap.parse_args()

    log("=" * 70)
    log(f"patch_615_flagged starting{'  (DRY RUN)' if args.dry_run else ''}")
    log("=" * 70)

    for path, name in [(TRANSLATED_FILE, "localization_translated.json"),
                       (EXPORT_FILE, "localization_export.json")]:
        if not os.path.exists(path):
            log(f"FATAL: missing {name}: {path}")
            return 1

    log(f"[*] Loading {TRANSLATED_FILE}")
    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
        translated = json.load(f)

    log("[*] Scanning for foreign-script / Niqqud contamination …")
    flagged = scan_flagged(translated)
    log(f"[*] Flagged entries: {len(flagged):,}")

    # Emit a report even on the empty path so the orchestrator always has one.
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dry_run":      args.dry_run,
        "flagged":      len(flagged),
        "fixed":        0,
        "failed":       0,
        "patched_sections": {"onscreens": [], "subtitles": [], "other": []},
    }

    if not flagged:
        log("[*] Nothing flagged — localization_translated.json is clean. Done.")
        _atomic_write_json(REPORT_FILE, report)
        log("=" * 70)
        return 0

    by_script: dict[str, int] = {}
    for fl in flagged:
        for s in fl["scripts"]:
            by_script[s] = by_script.get(s, 0) + 1
    log("[*] Per-script tally: " +
        ", ".join(f"{s}={c}" for s, c in sorted(by_script.items(), key=lambda kv: -kv[1])))

    if args.dry_run:
        log("[*] DRY RUN — would re-translate the entries above. No writes.")
        _atomic_write_json(REPORT_FILE, report)
        log("=" * 70)
        return 0

    if OpenAI is None:
        log("FATAL: the 'openai' package is required for a real run (pip install openai).")
        return 1

    # Preflight — fail fast and loud if LM Studio isn't up.
    client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=600)
    log("[*] Preflight: pinging LM Studio …")
    try:
        _lm_call(client, SYSTEM_PROMPT, "Apply")
        log("[*] Preflight OK")
    except Exception as e:                                # noqa: BLE001
        log(f"FATAL: cannot reach LM Studio at {LM_URL} — {type(e).__name__}: {e}")
        log("      Open LM Studio, load Gemma-2-27B, start the local server, retry.")
        return 1

    log(f"[*] Loading English source {EXPORT_FILE}")
    with open(EXPORT_FILE, "r", encoding="utf-8") as f:
        english_index = build_english_index(json.load(f))
    log(f"[*] Indexed {len(english_index):,} English source entries")

    # Index translated entries for O(1) writeback.
    translated_index: dict[tuple[str, str], dict] = {}
    for section, rows in translated.items():
        if isinstance(rows, list):
            for entry in rows:
                if isinstance(entry, dict) and entry.get("primaryKey") is not None:
                    translated_index[(section, str(entry["primaryKey"]))] = entry

    def worker(fl: dict) -> dict:
        key = (fl["section"], str(fl["pk"]))
        eng_entry = english_index.get(key)
        english = (eng_entry.get(fl["field"]) or eng_entry.get("femaleVariant")
                   or eng_entry.get("maleVariant")) if eng_entry else None
        result, mode = translate_clean(client, english=english,
                                       contaminated=fl["value"])
        return {**fl, "result": result, "mode": mode}

    fixed = 0
    failed = 0
    patched_sections: set[str] = set()
    t0 = time.time()

    log(f"[*] Re-translating {len(flagged):,} entries ({PARALLEL_WORKERS} workers) …")
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        futures = {pool.submit(worker, fl): fl for fl in flagged}
        done = 0
        for fut in as_completed(futures):
            done += 1
            r = fut.result()
            key = (r["section"], str(r["pk"]))
            entry = translated_index.get(key)
            short = r["section"].split("/")[-1][:34]
            if r["result"] and entry is not None:
                entry[r["field"]] = r["result"]
                fixed += 1
                patched_sections.add(r["section"])
                log(f"  [{done}/{len(flagged)}] OK  {short}:{r['pk']} "
                    f"({r['field']}, {r['mode']})")
            else:
                failed += 1
                why = "still contaminated" if entry is not None else "entry vanished"
                log(f"  [{done}/{len(flagged)}] FAIL {short}:{r['pk']} — {why}")

    if fixed:
        log(f"[*] Writing {fixed:,} fixes to {TRANSLATED_FILE}")
        _atomic_write_json(TRANSLATED_FILE, translated)
    else:
        log("[*] No entry could be cleaned — localization_translated.json untouched.")

    report.update(
        fixed=fixed,
        failed=failed,
        patched_sections={
            "onscreens": sorted(s for s in patched_sections if s.startswith("onscreens/")),
            "subtitles": sorted(s for s in patched_sections if s.startswith("subtitles/")),
            "other":     sorted(s for s in patched_sections
                                if not s.startswith(("onscreens/", "subtitles/"))),
        },
    )
    _atomic_write_json(REPORT_FILE, report)

    elapsed = time.time() - t0
    log("=" * 70)
    log(f"DONE — flagged {len(flagged):,} | fixed {fixed:,} | failed {failed:,} "
        f"| {elapsed / 60:.1f} min")
    log(f"  report -> {REPORT_FILE}")
    log("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
