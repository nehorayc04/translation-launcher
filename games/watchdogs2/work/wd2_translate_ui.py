"""
wd2_translate_ui.py
===================
High-throughput LM-Studio translator for Watch Dogs 2 UI strings.
Reads English text from oasisstrings XML (authoritative source),
filters out BarkSubtitles (dialogue), and translates the remaining
~29,579 UI strings to Hebrew.

Architecture mirrors translate_queue_fast.py from Cyberpunk 2077:
  • Phase 1: Load & filter strings from XML
  • Phase 2: TM cache + fast-track dictionary (instant)
  • Phase 3: Dynamic batches dispatched to LM Studio

Outputs:
  wd2_ui_translated.json       {id: hebrew_text} for all translated strings
  wd2_tm_cache.json             TM cache for resumability
  wd2_translate_ui.log          runtime log

Usage:
  python wd2_translate_ui.py [--single] [--temperature 0.3] [--workers 4]
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
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI

# ── force UTF-8 output ──
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace", write_through=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace", write_through=True
    )

# ── paths ────────────────────────────────────────────────────────────────
BASE = r"c:\Users\Nehoray_Cohen\Projects\Game translator\games\watchdogs2"
EXTRACT = os.path.join(BASE, "extract")

XML_PATHS = [
    os.path.join(EXTRACT, "en_oasis", "languages", "english", "oasisstrings_converted.xml"),
    os.path.join(EXTRACT, "patch2_en", "languages", "english", "oasisstrings_converted.xml"),
]

OUTPUT_FILE   = os.path.join(BASE, "extract", "wd2_ui_translated.json")
TM_CACHE_FILE = os.path.join(BASE, "extract", "wd2_tm_cache.json")
RUNTIME_LOG   = os.path.join(BASE, "wd2_translate_ui.log")

# ── tuning ───────────────────────────────────────────────────────────────
DYN_MAX_LINES    = 12
DYN_MAX_WORDS    = 100
LONG_ITEM_THRESH = 200
SAVE_EVERY       = 200

# ── LM Studio ───────────────────────────────────────────────────────────
LM_URL     = "http://127.0.0.1:1234/v1"
LM_MODEL   = "local-model"
DEFAULT_TEMP = 0.3
MAX_TOKENS = 512

SYSTEM_PROMPT = (
    "You are a professional game localizer for Watch Dogs 2. Translate the "
    "user's English text to Hebrew with a hacker/tech-savvy, San Francisco "
    "underground tone suitable for an open-world action game.\n"
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
    "  • Keep tags like \\n, [LF], [CR], {0}, %d, %u, %s, %i, "
    "[#PLAYER], [#ACTIVITY], [#MISSION], [CSS_*], [CREDITS], "
    "[SMARTPHONE_SELECT], [RELOAD], [NAVIGATION], [MAP_NAVIGATE], "
    "[FACTION_*], [HACK_*], &nbsp; "
    "EXACTLY as written — do not translate or alter them.\n"
    "  • Keep proper nouns (Marcus, Wrench, Sitara, Josh, Horatio, Ray, "
    "DedSec, Blume, ctOS, Nudle, Prime_Eight, Auntie Shu, "
    "Bratva, Tezcas, Sons of Ragnarok) transliterated naturally.\n"
    "  • Translate exactly what's there. NO hallucinations — if the input is a "
    "pure code, hex, placeholder, number, or a person's name, return it unchanged.\n"
    "\n"
    "Watch Dogs 2 glossary — use EXACTLY these Hebrew renderings:\n"
    "  DedSec -> דדסק\n"
    "  Hacker -> האקר\n"
    "  Hack -> האק\n"
    "  Botnet -> בוטנט\n"
    "  Followers -> עוקבים\n"
    "  ctOS -> ctOS\n"
    "  Research -> מחקר\n"
    "  Profiler -> פרופיילר\n"
)

BATCH_PROMPT_HEADER = (
    "Translate each line below to Hebrew.\n"
    "Format your output exactly as:\n"
    "1. [Hebrew translation 1]\n"
    "2. [Hebrew translation 2]\n\n"
)

# ── fast-track dictionary ───────────────────────────────────────────────
FAST_TRACK_DICT = {
    "yes": "כן", "yeah": "כן", "yep": "כן", "yup": "כן",
    "sure": "בטח", "ok": "אוקיי", "okay": "אוקיי", "alright": "בסדר",
    "no": "לא", "nope": "לא", "nah": "לא",
    "hello": "שלום", "hi": "היי", "hey": "היי",
    "bye": "ביי", "goodbye": "להתראות",
    "thanks": "תודה", "thank you": "תודה", "please": "בבקשה",
    "sorry": "סליחה", "excuse me": "סלח לי",
    "wait": "חכה", "stop": "עצור", "go": "לך",
    "look": "תראה", "listen": "תקשיב", "help": "עזרה",
    "come on": "נו", "hurry": "מהר",
    "damn": "לעזאזל", "shit": "חרא", "fuck": "פאק",
    "really": "באמת", "maybe": "אולי",
    "navigate": "ניווט", "confirm": "אישור", "exit": "יציאה",
    "select": "בחירה", "back": "חזרה", "cancel": "ביטול",
    "save": "שמירה", "load": "טעינה", "pause": "השהייה",
    "resume": "המשך", "close": "סגירה", "open": "פתיחה",
    "use": "שימוש", "take": "קח", "join": "הצטרף",
    "accept": "קבל", "decline": "דחה", "send": "שלח",
    "ready": "מוכן", "success": "הצלחה", "failed": "נכשל",
    "aim": "כוונן", "shoot": "ירה", "reload": "טען מחדש",
    "hack": "האק", "focus": "מיקוד",
    "cash": "מזומן", "ammo": "תחמושת",
    "enter": "כניסה", "details": "פרטים",
}

# ── regexes ──────────────────────────────────────────────────────────────
_THINK_RE   = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX_RE  = re.compile(r"^\s*(?:translation|תרגום|hebrew|output|answer)\s*[:\-]\s*", re.IGNORECASE)
_FT_PUNCT   = re.compile(r"^(.+?)([\.\!\?\,;:]*)$")
_TAG_RE     = re.compile(r"<.*?>|\{.*?\}|%[a-zA-Z]|\[.*?\]|&nbsp;")
_HEB_RE     = re.compile(r"[֐-׿]")
_FOREIGN_RE = re.compile(r"[Ѐ-ӿ؀-ۿ฀-๿ऀ-ॿ一-鿿]")
_LATIN_RE   = re.compile(r"[A-Za-z]")
_NIQQUD_RE  = re.compile(r"[֑-ׇ]")

# ── state ────────────────────────────────────────────────────────────────
state_lock = threading.Lock()
lm_client: OpenAI = None
TEMPERATURE = DEFAULT_TEMP
tm_cache: dict = {}
output: dict = {}         # {str(id): hebrew}
skip_set: set = set()

# ── logger ───────────────────────────────────────────────────────────────
_log_lock = threading.Lock()

def _log(line: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with _log_lock:
        print(line, flush=True)
        try:
            with open(RUNTIME_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {line}\n")
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
    s = _NIQQUD_RE.sub("", s)
    return s


def is_valid_translation(orig: str, trans: str) -> bool:
    if not trans or not isinstance(trans, str):
        return False
    if not _HEB_RE.search(trans):
        return False
    if _FOREIGN_RE.search(trans):
        return False
    return True


def needs_translation(src: str) -> bool:
    if not src or not src.strip():
        return False
    if not _LATIN_RE.search(src):
        return False
    cleaned = re.sub(r"<[^>]+>|\[[^\]]+\]", "", src)
    return len(re.sub(r"[^a-zA-Z]", "", cleaned)) > 1


def try_fast_track(text: str) -> str | None:
    if not text or "<" in text or "{" in text or "%" in text or "[" in text:
        return None
    s = text.strip()
    if not s:
        return None
    m = _FT_PUNCT.match(s)
    if not m:
        return None
    core, suffix = m.group(1).strip(), m.group(2)
    hebrew = FAST_TRACK_DICT.get(core.lower())
    return (hebrew + suffix) if hebrew else None


def build_dynamic_batches(items, text_for):
    batch, words = [], 0
    for item in items:
        text = text_for(item)
        if len(text) > LONG_ITEM_THRESH:
            if batch:
                yield batch; batch, words = [], 0
            yield [item]
            continue
        w = len(text.split())
        if batch and (words + w > DYN_MAX_WORDS or len(batch) >= DYN_MAX_LINES):
            yield batch; batch, words = [], 0
        batch.append(item); words += w
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
            if "context" in str(e).lower():
                break
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
        _log(f"      [~] Batch partial: {success} ok, {len(non_empty) - success} singles")
    except Exception as e:
        _log(f"      [!] Batch API Error → fallback: {e}")
    for i, text in enumerate(texts):
        if text and not is_valid_translation(texts[i], results[i]):
            results[i] = translate_one(text)
    return results


# ── IO ───────────────────────────────────────────────────────────────────
def _atomic_write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_output():
    _atomic_write(OUTPUT_FILE, output)

def save_tm():
    _atomic_write(TM_CACHE_FILE, tm_cache)

def save_all():
    save_output(); save_tm()


# ── load ─────────────────────────────────────────────────────────────────
def load_strings() -> list[tuple[int, str]]:
    """Load UI strings from XML. Returns [(id, english_text), ...]"""
    bark_ids = set()
    ui_strings: dict[int, str] = {}

    for xml_path in XML_PATHS:
        if not os.path.exists(xml_path):
            _log(f"[!] XML not found: {xml_path}")
            continue
        _log(f"[*] Parsing {xml_path}")
        tree = ET.parse(xml_path)
        for section in tree.getroot():
            name = section.attrib.get("name", "")
            is_bark = name == "BarkSubtitles"
            for child in section:
                lid = child.attrib.get("LineId")
                val = child.attrib.get("value", "")
                if lid:
                    lid_int = int(lid)
                    if is_bark:
                        bark_ids.add(lid_int)
                    elif val.strip():
                        ui_strings[lid_int] = val

    # Remove any bark IDs
    for bid in bark_ids:
        ui_strings.pop(bid, None)

    _log(f"[*] BarkSubtitles excluded: {len(bark_ids):,}")
    _log(f"[*] UI strings loaded: {len(ui_strings):,}")
    return sorted(ui_strings.items())


def load_state(all_strings: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Load existing progress. Returns items still needing translation."""
    global tm_cache, output

    if os.path.exists(TM_CACHE_FILE):
        try:
            with open(TM_CACHE_FILE, "r", encoding="utf-8") as f:
                tm_cache = json.load(f)
            if not isinstance(tm_cache, dict):
                tm_cache = {}
        except (json.JSONDecodeError, OSError):
            tm_cache = {}
    _log(f"[*] TM cache: {len(tm_cache):,} entries")

    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                output = json.load(f)
            if not isinstance(output, dict):
                output = {}
        except (json.JSONDecodeError, OSError):
            output = {}
    _log(f"[*] Already translated: {len(output):,} entries")

    # Filter out already-done
    done_keys = set(output.keys())
    remaining = [(lid, txt) for lid, txt in all_strings if str(lid) not in done_keys]
    return remaining


# ── preflight ────────────────────────────────────────────────────────────
def preflight():
    _log("[*] Preflight: pinging LM Studio…")
    try:
        resp = lm_client.chat.completions.create(
            model=LM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": "NAVIGATE"},
            ],
            temperature=0.0,
            max_tokens=32,
        )
        sample = clean_response(resp.choices[0].message.content)
        _log(f"[*] Preflight ok — 'NAVIGATE' -> {sample!r}")
    except Exception as e:
        sys.exit(
            f"FATAL: cannot reach LM Studio at {LM_URL}\n"
            f"  {type(e).__name__}: {e}\n"
            f"  Open LM Studio, load a model, start the local server, and retry."
        )


# ── main ─────────────────────────────────────────────────────────────────
def main():
    global lm_client, TEMPERATURE

    ap = argparse.ArgumentParser(description="WD2 UI Translator")
    ap.add_argument("--single", action="store_true", help="One-string-per-call")
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMP)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    TEMPERATURE = args.temperature

    lm_client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=600)

    _log("=" * 70)
    _log("Watch Dogs 2 — UI Translation to Hebrew")
    _log("=" * 70)
    _log(f"[*] Mode: {'single' if args.single else f'batch (≤{DYN_MAX_LINES} lines)'}")
    _log(f"[*] Workers: {args.workers}")
    _log(f"[*] Temperature: {TEMPERATURE}")
    _log(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]")

    preflight()

    all_strings = load_strings()
    remaining = load_state(all_strings)
    total = len(all_strings)
    already_done = total - len(remaining)

    _log(f"[*] Total UI: {total:,} | Done: {already_done:,} | Remaining: {len(remaining):,}")

    if not remaining:
        _log("[*] Done — nothing to translate.")
        return

    fixed = 0
    tm_hits = 0
    ft_hits = 0

    # ── Phase 2: TM + fast-track ──
    _log("[*] Phase 2: TM cache + fast-track...")
    slow: list[tuple[int, str]] = []

    for lid, src in remaining:
        if not needs_translation(src):
            # Keep original for non-translatable strings (numbers, names, codes)
            with state_lock:
                output[str(lid)] = src
                fixed += 1
                if fixed % SAVE_EVERY == 0:
                    save_all()
                    _log(f"  [~] Saved — {fixed:,} processed")
            continue

        cached = tm_cache.get(src)
        if cached and is_valid_translation(src, cached):
            with state_lock:
                output[str(lid)] = cached
                fixed += 1
                tm_hits += 1
                if fixed % SAVE_EVERY == 0:
                    save_all()
                    _log(f"  [~] Saved — {fixed:,} processed, ~{len(remaining) - fixed:,} left")
            continue

        ft = try_fast_track(src)
        if ft and is_valid_translation(src, ft):
            with state_lock:
                output[str(lid)] = ft
                tm_cache[src] = ft
                fixed += 1
                ft_hits += 1
                if fixed % SAVE_EVERY == 0:
                    save_all()
                    _log(f"  [~] Saved — {fixed:,} processed, ~{len(remaining) - fixed:,} left")
            continue

        slow.append((lid, src))

    _log(f"[*] Phase 2 done: {tm_hits:,} TM, {ft_hits:,} FT, {len(slow):,} need LM")
    save_all()

    if not slow:
        _log(f"[*] Done. Processed {fixed:,} strings (no LM needed).")
        return

    # ── Phase 3: LM translation ──
    def _text_for(item):
        return item[1]

    batches = [[it] for it in slow] if args.single \
              else list(build_dynamic_batches(slow, _text_for))

    _log(f"[*] Phase 3: {len(batches):,} batches, {args.workers} workers")
    lm_done = 0
    lm_skip = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        def _do_batch(texts):
            if len(texts) == 1:
                return [translate_one(texts[0])]
            return translate_batch(texts)

        future_map = {
            pool.submit(_do_batch, [it[1] for it in batch]): batch
            for batch in batches
        }

        for future in as_completed(future_map):
            batch = future_map[future]
            try:
                translations = future.result()
            except Exception as e:
                _log(f"  [!] Batch exception: {e}")
                translations = [it[1] for it in batch]

            with state_lock:
                for k, (lid, src) in enumerate(batch):
                    new_val = translations[k] if k < len(translations) else src
                    if is_valid_translation(src, new_val):
                        output[str(lid)] = new_val
                        tm_cache[src] = new_val
                        lm_done += 1
                        _log(f"  {lid}  {src[:35]!r} -> {new_val[:45]!r}")
                    else:
                        output[str(lid)] = src  # keep original
                        lm_skip += 1
                        _log(f"  {lid}  {src[:35]!r} -> [SKIP]")
                    fixed += 1
                    if fixed % SAVE_EVERY == 0:
                        save_all()
                        _log(f"  [~] Saved — {fixed:,} processed, ~{len(remaining) - fixed:,} left")

    save_all()
    _log(
        f"[*] Done. Processed {fixed:,} strings "
        f"({tm_hits:,} TM, {ft_hits:,} FT, {lm_done:,} LM, {lm_skip:,} skipped)."
    )
    _log(f"[*] Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
