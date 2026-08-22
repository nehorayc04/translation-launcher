# -*- coding: utf-8 -*-
"""Push the Spider-Man 2 New-Era line-by-line QA review progress live to the hub dashboard
(gameId=spiderman2), in parallel with the RDR2 pusher. SM2 is already translated + published —
this is a QUALITY review pass — so the bar tracks the review, not a translation.

Counted in SENTENCES (same splitter as the other pushers) so every dashboard shares one unit.
DONE = union of keys in banks/out_*.json (what the 9 streams have actually reviewed);
TOTAL = the full corpus.json. 60 s loop -> /api/admin/progress.
"""
import os, sys, json, time, re, glob, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_TAG = re.compile(r'<[^>]*>|\{[^}]*\}|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
_SENT = re.compile(r'[.!?…]+|\n+')
def _text(x):
    """The New-Era-2 corpus stores every language as a [feminine, masculine] PAIR, so `he` is a
    LIST here while the old New-Era-1 corpus had a plain string. Reading it blind raised
    `TypeError: expected string, got 'list'` at startup — and because the pusher is launched
    detached by the pull, that crash was completely silent: the fleet ran, the website showed
    nothing, and the only clue was a missing process."""
    if isinstance(x, list):
        return next((s for s in x if isinstance(s, str) and s.strip()), "")
    return x if isinstance(x, str) else ""


def sent_count(item):
    if isinstance(item, dict):
        t = _text(item.get("he")) or _text(item.get("en"))
    else:
        t = str(item or "")
    t = _TAG.sub(" ", t).strip()
    if not t:
        return 1
    return max(1, len([p for p in _SENT.split(t) if p.strip()]))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BANKS = os.path.join(HERE, "banks")
CORPUS = os.path.join(HERE, "corpus.json")
HIST = os.path.join(HERE, "sm2ne2_progress_hist.json")

GAME_ID = "spiderman2"              # MUST match the Supabase games row id (the dashboard joins on it)
_STREAM_RE = re.compile(r'_(?:groq|sambanova|nim)\.json$')

def count_streams(default=9):
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


def reviewed_keys():
    keys = set()
    for f in glob.glob(os.path.join(BANKS, "out_*.json")):
        try:
            keys.update(json.load(open(f, encoding="utf-8")))
        except Exception:
            pass
    return keys


def push(token, processed, total, rate, streams):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "qa",
        "phaseLabelHe": "בדיקת איכות שורה-שורה (התרגום כבר הושלם)",
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
    try:
        corpus = json.load(open(CORPUS, encoding="utf-8"))
    except Exception as e:
        print(f"corpus load failed: {e}"); return 1
    if not corpus:
        print("empty corpus — exiting"); return 1
    SENT = {k: sent_count(v) for k, v in corpus.items()}
    total = sum(SENT.values())
    print(f"SM2 QA pusher: total {total} sentences ({len(SENT)} lines), every {INTERVAL}s -> {API}")
    last_done = 0
    while True:
        try:
            done = min(sum(SENT[k] for k in reviewed_keys() if k in SENT), total)
            last_done = done
        except Exception:
            done = last_done
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
