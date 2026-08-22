"""Anno 1800 Hebrew Translator
Translates Anno 1800's GUID-keyed UI/dialogue text to Hebrew via LM Studio
(gemma-4-31b-it). Source = the English text table (the hijacked English slot,
PIPELINE.md §0). Output = hebrew.json {guid: hebrew} in LOGICAL order — the
visual()-vs-logical decision is made later at BUILD time (build_mod.py --visual),
gated on the in-game proof, NOT here.

Usage:
    python anno1800_translate.py                # full run
    python anno1800_translate.py --dry-run      # scan only, no requests
    python anno1800_translate.py --status       # show checkpoint progress
"""
import json, os, re, sys, time, threading, urllib.request, urllib.error
import xml.etree.ElementTree as ET

# Force UTF-8 stdout/stderr — when launched by the watchdog on Windows, stdout
# defaults to cp1255 and any print with a non-cp1255 char ('→', '…') raises
# UnicodeEncodeError and KILLS the process (the documented SM2 silent-freeze bug).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE   = os.path.dirname(os.path.abspath(__file__))
# Source: the extracted English text table. games/anno1800/work -> ../extract/...
SPINE  = os.path.join(HERE, "..", "extract", "data", "config", "gui", "texts_english.xml")
OUT    = os.path.join(HERE, "hebrew.json")          # {guid: hebrew} — THE resumable state
SKIP_F = os.path.join(HERE, "anno1800_translate_skip.json")
STRK_F = os.path.join(HERE, "anno1800_translate_strikes.json")

LM_URL = os.environ.get("ANNO_LM_URL", "http://localhost:1234/v1/chat/completions")
MODEL  = os.environ.get("ANNO_LM_MODEL", "gemma-4-31b-it@q2_k_xl")
# gemma-4-31b-it@q2_k_xl (14.08 GB) fits ~16 GB VRAM with near-zero RAM-spill.
# It MUST be served serial (LM Studio --parallel 1) — concurrent requests on a
# RAM-spilled/slow model split the fixed throughput and time out (the CP2077 +
# SM2 lesson). So WORKERS=1 (serial client), small batches so each request
# finishes well inside the timeout, generous TIMEOUT for the longest entries.
TIMEOUT      = 900    # ceiling — a single long lore/quest blurb can generate hundreds of tokens
WORKERS      = 1      # serial — matches LM Studio --parallel 1
# Anno strings are mostly short UI labels with a thin tail of long descriptions/
# quests. Pack by ESTIMATED output tokens (not a fixed count): short labels batch
# together; a long description lands in its own batch. max_tokens is then sized
# per batch from the estimate.
TOKEN_BUDGET = 340
MAX_TOK_CAP  = 1200
MIN_BATCH_TOK = 24    # floor per entry estimate

def est_out_tokens(ev):
    """Rough estimate of the Hebrew output token count for an English string.
    Hebrew output length ≈ the English source; ~3 chars/token is a safe lower
    bound, so this slightly OVER-estimates (good — it sizes max_tokens up)."""
    return max(MIN_BATCH_TOK, len(ev) // 3)

# ── System prompt ─────────────────────────────────────────────────────────────
# Kept deliberately SHORT (~400 tok) — it is re-prefilled on EVERY batch and
# prefill dominates the cost on a slow model (the SM2 lesson). All hard rules
# survive; only verbosity is cut.
SYSTEM = """You are an expert Hebrew localizer for Anno 1800, a Belle-Époque (19th-century industrial era) city-building strategy game. Translate English game strings into natural, clear Israeli Hebrew with a period-appropriate, sophisticated tone (UI labels, tooltips, quest/dialogue text).

HARD RULES — a violation means the line is REJECTED:
1. Output ONLY Hebrew + Latin letters. NO Arabic/Cyrillic/Greek/Thai/Devanagari/CJK/Hangul or any other script. NEVER use niqqud (vowel marks).
2. Copy these EXACTLY, unchanged, at the SAME position: [GuidName]-style reference tokens like [SourcePlayer] [TargetPlayer] [Island] [Amount]; any [BRACKETED] placeholder; formatting tags <... > and </...>; %d %u %s %i %f %% format specs (never collapse %% to %); HTML entities &lt; &gt; &nbsp; &amp;; literal \\n newlines.
3. Keep building, good, ware, character, faction, and place proper-NAMES as written (Latin) unless they are clearly a translatable common noun. When in doubt, keep the established name. Examples to keep Latin: Anno, Ubisoft, city/character names.
4. Do NOT add accented Latin letters (ł, ć, ś, ó, é, à, ü, ä) that are not in the English source.
5. If a string is only tags/placeholders/numbers with no real words, return it unchanged.

OUTPUT only the numbered lines: [1] [2] [3]… each followed by its Hebrew. No labels, no notes, no explanations."""

# ── Build queue ───────────────────────────────────────────────────────────────
def _load_skip():
    try:
        return set(str(k) for k in json.load(open(SKIP_F, encoding="utf-8")))
    except Exception:
        return set()

def build_queue():
    """Parse the English spine -> list of (guid, en). Excludes already-done
    (hebrew.json) and parked (skip-list) keys. Ordered SHORT-real-text first
    (the fast bulk leads; long blurbs trail) — the WD2/SM2 queue ordering."""
    done = set()
    if os.path.exists(OUT):
        try:
            done = set(json.load(open(OUT, encoding="utf-8")).keys())
        except Exception:
            done = set()
    skip = _load_skip()

    recs = []
    tree = ET.parse(SPINE)
    texts = tree.getroot().find("Texts")
    if texts is None:
        return []
    for el in texts.findall("Text"):
        guid = (el.findtext("GUID") or "").strip()
        ev   = (el.findtext("Text") or "").strip()
        if not guid or not ev:
            continue
        if guid in done or guid in skip:
            continue
        recs.append((guid, ev))

    # short-real-text first: real-word lines (the fast bulk), shortest first;
    # then the long / placeholder-only tail.
    def _has_real_word(ev):
        core = re.sub(r'\[[^\]]*\]|\{[^}]+\}|<[^>]+>|%[%a-zA-Z]|&[a-zA-Z#0-9]+;', '', ev)
        return bool(re.search(r'[A-Za-z]{2,}', core))
    recs.sort(key=lambda x: (not _has_real_word(x[1]), len(x[1])))
    return recs

def total_records():
    """Full translatable count from the spine (for --status / progress total)."""
    try:
        tree = ET.parse(SPINE)
        texts = tree.getroot().find("Texts")
        n = 0
        for el in texts.findall("Text"):
            if (el.findtext("GUID") or "").strip() and (el.findtext("Text") or "").strip():
                n += 1
        return n
    except Exception:
        return 28165

# ── LM call ───────────────────────────────────────────────────────────────────
def lm_call(messages, max_tok=320):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tok,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(LM_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()

# ── Parse batch response ──────────────────────────────────────────────────────
NUM_RE = re.compile(r'^\[(\d+)\]\*?\s*(.*)', re.DOTALL)

def parse_response(text, n):
    lines = text.splitlines()
    out = {}
    cur_idx = None
    cur_parts = []

    def flush():
        if cur_idx is not None and cur_parts:
            out[cur_idx] = " ".join(" ".join(cur_parts).split())

    for line in lines:
        m = NUM_RE.match(line)
        if m:
            flush()
            cur_idx = int(m.group(1))
            cur_parts = [m.group(2).strip()]
        elif cur_idx is not None:
            cur_parts.append(line.strip())
    flush()

    if n == 1 and not out:
        clean = text.strip()
        # Strip common conversational prefixes a chatty model adds
        clean = re.sub(r'^(here is the translation:|translation:|תרגום:)\s*', '',
                       clean, flags=re.IGNORECASE).strip()
        out[1] = clean

    return out

# ── Validate translated value ─────────────────────────────────────────────────
BAD_SCRIPTS = re.compile(
    r'[؀-ۿ'    # Arabic
    r'Ѐ-ӿ'     # Cyrillic
    r'Ͱ-Ͽ'     # Greek
    r'฀-๿'     # Thai
    r'ऀ-ॿ'     # Devanagari
    r'一-鿿'     # CJK
    r'가-힯'     # Hangul
    r'֐-ׇ]'    # Hebrew niqqud (0591-05C7 are niqqud; 05D0-05EA are letters)
)
NIQQUD = re.compile(r'[֑-ׇ]')
# placeholder / token multiset — every one in the source must survive verbatim.
TOK_BRACKET = re.compile(r'\[[^\]]+\]')          # [SourcePlayer], [Island], [BTN_X]
TAG_RE      = re.compile(r'</?[^>]+>')           # <font>, </font>, <b> …
PCT_RE      = re.compile(r'%[%a-zA-Z]')          # %d %s %% …
ENT_RE      = re.compile(r'&[a-zA-Z#0-9]+;')     # &lt; &nbsp; &amp; …
REFUSAL = re.compile(
    r'\b(i cannot|i can\'?t|as an ai|i\'?m sorry|sorry,? i|here is the|here\'?s the|'
    r'i am unable|cannot translate|i will not)\b', re.IGNORECASE)

def _placeholders(s):
    out = []
    out += TOK_BRACKET.findall(s)
    out += TAG_RE.findall(s)
    out += PCT_RE.findall(s)
    out += ENT_RE.findall(s)
    return sorted(out)

def validate(orig_en, translated):
    if not translated or not translated.strip():
        return False, "empty"
    # Model refusal / "here is the translation" leak
    if REFUSAL.search(translated):
        return False, "refusal"
    # Must have at least one Hebrew letter ...
    if not re.search(r'[א-ת]', translated):
        # ... UNLESS the source is essentially a NAME / code / acronym that
        # legitimately stays Latin (proper-noun ≤4 words, or no real lowercase
        # word) — rejecting those churns proper nouns forever (the SM2 lesson).
        text_only = re.sub(r'\[[^\]]+\]|\{[^}]+\}|%[\w%]+|&[a-zA-Z#0-9]+;|<[^>]+>',
                           '', orig_en).strip()
        if text_only:
            words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", text_only)
            is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
            no_real_word = not re.search(r'[a-z]{2,}', text_only)
            if not (is_namey or no_real_word):
                return False, "no Hebrew"
    # No bad scripts
    m = BAD_SCRIPTS.search(translated)
    if m:
        return False, f"bad script char U+{ord(m.group(0)):04X}"
    # No niqqud
    if NIQQUD.search(translated):
        return False, "niqqud"
    # No accented Latin chars unless in source (Polish/French hallucination guard)
    for c in re.findall(r'[À-ɏ]', translated):
        if c not in orig_en:
            return False, f"foreign accented char '{c}'"
    # Placeholder / tag / spec multiset must be IDENTICAL to the source
    if _placeholders(orig_en) != _placeholders(translated):
        return False, "placeholder mismatch"
    return True, ""

# ── Translate one batch ───────────────────────────────────────────────────────
def translate_batch(batch):
    """batch: list of (guid, en_val)"""
    lines = [f"[{i}] {ev}" for i, (g, ev) in enumerate(batch, 1)]
    user_msg = (
        "Translate each entry to Hebrew. Return only [N] Hebrew text.\n"
        "Copy every [Token], <tag>, %spec and &entity; exactly as written.\n\n"
        + "\n".join(lines)
    )
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": user_msg},
    ]
    # size the token cap from the batch's estimated output so a long blurb never
    # truncates inside a batch.
    est = sum(est_out_tokens(ev) for _, ev in batch)
    max_tok = min(MAX_TOK_CAP, int(est * 1.7) + 80)
    try:
        raw = lm_call(messages, max_tok)
    except urllib.error.URLError as e:
        return None, f"network: {e}"
    except Exception as e:
        return None, f"error: {e}"

    parsed = parse_response(raw, len(batch))
    results = {}
    for i, (g, ev) in enumerate(batch, 1):
        translated = parsed.get(i, "").strip()
        if not translated:
            continue
        ok, reason = validate(ev, translated)
        if not ok:
            print(f"    [SKIP] {g}: {reason} -> '{translated[:60]}'", flush=True)
            continue
        results[g] = translated
    return results, None

# ── Checkpoint helpers ─────────────────────────────────────────────────────────
_lock = threading.Lock()
_done = {}

def load_output():
    global _done
    if os.path.exists(OUT):
        try:
            _done = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            _done = {}

def _atomic_dump(obj, path):
    """Write to a temp file then os.replace — so a kill mid-write (the watchdog
    may restart us) never leaves a truncated/corrupt JSON, and any concurrent
    reader (the pusher / QA watchdog) always sees a complete file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def flush_output():
    with _lock:
        _atomic_dump(_done, OUT)

def record(results):
    with _lock:
        _done.update(results)

def park_failures(keys):
    """Persistent 3-strike park: a key that fails ALL attempts in a pass gets a
    strike; at 3 it joins anno1800_translate_skip.json so the queue stops looping
    on it forever (un-translatable names/codes, quant hallucinations) and the
    build's English fallback covers it. Returns the keys parked this call."""
    if not keys:
        return []
    try:
        strikes = json.load(open(STRK_F, encoding="utf-8")) if os.path.exists(STRK_F) else {}
    except Exception:
        strikes = {}
    skip = _load_skip()
    parked = []
    for k in keys:
        if k in skip:
            continue
        strikes[k] = strikes.get(k, 0) + 1
        if strikes[k] >= 3:
            skip.add(k); parked.append(k); strikes.pop(k, None)
    _atomic_dump(strikes, STRK_F)
    if parked:
        _atomic_dump(sorted(skip), SKIP_F)
    return parked

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    dry = "--dry-run" in sys.argv
    status_only = "--status" in sys.argv

    load_output()
    done_keys = set(_done)

    total = total_records()
    print(f"Total translatable: {total}")
    print(f"Already done:       {len(done_keys)}")

    if status_only:
        print(f"Remaining (est):    {max(0, total - len(done_keys))}")
        return

    queue = build_queue()       # excludes done + skip
    print(f"Remaining:          {len(queue)}")

    if dry:
        print("\n[dry-run] First 3 entries:")
        for g, ev in queue[:3]:
            print(f"  [{g}]: {ev[:80]}")
        return

    if not queue:
        print("All done!")
        return

    # Build batches packed by estimated output tokens. A short label batches with
    # neighbors; a long blurb lands in its own batch.
    batches = []
    cur, cur_est = [], 0
    for x in queue:
        e = est_out_tokens(x[1])
        if cur and cur_est + e > TOKEN_BUDGET:      # would overflow → close batch
            batches.append(cur); cur, cur_est = [], 0
        cur.append(x); cur_est += e
        if cur_est >= TOKEN_BUDGET:                  # full (or one huge entry) → close
            batches.append(cur); cur, cur_est = [], 0
    if cur:
        batches.append(cur)

    print(f"\nBatches: {len(batches)} (packed by ~{TOKEN_BUDGET} tok)  "
          f"Workers: {WORKERS}", flush=True)
    print("=" * 60)

    done_count = 0
    remaining = len(queue)

    # Serial loop (matches LM --parallel 1). Flush after EVERY sub-step so the
    # done-count advances promptly — the watchdog's hang detector keys off it.
    def _commit(res):
        if not res:
            return 0
        record(res)
        flush_output()
        return len(res)

    for bi, b in enumerate(batches):
        results, _err = translate_batch(b)
        results = results or {}
        n = _commit(results)
        # one retry for whatever's missing (timeout / truncation / skip)
        missing = [x for x in b if x[0] not in results]
        if missing:
            time.sleep(1)
            r2, _ = translate_batch(missing)
            if r2:
                results.update(r2); n += _commit(r2)
        # singleton fallback for stubborn long entries — alone they get the full budget
        for x in [x for x in b if x[0] not in results]:
            r3, _ = translate_batch([x])
            if r3:
                results.update(r3); n += _commit(r3)
        # strike + park anything that failed every attempt this pass so the queue
        # can NEVER loop on an un-translatable entry forever (the universal lesson).
        parked = park_failures([x[0] for x in b if x[0] not in results])
        if parked:
            print(f"  [PARK] {len(parked)} key(s) hit 3 strikes -> skip-list: "
                  f"{parked[:5]}", flush=True)
        done_count += n
        live = len(_done)
        pct = live / max(1, total) * 100
        if n:
            print(f"  +{n} ({done_count}/{remaining} this run) [{pct:.1f}% total]  "
                  f"done={live}", flush=True)
        else:
            print(f"  [skip] batch {bi} -> 0 results (stays queued)", flush=True)

    flush_output()
    print(f"\nDone. hebrew.json: {len(_done)} / {total}")
    print("Next: run `python build_mod.py` (then the proof gate / publish).")


if __name__ == "__main__":
    main()
