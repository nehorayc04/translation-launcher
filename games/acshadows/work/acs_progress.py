# -*- coding: utf-8 -*-
"""acs_progress.py — push AC Shadows translation progress to the hub (TEMPLATE).

>>> COPIED FROM games/spiderman2/work/sm2_progress.py. Adapt: gameId -> the
    Supabase games.id for AC Shadows ('acshadows'), point the done-count read at
    the AC Shadows translator output files, set total to the Oasis line count,
    and update aiModel/gpuModel. Per the Universal Playbook (CLAUDE.md §6). <<<

Original SM2 docstring follows:
sm2_progress.py — push SM2 translation progress to the hub homepage.

Standalone 60s loop, run ALONGSIDE sm2_translate.py (does not touch it).
Reads the live done-count from the translator's own output files
(subtitles_he.json + dialogue_he.json — which ARE the resumable state),
computes a rolling lines/hour rate, and upserts the `spiderman2`
progress_snapshots row via POST /api/admin/progress with meta.alive=true so
the website's live dashboard surfaces it (the same channel CP2077 uses).

Pure read-only w.r.t. translation data — only POSTs progress numbers.

    python sm2_progress.py            # run the loop (push every 60s)
    python sm2_progress.py --once     # single push then exit
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
# repo root: games/spiderman2/work -> ../../..
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

OUT_S = os.path.join(HERE, "subtitles_he.json")   # entries with <ts>
OUT_D = os.path.join(HERE, "dialogue_he.json")     # entries without <ts>

GAME_ID   = "spiderman2"
# Grand translatable total = subtitles 29,184 + dialogue/UI 12,140.
# Verified via `sm2_translate.py --status`: done 12 + remaining 41,312 = 41,324
# (done + remaining is invariant, so this constant is stable for the whole run).
TOTAL     = 41324
AI_MODEL  = "gemma-4-31b-it"
GPU_MODEL = "AMD RX 9070"
INTERVAL  = 60
RATE_WINDOW = 1800            # rolling window for lines/hour (30 min)


# ── env / config ───────────────────────────────────────────────────────
def _load_env(path):
    out = {}
    try:
        for raw in open(path, encoding="utf-8", errors="replace"):
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            v = v.strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k.strip()] = v
    except OSError:
        pass
    return out


_ENV   = _load_env(os.path.join(ROOT, ".env"))
_API   = (os.environ.get("PROGRESS_API_URL") or _ENV.get("PROGRESS_API_URL")
          or "https://hebrew-translation-hub.com").rstrip("/")
_TOKEN = os.environ.get("MONITOR_TOKEN") or _ENV.get("MONITOR_TOKEN")


# ── counting ───────────────────────────────────────────────────────────
def count_done():
    """(subs_done, dial_done). Tolerant of a mid-write file (returns last
    good count on a transient JSON error — the next tick recovers)."""
    def _n(p):
        try:
            with open(p, encoding="utf-8") as f:
                return len(json.load(f))
        except Exception:
            return None
    return _n(OUT_S), _n(OUT_D)


# ── push ───────────────────────────────────────────────────────────────
def push(subs, dial, rate):
    if not _TOKEN:
        print("[sm2_progress] no MONITOR_TOKEN in env/.env — cannot push", flush=True)
        return False
    done  = subs + dial
    total = max(TOTAL, done)
    payload = {
        "gameId":       GAME_ID,
        "phase":        "translation",
        "processed":    done,
        "total":        total,
        "ratePerHour":  int(rate),
        "unit":         "שורות",
        "gpuModel":     GPU_MODEL,
        "aiModel":      AI_MODEL,
        "phaseLabelHe": "תרגום כתוביות ודיאלוג",
        "meta": {
            "alive": True,
            "subs":  subs,
            "dial":  dial,
            "subsTotal": 29184,
            "dialTotal": 12140,
        },
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{_API}/api/admin/progress",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_TOKEN}",
            "Content-Type":  "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status < 400
    except urllib.error.HTTPError as e:
        print(f"[sm2_progress] HTTP {e.code}: {e.read().decode()[:200]}", flush=True)
        return False
    except Exception as e:                              # pylint: disable=broad-except
        print(f"[sm2_progress] {type(e).__name__}: {e}", flush=True)
        return False


# ── loop ───────────────────────────────────────────────────────────────
def main():
    once = "--once" in sys.argv
    print(f"[sm2_progress] api={_API}  token={'set' if _TOKEN else 'MISSING'}  "
          f"total={TOTAL}", flush=True)
    hist = []                # (epoch, done) for the rolling rate
    last_subs = last_dial = 0
    while True:
        try:
            subs, dial = count_done()
            # hold the last good count through a transient mid-write read
            subs = last_subs if subs is None else subs
            dial = last_dial if dial is None else dial
            last_subs, last_dial = subs, dial
            done = subs + dial

            now = time.time()
            hist.append((now, done))
            while hist and now - hist[0][0] > RATE_WINDOW:
                hist.pop(0)
            rate = 0.0
            if len(hist) >= 2:
                dt = now - hist[0][0]
                if dt > 0:
                    rate = (done - hist[0][1]) / dt * 3600.0

            ok = push(subs, dial, rate)
            total = max(TOTAL, done)
            print(f"[{time.strftime('%H:%M:%S')}] {done}/{total} "
                  f"({done / total * 100:.2f}%)  subs={subs} dial={dial}  "
                  f"rate={rate:.0f}/h  push={'ok' if ok else 'FAIL'}", flush=True)
        except Exception as e:                          # pylint: disable=broad-except
            print(f"[sm2_progress] loop error: {type(e).__name__}: {e}", flush=True)

        if once:
            break
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
