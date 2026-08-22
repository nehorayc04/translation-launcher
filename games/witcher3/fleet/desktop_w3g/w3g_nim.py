"""Witcher 3 NIM GENDER-REVIEW worker — cross-check every addressee-gendered line's
Hebrew against the game's ARABIC (the professional loc that MARKS gender) and fix ONLY
the addressee gender where the Hebrew (translated from gender-less English) guessed wrong.

SAFETY: a gender CHANGE is accepted ONLY when the Arabic UNAMBIGUOUSLY marks the addressee
gender (vocalized أنتِ/أنتَ, ـكِ/ـكَ, a curated 2nd-fem verb, or أنتم plural) AND the model's
new Hebrew matches THAT gender. Lines whose Arabic is ambiguous (bare أنت, bare تفعل) are
UN-VERIFIABLE -> kept EXACTLY as-is (never flipped on a guess). This makes the pass monotonic:
it can only FIX a wrong gender, never introduce one.

corpus.json = {id: {"en":..., "ar":<ground truth>, "he":<current Hebrew>}}. Output out.json
= {id: <reviewed Hebrew>} (unchanged unless a verifiable fix applied). Stores LOGICAL; the
VISUAL bake happens at BUILD. Run: python w3g_nim.py
"""
import json, os, re, sys, time, difflib, urllib.request, urllib.error, ssl
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
BUDGET = 220
NW = 1
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, "out.json")

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')

# ── embedded gender parsers (ported from universal/gender_oracle.py — the worker runs
#    stand-alone on the VMs, so no import) ────────────────────────────────────────────
_AR_FATHA = "َ"; _AR_KASRA = "ِ"
_AR_YOU_F_PRON = re.compile("أنت" + _AR_KASRA)          # أنتِ
_AR_YOU_M_PRON = re.compile("أنت" + _AR_FATHA)          # أنتَ
_AR_YOU_PL = re.compile(r"أنتم|أنتن|أنتما")
_AR_SUF_KF = re.compile("ك" + _AR_KASRA + r"(?![ء-يـ])")
_AR_SUF_KM = re.compile("ك" + _AR_FATHA + r"(?![ء-يـ])")
_AR_F_VERBS = ["تريدين", "تعرفين", "تعلمين", "تفعلين", "تقولين", "تفكرين", "تعتقدين", "تستطيعين",
               "تذهبين", "تأتين", "تسمعين", "تشعرين", "تحتاجين", "تختارين", "تجدين", "تكونين",
               "تحبين", "تظنين", "تبحثين", "تحاولين", "ترين", "تدركين", "تتذكرين", "تنظرين",
               "تعملين", "تصدقين", "تخططين", "تملكين", "تعيشين", "تموتين", "تخبرين", "تسألين",
               "تجيبين", "تفهمين", "تقصدين", "تنوين", "تحملين", "تقاتلين", "تتعلمين", "تخافين",
               "تستحقين", "تنتمين", "تتوقعين", "تلعبين"]
_AR_YOU_F_VERB = re.compile(r"\b(?:" + "|".join(sorted(_AR_F_VERBS, key=len, reverse=True)) +
                            r")(?:ه|ها|هم|هن|كِ|كَ|ك|كم|كن|ني|نا)?\b")


def ar_gender(text):
    """'m'|'f'|'pl'|None — HIGH-PRECISION addressee gender (vocalized markers + curated verbs)."""
    if not text:
        return None
    if _AR_YOU_PL.search(text):
        return "pl"
    fem = bool(_AR_YOU_F_PRON.search(text) or _AR_SUF_KF.search(text) or _AR_YOU_F_VERB.search(text))
    masc = bool(_AR_YOU_M_PRON.search(text) or _AR_SUF_KM.search(text))
    if fem and not masc:
        return "f"
    if masc and not fem:
        return "m"
    return None


_HE_YOU_M = re.compile(r"(?<![א-ת])אתה(?![א-ת])")
_HE_YOU_PL = re.compile(r"(?<![א-ת])את[םן](?![א-ת])")
_HE_VERB_F = re.compile(r"\b(?:צריכה|יכולה|יודעת|מוכנה|חייבת|תוכלי|תדעי|בואי|קחי|"
                        r"תעשי|לכי|בטוחה|מבינה|שומעת|אמרת|תגידי|רוצה)\b")
_HE_VERB_M = re.compile(r"\b(?:צריך|יכול|יודע|מוכן|חייב|תוכל|תדע|בוא|קח|"
                        r"תעשה|בטוח|מבין|שומע|תגיד)\b")


def he_gender(text):
    """'m'|'f'|'pl'|None — gender/number the Hebrew is CURRENTLY addressing."""
    if not text:
        return None
    if _HE_YOU_PL.search(text):
        return "pl"
    has_f_pron = bool(re.search(r"(?<![א-ת])את(?![א-ת])(?!\s+ה)", text))
    fem = bool(_HE_VERB_F.search(text)) or has_f_pron
    masc = bool(_HE_YOU_M.search(text)) or bool(_HE_VERB_M.search(text))
    if masc and not fem:
        return "m"
    if fem and not masc:
        return "f"
    return None


def _tok(v):
    h = v.get("he", "") if isinstance(v, dict) else ""
    a = v.get("ar", "") if isinstance(v, dict) else ""
    return (len(h) + len(a)) // 3 + 10


S1 = ("You are a senior Hebrew localizer for The Witcher 3. Each item has the English source, "
      "the game's professional ARABIC translation (which correctly MARKS the ADDRESSEE's gender/"
      "number), and a current HEBREW line that was translated from the gender-less English and may "
      "have the WRONG gender. Your ONLY job: make the Hebrew's ADDRESSEE gender/number match the "
      "Arabic. أنتَ/ـكَ=masculine→אתה; أنتِ/ـكِ/verb…ين=feminine→את; أنتم=plural→אתם. Fix the "
      "second-person pronoun AND its verbs/adjectives (תוכל↔תוכלי, קח↔קחי, תן↔תני, חושב↔חושבת, "
      "יודע↔יודעת, שלך). CHANGE NOTHING ELSE — same words/meaning/names/numbers/punctuation, and "
      "every tag/placeholder VERBATIM (<br> <i> </i> <font..> {..} %d &ent;). Do NOT re-translate; "
      "do NOT touch 1st/3rd-person verbs (the speaker's own 'אני יודע' stays). If already correct, "
      "return it UNCHANGED. Output JSON {id: hebrew} only, same ids.")


def valid_shape(new, cur):
    """same line, gender-only edit — no re-translation, tags preserved."""
    if not new or not new.strip():
        return False
    if FOREIGN.search(new) or NIQ.search(new) or not HEB.search(new):
        return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(cur)):
        return False
    if difflib.SequenceMatcher(None, new, cur).ratio() < 0.60:
        return False
    return True


def guard(new, cur, ag):
    """Return the value to store. A CHANGE is accepted ONLY if it is a clean same-line edit
    AND the new Hebrew's addressee gender == the Arabic's unambiguous gender. Otherwise keep
    the ORIGINAL (never flip on a guess)."""
    if new == cur:
        return cur
    if not valid_shape(new, cur):
        return cur
    ng = he_gender(new)
    if ng == ag:               # verified fix toward the Arabic gender
        return new
    return cur                 # unverifiable / contradicts Arabic -> keep original


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
    payload = {"model": MODEL, "temperature": 0.1, "max_tokens": max_tokens,
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
    """sub = only ag-clear lines. Each item v carries a precomputed v['_ag']."""
    mx = min(3000, sum(_tok(v) for _, v in sub) * 3 + 150)
    to = min(300, 120 + sum(_tok(v) for _, v in sub) // 6)
    payload = {k: {"en": v.get("en", ""), "ar": v.get("ar", ""), "he": v.get("he", "")} for k, v in sub}
    try:
        s1 = chat(S1, "Review + fix addressee gender:\n" + json.dumps(payload, ensure_ascii=False),
                  timeout=to, max_tokens=mx)
    except Exception as e:
        print(f"  step1 fail ({e}) — skip batch"); return {}
    res = {}
    for k, v in sub:
        he = s1.get(k)
        if isinstance(he, dict):
            he = he.get("he") or he.get("hebrew") or he.get("text") or ""
        cur = v.get("he", "")
        if not isinstance(he, str):
            res[k] = cur           # no answer -> keep original (still reviewed)
            continue
        res[k] = guard(he.strip(), cur, v.get("_ag"))
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
    print(f"keys={len(_KEYS)} | model={MODEL} | corpus={len(corpus)} (Witcher 3 GENDER review vs Arabic)")

    while True:
        out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
        # ag-ambiguous lines are UN-VERIFIABLE: record them unchanged (no model call, no flip).
        recorded = False
        for k, v in corpus.items():
            if k in out:
                continue
            ag = ar_gender(v["ar"])
            if ag not in ("m", "f"):
                out[k] = v["he"]; recorded = True
        if recorded:
            atomic(OUT, out)
        todo = [(k, dict(corpus[k], _ag=ar_gender(corpus[k]["ar"]))) for k in corpus if k not in out]
        todo.sort(key=lambda kv: _tok(kv[1]))
        if not todo:
            changed = sum(1 for k in out if k in corpus and out[k] != corpus[k]["he"])
            print(f"✅ ALL DONE — {len(out)} reviewed, {changed} gender-fixed."); break
        batches = make_batches(todo)
        print(f"verifiable-remaining {len(todo)} | done {len(out)} | {len(batches)} batches x{NW}")
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
