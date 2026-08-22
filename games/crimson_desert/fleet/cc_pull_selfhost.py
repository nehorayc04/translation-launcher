"""Pull finished pool lines from the SELF-HOSTED cc_server (root@10.0.0.20:/opt/cc-pool/)
straight into fleet/hebrew.json.

`cc_pull.py` talks to Turso, which is dead (quota-blocked reads) since the pool migrated
self-hosted. `dbexec.py` on the pool host is the SSH-only operator data path (deliberately
not exposed over HTTP). Same QA gate as cc_pull.py (`cc_collect.classify`) -- untrusted
volunteer output is never merged unchecked.

Usage: python cc_pull_selfhost.py [--apply]
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..",
                                "community_compute", "control_plane", "turso"))
import cc_collect as qa  # noqa: E402  (the ONE QA gate; talks to nothing, pure classify())

GAME = "crimson-desert"
HEBREW_JSON = os.path.join(HERE, "hebrew.json")
HOST = "root@10.0.0.20"


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


def main():
    apply = "--apply" in sys.argv

    res = dbexec([["SELECT id, target, out, src FROM cc_lines "
                    "WHERE game=? AND status='done' AND collected=0", [GAME]]])
    rows = res[0]["rows"]
    print(f"pool: {len(rows):,} done+uncollected rows for {GAME}")
    if not rows:
        return

    good, requeue_ids, counts = {}, [], {}
    for r in rows:
        try:
            src_en = json.loads(r["src"]).get("en", "")
        except Exception:
            src_en = r["src"] or ""
        verdict, why, val = qa.classify(r["out"], src_en)
        k = f"{verdict}:{why}" if why else verdict
        counts[k] = counts.get(k, 0) + 1
        if verdict in ("ok", "recover", "passthrough"):
            good[r["target"]] = val
        else:
            requeue_ids.append(r["id"])

    for k in sorted(counts):
        print(f"  {k:<26} {counts[k]:>6,}")
    print(f"  -> accept {len(good):,}   requeue {len(requeue_ids):,}")

    if not apply:
        print("(dry-run -- pass --apply to write hebrew.json + mark collected + requeue defective)")
        return

    cur = {}
    if os.path.exists(HEBREW_JSON):
        cur = json.load(open(HEBREW_JSON, encoding="utf-8"))
    before = len(cur)
    for target, val in good.items():
        cur[target] = {"he": val, "iss": "ok"}
    tmp = HEBREW_JSON + ".tmp"
    json.dump(cur, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, HEBREW_JSON)
    print(f"fleet/hebrew.json: {before:,} -> {len(cur):,} entries")

    now = int(time.time())
    ids = [r["id"] for r in rows if r["target"] in good]
    for i in range(0, len(ids), 400):
        g = ids[i:i + 400]
        dbexec([[f"UPDATE cc_lines SET collected=1, updated_at={now} "
                 f"WHERE id IN ({','.join('?' * len(g))})", g]])
    for i in range(0, len(requeue_ids), 400):
        g = requeue_ids[i:i + 400]
        dbexec([[f"UPDATE cc_lines SET status='open', out=NULL, worker_id=NULL, "
                 f"lease_until=NULL, updated_at={now} WHERE id IN ({','.join('?' * len(g))})", g]])
    print(f"marked {len(ids):,} collected; re-queued {len(requeue_ids):,} defective")


if __name__ == "__main__":
    main()
