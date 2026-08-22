#!/usr/bin/env python3
r"""enrich_pool_gender.py — append the derived gender hint to the live /translate pool `context`.

Per GENDER_ORACLE_ROLLOUT.md #3 ("no gender debt"): the pool is already live, so a contributor
translating a line whose English "you" is actually FEMININE would default to masculine and create
debt. This surfaces the Arabic-derived hint (נמען=נקבה/רבים/זכר) in the `context` field, ONLY on
the lines that have a high-confidence hint. Targeted PATCH of `context` alone — never touches
`current_he`/`status`/`claimed_by` (no work lost). Read-only vs game files. Idempotent.

    python enrich_pool_gender.py           # apply
    python enrich_pool_gender.py --dry     # count only
"""
import sys
import json
import argparse
import urllib.request
import urllib.parse
import concurrent.futures as cf
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
EXTRACT = HERE.parent / "extract"
ROOT = HERE.parent.parent.parent


def _env():
    env = {}
    for line in (ROOT / "website" / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k] = v.strip().strip('"').strip("'")
    return env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"]


def main(dry):
    url, key = _env()
    gs = json.loads((EXTRACT / "gender_source.json").read_text(encoding="utf-8"))
    pool = json.loads((EXTRACT / "ct_strings.json").read_text(encoding="utf-8"))
    pool_base = {r["string_key"]: r["context"] for r in pool}  # base context (raw key) per pool line

    # DESIRED = base + the pre-derived (strict+whitelist) hint from gender_source.json.
    desired = {}
    for sk, base in pool_base.items():
        hint = gs.get(sk, {}).get("hint", "")
        desired[sk] = f"{base} · {hint}" if hint else base

    # LIVE state: fetch every pool row that currently carries a hint (context contains 'נמען=').
    marker = urllib.parse.quote("נמען=")
    live = {}
    off = 0
    while True:
        q = (f"/rest/v1/translation_strings?game_id=eq.hogwarts&context=ilike.*{marker}*"
             f"&select=string_key,context&limit=1000&offset={off}")
        r = urllib.request.Request(url + q, headers={"apikey": key, "Authorization": "Bearer " + key})
        rows = json.loads(urllib.request.urlopen(r).read())
        for x in rows:
            live[x["string_key"]] = x["context"]
        if len(rows) < 1000:
            break
        off += 1000

    # PATCH the symmetric difference: strip a stale/FP hint (live-hinted but desired has none/other),
    # and set a new/corrected hint (desired-hinted but live differs).
    todo = []
    for sk in set(live) | {k for k, v in desired.items() if " · " in v}:
        want = desired.get(sk, pool_base.get(sk, ""))
        have = live.get(sk, pool_base.get(sk, ""))   # if not in `live`, it currently = base
        if want != have:
            todo.append((sk, want))
    adds = sum(1 for _, c in todo if " · " in c)
    strips = len(todo) - adds
    print(f"live-hinted now: {len(live)} | desired-hinted: {sum(1 for v in desired.values() if ' · ' in v)}")
    print(f"reconcile PATCHes: {len(todo)}  (set/fix hint: {adds}, strip to base: {strips})")
    if dry:
        for sk, c in todo[:12]:
            print(f"   {sk}  ->  context={c!r}")
        return

    def patch(item):
        sk, ctx = item
        q = ("/rest/v1/translation_strings?game_id=eq.hogwarts&string_key=eq."
             + urllib.parse.quote(sk, safe=""))
        body = json.dumps({"context": ctx}).encode("utf-8")
        r = urllib.request.Request(url + q, data=body, method="PATCH", headers={
            "apikey": key, "Authorization": "Bearer " + key,
            "Content-Type": "application/json", "Prefer": "return=minimal"})
        urllib.request.urlopen(r).read()

    done = 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for _ in ex.map(patch, todo):
            done += 1
            if done % 200 == 0:
                print(f"  patched {done}/{len(todo)}")
    print(f"DONE: enriched {done} context fields")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    main(ap.parse_args().dry)
