"""
cp2077_fix_missing_translations.py  v2  (batch edition)
---------------------------------------------------------
Finds all untranslated / no-Hebrew entries in localization_translated.json
and retranslates them via the local LM Studio server.

NEW in v2: sends up to BATCH_SIZE entries per API call → ~5× faster.

Usage:
    python cp2077_fix_missing_translations.py              # batch mode (default, LM Studio)
    python cp2077_fix_missing_translations.py --single     # single-entry mode (safer)
    python cp2077_fix_missing_translations.py --claude     # batch mode via Anthropic API
    python cp2077_fix_missing_translations.py --claude --single  # single-entry via Anthropic

Safe to Ctrl+C and restart — saves every SAVE_EVERY fixes.
Default: LM Studio on http://127.0.0.1:1234 with Gemma-2-27b loaded.
With --claude: requires ANTHROPIC_API_KEY env var set.

Filters: only processes files in onscreens/ or subtitles/ folders.
Skips UI bindings ("+W", "Q", "[" etc — strings with ≤1 English letter).
"""

import io
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
import anthropic

# Force UTF-8 output so Hebrew text in log lines doesn't crash under cp1255.
# write_through=True preserves the -u unbuffered behaviour after wrapping.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", write_through=True
    )

# ── config ─────────────────────────────────────────────────────────────────────
BASE = r"C:\Users\Nehoray_Cohen\Projects\Game translator\תרגום_משחקים\source\resources"
ORIGINAL_FILE = os.path.join(BASE, "localization_export.json")
TRANSLATED_FILE = os.path.join(BASE, "localization_translated.json")
SKIP_FILE = os.path.join(BASE, "translation_skips.json")  # entries that always fail
TM_CACHE_FILE = os.path.join(BASE, "tm_cache.json")  # exact-match translation memory

BATCH_SIZE = 3  # legacy default; runtime override below picks 6 (LM Studio) / 10 (Claude) / 1 (--single)
SAVE_EVERY = 200  # checkpoint cadence — write all 3 JSON state files every N fixes

ALLOWED_FOLDERS = ["onscreens", "subtitles"]

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
    f"Translate each line below to Hebrew.\n"
    f"Format your output exactly as:\n"
    f"1. [Hebrew translation 1]\n"
    f"2. [Hebrew translation 2]\n\n"
)

# Global clients and flags (initialized in main)
USE_CLAUDE = False
lm_studio_client = None
claude_client = None
translated: dict = {}  # {filepath: [entries]} loaded from TRANSLATED_FILE
skips: set = set()     # {(filepath, idx, field)} loaded from SKIP_FILE
tm_cache: dict = {}    # exact-match {English: Hebrew} loaded from TM_CACHE_FILE

# Dynamic-batching caps (used in main loop)
DYN_MAX_WORDS = 150  # soft cap — close batch when accumulated word count exceeds this
DYN_MAX_LINES = 12   # hard cap — never exceed this many items per API call

# Concurrency — LM Studio runs with PARALLEL=4. Saturating all 4 slots doubles GPU
# utilisation and roughly doubles steady-state Phase 3 throughput on the RX 9070.
PARALLEL_WORKERS = 4
state_lock = threading.Lock()  # guards shared mutations: translated, tm_cache, skips, fixed, file I/O


# ── helpers ────────────────────────────────────────────────────────────────────


def in_allowed_folder(path):
    return any(f in path.lower() for f in ALLOWED_FOLDERS)


def has_latin(text):
    """If there's no English letter at all (e.g. '123' or '---'), skip translation."""
    return bool(re.search(r"[A-Za-z]", text))


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX_RE = re.compile(
    r"^\s*(?:translation|תרגום|hebrew|output|answer)\s*[:\-]\s*", re.IGNORECASE
)


def clean_response(raw):
    if not isinstance(raw, str):
        return ""
    s = _THINK_RE.sub("", raw).strip()
    s = re.sub(r"^\*+\s*(.+?)\s*\*+$", r"\1", s).strip()
    s = re.sub(r"^_+\s*(.+?)\s*_+$", r"\1", s).strip()
    s = _PREFIX_RE.sub("", s).strip()
    return s


def has_hebrew(text):
    return bool(re.search(r"[\u0590-\u05FF]", text))


def check_tags_preserved(orig, trans):
    """מוודא שכל משתני הקוד מהמקור קיימים גם בתרגום כדי למנוע קריסות משחק"""
    tags = re.findall(r"<.*?>|\{.*?\}|%[a-zA-Z]", orig)
    for tag in tags:
        if tag not in trans:
            return False
    return True


def is_valid_translation(orig_text, trans_text):
    """בודק גם אם יש עברית, גם שאין שפות זרות, וגם שהתגיות נשמרו"""
    if not trans_text or not isinstance(trans_text, str):
        return False
    if not has_hebrew(trans_text):
        return False
    # בדיקת שפות זרות (רוסית, ערבית וכו')
    if re.search(
        r"[\u0400-\u04FF\u0600-\u06FF\u0E00-\u0E7F\u0900-\u097F\u4E00-\u9FFF]",
        trans_text,
    ):
        return False
    # בדיקה קריטית: האם תגיות הקוד נשמרו
    if not check_tags_preserved(orig_text, trans_text):
        return False
    return True


def needs_translation(orig, trans):
    if not orig:
        return False
    if is_valid_translation(orig, trans):
        return False
    if not has_latin(orig):
        return False
    # UI binding / single-letter symbol — skip
    cleaned = re.sub(r"<[^>]+>", "", orig)
    if len(re.sub(r"[^a-zA-Z]", "", cleaned)) <= 1:
        return False
    return True


# ── Fast-track dictionary ─────────────────────────────────────────────────────
# Trivial 1-2 word phrases that translate unambiguously. Imperatives default to
# masculine form (matches what the LM produces for both gender fields anyway).
# Anything with slang, sarcasm, or context-dependence MUST go to the LM.

FAST_TRACK_DICT = {
    # Affirmation
    "yes": "כן", "yeah": "כן", "yep": "כן", "yup": "כן",
    "sure": "בטח", "ok": "אוקיי", "okay": "אוקיי", "alright": "בסדר",
    # Negation
    "no": "לא", "nope": "לא", "nah": "לא",
    # Greetings
    "hello": "שלום", "hi": "היי", "hey": "היי",
    "bye": "ביי", "goodbye": "להתראות",
    # Politeness
    "thanks": "תודה", "thank you": "תודה", "please": "בבקשה",
    "sorry": "סליחה", "excuse me": "סלח לי",
    # Commands (masculine imperative)
    "wait": "חכה", "stop": "עצור", "go": "לך",
    "look": "תראה", "listen": "תקשיב", "help": "הצילו",
    "come on": "נו", "hurry": "מהר",
    # Profanity (Cyberpunk-typical)
    "damn": "לעזאזל", "shit": "חרא", "fuck": "פאק",
    # Reactions
    "really": "באמת", "maybe": "אולי",
}

_FT_PUNCT_RE = re.compile(r"^(.+?)([\.\!\?,;:]*)$")


def try_fast_track(text):
    """Return Hebrew translation if text is a trivial dictionary phrase, else None."""
    if not text or not isinstance(text, str):
        return None
    # Skip anything with tags — fast-track only handles plain text.
    if "<" in text or "{" in text or "%" in text:
        return None
    s = text.strip()
    if not s:
        return None
    m = _FT_PUNCT_RE.match(s)
    if not m:
        return None
    core, suffix = m.group(1).strip(), m.group(2)
    hebrew = FAST_TRACK_DICT.get(core.lower())
    if hebrew is None:
        return None
    return hebrew + suffix


def build_dynamic_batches(items, text_for):
    """Yield sub-lists of `items`, grouped so cumulative word count stays under
    DYN_MAX_WORDS and len(batch) <= DYN_MAX_LINES.

    `text_for(item)` returns the source string for word counting. Items can be
    any tuple shape — the caller's `text_for` callback knows how to unpack.
    A single oversized line still gets a batch of 1 (we never split a single string).
    """
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


# ── AI calls ───────────────────────────────────────────────────────────────────


def translate_one(text, retries=3):
    """Translates a single string."""
    for attempt in range(1, retries + 1):
        try:
            if USE_CLAUDE:
                resp = claude_client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": text},
                    ],
                )
                raw = (resp.content[0].text or "").strip()
            else:
                resp = lm_studio_client.chat.completions.create(
                    model="local-model",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": text},
                    ],
                    temperature=0.1,
                    max_tokens=512,
                )
                raw = (resp.choices[0].message.content or "").strip()

            result = clean_response(raw)

            # Sometimes it prefixes with "1. " even in single mode
            m = re.match(r"^\s*1\.\s*(.+)", result)
            if m:
                result = m.group(1).strip()

            if is_valid_translation(text, result):
                return result
            else:
                print(f"      [!] Bad output (attempt {attempt}): {result!r}")
        except Exception as e:
            print(f"      [!] API Error (attempt {attempt}): {e}")
            time.sleep(2)
    return text  # fallback to original


def _parse_batch_response(raw_text, count):
    """Extracts '1. xxx \n 2. yyy' format into a list."""
    parsed = {}
    for line in raw_text.splitlines():
        line = line.strip()
        m = re.match(r"^\s*(\d+)\.\s*(.+)", line)
        if m:
            idx = int(m.group(1)) - 1
            if 0 <= idx < count:
                parsed[idx] = clean_response(m.group(2))

    # Fill missing ones with empty string so validation fails later
    return [parsed.get(i, "") for i in range(count)]


def translate_batch(texts):
    """Translates multiple strings at once. Falls back to single if batch fails."""
    non_empty = [(i, c) for i, c in enumerate(texts) if c]
    if not non_empty:
        return texts

    user_text = BATCH_PROMPT_HEADER
    for j, (_, text) in enumerate(non_empty):
        user_text += f"{j + 1}. {text}\n"

    for attempt in range(2):
        try:
            if USE_CLAUDE:
                resp = claude_client.messages.create(
                    model="claude-3-5-sonnet-latest",
                    max_tokens=512,
                    system=SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": user_text},
                    ],
                )
                raw = (resp.content[0].text or "").strip()
            else:
                resp = lm_studio_client.chat.completions.create(
                    model="local-model",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_text},
                    ],
                    temperature=0.1,
                    max_tokens=512,
                )
                raw = (resp.choices[0].message.content or "").strip()

            parsed = _parse_batch_response(raw, len(non_empty))

            results = list(texts)
            success_count = 0

            for k, (orig_idx, _) in enumerate(non_empty):
                if is_valid_translation(texts[orig_idx], parsed[k]):
                    results[orig_idx] = parsed[k]
                    success_count += 1

            if success_count == len(non_empty):
                return results

            print(
                f"      [~] Batch partial: {success_count} ok, {len(non_empty) - success_count} going to single mode"
            )
            break  # skip retry, just fall back to single mode

        except Exception as e:
            print(f"      [!] Batch API Error: {e}")
            time.sleep(2)

    # Fallback: anything that didn't get a valid translation gets done 1-by-1
    results = list(texts)
    for i, text in enumerate(texts):
        if text and not is_valid_translation(texts[i], results[i]):
            results[i] = translate_one(text)

    return results


# ── File saving functions ───────────────────────────────────────────────────────


def save():
    """Atomic Save - שומר לקובץ זמני ורק אז דורס את המקורי כדי למנוע השחתה מקריסות"""
    temp_file = TRANSLATED_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, TRANSLATED_FILE)
    except Exception as e:
        print(f"  [!] Error during Atomic Save: {e}")


def save_skips():
    """שמירת הדילוגים"""
    temp_file = SKIP_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(list(skips), f, ensure_ascii=False, indent=2)
        os.replace(temp_file, SKIP_FILE)
    except Exception as e:
        pass


def save_tm():
    """Atomic save for the translation-memory cache."""
    temp_file = TM_CACHE_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(tm_cache, f, ensure_ascii=False, indent=2)
        os.replace(temp_file, TM_CACHE_FILE)
    except Exception:
        pass


# ── Main ───────────────────────────────────────────────────────────────────────


def main():
    global translated, skips, tm_cache, USE_CLAUDE, lm_studio_client, claude_client, BATCH_SIZE

    USE_CLAUDE = "--claude" in sys.argv
    is_single = "--single" in sys.argv

    if USE_CLAUDE:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("[!] Error: ANTHROPIC_API_KEY environment variable not set")
            sys.exit(1)
        claude_client = anthropic.Anthropic(api_key=api_key)
        BATCH_SIZE = 10 if not is_single else 1
        print(f"[*] Using Anthropic API (Claude 3.5 Sonnet)")
    else:
        lm_studio_client = OpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio", timeout=600)
        BATCH_SIZE = 6 if not is_single else 1
        print(f"[*] Using LM Studio (Gemma-2-27b)")

    batch_size = BATCH_SIZE
    mode_label = "single" if batch_size == 1 else f"batch-dynamic (<={DYN_MAX_LINES} lines / ~{DYN_MAX_WORDS} words)"
    print(f"[*] Mode: {mode_label}")
    print(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]")

    try:
        with open(SKIP_FILE, "r", encoding="utf-8") as f:
            try:
                skips = set(tuple(x) for x in json.load(f))
            except Exception:
                skips = set()
    except FileNotFoundError:
        skips = set()

    print(f"[*] Loaded {len(skips)} permanently skipped entries")

    try:
        with open(TM_CACHE_FILE, "r", encoding="utf-8") as f:
            tm_cache = json.load(f)
        if not isinstance(tm_cache, dict):
            tm_cache = {}
    except (FileNotFoundError, json.JSONDecodeError):
        tm_cache = {}

    print(f"[*] Loaded {len(tm_cache)} TM cache entries")

    print(f"[*] Loading {ORIGINAL_FILE}")
    with open(ORIGINAL_FILE, "r", encoding="utf-8") as f:
        original = json.load(f)

    print(f"[*] Loading {TRANSLATED_FILE}")
    if os.path.exists(TRANSLATED_FILE):
        with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
            translated = json.load(f)
    else:
        translated = {}

    # ── Phase 1: build the global pending queue ───────────────────────────────
    print("[*] Phase 1: scanning all files for pending translations...")
    global_pending = []  # list of (filepath, idx, field)
    for filepath, orig_entries in original.items():
        if not in_allowed_folder(filepath):
            continue
        trans_entries = translated.setdefault(filepath, [])
        while len(trans_entries) < len(orig_entries):
            trans_entries.append(orig_entries[len(trans_entries)].copy())

        for i, orig in enumerate(orig_entries):
            t = trans_entries[i]
            for field in ("femaleVariant", "maleVariant"):
                if (filepath, str(i), field) in skips:
                    continue
                # Fall back to translated entry's current value when the export
                # has an empty field (re-extracted subtitle entries store the
                # English source there).
                src = orig.get(field, "") or t.get(field, "")
                if needs_translation(src, t.get(field, "")):
                    global_pending.append((filepath, i, field))

    total_need = len(global_pending)
    skipped_files = len(original) - sum(1 for p in original if in_allowed_folder(p))
    print(
        f"[*] Global queue: {total_need:,} pending items "
        f"(skipped {skipped_files} files outside onscreens/subtitles)"
    )

    if total_need == 0:
        return

    fixed = 0

    # ── Phase 2: apply TM cache + fast-track dictionary (single threaded) ─────
    print("[*] Phase 2: applying TM cache + fast-track dictionary...")
    slow_global = []  # list of (filepath, i, field, src) needing the LM
    tm_done = 0
    fast_done = 0
    for filepath, i, field in global_pending:
        src = original[filepath][i].get(field, "") or translated[filepath][i].get(field, "")

        # 1) TM cache — exact-match memory of prior successful translations
        cached = tm_cache.get(src)
        if cached and is_valid_translation(src, cached):
            translated[filepath][i][field] = cached
            fixed += 1
            tm_done += 1
            if fixed % SAVE_EVERY == 0:
                save(); save_tm()
                print(f"  [~] Saved — {fixed:,} fixed, ~{total_need - fixed:,} remaining")
            continue

        # 2) Fast-track dictionary
        ft = try_fast_track(src)
        if ft is not None and is_valid_translation(src, ft):
            translated[filepath][i][field] = ft
            fixed += 1
            fast_done += 1
            if fixed % SAVE_EVERY == 0:
                save(); save_tm()
                print(f"  [~] Saved — {fixed:,} fixed, ~{total_need - fixed:,} remaining")
            continue

        slow_global.append((filepath, i, field, src))

    print(
        f"[*] Phase 2 done: {tm_done:,} TM hits, {fast_done:,} fast-track hits, "
        f"{len(slow_global):,} need LM"
    )
    save(); save_tm()

    if not slow_global:
        print(f"\n[*] Done. Fixed {fixed:,} fields (no LM work needed).")
        return

    # ── Phase 3: cross-file dynamic batching + concurrent LM calls ────────────
    def _text_for(item):
        return item[3]  # src is index 3 in (filepath, i, field, src)

    if batch_size == 1:
        batches = [[item] for item in slow_global]
    else:
        batches = list(build_dynamic_batches(slow_global, _text_for))

    print(
        f"[*] Phase 3: {len(batches):,} batches "
        f"(<= {DYN_MAX_LINES} lines / ~{DYN_MAX_WORDS} words each), "
        f"{PARALLEL_WORKERS} concurrent workers"
    )

    def _do_one_batch(texts):
        """Worker — only touches its argument and the HTTP client, no shared state."""
        if len(texts) == 1:
            return [translate_one(texts[0])]
        return translate_batch(texts)

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        future_to_batch = {
            executor.submit(_do_one_batch, [item[3] for item in batch]): batch
            for batch in batches
        }
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                translations = future.result()
            except Exception as e:
                print(f"  [!] Batch exception: {e}")
                translations = [item[3] for item in batch]  # fall back to originals

            with state_lock:
                for k, (filepath, i, field, src) in enumerate(batch):
                    new_val = translations[k] if k < len(translations) else src
                    translated[filepath][i][field] = new_val
                    fixed += 1
                    short_fp = filepath.split("/")[-1]

                    if is_valid_translation(src, new_val):
                        tm_cache[src] = new_val
                        print(
                            f"  {short_fp[:35]}:{i} [{field}]  "
                            f"{src[:30]!r} -> {new_val[:45]!r}"
                        )
                    else:
                        skips.add((filepath, str(i), field))
                        save_skips()
                        print(
                            f"  {short_fp[:35]}:{i} [{field}]  "
                            f"{src[:30]!r} → [SKIP] {new_val[:25]!r}"
                        )

                    if fixed % SAVE_EVERY == 0:
                        save(); save_tm()
                        print(
                            f"  [~] Saved — {fixed:,} fixed, "
                            f"~{total_need - fixed:,} remaining"
                        )

    with state_lock:
        save(); save_tm()
    print(
        f"\n[*] Done. Fixed {fixed:,} fields "
        f"({tm_done:,} TM, {fast_done:,} FT, {fixed - tm_done - fast_done:,} via LM)."
    )


if __name__ == "__main__":
    main()
