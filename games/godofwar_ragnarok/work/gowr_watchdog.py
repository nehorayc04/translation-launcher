# -*- coding: utf-8 -*-
"""God of War: Ragnarök — self-healing supervisor (Gemini API backend).

Brings up + babysits gowr_translate.py + gowr_progress.py unattended.
No LM Studio management — the translator calls the Gemini API directly.

  Start-Process "<...>\Python313\python.exe" -ArgumentList '-u','gowr_watchdog.py' \
      -WorkingDirectory <work> -WindowStyle Hidden
"""
import os, sys, json, time, subprocess

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))

OUT_F    = os.path.join(HERE, "hebrew.json")
TR       = os.path.join(HERE, "gowr_translate.py")
PUSH     = os.path.join(HERE, "gowr_progress.py")
WD_LOG   = r"c:\tmp\gowr_watchdog.log"
TR_LOG   = r"c:\tmp\gowr_translate.log"
PUSH_LOG = r"c:\tmp\gowr_progress.log"
LOCK     = os.path.join(HERE, ".gowr_watchdog.lock")

CYCLE         = 60
STALL_SECONDS = 600   # done-count frozen >10 min -> restart translator
RELAUNCH_MIN  = 120


def log(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    try:
        open(WD_LOG, "a", encoding="utf-8").write(line + "\n")
    except OSError:
        pass


def count_done():
    try:
        return len(json.load(open(OUT_F, encoding="utf-8")))
    except (OSError, ValueError):
        return 0


def spawn(script, logpath):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    f = open(logpath, "a", encoding="utf-8")
    return subprocess.Popen([sys.executable, "-u", script], cwd=HERE, env=env,
                            stdout=f, stderr=subprocess.STDOUT,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def singleton():
    if os.path.exists(LOCK):
        try:
            pid = int(open(LOCK).read().strip())
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                               capture_output=True, text=True)
            if str(pid) in (r.stdout or ""):
                log(f"another watchdog alive (pid {pid}) -- exiting"); sys.exit(0)
        except Exception:
            pass
    open(LOCK, "w").write(str(os.getpid()))


def main():
    singleton()
    log("=== gowr_watchdog start (Gemini backend) ===")
    tr = push = None
    last_done = count_done()
    last_progress_t = time.time()
    last_relaunch = 0.0

    while True:
        try:
            now = time.time()

            # 1. translator liveness
            if (tr is None or tr.poll() is not None) and now - last_relaunch > RELAUNCH_MIN:
                log("launching translator")
                tr = spawn(TR, TR_LOG)
                last_relaunch = now

            # 2. progress pusher liveness
            if push is None or push.poll() is not None:
                log("launching progress pusher")
                push = spawn(PUSH, PUSH_LOG)

            # 3. stall detection (Gemini-rate-limit pauses can be long)
            done = count_done()
            if done > last_done:
                last_done = done
                last_progress_t = now
            elif now - last_progress_t > STALL_SECONDS:
                log(f"STALL: done frozen at {done} for >{STALL_SECONDS}s -- restarting translator")
                if tr and tr.poll() is None:
                    tr.terminate(); tr = None
                last_progress_t = now

            if int(now) % 600 < CYCLE:
                log(f"heartbeat: done={done:,}")

            time.sleep(CYCLE)

        except KeyboardInterrupt:
            log("interrupted -- exiting"); break
        except Exception as e:
            log(f"loop error (continuing): {e}"); time.sleep(CYCLE)

    open(LOCK, "w").write("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
