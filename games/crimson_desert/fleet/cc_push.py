"""Seed work into the Turso cc queue.

TWO modes, and the difference is the whole point:

  (default)  the DEVICE stream's shard - the split-fleet model, where a reslice
             hands every stream an equal share and the device stream's share
             lives in the queue instead of on a machine.

  --all      THE WHOLE REMAINDER - one pool that every client pulls from on
             demand: the machines AND the phones AND the launcher plugin.
             Nothing is pre-assigned, so a fast client simply takes more and a
             client that goes away strands nothing (its lease expires and the
             lines return). This is what "one pool" means; the shard model
             cannot do it, because a shard is a promise made to one machine.

Either way this SYNCs rather than blindly inserting:
  * inserts what is missing,
  * DELETES queued-but-unclaimed lines that are no longer work (banked
    meanwhile, or moved back to a machine) — never a line a client holds.

Prompt fidelity: `sys` and the per-line payload are imported from cd_nim itself,
so a device gets the SAME proven New-Era prompt the fleet uses (zero drift).

Usage:  python cc_push.py [--all] [--dry]
"""
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "..",
                                "community_compute", "control_plane", "turso"))

import cd_nim                                    # noqa: E402  (main-guarded: safe to import)
import turso_client as tc                        # noqa: E402

GAME = "crimson-desert"
SYS = cd_nim.S1 + ("\nGame rules:\n" + "\n".join(cd_nim._RULES) if cd_nim._RULES else "")
ROWS_PER_STMT, STMTS_PER_PIPE = 120, 8


def _en(v):
    return v if isinstance(v, str) else (v.get("en") or "")


def shard_lines():
    """The device's share, MINUS the lines no device can legally answer.

    🔴 A line that is 100% engine tokens (a bare `[EMPTY]`, `%0#`, `<br/>`) is UNWINNABLE:
    translating it breaks the token multiset (the guard rejects) and echoing it reads as
    'not translated' (the guard rejects too) — there is NO accepted answer, so it would
    loop claim->translate->requeue forever and burn the volunteer's quota. cd_nim parks
    exactly these on the fleet side (`tokonly`, cd_nim.py:632); the app has no park logic,
    so the filter must happen HERE, at seed time. Same rule, imported from cd_nim so the
    two can never drift. [[guard-accept-set-must-contain-a-correct-answer]]
    """
    out, parked = {}, 0
    for f in sorted(glob.glob(os.path.join(HERE, "shards", "corpus_device_*.json"))):
        for k, v in json.load(open(f, encoding="utf-8")).items():
            en = _en(v).strip()
            if en and not cd_nim.STRUCT.sub("", en).strip():
                parked += 1
                continue
            out[k] = v
    if parked:
        print(f"  skipped {parked:,} token-only lines (no legal answer exists — not work)")
    return out


def remainder_lines():
    """EVERY line still to do: the corpus minus everything already banked.

    Same definition of "done" as reslice_equal.py (the union of every bank plus
    the deliberate non-content list) - if the two ever disagreed, the pool would
    hand out work the fleet had already finished.
    """
    corpus = json.load(open(os.path.join(HERE, "corpus.json"), encoding="utf-8"))
    done = set()
    for fn in ("noncontent.json", "oversized.json"):
        try:
            done |= set(json.load(open(os.path.join(HERE, fn), encoding="utf-8")))
        except Exception:
            pass
    for f in glob.glob(os.path.join(HERE, "banks", "out_*.json")):
        try:
            done |= set(json.load(open(f, encoding="utf-8")).keys())
        except Exception:
            pass

    out, parked = {}, 0
    for k, v in corpus.items():                  # corpus order = visibility order
        if k in done:
            continue
        en = _en(v).strip()
        if en and not cd_nim.STRUCT.sub("", en).strip():
            parked += 1                          # token-only: no legal answer exists
            continue
        out[k] = v
    print(f"corpus={len(corpus):,}  banked={len(done):,}  token-only={parked:,}"
          f"  -> remainder {len(out):,}")
    return out


def main():
    dry = "--dry" in sys.argv
    want = remainder_lines() if "--all" in sys.argv else shard_lines()
    if not want:
        print("no device shard (set devices.json {\"streams\": N} and re-run reslice_equal.py)")
        return
    ids = {f"{GAME}|{k}": k for k in want}

    have = {r["id"]: r["status"] for r in tc.run(
        [("SELECT id, status FROM cc_lines WHERE game=? AND collected=0", [GAME])])[0]["rows"]}
    add = [i for i in ids if i not in have]
    # only drop what nobody is working on — never yank a line out from under a device
    drop = [i for i, st in have.items() if i not in ids and st == "open"]
    print(f"device shard={len(want):,}  in queue={len(have):,}  -> insert {len(add):,}, drop {len(drop):,}")
    if dry:
        print("(dry run)")
        return

    now = int(time.time())
    for i in range(0, len(drop), 400):
        grp = drop[i:i + 400]
        tc.run([(f"DELETE FROM cc_lines WHERE id IN ({','.join('?' * len(grp))})", grp)])

    cols = "id,game,target,sys,src,status,created_at,updated_at"
    ph = "(" + ",".join(["?"] * 8) + ")"
    for i in range(0, len(add), ROWS_PER_STMT * STMTS_PER_PIPE):
        chunk = add[i:i + ROWS_PER_STMT * STMTS_PER_PIPE]
        stmts = []
        for j in range(0, len(chunk), ROWS_PER_STMT):
            grp = chunk[j:j + ROWS_PER_STMT]
            args = []
            for cid in grp:
                key = ids[cid]
                src = json.dumps(cd_nim._payload(want[key]), ensure_ascii=False)
                args += [cid, GAME, key, SYS, src, "open", now, now]
            stmts.append((f"INSERT INTO cc_lines({cols}) VALUES "
                          + ",".join([ph] * len(grp)) + " ON CONFLICT(id) DO NOTHING", args))
        tc.run(stmts)
        print(f"  seeded {min(i + len(chunk), len(add)):,}/{len(add):,}")

    st = tc.run([("SELECT status, COUNT(*) n FROM cc_lines WHERE game=? AND collected=0 "
                  "GROUP BY status", [GAME])])[0]["rows"]
    print("queue now:", {r["status"]: r["n"] for r in st})


if __name__ == "__main__":
    main()
