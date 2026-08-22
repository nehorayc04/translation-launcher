"""Standalone Witcher 3 NIM translator — SINGLE-Hebrew {key: he} (NOT dual-gender).

Same fleet mechanism as CP2077's vm_nim.py (per-source-IP NIM quota, resumable via out.json,
disjoint corpus.json slice), but:
  * output shape = {key: "hebrew"}  (W3 has no per-listener gender split → one Hebrew string)
  * NO S2 gender-split call (half the requests → ~2x faster than the CP2077 worker)
  * store LOGICAL Hebrew here; the VISUAL pre-reversal (`visual_line`) happens at BUILD time
    (games/witcher3/work/w3strings.py), NEVER in the worker.

Put the NVIDIA key in key.txt (nvapi-... line) or NVIDIA_API_KEY. Run: python w3_nim.py
It loops until corpus.json (its disjoint slice) is drained. Copy out.json back to the main PC.
"""
import json, os, re, sys, time, urllib.request, urllib.error, ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import certifi
    _SSLCTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSLCTX = ssl._create_unverified_context()

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://integrate.api.nvidia.com/v1"
MODEL = "meta/llama-3.1-70b-instruct"
BUDGET = 150  # small batches complete within timeout even when NIM is throttled (~2-3 tok/s)
NW = 1         # single key per stream -> serial (NIM parallelism comes from the 6 separate keys, not threads)
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, "out.json")

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
# W3 tokens: <br>, XML-ish tags, {curly}, %spec, &entities, and studio markers like <font>/<color>
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;'); LOWER = re.compile(r'[a-z]{2,}')
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$"); MIXED = re.compile(r'[֐-׿][A-Za-z]|[A-Za-z][֐-׿]'); _CTRL = "".join(chr(c) for c in range(0x20))

S1 = ("You are a senior Hebrew localizer for The Witcher 3: Wild Hunt (dark medieval fantasy). "
      "Each input line has TWO fields: 'en' = the English MEANING to translate, and 'ar' = THE SAME "
      "line already professionally localized to Arabic. Translate the MEANING from 'en' into natural, "
      "fluent, period-appropriate Hebrew. Use 'ar' ONLY as the GENDER/NUMBER oracle: Arabic marks what "
      "English drops — the addressee (أنتَ=אתה / أنتِ=את / أنتم=אתם), the speaker's gender, feminine "
      "referents (ـة → ...ה), and plurals. Make your Hebrew match the gender/number the Arabic shows "
      "(so a line spoken to a woman gets את/feminine verbs, to a man gets אתה/masculine). Do NOT "
      "translate FROM the Arabic and do NOT copy Arabic words — 'en' is the meaning, 'ar' is only the "
      "gender hint. Keep every tag/placeholder VERBATIM from the English: <br>, <font..>, </font>, "
      "{curly}, %d/%s, &entities. No niqqud. Proper names (Geralt, Ciri, Yennefer, Novigrad, places, "
      "monsters) stay as their accepted Hebrew form or transliteration; brand/code tokens stay Latin. "
      "Output JSON {id: hebrew} only, same ids as the input.")


def _en(v):
    """corpus value → English (supports both the new {'en','ar'} shape and a bare string)."""
    return v.get("en", "") if isinstance(v, dict) else (v or "")


def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)


def valid(new, en):
    if not new or not new.strip(): return False
    if FOREIGN.search(new) or NIQ.search(new): return False
    if MIXED.search(new): return False   # reject Hebrew+Latin glued in a word (the reglue bug)
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)): return False
    core = STRUCT.sub(" ", en); bare = new.lstrip(_CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return False
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return False
    return True


def load_keys():
    keys = []
    raw = os.environ.get("NVIDIA_API_KEYS", "").strip()
    if raw: keys += [k.strip() for k in raw.split(",") if k.strip()]
    v = os.environ.get("NVIDIA_API_KEY", "").strip()
    if v and v not in keys: keys.append(v)
    kt = os.path.join(HERE, "key.txt")
    if os.path.exists(kt):
        for l in open(kt, encoding="utf-8"):
            l = l.strip()
            if l and not l.startswith("#") and l not in keys: keys.append(l)
    return keys


_KEYS = []; _KI = 0; _COOL = {}


def _pick_key():
    global _KI
    n = len(_KEYS); now = time.time()
    for _ in range(n):
        k = _KEYS[_KI % n]; _KI = (_KI + 1) % n
        if _COOL.get(k, 0) <= now: return k
    k = min(_KEYS, key=lambda x: _COOL.get(x, 0))
    time.sleep(max(0.0, _COOL.get(k, 0) - now) + 0.5)
    return k


def _one_call(key, sysmsg, usermsg, timeout=180, max_tokens=2500):
    payload = {"model": MODEL, "temperature": 0.2, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout, context=_SSLCTX).read().decode())["choices"][0]["message"]["content"]


def _parse(txt):
    m = re.search(r'\{.*\}', txt, re.S)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    out = {}
    for mm in re.finditer(r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*")', txt):
        try: out[mm.group(1)] = json.loads(mm.group(2))
        except Exception: pass
    return out


def chat(sysmsg, usermsg, retries=3, timeout=180, max_tokens=2500):
    last = None
    for _ in range(retries):
        k = _pick_key()
        try:
            r = _parse(_one_call(k, sysmsg, usermsg, timeout, max_tokens))
            if r: return r
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                _COOL[k] = time.time() + 90; continue
            time.sleep(2)
        except Exception as e:
            last = e; time.sleep(2)
    if last: raise last
    return {}


def atomic(path, obj):
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    for _ in range(12):
        try:
            os.replace(tmp, path); return
        except PermissionError:
            time.sleep(0.3)
    os.replace(tmp, path)


def _tok(v):
    """rough input-token estimate for one corpus item ({'en','ar'} or bare str)."""
    ar = v.get("ar", "") if isinstance(v, dict) else ""
    return (len(_en(v)) + len(ar)) // 3 + 8


def make_batches(todo):
    """token-budget batches: a long book gets its own call; short lines pack together."""
    batches, cur, ct = [], [], 0
    for k, v in todo:
        t = _tok(v)
        if cur and ct + t > BUDGET:
            batches.append(cur); cur, ct = [], 0
        cur.append((k, v)); ct += t
        if ct >= BUDGET:                      # a single oversized item -> flush as its own batch
            batches.append(cur); cur, ct = [], 0
    if cur:
        batches.append(cur)
    return batches


def do_batch(sub):
    """translate one batch -> {k: he} of the VALIDATED lines (runs in a worker thread; no I/O)."""
    to = min(300, 120 + sum(_tok(v) for _, v in sub) // 8)   # long books get a longer read timeout
    mx = min(2500, sum(_tok(v) for _, v in sub) * 2 + 120)   # small for short batches (NIM-reliable), big only for books
    try:
        s1 = chat(S1, "Translate:\n" + json.dumps({k: v for k, v in sub}, ensure_ascii=False), timeout=to, max_tokens=mx)
    except Exception as e:
        print(f"  step1 fail ({e}) — skip batch"); return {}
    res = {}
    for k, v in sub:
        he = s1.get(k)
        if isinstance(he, dict):                                  # llama sometimes nests {id:{he:..}}
            he = he.get("he") or he.get("hebrew") or he.get("text") or he.get("translation") or ""
        if not isinstance(he, str):
            continue
        he = he.strip()
        if he and valid(he, _en(v)):
            res[k] = he
    return res


def main():
    keys = load_keys()
    if not keys or not keys[0].startswith("nvapi-"):
        print("❌ No NVIDIA key found (key.txt / NVIDIA_API_KEY)."); return
    global _KEYS, _KI
    _KEYS = list(keys); _KI = 0
    if not os.path.exists(CORPUS):
        print(f"❌ corpus.json not found ({CORPUS})."); return
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    print(f"keys={len(_KEYS)} | model={MODEL} | corpus={len(corpus)} (Witcher 3, gender-aware: en+ar)")

    while True:
        out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
        todo = [(k, corpus[k]) for k in corpus if k not in out]
        todo.sort(key=lambda kv: _tok(kv[1]))   # SHORTS FIRST (small=fast+NIM-reliable), long books last
        if not todo:
            print(f"✅ ALL DONE — {len(out)} lines translated. Copy out.json to the main PC."); break
        batches = make_batches(todo)
        print(f"remaining {len(todo)} | done {len(out)} | {len(batches)} batches x{NW} concurrent")
        t0 = time.time(); prod = 0
        # NIM calls run concurrently in worker threads; only the main thread mutates out + writes.
        with ThreadPoolExecutor(max_workers=NW) as ex:
            for fut in as_completed([ex.submit(do_batch, b) for b in batches]):
                res = fut.result()
                if res:
                    out.update(res); prod += len(res)
                    atomic(OUT, out)
                    print(f"  ...{prod} produced | {int(time.time() - t0)}s | total {len(out)}")


if __name__ == "__main__":
    main()
