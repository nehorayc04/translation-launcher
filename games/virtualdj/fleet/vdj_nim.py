"""Standalone VirtualDJ Hebrew NIM translator (New-Era: source EN + all shipped
languages as the meaning/gender oracle). Same fleet mechanism as the W3/PT
workers: per-source-IP NIM quota, resumable via out.json, a disjoint
corpus.json slice ({key: {"en":.., "refs":{lang:..}}}).

Store LOGICAL Hebrew; NO bidi transform here (VirtualDJ RTL-renders the Arabic
locale, proven in-game). Put the NVIDIA key in key.txt (nvapi-...) or
NVIDIA_API_KEY. Run: python vdj_nim.py   (loops until corpus.json is drained).
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
BUDGET = 130
NW = 1
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, "out.json")

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿͰ-Ͽ฀-๿]')
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
HEB = re.compile(r'[א-ת]')
# VirtualDJ tokens to preserve: %-specs + [[...]] link markers.
TOK = re.compile(r'%%|%2F|%[0-9]*[a-zA-Z]|\[\[[^\]]*\]\]')
LOWER = re.compile(r'[a-z]{2,}')
_NAMEWORD = re.compile(r"^[A-Za-z0-9][\w.\-'/]*$")

S1 = ("You are a senior Hebrew software localizer for VirtualDJ (professional DJ "
      "software). Each line has 'en' = the English UI/help text to translate, and "
      "'refs' = the SAME line already localized to other languages (de/fr/es/it/ru/"
      "pt/nl/el/ja/zh/ar) — use them ONLY to disambiguate meaning, context, gender "
      "and number (the Arabic alone is sometimes wrong). Translate the MEANING of "
      "'en' into concise, natural, professional Hebrew (software-localization "
      "register, like Windows Hebrew). Rules: normal logical Hebrew (do NOT reverse "
      "letters). NO niqqud. Keep every token VERBATIM: %-format specs (%i %s %d %% "
      "%2F) and [[...]] link markers — same count. Brand/product names + acronyms "
      "stay Latin (VirtualDJ, ASIO, MIDI, CDJ, BPM, FX, EQ, iTunes, Serato, "
      "RekordBox, Traktor, Deezer, TIDAL, SoundCloud, Beatport, Spotify...). Glossary: "
      "Deck=דק, Loop=לולאה, Sampler=דוגם, Crossfader=קרוספיידר, Cue=קיו, Gain=גיין, "
      "Pitch=פיץ', Stems=סטמס, Beatgrid=רשת מקצבים, Skin=עיצוב, Broadcast=שידור, "
      "Karaoke=קריוקי. IMPORTANT: many lines are VDJScript command documentation — "
      "translate the prose explanation but keep command names, parameter names, "
      "on/off values and quoted code examples (e.g. 'beatjump +1', action_deck) in "
      "English exactly. Output JSON {id: hebrew} only, same ids as the input.")


def _en(v):
    return v.get("en", "") if isinstance(v, dict) else (v or "")


def _refs(v):
    return v.get("refs", {}) if isinstance(v, dict) else {}


def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    if ws and len(ws) <= 2 and all(_NAMEWORD.match(w) for w in ws):
        return True
    if len(ws) == 1 and any(c.isupper() for c in ws[0]):
        return True
    return False


def valid(new, en):
    if not new or not new.strip():
        return False
    if FOREIGN.search(new) or NIQ.search(new):
        return False
    if sorted(TOK.findall(new)) != sorted(TOK.findall(en)):
        return False
    core = TOK.sub(" ", en)
    if LOWER.search(core) and not HEB.search(new):
        if not is_namey(en):
            return False
    if new.strip() == en.strip() and LOWER.search(core) and not is_namey(en):
        return False
    return True


def key():
    for p in (os.path.join(HERE, "key.txt"), r"C:\ptw\key.txt", r"C:\w3w\key.txt"):
        if os.path.exists(p):
            for ln in open(p, encoding="utf-8"):
                if ln.strip().startswith("nvapi-"):
                    return ln.strip()
    return os.environ.get("NVIDIA_API_KEY", "").strip()


API_KEY = key()


def call(msgs, temp=0.2, mx=1600):
    body = json.dumps({"model": MODEL, "messages": msgs, "temperature": temp,
                       "max_tokens": mx}).encode()
    req = urllib.request.Request(BASE + "/chat/completions", data=body,
                                 headers={"Authorization": "Bearer " + API_KEY,
                                          "Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=180, context=_SSLCTX) as r:
        return json.load(r)["choices"][0]["message"]["content"]


def batch(items):
    payload = {k: {"en": _en(v), "refs": _refs(v)} for k, v in items}
    try:
        txt = call([{"role": "system", "content": S1},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
        s, e = txt.find("{"), txt.rfind("}")
        out = json.loads(txt[s:e + 1])
    except Exception as ex:
        print("  batch err:", type(ex).__name__, ex); return {}
    good = {}
    for k, v in items:
        raw = out.get(k)
        if isinstance(raw, dict):        # model sometimes nests {"he":..}/{"text":..}
            raw = raw.get("he") or raw.get("text") or raw.get("hebrew") or ""
        he = (raw if isinstance(raw, str) else "").strip()
        try:
            if valid(he, _en(v)):
                good[k] = he
        except Exception:
            pass
    return good


def main():
    if not API_KEY:
        print("NO KEY"); return
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    done = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    todo = [(k, v) for k, v in corpus.items() if k not in done]
    print(f"vdj_nim: {len(todo)} todo / {len(corpus)}  (model {MODEL})")
    i = 0
    while i < len(todo):
        # pack a budget of ~BUDGET output tokens worth of short UI lines
        chunk, cost = [], 0
        while i < len(todo) and cost < BUDGET and len(chunk) < 20:
            k, v = todo[i]; chunk.append((k, v))
            cost += max(6, len(_en(v)) // 4); i += 1
        got = batch(chunk)
        done.update(got)
        tmp = OUT + ".tmp"
        json.dump(done, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, OUT)
        print(f"  {len(done)}/{len(corpus)} (+{len(got)}/{len(chunk)})")
        if not got:
            time.sleep(3)
    print("vdj_nim: All done!")


if __name__ == "__main__":
    main()
