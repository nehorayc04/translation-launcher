"""Pull the DEVICE stream's finished lines out of the cc queue into the fleet's banks.

Volunteer output is UNTRUSTED, so every line goes through the shared QA gate
(cc_collect.classify): clean lines land in `banks/out_device.json` — which the
existing pull/reslice already treat as "done" — and defective ones are reset to
'open' in the queue so a device redoes them. Nothing defective reaches the build.

Run it alongside pull_cd.sh (or from it).  Usage: python cc_pull.py [--apply]
"""
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..",
                                "community_compute", "control_plane", "turso"))

import cc_collect as qa                           # noqa: E402  (the ONE QA gate)
import turso_client as tc                         # noqa: E402

GAME = "crimson-desert"
BANK = os.path.join(HERE, "banks", "out_device.json")


def main():
    apply = "--apply" in sys.argv
    rows = tc.run([("SELECT id, target, out, src FROM cc_lines "
                    "WHERE game=? AND status='done' AND collected=0", [GAME])])[0]["rows"]
    if not rows:
        print("device queue: nothing finished yet")
        return
    good, requeue, counts = {}, [], {}
    for r in rows:
        # the QA gate compares tokens against the SOURCE — here src is the JSON payload,
        # so compare against its 'en' (the text the device was actually asked to translate)
        try:
            src_en = json.loads(r["src"]).get("en", "")
        except Exception:
            src_en = r["src"] or ""
        verdict, why, val = qa.classify(r["out"], src_en)
        k = f"{verdict}:{why}" if why else verdict
        counts[k] = counts.get(k, 0) + 1
        (good.__setitem__(r["target"], val) if verdict in ("ok", "recover", "passthrough")
         else requeue.append(r["id"]))
    for k in sorted(counts):
        print(f"  {k:<26} {counts[k]:>6,}")
    print(f"  -> accept {len(good):,}   requeue {len(requeue):,}")
    if not apply:
        print("(dry-run — pass --apply to write the bank + re-queue the defective)")
        return

    os.makedirs(os.path.dirname(BANK), exist_ok=True)
    cur = {}
    if os.path.exists(BANK):
        try:
            cur = json.load(open(BANK, encoding="utf-8"))
        except Exception:
            cur = {}
    cur.update(good)
    tmp = BANK + ".tmp"                       # atomic: the pull/reslice read this file
    json.dump(cur, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, BANK)
    print(f"banks/out_device.json -> {len(cur):,} lines")

    now = int(time.time())
    ids = [r["id"] for r in rows if r["target"] in good]
    for i in range(0, len(ids), 400):
        g = ids[i:i + 400]
        tc.run([(f"UPDATE cc_lines SET collected=1, updated_at={now} "
                 f"WHERE id IN ({','.join('?' * len(g))})", g)])
    for i in range(0, len(requeue), 400):
        g = requeue[i:i + 400]
        tc.run([(f"UPDATE cc_lines SET status='open', out=NULL, worker_id=NULL, "
                 f"lease_until=NULL, updated_at={now} WHERE id IN ({','.join('?' * len(g))})", g)])
    print(f"marked {len(ids):,} collected; re-queued {len(requeue):,}")


if __name__ == "__main__":
    main()
