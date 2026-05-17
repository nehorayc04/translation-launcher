"""
translate_queue_fast.py
=======================
High-throughput LM-Studio translator driven by `missing_translations_queue.json`,
architected exactly like `cp2077_fix_missing_translations.py`:

  • Global pending queue (deduped across the two onscreens sister sections)
  • Phase 2: TM cache + fast-track dictionary (instant, no API calls)
  • Phase 3: dynamic batches of up to 12 lines / ~150 words per prompt,
             dispatched across 4 concurrent workers hitting LM Studio
  • Atomic incremental save every SAVE_EVERY entries — fully resumable

MONITOR INTEGRATION
-------------------
Writes its progress to the EXACT log file `cp2077_monitor.py` watches
(`fix_missing_translations.log`), using the EXACT marker lines and regex
shapes the monitor's parsers expect:

    [*] Using LM Studio (Gemma-2-27b)
    [started: 2026-05-17 12:34:56]
    [*] Global queue: 25,560 pending items
    [*] Phase 2 done: 1,234 TM hits, 567 fast-track hits, 23,759 need LM
    [*] Phase 3: 2,114 batches (<= 12 lines / ~150 words each), 4 concurrent workers
      onscreens.json:8887 [femaleVariant]  'Go to the chapel.' -> 'לך לכנסייה.'
      [~] Saved — 200 fixed, ~25,360 remaining
    [*] Done. Fixed 25,560 fields (... TM, ... FT, ... via LM).

Run `python cp2077_monitor.py` in another terminal (or via cp2077_monitor.bat)
to see the dashboard update live.

OUTPUTS
-------
  lm_output.json                          shape "a" for fill_translations_from_queue.py
  localization_translated.json            in-place update by primaryKey
  tm_cache.json                           grows with every successful new translation
  fix_missing_translations.log            monitor reads this
  translate_queue_fast.runtime.log        plain runtime log (timestamped)

USAGE
-----
  python translate_queue_fast.py [--single] [--temperature 0.3]

  --single      one-string-per-call mode (slower, debugging)
  --temperature default 0.3 (technical translation register)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

# ── force UTF-8 output (so Hebrew log lines don't crash cp1255 consoles) ─
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", write_through=True
    )

# ── paths ────────────────────────────────────────────────────────────────
SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
RESOURCES   = os.path.join(PROJECT, "source", "resources")

QUEUE_FILE      = os.path.join(SCRIPTS_DIR, "missing_translations_queue.json")
OUTPUT_FILE     = os.path.join(SCRIPTS_DIR, "lm_output.json")
TRANSLATED_FILE = os.path.join(RESOURCES, "localization_translated.json")
TM_CACHE_FILE   = os.path.join(RESOURCES, "tm_cache.json")
SKIP_FILE       = os.path.join(RESOURCES, "translation_skips.json")

# ── monitor-watched log file — DO NOT rename ─────────────────────────────
MONITOR_LOG = os.path.join(SCRIPTS_DIR, "fix_missing_translations.log")
RUNTIME_LOG = os.path.join(SCRIPTS_DIR, "translate_queue_fast.runtime.log")

# Both sister sections receive the same translations.
ONSCREENS_SECTIONS = ["onscreens/onscreens.json", "onscreens/onscreens_final.json"]
PRIMARY_OUT_SECTION = "onscreens/onscreens.json"  # what we write into lm_output.json

# ── tuning (matches cp2077_fix_missing_translations.py) ─────────────────
DYN_MAX_LINES    = 12     # hard cap per batch prompt
DYN_MAX_WORDS    = 150    # soft cap per batch prompt
PARALLEL_WORKERS = 4      # concurrent LM Studio slots
SAVE_EVERY       = 200    # checkpoint cadence

# ── LM Studio config ────────────────────────────────────────────────────
LM_URL          = "http://127.0.0.1:1234/v1"
LM_MODEL        = "local-model"
DEFAULT_TEMP    = 0.3     # user-requested technical-translation level
MAX_TOKENS      = 512

SYSTEM_PROMPT = (
    "Translate the user's English text to Hebrew. Output the Hebrew translation only.\n"
    "No explanations, no notes, no markdown, no quotes, no prefix like 'Translation:'.\n"
    "No <think> tags. No reasoning. Just the Hebrew text on a single line.\n"
    "CRITICAL: USE ONLY HEBREW AND ENGLISH ALPHABETS. DO NOT USE RUSSIAN, ARABIC, CYRILLIC, THAI, OR ANY OTHER LANGUAGES.\n"
    "Keep tags like <n>, <br>, {0}, %s exactly as written.\n"
    "Keep proper nouns (V, Johnny, Arasaka) transliterated naturally.\n"
    "\n"
    "Cyberpunk 2077 glossary — use EXACTLY these Hebrew renderings whenever the term appears:\n"
    "  Night City -> נייט סיטי\n"
    "  Netrunner -> נטראנר\n"
    "  Ripperdoc -> ריפרדוק\n"
    "  Corpo -> קורפו\n"
    "  Choom / Choomba -> צ'ום\n"
    "  Braindance -> בריינדאנס   (keep the abbreviation 'BD' as 'BD')\n"
    "  Cyberware -> סייברוור"
)
BATCH_PROMPT_HEADER = (
    "Translate each line below to Hebrew.\n"
    "Format your output exactly as:\n"
    "1. [Hebrew translation 1]\n"
    "2. [Hebrew translation 2]\n\n"
)

# ── fast-track dictionary (mirrors cp2077_fix_missing_translations.py) ─
FAST_TRACK_DICT = {
    "yes": "כן", "yeah": "כן", "yep": "כן", "yup": "כן",
    "sure": "בטח", "ok": "אוקיי", "okay": "אוקיי", "alright": "בסדר",
    "no": "לא", "nope": "לא", "nah": "לא",
    "hello": "שלום", "hi": "היי", "hey": "היי",
    "bye": "ביי", "goodbye": "להתראות",
    "thanks": "תודה", "thank you": "תודה", "please": "בבקשה",
    "sorry": "סליחה", "excuse me": "סלח לי",
    "wait": "חכה", "stop": "עצור", "go": "לך",
    "look": "תראה", "listen": "תקשיב", "help": "הצילו",
    "come on": "נו", "hurry": "מהר",
    "damn": "לעזאזל", "shit": "חרא", "fuck": "פאק",
    "really": "באמת", "maybe": "אולי",
}

# ── regexes ─────────────────────────────────────────────────────────────
_THINK_RE      = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX_RE     = re.compile(r"^\s*(?:translation|תרגום|hebrew|output|answer)\s*[:\-]\s*", re.IGNORECASE)
_FT_PUNCT_RE   = re.compile(r"^(.+?)([\.\!\?,;:]*)$")
_TAG_RE        = re.compile(r"<.*?>|\{.*?\}|%[a-zA-Z]")
_HEB_RE        = re.compile(r"[֐-׿]")
_FOREIGN_RE    = re.compile(r"[Ѐ-ӿ؀-ۿ฀-๿ऀ-ॿ一-鿿]")
_LATIN_RE      = re.compile(r"[A-Za-z]")

# ── shared mutable state (guarded by state_lock) ────────────────────────
state_lock = threading.Lock()
lm_client: OpenAI = None     # initialized in main()
TEMPERATURE = DEFAULT_TEMP

translated: dict = {}                                  # localization_translated.json (mutated in place)
translated_index: dict = {}                            # {section: {pk_str: entry_dict}} — O(1) lookup
tm_cache: dict = {}                                    # English -> Hebrew
skips: set = set()                                     # always-skipped (pk, field) tuples
lm_output: dict = {PRIMARY_OUT_SECTION: []}            # what fill_translations_from_queue reads
lm_output_pk_set: set = set()                          # pks already in lm_output (resume)
lm_output_index: dict = {}                             # {pk_str: entry_dict} — O(1) lookup

# ── tee logger: prints AND appends to monitor log + runtime log ─────────
_log_locks = threading.Lock()


def _log(line: str) -> None:
    """Write `line` to stdout, monitor log, and runtime log (with timestamp)."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    runtime_line = f"[{ts}] {line}"
    with _log_locks:
        print(line, flush=True)
        try:
            with open(MONITOR_LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
            with open(RUNTIME_LOG, "a", encoding="utf-8") as f:
                f.write(runtime_line + "\n")
        except OSError:
            pass


# ── translation helpers ─────────────────────────────────────────────────
def clean_response(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = _THINK_RE.sub("", raw).strip()
    s = re.sub(r"^\*+\s*(.+?)\s*\*+$", r"\1", s).strip()
    s = re.sub(r"^_+\s*(.+?)\s*_+$", r"\1", s).strip()
    s = _PREFIX_RE.sub("", s).strip()
    return s


def check_tags_preserved(orig: str, trans: str) -> bool:
    return all(tag in trans for tag in _TAG_RE.findall(orig))


def is_valid_translation(orig: str, trans: str) -> bool:
    if not trans or not isinstance(trans, str):
        return False
    if not _HEB_RE.search(trans):
        return False
    if _FOREIGN_RE.search(trans):
        return False
    return check_tags_preserved(orig or "", trans)


def needs_translation(src: str, current: str) -> bool:
    if not src:
        return False
    if is_valid_translation(src, current):
        return False
    if not _LATIN_RE.search(src):
        return False
    cleaned = re.sub(r"<[^>]+>", "", src)
    return len(re.sub(r"[^a-zA-Z]", "", cleaned)) > 1


def try_fast_track(text: str) -> str | None:
    if not text or "<" in text or "{" in text or "%" in text:
        return None
    s = text.strip()
    if not s:
        return None
    m = _FT_PUNCT_RE.match(s)
    if not m:
        return None
    core, suffix = m.group(1).strip(), m.group(2)
    hebrew = FAST_TRACK_DICT.get(core.lower())
    return (hebrew + suffix) if hebrew else None


def build_dynamic_batches(items, text_for):
    """Group items into sub-lists capped by DYN_MAX_WORDS / DYN_MAX_LINES."""
    batch, words = [], 0
    for item in items:
        w = len(text_for(item).split())
        if batch and (words + w > DYN_MAX_WORDS or len(batch) >= DYN_MAX_LINES):
            yield batch
            batch, words = [], 0
        batch.append(item)
        words += w
    if batch:
        yield batch


def translate_one(text: str, retries: int = 3) -> str:
    for attempt in range(1, retries + 1):
        try:
            resp = lm_client.chat.completions.create(
                model=LM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            raw = (resp.choices[0].message.content or "").strip()
            result = clean_response(raw)
            m = re.match(r"^\s*1\.\s*(.+)", result)
            if m:
                result = m.group(1).strip()
            if is_valid_translation(text, result):
                return result
        except Exception as e:
            _log(f"      [!] API Error (attempt {attempt}): {e}")
            time.sleep(2)
    return text


def _parse_batch_response(raw_text: str, count: int) -> list[str]:
    parsed = {}
    for line in raw_text.splitlines():
        m = re.match(r"^\s*(\d+)\.\s*(.+)", line.strip())
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < count:
                parsed[idx] = clean_response(m.group(2))
    return [parsed.get(i, "") for i in range(count)]


def translate_batch(texts: list[str]) -> list[str]:
    non_empty = [(i, c) for i, c in enumerate(texts) if c]
    if not non_empty:
        return texts
    user_text = BATCH_PROMPT_HEADER
    for j, (_, text) in enumerate(non_empty):
        user_text += f"{j + 1}. {text}\n"
    for attempt in range(2):
        try:
            resp = lm_client.chat.completions.create(
                model=LM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_text},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )
            raw = (resp.choices[0].message.content or "").strip()
            parsed = _parse_batch_response(raw, len(non_empty))
            results = list(texts)
            success = 0
            for k, (orig_idx, _) in enumerate(non_empty):
                if is_valid_translation(texts[orig_idx], parsed[k]):
                    results[orig_idx] = parsed[k]
                    success += 1
            if success == len(non_empty):
                return results
            _log(
                f"      [~] Batch partial: {success} ok, "
                f"{len(non_empty) - success} going to single mode"
            )
            break
        except Exception as e:
            _log(f"      [!] Batch API Error: {e}")
            time.sleep(2)
    results = list(texts)
    for i, text in enumerate(texts):
        if text and not is_valid_translation(texts[i], results[i]):
            results[i] = translate_one(text)
    return results


# ── atomic JSON writers ─────────────────────────────────────────────────
def _atomic_write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_translated() -> None:
    _atomic_write_json(TRANSLATED_FILE, translated)


def save_tm() -> None:
    _atomic_write_json(TM_CACHE_FILE, tm_cache)


def save_skips() -> None:
    try:
        _atomic_write_json(SKIP_FILE, [list(t) for t in skips])
    except OSError:
        pass


def save_lm_output() -> None:
    _atomic_write_json(OUTPUT_FILE, lm_output)


def save_all() -> None:
    save_translated()
    save_lm_output()
    save_tm()


# ── apply a successful translation into all 3 sinks (under state_lock) ─
def _record_success(pk: str, secondary_key: str, src: str, hebrew: str) -> None:
    """Write `hebrew` into:
       1. localization_translated.json — both onscreens sister sections, by pk
       2. lm_output.json — primary section list (resume-safe)
       3. tm_cache — exact source->target memoization
    Caller must hold state_lock.
    """
    for section in ONSCREENS_SECTIONS:
        idx = translated_index.setdefault(section, {})
        entry = idx.get(pk)
        if entry is not None:
            entry["femaleVariant"] = hebrew
        else:
            # not present (shouldn't happen post-fallback, but be defensive)
            new_entry = {
                "primaryKey":    int(pk) if pk.isdigit() else pk,
                "secondaryKey":  secondary_key,
                "femaleVariant": hebrew,
                "maleVariant":   "",
            }
            translated.setdefault(section, []).append(new_entry)
            idx[pk] = new_entry

    out_entry = lm_output_index.get(pk)
    if out_entry is not None:
        out_entry["femaleVariant"] = hebrew
    else:
        new_entry = {
            "primaryKey":    pk,
            "secondaryKey":  secondary_key,
            "femaleVariant": hebrew,
            "maleVariant":   "",
        }
        lm_output[PRIMARY_OUT_SECTION].append(new_entry)
        lm_output_pk_set.add(pk)
        lm_output_index[pk] = new_entry

    tm_cache[src] = hebrew


def _record_skip(pk: str) -> None:
    """Caller holds state_lock."""
    skips.add(("queue", pk, "femaleVariant"))


# ── load state ──────────────────────────────────────────────────────────
def load_state() -> tuple[list[tuple[str, str, str]], int, int]:
    """Returns (queue_items, already_done_count, total_unique).
    queue_items = list of (pk, secondary_key, english_text) yet to process."""
    global translated, tm_cache, skips, lm_output, lm_output_pk_set, lm_output_index

    if not os.path.exists(QUEUE_FILE):
        sys.exit(f"FATAL: missing {QUEUE_FILE}. Run audit_all_missing_translations.py.")
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        queue = json.load(f)

    _log(f"[*] Loading {TRANSLATED_FILE}")
    if os.path.exists(TRANSLATED_FILE):
        with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
            translated = json.load(f)
    else:
        translated = {}

    if os.path.exists(TM_CACHE_FILE):
        try:
            with open(TM_CACHE_FILE, "r", encoding="utf-8") as f:
                tm_cache = json.load(f)
            if not isinstance(tm_cache, dict):
                tm_cache = {}
        except json.JSONDecodeError:
            tm_cache = {}
    _log(f"[*] Loaded {len(tm_cache):,} TM cache entries")

    if os.path.exists(SKIP_FILE):
        try:
            with open(SKIP_FILE, "r", encoding="utf-8") as f:
                skips = set(tuple(x) for x in json.load(f))
        except (OSError, json.JSONDecodeError, TypeError):
            skips = set()
    _log(f"[*] Loaded {len(skips):,} permanently skipped entries")

    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                lm_output = json.load(f)
            if PRIMARY_OUT_SECTION not in lm_output:
                lm_output[PRIMARY_OUT_SECTION] = []
        except json.JSONDecodeError:
            lm_output = {PRIMARY_OUT_SECTION: []}
    lm_output_pk_set = {str(e["primaryKey"]) for e in lm_output[PRIMARY_OUT_SECTION]}
    lm_output_index = {str(e["primaryKey"]): e for e in lm_output[PRIMARY_OUT_SECTION]}
    _log(f"[*] Loaded {len(lm_output_pk_set):,} previously-translated entries from {os.path.basename(OUTPUT_FILE)}")

    _log("[*] Indexing localization_translated.json by primaryKey for O(1) updates…")
    for section in ONSCREENS_SECTIONS:
        idx = {}
        for e in translated.get(section, []):
            pk = e.get("primaryKey")
            if pk is not None:
                idx[str(pk)] = e
        translated_index[section] = idx
        _log(f"  {section}: indexed {len(idx):,} entries")

    # Dedupe across both sister sections — each pk handled once.
    unique: dict[str, dict] = {}
    for section, entries in queue.get("missing", {}).items():
        for e in entries:
            unique.setdefault(str(e["primaryKey"]), e)
    total_unique = len(unique)

    queue_items: list[tuple[str, str, str]] = []
    for pk, e in unique.items():
        if pk in lm_output_pk_set:
            continue
        src = (e.get("english_female") or "").strip()
        if not src:
            continue
        queue_items.append((pk, e.get("secondaryKey", "") or "", src))

    already_done = len(lm_output_pk_set)
    return queue_items, already_done, total_unique


# ── preflight ───────────────────────────────────────────────────────────
def preflight() -> None:
    _log("[*] preflight: pinging LM Studio…")
    try:
        resp = lm_client.chat.completions.create(
            model=LM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Apply"},
            ],
            temperature=0.0,
            max_tokens=32,
        )
        sample = clean_response(resp.choices[0].message.content)
        _log(f"[*] preflight ok — 'Apply' -> {sample!r}")
    except Exception as e:
        sys.exit(
            f"FATAL: cannot reach LM Studio at {LM_URL}\n"
            f"  {type(e).__name__}: {e}\n"
            f"  Open LM Studio, load a model, start the local server, and retry."
        )


# ── main ────────────────────────────────────────────────────────────────
def main():
    global lm_client, TEMPERATURE

    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--single", action="store_true",
                    help="One-string-per-call mode (slower)")
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMP,
                    help=f"LM temperature (default {DEFAULT_TEMP})")
    args = ap.parse_args()
    TEMPERATURE = args.temperature

    lm_client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=600)

    # ── monitor-expected start markers ──
    _log("[*] Using LM Studio (Gemma-2-27b)")
    mode_label = "single" if args.single else f"batch-dynamic (<={DYN_MAX_LINES} lines / ~{DYN_MAX_WORDS} words)"
    _log(f"[*] Mode: {mode_label}")
    _log(f"[*] Temperature: {TEMPERATURE}")
    _log(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]")

    preflight()
    queue_items, already_done, total_unique = load_state()
    remaining = len(queue_items)

    # ── monitor-expected scan markers ──
    _log(f"[*] Global queue: {remaining:,} pending items "
         f"(deduped from {total_unique:,} unique keys, "
         f"{already_done:,} already translated)")

    if not queue_items:
        _log("[*] Done. Fixed 0 fields (nothing to do).")
        return

    fixed_global = 0  # this run's count
    tm_done = 0
    fast_done = 0

    # ── Phase 2: TM + fast-track (single-threaded, instant) ──
    _log("[*] Phase 2: applying TM cache + fast-track dictionary...")
    slow_global: list[tuple[str, str, str]] = []  # (pk, sk, src)

    for pk, sk, src in queue_items:
        cached = tm_cache.get(src)
        if cached and is_valid_translation(src, cached):
            with state_lock:
                _record_success(pk, sk, src, cached)
                fixed_global += 1
                tm_done += 1
                if fixed_global % SAVE_EVERY == 0:
                    save_all()
                    _log(f"  [~] Saved — {fixed_global:,} fixed, ~{remaining - fixed_global:,} remaining")
            continue
        ft = try_fast_track(src)
        if ft and is_valid_translation(src, ft):
            with state_lock:
                _record_success(pk, sk, src, ft)
                fixed_global += 1
                fast_done += 1
                if fixed_global % SAVE_EVERY == 0:
                    save_all()
                    _log(f"  [~] Saved — {fixed_global:,} fixed, ~{remaining - fixed_global:,} remaining")
            continue
        slow_global.append((pk, sk, src))

    _log(
        f"[*] Phase 2 done: {tm_done:,} TM hits, {fast_done:,} fast-track hits, "
        f"{len(slow_global):,} need LM"
    )
    with state_lock:
        save_all()

    if not slow_global:
        _log(f"[*] Done. Fixed {fixed_global:,} fields (no LM work needed).")
        return

    # ── Phase 3: parallel batched LM calls ──
    def _text_for(item):
        return item[2]  # src
    batches = [[it] for it in slow_global] if args.single \
              else list(build_dynamic_batches(slow_global, _text_for))

    _log(
        f"[*] Phase 3: {len(batches):,} batches "
        f"(<= {DYN_MAX_LINES} lines / ~{DYN_MAX_WORDS} words each), "
        f"{PARALLEL_WORKERS} concurrent workers"
    )

    def _do_one_batch(texts):
        if len(texts) == 1:
            return [translate_one(texts[0])]
        return translate_batch(texts)

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        future_to_batch = {
            pool.submit(_do_one_batch, [it[2] for it in batch]): batch
            for batch in batches
        }
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                translations = future.result()
            except Exception as e:
                _log(f"  [!] Batch exception: {e}")
                translations = [it[2] for it in batch]  # fall back to originals

            with state_lock:
                for k, (pk, sk, src) in enumerate(batch):
                    new_val = translations[k] if k < len(translations) else src
                    if is_valid_translation(src, new_val):
                        _record_success(pk, sk, src, new_val)
                        _log(
                            f"  onscreens.json:{pk} [femaleVariant]  "
                            f"{src[:30]!r} -> {new_val[:45]!r}"
                        )
                    else:
                        _record_skip(pk)
                        save_skips()
                        _log(
                            f"  onscreens.json:{pk} [femaleVariant]  "
                            f"{src[:30]!r} → [SKIP] {new_val[:25]!r}"
                        )
                    fixed_global += 1
                    if fixed_global % SAVE_EVERY == 0:
                        save_all()
                        _log(
                            f"  [~] Saved — {fixed_global:,} fixed, "
                            f"~{remaining - fixed_global:,} remaining"
                        )

    with state_lock:
        save_all()
    _log(
        f"[*] Done. Fixed {fixed_global:,} fields "
        f"({tm_done:,} TM, {fast_done:,} FT, "
        f"{fixed_global - tm_done - fast_done:,} via LM)."
    )


if __name__ == "__main__":
    main()
