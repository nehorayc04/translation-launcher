# -*- coding: utf-8 -*-
"""anno1800_watchdog.py — self-healing supervisor for the Anno 1800 translation run.

Brings up and keeps the whole stack alive AND clean, unattended, for the
multi-day gemma-4-31b-it run. It is the single thing to launch.

  1. LOCAL MODEL — verifies gemma-4-31b-it@q2_k_xl stays loaded in LM Studio.
     If it drops or hangs, recovers it: KILL the translator FIRST (free the
     model — a busy/hung model won't cleanly unload), then `lms unload --all`,
     clear the known ~/.lmstudio/.internal ReadOnly flag, reload serial
     (--parallel 1), then an end-to-end `lm_responsive()` probe (a runtime hung
     in GENERATING still shows "loaded" — only a real generation proves health).
  2. TRANSLATOR  — keeps anno1800_translate.py running; relaunches if it died
     while work remains; detects a HANG (done-count frozen past STALL_SECONDS)
     and kicks it (reloading the LM first, the usual hang cause). Liveness via
     Popen.poll() on the handle it launched (no fragile cmdline scan).
  3. PROGRESS    — keeps anno1800_progress.py pushing so the website live
     dashboard always shows progress.
  4. HOURLY QA   — every hour, structurally re-validates the lines translated
     since the last check (placeholder/tag/%-spec multiset · foreign-script ·
     niqqud · untranslated leak, sharing the translator's name/code passthrough
     rule). Bad lines are REMOVED so the translator re-does them; a line failing
     3x is parked to the skip-list (left to the build's English fallback).

Run under BASE python (NOT the venv stub — the venv python.exe is a redirector
that double-spawns and breaks the singleton), hidden, with UTF-8 stdout:
    Start-Process "C:\\...\\Python313\\python.exe" `
        -ArgumentList '-u','work\\anno1800_watchdog.py' `
        -WorkingDirectory "<games/anno1800>" -WindowStyle Hidden

Singleton-guarded, crash-protected. Only writes translation data to REMOVE a
QA-failed line (atomic). Logs to c:/tmp/anno1800_watchdog.log.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anno1800_translate as T      # reuse regexes + paths (no side effects on import)

try:
    import psutil
except ImportError:
    psutil = None

HERE  = T.HERE
HOME  = os.path.expanduser("~")
LMS   = os.path.join(HOME, ".lmstudio", "bin", "lms.exe")
INTERNAL = os.path.join(HOME, ".lmstudio", ".internal")
MODEL = T.MODEL

OUT   = T.OUT          # hebrew.json
SKIP  = T.SKIP_F
STATE = os.path.join(HERE, "anno1800_watchdog_state.json")
SEEN  = os.path.join(HERE, "anno1800_watchdog_seen.json")

TR_LOG   = r"c:\tmp\anno1800_translate.log"
PUSH_LOG = r"c:\tmp\anno1800_progress.log"
WD_LOG   = r"c:\tmp\anno1800_watchdog.log"

# LM serving config — Anno runs SOLO on the slot, so serial --parallel 1 with the
# model's full context. Env-overridable; reload mirrors the live `lms ps` value
# when it can so a recovery never silently downgrades a user-chosen setting.
LM_CONTEXT  = os.environ.get("ANNO_LM_CONTEXT", "8192")
LM_PARALLEL = os.environ.get("ANNO_LM_PARALLEL", "1")
_LM_CFG = {"context": LM_CONTEXT, "parallel": LM_PARALLEL}

TOTAL          = T.total_records()   # translatable total from the spine (see anno1800_progress.py)
CYCLE          = 60          # supervisor tick (s)
STALL_SECONDS  = 1500        # done-count frozen this long while alive = LM hang.
                             # The translator flushes after every batch attempt,
                             # so a healthy run advances `done` every <~1000 s even on
                             # the biggest solo blurb → 1500 s frozen = hung.
LM_DEGRADE_WINDOW = 2400     # the RAM-fitting q2 LM is steady but a reload only re-warms it,
LM_DEGRADE_MIN    = 6        # it can't make it faster. Fire a reload ONLY on a near-hang
                             # (< LM_DEGRADE_MIN entries in the window), not on merely-slow —
                             # else it disrupts for nothing. Full hangs caught by STALL_SECONDS.
QA_INTERVAL    = 3600        # hourly structural QA
RELAUNCH_MIN   = 120         # min seconds between translator (re)launches
RELAUNCH_BACKOFF = 1800      # after repeated no-progress passes, slow down

DETACHED_PROCESS         = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

TR_SCRIPT   = "anno1800_translate.py"
PUSH_SCRIPT = "anno1800_progress.py"
WD_SCRIPT   = "anno1800_watchdog.py"


# ── logging ────────────────────────────────────────────────────────────
def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(WD_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# ── small json helpers ─────────────────────────────────────────────────
def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def atomic_dump(obj, path):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

_state = load_json(STATE, {}) or {}
def save_state():
    try: atomic_dump(_state, STATE)
    except Exception as e: log(f"save_state failed: {e}")


# ── process management ─────────────────────────────────────────────────
def running_pids(needle):
    """PIDs of python processes invoked as `python ... <needle>` — matched on
    the script being the FINAL cmdline token (so a stray process that merely
    mentions the name never false-matches)."""
    pids = []
    if psutil:
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                nm = (p.info.get("name") or "").lower()
                if "python" in nm:
                    cl = " ".join(p.info.get("cmdline") or [])
                    if cl.rstrip().endswith(needle):
                        pids.append(p.info["pid"])
            except Exception:
                pass
        return pids
    # PowerShell fallback (base python has no psutil) — '* <needle>' anchors the
    # script at the end of the command line.
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
             f"Where-Object {{ $_.CommandLine -like '* {needle}' }} | "
             "Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=30).stdout
        for ln in out.splitlines():
            ln = ln.strip()
            if ln.isdigit():
                pids.append(int(ln))
    except Exception:
        pass
    return pids

def kill_script(needle):
    for pid in running_pids(needle):
        if pid == os.getpid():
            continue
        try:
            if psutil:
                psutil.Process(pid).kill()
            else:
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                               capture_output=True, timeout=15)
        except Exception:
            pass

def launch(script, logpath):
    """Launch a child detached (survives the watchdog) and return its Popen so
    liveness can be checked with .poll() — no cmdline scan needed. Children get
    PYTHONIOENCODING=utf-8 so a non-cp1255 char in a print can never crash them."""
    try:
        f = open(logpath, "a", encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        p = subprocess.Popen(
            [sys.executable, "-u", script],
            cwd=HERE, stdout=f, stderr=subprocess.STDOUT, env=env,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        log(f"launched {script} (pid={p.pid})")
        return p
    except Exception as e:
        log(f"launch {script} failed: {e}")
        return None

def alive(proc):
    return proc is not None and proc.poll() is None


# ── LM Studio health ───────────────────────────────────────────────────
def lm_loaded():
    try:
        out = subprocess.run([LMS, "ps"], capture_output=True, text=True,
                             timeout=30).stdout or ""
        return MODEL in out
    except Exception as e:
        log(f"lms ps failed: {e}")
        return False

def capture_lm_config():
    """Read the loaded model's live CONTEXT + PARALLEL from `lms ps` so a reload
    re-applies the SAME settings instead of forcing defaults. Falls back to the
    last-known / env values when the model has already dropped out of `lms ps`.
    Returns (context, parallel)."""
    try:
        out = subprocess.run([LMS, "ps"], capture_output=True, text=True,
                             timeout=30).stdout or ""
        for line in out.splitlines():
            if MODEL in line:
                nums = [p for p in re.split(r"\s{2,}", line.strip()) if p.isdigit()]
                if len(nums) >= 2:
                    _LM_CFG["context"], _LM_CFG["parallel"] = nums[0], nums[1]
                break
    except Exception as e:
        log(f"capture_lm_config failed: {e}")
    return _LM_CFG["context"], _LM_CFG["parallel"]

def lm_responsive(timeout=60):
    """True iff the LM actually answers a tiny prompt. A runtime hung in
    GENERATING still shows 'loaded' in `lms ps` but never returns — only an
    end-to-end probe distinguishes healthy from hung. Caller must ensure the
    translator isn't holding the (parallel=1) slot, or this queues + times out."""
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
        log(f"LM probe failed: {e}")
        return False

def reload_lm():
    """FULL clean reload. The caller MUST kill the translator first so the model
    is free (a busy/hung model won't cleanly unload — the 10-hour SM2 bug).
    unload --all → clear ReadOnly → load serial → warmup probe to confirm it
    actually serves (not just 'loaded')."""
    ctx, par = capture_lm_config()   # mirror the LIVE setting — never downgrade
    log(f"reloading LM (unload --all → clear ReadOnly → "
        f"load --context-length {ctx} --parallel {par} → probe) ...")
    try:
        subprocess.run([LMS, "unload", "--all"], capture_output=True, timeout=90)
    except Exception:
        pass
    try:
        subprocess.run(["attrib", "-R", INTERNAL, "/S", "/D"],
                       capture_output=True, timeout=30)
    except Exception as e:
        log(f"attrib failed: {e}")
    try:
        r = subprocess.run(
            [LMS, "load", MODEL, "-y", "--gpu", "max",
             "--context-length", ctx, "--parallel", par],
            capture_output=True, text=True, timeout=300)
        log(f"lms load rc={r.returncode}")
    except Exception as e:
        log(f"lms load failed: {e}")
        return False
    ok = lm_responsive()
    log(f"LM reload {'OK (responsive)' if ok else 'FAILED (not responsive)'}")
    return ok


# ── progress counting ──────────────────────────────────────────────────
def count_done():
    d = load_json(OUT, {})
    return len(d) if isinstance(d, dict) else 0


# ── structural QA ──────────────────────────────────────────────────────
def _spine_en():
    """Read the English spine into {guid: en} (cached on _state for the session)."""
    en = _state.get("_en_cache")
    if en is not None:
        return en
    en = {}
    try:
        import xml.etree.ElementTree as ET
        texts = ET.parse(T.SPINE).getroot().find("Texts")
        for el in texts.findall("Text"):
            g = (el.findtext("GUID") or "").strip()
            v = (el.findtext("Text") or "").strip()
            if g:
                en[g] = v
    except Exception as e:
        log(f"spine read failed: {e}")
    _state["_en_cache"] = en
    return en

def qa_entry(key, he, en):
    """Return a defect reason string, or None if the line is structurally OK.
    Shares the translator's name/code passthrough rule (the universal lesson:
    a QA leak-check that doesn't share it churns on every proper noun)."""
    if not he or not he.strip():
        return "empty"
    if T.BAD_SCRIPTS.search(he):
        return "foreign_script_or_niqqud"
    if T.NIQQUD.search(he):
        return "niqqud"
    ev = en.get(key, "") or ""
    # placeholder / tag / %-spec / entity multiset present in EN must survive
    if T._placeholders(ev) != T._placeholders(he):
        return "placeholder_lost"
    # untranslated leak: identical to EN with no Hebrew, yet EN had real text —
    # BUT a name/code that legitimately stays Latin is NOT a leak.
    core = re.sub(r'\[[^\]]*\]|\{[^}]+\}|<[^>]+>|%[%a-zA-Z]|&[a-zA-Z#0-9]+;', '', ev).strip()
    if core and he.strip() == ev.strip() and not re.search(r'[א-ת]', he):
        words = re.findall(r"[A-Za-z][A-Za-z'.\-]*", core)
        is_namey = bool(words) and len(words) <= 4 and all(w[0].isupper() for w in words)
        no_real_word = not re.search(r'[a-z]{2,}', core)
        if not (is_namey or no_real_word):
            return "untranslated"
    return None

def run_qa():
    cur = load_json(OUT, {}) or {}
    if not isinstance(cur, dict):
        cur = {}
    seen = set(load_json(SEEN, []) or [])
    new_keys = [k for k in cur if k not in seen]
    if not new_keys:
        log("[QA] no new lines since last check")
        atomic_dump(sorted(cur), SEEN)
        return

    en = _spine_en()
    bad = {}
    for k in new_keys:
        try:
            reason = qa_entry(k, cur[k], en)
        except Exception as e:
            reason = f"qa_error:{type(e).__name__}"
        if reason:
            bad[k] = reason
    log(f"[QA] checked {len(new_keys)} new lines — {len(bad)} flagged")

    if bad:
        # stop the translator so we can rewrite the output file race-free
        kill_script(TR_SCRIPT)
        time.sleep(2)
        cur = load_json(OUT, {}) or {}
        strikes = _state.setdefault("strikes", {})
        skip = set(load_json(SKIP, []) or [])
        removed = parked = 0
        for k, reason in bad.items():
            strikes[k] = strikes.get(k, 0) + 1
            cur.pop(k, None)
            removed += 1
            tag = ""
            if strikes[k] >= 3:
                skip.add(k); parked += 1; tag = " PARKED(skip-list)"
            log(f"[QA] removed {k} [{reason}] strike={strikes[k]}{tag}")
        atomic_dump(cur, OUT)
        atomic_dump(sorted(skip), SKIP)
        save_state()
        log(f"[QA] removed {removed} bad lines (parked {parked}); "
            f"translator will re-translate the rest")

    atomic_dump(sorted(cur), SEEN)


# ── singleton guard ────────────────────────────────────────────────────
def singleton_guard():
    others = [p for p in running_pids(WD_SCRIPT) if p != os.getpid()]
    if others:
        log(f"another watchdog already running (pids={others}) — exiting")
        sys.exit(0)


# ── main supervisor loop ───────────────────────────────────────────────
def main():
    singleton_guard()
    log("=" * 60)
    log(f"watchdog start (pid={os.getpid()})  total={TOTAL}")

    # Clear any orphan translator/pusher from a previous session so the ones we
    # launch are the only instances and we can track them by Popen handle.
    kill_script(TR_SCRIPT)
    kill_script(PUSH_SCRIPT)
    time.sleep(2)

    tr_proc   = None
    push_proc = None
    last_done       = count_done()
    last_progress   = time.time()
    last_launch     = 0.0
    last_qa         = _state.get("last_qa_ts", 0.0)
    done_at_launch  = None
    noprog_count    = 0
    announced_done  = False
    last_degrade_check    = time.time()
    done_at_degrade_check = last_done

    while True:
        try:
            now = time.time()

            # 1) LM health — reload if the model fell out of LM Studio. Kill the
            #    translator FIRST so the model is free to unload cleanly.
            lm_ok = lm_loaded()
            if not lm_ok:
                log("LM not loaded — kill translator + reload")
                kill_script(TR_SCRIPT)
                tr_proc = None
                time.sleep(3)
                reload_lm()
                lm_ok = lm_loaded()

            # 2) progress accounting
            done = count_done()
            remaining = max(0, TOTAL - done)
            if done > last_done:
                last_done = done
                last_progress = now
                noprog_count = 0

            # if QA / an external kill ended the translator, drop the dead handle
            if tr_proc is not None and tr_proc.poll() is not None:
                tr_proc = None

            # 2.5) degradation guard — reload the LM if throughput collapsed without
            #      a full freeze (the slow-crawl state the frozen-stall guard misses)
            if now - last_degrade_check >= LM_DEGRADE_WINDOW:
                win = done - done_at_degrade_check
                if win < LM_DEGRADE_MIN and remaining > 0:
                    log(f"LM DEGRADED ({win} entries in {int(now - last_degrade_check)}s) "
                        f"— kill translator + reload LM")
                    kill_script(TR_SCRIPT)
                    tr_proc = None
                    time.sleep(3)
                    reload_lm()
                    last_progress = now
                last_degrade_check = now
                done_at_degrade_check = done

            # 3) completion
            if remaining == 0:
                if not announced_done:
                    log(f"*** TRANSLATION COMPLETE — {done}/{TOTAL} ***")
                    log("Next: run `python build_mod.py` (logical) → proof gate → publish.")
                    announced_done = True
            else:
                announced_done = False
                # 4) keep the translator alive
                if not alive(tr_proc):
                    interval = RELAUNCH_BACKOFF if noprog_count >= 3 else RELAUNCH_MIN
                    if done_at_launch is not None and done <= done_at_launch:
                        noprog_count += 1
                        log(f"translator ended a pass with NO progress "
                            f"(done={done}, remaining={remaining}, noprog={noprog_count})")
                    if now - last_launch >= interval:
                        if lm_ok:
                            done_at_launch = done
                            tr_proc = launch(TR_SCRIPT, TR_LOG)
                            if tr_proc:
                                last_launch = now
                                last_progress = now
                        else:
                            log("LM not ready — deferring translator launch")
                else:
                    # 5) hang detection — a frozen done-count means the LM is hung
                    #    in GENERATING. Kill the translator FIRST (free the model),
                    #    THEN reload (a busy model won't unload), then relaunch next cycle.
                    if now - last_progress > STALL_SECONDS:
                        log(f"translator STALLED ({int(now - last_progress)}s no progress) "
                            f"— kill translator + reload LM")
                        kill_script(TR_SCRIPT)
                        tr_proc = None
                        time.sleep(3)
                        reload_lm()
                        last_progress = now  # grace before re-evaluating

            # 6) keep the progress pusher alive
            if not alive(push_proc):
                push_proc = launch(PUSH_SCRIPT, PUSH_LOG)

            # 7) hourly structural QA
            if now - last_qa >= QA_INTERVAL:
                try:
                    run_qa()
                    if tr_proc is not None and tr_proc.poll() is not None:
                        tr_proc = None      # QA may have killed it to rewrite output
                except Exception as e:
                    log(f"QA error: {type(e).__name__}: {e}")
                last_qa = now
                _state["last_qa_ts"] = now
                save_state()

            # heartbeat
            log(f"[hb] done={done}/{TOTAL} rem={remaining} "
                f"tr={'up' if alive(tr_proc) else 'DOWN'} "
                f"push={'up' if alive(push_proc) else 'DOWN'} "
                f"lm={'ok' if lm_ok else 'DOWN'} idle={int(now - last_progress)}s")

        except Exception as e:
            log(f"loop error: {type(e).__name__}: {e}")

        time.sleep(CYCLE)


if __name__ == "__main__":
    main()
