# -*- coding: utf-8 -*-
"""Push the W3 gender-review sub-task live to the hub (witcher3 tab). Reads
w3_gender_reviewed.json (the pull merges the 3 streams there). Counts by SENTENCES (the
project-wide W3 convention, unit="משפטים") — each corpus line's English is split into
sentences and that weight is what's done/total. 60 s loop -> POST /api/admin/progress.
"""
import os, re, sys, json, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BANK = os.path.join(HERE, "w3_gender_reviewed.json")
CORPUS = os.path.join(HERE, "w3_gender_corpus.json")
HIST = os.path.join(HERE, "w3g_progress_hist.json")

GAME_ID = "witcher3"
AI_MODEL = "llama-3.1-70b (NIM cloud, 3-stream, gender vs Arabic)"
INTERVAL = 60
API = "https://hebrew-translation-hub.com"
UNIT = "משפטים"

_TERM = re.compile(r'[.!?…]+')
_STRUCT = re.compile(r'<[^>]*>|\{[^}]*\}|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')


def _sentences(en):
    en = _STRUCT.sub(" ", en or "").strip()
    return max(1, len(_TERM.findall(en))) if en else 0


def _sent_map():
    """id -> sentence-count (from the gender corpus' English)."""
    try:
        c = json.load(open(CORPUS, encoding="utf-8"))
    except (OSError, ValueError):
        return {}, 0
    m = {k: _sentences(v.get("en", "")) for k, v in c.items()}
    return m, sum(m.values())


def _load_env(path):
    env = {}
    try:
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def _rate(done):
    hist = []
    try: hist = json.load(open(HIST, encoding="utf-8"))
    except Exception: hist = []
    now = time.time(); hist.append([now, done])
    hist = [p for p in hist if now - p[0] <= 3900][-80:]
    try: json.dump(hist, open(HIST, "w", encoding="utf-8"))
    except OSError: pass
    win = [p for p in hist if now - p[0] <= 1500] or hist[-2:]
    if len(win) < 2: return 0.0
    (t0, c0), (t1, c1) = win[0], win[-1]
    if t1 <= t0 or c1 < c0: return 0.0
    return (c1 - c0) / ((t1 - t0) / 3600.0)


def push(token, processed, total, rate):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "translation", "phaseLabelHe": "ביקורת מגדר מול ערבית",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": UNIT, "meta": {"alive": True, "streams": 3, "countUnit": "sentences"},
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
        print("no MONITOR_TOKEN — exiting"); return 1
    sent, total = _sent_map()
    if total <= 0:
        print("could not build the sentence map (corpus missing?) — exiting"); return 1
    print(f"W3-gender pusher: {len(sent):,} lines = {total:,} sentences, every {INTERVAL}s -> {API}")
    while True:
        try: bank = json.load(open(BANK, encoding="utf-8"))
        except Exception: bank = {}
        done = sum(sent.get(str(k), 1) for k in bank)
        rate = _rate(done)
        try:
            st = push(token, done, total, rate)
            print(f"pushed {done:,}/{total:,} sentences ({100*done/total:.1f}%) "
                  f"rate={int(rate)}/h [lines {len(bank):,}] -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
