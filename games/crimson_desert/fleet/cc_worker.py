"""A fleet machine as a POOL CLIENT - the same queue the phones and the launcher plugin use.

WHY THIS EXISTS (the shard model's limit):
`cd_nim.py` owns a SHARD - a pre-assigned slice written to the machine by the
reslice. That is efficient while every stream runs, and it is exactly what goes
wrong otherwise: a stream that dies, is throttled, or is simply slower than the
rest strands its slice until a human re-slices, and a fast stream sits idle next
to it. This worker takes the OPPOSITE approach: nothing is pre-assigned, every
client pulls the next lines on demand, and a client that disappears strands
nothing (its lease expires and the lines return to the pool by themselves).
One pool, any number of clients - machines, phones, launcher plugins.

WHAT IS REUSED, DELIBERATELY:
Everything that decides QUALITY is imported from `cd_nim`, never re-implemented:
the New-Era system prompt, the per-provider batch sizing, the token/gender/
copy-EN guard, the glossary injection and the normalizer. The only new code here
is "where does a line come from and where does the answer go" - so a pool line
and a shard line get a byte-identical prompt and a byte-identical guard.

THE PAYLOAD IS THE WHOLE LINE, so a machine needs NO corpus file: the queue
carries `src` (cd_nim's own payload JSON), and `_v_from_payload` inverts it back
into the corpus-shaped dict the guard expects. Same as the phone: the client is
stateless, the pool is the source of truth.

Usage:  python cc_worker.py <provider>        # groq | sambanova | nim
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cd_nim                                    # noqa: E402  (main-guarded: safe to import)

GAME = "crimson-desert"
# The pool moved to the SELF-HOSTED server (gen 3). Turso itself now HARD-BLOCKS all
# reads (plan quota exceeded) - the old Worker/Turso path is DEAD, not a fallback
# option anymore, so the default here is the self-hosted pool. Still overridable via
# the env var for a future migration.
CC_BASE = os.environ.get("CC_BASE") or "https://pool.hebrew-translation-hub.com/cc"
CC_SECRET = "bff947baf4b340ec303dbabd377dd7aaa9f10ebc143ece3e"
# 🔴 Cloudflare answers 403 "error code: 1010" to urllib's DEFAULT User-Agent. The launcher
# plugin shipped for a day showing "no connection to the server" for exactly this reason -
# the pool was up the whole time and every request was being refused at the edge.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

IDLE_SLEEP = 60          # the pool is empty: wait rather than hammer it
ERR_SLEEP = 30
SAMPLES = "samples.jsonl"   # rolling feed of what was just submitted (the dashboard reads it)
SAMPLES_KEEP = 300
HEARTBEAT_S = 240        # < the pool's 300s heartbeat_seconds and far under its 1200s lease
MAX_STRIKES = 3          # a line this worker could not answer 3 times is not worth a 4th


def _cc(op, body, timeout=60):
    req = urllib.request.Request(
        f"{CC_BASE}/{op}", data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"x-cc-secret": CC_SECRET, "Content-Type": "application/json",
                 "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _v_from_payload(src):
    """Rebuild the corpus-shaped value from the queued payload.

    The guard reads `v` directly (`gender_conflict` looks at `v["ag"]`), so the
    two gender fields must be inverted back to their short corpus names - if
    they were dropped, every gendered line would lose its hard fact and the
    guard would silently stop enforcing it.
    """
    try:
        p = json.loads(src) if isinstance(src, str) else dict(src or {})
    except Exception:
        return {"en": str(src or "")}
    inv = {"male": "m", "female": "f", "plural": "pl"}
    v = dict(p)
    for long, short in (("addressee_gender", "ag"), ("speaker_gender", "sg")):
        if long in v:
            g = inv.get(v.pop(long))
            if g:
                v[short] = g
    return v


def start_heartbeat(wid):
    """Renew the lease from a DAEMON THREAD, independent of the work loop.

    🔴 A between-batches heartbeat is not enough: one doomed batch can sit inside the
    provider adapter for many minutes (timeout x retries x key cooldowns), and while it
    does, the worker proves nothing. The queue's steal condition reads the WORKER's
    last_seen, so a slow worker silently loses the 50 lines it is still translating and
    its own submit is then rejected - the work is done twice and thrown away once.
    A thread makes visibility a property of the PROCESS being alive, which is exactly
    the question the lease is asking.
    """
    def loop():
        while True:
            time.sleep(HEARTBEAT_S)
            try:
                if (_cc("renew", {"worker": wid}, timeout=30) or {}).get("reenroll"):
                    _cc("enroll", {"worker": wid, "platform": "windows-fleet"}, timeout=30)
            except Exception:
                pass                      # a missed beat is harmless; the next one is in 4 min
    t = threading.Thread(target=loop, name="cc-heartbeat", daemon=True)
    t.start()
    return t


def _load_skip(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh))
    except Exception:
        return set()


def _save_skip(path, skipped):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(sorted(skipped), fh, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def _record_samples(rows):
    """Append what we just submitted, so the dashboard can still show a live feed.

    In the shard model the dashboard read the BANKS to show recently-translated lines.
    A pool client writes nothing local - the answer goes straight to the queue - so the
    feed went silent. This is the cheapest way to keep it: the worker already holds the
    English and the Hebrew at submit time, so it writes them next to its own log. Purely
    diagnostic; losing the file costs nothing.
    """
    if not rows:
        return
    path = os.path.join(HERE, SAMPLES)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            for key, en, he in rows:
                fh.write(json.dumps({"t": int(time.time()), "prov": cd_nim._PROV,
                                     "id": key, "en": en[:300], "he": he[:300]},
                                    ensure_ascii=False) + "\n")
        # keep it bounded - trim only when it has grown well past the cap, so the common
        # path stays a single append
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > SAMPLES_KEEP * 2:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-SAMPLES_KEEP:])
            os.replace(tmp, path)
    except Exception:
        pass


def main():
    if not cd_nim.acquire_singleton():
        return
    keys = cd_nim.load_keys()
    cd_nim._KEYS, cd_nim._KI = list(keys), 0
    if cd_nim._FLEET is None and (not keys or not keys[0].startswith("nvapi-")):
        print("[X] No key found (keys.json / key.txt / NVIDIA_API_KEY)."); return

    machine = os.environ.get("CD_MACHINE") or os.environ.get("COMPUTERNAME") or "machine"
    wid = f"cd-{machine}-{cd_nim._PROV}".lower()
    try:
        m = _cc("enroll", {"worker": wid, "platform": "windows-fleet"})
        print(f"[pool] enrolled {wid} | server config {m.get('config')}", flush=True)
    except Exception as e:
        print(f"[pool] enroll failed ({e}) - retrying in the loop", flush=True)

    start_heartbeat(wid)
    skip_path = os.path.join(HERE, f"cc_skip_{cd_nim._PROV or 'rr'}.json")
    skipped = _load_skip(skip_path)
    strikes: dict = {}
    if skipped:
        print(f"[pool] {len(skipped)} lines parked from earlier runs", flush=True)

    done_total = 0
    while True:
        try:
            r = _cc("claim", {"worker": wid, "max": 50})
        except Exception as e:
            print(f"[pool] claim failed ({e})", flush=True); time.sleep(ERR_SLEEP); continue
        if r.get("reenroll"):
            # The pool forgot us (pruned as long-gone). Re-enroll and try again - never
            # treat this as "no work", or the machine would idle forever.
            try:
                _cc("enroll", {"worker": wid, "platform": "windows-fleet"})
            except Exception:
                pass
            continue
        lines = r.get("lines") or []
        if not lines:
            # 🔴 RELEASE BEFORE SLEEPING. An empty claim does NOT always mean an empty queue:
            # the server also returns nothing when this worker is already at max_inflight, so
            # a worker that accumulated held lines (a release that failed, a kill mid-claim)
            # would sleep on them forever - and the heartbeat that keeps it healthy is exactly
            # what stops the lease from ever freeing them. Handing them back is what breaks
            # that deadlock, and it costs nothing when there is nothing to hand back.
            try:
                rel = int((_cc("release", {"worker": wid}) or {}).get("released") or 0)
            except Exception:
                rel = 0
            print(f"[pool] nothing to claim{f' (released {rel} held lines)' if rel else ''}"
                  f" - sleeping {IDLE_SLEEP}s (done so far {done_total})", flush=True)
            time.sleep(IDLE_SLEEP); continue

        # id -> corpus key, and the (k, v) pairs the proven batcher/guard expect.
        by_key, todo = {}, []
        for ln in lines:
            key = ln.get("target") or ""
            if not key or key in skipped:
                continue
            by_key[key] = ln["id"]
            todo.append((key, _v_from_payload(ln.get("src"))))
        if not todo:
            # everything we were handed is already parked - give it straight back
            try:
                _cc("release", {"worker": wid})
            except Exception:
                pass
            time.sleep(5)
            continue

        for bi, sub in enumerate(cd_nim.make_batches(todo), 1):
            ok = False
            try:
                res, ok, answered = cd_nim.do_batch(sub)
                if ok and len(sub) > 1:                  # re-ask silent omissions singly
                    for one in [x for x in sub if x[0] not in answered]:
                        try:
                            r1, _o, _s = cd_nim.do_batch([one])
                            res.update(r1)
                        except Exception:
                            pass
            except Exception as e:
                print(f"  [{bi}] batch error ({e}) - continuing", flush=True)
                res = {}
            # A line the guard can never accept (all engine tokens, a source the model always
            # copies back) is otherwise re-served forever: released here, claimed by the next
            # worker, failed again, across the whole fleet. Three misses and THIS worker stops
            # spending calls on it. The strike is only charged when the batch actually came
            # back - a provider that refused us says nothing about the line.
            if ok:
                for k, _v in sub:
                    if k in res:
                        strikes.pop(k, None)
                        continue
                    strikes[k] = strikes.get(k, 0) + 1
                    if strikes[k] >= MAX_STRIKES:
                        skipped.add(k)
                        strikes.pop(k, None)
                if skipped:
                    _save_skip(skip_path, skipped)
            # Submit PER BATCH, not once at the end of the claim: a claim of 50 lines is
            # ~8 calls and a slow provider can push that past a minute, so banking only
            # at the end delays every line behind the slowest batch AND loses the lot if
            # the worker dies mid-claim. The queue counts what has arrived, not what is
            # in flight, so this is also what makes progress visible while it happens.
            out = {by_key[k]: he for k, he in res.items()}
            print(f"  [{bi}] +{len(res)}/{len(sub)}", flush=True)
            # 🔴 HEARTBEAT AFTER EVERY BATCH, submit or not. A claim of 50 lines is 8-16
            # provider calls; when they all fail (a throttled provider) the worker makes NO
            # pool call for the whole claim, and the queue re-serves a claimed line the moment
            # its WORKER has been silent for one lease (the steal condition is the worker's
            # last_seen, not the line's lease_until). So a slow-or-throttled worker silently
            # (a) vanishes from the board and (b) has the lines it is still working on handed
            # to someone else - duplicate work, and its own submit is then rejected. One cheap
            # 1-write call per batch prevents both.
            try:
                if (_cc("renew", {"worker": wid}) or {}).get("reenroll"):
                    _cc("enroll", {"worker": wid, "platform": "windows-fleet"})
            except Exception:
                pass
            if not out:
                continue
            try:
                s = _cc("submit", {"worker": wid, "out": out})
                done_total += int(s.get("accepted") or 0)
                print(f"[pool] submitted {s.get('accepted')}/{len(out)} "
                      f"(total {done_total})", flush=True)
                src = dict(sub)
                _record_samples([(k, cd_nim._en(src.get(k) or {}), he)
                                 for k, he in res.items() if k in src])
            except Exception as e:
                print(f"[pool] submit failed ({e}) - the lease will return them", flush=True)
        # Hand back whatever we could not answer INSTEAD of holding it for the full lease:
        # a rejected line is someone else's chance, not ours to sit on.
        try:
            _cc("release", {"worker": wid})
        except Exception:
            pass


if __name__ == "__main__":
    main()
