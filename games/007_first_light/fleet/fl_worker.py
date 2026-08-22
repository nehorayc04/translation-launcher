"""A fleet machine as a POOL CLIENT for 007 First Light — the SAME self-hosted queue
crimson-desert's cc_worker.py uses, on the SAME machines, but scoped to ONLY this game.

WHY A SEPARATE SCRIPT, NOT A PATCH TO cc_worker.py: cc_worker.py drives 21 LIVE crimson-desert
processes across 7 machines mid-run. Rather than touch that running code, this is a standalone
twin that (a) always passes `game="007-first-light"` on every /cc/claim call — the server now
supports that optional filter (cc_server.py op_claim) — so it can NEVER be handed a
crimson-desert line, and (b) imports fl_nim (this game's own system prompt/guard/glossary)
instead of cd_nim. Runs ALONGSIDE the crimson-desert workers on the same idle machines,
using the same provider keys — zero risk to the crimson-desert job, zero context mixing.

Usage:  python fl_worker.py <provider>        # groq | sambanova | nim
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fl_nim                                    # noqa: E402  (main-guarded: safe to import)

GAME = "007-first-light"
CC_BASE = os.environ.get("CC_BASE") or "https://pool.hebrew-translation-hub.com/cc"
CC_SECRET = "bff947baf4b340ec303dbabd377dd7aaa9f10ebc143ece3e"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

IDLE_SLEEP = 60
ERR_SLEEP = 30
SAMPLES = "samples.jsonl"
SAMPLES_KEEP = 300
HEARTBEAT_S = 240
MAX_STRIKES = 3


def _cc(op, body, timeout=60):
    req = urllib.request.Request(
        f"{CC_BASE}/{op}", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"x-cc-secret": CC_SECRET, "Content-Type": "application/json",
                 "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def start_heartbeat(wid):
    def loop():
        while True:
            time.sleep(HEARTBEAT_S)
            try:
                if (_cc("renew", {"worker": wid}, timeout=30) or {}).get("reenroll"):
                    _cc("enroll", {"worker": wid, "platform": "windows-fleet"}, timeout=30)
            except Exception:
                pass
    t = threading.Thread(target=loop, name="fl-heartbeat", daemon=True)
    t.start()
    return t


def _load_skip(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh))
    except Exception:
        return set()


def _save_skip(path, skipped):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(sorted(skipped), fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def _record_samples(rows):
    if not rows:
        return
    path = os.path.join(HERE, SAMPLES)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            for key, en, he in rows:
                fh.write(json.dumps({"t": int(time.time()), "prov": fl_nim._PROV,
                                     "id": key, "en": en[:300], "he": he[:300]},
                                    ensure_ascii=False) + "\n")
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > SAMPLES_KEEP * 2:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-SAMPLES_KEEP:])
            os.replace(tmp, path)
    except Exception:
        pass


def main():
    if not fl_nim.acquire_singleton():
        return
    keys = fl_nim.load_keys()
    fl_nim._KEYS, fl_nim._KI = list(keys), 0
    if fl_nim._FLEET is None and (not keys or not keys[0].startswith("nvapi-")):
        print("[X] No key found (keys.json / key.txt / NVIDIA_API_KEY)."); return

    machine = os.environ.get("CD_MACHINE") or os.environ.get("COMPUTERNAME") or "machine"
    wid = f"fl-{machine}-{fl_nim._PROV}".lower()
    try:
        m = _cc("enroll", {"worker": wid, "platform": "windows-fleet"})
        print(f"[pool] enrolled {wid} | server config {m.get('config')}", flush=True)
    except Exception as e:
        print(f"[pool] enroll failed ({e}) - retrying in the loop", flush=True)

    start_heartbeat(wid)
    skip_path = os.path.join(HERE, f"fl_skip_{fl_nim._PROV or 'rr'}.json")
    skipped = _load_skip(skip_path)
    strikes: dict = {}
    if skipped:
        print(f"[pool] {len(skipped)} lines parked from earlier runs", flush=True)

    done_total = 0
    while True:
        try:
            r = _cc("claim", {"worker": wid, "max": 50, "game": GAME})
        except Exception as e:
            print(f"[pool] claim failed ({e})", flush=True); time.sleep(ERR_SLEEP); continue
        if r.get("reenroll"):
            try:
                _cc("enroll", {"worker": wid, "platform": "windows-fleet"})
            except Exception:
                pass
            continue
        lines = r.get("lines") or []
        if not lines:
            try:
                rel = int((_cc("release", {"worker": wid}) or {}).get("released") or 0)
            except Exception:
                rel = 0
            print(f"[pool] nothing to claim{f' (released {rel} held lines)' if rel else ''}"
                  f" - sleeping {IDLE_SLEEP}s (done so far {done_total})", flush=True)
            time.sleep(IDLE_SLEEP); continue

        by_key, todo = {}, []
        for ln in lines:
            key = ln.get("target") or ""
            if not key or key in skipped:
                continue
            by_key[key] = ln["id"]
            try:
                v = json.loads(ln.get("src") or "{}")
            except Exception:
                v = {"en": str(ln.get("src") or "")}
            todo.append((key, v))
        if not todo:
            try:
                _cc("release", {"worker": wid})
            except Exception:
                pass
            time.sleep(5)
            continue

        for bi, sub in enumerate(fl_nim.make_batches(todo), 1):
            ok = False
            try:
                res, ok, answered = fl_nim.do_batch(sub)
                if ok and len(sub) > 1:
                    for one in [x for x in sub if x[0] not in answered]:
                        try:
                            r1, _o, _s = fl_nim.do_batch([one])
                            res.update(r1)
                        except Exception:
                            pass
            except Exception as e:
                print(f"  [{bi}] batch error ({e}) - continuing", flush=True)
                res = {}
            if ok:
                for k, _v in sub:
                    if k in res:
                        strikes.pop(k, None)
                        continue
                    strikes[k] = strikes.get(k, 0) + 1
                    if strikes[k] >= MAX_STRIKES:
                        skipped.add(k)
                        strikes.pop(k, None)
                if skipped:
                    _save_skip(skip_path, skipped)
            out = {by_key[k]: he for k, he in res.items()}
            print(f"  [{bi}] +{len(res)}/{len(sub)}", flush=True)
            try:
                if (_cc("renew", {"worker": wid}) or {}).get("reenroll"):
                    _cc("enroll", {"worker": wid, "platform": "windows-fleet"})
            except Exception:
                pass
            if not out:
                continue
            try:
                s = _cc("submit", {"worker": wid, "out": out})
                done_total += int(s.get("accepted") or 0)
                print(f"[pool] submitted {s.get('accepted')}/{len(out)} "
                      f"(total {done_total})", flush=True)
                src = dict(sub)
                _record_samples([(k, fl_nim._en(src.get(k) or {}), he)
                                 for k, he in res.items() if k in src])
            except Exception as e:
                print(f"[pool] submit failed ({e}) - the lease will return them", flush=True)
        try:
            _cc("release", {"worker": wid})
        except Exception:
            pass


if __name__ == "__main__":
    main()
