# -*- coding: utf-8 -*-
"""Push the Witcher-3 New-Era QA review progress live to the hub dashboard (gameId=witcher3),
in PARALLEL with the CP2077-QA and AC2 pushers. The W3 translation is already complete — this
is a QUALITY pass — so the bar tracks the review, not the translation.

Counted in SENTENCES (same splitter as cpqa_progress.py) so all three dashboards share one unit.
DONE = the union of keys in banks/qa_out_*.json (what the 2 streams have actually reviewed);
TOTAL = the 2 review slices. 60 s loop -> /api/admin/progress.
"""
import os, sys, json, time, re, glob, urllib.request
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# count by SENTENCES (not lines): split each line on sentence terminators + newlines, min 1.
_TAG = re.compile(r'<[^>]*>|\{[^}]*\}|%[#0-9.*\-+]*[a-zA-Z]+|&[a-zA-Z#0-9]+;')
_SENT = re.compile(r'[.!?…]+|\n+')
def sent_count(item):
    t = (item.get("he") or item.get("en") or "") if isinstance(item, dict) else str(item or "")
    t = _TAG.sub(" ", t).strip()
    if not t:
        return 1
    return max(1, len([p for p in _SENT.split(t) if p.strip()]))

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BANKS = os.path.join(HERE, "banks")
# The FULL review corpus (all ~92.6k lines) — the denominator. The qa_slice_* files are the
# machine SHARDS of the not-yet-reviewed remainder and change with every re-slice, so the total
# must come from the whole corpus, not the shards.
SLICES = [os.path.join(HERE, "w3qa_corpus.json")]
HIST = os.path.join(HERE, "w3qa_progress_hist.json")
# Lines already reviewed AND whose fixes were merged into a PUBLISHED mod build. They are done
# and shipped, so the bar must not keep counting them — it restarts from 0 over what REMAINS.
# Refresh it (snapshot the current union of banks/qa_out_*.json) after every merge+publish.
BASELINE = os.path.join(HERE, "qa_merged_baseline.json")

GAME_ID = "witcher3"               # MUST match the Supabase games row id (the dashboard joins on it)
_STREAM_RE = re.compile(r'_(?:groq|sambanova|nim)\.json$')

def count_streams(default=6):
    """Live provider-stream count = number of per-provider bank files (slice x provider)."""
    try:
        n = sum(1 for f in glob.glob(os.path.join(BANKS, "qa_out_*.json"))
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
    """Union of every stream bank — the banks are the source of truth for what was reviewed
    (qa_reviewed.json holds only the PROPOSED CHANGES, a small subset, so it must not be used)."""
    keys = set()
    for f in glob.glob(os.path.join(BANKS, "qa_out_*.json")):
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
    corpus = {}
    for p in SLICES:
        try: corpus.update(json.load(open(p, encoding="utf-8")))
        except Exception as e: print(f"slice {p} failed: {e}")
    if not corpus:
        print("empty corpus — exiting"); return 1
    base = set()
    try:
        base = set(json.load(open(BASELINE, encoding="utf-8")))
    except Exception:
        pass
    # exclude the already-merged/published lines from BOTH sides -> the bar starts at 0 and
    # tracks only the remaining review work.
    SENT = {k: sent_count(v) for k, v in corpus.items() if k not in base}
    total = sum(SENT.values())
    print(f"W3 QA pusher: total {total} sentences ({len(SENT)} lines) "
          f"[baseline excluded: {len(base)} lines already merged], every {INTERVAL}s -> {API}")
    last_done = 0
    while True:
        try:
            # only count reviewed keys that are still in the (baseline-excluded) corpus
            done = min(sum(SENT[k] for k in reviewed_keys() if k in SENT), total)
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
