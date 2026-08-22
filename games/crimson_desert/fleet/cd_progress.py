# -*- coding: utf-8 -*-
"""Push the Crimson Desert translation progress live to the hub dashboard (gameId=crimson-desert).

Counted in SENTENCES, with the same splitter every other fleet pusher uses, so all the
dashboards share one unit. DONE = keys in hebrew.json (the merged bank the pull writes);
TOTAL = corpus.json. 60 s loop -> /api/admin/progress.

⚠️ The homepage tab only appears for a game whose catalog row is NOT `availability=planned`
(ProgressDashboard.tsx builds `publicIds` from that filter). Crimson Desert is deliberately still
`planned`, so these snapshots are recorded but stay INVISIBLE on the site — flipping that flag
is an admin/publish decision, not this script's.
"""
import os, sys, json, time, re, glob, subprocess, urllib.request
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
HIST = os.path.join(HERE, "cd_progress_hist.json")
BANKS = os.path.join(HERE, "banks")

GAME_ID = "crimson-desert"            # MUST match the Supabase games row id (the dashboard joins on it)
_STREAM_RE = re.compile(r"_(?:groq|sambanova|nim)\.json$")
INTERVAL = 60
API = "https://hebrew-translation-hub.com"

# POOL MODE: the fleet machines and the volunteer devices all pull from ONE queue, so the
# banks stopped growing. Counting only hebrew.json therefore freezes the site at the
# pre-migration number and reports 0/h on a working fleet — the exact "healthy fleet, dead
# dashboard" shape this pusher exists to avoid. The queue is now the second source.
# דור 3 (תשתית): Turso hard-blocks all reads now (plan quota) - the Worker/Turso path
# is DEAD, so the self-hosted pool is the default, not just an env-var opt-in.
CC_BASE = os.environ.get("CC_BASE") or "https://pool.hebrew-translation-hub.com/cc"
CC_SECRET = "bff947baf4b340ec303dbabd377dd7aaa9f10ebc143ece3e"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")   # Cloudflare 403s the default UA


def pool_stats():
    """(done, remaining, workers) from the queue, or None when it cannot be reached."""
    try:
        body = json.dumps({"game": GAME_ID}).encode("utf-8")
        req = urllib.request.Request(CC_BASE + "/stats", body,
                                     {"x-cc-secret": CC_SECRET, "Content-Type": "application/json",
                                      "User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        return (int(d.get("done", 0) or 0),
                int(d.get("open", 0) or 0) + int(d.get("claimed", 0) or 0),
                int(d.get("workers", 0) or 0))
    except Exception:
        return None


def count_streams(default=9, pool_workers=None):
    """Live stream count. In pool mode that is the number of ACTIVE clients the queue sees
    (fleet machines + volunteer devices); the old bank-file count returns 0 there because a
    pool client writes no bank."""
    if pool_workers:
        return pool_workers
    try:
        n = sum(1 for f in glob.glob(os.path.join(BANKS, "out_*.json"))
                if _STREAM_RE.search(os.path.basename(f)))
        return n if n > 0 else default
    except Exception:
        return default


def model_line(streams):
    return f"תרגום רב לשוני - {streams} זרמים"


def acquire_singleton():
    """One pusher, ever. TWO pushers append samples to the SAME history file, and the rate
    window then reads 0/h on a perfectly healthy fleet - a documented false alarm that has
    sent this project hunting phantom outages more than once. Being a no-op when one is
    already alive is what lets a 5-minute relaunch task exist at all.

    The pid is validated against its COMMAND LINE: Windows recycles pids, so a bare
    "is that pid alive" check can be satisfied by an unrelated process forever.
    """
    lock = os.path.join(HERE, "cd_progress.lock")
    try:
        with open(lock, encoding="utf-8") as fh:
            old = int((fh.read() or "0").strip() or 0)
    except Exception:
        old = 0
    if old and old != os.getpid():
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance Win32_Process -Filter \"ProcessId={old}\").CommandLine"],
                capture_output=True, text=True, timeout=30, errors="replace").stdout or ""
            if "cd_progress" in out:
                print(f"another pusher is already running (pid {old}) - exiting")
                return False
        except Exception:
            pass                      # cannot prove it is alive -> assume it is not
    try:
        with open(lock, "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except OSError:
        pass
    return True


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
    # A clock jump (e.g. around a reboot) can write a FUTURE timestamp -- `now - p[0]` on that
    # point is deeply negative, so it never ages out of the 3900s window and permanently pins
    # t0 to the largest t in the list -> t1<=t0 forever -> rate stuck at 0.0. Drop it outright.
    hist = [p for p in hist if 0 <= now - p[0] <= 3900][-80:]
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
    if not acquire_singleton():
        return 0
    env = _load_env(os.path.join(ROOT, ".env"))
    token = env.get("MONITOR_TOKEN", "")
    if not token:
        print("no MONITOR_TOKEN — exiting"); return 1
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    SENT = {k: sent_count(v) for k, v in corpus.items() if not is_token_only(v)}
    skipped = len(corpus) - len(SENT)
    total = sum(SENT.values())
    print(f"Crimson Desert pusher: total {total} sentences ({len(SENT)} lines; "
          f"{skipped} token-only out of scope), every {INTERVAL}s -> {API}")
    last_done = 0
    while True:
        try:
            bank = json.load(open(BANK, encoding="utf-8"))
            # only in-scope keys count — a banked token-only line is out of the denominator
            # too, so counting it would push `done` past 100%.
            banked = sum(SENT[k] for k in bank if k in SENT)
            # The queue reports a COUNT of finished lines, not which keys they are, so their
            # sentence weight is taken as the average of the lines that are actually in it
            # (corpus minus what is already banked). Self-correcting: if a future merge folds
            # pool results back into hebrew.json, those keys move from the estimate to the
            # exact sum on the very next tick.
            rest = [k for k in SENT if k not in bank]
            avg = (sum(SENT[k] for k in rest) / len(rest)) if rest else 1.0
            done = min(banked, total)
            last_done = done
        except Exception:
            # 🔴 transient read (file mid-write / full disk) must REUSE the last good value.
            # Publishing a 0 poisons the rate window and shows 0/min on a healthy fleet.
            done, avg = last_done, 1.0
        ps = pool_stats()
        if ps:
            pdone, _premaining, pworkers = ps
            done = min(total, int(done + pdone * avg))
            last_done = done
        rate = _rate(done)
        streams = count_streams(pool_workers=(ps[2] if ps else None))
        try:
            st = push(token, done, total, rate, streams)
            print(f"pushed {done}/{total} ({100 * done / max(1, total):.1f}%) "
                  f"rate={int(rate)}/h streams={streams} -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
