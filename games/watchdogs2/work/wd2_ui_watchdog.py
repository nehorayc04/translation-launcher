"""WD2 UI translation supervisor — keeps the translator alive and AUTO-DEPLOYS.

ONE process to run for the whole multi-day haul (parallel to the SM2 run, sharing
the local LM serial slot). It:
  * owns wd2_ui_translate.py via Popen — relaunches it on death; hang-kicks it if
    the done-count freezes (> HANG_S with the queue not empty).
  * every CHECKPOINT_EVERY new translations, if Watch Dogs 2 is NOT running,
    rebuilds (combine -> visual merge -> encode -> fat-redirect deploy) so the
    game shows the latest Hebrew automatically. (Deploy needs the game closed —
    it's skipped while WatchDogs2.exe is alive, retried next tick.)
  * a final deploy when the queue is fully drained.

Launch under BASE python (NOT the venv stub — it double-spawns and breaks the
singleton), hidden, with PYTHONIOENCODING=utf-8.
"""
import os, sys, json, time, re, subprocess, ctypes, importlib.util

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # games/watchdogs2
PY   = sys.executable
TRANSLATOR = os.path.join(HERE, "wd2_ui_translate.py")

# load the translator module to REUSE its exact validators (same rules as the
# write-time gate — the QA must never disagree with translate.validate()).
_spec = importlib.util.spec_from_file_location("wd2tr", TRANSLATOR)
T = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(T)
MERGE      = os.path.join(HERE, "wd2_ui_merge.py")
LOCTOOL    = os.path.join(HERE, "wd2_loc.py")
ARCHIVE    = os.path.join(HERE, "wd2_archive.py")

QUEUE    = "C:/tmp/wd2_ui_queue.json"
OUT      = "C:/tmp/wd2_ui_he.json"
ALLJSON  = "C:/tmp/wd2_ui_all.json"
COMBINED = "C:/tmp/wd2_ui_combined.json"
STRINGS  = "C:/tmp/ui_he_strings.txt"
ARLOC    = "C:/tmp/ar.loc"
OUTLOC   = "C:/tmp/main_arabic_he.loc"
REL      = r"languages\main_arabic.loc"
STATE    = "C:/tmp/wd2_ui_watchdog_state.json"
LOCK     = "C:/tmp/wd2_ui_watchdog.lock"
SKIPLIST = "C:/tmp/wd2_ui_skip.json"        # keys parked after 3 QA strikes (translator reads this)
SEEN     = "C:/tmp/wd2_ui_qa_seen.json"     # ids QA has already cleared

CHECKPOINT_EVERY = 400     # new translations between auto-deploys
TICK_S   = 120
HANG_S   = 1800            # done-count frozen this long -> kill+relaunch the translator
QA_EVERY = 3600            # structural QA sweep cadence (seconds)

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")

def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

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
        return True   # unknown -> assume running (don't deploy)

# ── singleton ──────────────────────────────────────────────────────────────────
def _alive(pid):
    PROCESS_QUERY = 0x1000
    h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY, False, pid)
    if not h:
        return False
    ctypes.windll.kernel32.CloseHandle(h)
    return True

def acquire_singleton():
    if os.path.exists(LOCK):
        try:
            old = int(open(LOCK).read().strip())
            if old != os.getpid() and _alive(old):
                log(f"another watchdog alive (pid {old}); exiting")
                sys.exit(0)
        except Exception:
            pass
    open(LOCK, "w").write(str(os.getpid()))

# ── deploy chain ────────────────────────────────────────────────────────────────
def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, cwd=ROOT)
    return r.returncode, (r.stdout or "") + (r.stderr or "")

def rebuild_deploy(done_n):
    if game_running():
        log("game running -> skip deploy this tick")
        return False
    allj = jload(ALLJSON, {}); hej = jload(OUT, {})
    comb = {str(k): v for k, v in allj.items()}
    comb.update({str(k): v for k, v in hej.items()})
    json.dump(comb, open(COMBINED, "w", encoding="utf-8"), ensure_ascii=False)
    rc, o = run([PY, MERGE, COMBINED])
    if rc:
        log(f"merge FAIL: {o[-200:]}"); return False
    rc, o = run([PY, LOCTOOL, "encode", ARLOC, STRINGS, OUTLOC])
    if rc:
        log(f"encode FAIL: {o[-200:]}"); return False
    rc, o = run([PY, ARCHIVE, "deploy", REL, OUTLOC])
    if rc or "DONE deploy" not in o:
        log(f"deploy FAIL: {o[-200:]}"); return False
    log(f"DEPLOYED checkpoint at {done_n} translated ({len(comb)} total UI strings)")
    return True

# ── structural QA (self-healing) ─────────────────────────────────────────────────
# Mirrors the SM2/CP2077 protective QA: re-check every translated line; REMOVE the
# bad ones so the translator re-does them; park a key failing 3x to the skip-list.
# Catches: foreign script, niqqud, lost/added placeholders, untranslated leaks,
# model-refusal / explanation leaks, and length blow-ups — so no defect ships.
# REFUSAL/length rules come from the translator module (T) — ONE source of truth.

def qa_entry(key, he, en):
    """Return a defect reason, or None if the line is structurally OK.
    `en` is the English source string for this id."""
    if not he or not he.strip():
        return "empty"
    if T.BAD_SCRIPTS.search(he):
        return "foreign_script_or_niqqud"
    if T.NIQQUD.search(he):
        return "niqqud"
    # placeholder multiset must be IDENTICAL (tokens/{VALUE}/%spec/&entities;/CSS)
    if T.placeholders(en) != T.placeholders(he):
        return "placeholder_mismatch"
    # model refusal / "here is the translation" / explanation leak
    if T.REFUSAL.search(he):
        return "model_refusal_leak"
    # length blow-up: the model appended an explanation (Hebrew ≈ English length;
    # a 2.4x+ blow-up on a non-trivial source is almost always rambling)
    if len(en) >= 8 and len(he) > 2.4 * len(en) + 40:
        return "length_anomaly"
    # untranslated leak: identical to EN with no Hebrew, yet EN had a real word.
    # name/code passthrough is NOT a leak (same rule as translate.validate — else
    # QA churns forever on every brand/acronym/proper-noun UI label).
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
    """Re-check newly-translated lines; remove the bad; relaunch the translator so
    it re-does them. Returns the (possibly new) translator process handle."""
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
        # kill the translator so we can rewrite the output race-free
        try: proc.kill()
        except Exception: pass
        time.sleep(2)
        cur = jload(OUT, {})
        st = jload(STATE, {}); strikes = st.get("strikes", {})
        skip = set(jload(SKIPLIST, []) or [])
        removed = parked = 0
        for k, reason in bad.items():
            strikes[k] = strikes.get(k, 0) + 1
            cur.pop(k, None); removed += 1
            tag = ""
            if strikes[k] >= 3:
                skip.add(k); parked += 1; tag = " PARKED"
            log(f"[QA] removed {k} [{reason}] strike={strikes[k]}{tag}")
        # atomic writes
        t = OUT + ".tmp"; json.dump(cur, open(t, "w", encoding="utf-8"), ensure_ascii=False, indent=0); os.replace(t, OUT)
        json.dump(sorted(skip), open(SKIPLIST, "w", encoding="utf-8"), ensure_ascii=False)
        st["strikes"] = strikes; json.dump(st, open(STATE, "w"))
        log(f"[QA] removed {removed} (parked {parked}); relaunching translator to re-do them")
        proc = spawn()
    json.dump(sorted(set(cur)), open(SEEN, "w", encoding="utf-8"))
    return proc

# ── translator process management ────────────────────────────────────────────────
def spawn():
    p = subprocess.Popen([PY, "-u", TRANSLATOR], cwd=HERE, env=ENV,
                         stdout=open("C:/tmp/wd2_ui_translate.log", "a", encoding="utf-8"),
                         stderr=subprocess.STDOUT,
                         creationflags=0x00000008)  # DETACHED_PROCESS
    log(f"translator spawned pid {p.pid}")
    return p

def main():
    acquire_singleton()
    total = len(jload(QUEUE, []))
    st = jload(STATE, {})
    last_deploy = st.get("last_deploy", count(OUT))
    log(f"supervisor up. queue={total} done={count(OUT)} last_deploy={last_deploy}")

    proc = spawn()
    last_done = count(OUT); last_progress = time.time(); last_qa = time.time()

    def save_state(**kw):
        s = jload(STATE, {}); s.update(kw); json.dump(s, open(STATE, "w"))

    while True:
        time.sleep(TICK_S)
        done = count(OUT)

        # periodic structural QA (self-healing — removes defects so they re-translate)
        if time.time() - last_qa > QA_EVERY:
            try:
                proc = run_qa(proc)
            except Exception as e:
                log(f"[QA] error: {e}")
            last_qa = time.time()
            last_done = count(OUT); last_progress = time.time()

        # finished?
        if done >= total:
            log(f"queue drained ({done}/{total}) — final deploy")
            # wait for game to be closed, then deploy once
            for _ in range(120):
                if rebuild_deploy(done):
                    break
                time.sleep(60)
            log("DONE — all UI translated + deployed"); break

        # progress / hang handling
        if done > last_done:
            last_done = done; last_progress = time.time()
        elif time.time() - last_progress > HANG_S:
            log(f"hang: done frozen at {done} > {HANG_S}s — restarting translator")
            try: proc.kill()
            except Exception: pass
            proc = spawn(); last_progress = time.time()

        # translator died? relaunch
        if proc.poll() is not None:
            log(f"translator exited ({proc.returncode}) with {done}/{total} — relaunch")
            proc = spawn()

        # checkpoint auto-deploy
        if done - last_deploy >= CHECKPOINT_EVERY:
            if rebuild_deploy(done):
                last_deploy = done
                save_state(last_deploy=last_deploy)

if __name__ == "__main__":
    main()
