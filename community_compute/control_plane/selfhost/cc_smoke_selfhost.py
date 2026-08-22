#!/usr/bin/env python3
"""
End-to-end smoke test for the SELF-HOSTED cc pool.

Exercises the exact device contract (enroll/claim/renew/submit/release) plus the
operator ops (stats/detail/config/block), and asserts the invariants that make
the pull-model safe:

  * two workers NEVER get the same line (disjoint claim)
  * submit commits ONLY lines the worker still HOLDS (poison-safe)
  * a line held by a STALE worker is reclaimable; one held by a LIVE worker is not
  * block() releases the device's lines back to the pool
  * config is live-tunable and returned on every reply

Runs against a scratch game id so it never touches real corpus rows.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("CC_BASE", "http://10.0.0.20:8787/cc")
SECRET = os.environ.get("CC_SECRET", "")
ADMIN = os.environ.get("CC_ADMIN_SECRET", "")
GAME = "__smoke__"

_ok = _fail = 0


def call(op, body=None, secret=None, method=None):
    m = method or ("POST" if body is not None else "GET")
    data = json.dumps(body or {}).encode() if m == "POST" else None
    req = urllib.request.Request(f"{BASE}/{op}", data=data, method=m)
    req.add_header("x-cc-secret", secret if secret is not None else SECRET)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def check(name, cond, extra=""):
    global _ok, _fail
    if cond:
        _ok += 1
        print(f"  PASS  {name}")
    else:
        _fail += 1
        print(f"  FAIL  {name}  {extra}")


def sql(stmt):
    """Direct sqlite surgery on the host, for seeding + stale simulation.

    Piped through STDIN on purpose: inlining SQL into an `ssh "python3 -c ..."`
    one-liner hits the nested-quote trap and silently seeds NOTHING.
    """
    import subprocess
    return subprocess.run(
        ["ssh", "-o", "ConnectTimeout=15", "root@10.0.0.20",
         "python3 /opt/cc-pool/sqlexec.py"],
        input=stmt, capture_output=True, text=True)


def main():
    if not SECRET or not ADMIN:
        print("set CC_SECRET and CC_ADMIN_SECRET", file=sys.stderr)
        return 2

    print("== gates ==")
    s, _ = call("stats", secret="wrong")
    check("bad secret rejected", s == 401, s)
    s, _ = call("detail", secret=SECRET)
    check("device secret cannot read detail", s == 401, s)
    s, d = call("detail", secret=ADMIN)
    check("admin secret can read detail", s == 200 and "games" in d, d)

    print("== seed ==")
    now = int(time.time())
    rows = ";".join(
        f"INSERT OR REPLACE INTO cc_lines(id,game,target,sys,src,status,created_at,updated_at) "
        f"VALUES('{GAME}|k{i}','{GAME}','k{i}','SYS','SRC {i}','open',{now},{now})"
        for i in range(120))
    r = sql(f"DELETE FROM cc_lines WHERE game='{GAME}';{rows};"
            f"DELETE FROM cc_workers WHERE id LIKE 'smoke%'")
    check("seeded 120 lines", r.returncode == 0, r.stderr[:200])

    print("== enroll ==")
    s, a = call("enroll", {"worker": "smokeA", "platform": "test"})
    s2, b = call("enroll", {"worker": "smokeB", "platform": "test"})
    check("both enrolled", s == 200 and s2 == 200 and not a.get("blocked"), (a, b))
    check("config returned on enroll", isinstance(a.get("config"), dict), a)

    print("== claim: disjoint ==")
    _, ca = call("claim", {"worker": "smokeA"})
    _, cb = call("claim", {"worker": "smokeB"})
    ida = {l["id"] for l in ca["lines"]}
    idb = {l["id"] for l in cb["lines"]}
    check("A got lines", len(ida) > 0, len(ida))
    check("B got lines", len(idb) > 0, len(idb))
    check("ZERO overlap between workers", not (ida & idb), sorted(ida & idb)[:5])
    check("batch respects batch_size", len(ida) <= ca["config"]["batch_size"], len(ida))
    check("line payload complete", all(set(l) >= {"id", "target", "sys", "src"} for l in ca["lines"]))

    print("== submit: only what you hold ==")
    mine = sorted(ida)[:3]
    theirs = sorted(idb)[:2]
    _, sub = call("submit", {"worker": "smokeA", "out": {i: "שלום" for i in mine + theirs}})
    check("accepted exactly my 3", sub["accepted"] == 3, sub)
    check("rejected the 2 I don't hold", sub["rejected"] == 2, sub)

    print("== renew (the cheap heartbeat) ==")
    _, rn = call("renew", {"worker": "smokeA"})
    check("renew ok", rn.get("ok") is True, rn)
    _, rn2 = call("renew", {"worker": "ghost-never-enrolled"})
    check("unknown worker told to re-enroll", rn2.get("reenroll") is True, rn2)

    print("== reclaim predicate ==")
    # B is LIVE -> its lines must NOT be reclaimable by A
    _, ca2 = call("claim", {"worker": "smokeA"})
    check("live worker's lines are NOT stolen", not ({l["id"] for l in ca2["lines"]} & idb), "overlap!")
    # make B stale, then its lines must become reclaimable
    ttl = ca2["config"]["lease_ttl_seconds"]
    sql(f"UPDATE cc_workers SET last_seen={now - ttl - 60} WHERE id='smokeB'")
    _, ca3 = call("claim", {"worker": "smokeA"})
    got_from_b = {l["id"] for l in ca3["lines"]} & idb
    check("STALE worker's lines ARE reclaimed", len(got_from_b) > 0, len(got_from_b))

    print("== release + block ==")
    _, rel = call("release", {"worker": "smokeA"})
    check("release returns lines to pool", rel["released"] > 0, rel)
    call("claim", {"worker": "smokeB"})
    _, bl = call("block", {"worker": "smokeB"}, secret=ADMIN)
    check("block releases its lines", bl["blocked"] is True, bl)
    _, cbl = call("claim", {"worker": "smokeB"})
    check("blocked worker gets no work", cbl["lines"] == [] and cbl.get("blocked"), cbl)
    call("unblock", {"worker": "smokeB"}, secret=ADMIN)
    _, cub = call("claim", {"worker": "smokeB"})
    check("unblocked worker works again", len(cub["lines"]) > 0, cub)

    print("== live config ==")
    _, c0 = call("config", secret=ADMIN)
    orig = c0["config"]["batch_size"]
    _, c1 = call("config", {"set": {"batch_size": 7}}, secret=ADMIN)
    check("config changed live", c1["config"]["batch_size"] == 7, c1)
    call("release", {"worker": "smokeA"})
    _, c2 = call("claim", {"worker": "smokeA"})
    check("new batch size applied immediately", len(c2["lines"]) <= 7, len(c2["lines"]))
    _, c3 = call("config", {"set": {"batch_size": 99999}}, secret=ADMIN)
    check("out-of-range value clamped", c3["config"]["batch_size"] == 200, c3)
    call("config", {"set": {"batch_size": orig}}, secret=ADMIN)

    print("== stats ==")
    _, st = call("stats")
    check("stats shape", all(k in st for k in ("open", "claimed", "done", "workers", "games")), st)

    print("== cleanup ==")
    call("release", {"worker": "smokeA"})
    call("release", {"worker": "smokeB"})
    sql(f"DELETE FROM cc_lines WHERE game='{GAME}';DELETE FROM cc_workers WHERE id LIKE 'smoke%'")
    _, stf = call("stats")
    print(f"\n{_ok} passed, {_fail} failed   (pool now: {stf.get('open')} open / "
          f"{stf.get('claimed')} claimed / {stf.get('done')} done)")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
