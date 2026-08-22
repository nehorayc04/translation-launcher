# -*- coding: utf-8 -*-
"""Push the CP2077 line-by-line QA progress live to the hub dashboard (gameId=cyberpunk2077),
in PARALLEL with the Witcher-3 pusher. The base translation is already 100% + published — this
is a QUALITY pass — so the label makes that explicit and the bar tracks the QA review, not the
translation. Reads cpqa_out.json (the merged reviewed set). 60 s loop -> /api/admin/progress.
"""
import os, sys, json, time, re, glob, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# count by SENTENCES (not items): split each line on sentence terminators + newlines, min 1.
_TAG = re.compile(r'<[^>]*>|\{[^}]*\}|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
_SENT = re.compile(r'[.!?…]+|\n+')
def sent_count(item):
    t = (item.get("he") or item.get("en") or "")
    t = _TAG.sub(" ", t).strip()
    if not t:
        return 1
    return max(1, len([p for p in _SENT.split(t) if p.strip()]))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "cpqa_out.json")
CORPUS = os.path.join(HERE, "qa_corpus.json")
HIST = os.path.join(HERE, "cpqa_progress_hist.json")

GAME_ID = "cyberpunk"              # MUST match the Supabase games row id (the dashboard joins on it)
BANKS = os.path.join(HERE, "banks")
_STREAM_RE = re.compile(r'_(?:groq|sambanova|nim)\.json$')

def count_streams(default=9):
    """Live provider-stream count = number of per-provider bank files (machine x provider)."""
    try:
        n = sum(1 for f in glob.glob(os.path.join(BANKS, "out_*.json"))
                if _STREAM_RE.search(os.path.basename(f)))
        return n if n > 0 else default
    except Exception:
        return default

def model_line(streams):
    return f"ביקורת רב לשונית - {streams} זרמים"

INTERVAL = 60
API = "https://hebrew-translation-hub.com"


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


def push(token, processed, total, rate, streams):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "qa",
        "phaseLabelHe": "בדיקת איכות שורה-שורה (התרגום כבר 100%)",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": "משפטים", "meta": {"alive": True, "streams": streams, "countUnit": "sentences"},
        "aiModel": model_line(streams), "gpuModel": "",
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
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    SENT = {k: sent_count(v) for k, v in corpus.items()}   # per-item sentence count (precomputed once)
    total = sum(SENT.values())
    print(f"CP2077 QA pusher: total {total} sentences ({len(corpus)} items), every {INTERVAL}s -> {API}")
    last_done = 0
    while True:
        try:
            reviewed = json.load(open(OUT, encoding="utf-8"))
            done = min(sum(SENT.get(k, 1) for k in reviewed), total)
            last_done = done
        except Exception:
            done = last_done   # transient read (file mid-write / disk hiccup) — reuse last good, never push 0
        rate = _rate(done)
        streams = count_streams()
        try:
            st = push(token, done, total, rate, streams)
            print(f"pushed {done}/{total} ({100*done/total:.1f}%) rate={int(rate)}/h streams={streams} -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
