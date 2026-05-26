"""
translate_cleanup_all.py
========================
Final-sweep translator for the 100%-completion run.

Differs from `translate_queue_fast.py` in one critical way: it's
SECTION-AWARE. Each queue item carries its source section name, and
translation results are written back to that exact section in
`localization_translated.json`. The legacy script hardcodes the two
onscreens sections — fine for the bulk onscreens run, but it silently
discards subtitle-section entries.

Mirrors all the perf tuning from translate_queue_fast.py:
  • Gemma-2-27B on LM Studio (PARALLEL=4 slots)
  • Dynamic batches: <=12 lines / ~100 words
  • LONG_ITEM_CHAR_THRESHOLD: items > 200 chars bypass batching
  • Instant single-mode failover on context-400 errors
  • Same monitor-watched log file shape — cp2077 adapter parses it
    unchanged

When the queue empties, the script chains `rebuild_onscreens_and_pack.py`
so the new onscreens translations land in the deployed mod archive
without any second command. Subtitle entries (much rarer in this final
sweep) still require a follow-up `cp2077_subtitle_batch.py` run to bake
into CR2W files — the script prints a reminder at the end.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI


if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", write_through=True
    )

SCRIPTS_DIR = r"C:\Users\nc528\סקריפטים\תרגום משחקים"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
RESOURCES   = os.path.join(PROJECT, "source", "resources")

QUEUE_FILE      = os.path.join(SCRIPTS_DIR, "cleanup_queue.json")
TRANSLATED_FILE = os.path.join(RESOURCES, "localization_translated.json")
TM_CACHE_FILE   = os.path.join(RESOURCES, "tm_cache.json")
SKIP_FILE       = os.path.join(RESOURCES, "translation_skips.json")
LM_OUTPUT       = os.path.join(SCRIPTS_DIR, "cleanup_lm_output.json")

# Monitor-watched log — same file translate_queue_fast.py writes to so the
# existing adapter's regexes match unchanged.
MONITOR_LOG = os.path.join(SCRIPTS_DIR, "fix_missing_translations.log")
RUNTIME_LOG = os.path.join(SCRIPTS_DIR, "translate_cleanup_all.runtime.log")

REBUILD_SCRIPT = os.path.join(SCRIPTS_DIR, "rebuild_onscreens_and_pack.py")

DYN_MAX_LINES    = 12
DYN_MAX_WORDS    = 100
LONG_ITEM_CHAR_THRESHOLD = 200
PARALLEL_WORKERS = 4
SAVE_EVERY       = 50      # checkpoint cadence — cleanup queue is small, save often

LM_URL          = "http://127.0.0.1:1234/v1"
LM_MODEL        = "local-model"
DEFAULT_TEMP    = 0.3
MAX_TOKENS      = 512

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

BATCH_PROMPT_HEADER = (
    "Translate each line below to Hebrew.\n"
    "Format your output exactly as:\n"
    "1. [Hebrew translation 1]\n"
    "2. [Hebrew translation 2]\n\n"
)

TEMPERATURE: float = DEFAULT_TEMP
lm_client: OpenAI | None = None
translated: dict = {}                       # full localization_translated.json
translated_index: dict[str, dict] = {}      # section -> {pk -> entry}
tm_cache: dict[str, str] = {}
skips: set[tuple[str, str, str]] = set()    # (section, pk, "femaleVariant")
state_lock = threading.Lock()
fixed_counter = 0
total_to_do   = 0


def _log(msg: str) -> None:
    line = msg.rstrip("\n")
    print(line, flush=True)
    for path in (MONITOR_LOG, RUNTIME_LOG):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


_THINK_RE  = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX_RE = re.compile(r"^\s*(?:translation|תרגום|hebrew|output|answer)\s*[:\-]\s*", re.IGNORECASE)


def clean_response(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = _THINK_RE.sub("", raw).strip()
    s = re.sub(r"^\*+\s*(.+?)\s*\*+$", r"\1", s).strip()
    s = re.sub(r"^_+\s*(.+?)\s*_+$", r"\1", s).strip()
    s = _PREFIX_RE.sub("", s).strip()
    return s


def has_hebrew(text: str) -> bool:
    return bool(re.search(r"[֐-׿]", text))


def is_valid_translation(orig: str, trans: str) -> bool:
    if not trans or not isinstance(trans, str):
        return False
    if trans.strip() == orig.strip():
        return False
    if not has_hebrew(trans):
        return False
    # Tag preservation — same as legacy script
    tags = re.findall(r"<.*?>|\{.*?\}|%[a-zA-Z]", orig)
    for tag in tags:
        if tag not in trans:
            return False
    return True


def _is_context_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return "context size" in s or "context length" in s or "context_length" in s


def _looks_like_framework_placeholder(src: str) -> bool:
    """Items leading with a CR2W control byte (0x01-0x05) followed by Rich-text
    or interpolation markup are formatting placeholders. The LM can't translate
    them cleanly — it either strips the control byte (breaks the engine) or
    hallucinates partial Hebrew that fails tag validation. Pre-skip to save
    LM Studio calls and silence the noise in the monitor feed."""
    if not src:
        return False
    first = src[0]
    if not (0x01 <= ord(first) <= 0x05):
        return False
    rest = src[1:].lstrip()
    return rest.startswith(("<Rich", "<rich", "{", "<"))


def build_dynamic_batches(items, text_for):
    """Mirrors translate_queue_fast.build_dynamic_batches: long items bypass
    batching as size-1 batches; the rest pack into 100-word groups."""
    batch, words = [], 0
    for item in items:
        text = text_for(item)
        if len(text) > LONG_ITEM_CHAR_THRESHOLD:
            if batch:
                yield batch
                batch, words = [], 0
            yield [item]
            continue
        w = len(text.split())
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
                    {"role": "user",   "content": text},
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
            if _is_context_error(e):
                break
            time.sleep(2)
    return text


def _parse_batch_response(raw: str, count: int) -> list[str]:
    parsed: dict[int, str] = {}
    for line in raw.splitlines():
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
    results = list(texts)
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
    except Exception as e:
        _log(f"      [!] Batch API Error → fallback to singles: {e}")
    for i, text in enumerate(texts):
        if text and not is_valid_translation(texts[i], results[i]):
            results[i] = translate_one(text)
    return results


def _atomic_write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_all() -> None:
    """Persist localization_translated.json + tm_cache.json + skips."""
    _atomic_write_json(TRANSLATED_FILE, translated)
    try:
        _atomic_write_json(TM_CACHE_FILE, tm_cache)
    except OSError:
        pass
    try:
        _atomic_write_json(SKIP_FILE, [list(t) for t in skips])
    except OSError:
        pass


def _record_success(section: str, pk: str, secondary_key: str, src: str, hebrew: str) -> None:
    """Caller holds state_lock. Writes the Hebrew translation back into
    `translated[section]` at the entry indexed by pk."""
    idx = translated_index.get(section, {})
    entry = idx.get(pk)
    if entry is None:
        # Defensive — shouldn't happen since queue is built from the same
        # localization_translated.json we're updating.
        new_entry = {
            "primaryKey":    int(pk) if pk.isdigit() else pk,
            "secondaryKey":  secondary_key,
            "femaleVariant": hebrew,
            "maleVariant":   "",
        }
        translated.setdefault(section, []).append(new_entry)
        idx[pk] = new_entry
    else:
        entry["femaleVariant"] = hebrew
    tm_cache[src] = hebrew


def load_state() -> list[dict]:
    """Read queue + translated + tm_cache + skips. Returns the pending items."""
    global translated, tm_cache, skips

    if not os.path.exists(QUEUE_FILE):
        sys.exit(f"FATAL: missing {QUEUE_FILE}")

    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)

    _log(f"[*] Loading {TRANSLATED_FILE}")
    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
        translated = json.load(f)

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

    # Build per-section index so worker writeback is O(1).
    items = payload.get("queue", [])
    sections_in_queue = {it["section"] for it in items}
    for sect in sections_in_queue:
        idx = {}
        for e in translated.get(sect, []):
            pk = e.get("primaryKey")
            if pk is not None:
                idx[str(pk)] = e
        translated_index[sect] = idx
    _log(f"[*] Indexed {len(sections_in_queue)} sections for writeback")

    # Filter: drop entries already SKIPped, drop entries that now have Hebrew
    # (translated by an earlier resume), drop entries with no English source,
    # drop framework placeholders (control-byte + Rich-text/JSON markers — LM
    # mangles them and they show up as endless [SKIP] noise).
    pending = []
    framework_dropped = 0
    for it in items:
        section = it["section"]
        pk      = str(it["primaryKey"])
        if (section, pk, "femaleVariant") in skips:
            continue
        entry = translated_index.get(section, {}).get(pk)
        if entry is not None:
            existing_fv = (entry.get("femaleVariant") or "").strip()
            if existing_fv and has_hebrew(existing_fv):
                continue  # already translated since the queue was built
        src = (it.get("english_female") or it.get("english_male") or "").strip()
        if not src:
            continue
        if _looks_like_framework_placeholder(src):
            framework_dropped += 1
            continue
        pending.append({
            "section": section,
            "primaryKey": pk,
            "secondaryKey": it.get("secondaryKey") or "",
            "src": src,
        })

    if framework_dropped:
        _log(f"[*] Pre-filtered {framework_dropped:,} framework placeholders "
             f"(control-byte + Rich-text markers — not translatable)")
    return pending


def preflight() -> None:
    _log("[*] preflight: pinging LM Studio…")
    try:
        resp = lm_client.chat.completions.create(
            model=LM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": "Apply"},
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
            f"  Open LM Studio, load Gemma-2-27B, start the local server, and retry."
        )


def chain_rebuild() -> None:
    _log("")
    _log("=" * 64)
    _log(f"[*] Chaining rebuild: {REBUILD_SCRIPT}")
    _log("=" * 64)
    try:
        r = subprocess.run(
            [sys.executable, REBUILD_SCRIPT],
            cwd=SCRIPTS_DIR,
        )
        _log(f"[*] Rebuild exited with code {r.returncode}")
    except Exception as e:
        _log(f"[!] Rebuild chain failed: {e}")


def main() -> None:
    global lm_client, TEMPERATURE, fixed_counter, total_to_do

    ap = argparse.ArgumentParser(description="Final-sweep section-aware translator.")
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMP,
                    help=f"LM temperature (default {DEFAULT_TEMP})")
    ap.add_argument("--no-rebuild", action="store_true",
                    help="Skip the rebuild_onscreens_and_pack.py chain at the end")
    args = ap.parse_args()
    TEMPERATURE = args.temperature

    lm_client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=600)

    # Monitor-recognized start markers (translate_queue_fast.py format).
    _log("[*] Using LM Studio (Gemma-2-27b)")
    _log(f"[*] Mode: batch-dynamic (<={DYN_MAX_LINES} lines / ~{DYN_MAX_WORDS} words)")
    _log(f"[*] Temperature: {TEMPERATURE}")
    _log(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]")

    preflight()
    pending = load_state()
    total_to_do = len(pending)
    _log(f"[*] Global queue: {total_to_do:,} pending items "
         f"(deduped across sections; cleanup mode)")

    if total_to_do == 0:
        _log("[*] Nothing to translate — exiting before any LM calls.")
        if not args.no_rebuild:
            chain_rebuild()
        return

    # Try TM cache first — instant hits for any string we've seen before.
    _log("[*] Phase 2: applying TM cache (instant)")
    tm_hits = 0
    still_pending: list[dict] = []
    for it in pending:
        cached = tm_cache.get(it["src"])
        if cached and has_hebrew(cached):
            with state_lock:
                _record_success(it["section"], it["primaryKey"],
                                it["secondaryKey"], it["src"], cached)
                fixed_counter += 1
                tm_hits += 1
                if fixed_counter % SAVE_EVERY == 0:
                    save_all()
                    _log(f"  [~] Saved — {fixed_counter:,} fixed, "
                         f"~{total_to_do - fixed_counter:,} remaining")
        else:
            still_pending.append(it)
    if tm_hits:
        _log(f"[*] Phase 2 done: {tm_hits:,} TM cache hits, "
             f"{len(still_pending):,} need LM Studio")
        save_all()

    if not still_pending:
        _log(f"\n[*] Done. Fixed {fixed_counter:,} fields (0 via LM, "
             f"{tm_hits} via TM cache, 0 skipped).")
        if not args.no_rebuild:
            chain_rebuild()
        return

    # Build batches over remaining items.
    batches = list(build_dynamic_batches(
        still_pending, text_for=lambda it: it["src"]
    ))
    _log(f"[*] Phase 3: {len(batches):,} batches "
         f"(<= {DYN_MAX_LINES} lines / ~{DYN_MAX_WORDS} words each), "
         f"{PARALLEL_WORKERS} concurrent workers")

    def _do_one_batch(items: list[dict]) -> list[str]:
        texts = [it["src"] for it in items]
        if len(items) == 1:
            return [translate_one(texts[0])]
        return translate_batch(texts)

    skip_count = 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        future_to_batch = {pool.submit(_do_one_batch, b): b for b in batches}
        for fut in as_completed(future_to_batch):
            batch = future_to_batch[fut]
            try:
                outs = fut.result()
            except Exception as e:
                _log(f"  [!] Batch exception: {e}")
                outs = [it["src"] for it in batch]

            with state_lock:
                for k, it in enumerate(batch):
                    new_val = outs[k] if k < len(outs) else it["src"]
                    short_sect = it["section"].split("/")[-1]
                    if is_valid_translation(it["src"], new_val):
                        _record_success(it["section"], it["primaryKey"],
                                        it["secondaryKey"], it["src"], new_val)
                        fixed_counter += 1
                        _log(f"  {short_sect[:35]}:{it['primaryKey']} "
                             f"{it['src'][:30]!r} -> {new_val[:45]!r}")
                    else:
                        skips.add((it["section"], it["primaryKey"], "femaleVariant"))
                        skip_count += 1
                        _log(f"  {short_sect[:35]}:{it['primaryKey']} "
                             f"{it['src'][:30]!r} → [SKIP] {new_val[:25]!r}")

                    if fixed_counter % SAVE_EVERY == 0 and fixed_counter:
                        save_all()
                        _log(f"  [~] Saved — {fixed_counter:,} fixed, "
                             f"~{total_to_do - fixed_counter - skip_count:,} remaining")

    with state_lock:
        save_all()

    _log("")
    _log(f"[*] Done. Fixed {fixed_counter:,} fields "
         f"({tm_hits} via TM, {fixed_counter - tm_hits} via LM, "
         f"{skip_count} permanently skipped).")

    if not args.no_rebuild:
        chain_rebuild()


if __name__ == "__main__":
    main()
