"""
cp2077_markup_translate.py
==========================
Markup-aware translator for the <kiroshi> / <mothertongue> / <Rich> subtitle
and tooltip entries that translate_cleanup_all.py skips by design.

WHY A SEPARATE TOOL
In these entries the player-visible English is locked inside tag attributes
or text nodes, next to FOREIGN text that must survive byte-for-byte and a
leading CR2W control byte (0x01-0x05). Feeding the whole string to the LLM
corrupts the foreign text (proven: 49 <kiroshi> already damaged) or drops
the control byte (breaks the engine).

THE FIXED / TRANS SLOT MODEL
Every source string is parsed into an ordered list of slots:
    FIX  — control byte, tags, attribute syntax, foreign o/m values,
           {placeholders}, closers, whitespace — emitted verbatim
    TR   — the English text the player actually reads — sent to LM Studio
Only TR slots are translated; the output is the slots re-joined. Foreign
text and the control byte sit in FIX slots, so corruption is structurally
impossible. If a string contains a malformed / truncated tag, parse_slots
returns None and the entry is left completely untouched.

TRANSLATE / PRESERVE MAP (proven by cp2077_markup_analysis.py)
    <kiroshi l o t b a/>     translate t, b, a   | keep l, o
    <mothertongue l m b a/>  translate b, a      | keep l, m
    <Rich attr...>TEXT</>    translate TEXT      | keep tag, attrs, </>
    always FIX: leading 0x01-0x05 byte, {placeholders}, every other <tag>

SOURCE OF TRUTH
The text is read from, and written back to, femaleVariant. femaleVariant is
the complete text field; secondaryKey is only a reference label and is
TRUNCATED in the data (it loses the closing '>' and sometimes more), so it
is never used as the source.

USAGE
    python cp2077_markup_translate.py --dry-run     parse self-test, NO LM, NO write
    python cp2077_markup_translate.py --preview 20  translate 20 spread entries, PRINT only
    python cp2077_markup_translate.py --sample 20   translate 20 entries, WRITE (test batch)
    python cp2077_markup_translate.py               full markup run
Writes localization_translated.json (atomic). Does NOT pack/deploy.
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

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace", write_through=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8",
                                  errors="replace", write_through=True)

# ── paths ────────────────────────────────────────────────────────────────
SCRIPTS_DIR = r"C:\Users\Nehoray_Cohen\Projects\Game translator"
PROJECT     = os.path.join(SCRIPTS_DIR, "תרגום_משחקים")
RESOURCES   = os.path.join(PROJECT, "source", "resources")
TRANSLATED_FILE = os.path.join(RESOURCES, "localization_translated.json")
RESUME_FILE     = os.path.join(SCRIPTS_DIR, "markup_done.json")
TOUCHED_FILE    = os.path.join(SCRIPTS_DIR, "markup_touched_sections.txt")
MONITOR_LOG     = os.path.join(SCRIPTS_DIR, "fix_missing_translations.log")
RUNTIME_LOG     = os.path.join(SCRIPTS_DIR, "cp2077_markup_translate.runtime.log")

ONSCREENS_SECTIONS = ("onscreens/onscreens.json", "onscreens/onscreens_final.json")

# ── tuning (matches the proven pipeline) ─────────────────────────────────
PARALLEL_WORKERS = 4
DYN_MAX_PIECES   = 12
DYN_MAX_WORDS    = 100
SAVE_EVERY       = 50
LM_URL    = "http://127.0.0.1:1234/v1"
LM_MODEL  = "local-model"
TEMPERATURE = 0.3
MAX_TOKENS  = 512

SYSTEM_PROMPT = (
    "You are a professional game localizer for Cyberpunk 2077. Translate the "
    "user's English text to Hebrew with a gritty, high-tech, Night City tone.\n"
    "Output the Hebrew translation ONLY — no explanations, quotes, markdown, "
    "no 'Translation:' prefix, no <think> tags. One line per item.\n"
    "HARD RULES:\n"
    "  - USE ONLY HEBREW AND ENGLISH LETTERS. No Russian/Arabic/Cyrillic/Thai/"
    "Greek/CJK/Korean.\n"
    "  - NEVER use Hebrew Niqqud (vowel points).\n"
    "  - Do NOT add any tags, <>, {} or markup — the text given is already "
    "plain. Return plain Hebrew text only.\n"
    "  - Keep proper nouns (V, Johnny, Arasaka, Night City...) transliterated "
    "naturally.\n"
    "  - If an item is a pure code/number/symbol, return it unchanged.\n"
    "Glossary: Night City->נייט סיטי  Netrunner->נטראנר  Ripperdoc->ריפרדוק  "
    "Corpo->קורפו  Choom->צ'ום  Cyberware->סייברוור  Shard->שארד"
)
BATCH_HEADER = ("Translate each line below to Hebrew. Output exactly:\n"
                "1. [hebrew]\n2. [hebrew]\n\n")

# ── regexes ──────────────────────────────────────────────────────────────
# Escape-aware self-closing tags: an attribute value is "..." whose body is
# any run of (escaped \X) or (non-quote non-backslash) — this skips safely
# over nested <Rich> tags and \" sequences embedded inside a value.
KIRO_RE  = re.compile(r'<kiroshi(?:\s+\w+="(?:\\.|[^"\\])*")*\s*/?>')
MOTH_RE  = re.compile(r'<mothertongue(?:\s+\w+="(?:\\.|[^"\\])*")*\s*/?>')
ANYTAG_RE = re.compile(r'</>|</?\w[^<>]*?/?>')
PLACE_RE  = re.compile(r'\{[^{}]*\}')
ATTR_RE   = re.compile(r'(\w+)="((?:\\.|[^"\\])*)"')
HEB     = re.compile(r"[֐-׿]")
NIQQUD  = re.compile(r"[֑-ׇ]")
FOREIGN = re.compile(r"[Ѐ-ӿ؀-ۿ฀-๿ऀ-ॿ぀-ヿ一-鿿가-힣]")
LATIN   = re.compile(r"[A-Za-z]")
_THINK  = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_PREFIX = re.compile(r"^\s*(?:translation|תרגום|hebrew|output)\s*[:\-]\s*", re.IGNORECASE)

state_lock = threading.Lock()
lm_client: OpenAI | None = None
_log_lock = threading.Lock()


def log(msg: str) -> None:
    with _log_lock:
        print(msg, flush=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        for path, line in ((MONITOR_LOG, msg), (RUNTIME_LOG, f"[{ts}] {msg}")):
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass


# ── slot model ───────────────────────────────────────────────────────────
def is_translatable(text: str) -> bool:
    """A plain-text run is worth translating only if it carries real words."""
    return len(LATIN.findall(text)) >= 2


def _decompose_tag(tag: str, targets: tuple, slots: list) -> bool:
    """Split a <kiroshi>/<mothertongue> tag into FIX/TR slots — only the
    `targets` attribute values become TR. Returns False (→ skip the whole
    entry) if a target value embeds nested markup we won't risk."""
    last = 0
    for am in ATTR_RE.finditer(tag):
        if am.group(1) in targets:
            val = am.group(2)
            if "<" in val or "{" in val:
                return False
            slots.append(("FIX", tag[last:am.start(2)]))
            slots.append(("TR", val) if is_translatable(val) else ("FIX", val))
            last = am.end(2)
    slots.append(("FIX", tag[last:]))
    return True


def parse_slots(s: str):
    """Parse `s` into ordered (kind, text) slots — 'FIX' = verbatim, 'TR' =
    translatable English. Returns None when the string is damaged or too
    complex to touch safely: a corrupted byte, or a `<`/`{` that does not
    form a complete recognized tag/placeholder (truncated markup). The caller
    then leaves that entry completely alone."""
    if not s or "�" in s:
        return None
    slots: list = []
    i, n = 0, len(s)
    if 0x01 <= ord(s[0]) <= 0x05:
        slots.append(("FIX", s[0]))
        i = 1
    while i < n:
        ch = s[i]
        if ch == "<":
            m = KIRO_RE.match(s, i) or MOTH_RE.match(s, i)
            if m:
                targets = (("t", "b", "a") if m.group(0).startswith("<kiroshi")
                           else ("b", "a"))
                if not _decompose_tag(m.group(0), targets, slots):
                    return None
                i = m.end()
                continue
            m = ANYTAG_RE.match(s, i)
            if m:
                slots.append(("FIX", m.group(0)))
                i = m.end()
                continue
            return None                       # malformed / truncated tag
        if ch == "{":
            m = PLACE_RE.match(s, i)
            if m:
                slots.append(("FIX", m.group(0)))
                i = m.end()
                continue
            return None                       # malformed placeholder
        j = i
        while j < n and s[j] not in "<{":
            j += 1
        chunk = s[i:j]
        slots.append(("TR", chunk) if is_translatable(chunk) else ("FIX", chunk))
        i = j
    return slots


def reassemble(slots: list) -> str:
    return "".join(t for _, t in slots)


# ── translation helpers ──────────────────────────────────────────────────
def clean_response(raw: str) -> str:
    if not isinstance(raw, str):
        return ""
    s = _THINK.sub("", raw).strip()
    s = re.sub(r"^\*+\s*(.+?)\s*\*+$", r"\1", s).strip()
    s = _PREFIX.sub("", s).strip()
    return NIQQUD.sub("", s)


def valid_piece(src: str, he: str) -> bool:
    """A translated TR piece must be Hebrew, contamination-free, and must not
    have invented any markup (tags live in FIX slots only)."""
    if not he or not HEB.search(he):
        return False
    if FOREIGN.search(he):
        return False
    if any(c in he for c in "<>{}"):
        return False
    return True


def translate_one(text: str) -> str:
    try:
        resp = lm_client.chat.completions.create(
            model=LM_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": text}],
            temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
        out = clean_response(resp.choices[0].message.content or "")
        m = re.match(r"^\s*1\.\s*(.+)", out)
        return m.group(1).strip() if m else out
    except Exception as e:
        log(f"      [!] single API error: {e}")
        return ""


def translate_pieces(texts: list[str]) -> list[str]:
    """Translate a batch of plain-text pieces. Falls back to single mode for
    any piece the batch response didn't cover cleanly."""
    if not texts:
        return []
    user = BATCH_HEADER + "".join(f"{i+1}. {t}\n" for i, t in enumerate(texts))
    results = [""] * len(texts)
    try:
        resp = lm_client.chat.completions.create(
            model=LM_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user}],
            temperature=TEMPERATURE, max_tokens=MAX_TOKENS)
        raw = resp.choices[0].message.content or ""
        for line in raw.splitlines():
            m = re.match(r"^\s*(\d+)\.\s*(.+)", line.strip())
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(texts):
                    results[idx] = clean_response(m.group(2))
    except Exception as e:
        log(f"      [!] batch API error → singles: {e}")
    for i, t in enumerate(texts):
        if not valid_piece(t, results[i]):
            results[i] = translate_one(t)
    return results


def make_batches(items, text_of):
    batch, words = [], 0
    for it in items:
        w = len(text_of(it).split())
        if batch and (words + w > DYN_MAX_WORDS or len(batch) >= DYN_MAX_PIECES):
            yield batch
            batch, words = [], 0
        batch.append(it)
        words += w
    if batch:
        yield batch


def atomic_write(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ── scan ─────────────────────────────────────────────────────────────────
def scan(translated: dict, done: set) -> tuple[list, dict]:
    """Find every entry whose femaleVariant carries markup and still has an
    untranslated TR piece. femaleVariant is both the source and the write
    target — for an untranslated entry it holds the complete English markup."""
    work: list[dict] = []
    stats = dict(markup=0, done=0, damaged=0, no_tr=0)
    for sec, rows in translated.items():
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            fv = e.get("femaleVariant") or ""
            if not any(t in fv for t in ("<kiroshi", "<mothertongue", "<Rich")):
                continue
            stats["markup"] += 1
            pk = str(e.get("primaryKey"))
            if (sec, pk) in done:
                stats["done"] += 1
                continue
            slots = parse_slots(fv)
            if slots is None:
                stats["damaged"] += 1
                continue
            tr = [t for k, t in slots if k == "TR"]
            if not tr:
                stats["no_tr"] += 1
                continue
            if all(HEB.search(t) for t in tr):
                stats["done"] += 1
                continue
            work.append({"section": sec, "pk": pk, "src": fv, "slots": slots})
    return work, stats


def main() -> int:
    global lm_client
    ap = argparse.ArgumentParser(description="Markup-aware CP2077 translator.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse self-test only — no LM, no write.")
    ap.add_argument("--sample", type=int, default=0,
                    help="Translate only the first N entries (test batch, writes).")
    ap.add_argument("--preview", type=int, default=0,
                    help="Translate N entries spread across the queue and PRINT "
                         "before/after — no write.")
    args = ap.parse_args()

    with open(TRANSLATED_FILE, "r", encoding="utf-8") as f:
        translated = json.load(f)

    done: set = set()
    if os.path.exists(RESUME_FILE):
        try:
            with open(RESUME_FILE, "r", encoding="utf-8") as f:
                done = {tuple(x) for x in json.load(f)}
        except (OSError, json.JSONDecodeError):
            done = set()

    log("[*] Using LM Studio (Gemma-2-27b)")
    log("[*] Mode: markup-aware (FIXED/TRANS slot model)")
    log(f"[started: {time.strftime('%Y-%m-%d %H:%M:%S')}]")

    work, stats = scan(translated, done)
    log(f"[*] markup entries: {stats['markup']:,}  |  to translate: {len(work):,}  |  "
        f"already done: {stats['done']:,}  |  no translatable text: {stats['no_tr']:,}  |  "
        f"damaged/truncated (left untouched): {stats['damaged']:,}")
    log(f"[*] Global queue: {len(work):,} pending items (cleanup mode)")

    # ── dry-run: prove the parser is lossless on everything it accepts ──
    if args.dry_run:
        bad = 0
        for w in work:
            if reassemble(w["slots"]) != w["src"]:
                bad += 1
                if bad <= 5:
                    log(f"  [!] LOSSY: {w['src'][:90]!r}")
        log(f"[*] dry-run: {len(work):,} accepted entries  |  lossy re-assembly: {bad}")
        log("[*] dry-run OK — parser is lossless." if bad == 0
            else "[!] dry-run FAILED.")
        return 0 if bad == 0 else 1

    limit = args.preview or args.sample
    if limit:
        step = max(1, len(work) // limit)
        work = work[::step][:limit]
        log(f"[*] {'preview' if args.preview else 'sample'}: "
            f"{len(work):,} entries sampled across the queue")
    if not work:
        log("[*] Nothing to do.")
        return 0

    lm_client = OpenAI(base_url=LM_URL, api_key="lm-studio", timeout=600)

    pieces: list[dict] = []
    pending: dict[int, int] = {}          # w_idx -> TR pieces still outstanding
    for w_idx, w in enumerate(work):
        w["_en"] = " / ".join(t for k, t in w["slots"] if k == "TR")
        for s_idx, (kind, text) in enumerate(w["slots"]):
            if kind == "TR":
                pieces.append({"w": w_idx, "s": s_idx, "text": text})
                pending[w_idx] = pending.get(w_idx, 0) + 1
    log(f"[*] Phase 3: {len(pieces):,} translatable pieces from "
        f"{len(work):,} entries, {PARALLEL_WORKERS} workers")

    batches = list(make_batches(pieces, lambda p: p["text"]))

    def run_batch(batch):
        return batch, translate_pieces([p["text"] for p in batch])

    fixed = skipped = 0
    touched: set = set()

    def checkpoint() -> None:
        atomic_write(TRANSLATED_FILE, translated)
        atomic_write(RESUME_FILE, [list(t) for t in done])
        if touched:
            with open(TOUCHED_FILE, "w", encoding="utf-8") as f:
                f.write(",".join(sorted(touched)))

    def finalize(w_idx: int) -> None:
        """Reassemble one fully-translated entry, write it back into
        `translated`, log a monitor-countable progress line, and checkpoint
        every SAVE_EVERY entries. Called the moment an entry's last TR piece
        lands — this is what makes the run observable and crash-resumable."""
        nonlocal fixed, skipped
        w   = work[w_idx]
        out = reassemble(w["slots"])
        src = w["src"]
        ok  = (out.count("<") == src.count("<")
               and out.count("{") == src.count("{")
               and (not src or out[0] == src[0]))
        short = w["section"].split("/")[-1][:24]
        if args.preview:
            log(f"  [{'SKIP' if (w.get('_skip') or not ok) else 'OK'}] "
                f"{short}:{w['pk']}")
            log(f"        EN: {src[:150]}")
            log(f"        HE: {out[:150]}")
            return
        if w.get("_skip") or not ok:
            skipped += 1
            log(f"  [SKIP] {short}:{w['pk']}")
            return
        for section in ({w["section"]} | (set(ONSCREENS_SECTIONS)
                                          if w["section"] in ONSCREENS_SECTIONS
                                          else set())):
            idx = {str(e.get("primaryKey")): e
                   for e in translated.get(section, []) if isinstance(e, dict)}
            if w["pk"] in idx:
                idx[w["pk"]]["femaleVariant"] = out
        fixed += 1
        done.add((w["section"], w["pk"]))
        if w["section"].startswith("subtitles/"):
            touched.add(w["section"])
        # one ' -> ' arrow line per entry — progress_monitor counts these;
        # show the translatable text only (English -> Hebrew); the verbatim
        # tag prefix is identical on both sides and uninformative in the feed.
        tr_he = " / ".join(t for k, t in w["slots"] if k == "TR")
        log(f"  [OK] {short}:{w['pk']}  '{w['_en'][:60]}' -> '{tr_he[:60]}'")
        if fixed % SAVE_EVERY == 0:
            checkpoint()
            log(f"  [~] Saved — {fixed:,} fixed, "
                f"~{len(work) - fixed - skipped:,} remaining")

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
        futures = [pool.submit(run_batch, b) for b in batches]
        for fut in as_completed(futures):
            batch, hebrew = fut.result()
            with state_lock:
                for p, he in zip(batch, hebrew):
                    w = work[p["w"]]
                    if valid_piece(p["text"], he):
                        w["slots"][p["s"]] = ("TR", he)
                    else:
                        w["slots"][p["s"]] = ("TR", p["text"])   # leave English
                        w["_skip"] = True
                    pending[p["w"]] -= 1
                    if pending[p["w"]] == 0:        # entry complete -> write it
                        finalize(p["w"])

    if args.preview:
        log(f"[*] preview done — {len(work):,} entries shown, nothing written.")
        return 0

    checkpoint()
    log(f"[*] Done. Fixed {fixed:,} markup entries, {skipped:,} skipped "
        f"(validation failed — left in English).")
    log(f"[*] touched {len(touched):,} subtitle sections -> "
        f"{os.path.basename(TOUCHED_FILE)}")
    log("[*] Next: rebuild_subtitles_and_pack.py --sections-file "
        "markup_touched_sections.txt  +  rebuild_onscreens_and_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
