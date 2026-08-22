# -*- coding: utf-8 -*-
"""Push the Corsair Cove translation progress live to the hub dashboard (gameId=corsair-cove).

Counted in SENTENCES, with the same splitter every other fleet pusher uses, so all the
dashboards share one unit. DONE = keys in hebrew.json (the merged bank the pull writes);
TOTAL = corpus.json. 60 s loop -> /api/admin/progress.

⚠️ The homepage tab only appears for a game whose catalog row is NOT `availability=planned`
(ProgressDashboard.tsx builds `publicIds` from that filter). Corsair Cove is deliberately still
`planned`, so these snapshots are recorded but stay INVISIBLE on the site — flipping that flag
is an admin/publish decision, not this script's.
"""
import os, sys, json, time, re, glob, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# count by SENTENCES (not lines): strip tokens, split on sentence terminators + newlines, min 1.
_TAG = re.compile(r"<[^<>]{1,80}>|\{[^{}]{0,80}\}|&[a-zA-Z#0-9]{1,10};")
_SENT = re.compile(r"[.!?…]+|\n+")


def sent_count(item):
    t = (item.get("en") or "") if isinstance(item, dict) else str(item or "")
    t = _TAG.sub(" ", t).strip()
    if not t:
        return 1
    return max(1, len([p for p in _SENT.split(t) if p.strip()]))


def is_token_only(item):
    """A line that is NOTHING but engine tokens cannot be translated — rendering it changes the
    token multiset and copying it back is not a translation. Out of scope, so it must not sit in
    the denominator, or a finished job is pinned below 100% with a 0/min rate forever."""
    en = (item.get("en") or "") if isinstance(item, dict) else str(item or "")
    return bool(en.strip()) and not _TAG.sub("", en).strip()


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CORPUS = os.path.join(HERE, "corpus.json")
BANK = os.path.join(HERE, "hebrew.json")
HIST = os.path.join(HERE, "cc_progress_hist.json")
BANKS = os.path.join(HERE, "banks")

GAME_ID = "corsair-cove"            # MUST match the Supabase games row id (the dashboard joins on it)
_STREAM_RE = re.compile(r"_(?:groq|sambanova|nim)\.json$")
INTERVAL = 60
API = "https://hebrew-translation-hub.com"


def count_streams(default=9):
    """Live provider-stream count = number of per-provider bank files (machine x provider)."""
    try:
        n = sum(1 for f in glob.glob(os.path.join(BANKS, "out_*.json"))
                if _STREAM_RE.search(os.path.basename(f)))
        return n if n > 0 else default
    except Exception:
        return default


def model_line(streams):
    return f"תרגום רב לשוני - {streams} זרמים"


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
    try:
        hist = json.load(open(HIST, encoding="utf-8"))
    except Exception:
        hist = []
    now = time.time(); hist.append([now, done])
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


def push(token, processed, total, rate, streams):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "translation",
        "phaseLabelHe": "תרגום ממשק וכתוביות לעברית",
        "processed": processed, "total": total, "ratePerHour": int(rate),
        "unit": "משפטים", "meta": {"alive": True, "streams": streams, "countUnit": "sentences"},
        "aiModel": model_line(streams), "gpuModel": "",
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
        print("no MONITOR_TOKEN — exiting"); return 1
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    SENT = {k: sent_count(v) for k, v in corpus.items() if not is_token_only(v)}
    skipped = len(corpus) - len(SENT)
    total = sum(SENT.values())
    print(f"Corsair Cove pusher: total {total} sentences ({len(SENT)} lines; "
          f"{skipped} token-only out of scope), every {INTERVAL}s -> {API}")
    last_done = 0
    while True:
        try:
            bank = json.load(open(BANK, encoding="utf-8"))
            # only in-scope keys count — a banked token-only line is out of the denominator
            # too, so counting it would push `done` past 100%.
            done = min(sum(SENT[k] for k in bank if k in SENT), total)
            last_done = done
        except Exception:
            # 🔴 transient read (file mid-write / full disk) must REUSE the last good value.
            # Publishing a 0 poisons the rate window and shows 0/min on a healthy fleet.
            done = last_done
        rate = _rate(done)
        streams = count_streams()
        try:
            st = push(token, done, total, rate, streams)
            print(f"pushed {done}/{total} ({100 * done / max(1, total):.1f}%) "
                  f"rate={int(rate)}/h streams={streams} -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
