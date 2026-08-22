#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""requeue_fleet.py — reset the QA-failed Hogwarts cc_lines rows to 'open' so the
community-compute fleet redoes them (delegate-all-translation: Claude never
translates; the fleet does). Reads work/requeue_keys.json (from qa_scan.py).

Non-destructive: the current (bad) `out` is already preserved in work/hebrew.json
+ its .bak; here we clear out/worker/lease and flip status back to 'open'. The
running fleet re-claims them; a future collect re-pulls only the fresh output.

    python requeue_fleet.py --dry      # count only
    python requeue_fleet.py            # apply
"""
import argparse, json, time, urllib.request, urllib.parse, urllib.error
from pathlib import Path


def _send(req):
    """PostgREST 500/503s transiently while its schema cache reloads — retry."""
    for a in range(4):
        try:
            return urllib.request.urlopen(req, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code in (500, 503) and a < 3:
                time.sleep(3 + a * 2); continue
            raise

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
URL = "https://mfudkftrluabqlrpkvtj.supabase.co"
GAME = "hogwarts"
BATCH = 120


def _key():
    for line in (REPO / "website" / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("SUPABASE_SERVICE_ROLE_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("SUPABASE_SERVICE_ROLE_KEY not in website/.env")


def main(dry):
    key = _key()
    keys = json.loads((HERE / "requeue_keys.json").read_text(encoding="utf-8"))
    print(f"re-queue {len(keys)} lines (game={GAME}) in batches of {BATCH}")
    if dry:
        for k in keys[:8]:
            print("  ", k)
        return
    hdr = {"apikey": key, "Authorization": "Bearer " + key,
           "Content-Type": "application/json", "Prefer": "return=minimal"}
    body = json.dumps({"status": "open", "out": None, "worker_id": None,
                       "lease_until": None, "collected": False}).encode()
    done = 0
    for i in range(0, len(keys), BATCH):
        chunk = keys[i:i + BATCH]
        inlist = ",".join('"' + k.replace('"', '\\"') + '"' for k in chunk)
        q = (f"/rest/v1/cc_lines?game=eq.{GAME}"
             f"&target=in.({urllib.parse.quote(inlist)})&status=eq.done")
        req = urllib.request.Request(URL + q, data=body, method="PATCH", headers=hdr)
        _send(req)
        done += len(chunk)
        if done % 600 == 0 or done == len(keys):
            print(f"  re-queued {done}/{len(keys)}")
    print(f"DONE: {done} lines reset to open — the fleet will re-translate them.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    main(ap.parse_args().dry)
