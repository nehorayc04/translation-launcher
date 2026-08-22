"""Witcher 3 NIM translator — ARABIC -> Hebrew (for the ~1,447 lines whose English
extraction was corrupted; the Arabic is the only clean source).

Same fleet mechanism as w3_nim.py (per-key NIM quota, resumable via out.json, disjoint
corpus.json slice), but the source is the ARABIC text (corpus value = {"ar": ...}).
Stores LOGICAL Hebrew; the VISUAL bake happens at BUILD time. Run: python w3ar_nim.py
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
BUDGET = 150
NW = 1
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, "out.json")

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
_CTRL = "".join(chr(c) for c in range(0x20))

S1 = ("You are a senior Hebrew localizer for The Witcher 3: Wild Hunt (dark medieval fantasy). "
      "Each input line is a string ALREADY professionally localized to ARABIC. Translate it into "
      "natural, fluent, period-appropriate Hebrew, preserving the exact meaning, gender and number "
      "the Arabic marks (أنتَ=אתה / أنتِ=את / أنتم=אתם; feminine ـة → ...ה; plurals). Output ONLY "
      "Hebrew — NO Arabic letters at all. Keep every tag/placeholder VERBATIM: <br>, <i>, </i>, "
      "<font..>, </font>, {curly}, %d/%s, &entities. No niqqud. Proper names use their accepted "
      "Hebrew form (Geralt=גראלט, Ciri=סירי, Yennefer=ינפר, Nilfgaard=נילפגארד, Novigrad=נוביגרד, "
      "Velen=ולן, Skellige=סקליגה, Kaer Morhen=קאר מורהן). Output JSON {id: hebrew} only, same ids.")


def _src(v):
    return v.get("ar", "") if isinstance(v, dict) else (v or "")


def valid(new, src):
    if not new or not new.strip(): return False
    if FOREIGN.search(new) or NIQ.search(new): return False        # no Arabic/foreign, no niqqud
    if not HEB.search(new): return False                            # must be Hebrew
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(src)): return False
    if new.lstrip(_CTRL).strip() == src.strip(): return False       # not a copy of the source
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
    return len(_src(v)) // 3 + 8


def make_batches(todo):
    batches, cur, ct = [], [], 0
    for k, v in todo:
        t = _tok(v)
        if cur and ct + t > BUDGET:
            batches.append(cur); cur, ct = [], 0
        cur.append((k, v)); ct += t
        if ct >= BUDGET:
            batches.append(cur); cur, ct = [], 0
    if cur:
        batches.append(cur)
    return batches


def do_batch(sub):
    to = min(300, 120 + sum(_tok(v) for _, v in sub) // 8)
    mx = min(2500, sum(_tok(v) for _, v in sub) * 2 + 120)
    try:
        s1 = chat(S1, "Translate to Hebrew:\n" + json.dumps({k: _src(v) for k, v in sub}, ensure_ascii=False), timeout=to, max_tokens=mx)
    except Exception as e:
        print(f"  step1 fail ({e}) — skip batch"); return {}
    res = {}
    for k, v in sub:
        he = s1.get(k)
        if isinstance(he, dict):
            he = he.get("he") or he.get("hebrew") or he.get("text") or he.get("translation") or ""
        if not isinstance(he, str):
            continue
        he = he.strip()
        if he and valid(he, _src(v)):
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
    print(f"keys={len(_KEYS)} | model={MODEL} | corpus={len(corpus)} (Witcher 3 ARABIC->Hebrew)")

    while True:
        out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
        todo = [(k, corpus[k]) for k in corpus if k not in out]
        todo.sort(key=lambda kv: _tok(kv[1]))
        if not todo:
            print(f"✅ ALL DONE — {len(out)} lines translated."); break
        batches = make_batches(todo)
        print(f"remaining {len(todo)} | done {len(out)} | {len(batches)} batches x{NW} concurrent")
        t0 = time.time(); prod = 0
        with ThreadPoolExecutor(max_workers=NW) as ex:
            for fut in as_completed([ex.submit(do_batch, b) for b in batches]):
                res = fut.result()
                if res:
                    out.update(res); prod += len(res)
                    atomic(OUT, out)
                    print(f"  ...{prod} produced | {int(time.time() - t0)}s | total {len(out)}")


if __name__ == "__main__":
    main()
