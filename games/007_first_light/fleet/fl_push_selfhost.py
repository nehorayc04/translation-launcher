"""Seed 007 First Light work into the SELF-HOSTED cc_server (root@10.0.0.20:/opt/cc-pool/),
the SAME queue table (`cc_lines`) crimson-desert's cc_worker.py fleet already claims from.

game='007-first-light' keeps every row queryable/collectible separately from crimson-desert
(cc_pull_selfhost.py-style scripts always filter `WHERE game=?`) — nothing merges between the
two games' banks. `sys`/`src` are baked in AT SEED TIME from fl_nim's OWN system prompt +
payload builder, so a claimed line carries the correct 007 context wherever it lands.

SYNCs rather than blindly inserting: inserts what's missing, drops queued-but-unclaimed rows
that are no longer work (banked meanwhile) — never a row a worker currently holds.

Usage:  python fl_push_selfhost.py [--dry]
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fl_nim                                    # noqa: E402  (main-guarded: safe to import)

GAME = "007-first-light"
HOST = "root@10.0.0.20"
SYS = fl_nim.S1 + ("\nGame rules:\n" + "\n".join(fl_nim._RULES) if fl_nim._RULES else "")
CORPUS = os.path.join(HERE, "corpus.json")
BANK = os.path.join(HERE, "hebrew.json")


def dbexec(statements):
    payload = json.dumps({"statements": statements}).encode("utf-8")
    p = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
         "-o", "ConnectTimeout=15", HOST, "python3 /opt/cc-pool/dbexec.py"],
        input=payload, capture_output=True, timeout=180)
    if p.returncode != 0:
        raise SystemExit(f"dbexec failed: {p.stderr.decode(errors='replace')[:500]}")
    out = json.loads(p.stdout.decode("utf-8"))
    if "error" in out:
        raise SystemExit(f"dbexec sql error: {out['error']}")
    return out["results"]


def remainder_lines():
    corpus = json.load(open(CORPUS, encoding="utf-8"))
    banked = set()
    if os.path.exists(BANK):
        try:
            banked = set(json.load(open(BANK, encoding="utf-8")).keys())
        except Exception:
            pass
    out, parked = {}, 0
    for k, v in corpus.items():
        if k in banked:
            continue
        en = fl_nim._en(v).strip()
        if en and not fl_nim.STRUCT.sub("", en).strip():
            parked += 1                          # token-only: no legal answer exists
            continue
        out[k] = v
    print(f"corpus={len(corpus):,}  banked={len(banked):,}  token-only={parked:,}"
          f"  -> remainder {len(out):,}")
    return out


def main():
    dry = "--dry" in sys.argv
    want = remainder_lines()
    if not want:
        print("nothing to seed (corpus fully banked)")
        return
    ids = {f"{GAME}|{k}": k for k in want}

    have = {r["id"]: r["status"] for r in dbexec(
        [["SELECT id, status FROM cc_lines WHERE game=? AND collected=0", [GAME]]])[0]["rows"]}
    add = [i for i in ids if i not in have]
    drop = [i for i, st in have.items() if i not in ids and st == "open"]
    print(f"want={len(want):,}  in queue={len(have):,}  -> insert {len(add):,}, drop {len(drop):,}")
    if dry:
        print("(dry run)")
        return

    now = int(time.time())
    for i in range(0, len(drop), 400):
        grp = drop[i:i + 400]
        dbexec([[f"DELETE FROM cc_lines WHERE id IN ({','.join('?' * len(grp))})", grp]])

    cols = "id,game,target,sys,src,status,created_at,updated_at"
    ph = "(" + ",".join(["?"] * 8) + ")"
    ROWS_PER_STMT = 100
    for i in range(0, len(add), ROWS_PER_STMT):
        grp = add[i:i + ROWS_PER_STMT]
        args = []
        for cid in grp:
            key = ids[cid]
            src = json.dumps(fl_nim._payload(want[key]), ensure_ascii=False)
            args += [cid, GAME, key, SYS, src, "open", now, now]
        stmt = (f"INSERT INTO cc_lines({cols}) VALUES "
                + ",".join([ph] * len(grp)) + " ON CONFLICT(id) DO NOTHING", args)
        dbexec([stmt])
        print(f"  seeded {min(i + len(grp), len(add)):,}/{len(add):,}")

    st = dbexec([["SELECT status, COUNT(*) n FROM cc_lines WHERE game=? AND collected=0 "
                  "GROUP BY status", [GAME]]])[0]["rows"]
    print("queue now:", {r["status"]: r["n"] for r in st})


if __name__ == "__main__":
    main()
