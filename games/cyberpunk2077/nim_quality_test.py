"""NVIDIA NIM (build.nvidia.com) — Hebrew dual-gender translation QUALITY TEST.

Reads NVIDIA_API_KEY from the repo-root .env (or env), lists available models,
translates a diverse sample of REAL CP2077 lines dual-gender through a few strong
models, validates them with our own gates, and prints a side-by-side vs the
current spine (the Gemini/old translation). No game file is modified.

Usage:
  python games/cyberpunk2077/nim_quality_test.py            # auto-pick models
  python games/cyberpunk2077/nim_quality_test.py --models meta/llama-3.3-70b-instruct,qwen/qwen2.5-72b-instruct
  python games/cyberpunk2077/nim_quality_test.py --n 18     # sample size
"""
import json, os, sys, re, urllib.request, urllib.error, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
QA = os.path.join(HERE, "agent_handoff_qa")
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "universal"))
import get_next_audit_batch as G
import cp2077_markup_translate as mk

BASE = "https://integrate.api.nvidia.com/v1"
NIQ = re.compile(r'[֑-ֽֿׁׂ]')
FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
HEB = re.compile(r'[֐-׿]'); LOWER = re.compile(r'[a-z]{2,}')
YOU = re.compile(r"\b(you|your|you're|you’re|yours|yourself)\b", re.I)
WORD = re.compile(r'[A-Za-z]{2,}')


def load_key():
    k = os.environ.get("NVIDIA_API_KEY", "").strip()
    if k:
        return k
    for envp in (os.path.join(ROOT, ".env"), os.path.join(ROOT, "website", ".env")):
        try:
            for line in open(envp, encoding="utf-8"):
                if line.strip().startswith("NVIDIA_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return ""


def api(key, path, payload=None, method="GET", timeout=120):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json",
                                          "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def list_models(key):
    try:
        d = api(key, "/models")
        return [m["id"] for m in d.get("data", [])]
    except Exception as e:
        print(f"[models] list failed: {e}")
        return []


def pick_models(ids):
    """Pick a few strong translation candidates from the available list."""
    prefs = [
        (r"deepseek.*v3|deepseek.*3\.", 3), (r"deepseek", 2),
        (r"qwen.*(2\.5|3).*(72|122|110|32)b|qwen3", 3), (r"qwen", 1),
        (r"llama-4|llama.*maverick", 3), (r"llama-3\.3-70b|llama-3\.1-405b", 2),
        (r"mistral-large", 2), (r"nemotron.*(70|49|51|super)", 2),
    ]
    scored = {}
    for mid in ids:
        for pat, sc in prefs:
            if re.search(pat, mid, re.I):
                scored[mid] = max(scored.get(mid, 0), sc)
    chosen = sorted(scored, key=lambda m: -scored[m])
    # dedup by family, keep top 4
    fams = set(); out = []
    for m in chosen:
        fam = m.split("/")[-1].split("-")[0]
        if fam in fams:
            continue
        fams.add(fam); out.append(m)
        if len(out) >= 4:
            break
    return out


IMP = re.compile(r"^\s*(go|get|take|come|move|stop|wait|look|listen|give|help|run|drop|hold|keep|find|open|close|follow|leave|stay|watch|shoot|drive|choose|pay|confess|exercise|press|select|use|enter|talk|call|meet|kill|grab|check)\b", re.I)


def is_gender_line(en):
    """A line that SHOULD differ by V-gender: imperative verb, or 'you are/can/will/have'."""
    core = STRUCT.sub(" ", en)
    if IMP.search(core.strip()) and len(WORD.findall(core)) >= 2:
        return True
    if re.search(r"\byou (are|can|will|have|need|must|should|were|did|got|know|want|feel|look)\b", core, re.I):
        return True
    if re.search(r"\byou're\b", core, re.I):
        return True
    return False


def sample_lines(n):
    pool = json.load(open(os.path.join(QA, "_pool", "full_pool.json"), encoding="utf-8"))
    gender, tagged, short, other = [], [], [], []
    for k, en in pool.items():
        if is_gender_line(en) and not STRUCT.search(en):
            gender.append((k, en))
        elif STRUCT.search(en):
            tagged.append((k, en))
        elif len(en) <= 25:
            short.append((k, en))
        else:
            other.append((k, en))
    # weight toward gender-critical lines (that's the real differentiator)
    g = max(6, n // 2)
    pick = gender[:g] + tagged[: n // 4] + short[: n // 6] + other[: n]
    seen = set(); out = []
    for k, en in pick:
        if k in seen:
            continue
        seen.add(k); out.append((k, en))
        if len(out) >= n:
            break
    return out


SYS = ("You are a senior Hebrew game localizer for Cyberpunk 2077. Translate each English "
       "line into natural, fluent Hebrew. In CP2077 the player V can be MALE or FEMALE, so give "
       "TWO Hebrew variants per line: 'f' for a female-V, 'm' for a male-V. For most lines (NPC "
       "speech about others, item/UI text) f and m are IDENTICAL — copy them. They DIFFER only when "
       "the line addresses V or V speaks ('You're ready' -> f='את מוכנה' m='אתה מוכן'). "
       "Keep every tag/placeholder verbatim (<Rich...>, {VALUE...}, %d, &rlm;). No niqqud. Brand names "
       "and the name 'V' stay Latin. Output ONLY a JSON object mapping each id to {\"f\":..,\"m\":..}.")


def translate(key, model, batch):
    user = "Translate these lines. Return JSON {id:{f,m}} only.\n" + json.dumps(
        {k: en for k, en in batch}, ensure_ascii=False, indent=0)
    payload = {"model": model,
               "messages": [{"role": "system", "content": SYS},
                            {"role": "user", "content": user}],
               "temperature": 0.2, "max_tokens": 4000}
    d = api(key, "/chat/completions", payload, method="POST", timeout=240)
    txt = d["choices"][0]["message"]["content"]
    m = re.search(r'\{.*\}', txt, re.S)
    return json.loads(m.group(0)) if m else {}


def check(en, f, m):
    flags = []
    if not f.strip() or not m.strip():
        flags.append("EMPTY")
    if FOREIGN.search(f) or FOREIGN.search(m):
        flags.append("FOREIGN")
    if NIQ.search(f) or NIQ.search(m):
        flags.append("NIQQUD")
    if sorted(STRUCT.findall(en)) != sorted(STRUCT.findall(f)):
        flags.append("STRUCT")
    core = STRUCT.sub(" ", en)
    if LOWER.search(core) and not HEB.search(f):
        flags.append("NO_HEB")
    if mk.parse_slots(f) is None:
        flags.append("PARSE")
    return flags


def spine_lookup(keys):
    spine = json.load(open(G.BASE_TR, encoding="utf-8"))
    idx = {}
    for sec, rows in spine.items():
        if isinstance(rows, list):
            for e in rows:
                if isinstance(e, dict):
                    idx[f"{sec}|{e.get('primaryKey')}"] = (e.get("femaleVariant") or "", e.get("maleVariant") or "")
    return {k: idx.get(k, ("", "")) for k in keys}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="")
    ap.add_argument("--n", type=int, default=18)
    ap.add_argument("--compact", action="store_true")
    a = ap.parse_args()
    key = load_key()
    if not key or not key.startswith("nvapi-"):
        print("❌ אין NVIDIA_API_KEY (שמתחיל ב-nvapi-) ב-.env. הוסף שורה: NVIDIA_API_KEY=nvapi-...")
        return
    print(f"key loaded: {key[:10]}...\n")

    all_ids = list_models(key)
    print(f"available models: {len(all_ids)}")
    models = [x.strip() for x in a.models.split(",") if x.strip()] or pick_models(all_ids)
    print(f"testing models: {models}\n")

    batch = sample_lines(a.n)
    print(f"sample: {len(batch)} lines\n")
    spine = spine_lookup([k for k, _ in batch])

    for model in models:
        print("=" * 78)
        print(f"MODEL: {model}")
        print("=" * 78)
        try:
            res = translate(key, model, batch)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code}: {e.read().decode()[:200]}"); continue
        except Exception as e:
            print(f"  FAILED: {e}"); continue
        ok = 0; genderdiff = 0; gcount = 0; allflags = []; examples = []
        for k, en in batch:
            v = res.get(k) or {}
            f = (v.get("f") or "").strip(); m = (v.get("m") or "").strip()
            flags = check(en, f, m)
            allflags += flags
            if not flags:
                ok += 1
            gl = is_gender_line(en)
            if gl:
                gcount += 1
                if f != m:
                    genderdiff += 1
            gem_f = spine.get(k, ("", ""))[0]
            tag = "".join(f" [{x}]" for x in flags)
            if a.compact:
                if gl and len(examples) < 3:
                    examples.append(f"    EN: {en[:55]}\n    → f={f[:45]}{' | m='+m[:45] if m!=f else '  (זהה!)'}{tag}")
            else:
                print(f"EN : {en[:70]}")
                print(f"NIM: f={f[:55]}{'  | m='+m[:40] if m!=f else '  (f=m)'}{tag}")
                print(f"GEM: {gem_f[:70]}")
                print("-" * 40)
        from collections import Counter
        fc = Counter(allflags)
        badstr = " ".join(f"{x}×{c}" for x, c in fc.items()) or "נקי"
        print(f"  ✅ valid {ok}/{len(batch)} | מבדיל-מגדר {genderdiff}/{gcount} | פגמים: {badstr}")
        if a.compact:
            for e in examples:
                print(e)
        print()


if __name__ == "__main__":
    main()
