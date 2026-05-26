"""
translate_missing_from_queue.py
================================
Drives the local LM Studio API to translate every missing English string
from `missing_translations_queue.json` to Hebrew, saving incrementally so
no progress is lost on interrupt / crash / power-cut.

INPUT
  missing_translations_queue.json   produced by audit_all_missing_translations.py
  LM Studio @ http://127.0.0.1:1234  must be running with a model loaded

OUTPUT
  lm_output.json                    in the exact shape consumed by
                                    fill_translations_from_queue.py (shape "a")
  lm_translation_progress.json      sidecar with timing + last-saved counter

DEDUPLICATION
  The queue has 51,120 entries (25,560 unique primary keys × 2 sister
  sections that hold identical data). We translate each unique key once.
  `fill_translations_from_queue.py` automatically mirrors the result into
  both onscreens.json and onscreens_final.json on merge.

RESUMABILITY
  Each save flushes the full `lm_output.json`. On startup we load the
  existing file (if any), build the set of already-translated keys, and
  skip them. Crash anywhere → restart picks up exactly where it left off.

USAGE
  python translate_missing_from_queue.py [--limit N] [--save-every N] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from openai import OpenAI
except ImportError:
    sys.exit("FATAL: install the openai package: pip install openai")

# ── Paths ────────────────────────────────────────────────────────────────
SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
QUEUE       = os.path.join(SCRIPTS_DIR, "missing_translations_queue.json")
OUTPUT      = os.path.join(SCRIPTS_DIR, "lm_output.json")
PROGRESS    = os.path.join(SCRIPTS_DIR, "lm_translation_progress.json")
LOG_FILE    = os.path.join(SCRIPTS_DIR, "translate_missing_from_queue.log")

# Single section to write to. `fill_translations_from_queue.py` mirrors
# this to both onscreens.json + onscreens_final.json on merge.
PRIMARY_SECTION = "onscreens/onscreens.json"

# ── LM Studio client ────────────────────────────────────────────────────
CLIENT = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
MODEL  = "local-model"        # LM Studio routes this to the loaded model
SYSTEM_PROMPT = (
    "Translate the user's English text to Hebrew. "
    "Output the Hebrew translation only. "
    "No explanations, no notes, no markdown, no quotes, no prefix like 'Translation:'. "
    "No <think> tags. No reasoning. Just the Hebrew text on a single line. "
    "Keep tags like <n>, <br>, {0}, %s exactly as written. "
    "Keep proper nouns (Night City, V, Johnny, Arasaka) transliterated naturally."
)

# ── Translation helpers (mirrors cp2077_translate.py rules) ────────────
_THINK_RE  = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX_RE = re.compile(
    r"^\s*(?:translation|תרגום|hebrew|output|answer)\s*[:\-]\s*",
    re.IGNORECASE,
)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def needs_translation(text: str) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    if "\x00" in text or "�" in text:
        return False
    if not re.search(r"[a-zA-Z]", text):
        return False
    letters = re.sub(r"[^a-zA-Z]", "", text)
    return len(letters) > 1


def clean_text_for_ai(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"[^\x20-\x7E֐-׿\n\r\t]", "", text).strip()


def clean_response(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = _THINK_RE.sub("", raw).strip()
    while len(s) >= 2 and s[0] == s[-1] and s[0] in ("\"", "'", "`", "“", "”", "„"):
        s = s[1:-1].strip()
    s = re.sub(r"^\*+\s*(.+?)\s*\*+$", r"\1", s).strip()
    s = re.sub(r"^_+\s*(.+?)\s*_+$", r"\1", s).strip()
    s = _PREFIX_RE.sub("", s).strip()
    return s


def translate_one(text: str, retries: int = 3) -> str:
    """Returns Hebrew text, or the original (unchanged) if untranslatable
    or all retries fail. Matching cp2077_translate.py semantics."""
    if not needs_translation(text):
        return text
    cleaned = clean_text_for_ai(text)
    if not cleaned or not needs_translation(cleaned):
        return text
    for attempt in range(retries):
        try:
            resp = CLIENT.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": cleaned},
                ],
                temperature=0.2,
                max_tokens=512,
            )
            out = clean_response(resp.choices[0].message.content)
            if out:
                return out
        except Exception as e:
            log(f"    [retry {attempt+1}] {type(e).__name__}: {e}")
            time.sleep(2)
    log(f"    [!] giving up on: {cleaned[:60]!r}")
    return text  # fall back to original (English) — caller will keep it


# ── Preflight check ─────────────────────────────────────────────────────
def preflight() -> None:
    log("preflight: pinging LM Studio…")
    try:
        resp = CLIENT.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": "Apply"},
            ],
            temperature=0.0,
            max_tokens=32,
        )
        sample = clean_response(resp.choices[0].message.content)
        log(f"  OK — sample translation of 'Apply' -> {sample!r}")
    except Exception as e:
        sys.exit(
            f"FATAL: cannot reach LM Studio at {CLIENT.base_url}\n"
            f"  {type(e).__name__}: {e}\n"
            f"  Open LM Studio, load a model, start the local server, and retry."
        )


# ── Load / save ─────────────────────────────────────────────────────────
def load_queue() -> dict:
    if not os.path.exists(QUEUE):
        sys.exit(f"FATAL: missing {QUEUE}. Run audit_all_missing_translations.py first.")
    with open(QUEUE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_output() -> dict:
    if not os.path.exists(OUTPUT):
        return {PRIMARY_SECTION: []}
    try:
        with open(OUTPUT, "r", encoding="utf-8") as f:
            data = json.load(f)
        if PRIMARY_SECTION not in data:
            data[PRIMARY_SECTION] = []
        return data
    except json.JSONDecodeError:
        # corrupted partial save — back it up and start fresh
        bak = f"{OUTPUT}.corrupt.{int(time.time())}"
        os.rename(OUTPUT, bak)
        log(f"WARN: output JSON was corrupt; moved to {bak} and starting fresh")
        return {PRIMARY_SECTION: []}


def save_output(output: dict) -> None:
    # write to a temp file then rename to avoid corruption mid-flush
    tmp = OUTPUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUTPUT)


def save_progress(state: dict) -> None:
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ── Main ────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--limit", type=int, default=0,
                    help="Stop after translating N entries (0 = unlimited)")
    ap.add_argument("--save-every", type=int, default=20,
                    help="Flush output to disk every N entries (default 20)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Skip API calls, just print the to-do count")
    args = ap.parse_args()

    log("=" * 68)
    log("translate_missing_from_queue starting")
    log("=" * 68)

    if not args.dry_run:
        preflight()

    log("loading queue + existing output…")
    queue = load_queue()
    output = load_output()
    done_pks = {str(e["primaryKey"]) for e in output[PRIMARY_SECTION]}

    # Dedupe across both onscreens sections in the queue.
    unique_by_pk: dict[str, dict] = {}
    for section, entries in queue.get("missing", {}).items():
        for e in entries:
            pk = str(e["primaryKey"])
            unique_by_pk.setdefault(pk, e)

    total_unique = len(unique_by_pk)
    to_do = [(pk, e) for pk, e in unique_by_pk.items() if pk not in done_pks]

    log(f"unique primary keys in queue: {total_unique:,}")
    log(f"already translated (resume):  {len(done_pks):,}")
    log(f"remaining to translate:       {len(to_do):,}")

    if args.dry_run:
        log("dry-run: exiting without API calls")
        return

    if not to_do:
        log("nothing to do. lm_output.json is complete.")
        return

    if args.limit:
        to_do = to_do[: args.limit]
        log(f"--limit {args.limit}: processing first {len(to_do):,} only")

    t0 = time.time()
    last_save = 0
    api_failures = 0

    for i, (pk, qe) in enumerate(to_do, start=1):
        fem_en = (qe.get("english_female") or "").strip()
        mal_en = (qe.get("english_male") or "").strip()

        fem_he = translate_one(fem_en) if fem_en else ""
        mal_he = translate_one(mal_en) if mal_en else ""

        if fem_en and fem_he == fem_en:
            api_failures += 1  # we returned the English as fallback

        output[PRIMARY_SECTION].append({
            "primaryKey":    qe["primaryKey"],
            "secondaryKey":  qe.get("secondaryKey", "") or "",
            "femaleVariant": fem_he,
            "maleVariant":   mal_he,
        })

        if i - last_save >= args.save_every or i == len(to_do):
            save_output(output)
            elapsed = time.time() - t0
            rate = i / max(elapsed, 0.01)
            eta_min = (len(to_do) - i) / max(rate, 0.01) / 60
            done_total = len(done_pks) + i
            log(
                f"[{i:,}/{len(to_do):,}]  "
                f"saved  rate={rate:.2f}/s  "
                f"eta={eta_min:.0f}min  "
                f"total_done={done_total:,}/{total_unique:,}  "
                f"fallbacks={api_failures}"
            )
            save_progress({
                "started_at":        time.strftime("%Y-%m-%d %H:%M:%S",
                                                    time.localtime(t0)),
                "last_save_at":      time.strftime("%Y-%m-%d %H:%M:%S"),
                "elapsed_seconds":   round(elapsed, 1),
                "this_run_done":     i,
                "this_run_total":    len(to_do),
                "grand_total_done":  done_total,
                "grand_total":       total_unique,
                "rate_per_second":   round(rate, 3),
                "eta_minutes":       round(eta_min, 1),
                "api_fallbacks":     api_failures,
            })
            last_save = i

    log("=" * 68)
    log(f"DONE — {len(to_do):,} translated this run, "
        f"{len(done_pks) + len(to_do):,}/{total_unique:,} total")
    log(f"output: {OUTPUT}")
    log("=" * 68)


if __name__ == "__main__":
    main()
