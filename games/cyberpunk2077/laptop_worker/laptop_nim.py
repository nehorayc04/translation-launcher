"""Standalone CP2077 dual-gender NIM translator — run on a SECOND machine with a
DIFFERENT IP + a second NVIDIA key, to add a parallel translation stream.

Why it helps: NVIDIA NIM throttles per SOURCE-IP (all keys from one IP share the
limit). A second machine on a different network = an independent quota ≈ doubles
total throughput. Output is {key:{"f":..,"m":..}} — the EXACT shape the main PC's
watchdog banks, so it drops straight into the pipeline.

Stdlib only (no pip). Resumable (skips keys already in out.json). Processes the
corpus longest-first, which the main PC (shortest-first) won't reach for many
hours → the two streams barely overlap.

SETUP ON THE LAPTOP
  1. Install Python 3.10+ from python.org (tick "Add to PATH"). No pip packages.
  2. Put the SECOND NVIDIA key next to this script, EITHER:
        - create a file  key.txt  containing just the key (nvapi-...), OR
        - set an env var:  set NVIDIA_API_KEY=nvapi-xxxx   (Windows CMD)
  3. Run:  python laptop_nim.py
  4. Leave it running. Every so often copy  out.json  back to the main PC — see
     README_LAPTOP.md (drop it as retrans_agent_laptop\retrans_corrections.json).

It loops forever until the corpus is done or you close it. Safe to stop/restart.
"""
import json, os, re, sys, time, urllib.request, urllib.error
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://integrate.api.nvidia.com/v1"
MODEL = "qwen/qwen3-next-80b-a3b-instruct"
SB = 32                                   # lines per request
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, "out.json")

FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;'); LOWER = re.compile(r'[a-z]{2,}')
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$"); _CTRL = "".join(chr(c) for c in range(0x20))

S1 = ("You are a senior Hebrew localizer for Cyberpunk 2077. Translate each English line to natural, fluent Hebrew "
      "(spoken to/by the player, or UI/item text). Keep every tag/placeholder verbatim (<Rich...>, {VALUE...}, %d, "
      "&rlm;). No niqqud. Brand names and the name 'V' stay Latin. Output JSON {id: hebrew} only.")
S2 = ("You are a Hebrew grammar expert. Each item = an English line addressing the player V + a Hebrew translation. "
      "Hebrew verbs/adjectives/2nd-person pronouns agree with the LISTENER's gender. Produce two versions:\n"
      " \"f\" = V FEMALE (את, מוכנה, היכנסי, תוכלי, יודעת, נראית, קחי, בואי)\n"
      " \"m\" = V MALE (אתה, מוכן, היכנס, תוכל, יודע, נראה, קח, בוא)\n"
      "Change ONLY gender-agreement words; keep the rest identical and keep all tags/placeholders. If NO word changes "
      "by gender (שלך, אותך, past עשית, an infinitive, or NPC/3rd-person text), return f and m identical.\n"
      "Examples: EN 'Get in the car.' base 'תיכנס לרכב.' -> {\"f\":\"היכנסי לרכב.\",\"m\":\"היכנס לרכב.\"}; "
      "EN \"You're the best.\" -> {\"f\":\"את הכי טובה.\",\"m\":\"אתה הכי טוב.\"}; "
      "EN 'Take your time.' -> {\"f\":\"קחי את הזמן שלך.\",\"m\":\"קח את הזמן שלך.\"}; "
      "EN 'It's yours.' -> {\"f\":\"זה שלך.\",\"m\":\"זה שלך.\"}.\n"
      "Output JSON {id:{\"f\":..,\"m\":..}} only.")


def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)


def valid(new, en):
    """Light pre-filter. The main PC's watchdog re-validates authoritatively at
    bank time (incl. markup-parse), so this only blocks obvious garbage."""
    if not new or not new.strip(): return False
    if FOREIGN.search(new) or NIQ.search(new): return False
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


def _one_call(key, sysmsg, usermsg, timeout=120):
    payload = {"model": MODEL, "temperature": 0.2, "max_tokens": 6000,
               "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())["choices"][0]["message"]["content"]


def _parse(txt):
    m = re.search(r'\{.*\}', txt, re.S)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    out = {}
    for mm in re.finditer(r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*"|\{[^{}]*\})', txt):
        try: out[mm.group(1)] = json.loads(mm.group(2))
        except Exception: pass
    return out


def chat(sysmsg, usermsg, retries=3):
    last = None
    for _ in range(retries):
        k = _pick_key()
        try:
            r = _parse(_one_call(k, sysmsg, usermsg))
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
    os.replace(tmp, path)


def main():
    keys = load_keys()
    if not keys or not keys[0].startswith("nvapi-"):
        print("❌ No NVIDIA key found. Put it in key.txt (just the nvapi-... line) "
              "or set NVIDIA_API_KEY, then re-run.")
        return
    global _KEYS, _KI
    _KEYS = list(keys); _KI = 0
    if not os.path.exists(CORPUS):
        print(f"❌ corpus.json not found next to this script ({CORPUS}).")
        return
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    print(f"keys={len(_KEYS)} | model={MODEL} | corpus={len(corpus)} lines")

    while True:
        out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
        todo = [(k, corpus[k]) for k in corpus if k not in out]   # longest-first (corpus order)
        if not todo:
            print(f"✅ ALL DONE — {len(out)} lines translated. Copy out.json to the main PC. You can close this.")
            break
        print(f"remaining {len(todo)} | done {len(out)}")
        t0 = time.time(); prod = 0
        for i in range(0, len(todo), SB):
            sub = todo[i:i + SB]
            try:
                s1 = chat(S1, "Translate:\n" + json.dumps({k: en for k, en in sub}, ensure_ascii=False))
            except Exception as e:
                print(f"  step1 fail ({e}) — skipping this sub-batch"); continue
            try:
                p2 = {k: {"en": en, "he": s1.get(k, "")} for k, en in sub if s1.get(k)}
                s2 = chat(S2, "Gender-split:\n" + json.dumps(p2, ensure_ascii=False))
            except Exception:
                s2 = {}
            for k, en in sub:
                f = (s2.get(k, {}).get("f") or s1.get(k, "") or "").strip()
                m = (s2.get(k, {}).get("m") or s1.get(k, "") or "").strip()
                if not f and m: f = m
                if not m and f: m = f
                if valid(f, en) and valid(m, en):
                    out[k] = {"f": f, "m": m}; prod += 1
            atomic(OUT, out)
            print(f"  ...{prod} produced | {int(time.time() - t0)}s | total {len(out)}")


if __name__ == "__main__":
    main()
