# -*- coding: utf-8 -*-
"""A Plague Tale: Requiem — push LIVE gender-review (QA) progress to the hub home page.

PT translation is 100%; this phase reviews every gender-bearing line against the game's professional
Arabic and fixes mismatched gender/number. 60 s loop -> POST /api/admin/progress (MONITOR_TOKEN from
the repo-root .env). processed = lines reviewed so far (union of gbanks/out_*.json), total = the
reviewable gender-signal set (gender_corpus.json). gameId MUST equal Supabase games.id.
"""
import os, sys, json, time, glob, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
GB = os.path.join(HERE, "gbanks")
CORPUS = os.path.join(HERE, "gender_corpus.json")
OVERRIDES = os.path.join(HERE, "..", "gender_overrides.json")
HIST = os.path.join(HERE, "pt_gender_prog_hist.json")

GAME_ID = "plague-tale-requiem"
AI_MODEL = "llama-3.1-70b (NIM) — gender QA vs Arabic"
INTERVAL = 60
API = "https://hebrew-translation-hub.com"
UNIT = "שורות"


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


def _total():
    try:
        return len(json.load(open(CORPUS, encoding="utf-8")))
    except (OSError, ValueError):
        return 0


def _reviewed():
    keys = set()
    for f in glob.glob(os.path.join(GB, "out_*.json")):
        try:
            keys |= set(json.load(open(f, encoding="utf-8")).keys())
        except (OSError, ValueError):
            pass
    return len(keys)


def _fixes():
    try:
        return len(json.load(open(OVERRIDES, encoding="utf-8")))
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


def push(token, processed, total, rate, fixes):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "qa", "phaseLabelHe": "בקרת מגדר (מול ערבית)",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": UNIT, "meta": {"alive": True, "streams": 4, "genderFixes": fixes},
        "aiModel": AI_MODEL, "gpuModel": "",
    }).encode("utf-8")
    req = urllib.request.Request(API + "/api/admin/progress", body,
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    env = _load_env(os.path.join(ROOT, ".env"))
    token = env.get("MONITOR_TOKEN", "")
    if not token:
        print("no MONITOR_TOKEN in root .env — exiting"); return 1
    total = _total()
    if total <= 0:
        print("gender_corpus.json missing — exiting"); return 1
    once = "--once" in sys.argv
    print(f"gender-QA progress pusher: total={total} reviewable, {'single push' if once else f'every {INTERVAL}s'} -> {API}")
    while True:
        done = _reviewed()
        rate = _rate(done)
        fixes = _fixes()
        try:
            st = push(token, done, total, rate, fixes)
            print(f"{time.strftime('%F %H:%M:%S')} pushed {done}/{total} reviewed ({100*done/total:.1f}%) rate={int(rate)}/h fixes={fixes} -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        if once:
            return 0
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
