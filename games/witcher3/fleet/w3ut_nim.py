"""Witcher 3 NIM translator for the UNTRANSLATED subtitles (still showing Arabic in-game),
with MULTI-LANGUAGE gender review BUILT IN. Each line is translated EN->Hebrew, and its addressee
gender/number is set from a consensus of the game's own gendered languages (Arabic + Russian +
Polish + Spanish + Italian) — so gender is right AT TRANSLATION time, not fixed afterward.

corpus.json = {id: {"en":.., "ar":.., "ru":.., "pl":.., "es":.., "it":..}}  (no 'he' — we create it)
out.json    = {id: "<Hebrew>"}   (LOGICAL; the VISUAL bake happens at BUILD, never here)
Resumable, disjoint slice, per-stream NIM key in key.txt. Run: python w3ut_nim.py
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
STRIKES = os.path.join(HERE, "strikes.json")   # {key: failed attempts}
SKIP = os.path.join(HERE, "skip.json")         # keys parked after MAX_STRIKES (never loop forever)
MAX_STRIKES = 3
SOFT_GENDER_AT = 2   # after this many strikes, accept a valid translation even if the gender guard trips

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;'); LOWER = re.compile(r'[a-z]{2,}')
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$"); _CTRL = "".join(chr(c) for c in range(0x20))
# The EN extraction is XOR-corrupted for ~90% of the untranslated set (garbage CJK/PUA glyphs) while the
# Arabic (keyID0 cleartext) is clean -> for those lines the ARABIC is the real translation source.
_GARB = re.compile(r'[　-￿]'); _BIDICTL = re.compile(r'[‎‏‪-‮⁦-⁩]')


def clean_en(en):
    """Return the English ONLY if it is real readable text; else '' (garbage/empty -> translate from ar)."""
    en = (en or "").strip()
    if not en or _GARB.search(en):
        return ""
    p = sum(1 for c in en if 32 <= ord(c) < 127)
    return en if len(en) and p / len(en) > 0.7 else ""


def src_text(v):
    """The effective translation source: clean English if present, else the Arabic (bidi-stripped)."""
    en = clean_en(v.get("en", "")) if isinstance(v, dict) else ""
    if en:
        return en
    return _BIDICTL.sub("", (v.get("ar", "") if isinstance(v, dict) else "")).strip()

# ── multi-language ADDRESSEE gender oracle (embedded; worker is standalone on the VMs) ──────────
_AR_FATHA = "َ"; _AR_KASRA = "ِ"
_AR_YOU_F_PRON = re.compile("أنت" + _AR_KASRA); _AR_YOU_M_PRON = re.compile("أنت" + _AR_FATHA)
_AR_YOU_PL = re.compile(r"أنتم|أنتن|أنتما")
_AR_SUF_KF = re.compile("ك" + _AR_KASRA + r"(?![ء-يـ])"); _AR_SUF_KM = re.compile("ك" + _AR_FATHA + r"(?![ء-يـ])")
_AR_F_VERBS = ["تريدين","تعرفين","تعلمين","تفعلين","تقولين","تفكرين","تعتقدين","تستطيعين","تذهبين","تأتين",
               "تسمعين","تشعرين","تحتاجين","تختارين","تجدين","تكونين","تحبين","تظنين","تبحثين","تحاولين",
               "ترين","تدركين","تتذكرين","تنظرين","تعملين","تصدقين","تخططين","تملكين","تعيشين","تموتين",
               "تخبرين","تسألين","تجيبين","تفهمين","تقصدين","تنوين","تحملين","تقاتلين","تتعلمين","تخافين",
               "تستحقين","تنتمين","تتوقعين","تلعبين"]
_AR_YOU_F_VERB = re.compile(r"\b(?:" + "|".join(sorted(_AR_F_VERBS, key=len, reverse=True)) +
                            r")(?:ه|ها|هم|هن|كِ|كَ|ك|كم|كن|ني|نا)?\b")


def ar_gender(text):
    if not text:
        return None
    if _AR_YOU_PL.search(text):
        return "pl"
    fem = bool(_AR_YOU_F_PRON.search(text) or _AR_SUF_KF.search(text) or _AR_YOU_F_VERB.search(text))
    masc = bool(_AR_YOU_M_PRON.search(text) or _AR_SUF_KM.search(text))
    return "f" if fem and not masc else "m" if masc and not fem else None


_RU_TOK = re.compile(r"[а-яё]+", re.I)
_RU_ADJ_F = {"готова","уверена","рада","должна","сама","одна","права","жива","мертва"}
_RU_ADJ_M = {"готов","уверен","рад","должен","сам","один","прав","жив","мёртв","мертв"}


def _ru_axis(text):
    gs = set()
    for w in _RU_TOK.findall(text.lower()):
        if w in _RU_ADJ_F or (len(w) >= 4 and w.endswith("ла")):
            gs.add("f")
        elif w in _RU_ADJ_M or (len(w) >= 3 and w.endswith("л") and not w.endswith("ль")):
            gs.add("m")
    return "f" if gs == {"f"} else "m" if gs == {"m"} else None


def ru_addr(text):
    if not text:
        return None
    t = _RU_TOK.findall(text.lower())
    if "вы" in t:
        return "pl"
    if "ты" in t and "я" not in t:
        return _ru_axis(text)
    return None


_PL_TOK = re.compile(r"[a-ząćęłńóśźż]+", re.I)
_PL_ADJ_F = {"gotowa","pewna","sama","zmęczona","pijana","martwa","bezpieczna","wolna","chora","silna"}
_PL_ADJ_M = {"gotowy","pewien","pewny","sam","zmęczony","pijany","martwy","bezpieczny","wolny","chory","silny"}


def pl_addr(text):
    if not text:
        return None
    t = _PL_TOK.findall(text.lower()); ts = set(t)
    if "wy" in ts or "jesteście" in ts or any(w.endswith("liście") or w.endswith("łyście") for w in t):
        return "pl"
    f = any(w.endswith("łaś") and len(w) >= 5 for w in t) or bool(ts & _PL_ADJ_F)
    m = any(w.endswith("łeś") and len(w) >= 5 for w in t) or bool(ts & _PL_ADJ_M)
    return "f" if f and not m else "m" if m and not f else None


_ES_2P = re.compile(r"\b(?:estás|estabas|eres|serás|fuiste|quedaste|estuviste|pareces|sigues)\s+"
                    r"(?:muy\s+|tan\s+|un\s+poco\s+|bastante\s+)?[a-záéíóúñ]{3,}?([oa])s?\b", re.I)
_ES_WEL = re.compile(r"\bbienvenid([oa])s?\b", re.I)
_ES_PL = re.compile(r"\b(?:vosotros|vosotras|estáis|sois|habéis|tenéis|podéis|queréis|sabéis|vuestr[oa]s?)\b", re.I)


def es_addr(text):
    if not text:
        return None
    if _ES_PL.search(text):
        return "pl"
    m = _ES_2P.search(text) or _ES_WEL.search(text)
    return ("f" if m.group(1).lower() == "a" else "m") if m else None


_IT_2P = re.compile(r"\b(?:sei|eri|sarai|fosti)\s+(?:molto\s+|tanto\s+|piuttosto\s+)?[a-zàèéìòù]{3,}?([oa])\b", re.I)
_IT_WEL = re.compile(r"\bbenvenut([oa])\b", re.I)
_IT_PL = re.compile(r"\b(?:voi|siete|sarete|foste|avete|potete|volete|dovete|sapete|vostr[oaie])\b", re.I)


def it_addr(text):
    if not text:
        return None
    if _IT_PL.search(text):
        return "pl"
    m = _IT_2P.search(text) or _IT_WEL.search(text)
    return ("f" if m.group(1).lower() == "a" else "m") if m else None


_HE_YOU_M = re.compile(r"(?<![א-ת])אתה(?![א-ת])"); _HE_YOU_PL = re.compile(r"(?<![א-ת])את[םן](?![א-ת])")
_HE_VERB_F = re.compile(r"\b(?:צריכה|יכולה|יודעת|מוכנה|חייבת|תוכלי|תדעי|בואי|קחי|תעשי|לכי|בטוחה|מבינה|שומעת|תגידי|רוצה)\b")
_HE_VERB_M = re.compile(r"\b(?:צריך|יכול|יודע|מוכן|חייב|תוכל|תדע|בוא|קח|תעשה|בטוח|מבין|שומע|תגיד)\b")


def he_gender(text):
    if not text:
        return None
    if _HE_YOU_PL.search(text):
        return "pl"
    has_f = bool(re.search(r"(?<![א-ת])את(?![א-ת])(?!\s+ה)", text))
    fem = bool(_HE_VERB_F.search(text)) or has_f
    masc = bool(_HE_YOU_M.search(text)) or bool(_HE_VERB_M.search(text))
    return "m" if masc and not fem else "f" if fem and not masc else None


def consensus_target(v):
    """Arabic (strict 2nd-person) decides alone; when it is ambiguous, >=2 non-Arabic languages
    agreeing on m/f decide; plural is taken ONLY from Arabic أنتم (ru вы / it voi are formal-sing)."""
    a = ar_gender(v.get("ar", ""))
    if a in ("m", "f", "pl"):
        return a
    votes = {}
    for fn, txt in ((ru_addr, v.get("ru", "")), (pl_addr, v.get("pl", "")),
                    (es_addr, v.get("es", "")), (it_addr, v.get("it", ""))):
        g = fn(txt)
        if g in ("m", "f"):
            votes[g] = votes.get(g, 0) + 1
    if not votes:
        return None
    best = max(votes, key=lambda k: votes[k])
    if votes[best] < 2 or (len(votes) > 1 and sorted(votes.values())[-2:] == [votes[best], votes[best]]):
        return None
    return best


_GTXT = {"m": "The listener being addressed is MALE — use אתה and masculine 2nd-person verbs.",
         "f": "The listener being addressed is FEMALE — use את and feminine 2nd-person verbs (חושבת/תגידי/קחי).",
         "pl": "The listener is PLURAL — use אתם and plural 2nd-person verbs."}

S1 = ("You are a senior Hebrew localizer for The Witcher 3: Wild Hunt (dark medieval fantasy). "
      "Each input line gives the SAME line in several languages of the game's own professional "
      "localization: 'en' (English — MAY BE EMPTY/corrupted, ignore it then), 'ar' (Arabic), "
      "'ru' (Russian), 'es' (Spanish), 'it' (Italian), plus 'g' = the addressee gender/number. "
      "TRANSLATE THE MEANING into natural, fluent, period-appropriate Hebrew: if 'en' is present and "
      "readable use it; OTHERWISE the Arabic 'ar' is the PRIMARY source and Russian/Spanish/Italian "
      "confirm the meaning. NEVER copy Arabic/Russian/foreign letters — produce clean Hebrew only. "
      "Set the ADDRESSEE's gender/number to 'g' (m=אתה, f=את, pl=אתם) and inflect verbs/possessives "
      "to match — Arabic (أنتَ/أنتِ/أنتم) gives the addressee gender, Russian past (сказал/сказала) "
      "the speaker gender, Spanish/Italian (-o/-a) the referent; make the Hebrew agree with them. "
      "Keep every tag/placeholder VERBATIM (<br>, <font..>, </font>, {curly}, %d/%s, &entities). "
      "No niqqud. Proper names (Geralt=גֵּרַלט, Ciri=סירי, Yennefer=יינפר, Novigrad, places, monsters) "
      "stay in their accepted Hebrew form; brand/code tokens stay Latin. Output JSON {id: hebrew} "
      "only, same ids.")


def _en(v):
    return v.get("en", "") if isinstance(v, dict) else (v or "")


def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)


def valid(new, src):
    if not new or not new.strip():
        return False
    if FOREIGN.search(new) or NIQ.search(new):
        return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(src)):
        return False
    core = STRUCT.sub(" ", src); bare = new.lstrip(_CTRL).strip()
    # require real Hebrew output when the source has translatable words (English OR Arabic)
    has_words = bool(LOWER.search(core)) or bool(re.search(r'[؀-ۿ]', core))
    if has_words and not HEB.search(new):
        if not (bare == src.strip() and is_namey(src)):
            return False
    if len(src) >= 12 and bare == src.strip() and not is_namey(src):
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
    payload = {"model": MODEL, "temperature": 0.2, "max_tokens": max_tokens,
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
    ar = v.get("ar", "") if isinstance(v, dict) else ""
    return (len(_en(v)) + len(ar)) // 3 + 8


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


def do_batch(sub, strikes=None):
    strikes = strikes or {}
    to = min(300, 120 + sum(_tok(v) for _, v in sub) // 8)
    mx = min(2500, sum(_tok(v) for _, v in sub) * 2 + 120)
    # payload gives the model every clean language of the game's own localization + the resolved gender.
    payload = {}
    tgt = {}
    for k, v in sub:
        g = consensus_target(v) or ""
        tgt[k] = g
        payload[k] = {"en": clean_en(v.get("en", "")),
                      "ar": _BIDICTL.sub("", v.get("ar", "")).strip(),
                      "ru": v.get("ru", ""), "es": v.get("es", ""), "it": v.get("it", ""),
                      "g": {"m": "masculine", "f": "feminine", "pl": "plural"}.get(g, "unknown")}
    hint = "\n".join(_GTXT[g] for g in {t for t in tgt.values() if t}) if any(tgt.values()) else ""
    try:
        s1 = chat(S1 + (" " + hint if hint else ""),
                  "Translate the MEANING (prefer 'en' if readable, else the Arabic; respect each 'g'):\n"
                  + json.dumps(payload, ensure_ascii=False),
                  timeout=to, max_tokens=mx)
    except Exception as e:
        print(f"  step1 fail ({e}) — skip batch"); return {}
    res = {}
    single = len(sub) == 1
    for k, v in sub:
        he = s1.get(k)
        # a LONG line goes solo (its own batch); llama then often answers {"he": "..."} / {"text": "..."}
        # instead of keying by the id -> s1.get(id) misses it and the highest-value narrative lines
        # (quest logs, autopsy report) all parked. For a 1-line batch, fall back to the sole value.
        if he is None and single and len(s1) == 1:
            he = next(iter(s1.values()))
        if isinstance(he, dict):
            he = he.get("he") or he.get("hebrew") or he.get("text") or he.get("translation") or ""
        if not isinstance(he, str):
            continue
        # llama often ignores "No niqqud" and returns vowel-pointed Hebrew (פֵּיווֶה / גֵּרַלט). The
        # consonantal text is CORRECT — STRIP the niqqud instead of rejecting it (rejecting looped the
        # queue forever → the whole run stalled). Also drop bidi controls the model may inject.
        he = NIQ.sub("", _BIDICTL.sub("", he.strip()))
        if not he or not valid(he, src_text(v)):
            continue
        # gender guard: if the multi-lang target is determinable and the Hebrew came out with the
        # OPPOSITE explicit gender, reject -> re-queued and retried. But NEVER loop forever: after
        # SOFT_GENDER_AT strikes accept the (valid) translation anyway — a correct meaning with an
        # uncertain gender beats a line left showing ARABIC in-game.
        g = tgt.get(k)
        if g in ("m", "f", "pl") and strikes.get(k, 0) < SOFT_GENDER_AT:
            hg = he_gender(he)
            if hg and hg != g:
                continue
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
    print(f"keys={len(_KEYS)} | model={MODEL} | corpus={len(corpus)} (W3 untranslated, translate + multi-lang gender)")

    def _load(p, dflt):
        try:
            return json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            return dflt

    while True:
        out = _load(OUT, {})
        strikes = _load(STRIKES, {})
        skip = set(_load(SKIP, []))
        todo = [(k, corpus[k]) for k in corpus if k not in out and k not in skip]
        todo.sort(key=lambda kv: _tok(kv[1]))
        if not todo:
            print(f"✅ ALL DONE — {len(out)} lines ({len(skip)} parked). Copy out.json to the main PC."); break
        batches = make_batches(todo)
        print(f"remaining {len(todo)} | done {len(out)} | parked {len(skip)} | {len(batches)} batches x{NW}")
        t0 = time.time(); prod = 0
        with ThreadPoolExecutor(max_workers=NW) as ex:
            futs = {ex.submit(do_batch, b, strikes): b for b in batches}
            for fut in as_completed(futs):
                sub = futs[fut]
                res = fut.result() or {}
                # STRIKE every key that was attempted but produced nothing (invalid / gender-guard /
                # API failure). At MAX_STRIKES it is PARKED -> the queue can NEVER loop forever on an
                # un-bankable line (the documented SM2 stall bug). Parked lines keep the Arabic.
                newly_parked = 0
                for k, _ in sub:
                    if k in res:
                        strikes.pop(k, None)
                        continue
                    strikes[k] = strikes.get(k, 0) + 1
                    if strikes[k] >= MAX_STRIKES:
                        skip.add(k); newly_parked += 1
                if res:
                    out.update(res); prod += len(res)
                    atomic(OUT, out)
                atomic(STRIKES, strikes)
                if newly_parked:
                    atomic(SKIP, sorted(skip))
                    print(f"  parked {newly_parked} un-bankable (total {len(skip)})")
                if res:
                    print(f"  ...{prod} produced | {int(time.time() - t0)}s | total {len(out)}")


if __name__ == "__main__":
    main()
