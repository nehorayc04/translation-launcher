"""WD2 SUBTITLE translation supervisor — owns the WHOLE stack for an unattended,
multi-day run (e.g. a full weekend). ONE process to launch.

It babysits, with the heavy protections proven on SM2/CP2077/the WD2 UI run:
  * the LOCAL LM — monitors `lms ps`; if gemma drops out OR the done-count freezes
    (a GENERATING hang), it RECOVERS in the only safe order (the 10-hour-bug fix):
    kill the translator FIRST -> `lms unload --all` -> clear ReadOnly -> reload ->
    end-to-end responsiveness probe -> relaunch the translator. A model that says
    "loaded" in `lms ps` can still be hung; only a real generation proves health.
  * the translator (wd2_sub_translate.py) via Popen — relaunch on death; hang-kick.
  * hourly structural QA — re-checks newly-translated lines (reusing the translator's
    EXACT validators so QA never disagrees), REMOVES defects so they re-translate,
    parks a key failing 3x to the skip-list. No defect ever ships.
  * auto-deploy every CHECKPOINT_EVERY new lines when WatchDogs2.exe is CLOSED
    (combine UI[visual] + subtitles[logical] -> encode -> fat-redirect deploy), plus
    a final deploy when the queue drains.

Launch under BASE python (NOT the venv stub — it double-spawns + breaks the
singleton), hidden, with PYTHONIOENCODING=utf-8.
"""
import os, sys, json, time, re, subprocess, ctypes, importlib.util
import urllib.request, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY   = sys.executable
HOME = os.path.expanduser("~")
LMS      = os.path.join(HOME, ".lmstudio", "bin", "lms.exe")
INTERNAL = os.path.join(HOME, ".lmstudio", ".internal")

TRANSLATOR = os.path.join(HERE, "wd2_sub_translate.py")
MERGE      = os.path.join(HERE, "wd2_sub_merge.py")
LOCTOOL    = os.path.join(HERE, "wd2_loc.py")
ARCHIVE    = os.path.join(HERE, "wd2_archive.py")

# reuse the translator's EXACT validators (one source of truth for QA)
_spec = importlib.util.spec_from_file_location("wd2sub", TRANSLATOR)
T = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(T)
MODEL = T.MODEL

QUEUE   = T.QUEUE
OUT     = T.OUT
SKIP    = T.SKIP
STRIKES = T.STRIKES

# UI hebrew (already done) — combined into every deploy so the UI stays Hebrew
UI_HE     = "C:/tmp/wd2_ui_he.json"
UI_ALL    = "C:/tmp/wd2_ui_all.json"
UI_HANDOFF = os.path.join(ROOT, "agent_handoff", "hebrew.json")
UI_COMBINED = "C:/tmp/wd2_ui_combined_for_sub.json"

STRINGS = "C:/tmp/ui_he_strings.txt"
ARLOC   = "C:/tmp/ar.loc"
OUTLOC  = "C:/tmp/main_arabic_sub.loc"
REL     = r"languages\main_arabic.loc"

STATE = "C:/tmp/wd2_sub_watchdog_state.json"
SEEN  = "C:/tmp/wd2_sub_qa_seen.json"
LOCK  = "C:/tmp/wd2_sub_watchdog.lock"
TR_LOG = "C:/tmp/wd2_sub_translate.log"
WD_LOG = "C:/tmp/wd2_sub_watchdog.log"

CHECKPOINT_EVERY = 500     # new translations between auto-deploys
TICK_S   = 120
HANG_S   = 1800            # done frozen this long while alive -> LM hang recovery
QA_EVERY = 3600            # hourly structural QA
LM_DROP_GRACE = 2          # consecutive ticks gemma missing from `lms ps` before reload

# Solo run (SM2 not running) -> full context, one slot. capture_lm_config() mirrors
# the LIVE setting if present so we never downgrade a user choice.
LM_CONTEXT  = os.environ.get("WD2_LM_CONTEXT", "8192")
LM_PARALLEL = os.environ.get("WD2_LM_PARALLEL", "1")
_LM_CFG = {"context": LM_CONTEXT, "parallel": LM_PARALLEL}

DETACHED_PROCESS = 0x00000008
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

def log(m):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(line, flush=True)
    try:
        open(WD_LOG, "a", encoding="utf-8").write(line + "\n")
    except OSError:
        pass

def jload(p, d):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d

def count(p):
    return len(jload(p, {}))

def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq WatchDogs2.exe"],
                             capture_output=True, text=True, timeout=20).stdout
        return "WatchDogs2.exe" in out
    except Exception:
        return True

# ── singleton ────────────────────────────────────────────────────────────────
def _alive(pid):
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    ctypes.windll.kernel32.CloseHandle(h)
    return True

def acquire_singleton():
    if os.path.exists(LOCK):
        try:
            old = int(open(LOCK).read().strip())
            if old != os.getpid() and _alive(old):
                log(f"another watchdog alive (pid {old}); exiting"); sys.exit(0)
        except Exception:
            pass
    open(LOCK, "w").write(str(os.getpid()))

# ── LM Studio health ───────────────────────────────────────────────────────────
def lm_loaded():
    try:
        out = subprocess.run([LMS, "ps"], capture_output=True, text=True, timeout=30).stdout or ""
        return MODEL in out
    except Exception as e:
        log(f"lms ps failed: {e}"); return False

def capture_lm_config():
    try:
        out = subprocess.run([LMS, "ps"], capture_output=True, text=True, timeout=30).stdout or ""
        for line in out.splitlines():
            if MODEL in line:
                nums = [p for p in re.split(r"\s{2,}", line.strip()) if p.isdigit()]
                if len(nums) >= 2:
                    _LM_CFG["context"], _LM_CFG["parallel"] = nums[0], nums[1]
                break
    except Exception as e:
        log(f"capture_lm_config failed: {e}")
    return _LM_CFG["context"], _LM_CFG["parallel"]

def lm_responsive(timeout=90):
    """True iff the LM actually answers a tiny prompt. Caller MUST ensure the
    translator isn't holding the slot, else this queues + times out."""
    try:
        body = json.dumps({"model": MODEL,
                           "messages": [{"role": "user", "content": "Reply with OK"}],
                           "max_tokens": 3, "temperature": 0}).encode()
        req = urllib.request.Request(T.LM_URL, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            json.loads(r.read())
        return True
    except Exception as e:
        log(f"LM probe failed: {e}"); return False

def reload_lm():
    """FULL clean reload. The caller MUST kill the translator first (a busy/hung
    model won't cleanly unload — the 10-hour bug). unload --all -> clear ReadOnly
    -> load -> probe."""
    ctx, par = capture_lm_config()
    log(f"reloading LM (unload --all -> clear ReadOnly -> load --context-length {ctx} "
        f"--parallel {par} -> probe) ...")
    try:
        subprocess.run([LMS, "unload", "--all"], capture_output=True, timeout=90)
    except Exception:
        pass
    try:
        subprocess.run(["attrib", "-R", INTERNAL, "/S", "/D"], capture_output=True, timeout=30)
    except Exception as e:
        log(f"attrib failed: {e}")
    try:
        r = subprocess.run([LMS, "load", MODEL, "-y", "--gpu", "max",
                            "--context-length", ctx, "--parallel", par],
                           capture_output=True, text=True, timeout=360)
        log(f"lms load rc={r.returncode}")
    except Exception as e:
        log(f"lms load failed: {e}"); return False
    ok = lm_responsive()
    log(f"LM reload {'OK (responsive)' if ok else 'FAILED (not responsive)'}")
    return ok

# ── deploy chain ─────────────────────────────────────────────────────────────
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, cwd=ROOT)
    return r.returncode, (r.stdout or "") + (r.stderr or "")

def build_ui_combined():
    comb = {}
    for p in (UI_ALL, UI_HE, UI_HANDOFF):
        comb.update({str(k): v for k, v in jload(p, {}).items()})
    json.dump(comb, open(UI_COMBINED, "w", encoding="utf-8"), ensure_ascii=False)
    return len(comb)

def rebuild_deploy(done_n):
    if game_running():
        log("game running -> skip deploy this tick"); return False
    nui = build_ui_combined()
    rc, o = run([PY, MERGE, UI_COMBINED, OUT])
    if rc:
        log(f"merge FAIL: {o[-200:]}"); return False
    rc, o = run([PY, LOCTOOL, "encode", ARLOC, STRINGS, OUTLOC])
    if rc:
        log(f"encode FAIL: {o[-200:]}"); return False
    rc, o = run([PY, ARCHIVE, "deploy", REL, OUTLOC])
    if rc or "DONE deploy" not in o:
        log(f"deploy FAIL: {o[-200:]}"); return False
    log(f"DEPLOYED at {done_n} subtitles ({nui} UI + {count(OUT)} subtitle lines)")
    return True

# ── structural QA (self-healing) ─────────────────────────────────────────────
def qa_entry(key, he, en):
    if not he or not he.strip():
        return "empty"
    if T.BAD_SCRIPTS.search(he):
        return "foreign_script"
    if T.NIQQUD.search(he):
        return "niqqud"
    if T.placeholders(en) != T.placeholders(he):
        return "placeholder_mismatch"
    if T.REFUSAL.search(he):
        return "model_refusal_leak"
    if len(en) >= 8 and len(he) > 2.6 * len(en) + 50:
        return "length_anomaly"
    core = T.PH.sub("", en).strip()
    if core and he.strip() == en.strip() and not T.HEB.search(he):
        words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
        is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
        no_real_word = not re.search(r'[a-z]{2,}', core)
        if not (is_namey or no_real_word):
            return "untranslated"
    return None

def _en_by_id():
    return {str(r["id"]): r["en"] for r in jload(QUEUE, [])}

def run_qa(proc):
    cur = jload(OUT, {})
    seen = set(jload(SEEN, []) or [])
    new_keys = [k for k in cur if k not in seen]
    if not new_keys:
        return proc
    en = _en_by_id()
    bad = {}
    for k in new_keys:
        try:
            reason = qa_entry(k, cur[k], en.get(k, ""))
        except Exception as e:
            reason = f"qa_error:{type(e).__name__}"
        if reason:
            bad[k] = reason
    log(f"[QA] checked {len(new_keys)} new lines — {len(bad)} flagged")
    if bad:
        try: proc.kill()
        except Exception: pass
        time.sleep(2)
        cur = jload(OUT, {})
        strikes = jload(STRIKES, {}) or {}
        skip = set(jload(SKIP, []) or [])
        removed = parked = 0
        for k, reason in bad.items():
            strikes[k] = strikes.get(k, 0) + 1
            cur.pop(k, None); removed += 1
            tag = ""
            if strikes[k] >= 3:
                skip.add(k); parked += 1; tag = " PARKED"
            log(f"[QA] removed {k} [{reason}] strike={strikes[k]}{tag}")
        t = OUT + ".tmp"; json.dump(cur, open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=0); os.replace(t, OUT)
        json.dump(sorted(skip), open(SKIP, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(strikes, open(STRIKES, "w", encoding="utf-8"), ensure_ascii=False)
        log(f"[QA] removed {removed} (parked {parked}); relaunching translator")
        proc = spawn()
    json.dump(sorted(set(cur)), open(SEEN, "w", encoding="utf-8"))
    return proc

# ── translator process ──────────────────────────────────────────────────────
def spawn():
    p = subprocess.Popen([PY, "-u", TRANSLATOR], cwd=HERE, env=ENV,
                         stdout=open(TR_LOG, "a", encoding="utf-8"),
                         stderr=subprocess.STDOUT, creationflags=DETACHED_PROCESS)
    log(f"translator spawned pid {p.pid}")
    return p

def recover_lm(proc, why):
    """Safe recovery order: kill the translator FIRST, reload the LM, then relaunch."""
    log(f"LM recovery ({why}) — killing translator first")
    try: proc.kill()
    except Exception: pass
    time.sleep(3)
    reload_lm()
    return spawn()

def main():
    acquire_singleton()
    total = len(jload(QUEUE, []))
    st = jload(STATE, {})
    last_deploy = st.get("last_deploy", count(OUT))
    log(f"supervisor up. queue={total} done={count(OUT)} last_deploy={last_deploy}")

    # make sure the LM is actually serving before the first launch
    if not lm_loaded():
        log("LM not loaded at startup — reloading")
        reload_lm()

    proc = spawn()
    last_done = count(OUT); last_progress = time.time(); last_qa = time.time()
    lm_missing = 0

    def save_state(**kw):
        s = jload(STATE, {}); s.update(kw); json.dump(s, open(STATE, "w"))

    while True:
        time.sleep(TICK_S)
        done = count(OUT)

        # hourly structural QA
        if time.time() - last_qa > QA_EVERY:
            try:
                proc = run_qa(proc)
            except Exception as e:
                log(f"[QA] error: {e}")
            last_qa = time.time(); last_done = count(OUT); last_progress = time.time()

        # finished?
        if done >= total:
            log(f"queue drained ({done}/{total}) — final deploy")
            for _ in range(180):
                if rebuild_deploy(done):
                    break
                time.sleep(60)
            log("DONE — all subtitles translated + deployed"); break

        # LM dropped from memory?
        if not lm_loaded():
            lm_missing += 1
            log(f"LM missing from `lms ps` ({lm_missing}/{LM_DROP_GRACE})")
            if lm_missing >= LM_DROP_GRACE:
                proc = recover_lm(proc, "LM dropped from ps")
                lm_missing = 0; last_progress = time.time(); last_done = count(OUT)
                continue
        else:
            lm_missing = 0

        # progress / hang handling
        if done > last_done:
            last_done = done; last_progress = time.time()
        elif time.time() - last_progress > HANG_S:
            # frozen while alive = a GENERATING hang -> full LM recovery
            proc = recover_lm(proc, f"done frozen at {done} > {HANG_S}s")
            last_progress = time.time(); last_done = count(OUT); continue

        # translator died? relaunch (probe the LM first so we don't relaunch into a hang)
        if proc.poll() is not None:
            log(f"translator exited ({proc.returncode}) at {done}/{total}")
            if lm_loaded() and lm_responsive():
                proc = spawn()
            else:
                proc = recover_lm(proc, "translator died + LM unhealthy")
            last_progress = time.time()

        # checkpoint auto-deploy
        if done - last_deploy >= CHECKPOINT_EVERY:
            if rebuild_deploy(done):
                last_deploy = done; save_state(last_deploy=last_deploy)

if __name__ == "__main__":
    main()
