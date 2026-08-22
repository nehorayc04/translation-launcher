# -*- coding: utf-8 -*-
"""God of War: Ragnarök — push translation progress to the hub site.

60 s loop → POST /api/admin/progress (MONITOR_TOKEN from the repo-root .env).
The homepage pickActiveSnapshot surfaces the freshest live snapshot.
gameId MUST equal the Supabase games.id row once the game is registered.
"""
import os, sys, json, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EN_F   = os.path.join(HERE, "english.json")
AR_F   = os.path.join(HERE, "arabic.json")
OUT_F  = os.path.join(HERE, "hebrew.json")

GAME_ID  = "gowragnarok"   # MUST match the Supabase games.id (was "godofwar_ragnarok" → no title match)
AI_MODEL = "gemma-4-31b-it"
GPU_MODEL = "AMD RX 9070"
INTERVAL = 60
API = "https://hebrew-translation-hub.com"


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


def scope_total():
    """Shared EN∩AR ids minus dev-meta — the real translatable scope."""
    try:
        en = json.load(open(EN_F, encoding="utf-8"))
        ar = json.load(open(AR_F, encoding="utf-8"))
    except (OSError, ValueError):
        return 48886  # measured fallback
    n = 0
    for k in ar:
        s = en.get(k)
        if s and s.strip() and not s.startswith("Design#") and s not in ("OBSOLETE", "CUT"):
            n += 1
    return n or 48886


def push(token, processed, total):
    body = json.dumps({
        "gameId": GAME_ID, "phase": "translation", "phaseLabelHe": "תרגום",
        "processed": processed, "total": total,
        "meta": {"alive": True}, "aiModel": AI_MODEL, "gpuModel": GPU_MODEL,
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
    total = scope_total()
    while True:
        done = _count(OUT_F)
        try:
            st = push(token, done, total)
            print(f"pushed {done:,}/{total:,} -> {st}")
        except Exception as e:
            print(f"push failed: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
