"""NIM two-step dual-gender translator for the CP2077 re-translate pool.
Step 1: translate a sub-batch to single Hebrew (model strength).
Step 2: focused gender-split -> {f, m}.
Validates each (struct/foreign/niqqud/hebrew/parse), writes an accumulator
{key:{f,m}} in the SAME shape the agents produce, so it banks with the existing
pipeline. Designed to be looped by a watchdog.

Usage:
  python games/cyberpunk2077/nim_translate.py --n 100 --test          # 100-line real test + Gemini compare
  python games/cyberpunk2077/nim_translate.py --n 2000                # produce 2000 lines
  python games/cyberpunk2077/nim_translate.py --slot 0 --nslots 3     # parallel partition
"""
import json, os, sys, re, time, urllib.request, urllib.error, argparse, hashlib
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
QA = os.path.join(HERE, "agent_handoff_qa"); POOL = os.path.join(QA, "_pool", "full_pool.json")
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import cp2077_markup_translate as mk
import get_next_audit_batch as G

BASE = "https://integrate.api.nvidia.com/v1"
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]'); NIQ = re.compile(r'[֑-ֽֿׁׂ]'); HEB = re.compile(r'[֐-׿]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;'); LOWER = re.compile(r'[a-z]{2,}')
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")  # a token starting uppercase or a digit
_CTRL = "".join(chr(c) for c in range(0x20))     # the spine's leading control-byte prefix


def is_namey(en):
    """A proper-noun / code string (≤4 words, every word Title-case/ALLCAPS/digit,
    no lowercase-initial common word). Used ONLY to accept a model-UNCHANGED Latin
    result so the queue doesn't loop forever on names (Playbook §7)."""
    en = (en or "").strip()
    ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)
SB = 32  # sub-batch size — MORE lines per request = higher throughput at the SAME request rate (per-model limit is on RPM, not lines)

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


def load_keys():
    """All NVIDIA keys, in order. Supports NIM_KEY (single, watchdog-assigned),
    NVIDIA_API_KEYS (comma-separated), and NVIDIA_API_KEY / _KEY2 / _KEY3 ..."""
    forced = os.environ.get("NIM_KEY", "").strip()
    if forced: return [forced]
    keys = []
    raw = os.environ.get("NVIDIA_API_KEYS", "").strip()
    if raw: keys += [k.strip() for k in raw.split(",") if k.strip()]
    for name, v in os.environ.items():
        if name.startswith("NVIDIA_API_KEY") and name != "NVIDIA_API_KEYS":
            v = v.strip()
            if v and v not in keys: keys.append(v)
    if keys: return keys
    for e in (os.path.join(ROOT, ".env"), os.path.join(ROOT, "website", ".env")):
        try:
            for l in open(e, encoding="utf-8"):
                l = l.strip()
                if not l or l.startswith("#") or "=" not in l: continue
                name, _, v = l.partition("="); name = name.strip(); v = v.strip().strip('"').strip("'")
                if name == "NVIDIA_API_KEYS":
                    keys += [k.strip() for k in v.split(",") if k.strip()]
                elif name.startswith("NVIDIA_API_KEY") and v and v not in keys:
                    keys.append(v)
        except OSError: pass
    return keys


def _one_call(key, model, sysmsg, usermsg, timeout):
    payload = {"model": model, "temperature": 0.2, "max_tokens": 6000,
               "messages": [{"role": "system", "content": sysmsg}, {"role": "user", "content": usermsg}]}
    req = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())
    return d["choices"][0]["message"]["content"]


def _parse(txt):
    """Robust JSON extraction: whole-object, else per-line salvage."""
    m = re.search(r'\{.*\}', txt, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # salvage individual  "key": "val"  or  "key": {..}  pairs
    out = {}
    for mm in re.finditer(r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*"|\{[^{}]*\})', txt):
        try:
            out[mm.group(1)] = json.loads(mm.group(2))
        except Exception:
            pass
    return out


# ---- key rotation (spread load across all keys; rest a key on 429) ----
_KEYS = []; _KI = 0; _COOL = {}


def init_keys(keys, start=0):
    global _KEYS, _KI
    _KEYS = list(keys); _KI = start % max(1, len(_KEYS))


def _pick_key():
    """Next key not in cooldown; if all are cooling, wait for the soonest."""
    global _KI
    n = len(_KEYS); now = time.time()
    for _ in range(n):
        k = _KEYS[_KI % n]; _KI = (_KI + 1) % n
        if _COOL.get(k, 0) <= now:
            return k
    k = min(_KEYS, key=lambda x: _COOL.get(x, 0))
    time.sleep(max(0.0, _COOL.get(k, 0) - now) + 0.5)
    return k


# ---- model rotation (each model = a SEPARATE per-model quota; spread the load) ----
_MODELS = []; _MI = 0; _MCOOL = {}


def init_models(models, start=0):
    global _MODELS, _MI
    _MODELS = list(models); _MI = start % max(1, len(_MODELS))


def pick_model():
    """Next model not in cooldown; if all are cooling, wait for the soonest."""
    global _MI
    n = len(_MODELS); now = time.time()
    for _ in range(n):
        m = _MODELS[_MI % n]; _MI = (_MI + 1) % n
        if _MCOOL.get(m, 0) <= now:
            return m
    m = min(_MODELS, key=lambda x: _MCOOL.get(x, 0))
    time.sleep(max(0.0, _MCOOL.get(m, 0) - now) + 0.5)
    return m


def chat(model, sysmsg, usermsg, timeout=180, retries=3):
    """Rotate keys per attempt. On 429, rest THAT key ~90s and try the next
    one immediately. Few retries + a caller-side escalating idle sleep keep the
    source IP gentle during a rate-limit penalty window (NVIDIA throttles per
    source-IP, so all keys share it — don't hammer)."""
    last = None
    for att in range(retries):
        k = _pick_key()
        try:
            r = _parse(_one_call(k, model, sysmsg, usermsg, timeout))
            if r:
                return r
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                _COOL[k] = time.time() + 90     # rest this key, rotate on
                continue
            time.sleep(2)
        except Exception as e:
            last = e
            time.sleep(2)
    if last:
        raise last
    return {}


def valid(new, en):
    if not new or not new.strip() or mk.parse_slots(new) is None: return False
    if FOREIGN.search(new) or NIQ.search(new): return False
    if sorted(STRUCT.findall(new)) != sorted(STRUCT.findall(en)): return False
    core = STRUCT.sub(" ", en)
    bare = new.lstrip(_CTRL).strip()   # drop the spine's leading control prefix before identity checks
    if LOWER.search(core) and not HEB.search(new):
        if not (bare == en.strip() and is_namey(en)): return False  # name/code passthrough
    if len(en) >= 12 and bare == en.strip() and not is_namey(en): return False
    return True


def jload(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def atomic(path, obj):
    tmp = path + ".tmp"; json.dump(obj, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen/qwen3-next-80b-a3b-instruct")
    ap.add_argument("--models", default="")   # comma list to ROTATE (each = separate per-model quota); else uses --model
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--slot", type=int, default=-1); ap.add_argument("--nslots", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(QA, "_pool", "nim_out.json"))
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--minlen", type=int, default=0)
    ap.add_argument("--base-only", action="store_true")
    ap.add_argument("--loop", action="store_true")
    a = ap.parse_args()
    keys = load_keys()
    if not keys or not keys[0].startswith("nvapi-"): print("❌ אין NVIDIA_API_KEY ב-.env"); return
    init_keys(keys, start=max(0, a.slot))     # rotate all keys; offset start per slot
    models = [m.strip() for m in a.models.split(",") if m.strip()] or [a.model]
    init_models(models, start=max(0, a.slot))  # rotate models; offset start per slot so slots don't collide
    print(f"מפתחות ברוטציה: {len(keys)} | מודלים ברוטציה: {len(models)} | פרוסה {a.slot}/{a.nslots}")

    ckpt_path = os.path.join(ROOT, "universal", "opus_qa_checkpoint.json")
    idle = 0
    while True:
        did = run_once(a, ckpt_path)
        if not a.loop:
            break
        if did == 0:
            idle += 1
            nap = min(60 * (2 ** min(idle, 4)), 900)   # 120,240,480,900,900 — near-silent during a block so a sliding-window IP penalty can clear
            print(f"  (0 השורות — נמנום {nap}s | סבב ריק {idle})")
            time.sleep(nap)
        else:
            idle = 0


def run_once(a, ckpt_path):
    pool = jload(POOL, {})
    reviewed = set(jload(os.path.join(ROOT, "universal", "opus_qa_checkpoint.json"), {}).get("reviewed", []))
    out = jload(a.out, {})
    done = set(out.keys())
    # park (§7): a key that fails valid() 3× (a name the model didn't keep
    # identical, a partial JSON, etc.) is skipped so it can't loop the queue
    # forever and starve the bulk. Per-slot files → no cross-process race; the
    # spine/checkpoint are NEVER touched (a parked key keeps its current value).
    skip_p = a.out + ".skip.json"; strikes_p = a.out + ".strikes.json"
    skip = set(jload(skip_p, [])); strikes = jload(strikes_p, {})
    base_keys = set()
    if a.base_only or a.test:
        sp = jload(G.BASE_TR, {})
        for sec, rows in sp.items():
            if isinstance(rows, list):
                for e in rows:
                    if isinstance(e, dict): base_keys.add(f"{sec}|{e.get('primaryKey')}")
    todo = []
    for k, en in pool.items():
        if k in reviewed or k in done or k in skip: continue
        if a.minlen and len(en) < a.minlen: continue
        if a.base_only and k not in base_keys: continue
        if a.slot >= 0 and int(hashlib.md5(k.encode()).hexdigest(), 16) % a.nslots != a.slot: continue
        todo.append((k, en))
    todo.sort(key=lambda x: len(x[1]))
    todo = todo[:a.n]
    print(f"model={a.model} | לתרגם עכשיו: {len(todo)} (out קיים: {len(done)})")

    t0 = time.time(); produced = 0; rej = 0; attempted = []
    for i in range(0, len(todo), SB):
        sub = todo[i:i + SB]
        model = pick_model()                    # rotate models — each has its own per-model quota
        try:
            s1 = chat(model, S1, "Translate:\n" + json.dumps({k: en for k, en in sub}, ensure_ascii=False))
        except Exception as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                _MCOOL[model] = time.time() + 30   # this MODEL is throttled — rest it, next sub-batch uses another
            print(f"  [sub {i//SB}] step1 ({model.split('/')[-1]}) נכשל: {e}"); continue
        try:
            p2 = {k: {"en": en, "he": s1.get(k, "")} for k, en in sub if s1.get(k)}
            s2 = chat(model, S2, "Gender-split:\n" + json.dumps(p2, ensure_ascii=False))
        except Exception as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                _MCOOL[model] = time.time() + 30
            print(f"  [sub {i//SB}] step2 ({model.split('/')[-1]}) -> נפילה ל-step1 (f=m): {e}"); s2 = {}
        for k, en in sub:
            attempted.append(k)               # step1 responded → this key was really tried
            f = (s2.get(k, {}).get("f") or s1.get(k, "") or "").strip()
            m = (s2.get(k, {}).get("m") or s1.get(k, "") or "").strip()
            if not f and m: f = m
            if not m and f: m = f
            if valid(f, en) and valid(m, en):
                out[k] = {"f": f, "m": m}; produced += 1
            else:
                rej += 1
        atomic(a.out, out)
        print(f"  ...{produced} תורגמו ({rej} נדחו) | {int(time.time()-t0)}s")

    # strike/park bookkeeping: a tried key that produced nothing gets a strike;
    # 3 strikes → parked to the skip file (leaves the queue, spine untouched).
    parked = 0
    for k in attempted:
        if k in out:
            strikes.pop(k, None)
        else:
            strikes[k] = strikes.get(k, 0) + 1
            if strikes[k] >= 3: skip.add(k); strikes.pop(k, None); parked += 1
    atomic(skip_p, sorted(skip)); atomic(strikes_p, strikes)
    if parked: print(f"  🅿 נחנו {parked} מפתחות עקשניים (סה\"כ skip: {len(skip)})")

    dt = time.time() - t0
    rate = produced / dt * 3600 if dt else 0
    print(f"\n✅ הופקו {produced} | נדחו {rej} | {int(dt)}s | ~{int(rate)}/שעה")

    if a.test:
        spine = json.load(open(G.BASE_TR, encoding="utf-8"))
        idx = {}
        for sec, rows in spine.items():
            if isinstance(rows, list):
                for e in rows:
                    if isinstance(e, dict): idx[f"{sec}|{e.get('primaryKey')}"] = (e.get("femaleVariant") or "")
        gdiff = 0; shown = 0
        print("\n===== השוואה מול Gemini (מדגם) =====")
        for k, en in todo:
            if k not in out: continue
            f = out[k]["f"]; m = out[k]["m"]
            if f != m: gdiff += 1
            if shown < 25:
                gem = idx.get(k, "")
                print(f"EN : {en[:60]}")
                print(f"NIM: f={f[:48]}{'  | m='+m[:40] if m!=f else '  (f=m)'}")
                print(f"GEM: {gem[:60]}\n")
                shown += 1
        print(f"מבדיל-מגדר: {gdiff}/{produced}")
    return produced


if __name__ == "__main__":
    main()
