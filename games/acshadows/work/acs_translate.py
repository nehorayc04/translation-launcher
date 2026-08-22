"""acs_translate.py — Assassin's Creed Shadows Hebrew translator (TEMPLATE).

>>> COPIED VERBATIM FROM games/spiderman2/work/sm2_translate.py — the LM Studio
    translation engine (serial gemma-4-31b-it, token-budget batching, atomic
    flush, validate()/skip-list resilience) carries over UNCHANGED per the
    Universal Game-Translation Playbook (CLAUDE.md §3). ADAPT before running:
      • INPUT  — read the extracted Oasis EN source + Arabic skeleton produced
        by the forge-extract step (see ../PIPELINE.md), NOT sm2 *_he.json.
      • OUTPUT — write the Hebrew Oasis strings the repack step consumes.
      • TAGS   — AC Shadows uses Ubisoft Oasis placeholders/markup, not SM2's
        <ts>/<span>; update validate()/the system prompt accordingly.
    Until the forge extract/repack path is proven (the GO/NO-GO linchpin),
    this is groundwork, not a runnable pipeline. <<<

Usage (after adaptation):
    python acs_translate.py                # full run
    python acs_translate.py --dry-run      # scan only, no requests
    python acs_translate.py --status       # show checkpoint progress
"""
import json, os, re, sys, time, threading, urllib.request, urllib.error, glob
from concurrent.futures import ThreadPoolExecutor, as_completed

# Force UTF-8 stdout/stderr — when launched by the watchdog on Windows, stdout
# defaults to cp1255 and any print with a non-cp1255 char ('→', '…') raises
# UnicodeEncodeError and KILLS the process (this silently froze the whole run).
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE    = os.path.dirname(os.path.abspath(__file__))
CHKPT   = os.path.join(HERE, "sm2_translate_checkpoint.json")
OUT_S   = os.path.join(HERE, "subtitles_he.json")   # entries with <ts>
OUT_D   = os.path.join(HERE, "dialogue_he.json")    # entries without <ts>

LM_URL  = "http://localhost:1234/v1/chat/completions"
MODEL   = "gemma-4-31b-it@q2_k_xl"   # UD-Q2_K_XL 14.08GB — fits ~16GB VRAM, zero RAM-spill, maximum speed
# gemma-4-31b-it (19.9 GB) spills to RAM on the 16 GB RX 9070 → ~2-2.5 tok/s.
# It MUST be served serial (LM Studio --parallel 1) — concurrent requests on a
# RAM-spilled model just split the fixed throughput and time out (the lesson
# from the CP2077 audit). So WORKERS=1 (serial client) to match, smaller BATCH
# so each request finishes well inside the timeout, and a generous TIMEOUT to
# absorb variance on the longest entries.
TIMEOUT      = 900    # ceiling — a single huge multi-<ts> scene can generate ~600-800 tok
WORKERS      = 1      # serial — matches LM Studio --parallel 1
# Dialogue/UI lines are short → fixed batch of 10 amortizes the system-prompt prefill.
BATCH_DIAL   = 10
MAX_TOK_DIAL = 320
# A subtitle entry's size varies wildly — ONE key can be a whole scene with many
# <ts> segments. So subtitles are packed by ESTIMATED output tokens (not by count):
# small lines batch together; a huge scene lands in its own batch. max_tokens is
# then sized per batch from that estimate (measured gen ~1.5 tok/s).
SUB_TOKEN_BUDGET = 340
SUB_MAX_TOK_CAP  = 1200

TS_RE   = re.compile(r'<ts="[^"]*">')

def est_out_tokens(ev):
    """Rough estimate of the Hebrew output token count for an English string.
    Hebrew output length ≈ the English source; ~3 chars/token is a safe lower
    bound, so this slightly OVER-estimates (good — it sizes max_tokens up)."""
    return max(24, len(ev) // 3)

# ── System prompt ─────────────────────────────────────────────────────────────
# Kept deliberately SHORT — it is re-prefilled on every batch; ~1000 tokens of
# system prompt was the dominant cost on the RAM-spilled model (measured 1419
# prompt_tokens / 180 s). All the hard rules survive; only verbosity is cut.
SYSTEM = """You are an expert Hebrew localizer for Marvel's Spider-Man 2. Translate English game strings into natural, spoken Israeli Hebrew (energetic action-game tone, not literary).

HARD RULES — a violation means the line is REJECTED:
1. Output ONLY Hebrew + Latin letters. NO Arabic/Cyrillic/Greek/Thai/Devanagari/CJK/Hangul or any other script. NEVER use niqqud (vowel marks).
2. Copy these EXACTLY, unchanged, at the SAME position: <ts="N;N"> timing tags; [UPPER_TOKEN] and {VALUE} placeholders; %d %u %s %i %f %% format specs (never collapse %% to %); &rlm; &gt; &nbsp; <br> <span> </span>.
3. Keep names in English exactly as written — characters: Spider-Man, Miles, Peter, MJ, Mary Jane, Harry, Norman, Venom, Anti-Venom, Carnage, Kraven, Sandman, Lizard, Electro, Mister Negative, Martin Li, Wraith, Yuri, Rio, Jeff, Symbiote, Scream, Taskmaster, Tombstone, Vulture; places/brands: New York, Brooklyn, Queens, Manhattan, Harlem, F.E.A.S.T., Oscorp, Daily Bugle, ESU, NYPD, S.H.I.E.L.D.
4. [bracketed sound cues]: translate the word inside, keep the brackets — [laughing]→[צוחק], [gasping]→[נאנח], [grunting]→[נחירה], [groaning]→[גניחה], [sighing]→[אנחה], [coughing]→[שיעול], [screaming]→[צרחה], [crying]→[בכי], [panting]→[התנשפות]. Short Hebrew word for any other.
5. If the entry is marked * it MUST end with &rlm;.
6. If a string has only tags/placeholders and no real words, return it unchanged.
7. GENDER: Character bios (keys ending in _MILES or _PETER) are written by Miles Morales and Peter Parker, who are male. All first-person verbs/adjectives/pronouns in these bios MUST be translated in the masculine in Hebrew (e.g. "אני זוכר", "אני מניח", "שמח", "צריך", "יכול", "יודע"). Other dialogue defaults to masculine in Hebrew unless the speaker is clearly female (MJ, Rio, Yuri/Wraith, Hailey, Felicia/Black Cat, Danika, Aunt May).
8. NO accented Latin letters (like ł, ć, ś, ó, é, à, ü, ä) in the Hebrew translation unless they exist in the English source.

OUTPUT only the numbered lines: [1] [2] [3]… each followed by its Hebrew. No labels, no notes, no explanations."""

# ── Build queue ───────────────────────────────────────────────────────────────
def build_queue():
    ar = json.load(open(os.path.join(HERE, "arabic.json"), encoding="utf-8"))
    en = json.load(open(os.path.join(HERE, "english.json"), encoding="utf-8"))

    he = {}
    for f in sorted(glob.glob(os.path.join(HERE, "*_he.json"))):
        if os.path.basename(f) in ("subtitles_he.json", "dialogue_he.json"):
            continue  # output files, skip
        d = json.load(open(f, encoding="utf-8"))
        he.update(d)

    # Also load output files if partially done
    for out in (OUT_S, OUT_D):
        if os.path.exists(out):
            d = json.load(open(out, encoding="utf-8"))
            he.update(d)

    # Parked keys (the QA watchdog gives up after 3 strikes) — never re-queue;
    # the build's Arabic/English fallback covers them.
    skip = set()
    sp = os.path.join(HERE, "sm2_translate_skip.json")
    if os.path.exists(sp):
        try:
            skip = set(json.load(open(sp, encoding="utf-8")))
        except Exception:
            skip = set()

    untrans = []
    for k, av in ar.items():
        if k in he or k in skip:
            continue
        if k.startswith("CREDITS_"):
            continue
        ev = en.get(k, "").strip()
        if not ev:
            continue
        # Skip SFX-only entries (just a sound cue, no real text)
        text_only = TS_RE.sub("", ev).strip()
        if re.match(r'^\[[^\]]+\]$', text_only):
            continue
        av_strip = av.strip() if av else ""
        has_ts = bool(TS_RE.search(ev))
        ends_rlm = av_strip.endswith("&rlm;")
        untrans.append((k, ev, has_ts, ends_rlm))

    return untrans

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
        # Remove common conversational prefixes
        clean = re.sub(r'^(here is the translation:|translation:|עבור השורה:|תרגום:)\s*', '', clean, flags=re.IGNORECASE).strip()
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

def validate(orig_en, translated):
    if not translated or not translated.strip():
        return False, "empty"
    # Must have at least one Hebrew letter
    if not re.search(r'[א-ת]', translated):
        # Allow if original was mostly tags/placeholders, OR if the source is
        # essentially a NAME / code / acronym that legitimately stays Latin
        # (e.g. "Miles?", "F.E.A.S.T.", "MJ") — rejecting those wastes retries.
        text_only = TS_RE.sub("", orig_en)
        text_only = re.sub(r'\[[A-Z_]+\]|\{[^}]+\}|%[\w%]+', '', text_only).strip()
        if text_only:
            words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", text_only)
            is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
            # no REAL lowercase word (len>=2) → it's a code / quantity / acronym
            # ("5x[CURRENCY]", "F.E.A.S.T.", "%dx") that legitimately stays Latin.
            no_real_word = not re.search(r'[a-z]{2,}', text_only)
            if not (is_namey or no_real_word):
                return False, "no Hebrew"
    # No bad scripts
    m = BAD_SCRIPTS.search(translated)
    if m:
        char = m.group(0)
        return False, f"bad script char U+{ord(char):04X}"
    # No niqqud
    if NIQQUD.search(translated):
        return False, "niqqud"
    # No accented Latin characters unless in source (detects Polish/French hallucinations)
    for c in re.findall(r'[\u00C0-\u024F]', translated):
        if c not in orig_en:
            return False, f"foreign accented char '{c}'"
    return True, ""

# ── Translate one batch ───────────────────────────────────────────────────────
def translate_batch(batch):
    """batch: list of (key, en_val, has_ts, ends_rlm)"""
    lines = []
    for i, (k, ev, has_ts, ends_rlm) in enumerate(batch, 1):
        marker = "*" if ends_rlm else ""
        lines.append(f"[{i}]{marker} {ev}")

    note = ""
    if any(ends_rlm for _, _, _, ends_rlm in batch):
        note = "\nNote: entries marked with * must end with &rlm;"

    user_msg = (
        "Translate each entry to Hebrew. Return only [N] Hebrew text.\n"
        f"Keep all <ts=\"...\"> tags exactly as written.{note}\n\n"
        + "\n".join(lines)
    )

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user",   "content": user_msg},
    ]

    # subtitle batches: size the token cap from the batch's estimated output so a
    # long multi-<ts> scene never truncates; dialogue uses a fixed cap.
    if any(b[2] for b in batch):
        est = sum(est_out_tokens(b[1]) for b in batch)
        max_tok = min(SUB_MAX_TOK_CAP, int(est * 1.7) + 80)
    else:
        max_tok = MAX_TOK_DIAL
    try:
        raw = lm_call(messages, max_tok)
    except urllib.error.URLError as e:
        return None, f"network: {e}"
    except Exception as e:
        return None, f"error: {e}"

    parsed = parse_response(raw, len(batch))
    results = {}
    for i, (k, ev, has_ts, ends_rlm) in enumerate(batch, 1):
        translated = parsed.get(i, "").strip()
        if not translated:
            continue
        ok, reason = validate(ev, translated)
        if not ok:
            print(f"    [SKIP] {k}: {reason} → '{translated[:60]}'")
            continue
        # Enforce &rlm; if needed
        if ends_rlm and not translated.endswith("&rlm;"):
            translated = translated.rstrip() + "&rlm;"
        results[k] = translated
    return results, None

def translate_batch_robust(batch):
    """Resilient wrapper: translate the batch; whatever's missing (timeout,
    partial response, validation skips) is retried ONCE as a smaller batch.
    Anything still missing is left unwritten → it stays in the queue and is
    re-attempted on the next pass (the supervisor relaunches until 0 remain),
    so no entry is ever lost. Returns a results dict (key -> Hebrew)."""
    results, _err = translate_batch(batch)
    results = results or {}
    missing = [x for x in batch if x[0] not in results]
    if missing:
        time.sleep(1)
        r2, _ = translate_batch(missing)
        if r2:
            results.update(r2)
    # singleton fallback for stubborn entries (e.g. a very long subtitle line
    # that truncates inside a batch) — alone it gets the full token budget.
    missing = [x for x in batch if x[0] not in results]
    for x in missing:
        r3, _ = translate_batch([x])
        if r3:
            results.update(r3)
    return results

# ── Checkpoint helpers ─────────────────────────────────────────────────────────
_lock = threading.Lock()
_done_subs = {}
_done_dial = {}

def load_outputs():
    global _done_subs, _done_dial
    if os.path.exists(OUT_S):
        _done_subs = json.load(open(OUT_S, encoding="utf-8"))
    if os.path.exists(OUT_D):
        _done_dial = json.load(open(OUT_D, encoding="utf-8"))

def _atomic_dump(obj, path):
    """Write to a temp file then os.replace — so a kill mid-write (the
    watchdog may restart us) never leaves a truncated/corrupt JSON, and any
    concurrent reader (the pusher / QA watchdog) always sees a complete file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def flush_outputs():
    with _lock:
        _atomic_dump(_done_subs, OUT_S)
        _atomic_dump(_done_dial, OUT_D)

def record(results, batch):
    with _lock:
        for k, v in results.items():
            has_ts = next((b[2] for b in batch if b[0] == k), False)
            if has_ts:
                _done_subs[k] = v
            else:
                _done_dial[k] = v

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    dry = "--dry-run" in sys.argv
    status_only = "--status" in sys.argv

    load_outputs()
    done_keys = set(_done_subs) | set(_done_dial)

    queue = build_queue()
    remaining = [x for x in queue if x[0] not in done_keys]

    print(f"Total to translate: {len(queue)}")
    print(f"Already done:       {len(done_keys)}")
    print(f"Remaining:          {len(remaining)}")
    print(f"  Subtitles done:   {len(_done_subs)}")
    print(f"  Dialogue done:    {len(_done_dial)}")

    if status_only or dry:
        if dry:
            print("\n[dry-run] First 3 entries:")
            for k, ev, has_ts, ends_rlm in remaining[:3]:
                print(f"  [{k}] ts={has_ts} rlm={ends_rlm}: {ev[:80]}")
        return

    if not remaining:
        print("All done!")
        return

    # Build batches — split by type. Dialogue first (short → fast early progress
    # on the website bar), then subtitles packed by estimated token budget.
    dial_q = [x for x in remaining if not x[2]]
    subs_q = [x for x in remaining if x[2]]
    batches = []
    for i in range(0, len(dial_q), BATCH_DIAL):
        batches.append(dial_q[i:i+BATCH_DIAL])
    cur, cur_est = [], 0
    for x in subs_q:
        e = est_out_tokens(x[1])
        if cur and cur_est + e > SUB_TOKEN_BUDGET:   # would overflow → close batch
            batches.append(cur); cur, cur_est = [], 0
        cur.append(x); cur_est += e
        if cur_est >= SUB_TOKEN_BUDGET:              # full (or one huge entry) → close
            batches.append(cur); cur, cur_est = [], 0
    if cur:
        batches.append(cur)

    print(f"\nBatches: {len(batches)} "
          f"(dialogue {len(dial_q)} @ {BATCH_DIAL}, subtitles {len(subs_q)} "
          f"packed by ~{SUB_TOKEN_BUDGET} tok)  Workers: {WORKERS}", flush=True)
    print("=" * 60)

    done_count = 0
    total = len(remaining)

    # Serial loop (matches LM --parallel 1). Flush after EVERY sub-step so the
    # done-count advances promptly — the watchdog's hang detector keys off it.
    def _commit(res, b):
        if not res:
            return 0
        record(res, b)
        flush_outputs()
        return len(res)

    for bi, b in enumerate(batches):
        results, _err = translate_batch(b)
        results = results or {}
        n = _commit(results, b)
        # one retry for whatever's missing (timeout / truncation / skip)
        missing = [x for x in b if x[0] not in results]
        if missing:
            time.sleep(1)
            r2, _ = translate_batch(missing)
            if r2:
                results.update(r2); n += _commit(r2, b)
        # singleton fallback for stubborn long entries — alone they get the full budget
        for x in [x for x in b if x[0] not in results]:
            r3, _ = translate_batch([x])
            if r3:
                results.update(r3); n += _commit(r3, b)
        done_count += n
        pct = (len(_done_subs) + len(_done_dial)) / max(1, len(queue)) * 100
        if n:
            print(f"  +{n} ({done_count}/{total}) [{pct:.1f}%]  "
                  f"subs={len(_done_subs)} dial={len(_done_dial)}", flush=True)
        else:
            print(f"  [skip] batch {bi} -> 0 results (stays queued)", flush=True)

    flush_outputs()
    print(f"\nDone. subtitles_he.json: {len(_done_subs)}  dialogue_he.json: {len(_done_dial)}")
    print("Next: re-run `python 10_build_patched_localization.py` and rebuild mod.")


if __name__ == "__main__":
    main()
