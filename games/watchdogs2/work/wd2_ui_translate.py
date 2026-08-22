"""WD2 Hebrew UI Translator
Translates Watch Dogs 2 interface strings (menus, HUD, objectives, prompts,
settings, item/vehicle descriptions) to Hebrew via LM Studio (same local model
the SM2 run uses — gemma-4-31b-it). Shares the serial --parallel 1 slot, so it
runs ALONGSIDE the SM2 translator (requests interleave).

Input : C:/tmp/wd2_ui_queue.json   [{id, enum, en}, ...]  (built by the analysis step)
Output: C:/tmp/wd2_ui_he.json      {id_str: hebrew_LOGICAL}  (resumable checkpoint)
        Hebrew is stored LOGICAL here; wd2_ui_merge.py applies the visual-order
        reversal (the WD2 frontend renderer is non-bidi).

Usage:
    python wd2_ui_translate.py            # full run (resumable)
    python wd2_ui_translate.py --status   # show progress
    python wd2_ui_translate.py --dry-run  # scan only
"""
import json, os, re, sys, time, urllib.request, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

QUEUE = "C:/tmp/wd2_ui_queue.json"
OUT   = "C:/tmp/wd2_ui_he.json"
SKIP  = "C:/tmp/wd2_ui_skip.json"   # permanently-unfixable keys (optional)

LM_URL = "http://localhost:1234/v1/chat/completions"
MODEL  = "gemma-4-31b-it@q2_k_xl"   # same model the SM2 run uses; shares the serial slot
TIMEOUT = 600
BATCH   = 14          # UI lines are short → a bigger batch amortizes the prefill
MAX_TOK = 460         # per-batch ceiling (sized up for the occasional long description)

# ── System prompt (short, strict — re-prefilled every batch) ───────────────────
SYSTEM = """You are an expert Hebrew localizer for the video game Watch Dogs 2. Translate English INTERFACE strings (menus, HUD labels, mission objectives, button prompts, settings, item/vehicle/clothing names and descriptions) into concise, natural Israeli Hebrew — the tone of a real game UI.

HARD RULES — a violation REJECTS the line:
1. Output ONLY Hebrew + Latin letters/digits. NO Arabic/Cyrillic/Greek/CJK/Hangul/Thai or any other script. NEVER use niqqud (vowel marks).
2. Copy these EXACTLY, unchanged, in place: button tokens in brackets like [HIDEINCAR] [PLACEWAYPOINT] [RELOAD]; color tags [CSS_BLUE] [CSS_RED] [CSS_END] [CSS_...]; {VALUE} placeholders; format specs %d %u %s %ls %0.2f %i %f and %% (never collapse %% to %); HTML entities &#xA; &amp; &gt; &lt; &nbsp; &apos; &quot;; and any single replacement-character icon byte.
3. Keep names/brands in English exactly as written: Watch Dogs, Watch_Dogs, DedSec, ctOS, Blume, San Francisco, Oakland, Marin, Silicon Valley, Marcus, Wrench, Sitara, Josh, Horatio, Ray/T-Bone, Bratva, Prime_Eight, Tezcas, Ubisoft, Uplay, Nudle, !nvite, Driver SF, Hacker, and all person/company/place/product proper names.
4. Acronyms stay English (XP, GPS, HUD, FPS, AI, ID, ATM, SF, GB, MB, RAM, CPU).
5. A string that is only a code/number/symbol with no real word (e.g. "TBT-7000", "336-TT", "%ls") — return it UNCHANGED.
6. ON/OFF toggles: ON→"פעיל", OFF→"כבוי", YES→"כן", NO→"לא", OK→"אישור".

OUTPUT only the numbered lines: [1] [2] [3]… each followed by its Hebrew (or the unchanged source for rule 5). No labels, no notes, no explanations."""

# ── placeholder preservation check ─────────────────────────────────────────────
PH = re.compile(r'\[[A-Z0-9_]+\]|\[CSS_[A-Z]+\]|\{[^}]*\}|%[0-9.]*[diufsl]+|%%|&#?\w+;')
def placeholders(s):
    from collections import Counter
    return Counter(PH.findall(s))

BAD_SCRIPTS = re.compile(r'[؀-ۿЀ-ӿͰ-Ͽ฀-๿ऀ-ॿ一-鿿가-힯֑-ׇ]')
NIQQUD = re.compile(r'[֑-ׇ]')
HEB = re.compile(r'[א-ת]')
WORDEN = re.compile(r'[a-z]{2,}')
# the model occasionally REFUSES or appends an explanation instead of translating —
# catch the meta-text (English or Hebrew) so it never ships (re-queued instead).
REFUSAL = re.compile(
    r"(as an ai|i\s+(cannot|can'?t|am unable|am sorry|apolog)"
    r"|unable to (translate|comply|process)|cannot (translate|comply|fulfil)"
    r"|here('?s| is) the translation|i\s+don'?t\s+understand"
    r"|לתרגם את הבקשה|אינני יכול לתרגם|לא ניתן לתרגם|איני יכול לתרגם)", re.I)

def validate(en, he):
    if not he or not he.strip():
        return False, "empty"
    if not HEB.search(he):
        # accept no-Hebrew only when the source is a NAME/CODE that legitimately
        # stays Latin (proper noun ≤4 words, OR no real lowercase word like a code).
        # MUST match the QA rule, else the model correctly keeping "Marcus"/"DedSec"
        # is rejected and re-queued forever (the SM2 name/code-churn lesson).
        core = PH.sub("", en).strip()
        # also strip html entities/tags so a markup-only string reads as empty.
        core = re.sub(r'&[a-zA-Z#0-9]+;|<[^>]+>', '', core).strip()
        words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
        is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
        no_real_word = not re.search(r'[a-z]{2,}', core)
        # single-token camelCase / has-digit / long concatenation = a handle/id
        # ("doneGOOFED") — untranslatable, stays Latin (else it loops the queue).
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
    if len(en) >= 8 and len(he) > 2.4 * len(en) + 40:
        return False, "length anomaly (rambling)"
    if placeholders(en) != placeholders(he):
        return False, "placeholder mismatch"
    return True, ""

# ── LM ──────────────────────────────────────────────────────────────────────--
def lm_call(messages, max_tok):
    body = json.dumps({"model": MODEL, "messages": messages,
                       "max_tokens": max_tok, "temperature": 0.2}).encode()
    req = urllib.request.Request(LM_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()

NUM_RE = re.compile(r'^\[(\d+)\]\s*(.*)', re.DOTALL)
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

def est_tok(batch):
    return min(MAX_TOK if len(batch) > 1 else 700,
              int(sum(len(r["en"]) for r in batch) / 2.3) + 90)

def translate_batch(batch):
    lines = [f"[{i}] {r['en']}" for i, r in enumerate(batch, 1)]
    user = ("Translate each interface string to Hebrew. Return only [N] Hebrew.\n\n"
            + "\n".join(lines))
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    try:
        raw = lm_call(msgs, est_tok(batch))
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

STRIKES = "C:/tmp/wd2_ui_strikes.json"

def park_failures(ids):
    """3-strike park (mirrors the SM2 stall fix): an id that fails EVERY attempt
    in a pass strikes; at 3 it joins wd2_ui_skip.json so the queue can't loop on
    it forever (model refusals, handles, brand names) — the build's English
    fallback covers it. Returns the ids parked this call."""
    if not ids:
        return []
    try:
        strikes = load(STRIKES, {})
    except Exception:
        strikes = {}
    try:
        skip = set(load(SKIP, []))
    except Exception:
        skip = set()
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
    skip  = set(load(SKIP, []))
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

    batches = [remaining[i:i+BATCH] for i in range(0, len(remaining), BATCH)]
    print(f"Batches: {len(batches)} @ {BATCH}\n" + "=" * 56, flush=True)

    total = len(queue)
    for bi, b in enumerate(batches):
        res, err = translate_batch(b)
        # retry the missing subset once
        miss = [r for r in b if str(r["id"]) not in res]
        if miss:
            time.sleep(0.5)
            r2, _ = translate_batch(miss)
            res.update(r2)
        # singleton fallback for stubborn long entries
        for r in [r for r in b if str(r["id"]) not in res]:
            r3, _ = translate_batch([r])
            res.update(r3)
        if res:
            done.update(res)
            atomic_dump(done, OUT)
        # strike + park anything that failed every attempt so the queue can't
        # loop on it forever (refusals/handles/brand names) — the WD2 stall fix.
        parked = park_failures([str(r["id"]) for r in b if str(r["id"]) not in res])
        if parked:
            print(f"  [PARK] {len(parked)} id(s) hit 3 strikes -> skip-list", flush=True)
        pct = len(done) / max(1, total) * 100
        tag = f"+{len(res)}" if res else "[skip]"
        print(f"  {tag} batch {bi+1}/{len(batches)}  ({len(done)}/{total}) [{pct:.1f}%]", flush=True)

    print(f"\nDone. {len(done)} translated -> {OUT}")
    print("Next: wd2_ui_merge.py (combine + visual) -> wd2_loc.py encode -> deploy")

if __name__ == "__main__":
    main()
