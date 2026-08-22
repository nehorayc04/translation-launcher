# -*- coding: utf-8 -*-
"""God of War: Ragnarök — EN→Hebrew translator (local LM Studio).

Reads  english.json  (EN source, id->str)  +  arabic.json (AR skeleton, id->str)
Writes hebrew.json   (id->str)  ← the resumable checkpoint (atomic writes).

Scope = ids present in BOTH en and ar (the shippable AR-slot, ~48,886). Hebrew
is written into those ids; the build step (gowr_wad.py pack) drops them into the
Arabic slot of r_lang_ar.wad.

Design follows the Universal Playbook §3 (serial LM, short strict prompt,
token-budget batching, validate(), atomic flush). Run via gowr_watchdog.py.

  python gowr_translate.py            # translate the queue
  python gowr_translate.py --status   # count done / remaining
"""
import os, sys, re, json, time, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # playbook gotcha #1

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EN_F   = os.path.join(HERE, "english.json")
AR_F   = os.path.join(HERE, "arabic.json")
OUT_F  = os.path.join(HERE, "hebrew.json")
SKIP_F = os.path.join(HERE, "gowr_translate_skip.json")

# Gemini via OpenAI-compatible endpoint (1M context, fast, no slot limit)
GEMINI_URL  = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
MODEL   = "gemini-2.5-flash"    # change to gemini-2.5-pro for higher quality
TIMEOUT = 120
TOKEN_BUDGET = 1500      # Gemini handles large batches; pack until estimated tokens hit this
MAX_TOK_CAP  = 4096      # absolute per-batch max_tokens
SOLO_CHARS   = 3000      # a value longer than this gets its own batch

def _load_env(path):
    env = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env

_ENV = _load_env(os.path.join(ROOT, ".env"))
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or _ENV.get("GEMINI_API_KEY", "")

# tokens that must survive verbatim
TOK_RE = re.compile(r"\[\[S:[^\]]*\]\]|\[/?style[^\]]*\]|\[/?i\]|\[Icons:[^\]]*\]|\[[A-Za-z][^\]]*Button\]|%d|%s|\\n")
# Old-Norse runic block (U+16A0–U+16FF) — keep VERBATIM, never translate/transliterate
RUNE_RE = re.compile(r"[ᚠ-᛿]")

# minimal seed glossary — extend as the game's terms surface
GLOSSARY = {
    "Kratos": "קרייטוס", "Atreus": "אטראוס", "Mimir": "מימיר", "Freya": "פריה",
    "Brok": "ברוק", "Sindri": "סינדרי", "Tyr": "טיר", "Thor": "ת'ור",
    "Odin": "אודין", "Angrboda": "אנגרבודה", "Heimdall": "היימדל",
    "Svartalfheim": "סוורטלפהיים", "Midgard": "מידגארד", "Asgard": "אסגארד",
    "Ragnarok": "ראגנארוק", "Valhalla": "ולהאלה", "Spartan": "ספרטני",
}

SYSTEM = (
    "You are a professional God of War: Ragnarök localizer translating English to Hebrew.\n"
    "HARD RULES:\n"
    "1. Output Hebrew. Latin letters allowed only for untranslatable brand/code.\n"
    "2. NEVER use niqqud (vowel points).\n"
    "3. Copy EVERY tag/placeholder EXACTLY, same count, same position: [[S:...]] voice cues, "
    "[style=...]/[/style], [i]/[/i], [Icons:...], [...Button] glyphs, %d, %s, and literal \\n.\n"
    "4. Do NOT translate the text inside [[S:...]] — it is an audio reference.\n"
    "5. Character & realm names use their fixed Hebrew spelling (Kratos=קרייטוס, Atreus=אטראוס, "
    "Mimir=מימיר, Freya=פריה, Tyr=טיר, Odin=אודין, Svartalfheim=סוורטלפהיים).\n"
    "6. Translate ONLY what needs translating. Copy these VERBATIM, never translate/transliterate "
    "them: Old-Norse RUNES (ᚠᚢᚦᚨᚱ… U+16A0–U+16FF), standalone Latin words/codes, digits 0-9, and "
    "basic punctuation ? ! @ & %. A line that is only runes/Latin/digits/punctuation is returned "
    "unchanged.\n"
    "7. Output ONLY numbered translated lines, nothing else."
)


def _load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _atomic_write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=0)
    os.replace(tmp, path)


def is_dev_meta(v):
    return (not v.strip()) or v.startswith("Design#") or v in ("OBSOLETE", "CUT")


def is_namey(v):
    """A short value with no lowercase English word — keep as-is is acceptable."""
    return not re.search(r"[a-z]{2,}", v)


def est_tokens(s):
    return max(8, len(s) // 3)


def build_queue():
    en = _load(EN_F, {})
    ar = _load(AR_F, {})
    done = _load(OUT_F, {})
    skip = set(_load(SKIP_F, []))
    q = []
    for k in ar:                       # AR-slot ids are the shippable target
        if k in done or k in skip:
            continue
        src = en.get(k)
        if src is None or is_dev_meta(src):
            continue
        q.append((k, src))
    q.sort(key=lambda kv: int(kv[0]))
    return en, ar, done, q


def pack_batches(queue):
    batch, budget = [], 0
    for k, src in queue:
        if len(src) > SOLO_CHARS:
            if batch:
                yield batch; batch, budget = [], 0
            yield [(k, src)]
            continue
        t = est_tokens(src)
        if batch and budget + t > TOKEN_BUDGET:
            yield batch; batch, budget = [], 0
        batch.append((k, src)); budget += t
    if batch:
        yield batch


def lm_call(user, max_tok):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set — add it to the root .env")
    body = json.dumps({
        "model": MODEL, "temperature": 0.2, "max_tokens": max_tok,
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(GEMINI_URL, body, {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + GEMINI_API_KEY,
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def validate(src, out):
    if not out or not out.strip():
        return False
    if re.search(r"[֑-ׇ]", out):              # niqqud
        return False
    if re.search(r"[؀-ۿЀ-ӿ一-鿿]", out):  # arabic/cyrillic/cjk
        return False
    # token multiset preserved
    if sorted(TOK_RE.findall(src)) != sorted(TOK_RE.findall(out)):
        return False
    # Old-Norse runes must survive verbatim (keep-as-is, never translated)
    if sorted(RUNE_RE.findall(src)) != sorted(RUNE_RE.findall(out)):
        return False
    # must contain Hebrew unless the source is a name/code OR pure runes/punct
    if (not re.search(r"[א-ת]", out) and not is_namey(src)
            and not RUNE_RE.search(src)):
        return False
    return True


def translate_batch(batch):
    numbered = "\n".join(f"{i+1}. {src}" for i, (_, src) in enumerate(batch))
    max_tok = min(MAX_TOK_CAP, max(64, sum(est_tokens(s) for _, s in batch) * 2 + 64))
    raw = lm_call(numbered, max_tok)
    lines = {}
    for m in re.finditer(r"^\s*(\d+)\.\s?(.*)$", raw, re.M):
        lines[int(m.group(1))] = m.group(2).rstrip()
    out = {}
    for i, (k, src) in enumerate(batch):
        cand = lines.get(i + 1, "")
        if validate(src, cand):
            out[k] = cand
    return out


def main():
    if "--status" in sys.argv:
        en, ar, done, q = build_queue()
        total = len(done) + len(q)
        print(f"done {len(done):,} / scope {total:,}  ({len(q):,} remaining)")
        return 0
    en, ar, done, queue = build_queue()
    print(f"queue: {len(queue):,} to translate, {len(done):,} already done")
    n = 0
    for batch in pack_batches(queue):
        try:
            res = translate_batch(batch)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"[lm-error] {e} — sleeping 15s"); time.sleep(15); continue
        # robust: retry the misses once, singly
        miss = [(k, s) for k, s in batch if k not in res]
        for k, s in miss:
            try:
                r1 = translate_batch([(k, s)])
                res.update(r1)
            except Exception:
                pass
        done.update(res); n += len(res)
        _atomic_write(OUT_F, done)          # flush after EVERY batch (playbook)
        print(f"[+{len(res)}/{len(batch)}] total {len(done):,}")
    print(f"finished this pass: +{n}, total {len(done):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
