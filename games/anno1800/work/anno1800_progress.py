# -*- coding: utf-8 -*-
"""anno1800_progress.py — push Anno 1800 translation progress to the hub homepage.

Standalone 60s loop, run ALONGSIDE anno1800_translate.py (does not touch it).
Reads the live done-count from the translator's own output file (hebrew.json —
which IS the resumable state), computes a rolling lines/hour rate, and upserts
the `anno1800` progress_snapshots row via POST /api/admin/progress with
meta.alive=true so the website's live dashboard surfaces it (the same channel
CP2077 / SM2 use).

Pure read-only w.r.t. translation data — only POSTs progress numbers.

    python anno1800_progress.py            # run the loop (push every 60s)
    python anno1800_progress.py --once     # single push then exit
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
# repo root: games/anno1800/work -> ../../..
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

OUT   = os.path.join(HERE, "hebrew.json")           # {guid: hebrew} — THE resumable state
SPINE = os.path.join(HERE, "..", "extract", "data", "config", "gui", "texts_english.xml")

GAME_ID   = "anno1800"
AI_MODEL  = "gemma-4-31b-it"
GPU_MODEL = "AMD RX 9070"
INTERVAL  = 60
RATE_WINDOW = 1800            # rolling window for lines/hour (30 min)
FALLBACK_TOTAL = 28165        # base GUID count (PIPELINE.md scope)


def _count_total():
    """Translatable total from the spine; FALLBACK_TOTAL if the spine is unreadable."""
    try:
        texts = ET.parse(SPINE).getroot().find("Texts")
        n = 0
        for el in texts.findall("Text"):
            if (el.findtext("GUID") or "").strip() and (el.findtext("Text") or "").strip():
                n += 1
        return n or FALLBACK_TOTAL
    except Exception:
        return FALLBACK_TOTAL


TOTAL = _count_total()


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
    """done-count from hebrew.json. Tolerant of a mid-write file (returns None
    on a transient JSON error — the caller holds the last good count)."""
    try:
        with open(OUT, encoding="utf-8") as f:
            return len(json.load(f))
    except Exception:
        return None


# ── push ───────────────────────────────────────────────────────────────
def push(done, rate):
    if not _TOKEN:
        print("[anno1800_progress] no MONITOR_TOKEN in env/.env — cannot push", flush=True)
        return False
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
        "phaseLabelHe": "תרגום ממשק ודיאלוג",
        "meta": {
            "alive": True,
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
        print(f"[anno1800_progress] HTTP {e.code}: {e.read().decode()[:200]}", flush=True)
        return False
    except Exception as e:                              # pylint: disable=broad-except
        print(f"[anno1800_progress] {type(e).__name__}: {e}", flush=True)
        return False


# ── loop ───────────────────────────────────────────────────────────────
def main():
    once = "--once" in sys.argv
    print(f"[anno1800_progress] api={_API}  token={'set' if _TOKEN else 'MISSING'}  "
          f"total={TOTAL}", flush=True)
    hist = []                # (epoch, done) for the rolling rate
    last_done = 0
    while True:
        try:
            done = count_done()
            # hold the last good count through a transient mid-write read
            done = last_done if done is None else done
            last_done = done

            now = time.time()
            hist.append((now, done))
            while hist and now - hist[0][0] > RATE_WINDOW:
                hist.pop(0)
            rate = 0.0
            if len(hist) >= 2:
                dt = now - hist[0][0]
                if dt > 0:
                    rate = (done - hist[0][1]) / dt * 3600.0

            ok = push(done, rate)
            total = max(TOTAL, done)
            print(f"[{time.strftime('%H:%M:%S')}] {done}/{total} "
                  f"({done / total * 100:.2f}%)  rate={rate:.0f}/h  "
                  f"push={'ok' if ok else 'FAIL'}", flush=True)
        except Exception as e:                          # pylint: disable=broad-except
            print(f"[anno1800_progress] loop error: {type(e).__name__}: {e}", flush=True)

        if once:
            break
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
