#!/usr/bin/env python3
"""
Concurrency + throughput test for the self-hosted pool.

The ONE invariant that must never break under load: a line is handed to exactly
one worker. A remote HTTP pipeline can in principle interleave two claims; a
local SQLite write lock cannot — this proves it with real simultaneous traffic.

Also measures request latency, so we know the box can carry the target device
count before anything is exposed to the internet.
"""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import threading
import time
import urllib.request

BASE = os.environ.get("CC_BASE", "http://10.0.0.20:8787/cc")
SECRET = os.environ.get("CC_SECRET", "")
GAME = "__load__"
WORKERS = int(os.environ.get("LOAD_WORKERS", "12"))
LINES = int(os.environ.get("LOAD_LINES", "600"))


def call(op, body=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(f"{BASE}/{op}", data=data, method="POST")
    req.add_header("x-cc-secret", SECRET)
    req.add_header("Content-Type", "application/json")
    t = time.time()
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode()), time.time() - t


def sql(stmt):
    return subprocess.run(["ssh", "-o", "ConnectTimeout=15", "root@10.0.0.20",
                           "python3 /opt/cc-pool/sqlexec.py"],
                          input=stmt, capture_output=True, text=True)


def main():
    if not SECRET:
        print("set CC_SECRET", file=sys.stderr)
        return 2

    now = int(time.time())
    print(f"seeding {LINES} lines...")
    rows = ";".join(
        f"INSERT OR REPLACE INTO cc_lines(id,game,target,sys,src,status,created_at,updated_at) "
        f"VALUES('{GAME}|k{i}','{GAME}','k{i}','SYS','SRC {i}','open',{now},{now})"
        for i in range(LINES))
    sql(f"DELETE FROM cc_lines WHERE game='{GAME}';{rows};"
        f"DELETE FROM cc_workers WHERE id LIKE 'load%'")

    all_claimed: dict[str, list[str]] = {}
    lat: list[float] = []
    lock = threading.Lock()
    errors: list[str] = []

    def worker(n):
        wid = f"load{n:02d}"
        try:
            _, t = call("enroll", {"worker": wid, "platform": "loadtest"})
            with lock:
                lat.append(t)
            mine: list[str] = []
            for _ in range(6):                       # each device does several cycles
                r, t = call("claim", {"worker": wid})
                with lock:
                    lat.append(t)
                ids = [l["id"] for l in r.get("lines", [])]
                if not ids:
                    break
                mine += ids
                # translate + submit the whole batch, like the real client
                _, t = call("submit", {"worker": wid, "out": {i: "שלום עולם" for i in ids}})
                with lock:
                    lat.append(t)
            with lock:
                all_claimed[wid] = mine
        except Exception as e:
            with lock:
                errors.append(f"{wid}: {e}")

    print(f"launching {WORKERS} concurrent workers...")
    t0 = time.time()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(WORKERS)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    elapsed = time.time() - t0

    seen: dict[str, str] = {}
    dupes = []
    for wid, ids in all_claimed.items():
        for i in ids:
            if i in seen:
                dupes.append((i, seen[i], wid))
            seen[i] = wid

    r = sql(f"SELECT status, COUNT(*) FROM cc_lines WHERE game='{GAME}' GROUP BY status")
    print("\n--- RESULT ---")
    print(f"workers            : {WORKERS}")
    print(f"lines handed out   : {len(seen)} of {LINES}")
    print(f"DUPLICATE lines    : {len(dupes)}  {'<-- INVARIANT BROKEN' if dupes else '(none)'}")
    print(f"errors             : {len(errors)} {errors[:3]}")
    print(f"wall time          : {elapsed:.2f}s")
    if lat:
        lat.sort()
        print(f"latency  median    : {statistics.median(lat)*1000:.0f} ms")
        print(f"latency  p95       : {lat[int(len(lat)*0.95)]*1000:.0f} ms")
        print(f"latency  max       : {max(lat)*1000:.0f} ms")
        print(f"requests           : {len(lat)}  ({len(lat)/elapsed:.1f}/s)")
    print(f"db state           : {r.stdout.strip()}")

    sql(f"DELETE FROM cc_lines WHERE game='{GAME}';DELETE FROM cc_workers WHERE id LIKE 'load%'")
    return 1 if (dupes or errors) else 0


if __name__ == "__main__":
    sys.exit(main())
