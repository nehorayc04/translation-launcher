# -*- coding: utf-8 -*-
"""Push the W3 "New Era" untranslated run (vm5) live to the hub home page.

The regular w3_progress.py counts hebrew.json against the clean community pool (ct_strings.json), but
1,448 of these 1,596 lines are NOT in that pool (their English extraction was XOR-corrupt), so the
normal bar never moves for this run. This dedicated pusher shows THIS run honestly: processed =
lines that passed the New Era (w3_newera_passed.json), total = the run's corpus (w3ut_corpus.json).

60 s loop -> POST /api/admin/progress (MONITOR_TOKEN from repo-root .env). gameId="witcher3" so it
lands on the home ProgressDashboard as the freshest live snapshot (meta.alive=True).
"""
import os, sys, json, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PASSED = os.path.join(HERE, "w3_newera_passed.json")
CORPUS = os.path.join(HERE, "w3ut_corpus.json")
HIST = os.path.join(HERE, "w3ut_progress_hist.json")

GAME_ID = "witcher3"
AI_MODEL = "llama-3.1-70b (NIM cloud) — עידן חדש: תרגום מהערבית + אימות מגדר רב-לשוני"
INTERVAL = 60
API = "https://hebrew-translation-hub.com"
UNIT = "שורות"
LABEL = "תרגום שורות אחרונות (עידן חדש)"


def _load_env(path):
    env = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def _count(path):
    try:
        return len(json.load(open(path, encoding="utf-8")))
    except (OSError, ValueError):
        return 0


def _rate(done):
    hist = []
    try:
        hist = json.load(open(HIST, encoding="utf-8"))
    except (OSError, ValueError):
        hist = []
    now = time.time()
    hist.append([now, done])
    hist = [p for p in hist if now - p[0] <= 3900][-80:]
    try:
        json.dump(hist, open(HIST, "w", encoding="utf-8"))
    except OSError:
        pass
    win = [p for p in hist if now - p[0] <= 1500] or hist[-2:]
    if len(win) < 2:
        return 0.0
    (t0, c0), (t1, c1) = win[0], win[-1]
    if t1 <= t0 or c1 < c0:
        return 0.0
    return (c1 - c0) / ((t1 - t0) / 3600.0)


def push(token, processed, total, rate):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "translation", "phaseLabelHe": LABEL,
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": UNIT, "meta": {"alive": True, "streams": 1, "run": "new-era-vm5"},
        "aiModel": AI_MODEL, "gpuModel": "",
    }).encode("utf-8")
    req = urllib.request.Request(API + "/api/admin/progress", body,
                                 {"Content-Type": "application/json",
                                  "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    env = _load_env(os.path.join(ROOT, ".env"))
    token = env.get("MONITOR_TOKEN", "")
    if not token:
        print("no MONITOR_TOKEN in root .env — exiting"); return 1
    total = _count(CORPUS) or 1596
    print(f"W3 New-Era progress pusher: total={total}, every {INTERVAL}s -> {API}")
    while True:
        done = min(_count(PASSED), total)
        rate = _rate(done)
        try:
            st = push(token, done, total, rate)
            print(f"pushed {done}/{total} ({100*done/total:.1f}%) rate={int(rate)}/h -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
