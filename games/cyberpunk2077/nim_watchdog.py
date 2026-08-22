"""NIM translation supervisor — runs N parallel GLM streams over the CP2077
re-translate pool and banks their output to the spine periodically.

Race-free: each stream writes ONLY its own nim_out_<slot>.json; the watchdog
only READS those + writes the spine + checkpoint. A banked key enters the
checkpoint, so streams skip it (no re-translate) and the watchdog skips it
(no re-bank).

Run under BASE python (not the venv stub), hidden:
  Start-Process ...Python313\python.exe -ArgumentList '-u','games\cyberpunk2077\nim_watchdog.py' -WindowStyle Hidden
Args: --slots 3 --model z-ai/glm-5.2 --chunk 60
Status: python games/cyberpunk2077/nim_watchdog.py --status
"""
import json, os, sys, re, time, subprocess, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
UNIV = os.path.join(ROOT, "universal"); QA = os.path.join(HERE, "agent_handoff_qa")
POOL = os.path.join(QA, "_pool", "full_pool.json"); OUTDIR = os.path.join(QA, "_pool")
CKPT = os.path.join(UNIV, "opus_qa_checkpoint.json"); DLC = os.path.join(ROOT, "תרגום_משחקים", "source", "resources", "dlc_ep1_translated.json")
LOCK = os.path.join(OUTDIR, "nim_watchdog.lock"); LOG = "c:/tmp/nim_watchdog.log"
sys.path.insert(0, os.path.join(QA, "retrans_agent_1")); sys.path.insert(0, HERE); sys.path.insert(0, UNIV)
import cp2077_markup_translate as mk
import get_next_audit_batch as G

NIQ = re.compile(r'[֑-ֽֿׁׂ]'); FOREIGN = re.compile(r'[؀-ۿ぀-ヿ一-鿿가-힣Ѐ-ӿ]')
STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%%|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
HEB = re.compile(r'[֐-׿]'); LOWER = re.compile(r'[a-z]{2,}')
_NAMEWORD = re.compile(r"^[A-Z0-9][\w.\-'/]*$")  # a token starting uppercase or a digit
_CTRL = "".join(chr(c) for c in range(0x20))     # the spine's leading control-byte prefix
BANK_EVERY = 240  # seconds


def is_namey(en):
    """Proper-noun / code (≤4 words, every word Title/ALLCAPS/digit). Accept a
    model-UNCHANGED Latin result for these so names don't loop forever (§7)."""
    en = (en or "").strip(); ws = en.split()
    return bool(ws) and len(ws) <= 4 and all(_NAMEWORD.match(w) for w in ws)


def jl(p, d):
    try: return json.load(open(p, encoding="utf-8"))
    except Exception: return d


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    try:
        open(LOG, "a", encoding="utf-8").write(line + "\n")
    except OSError:
        pass


def ctrl(s):
    i = 0
    while i < len(s) and ord(s[i]) < 0x20: i += 1
    return s[:i]


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


def out_files(slots):
    return [os.path.join(OUTDIR, f"nim_out_{i}.json") for i in range(slots)]


def agent_corr_files():
    import glob as _g
    return sorted(_g.glob(os.path.join(QA, "retrans_agent_*", "retrans_corrections.json")))


def collect(slots):
    merged = {}
    for p in out_files(slots) + agent_corr_files():
        for k, v in jl(p, {}).items():
            if isinstance(v, dict) and "f" in v and "m" in v:
                merged[k] = v
    return merged


def bank(slots):
    pool = jl(POOL, {}); ck = jl(CKPT, {}); reviewed = set(ck.get("reviewed", []))
    merged = collect(slots)
    # ---- BASE ----
    spine = jl(G.BASE_TR, {}); cur = {}
    for sec, rows in spine.items():
        if isinstance(rows, list):
            for e in rows:
                if isinstance(e, dict): cur[(sec, str(e.get("primaryKey")))] = (e.get("femaleVariant") or "", e.get("maleVariant") or "")
    out = []; bk = []
    for k, v in merged.items():
        if k in reviewed or k.startswith("ep1/"): continue
        sec, _, pk = k.rpartition("|"); en = pool.get(k, ""); c = cur.get((sec, pk))
        if c is None: continue
        cfv, cmv = c; pfx = ctrl(cfv) or ctrl(cmv)
        nf = pfx + (v.get("f") or "").strip(); nm = pfx + (v.get("m") or "").strip()
        if valid(nf, en) and valid(nm, en):
            out.append({"sec": sec, "pk": pk, "field": "femaleVariant", "old": cfv, "new": nf})
            out.append({"sec": sec, "pk": pk, "field": "maleVariant", "old": cmv, "new": nm}); bk.append(k)
    base = 0
    if out:
        open(os.path.join(UNIV, "opus_qa_fixes.jsonl"), "w", encoding="utf-8").write(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n")
        r = subprocess.run([sys.executable, os.path.join(HERE, "qa_review_apply.py")], capture_output=True, text=True, encoding="utf-8")
        base = len(bk)
    # ---- DLC ----
    dd = jl(DLC, {}); idx = {}
    for sec, rows in dd.items():
        if isinstance(rows, list):
            idx.setdefault(sec, {})
            for e in rows:
                if isinstance(e, dict): idx[sec][str(e.get("primaryKey"))] = e
    ONS = ("ep1/onscreens/onscreens.json", "ep1/onscreens/onscreens_final.json"); dbk = []; da = 0
    for k, v in merged.items():
        if not k.startswith("ep1/") or k in reviewed: continue
        sec, _, pk = k.rpartition("|"); en = pool.get(k, ""); e = idx.get(sec, {}).get(pk)
        if not e: continue
        cfv = e.get("femaleVariant") or ""; cmv = e.get("maleVariant") or ""; pfx = ctrl(cfv) or ctrl(cmv)
        nf = pfx + (v.get("f") or "").strip(); nm = pfx + (v.get("m") or "").strip()
        if not (valid(nf, en) and valid(nm, en)): continue
        e["femaleVariant"] = nf; e["maleVariant"] = nm; da += 1; dbk.append(k)
        if sec in ONS:
            o = ONS[1] if sec == ONS[0] else ONS[0]; oe = idx.get(o, {}).get(pk)
            if oe and (oe.get("femaleVariant") or "") == cfv: oe["femaleVariant"] = nf; oe["maleVariant"] = nm; dbk.append(f"{o}|{pk}")
    if da:
        stamp = time.strftime("%Y%m%d_%H%M%S"); import shutil; shutil.copy2(DLC, f"{DLC}.bak.opusqa.{stamp}")
        tmp = DLC + ".tmp"; json.dump(dd, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, DLC)
    reviewed.update(bk); reviewed.update(dbk); ck["reviewed"] = sorted(reviewed)
    tmp = CKPT + ".tmp"; json.dump(ck, open(tmp, "w", encoding="utf-8"), ensure_ascii=False); os.replace(tmp, CKPT)
    banked_pool = sum(1 for k in pool if k in reviewed)
    return base, da, banked_pool, len(pool)


def load_keys():
    forced = os.environ.get("NVIDIA_API_KEYS", "").strip()
    keys = [k.strip() for k in forced.split(",") if k.strip()] if forced else []
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


def probe_keys(keys, model):
    """One tiny call per key; return the keys that are NOT currently 429'd."""
    import urllib.request, urllib.error
    ok = []
    for k in keys:
        p = {"model": model, "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]}
        r = urllib.request.Request("https://integrate.api.nvidia.com/v1/chat/completions",
                                   data=json.dumps(p).encode(), method="POST",
                                   headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(r, timeout=30).read(); ok.append(k)
        except Exception:
            pass
    return ok


def launch(slot, slots, models, keyarg, pin):
    out = os.path.join(OUTDIR, f"nim_out_{slot}.json")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if pin:                                    # one dedicated key per slot (per-account stream)
        env["NIM_KEY"] = keyarg
    else:                                      # rotate all keys within the slot
        env["NVIDIA_API_KEYS"] = keyarg; env.pop("NIM_KEY", None)
    return subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "nim_translate.py"),
                             "--loop", "--slot", str(slot), "--nslots", str(slots),
                             "--models", models, "--n", "60", "--out", out],
                            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def status(slots):
    merged = collect(slots); ck = jl(CKPT, {}); reviewed = set(ck.get("reviewed", []))
    pool = jl(POOL, {}); bp = sum(1 for k in pool if k in reviewed)
    print(f"NIM out (לא-בוונק+בוונק): {len(merged)} | בוקן מהמאגר: {bp}/{len(pool)} ({100*bp/len(pool):.1f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", type=int, default=0)  # 0 = one slot per working key
    ap.add_argument("--model", default="qwen/qwen3-next-80b-a3b-instruct")
    ap.add_argument("--models", default="qwen/qwen3-next-80b-a3b-instruct,nvidia/llama-3.3-nemotron-super-49b-v1.5,openai/gpt-oss-120b")
    ap.add_argument("--rotate", action="store_true")  # rotate all keys within each slot (else pin one key/slot)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    keys = load_keys()
    if a.status:
        status(a.slots or 2); return
    if not keys:
        log("❌ אין מפתחות NVIDIA ב-.env"); return
    pin = not a.rotate
    if pin:
        working = probe_keys(keys, a.model)
        if not working:
            log(f"כל {len(keys)} המפתחות חסומים (429) כרגע — נופל לרוטציה עדינה של פרוסה 1")
            pin = False; keycsv = ",".join(keys); slots = 1
        else:
            slots = min(a.slots, len(working)) if a.slots else len(working)
            working = working[:slots]
            log(f"pinned: {len(working)}/{len(keys)} מפתחות עובדים → {slots} פרוסות (אחת לכל מפתח)")
    if not pin:
        keycsv = ",".join(keys); slots = a.slots or 1
    if os.path.exists(LOCK):
        try:
            if time.time() - os.path.getmtime(LOCK) < 120:
                print("watchdog כבר רץ (lock טרי)"); return
        except OSError:
            pass
    keyfor = (lambda i: working[i]) if pin else (lambda i: keycsv)
    nmodels = len([m for m in a.models.split(",") if m.strip()])
    open(LOCK, "w").write(str(os.getpid()))
    log(f"NIM watchdog התחיל · מצב={'pinned' if pin else 'rotate'} · slots={slots} · מודלים={nmodels}")
    procs = {i: launch(i, slots, a.models, keyfor(i), pin) for i in range(slots)}
    last_bank = 0
    # hang-kick: a slot whose nim_out_<i>.json is FROZEN while its process is
    # still ALIVE is wedged on a stuck NIM request (urllib's socket timeout is
    # inactivity, not a hard deadline, so a trickle/half-open connection blocks
    # .read() indefinitely). Kill+relaunch it — the run is checkpoint-resumable,
    # so nothing is lost (mirrors the SM2/WD2 watchdogs).
    STALL = 600
    def out_mtime(i):
        try: return os.path.getmtime(os.path.join(OUTDIR, f"nim_out_{i}.json"))
        except OSError: return None
    prog = {i: (out_mtime(i), time.time()) for i in range(slots)}
    try:
        while True:
            open(LOCK, "w").write(str(os.getpid()))  # heartbeat
            for i, p in list(procs.items()):
                if p.poll() is not None:
                    log(f"slot {i} מת (exit {p.returncode}) — מפעיל מחדש")
                    procs[i] = launch(i, slots, a.models, keyfor(i), pin)
                    prog[i] = (out_mtime(i), time.time())
                    continue
                mt = out_mtime(i); last_mt, since = prog[i]
                if mt != last_mt:
                    prog[i] = (mt, time.time())
                elif time.time() - since > STALL:
                    log(f"slot {i} תקוע (פלט קפוא {int(time.time()-since)}s) — הורג ומפעיל מחדש")
                    try: p.terminate()
                    except Exception: pass
                    try: p.wait(timeout=10)
                    except Exception:
                        try: p.kill()
                        except Exception: pass
                    procs[i] = launch(i, slots, a.models, keyfor(i), pin)
                    prog[i] = (out_mtime(i), time.time())
            if time.time() - last_bank > BANK_EVERY:
                try:
                    base, da, bp, tot = bank(slots)
                    log(f"בנק: +{base} base +{da} DLC | סה\"כ {bp}/{tot} ({100*bp/tot:.1f}%)")
                    if bp >= tot:
                        log("המאגר הושלם! עוצר."); break
                except Exception as e:
                    log(f"בנק נכשל: {e}")
                last_bank = time.time()
            time.sleep(15)
    finally:
        for p in procs.values():
            try: p.terminate()
            except Exception: pass
        try: os.remove(LOCK)
        except OSError: pass
        log("watchdog נעצר")


if __name__ == "__main__":
    main()
