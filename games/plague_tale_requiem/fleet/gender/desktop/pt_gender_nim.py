"""A Plague Tale: Requiem — fleet GENDER-REVIEW worker.

Each corpus item = {en, ar, he}: en = English meaning, ar = the professional Arabic localization
(the gender/number GROUND TRUTH), he = our current Hebrew. The model REVIEWS he against ar and
returns Hebrew whose gender/number (addressee את/אתה/אתם, speaker, referent, plural) matches the
Arabic — changing ONLY gender morphology, nothing else (same words, same order, same tokens). If he
is already correct it returns he UNCHANGED.

The main-PC merge (pull_gender.sh) is the authority: it accepts a proposed line ONLY when it is a
pure gender inflection of the original (identical non-Hebrew scaffold + tiny edit distance), so a
paraphrase or any degradation is rejected and the original stays. This worker just proposes.

Same fleet mechanics as pt_nim.py (key.txt / NVIDIA_API_KEY, corpus.json slice, resumable out.json).
Run: python pt_gender_nim.py
"""
import json, os, re, sys, time, urllib.request, urllib.error, ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # None/no-console when detached -> guard
except Exception:
    pass
try:
    import certifi
    _SSLCTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSLCTX = ssl._create_unverified_context()

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://integrate.api.nvidia.com/v1"
MODEL = "meta/llama-3.1-70b-instruct"
BUDGET = 220
NW = 1
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, "out.json")
LOCK = os.path.join(HERE, "worker.lock")   # PID-singleton: the newest worker wins; older ones exit


def _claim_lock():
    try:
        open(LOCK, "w", encoding="utf-8").write(str(os.getpid()))
    except Exception:
        pass


def _own_lock():
    try:
        return open(LOCK, encoding="utf-8").read().strip() == str(os.getpid())
    except Exception:
        return True

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'\{[^}]*\}|\||%%|%[#0-9.*\-+]*[a-zA-Z]+')

S1 = ("You are a Hebrew localization QA editor for A Plague Tale: Requiem (grim 1349 France). "
      "Each item has THREE fields: 'en' (English meaning), 'ar' (the SAME line professionally "
      "localized to Arabic = the GENDER/NUMBER GROUND TRUTH), and 'he' (our current Hebrew). "
      "Your ONLY job: make the Hebrew's gender & number agree with what the Arabic shows — the "
      "addressee (أنتَ=אתה / أنتِ=את / أنتم/أنتن=אתם/אתן), the speaker's gender, feminine referents "
      "(ـة), and plurals. Arabic 2nd-fem verbs end in ـين (تفعلين) and imperatives in ـي (افعلي); "
      "masculine is تفعل / افعل; plural is أنتم / ـوا / ـون. "
      "Rules: change ONLY the gender/number morphology (pronoun أתה↔את↔אתם, verb form יודע↔יודעת, "
      "adjective מוכן↔מוכנה, etc.). Keep EVERY other word identical, same order, same punctuation, "
      "same tokens ('|' line-breaks and {STR_...} verbatim, same count). Do NOT rephrase, do NOT "
      "add or remove words, do NOT translate from the Arabic or copy Arabic letters, no niqqud. "
      "If 'he' is already correct, return it UNCHANGED. Output JSON {id: hebrew} only, same ids.")


def _f(v, k):
    return (v.get(k, "") if isinstance(v, dict) else "") or ""


def valid(new, he):
    """light worker-side sanity (the merge does the strict scaffold guard)."""
    if not new or not new.strip():
        return False
    if FOREIGN.search(new) or NIQ.search(new):
        return False
    if not HEB.search(new):
        return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(he)):
        return False
    return True


def load_keys():
    keys = []
    raw = os.environ.get("NVIDIA_API_KEYS", "").strip()
    if raw:
        keys += [k.strip() for k in raw.split(",") if k.strip()]
    v = os.environ.get("NVIDIA_API_KEY", "").strip()
    if v and v not in keys:
        keys.append(v)
    kt = os.path.join(HERE, "key.txt")
    if os.path.exists(kt):
        for l in open(kt, encoding="utf-8"):
            l = l.strip()
            if l and not l.startswith("#") and l not in keys:
                keys.append(l)
    return keys


_KEYS = []; _KI = 0; _COOL = {}


def _pick_key():
    global _KI
    n = len(_KEYS); now = time.time()
    for _ in range(n):
        k = _KEYS[_KI % n]; _KI = (_KI + 1) % n
        if _COOL.get(k, 0) <= now:
            return k
    k = min(_KEYS, key=lambda x: _COOL.get(x, 0))
    time.sleep(max(0.0, _COOL.get(k, 0) - now) + 0.5)
    return k


def _one_call(key, sysmsg, usermsg, timeout=180, max_tokens=2500):
    payload = {"model": MODEL, "temperature": 0.1, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout, context=_SSLCTX).read().decode())["choices"][0]["message"]["content"]


def _parse(txt):
    m = re.search(r'\{.*\}', txt, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    out = {}
    for mm in re.finditer(r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*")', txt):
        try:
            out[mm.group(1)] = json.loads(mm.group(2))
        except Exception:
            pass
    return out


def chat(sysmsg, usermsg, retries=3, timeout=180, max_tokens=2500):
    last = None
    for _ in range(retries):
        k = _pick_key()
        try:
            r = _parse(_one_call(k, sysmsg, usermsg, timeout, max_tokens))
            if r:
                return r
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                _COOL[k] = time.time() + 90; continue
            time.sleep(2)
        except Exception as e:
            last = e; time.sleep(2)
    if last:
        raise last
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
    return (len(_f(v, "en")) + len(_f(v, "ar")) + len(_f(v, "he"))) // 3 + 8


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
    mx = min(2500, sum(_tok(v) for _, v in sub) * 2 + 160)
    payload = {k: {"en": _f(v, "en"), "ar": _f(v, "ar"), "he": _f(v, "he")} for k, v in sub}
    try:
        s1 = chat(S1, "Review gender/number:\n" + json.dumps(payload, ensure_ascii=False), timeout=to, max_tokens=mx)
    except Exception as e:
        print(f"  step1 fail ({e}) — skip batch"); return {}
    res = {}
    for k, v in sub:
        he = s1.get(k)
        if isinstance(he, dict):
            he = he.get("he") or he.get("hebrew") or he.get("text") or ""
        if not isinstance(he, str):
            continue
        he = he.strip()
        if he and valid(he, _f(v, "he")):
            res[k] = he            # propose (may equal original; the merge only keeps real, safe changes)
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
    _claim_lock()   # become the sole worker; any older instance exits on its next loop
    print(f"keys={len(_KEYS)} | model={MODEL} | gender-review corpus={len(corpus)} | pid={os.getpid()}")

    while True:
        if not _own_lock():
            print("superseded by a newer worker — exiting"); break
        out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
        todo = [(k, corpus[k]) for k in corpus if k not in out]
        todo.sort(key=lambda kv: _tok(kv[1]))
        if not todo:
            print(f"✅ ALL DONE — {len(out)} reviewed. Copy out.json to the main PC."); break
        batches = make_batches(todo)
        print(f"remaining {len(todo)} | done {len(out)} | {len(batches)} batches")
        t0 = time.time(); prod = 0
        with ThreadPoolExecutor(max_workers=NW) as ex:
            for fut in as_completed([ex.submit(do_batch, b) for b in batches]):
                res = fut.result()
                if res:
                    out.update(res); prod += len(res)
                    atomic(OUT, out)
                    print(f"  ...{prod} reviewed | {int(time.time() - t0)}s | total {len(out)}")


if __name__ == "__main__":
    main()
