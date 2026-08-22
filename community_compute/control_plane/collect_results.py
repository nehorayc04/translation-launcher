# -*- coding: utf-8 -*-
"""OPERATOR-ONLY — pull finished translations back out of the queue.

Reads every `cc_jobs` row that a volunteer finished (status='done', not yet
collected), merges their {id: hebrew} into one output file, and marks them
collected so a re-run only pulls new work.

The results are UNTRUSTED community output — feed the merged file through the
project's normal QA gate + admin approval before it touches the real corpus.

Usage:
    python collect_results.py --out results.json [--game <id>] [--mark]
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SUPABASE_URL = "https://mfudkftrluabqlrpkvtj.supabase.co"


def _service_key():
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not key:
        env = os.path.join(REPO, "website", ".env")
        if os.path.exists(env):
            for line in open(env, encoding="utf-8"):
                if line.strip().startswith("SUPABASE_SERVICE_ROLE_KEY"):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        sys.exit("SUPABASE_SERVICE_ROLE_KEY not set (env or website/.env)")
    return key


def _get(path, key):
    req = urllib.request.Request(
        SUPABASE_URL + "/rest/v1/" + path,
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())


def _patch_collected(ids, key):
    if not ids:
        return
    q = "cc_jobs?id=in.(" + ",".join(ids) + ")"
    req = urllib.request.Request(
        SUPABASE_URL + "/rest/v1/" + q,
        data=json.dumps({"collected": True}).encode(), method="PATCH",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"})
    urllib.request.urlopen(req, timeout=60).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="cc_results.json")
    ap.add_argument("--game", default="")
    ap.add_argument("--mark", action="store_true", help="mark rows collected so a re-run skips them")
    a = ap.parse_args()
    key = _service_key()

    flt = "status=eq.done&collected=eq.false"
    if a.game:
        flt += "&game=eq." + urllib.parse.quote(a.game)
    rows = _get(f"cc_jobs?{flt}&select=id,target,out&limit=100000", key)

    merged, seen_ids = {}, []
    for r in rows:
        seen_ids.append(str(r["id"]))
        for k, v in (r.get("out") or {}).items():
            merged[str(k)] = v
    json.dump(merged, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"collected {len(rows)} jobs -> {len(merged)} lines -> {a.out}")
    if a.mark:
        for i in range(0, len(seen_ids), 200):
            _patch_collected(seen_ids[i:i + 200], key)
        print(f"marked {len(seen_ids)} jobs collected")
    else:
        print("(dry: pass --mark to flag these collected so the next run skips them)")


if __name__ == "__main__":
    main()
