"""007 First Light translator worker — New-Era, five-language panel.

Same proven shape as crimson_desert/fleet/cd_nim.py (PANEL grammar-oracle prompt, strike/park,
atomic writes, PID+cmdline singleton) retargeted at this game:

  * game = 007 First Light (2026, IO Interactive) — a young-Bond MI6-origin spy thriller.
    Register: contemporary, terse, dry British wit where the source has it; never archaic,
    never slang-heavy. UI/menu text stays terse and functional, like a real game HUD.

  * the panel is ru/es/fr/it/pt — full 100% key-parity coverage (measured, extract_gender_context.py).
    Read grammar off them; NEVER translate from them — `en` is the meaning.

  * `addressee_gender`/`speaker_gender` are DETERMINISTIC, derived from the game's own Russian
    by universal/gender_oracle.py (ru_addressee/ru_speaker, a CLOSED set) at corpus-build time
    (build_corpus.py) — not guessed here.

  * the glossary is `fleet/name_registry.json` (characters/places/factions/systems/gear/
    keep_latin, web-verified where a Bond-canon Hebrew form already exists) — injected PER
    BATCH, only the terms that occur, and re-applied at merge so a later correction costs no
    re-translation.

  * tokens preserved VERBATIM (measured on the real corpus, see extract/report.txt sample scan):
    `<br/>`/`<br>`/`<b></b>`/`<u></u>`/`<li></li>` HTML-ish tags, `{0}`/`{1}` positional
    placeholders, `{ES_...}`/`{ES_.../NoGesture}` input-binding tokens, and short bracketed
    voice-direction cues (`[Laughs]`, `[sigh]`, `[Screams]`...).

  * IRON RULE: the plain hyphen `-`, never a long dash.

Run: python fl_nim.py <groq|sambanova|nim>   (keys in keys.json next to this file — same file
the crimson_desert fleet uses; copy it here per machine, or point KEYS_FROM at it)
"""
import json, os, re, sys, time, threading, urllib.request, urllib.error, ssl
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import certifi
    _SSLCTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _SSLCTX = ssl._create_unverified_context()

HERE = os.path.dirname(os.path.abspath(__file__))
_PORDER = ["groq", "sambanova", "nim"]
_PROV = (sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in _PORDER
         else os.environ.get("FLEET_PROVIDER", "")).strip().lower()
_SUF = f"_{_PROV}" if _PROV in _PORDER else ""
_PIDX = _PORDER.index(_PROV) if _PROV in _PORDER else -1
BASE = "https://integrate.api.nvidia.com/v1"
MODEL = "meta/llama-3.1-70b-instruct"
BUDGET = 1600
CORPUS = os.path.join(HERE, "corpus.json")
OUT = os.path.join(HERE, f"out{_SUF}.json")

_FLEET = None
try:
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(HERE, "..", "..", "crimson_desert", "fleet"))
    import fleet_providers as _fp
    _FLEET = _fp.Fleet(_fp.load_keys(HERE), only=(_PROV if _PIDX >= 0 else None))
    print(f"[fleet] {'PINNED ' + _PROV if _PIDX >= 0 else 'round-robin'}: "
          f"{_FLEET.provider_names()} -> {os.path.basename(OUT)}", flush=True)
except Exception as _e:
    print("[fleet] single-NIM fallback:", _e, flush=True)

PANEL = ("ru", "es", "fr", "it", "pt")

FOREIGN = re.compile("[Ѐ-ӿͰ-Ͽ؀-ۿݐ-ݿ"
                     "぀-ヿ一-鿿가-힯]")
NIQ = re.compile("[֑-ׇֽֿׁׂ]")
HEB = re.compile("[א-ת]")
# Measured on locr_en.json + dlge_en.json (see extract/report.txt scan): HTML-ish tags,
# {0}/{1} placeholders, {ES_...}/{ES_.../NoGesture} input-binding tokens, and short bracketed
# voice-direction cues ([Laughs], [sigh], [Screams], [Chuckles], [inhales]...) — letters+spaces
# only, no digits, so a real prose bracket (rare in this corpus) will not falsely match.
STRUCT = re.compile(r"<[^<>]{1,60}>|\{[^{}]{0,80}\}|\[[A-Za-z][A-Za-z ]{0,24}\]")
SEAM = re.compile(r"[א-ת][A-Za-z]|[A-Za-z][א-ת]")
LOWER = re.compile(r"[a-z]{2,}")
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'’/®™©]*$")
_CTRL = "".join(chr(c) for c in range(0x20))
_DASHES = str.maketrans({c: "-" for c in
                         "‐‑‒–—―−"
                         "⸺⸻﹘﹣－"})
_PREFIX_HYPHEN = re.compile("(?<![א-ת])([ובלמהשכ])"
                            "-(?=[א-ת])")

S1 = ("You are a senior Hebrew localizer for 007 First Light - a young-James-Bond MI6 origin "
      "story: spy tradecraft, gadgets, infiltration, dry British wit. Recurring names include "
      "Bond, M, Q, Moneypenny, Greenway, Monroe, Cressida, Isola, Damien, First Light Services, "
      "Webb Industries, MI6. Write natural, fluent, contemporary Hebrew with a dry, controlled "
      "espionage-thriller voice - never archaic, never slang-heavy. Keep each speaker's voice. "
      "UI labels, item names, tooltips and objectives stay terse and functional, like a real "
      "game HUD - short imperative phrases, not full sentences. "
      "Each input line gives 'en' = the English MEANING to translate, plus the SAME line as the "
      "game's own professional translators shipped it: 'ru' 'es' 'fr' 'it' 'pt'. Translate the "
      "MEANING from 'en'. Use the other languages ONLY as the grammar oracle, because English "
      "hides what Hebrew must state: ru marks the SPEAKER's and the ADDRESSEE's gender and "
      "NUMBER (a plural there means address a GROUP - atem and plural verbs), es/fr/it/pt mark "
      "the referent's gender. Follow them: a woman gets את and feminine verbs, a man אתה, a "
      "group אתם. Do NOT translate from those languages and NEVER copy a foreign word - "
      "Cyrillic, Greek or CJK characters in your output are always a bug. "
      "'addressee_gender'/'speaker_gender' when present are DETERMINISTIC facts read off the "
      "game's own Russian - obey them over your own reading. "
      "ADDRESS THE PLAYER (Bond) IN MASCULINE SINGULAR by default, consistently: an objective, "
      "a tooltip or a menu instruction is בצע / השג / עבור / דבר - never a plural verb. Only "
      "address a GROUP with אתם when the line really is spoken to several people (ru will show "
      "a plural there). "
      "Never put a hyphen between a Hebrew prefix and a Hebrew word: write בשבעת הימים, not "
      "ב-שבעת הימים. A hyphen after a prefix is only for Latin or digits (ל-NPC, ב-2024). "
      "Keep every token VERBATIM from the English, same count and same position: HTML-ish tags "
      "(<br/> <b> </b> <u> </u> <li> </li>), the {..} placeholders (including {0}, {ES_...}, "
      "{ES_.../NoGesture} input-binding tokens - these name a controller/keyboard button, "
      "NEVER translate the text inside {}), and short bracketed voice-direction cues like "
      "[Laughs] [sigh] [Screams] - copy them EXACTLY, letter-for-letter, never translate the "
      "word inside the brackets. "
      "Use the plain hyphen '-'. Never use a long dash. No niqqud. "
      "Proper names use their accepted Hebrew form from the glossary when given; a name not in "
      "the glossary gets a natural Hebrew phonetic transliteration. Brand/code tokens (MI6, "
      "Q-Lens, TacSim) stay Latin unless the glossary gives a Hebrew form. "
      "If a line is an ALL-CAPS code, a file path, an EULA/legal-boilerplate clause, or "
      "unreadable gibberish, still translate it faithfully into formal Hebrew (legal text is "
      "real content here, not a token) - only actual code/paths stay unchanged. "
      "Output JSON {id: hebrew} only, with exactly the same ids as the input.")


def _en(v):
    return v.get("en", "") if isinstance(v, dict) else (v or "")


def is_namey(en):
    en = (en or "").strip(); ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)


def normalize(s, en=""):
    s = NIQ.sub("", s).translate(_DASHES)
    return _PREFIX_HYPHEN.sub(r"\1", s).strip()


def why_invalid(new, en, v=None):
    if not new or not new.strip(): return "empty"
    if FOREIGN.search(new): return "foreign-script"
    if NIQ.search(new): return "niqqud"
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)):
        return f"token-mismatch {sorted(STRUCT.findall(en))} -> {sorted(STRUCT.findall(new))}"
    if en.count("\n") != new.count("\n"):
        return f"newline-count {en.count(chr(10))} -> {new.count(chr(10))}"
    s = SEAM.search(new)
    if s:
        return f"hebrew-latin-seam '{s.group(0)}'"
    core = STRUCT.sub(" ", en); bare = new.lstrip(_CTRL).strip()
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return "no-hebrew"
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return "copy-EN"
    p = plural_conflict(new, en)
    if p: return p
    g = gender_conflict(new, v)
    if g: return g
    return ""


def valid(new, en, v=None):
    return not why_invalid(new, en, v)


# ── canonical glossary — from fleet/name_registry.json ────────────────────────────────────
_GLOSS = {}
_RULES = []
try:
    _reg = json.load(open(os.path.join(HERE, "name_registry.json"), encoding="utf-8"))
    for _section in ("characters", "places", "factions", "systems", "gear"):
        for _en_term, _he_term in (_reg.get(_section) or {}).items():
            if _en_term and _he_term:
                _GLOSS[_en_term] = _he_term
    print(f"[glossary] {len(_GLOSS)} terms from name_registry.json", flush=True)
except Exception as _e:
    print("[glossary] none:", _e, flush=True)
_GLOSS_ORDER = sorted(_GLOSS, key=len, reverse=True)


def glossary_for(batch):
    hay = " ".join(_en(v) for _k, v in batch)
    hit, seen = [], set()
    for t in _GLOSS_ORDER:
        if t in hay and not any(t in s for s in seen):
            hit.append(f"{t} = {_GLOSS[t]}"); seen.add(t)
        if len(hit) >= 20: break
    return hit


# ── gender guard — same closed-set Hebrew-side check as cd_nim.py ─────────────────────────
_HE_PL = re.compile("(?<![א-ת])את[םן](?![א-ת])")
_HE_M = re.compile("(?<![א-ת])אתה(?![א-ת])")
_HE_F = re.compile("(?<![א-ת])את(?![א-ת])")
_HE_VF = re.compile("(?<![א-ת])(?:"
                    "צריכה|יכולה|"
                    "יודעת|מוכנה|"
                    "חייבת|תוכלי|"
                    "בואי|קחי|תעשי|"
                    "לכי|בטוחה|מבינה|"
                    "שומעת|תגידי|"
                    "רוצה|עושה|"
                    "הולכת|נראית"
                    ")(?![א-ת])")


def he_addressee(t):
    if not t: return None
    if _HE_PL.search(t): return "pl"
    if _HE_M.search(t): return "m"
    if _HE_F.search(t) and _HE_VF.search(t): return "f"
    if _HE_VF.search(t): return "f"
    return None


PLURAL = re.compile(r"\|plural\(([^)]*)\)")


def _plural_cases(clause):
    out = {}
    for part in clause.split(","):
        part = part.strip()
        if "=" in part:
            k, _, val = part.partition("=")
            out[k.strip()] = val.strip()
    return out


def plural_conflict(new, en):
    en_cl, he_cl = PLURAL.findall(en), PLURAL.findall(new)
    if len(en_cl) != len(he_cl):
        return f"plural-clause-count {len(en_cl)} -> {len(he_cl)}"
    for e, h in zip(en_cl, he_cl):
        ec, hc = _plural_cases(e), _plural_cases(h)
        if set(ec) != set(hc):
            return f"plural-case-names {sorted(ec)} -> {sorted(hc)}"
        for k, ev in ec.items():
            if ev.strip() and not hc.get(k, "").strip():
                return f"plural-empty-branch [{k}]"
    return ""


def gender_conflict(new, v):
    a = (v or {}).get("ag") if isinstance(v, dict) else None
    if not a: return ""
    h = he_addressee(new)
    if not h or h == a: return ""
    return f"gender {h} vs devkit {a}"


def load_keys():
    keys = []
    raw = os.environ.get("NVIDIA_API_KEYS", "").strip()
    if raw: keys += [k.strip() for k in raw.split(",") if k.strip()]
    v = os.environ.get("NVIDIA_API_KEY", "").strip()
    if v and v not in keys: keys.append(v)
    kj = os.path.join(HERE, "keys.json")
    if os.path.exists(kj):
        try:
            d = json.load(open(kj, encoding="utf-8"))
            if d.get("nim") and d["nim"] not in keys: keys.append(str(d["nim"]).strip())
        except Exception:
            pass
    for kt in (os.path.join(HERE, "key.txt"),):
        if os.path.exists(kt):
            for l in open(kt, encoding="utf-8"):
                l = l.strip()
                if l.startswith("nvapi-") and l not in keys: keys.append(l)
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


def _one_call_blocking(key, sysmsg, usermsg, timeout=180, max_tokens=2500):
    payload = {"model": MODEL, "temperature": 0.2, "max_tokens": max_tokens,
               "messages": [{"role": "system", "content": sysmsg},
                            {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload).encode(),
                                 method="POST",
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout, context=_SSLCTX).read()
                      .decode())["choices"][0]["message"]["content"]


def _one_call(key, sysmsg, usermsg, timeout=180, max_tokens=2500):
    box = {}

    def _run():
        try:
            box["ok"] = _one_call_blocking(key, sysmsg, usermsg, timeout, max_tokens)
        except Exception as e:
            box["err"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout + 15)
    if t.is_alive():
        raise TimeoutError(f"hard wall-clock timeout ({timeout + 15}s) - likely a stuck DNS lookup")
    if "err" in box:
        raise box["err"]
    return box["ok"]


# A model that ignores "the KEYS are the ids" and instead emits an ARRAY of
# {"id": "...", "he": "..."} objects — measured live on nim: our corpus keys look like
# "en:<md5>", and it silently drops the "en:" prefix too, treating the colon as if it
# started a value. The generic flat "key": "value" scanner below would then collapse
# every entry down to the SAME two literal keys ("id"/"he", each overwritten by the last
# line in the batch) -> every real corpus key resolves to None -> silent 0/N forever,
# no exception, no REJECT print (do_batch never even sees a candidate to reject).
_ID_HE_ITEM = re.compile(
    r'"id"\s*:\s*"([^"]*)"\s*,\s*"he"\s*:\s*("(?:[^"\\]|\\.)*")'
    r'|"he"\s*:\s*("(?:[^"\\]|\\.)*")\s*,\s*"id"\s*:\s*"([^"]*)"')


def _parse(txt):
    m = re.search(r"\{.*\}", txt, re.S)
    if m:
        try: return json.loads(m.group(0))
        except Exception: pass
    id_he = {}
    for mm in _ID_HE_ITEM.finditer(txt):
        if mm.group(1) is not None:
            try: id_he[mm.group(1)] = json.loads(mm.group(2))
            except Exception: pass
        else:
            try: id_he[mm.group(4)] = json.loads(mm.group(3))
            except Exception: pass
    if id_he:
        return id_he
    out = {}
    for mm in re.finditer(r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*")', txt):
        try: out[mm.group(1)] = json.loads(mm.group(2))
        except Exception: pass
    return out


def chat(sysmsg, usermsg, retries=3, timeout=180, max_tokens=2500):
    if _FLEET is not None:
        err = None
        try:
            r = _parse(_FLEET.complete(sysmsg, usermsg, retries=max(retries, 4),
                                       timeout=timeout, max_tokens=max_tokens))
            if r:
                return r
        except Exception as e:
            err = e
        if _PROV:
            if err:
                raise err
            return {}
    if not _KEYS:
        return {}
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
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    for i in range(20):
        try:
            os.replace(tmp, path); return
        except PermissionError:
            time.sleep(0.3 + i * 0.1)
    try:
        os.replace(tmp, path)
    except PermissionError:
        try: os.remove(tmp)
        except OSError: pass


def _payload(v):
    if not isinstance(v, dict): return {"en": v or ""}
    p = {"en": v.get("en", "")}
    if v.get("ctx"): p["ctx"] = v["ctx"]
    _G = {"m": "male", "f": "female", "pl": "plural"}
    if v.get("ag") in _G: p["addressee_gender"] = _G[v["ag"]]
    if v.get("sg") in _G: p["speaker_gender"] = _G[v["sg"]]
    for L in PANEL:
        if v.get(L): p[L] = v[L]
    return p


def _tok(v):
    p = _payload(v)
    return sum(len(str(x)) for x in p.values()) // 3 + 10


MAXLINES = {"groq": 20, "sambanova": 14, "nim": 10}.get(_PROV, 16)


def make_batches(todo):
    batches, cur, ct = [], [], 0
    for k, v in todo:
        t = _tok(v)
        if cur and (ct + t > BUDGET or len(cur) >= MAXLINES):
            batches.append(cur); cur, ct = [], 0
        cur.append((k, v)); ct += t
        if ct >= BUDGET or len(cur) >= MAXLINES:
            batches.append(cur); cur, ct = [], 0
    if cur: batches.append(cur)
    return batches


def do_batch(sub):
    to = min(150, 75 + sum(_tok(v) for _, v in sub) // 10)
    mx = min(4000, 1000
             + sum(len(k) for k, _ in sub) // 2
             + sum(len(_en(v)) for _, v in sub) * 2)
    gl = glossary_for(sub)
    sysmsg = S1 + ("\nGame rules:\n" + "\n".join(_RULES) if _RULES else "")
    msg = "Translate:\n" + json.dumps({k: _payload(v) for k, v in sub}, ensure_ascii=False)
    if gl:
        msg = ("Canonical Hebrew for the names in this batch — use EXACTLY these:\n"
               + "\n".join(gl) + "\n\n" + msg)
    try:
        s1 = chat(sysmsg, msg, timeout=to, max_tokens=mx)
    except Exception as e:
        print(f"  step1 fail ({e}) — skip batch"); return {}, False, set()
    res, seen = {}, set()
    for k, v in sub:
        he = s1.get(k)
        # our keys are "en:<md5>" — a model that dropped the "en:" prefix (see _ID_HE_ITEM
        # in _parse) still resolves here, keyed by the bare hash it actually returned.
        if he is None and ":" in k:
            he = s1.get(k.split(":", 1)[1])
        if isinstance(he, dict):
            he = he.get("he") or he.get("hebrew") or he.get("text") or he.get("translation") or ""
        if not isinstance(he, str): continue
        he = normalize(he, _en(v))
        if not he: continue
        seen.add(k)
        bad = why_invalid(he, _en(v), v)
        if not bad:
            res[k] = he
        elif len(sub) == 1:
            print(f"    REJECT {k} [{bad}] en={_en(v)[:60]!r} he={he[:60]!r}", flush=True)
    return res, True, seen


LOCK = os.path.join(HERE, f"worker{_SUF}.lock")


def _alive(pid):
    try:
        if os.name == "nt":
            import subprocess
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter \"ProcessId={int(pid)}\").CommandLine"],
                capture_output=True, text=True, timeout=20).stdout
            return "fl_worker" in (out or "")
        os.kill(pid, 0); return True
    except Exception:
        return False


def acquire_singleton():
    if os.path.exists(LOCK):
        try:
            pid = int(open(LOCK).read().strip() or 0)
        except Exception:
            pid = 0
        if pid and pid != os.getpid() and _alive(pid):
            print(f"another worker is already running (pid {pid}) — exiting."); return False
    try:
        open(LOCK, "w").write(str(os.getpid()))
    except Exception:
        pass
    return True


if __name__ == "__main__":
    print("fl_nim.py is a library module for cc_worker.py / a future fl_worker.py — "
          "it has no standalone main() (pool-mode only, like cd_nim + cc_worker.py).")
