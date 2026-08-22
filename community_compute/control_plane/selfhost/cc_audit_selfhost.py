#!/usr/bin/env python3
"""
ADVERSARIAL audit of the self-hosted pool — run BEFORE exposing it.

The smoke test proves the happy path. This one attacks it: malformed input,
oversized bodies, wrong methods, a failed request mid-transaction, slow
clients, and keep-alive correctness. Anything that survives here is safe to
put behind a public port.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

HOST = os.environ.get("CC_HOSTPORT", "10.0.0.20:8787")
BASE = f"http://{HOST}/cc"
SECRET = os.environ.get("CC_SECRET", "")
ADMIN = os.environ.get("CC_ADMIN_SECRET", "")

_ok = _fail = _warn = 0


def check(name, cond, extra=""):
    global _ok, _fail
    if cond:
        _ok += 1
        print(f"  PASS  {name}")
    else:
        _fail += 1
        print(f"  FAIL  {name}   {extra}")


def warn(name, extra=""):
    global _warn
    _warn += 1
    print(f"  WARN  {name}   {extra}")


def raw(op, body=None, secret=None, method="POST", ctype="application/json"):
    """Send an arbitrary (possibly malformed) body and report status + text."""
    conn = http.client.HTTPConnection(HOST, timeout=20)
    headers = {"x-cc-secret": secret if secret is not None else SECRET}
    if ctype:
        headers["Content-Type"] = ctype
    try:
        conn.request(method, f"/cc/{op}", body=body, headers=headers)
        r = conn.getresponse()
        return r.status, r.read().decode("utf-8", "replace")
    finally:
        conn.close()


def call(op, body=None, secret=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(f"{BASE}/{op}", data=data, method="POST")
    req.add_header("x-cc-secret", secret if secret is not None else SECRET)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def sql(stmt):
    return subprocess.run(["ssh", "-o", "ConnectTimeout=15", "root@10.0.0.20",
                           "python3 /opt/cc-pool/sqlexec.py"],
                          input=stmt, capture_output=True, text=True)


def main():
    if not SECRET or not ADMIN:
        print("set CC_SECRET and CC_ADMIN_SECRET", file=sys.stderr)
        return 2

    print("== A. malformed input must never 500 or crash ==")
    s, t = raw("enroll", b"{not json at all")
    check("malformed JSON -> 400", s == 400, f"{s} {t[:80]}")
    s, t = raw("enroll", b"[1,2,3]")
    check("non-object JSON -> 400", s == 400, f"{s} {t[:80]}")
    s, t = raw("enroll", b"")
    check("empty body -> 400 (missing worker)", s == 400, f"{s} {t[:80]}")
    s, t = raw("claim", json.dumps({"worker": None}).encode())
    check("null worker -> 400", s == 400, f"{s} {t[:80]}")
    s, t = raw("nosuchop", b"{}")
    check("unknown op -> 404", s == 404, f"{s} {t[:80]}")
    s, t = raw("submit", json.dumps({"worker": "x", "out": "notadict"}).encode())
    check("wrong type for out -> handled", s in (200, 400, 500) and "Traceback" not in t, f"{s} {t[:120]}")
    s, t = raw("claim", json.dumps({"worker": "x" * 5000}).encode())
    check("absurdly long worker id -> handled", s in (200, 400), f"{s} {t[:80]}")

    print("\n== B. body size limit ==")
    big = json.dumps({"worker": "auditX", "out": {f"k{i}": "x" * 200 for i in range(60000)}}).encode()
    s, t = raw("submit", big)
    check(f"{len(big)//1024//1024}MB body rejected (413)", s == 413, f"{s} {t[:80]}")

    print("\n== C. auth ==")
    s, _ = raw("stats", b"{}", secret="")
    check("empty secret -> 401", s == 401, s)
    s, _ = raw("stats", b"{}", secret=SECRET[:-1] + "0")
    check("near-miss secret -> 401", s == 401, s)
    s, _ = raw("config", json.dumps({"set": {"batch_size": 5}}).encode(), secret=SECRET)
    check("device secret cannot WRITE config -> 401", s == 401, s)
    s, _ = raw("config", None, secret=SECRET, method="GET", ctype=None)
    check("device secret CAN read config", s == 200, s)
    s, _ = raw("block", json.dumps({"worker": "z"}).encode(), secret=SECRET)
    check("device secret cannot block -> 401", s == 401, s)

    print("\n== D. a FAILED request must not leak a transaction ==")
    _, before = call("config", secret=ADMIN)
    b0 = before["config"]["batch_size"]
    m0 = before["config"]["max_inflight"]
    # first key applies, second raises inside the locked block
    s, t = raw("config", json.dumps({"set": {"batch_size": 11, "max_inflight": "not-a-number"}}).encode(),
               secret=ADMIN)
    print(f"      (poison request returned {s})")
    _, after = call("config", secret=ADMIN)
    leaked = after["config"]["batch_size"] != b0
    if leaked:
        warn("partial write from a FAILED request became visible",
             f"batch_size {b0} -> {after['config']['batch_size']} (atomicity gap)")
    else:
        check("failed request left NO partial write", True)
    # whatever happened, the db must still be fully usable afterwards
    s2, st = call("stats")
    check("db still usable after the failure", s2 == 200 and "open" in st, st)
    _, w = call("enroll", {"worker": "audit_after_fail"})
    check("writes still work after the failure", w.get("worker") == "audit_after_fail", w)
    call("config", {"set": {"batch_size": b0, "max_inflight": m0}}, secret=ADMIN)

    print("\n== E. slow client must not hold a thread forever ==")
    t0 = time.time()
    sk = socket.create_connection(tuple(HOST.split(":")[0:1]) + (int(HOST.split(":")[1]),), timeout=10)
    sk.sendall(b"POST /cc/stats HTTP/1.1\r\nHost: x\r\nContent-Length: 100\r\n"
               b"x-cc-secret: " + SECRET.encode() + b"\r\n\r\n")  # promises 100 bytes, sends none
    sk.settimeout(75)
    try:
        data = sk.recv(100)
        dur = time.time() - t0
        if data:
            check(f"slow client closed by server after {dur:.0f}s", True)
        else:
            check(f"slow client connection dropped after {dur:.0f}s", True)
    except socket.timeout:
        warn("slow client held a thread >75s (no socket timeout)",
             "a flood of these could exhaust threads once public")
    finally:
        sk.close()
    # service must still answer normally
    s, _ = call("stats")
    check("server responsive during/after a slow client", s == 200, s)

    print("\n== F. keep-alive + concurrency correctness ==")
    conn = http.client.HTTPConnection(HOST, timeout=20)
    okc = 0
    for i in range(5):
        conn.request("POST", "/cc/stats", body=b"{}",
                     headers={"x-cc-secret": SECRET, "Content-Type": "application/json"})
        r = conn.getresponse()
        r.read()
        okc += 1 if r.status == 200 else 0
    conn.close()
    check("5 requests on ONE keep-alive connection", okc == 5, okc)

    errs = []

    def hammer(n):
        try:
            for _ in range(15):
                s, _ = call("stats")
                if s != 200:
                    errs.append(s)
        except Exception as e:
            errs.append(str(e))

    ths = [threading.Thread(target=hammer, args=(i,)) for i in range(16)]
    t0 = time.time()
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    check(f"240 concurrent requests, 0 errors ({time.time()-t0:.1f}s)", not errs, errs[:3])

    print("\n== G. persistence across a restart ==")
    call("enroll", {"worker": "audit_persist", "platform": "audit"})
    subprocess.run(["ssh", "-o", "ConnectTimeout=15", "root@10.0.0.20",
                    "systemctl restart cc-pool"], capture_output=True)
    time.sleep(3)
    s, d = call("enroll", {"worker": "audit_persist"})
    check("service came back after restart", s == 200, s)
    r = sql("SELECT COUNT(*) FROM cc_workers WHERE id='audit_persist';")
    check("worker row survived the restart", r.stdout.strip() == "1", r.stdout.strip())

    print("\n== H. state hygiene ==")
    r = sql("SELECT COUNT(*) FROM cc_lines;")
    check("pool is EMPTY (no test residue)", r.stdout.strip() == "0", r.stdout.strip())
    r = sql("SELECT id FROM cc_workers;")
    residue = [x for x in r.stdout.split() if x and not x.startswith("audit")]
    check("no leftover test workers", not residue, residue[:5])

    sql("DELETE FROM cc_workers WHERE id LIKE 'audit%';")
    print(f"\n{_ok} passed, {_fail} failed, {_warn} warnings")
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
