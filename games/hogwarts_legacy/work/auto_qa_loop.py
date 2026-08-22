#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""auto_qa_loop.py — autonomous QA-and-re-queue driver for the Hogwarts CC fleet.

Repeats, unattended, until the corpus is clean OR the residual stops shrinking:
  1. wait until the fleet has drained (cc_lines open==0 & claimed==0)
  2. re-pull the currently-queued keys' fresh `out`, merge into work/hebrew.json (backup)
  3. classify with qa_scan's logic; apply the deterministic SAFE_RECOVER fixes
  4. if RETRANS==0 -> DONE. if RETRANS didn't shrink for 2 rounds -> park stuck_keys.json, stop.
     else re-queue the RETRANS keys and loop.

Claude never translates — the fleet redoes the failures (delegate-all-translation).
Idempotent + crash-safe (backups per round, 500-retry on PostgREST). Run in background:
    python auto_qa_loop.py   >> auto_qa_loop.log 2>&1
"""
import json, time, shutil, urllib.request, urllib.parse, urllib.error
from pathlib import Path
import qa_scan as q   # reuse the classifier (try_recover / is_passthrough / regexes)

HERE = Path(__file__).resolve().parent
HE = HERE / "hebrew.json"
URL = "https://mfudkftrluabqlrpkvtj.supabase.co"
GAME = "hogwarts"
POLL_S = 90          # queue poll interval
MAX_ROUNDS = 10
STALL_ROUNDS = 2     # stop if RETRANS unchanged this many rounds


def _key():
    for line in (HERE.parent.parent.parent / "website" / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("SUPABASE_SERVICE_ROLE_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no SUPABASE_SERVICE_ROLE_KEY")


KEY = _key()
H = {"apikey": KEY, "Authorization": "Bearer " + KEY}


def _req(q_, data=None, method=None, extra=None):
    hdr = dict(H)
    if extra:
        hdr.update(extra)
    for a in range(5):
        try:
            r = urllib.request.Request(URL + q_, data=data, method=method, headers=hdr)
            resp = urllib.request.urlopen(r, timeout=60)
            return resp
        except urllib.error.HTTPError as e:
            if e.code in (500, 503) and a < 4:
                time.sleep(3 + a * 3); continue
            raise


def counts():
    out = {}
    for st in ("open", "claimed", "done"):
        resp = _req(f"/rest/v1/cc_lines?game=eq.{GAME}&status=eq.{st}&select=id&limit=1",
                    extra={"Prefer": "count=exact"})
        out[st] = int(resp.headers.get("content-range", "0/0").split("/")[-1])
    return out


def pull(keys):
    fetched = {}
    ks = sorted(keys)
    for i in range(0, len(ks), 100):
        chunk = ks[i:i + 100]
        inlist = ",".join('"' + k.replace('"', '\\"') + '"' for k in chunk)
        q_ = (f"/rest/v1/cc_lines?game=eq.{GAME}&status=eq.done"
              f"&target=in.({urllib.parse.quote(inlist)})&select=target,out")
        for row in json.loads(_req(q_).read()):
            if row["out"]:
                fetched[row["target"]] = row["out"]
    return fetched


def requeue(keys):
    body = json.dumps({"status": "open", "out": None, "worker_id": None,
                       "lease_until": None, "collected": False}).encode()
    for i in range(0, len(keys), 120):
        chunk = keys[i:i + 120]
        inlist = ",".join('"' + k.replace('"', '\\"') + '"' for k in chunk)
        q_ = (f"/rest/v1/cc_lines?game=eq.{GAME}"
              f"&target=in.({urllib.parse.quote(inlist)})&status=eq.done")
        _req(q_, data=body, method="PATCH",
             extra={"Content-Type": "application/json", "Prefer": "return=minimal"})


def classify(he):
    """Return (ok, recover[list of (k,v)], retrans[list of k], passthrough)."""
    ok = passth = 0
    recover, retrans = [], []
    for k, v in he.items():
        if not isinstance(v, str):
            v = json.dumps(v, ensure_ascii=False)
        leak = bool(q.LABEL_LINE.search(v))
        if q.HEB.search(v) and not leak:
            ok += 1; continue
        if leak:
            rec = q.try_recover(v)
            (recover.append((k, rec)) if rec is not None else retrans.append(k))
            continue
        if q.is_passthrough(k, v):
            passth += 1
        elif q.ARB.search(v) or q.LAT.search(v):
            retrans.append(k)
        else:
            passth += 1
    return ok, recover, retrans, passth


def main():
    stall = 0; prev = None
    for rnd in range(1, MAX_ROUNDS + 1):
        # 1. wait for drain
        while True:
            c = counts()
            if c["open"] == 0 and c["claimed"] == 0:
                break
            print(f"[r{rnd}] waiting — open={c['open']} claimed={c['claimed']} done={c['done']}",
                  flush=True)
            time.sleep(POLL_S)
        # 2. pull the currently-queued keys (from the last requeue_keys.json)
        qk = json.loads((HERE / "requeue_keys.json").read_text(encoding="utf-8"))
        fresh = pull(qk) if qk else {}
        he = json.loads(HE.read_text(encoding="utf-8"))
        bak = HE.with_suffix(f".json.bak.auto.{time.strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(HE, bak)
        he.update(fresh)
        # 3. classify + apply safe recover
        ok, recover, retrans, passth = classify(he)
        for k, val in recover:
            he[k] = val
        HE.write_text(json.dumps(he, ensure_ascii=False, indent=1), encoding="utf-8")
        (HERE / "requeue_keys.json").write_text(json.dumps(sorted(retrans), ensure_ascii=False, indent=1),
                                                encoding="utf-8")
        n = len(retrans)
        print(f"[r{rnd}] pulled {len(fresh)} | OK {ok} | recovered {len(recover)} | "
              f"PASSTHROUGH {passth} | RETRANS {n}", flush=True)
        # 4. stop conditions
        if n == 0:
            print(f"[r{rnd}] ✅ DONE — corpus clean (OK {ok}, passthrough {passth}).", flush=True)
            return
        if prev is not None and n >= prev:
            stall += 1
        else:
            stall = 0
        prev = n
        if stall >= STALL_ROUNDS:
            (HERE / "stuck_keys.json").write_text(json.dumps(sorted(retrans), ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
            print(f"[r{rnd}] ⚠️ STALLED at {n} residual (no shrink {STALL_ROUNDS}x) — "
                  f"parked stuck_keys.json for manual/final handling. Stopping.", flush=True)
            return
        requeue(retrans)
        print(f"[r{rnd}] re-queued {n} — waiting for the next fleet pass…", flush=True)
        time.sleep(POLL_S)
    print(f"⚠️ hit MAX_ROUNDS={MAX_ROUNDS}; residual left in requeue_keys.json.", flush=True)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
