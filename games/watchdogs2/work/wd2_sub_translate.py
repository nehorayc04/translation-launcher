"""WD2 Hebrew SUBTITLE / dialogue translator.

Translates the spoken in-game lines (oasis enum="soundbinary\\N.bnk") + the
remaining translatable named content (messages, descriptions, objectives,
profiler facts) EN->Hebrew via the local LM (gemma-4-31b-it@q2_k_xl @ LM Studio).

Input : C:/tmp/wd2_sub_queue.json   [{id, enum, en}, ...]  (wd2_sub_build_queue.py)
Output: C:/tmp/wd2_sub_he.json      {id_str: hebrew_LOGICAL}  (resumable checkpoint)
        Hebrew is stored LOGICAL here; wd2_ui_merge.py applies the visual-order
        reversal at build time (the WD2 frontend renderer is non-bidi).

Same heavy protections as the UI/SM2/CP2077 runs: short strict prompt, token-budget
batching (a long bark scene goes solo), validate() with name/code passthrough,
3-strike park, atomic resumable writes.

Usage:
    python wd2_sub_translate.py            # full run (resumable)
    python wd2_sub_translate.py --status   # show progress
    python wd2_sub_translate.py --dry-run  # scan only
"""
import json, os, re, sys, time, urllib.request, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

QUEUE = "C:/tmp/wd2_sub_queue.json"
OUT   = "C:/tmp/wd2_sub_he.json"
SKIP  = "C:/tmp/wd2_sub_skip.json"
STRIKES = "C:/tmp/wd2_sub_strikes.json"

LM_URL = "http://localhost:1234/v1/chat/completions"
MODEL  = "gemma-4-31b-it@q2_k_xl"
TIMEOUT = 900          # subtitle scenes can be long; generous so a real reply completes
# token-budget batching — pack short barks together, let a long scene go solo.
SUB_TOKEN_BUDGET = 320   # estimated source tokens per batch
MAX_BATCH        = 12    # never exceed this many lines per batch
MAX_TOK_CAP      = 1100  # per-batch generation ceiling

# ── System prompt (short, strict — re-prefilled every batch) ───────────────────
SYSTEM = """You are an expert Hebrew localizer for the video game Watch Dogs 2. Translate spoken SUBTITLE / dialogue lines (characters talking, radio chatter, NPC barks, mission narration, in-game messages) into natural, idiomatic Israeli Hebrew — fluent spoken Hebrew, matching the streetwise hacker tone of DedSec. Keep it concise; a subtitle must read fast.

HARD RULES — a violation REJECTS the line:
1. Output ONLY Hebrew + Latin letters/digits. NO Arabic/Cyrillic/Greek/CJK/Hangul/Thai or any other script. NEVER use niqqud (vowel marks).
2. Copy these EXACTLY, unchanged, in place: bracket tokens like [PlayerName] [hacker] [HACK] [CSS_BLUE] [CSS_END] [laughs] [beat]; {threshold} {VALUE} placeholders; the literal two-character sequence \\n (a forced line break — keep it where it is); format specs %d %u %s %ls %i %f %0.2f and %% (never collapse %% to %); HTML entities &#xA; &amp; &gt; &lt; &nbsp;.
3. Keep names/brands in English exactly: Watch Dogs, DedSec, ctOS, Blume, San Francisco, Oakland, Marin, Silicon Valley, Marcus, Wrench, Sitara, Josh, Horatio, Ray, T-Bone, Bratva, Prime_Eight, Tezcas, Nudle, !nvite, and all person/company/place/product proper names.
4. Acronyms stay English (XP, GPS, HUD, FPS, AI, ID, ATM, SF, GB, MB, OPD, FBI).
5. A line that is only a code/number/symbol/proper-name with no real word — return it UNCHANGED.
6. Translate the meaning naturally — do NOT translate word-for-word, do NOT add notes or explanations, do NOT answer questions in the text. Preserve tone, slang, and profanity intensity.

OUTPUT only the numbered lines: [1] [2] [3]… each followed by its Hebrew (or the unchanged source for rule 5). No labels, no commentary."""

# ── placeholder preservation check (subtitle-tuned) ─────────────────────────────
# any bracket token (upper OR lower case: [HACK] [hacker] [laughs] [PlayerName]),
# {tokens}, printf specs incl. width/x/e, %%, and numeric/named HTML entities.
PH = re.compile(r'\[[A-Za-z0-9_]+\]|\{[^}]*\}|%[0-9.]*[diufslxe]+|%%|&#?\w+;')
def placeholders(s):
    from collections import Counter
    return Counter(PH.findall(s))

BAD_SCRIPTS = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯֑-ׇ]')
NIQQUD = re.compile(r'[֑-ׇ]')
HEB = re.compile(r'[א-ת]')
REFUSAL = re.compile(
    r"(as an ai|i\s+(cannot|can'?t|am unable|am sorry|apolog)"
    r"|unable to (translate|comply|process)|cannot (translate|comply|fulfil)"
    r"|here('?s| is) the translation|i\s+don'?t\s+understand"
    r"|לתרגם את הבקשה|אינני יכול לתרגם|לא ניתן לתרגם|איני יכול לתרגם)", re.I)

def validate(en, he):
    if not he or not he.strip():
        return False, "empty"
    if not HEB.search(he):
        core = PH.sub("", en).strip()
        core = re.sub(r'&[a-zA-Z#0-9]+;|<[^>]+>', '', core).strip()
        words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
        is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
        no_real_word = not re.search(r'[a-z]{2,}', core)
        is_handle = (" " not in core and
                     bool(re.search(r'[a-z][A-Z]', core) or re.search(r'\d', core)
                          or len(core) >= 11))
        if core and not (is_namey or no_real_word or is_handle):
            return False, "no Hebrew"
    m = BAD_SCRIPTS.search(he)
    if m:
        return False, f"bad script U+{ord(m.group(0)):04X}"
    if NIQQUD.search(he):
        return False, "niqqud"
    for c in re.findall(r'[À-ɏ]', he):
        if c not in en:
            return False, f"foreign accent '{c}'"
    if REFUSAL.search(he):
        return False, "refusal/explanation leak"
    if len(en) >= 8 and len(he) > 2.6 * len(en) + 50:
        return False, "length anomaly (rambling)"
    if placeholders(en) != placeholders(he):
        return False, "placeholder mismatch"
    return True, ""

# ── LM ──────────────────────────────────────────────────────────────────────--
def lm_call(messages, max_tok):
    body = json.dumps({"model": MODEL, "messages": messages,
                       "max_tokens": max_tok, "temperature": 0.25}).encode()
    req = urllib.request.Request(LM_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()

NUM_RE = re.compile(r'^\s*\[(\d+)\]\s*(.*)', re.DOTALL)
def parse_response(text, n):
    out = {}; cur = None; parts = []
    def flush():
        if cur is not None and parts:
            out[cur] = " ".join(" ".join(parts).split())
    for line in text.splitlines():
        m = NUM_RE.match(line)
        if m:
            flush(); cur = int(m.group(1)); parts = [m.group(2)]
        elif cur is not None:
            parts.append(line)
    flush()
    if n == 1 and not out:
        out[1] = re.sub(r'^(translation:|here is.*?:)\s*', '', text.strip(), flags=re.I).strip()
    return out

def est_out_tokens(batch):
    # Hebrew output ~ source length; size the gen ceiling from the batch.
    est = int(sum(len(r["en"]) for r in batch) / 1.8) + 60 * len(batch)
    return max(120, min(MAX_TOK_CAP, est))

def make_batches(rows):
    """Token-budget packing: a long scene lands alone; short barks pack together."""
    batches, cur, cur_tok = [], [], 0
    for r in rows:
        t = int(len(r["en"]) / 3.2) + 8        # rough source-token estimate
        if cur and (cur_tok + t > SUB_TOKEN_BUDGET or len(cur) >= MAX_BATCH):
            batches.append(cur); cur, cur_tok = [], 0
        cur.append(r); cur_tok += t
        if t > SUB_TOKEN_BUDGET:               # huge single scene -> flush solo
            batches.append(cur); cur, cur_tok = [], 0
    if cur:
        batches.append(cur)
    return batches

def translate_batch(batch):
    lines = [f"[{i}] {r['en']}" for i, r in enumerate(batch, 1)]
    user = ("Translate each subtitle/dialogue line to Hebrew. Return only [N] Hebrew.\n\n"
            + "\n".join(lines))
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    try:
        raw = lm_call(msgs, est_out_tokens(batch))
    except Exception as e:
        return {}, str(e)
    parsed = parse_response(raw, len(batch))
    res = {}
    for i, r in enumerate(batch, 1):
        he = parsed.get(i, "").strip()
        if not he:
            continue
        ok, why = validate(r["en"], he)
        if not ok:
            print(f"    [SKIP] {r['id']} ({why}): {he[:50]!r}")
            continue
        res[str(r["id"])] = he
    return res, None

# ── checkpoint ─────────────────────────────────────────────────────────────────
def load(path, default):
    if os.path.exists(path):
        try: return json.load(open(path, encoding="utf-8"))
        except Exception: pass
    return default

def atomic_dump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def park_failures(ids):
    if not ids:
        return []
    strikes = load(STRIKES, {}) or {}
    skip = set(load(SKIP, []) or [])
    parked = []
    for k in ids:
        if k in skip:
            continue
        strikes[k] = strikes.get(k, 0) + 1
        if strikes[k] >= 3:
            skip.add(k); parked.append(k); strikes.pop(k, None)
    atomic_dump(strikes, STRIKES)
    if parked:
        atomic_dump(sorted(skip), SKIP)
    return parked

def main():
    queue = load(QUEUE, [])
    done  = load(OUT, {})
    skip  = set(load(SKIP, []) or [])
    remaining = [r for r in queue if str(r["id"]) not in done and str(r["id"]) not in skip]

    print(f"Queue: {len(queue)}  done: {len(done)}  remaining: {len(remaining)}", flush=True)
    if "--status" in sys.argv:
        return
    if "--dry-run" in sys.argv:
        for r in remaining[:5]:
            print(f"  [{r['id']}] {r['enum']}: {r['en'][:70]}")
        return
    if not remaining:
        print("All done!"); return

    batches = make_batches(remaining)
    print(f"Batches: {len(batches)} (token-budget packed)\n" + "=" * 56, flush=True)

    total = len(queue)
    for bi, b in enumerate(batches):
        res, err = translate_batch(b)
        miss = [r for r in b if str(r["id"]) not in res]
        if miss:
            time.sleep(0.5)
            r2, _ = translate_batch(miss)
            res.update(r2)
        for r in [r for r in b if str(r["id"]) not in res]:
            r3, _ = translate_batch([r])
            res.update(r3)
        if res:
            done.update(res)
            atomic_dump(done, OUT)
        parked = park_failures([str(r["id"]) for r in b if str(r["id"]) not in res])
        if parked:
            print(f"  [PARK] {len(parked)} id(s) hit 3 strikes -> skip-list", flush=True)
        pct = len(done) / max(1, total) * 100
        tag = f"+{len(res)}" if res else "[skip]"
        print(f"  {tag} batch {bi+1}/{len(batches)}  ({len(done)}/{total}) [{pct:.1f}%]", flush=True)

    print(f"\nDone. {len(done)} translated -> {OUT}")

if __name__ == "__main__":
    main()
