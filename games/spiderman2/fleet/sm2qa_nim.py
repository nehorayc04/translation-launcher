# -*- coding: utf-8 -*-
"""עידן חדש — Spider-Man 2 line-by-line QA worker (NIM fleet). Reviews EVERY Hebrew line against
its English source AND the game's own gendered languages (Arabic + Russian + Polish + Spanish +
Italian). Per line: ADDRESSEE gender/number, SPEAKER gender, unnatural PHRASING, wrong register,
MISTRANSLATION vs English, leftover FOREIGN/English glued into Hebrew.

Already-translated (review-only) mode — MONOTONIC, can only FIX (never degrade a good line):
  • GENDER flip accepted ONLY when the multi-language evidence baked in (ag=addressee m/f/pl,
    num='pl' true-plural, formal=formal-SINGULAR trap) confirms the NEW Hebrew form.
  • FORMAL-YOU TRAP: ru вы / it voi / es usted to ONE person is FORMAL SINGULAR, NOT plural
    (plural only from Arabic أنتم) -> reject any Hebrew->אתם edit when formal.
  • STRUCTURAL: every <ts>/tag/[TOKEN]/{VALUE}/%spec/&rlm; preserved, stays Hebrew, no
    foreign/niqqud, not a wild rewrite -> else keep the original.
  • Every change is TAGGED; the host merge records before/after for a human audit BEFORE any bake.

⚠️ SM2 Arabic = EGYPTIAN COLLOQUIAL (عامية): إنتَ/إنتِ, عايز/عايزة, فاهم/فاهمة, بتعمل/بتعملي — the
LLM reads it directly; the baked `ag` (MSA-parser) is a conservative hint, not the only signal.

corpus.json = {id:{en,he,ar,ru,pl,es,it,ag,num,formal}}
out.json    = {id:{he,iss}}   (resumable; one stream per VM, disjoint slice)
Run: python sm2qa_nim.py
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
# multi-provider: provider from argv[1] (visible in the process cmdline) or env FLEET_PROVIDER.
_PORDER = ["groq", "sambanova", "nim"]
_PROV = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in _PORDER
         else os.environ.get("FLEET_PROVIDER", "")).strip().lower()
_SUF = f"_{_PROV}" if _PROV in _PORDER else ""
_PIDX = _PORDER.index(_PROV) if _PROV in _PORDER else -1
BASE = "https://integrate.api.nvidia.com/v1"
MODEL = "meta/llama-3.1-70b-instruct"
BUDGET = 220
NW = 1
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, f"out{_SUF}.json")


def _load_out():
    """Load our bank, surviving a file the last hard power-cycle left unflushed (NUL-filled).
    The review is monotonic, so moving a corrupt bank aside merely re-does the slice."""
    if not os.path.exists(OUT):
        return {}
    try:
        return json.load(open(OUT, encoding="utf-8"))
    except Exception as e:
        bad = OUT + ".corrupt-%d" % int(time.time())
        try:
            os.replace(OUT, bad)
        except Exception:
            pass
        print(f"!! {os.path.basename(OUT)} unreadable ({e}) — moved aside, starting empty", flush=True)
        return {}

# --- multi-provider fleet (Groq + SambaNova + NIM). FLEET_PROVIDER/argv pins one provider
#     (3 parallel workers per machine); unset = round-robin. NIM-only fallback if absent. ---
_FLEET = None
try:
    sys.path.insert(0, HERE)
    import fleet_providers as _fp
    _FLEET = _fp.Fleet(_fp.load_keys(HERE), only=(_PROV if _PIDX >= 0 else None))
    print(f"[fleet] {'PINNED ' + _PROV if _PIDX >= 0 else 'round-robin'}: "
          f"{_FLEET.provider_names()} -> {os.path.basename(OUT)}", flush=True)
except Exception as _e:
    print("[fleet] single-NIM fallback:", _e, flush=True)


def _acquire_singleton():
    try:
        import msvcrt
        fh = open(os.path.join(HERE, f"sm2qa{_SUF}.lock"), "w")
        try:
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print("sm2qa_nim already running on this stream -> exit", flush=True)
            sys.exit(0)
        return fh
    except SystemExit:
        raise
    except Exception:
        return None
_SINGLETON = _acquire_singleton()

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
# SM2 structural tokens that MUST survive verbatim: <ts="..">/<span..>/<br>/<i> tags, {VALUE},
# %spec, &rlm;/&nbsp;/&lt; entities, [UPPER_TOKEN] button/icon codes.
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|\[[A-Z0-9_]+\]|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')

# ── multi-language addressee oracle (embedded — the worker runs standalone on the VMs) ──────
_AR_FATHA = "َ"; _AR_KASRA = "ِ"
_AR_YOU_F_PRON = re.compile("(?:أنت|إنت)" + _AR_KASRA); _AR_YOU_M_PRON = re.compile("(?:أنت|إنت)" + _AR_FATHA)
_AR_YOU_PL = re.compile(r"أنتم|أنتن|إنتوا|أنتوا")
_AR_SUF_KF = re.compile("ك" + _AR_KASRA + r"(?![ء-يـ])"); _AR_SUF_KM = re.compile("ك" + _AR_FATHA + r"(?![ء-يـ])")
# feminine 2nd-person ONLY (…ين = unambiguously 2nd-fem). NO bare participles (عايزة/فاهمة) —
# those are 1st/3rd-person too (أنا فاهمة = I-fem SPEAKER) and would pollute the ADDRESSEE signal.
_AR_F_VERBS = ["تريدين","تعرفين","تعلمين","تفعلين","تقولين","تفكرين","تعتقدين","تستطيعين","تذهبين","تأتين",
               "تسمعين","تشعرين","تحتاجين","تجدين","تكونين","تحبين","تظنين","تحاولين","ترين","تدركين",
               "تتذكرين","تنظرين","تعملين","تصدقين","تملكين","تعيشين","تموتين","تخبرين","تسألين","تفهمين",
               "تقصدين","تحملين","تقاتلين","تتعلمين","تخافين","تستحقين","تتوقعين","تلعبين"]
# ⛔ NO colloquial "بت/هت…ي" rule — measured 482/551 WRONG on SM2's Egyptian corpus (weak-final verb
# roots هتيجي, object suffix بترجعني, possessive بتاعي). Precision over recall. Keep in lockstep
# with sm2_build_corpus.py.
_AR_YOU_F_VERB = re.compile(r"(?<![ء-ي])(?:" + "|".join(sorted(_AR_F_VERBS, key=len, reverse=True)) +
                            r")(?:ه|ها|هم|هن|ك|كم|كن|ني|نا)?")


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
_HE_VERB_F = re.compile(r"\b(?:צריכה|יכולה|יודעת|מוכנה|חייבת|תוכלי|תדעי|בואי|קחי|תעשי|לכי|בטוחה|מבינה|שומעת|אמרת|תגידי|רוצה)\b")
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


def _tok(v):
    h = v.get("he", "") if isinstance(v, dict) else ""
    e = v.get("en", "") if isinstance(v, dict) else ""
    return (len(h) + len(e)) // 3 + 10


S1 = ("You are a senior Hebrew localizer for Marvel's Spider-Man 2 (modern-day New York superhero "
      "action — the two Spider-Men Peter Parker & Miles Morales, banter, mission dialogue, story "
      "cutscenes, subtitles). Each item has the English SOURCE, the current HEBREW line, and the "
      "game's PROFESSIONAL translations in ARABIC (ar — EGYPTIAN COLLOQUIAL), RUSSIAN (ru), POLISH "
      "(pl), SPANISH (es) and ITALIAN (it). Those are your GROUND TRUTH for grammatical gender that "
      "English hides. Review each line and FIX real problems, but change NOTHING on a line that is "
      "already good.\n"
      "CROSS-LANGUAGE GENDER:\n"
      "  • ADDRESSEE ('you') — ARABIC decides (colloquial Egyptian): إنتَ/عايز/فاهم/بتعمل→אתה ; "
      "إنتِ/عايزة/فاهمة/بتعملي/ـكِ→את ; أنتم/إنتوا→אתם. Polish confirms: -łeś→אתה, -łaś→את, wy→אתם. "
      "Russian ты+…л→אתה, ты+…ла→את.\n"
      "  • SPEAKER ('I') — Russian я …-л (male) / …-ла (female); Polish -łem/-łam; Arabic أنا فاهم/"
      "فاهمة — match the Hebrew 1st-person, and NEVER change a 1st/3rd-person verb into 2nd-person.\n"
      "  • FORMAL-YOU TRAP: Russian 'вы' / Italian 'voi' / Spanish 'usted' to ONE person is FORMAL "
      "SINGULAR, NOT plural — Hebrew stays אתה/את. Only a TRUE plural (Arabic أنتم/إنتوا) becomes אתם.\n"
      "Also fix: UNNATURAL/literal phrasing → natural modern spoken Hebrew; clear MISTRANSLATION vs "
      "English; leftover FOREIGN/English/Arabic words that should be Hebrew.\n"
      "HARD RULES: keep the SAME meaning; keep every tag/placeholder VERBATIM (the <ts=\"..\"> timing "
      "tags, <span..> <i> <br>, {VALUE}, [TOKEN], %d %s, and the &rlm; RTL anchors); keep proper "
      "NAMES in their canonical Hebrew (ספיידרמן, מיילס, פיטר/פיט, מרי ג'יין, הארי, מיי, ונום, קרייבן, "
      "הלטאה, העקרב, הנשר, החתולה השחורה, מיסטריו, סאנדמן, טומסטון) and NUMBERS; NO niqqud; store "
      "LOGICAL Hebrew (no letter-reversal). If already correct, return it UNCHANGED. Output JSON "
      "{id:{\"he\":<hebrew>,\"iss\":<ok|gender|phrasing|error|foreign>}} — same ids, nothing else.")


def valid_shape(new, cur):
    if not new or not new.strip():
        return False
    if FOREIGN.search(new) or NIQ.search(new) or not HEB.search(new):
        return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(cur)):
        return False
    if difflib.SequenceMatcher(None, new, cur).ratio() < 0.45:
        return False
    return True


def guard(new, iss, cur, ag, num, formal):
    if not isinstance(new, str) or new.strip() == cur.strip() or new == cur:
        return cur, "ok"
    if not valid_shape(new, cur):
        return cur, "ok"
    gc, gn = he_gender(cur), he_gender(new)
    target = "pl" if num == "pl" else ag
    if gn != gc:
        if formal and gn == "pl":
            return cur, "ok"
        if not (target in ("m", "f", "pl") and gn == target):
            return cur, "ok"
    return new, (iss if iss in ("gender", "phrasing", "slang", "error", "foreign") else "error")


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
    return {}


def chat(sysmsg, usermsg, retries=3, timeout=180, max_tokens=2500):
    if _FLEET is not None:
        try:
            r = _parse(_FLEET.complete(sysmsg, usermsg, retries=max(retries, 4),
                                       timeout=timeout, max_tokens=max_tokens))
            if r:
                return r
        except Exception:
            pass
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


def _payload_item(v):
    d = {"en": v.get("en", ""), "he": v.get("he", "")}
    for lg in ("ar", "ru", "pl", "es", "it"):
        if v.get(lg):
            d[lg] = v[lg]
    return d


def do_batch(sub):
    mx = min(3000, sum(_tok(v) for _, v in sub) * 3 + 200)
    # FAIL-FAST timeout (same fix as games/rdr2/fleet/rdr2_nim.py 2026-08-02): every
    # provider's real median (~1s groq, ~3s sambanova, ~16s nim) fits comfortably under
    # 90s; the old ceiling (300s, base 120s) combined with fleet_providers' old 4-attempt
    # single-key retry let ONE stuck batch block a whole worker for up to ~20 minutes
    # with zero output - indistinguishable from "dead" on the dashboard.
    to = min(90, 45 + sum(_tok(v) for _, v in sub) // 10)
    payload = {k: _payload_item(v) for k, v in sub}
    try:
        s1 = chat(S1, "Review each line; fix only real problems:\n" + json.dumps(payload, ensure_ascii=False),
                  timeout=to, max_tokens=mx)
    except Exception as e:
        print(f"  batch fail ({e}) — skip"); return {}
    res = {}
    for k, v in sub:
        cur = v.get("he", "")
        ans = s1.get(k)
        he, iss = None, "ok"
        if isinstance(ans, dict):
            he = ans.get("he") or ans.get("hebrew") or ans.get("text")
            iss = ans.get("iss") or ans.get("issue") or "error"
        elif isinstance(ans, str):
            he = ans
        val, tag = guard(he.strip() if isinstance(he, str) else None, iss, cur,
                         v.get("ag"), v.get("num"), v.get("formal"))
        res[k] = {"he": val, "iss": tag}
    return res


def main():
    keys = load_keys()
    global _KEYS, _KI
    _KEYS = list(keys); _KI = 0
    if _FLEET is None and (not keys or not keys[0].startswith("nvapi-")):
        print("❌ No key found (keys.json / key.txt / NVIDIA_API_KEY)."); return
    # 🔑 A per-provider corpus (corpus_<prov>.json) OVERRIDES the md5%3 split (a reslice hands each
    # stream an exactly equal share once one provider is throttled and strands its third).
    _cp = os.path.join(HERE, f"corpus{_SUF}.json")
    per_prov = bool(_SUF) and os.path.exists(_cp)
    src = _cp if per_prov else CORPUS
    if not os.path.exists(src):
        print(f"❌ corpus not found ({src})."); return
    corpus = json.load(open(src, encoding="utf-8"))
    if _PIDX >= 0 and not per_prov:
        import hashlib
        corpus = {k: v for k, v in corpus.items()
                  if int(hashlib.md5(k.encode()).hexdigest(), 16) % 3 == _PIDX}
    print(f"keys={len(_KEYS)} | corpus={len(corpus)} ({'per-provider file' if per_prov else 'md5%3'})"
          f" | provider={_PROV or 'round-robin'} (Spider-Man 2 QA)")

    while True:
        out = _load_out()
        todo = [(k, corpus[k]) for k in corpus if k not in out]
        todo.sort(key=lambda kv: _tok(kv[1]))
        if not todo:
            fixed = sum(1 for k, v in out.items() if isinstance(v, dict) and v.get("iss") != "ok")
            print(f"✅ ALL DONE — {len(out)} reviewed, {fixed} fixes proposed."); break
        batches = make_batches(todo)
        print(f"remaining {len(todo)} | done {len(out)} | {len(batches)} batches x{NW}")
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
