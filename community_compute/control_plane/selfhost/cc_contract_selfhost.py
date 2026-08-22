#!/usr/bin/env python3
"""
CONTRACT test — replays the EXACT calls the shipped clients make.

Derived line-by-line from community_compute/android/lib/client.dart and
community_compute/desktop/client.py. A field the Dart code reads but the server
does not return fails SILENTLY in the app (a null becomes "no work", "not
blocked", "0 accepted"), so the only safe check is to assert every field those
clients actually touch.

If this passes, migrating an app is a BASE-URL change and nothing else.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("CC_BASE", "http://10.0.0.20:8787/cc")
SECRET = os.environ.get("CC_SECRET", "")
GAME = "__contract__"
WID = "contract-device-01"

_ok = _fail = 0


def check(name, cond, extra=""):
    global _ok, _fail
    if cond:
        _ok += 1
        print(f"  PASS  {name}")
    else:
        _fail += 1
        print(f"  FAIL  {name}   {extra}")


def cc(op, body):
    """Exactly what _cc() in client.dart does: POST + json + the two headers."""
    req = urllib.request.Request(f"{BASE}/{op}", data=json.dumps(body).encode(), method="POST")
    req.add_header("x-cc-secret", SECRET)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Dart/3.4 (dart:io)")
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def sql(stmt):
    return subprocess.run(["ssh", "-o", "ConnectTimeout=15", "root@10.0.0.20",
                           "python3 /opt/cc-pool/sqlexec.py"],
                          input=stmt, capture_output=True, text=True)


def main():
    if not SECRET:
        print("set CC_SECRET", file=sys.stderr)
        return 2

    now = int(time.time())
    sql(f"DELETE FROM cc_lines WHERE game='{GAME}';DELETE FROM cc_workers WHERE id='{WID}';" +
        ";".join(
            f"INSERT INTO cc_lines(id,game,target,sys,src,status,created_at,updated_at) "
            f"VALUES('{GAME}|line{i}','{GAME}','ui:key_{i}',"
            f"'תרגם לעברית תקינה','EN: Save Game\nAR: حفظ اللعبة','open',{now},{now})"
            for i in range(80)))

    print("== enroll (client.dart :: enroll) ==")
    s, m = cc("enroll", {"worker": WID, "platform": "android"})
    check("status 200", s == 200, s)
    check("reads m['blocked']", "blocked" in m, list(m))
    check("reads m['config']", isinstance(m.get("config"), dict), m.get("config"))
    cfg = m["config"]
    check("config has heartbeat_seconds", isinstance(cfg.get("heartbeat_seconds"), int), cfg)
    check("config has lease_ttl_seconds", isinstance(cfg.get("lease_ttl_seconds"), int), cfg)
    check("config has batch_size", isinstance(cfg.get("batch_size"), int), cfg)
    check("config has max_inflight", isinstance(cfg.get("max_inflight"), int), cfg)
    check("ttl EXCEEDS heartbeat (else a live device is reclaimed)",
          cfg["lease_ttl_seconds"] > cfg["heartbeat_seconds"], cfg)

    print("\n== claim (client.dart :: claim) ==")
    s, m = cc("claim", {"worker": WID, "max": 50})
    check("status 200", s == 200, s)
    check("m['lines'] is a list", isinstance(m.get("lines"), list), type(m.get("lines")))
    jobs = m["lines"]
    check("got work", len(jobs) > 0, len(jobs))
    check("every line has id/sys/target/src (the 4 Job fields)",
          all(all(k in j and j[k] is not None for k in ("id", "sys", "target", "src")) for j in jobs),
          jobs[0] if jobs else None)
    check("Hebrew/Arabic survive the round trip",
          any("עברית" in j["sys"] for j in jobs) and any("حفظ" in j["src"] for j in jobs),
          jobs[0]["src"][:40] if jobs else "")
    check("batch never exceeds the live batch_size", len(jobs) <= cfg["batch_size"], len(jobs))
    check("'max' from the client does NOT override the server cap",
          len(jobs) <= cfg["batch_size"], len(jobs))

    print("\n== renew (client.dart :: renew) ==")
    s, m = cc("renew", {"worker": WID})
    check("m['ok'] is true", m.get("ok") is True, m)
    check("config on the heartbeat too (live retune)", isinstance(m.get("config"), dict), m)

    print("\n== submit (client.dart :: submit) ==")
    out = {j["id"]: f"שמור משחק {i}" for i, j in enumerate(jobs[:10])}
    s, m = cc("submit", {"worker": WID, "out": out})
    check("m['accepted'] is numeric", isinstance(m.get("accepted"), (int, float)), m)
    check("accepted == what we sent", m.get("accepted") == len(out), m)
    r = sql(f"SELECT out FROM cc_lines WHERE id='{jobs[0]['id']}';")
    check("Hebrew stored EXACTLY as sent", r.stdout.strip() == "שמור משחק 0", repr(r.stdout.strip()))

    print("\n== release (client.dart :: release) ==")
    s, m = cc("release", {"worker": WID})
    check("m['released'] is numeric", isinstance(m.get("released"), (int, float)), m)
    check("released the rest of the batch", m["released"] == len(jobs) - len(out), m)

    print("\n== the app's failure paths ==")
    s, m = cc("renew", {"worker": "device-that-was-wiped"})
    check("unknown device -> reenroll flag (app re-enrolls itself)", m.get("reenroll") is True, m)
    check("...and NOT a 5xx (the app would treat that as a network error)", s == 200, s)
    s, m = cc("claim", {"worker": "device-that-was-wiped", "max": 50})
    check("claim by unknown device -> reenroll + empty, no crash",
          m.get("reenroll") is True and m.get("lines") == [], m)

    print("\n== a translated line is never handed out twice ==")
    s, m = cc("claim", {"worker": WID, "max": 50})
    again = {j["id"] for j in m["lines"]} & set(out)
    check("already-done lines are NOT re-served", not again, sorted(again)[:3])

    cc("release", {"worker": WID})
    sql(f"DELETE FROM cc_lines WHERE game='{GAME}';DELETE FROM cc_workers WHERE id='{WID}';"
        f"DELETE FROM cc_workers WHERE id='device-that-was-wiped';")
    print(f"\n{_ok} passed, {_fail} failed")
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
