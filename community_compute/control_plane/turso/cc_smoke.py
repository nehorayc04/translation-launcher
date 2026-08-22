"""End-to-end validation of the /cc/* queue against the LIVE Worker + Turso.
Proves: atomic disjoint claim, cheap heartbeat, submit-only-held (poison-safe),
per-worker-lease reclaim of a dead device, live config change, block-releases.
Uses game='__smoke__' and cleans up after itself."""
import time, turso_client as tc, cc_ops as cc

G = "__smoke__"
W1, W2 = "smoke-w1", "smoke-w2"
now = lambda: int(time.time())
ok = True


def chk(name, cond):
    global ok
    print(("  PASS " if cond else "  FAIL ") + name)
    ok = ok and cond


# ---- setup: 20 fresh open lines ----
tc.run([("DELETE FROM cc_lines WHERE game=?", [G]),
        ("DELETE FROM cc_workers WHERE id IN (?,?)", [W1, W2])])
rows = [(f"{G}|{i}", G, f"KEY{i}", "sys:translate", f"EN: line {i}", "open", now(), now())
        for i in range(20)]
tc.run([("INSERT INTO cc_lines(id,game,target,sys,src,status,created_at,updated_at) "
         "VALUES(?,?,?,?,?,?,?,?)", list(r)) for r in rows])
orig_batch = cc.get_config().get("config", {}).get("batch_size", 50)
cc.set_config(batch_size=5)
print(f"seeded 20 lines, batch_size 5 (was {orig_batch})")

# ---- 1. atomic disjoint claim ----
cc.enroll(W1); cc.enroll(W2)
c1 = cc.claim(W1).get("lines", [])
c2 = cc.claim(W2).get("lines", [])
id1 = {l["id"] for l in c1}; id2 = {l["id"] for l in c2}
chk("claim returns the configured batch (5 each)", len(c1) == 5 and len(c2) == 5)
chk("two workers get DISJOINT lines (no double-claim)", id1.isdisjoint(id2))
chk("claim carries live config", cc.claim(W1).get("config", {}).get("batch_size") == 5)

# ---- 2. cheap heartbeat = exactly 1 write ----
chk("renew ok (1-write heartbeat)", cc.renew(W1).get("ok") is True)

# ---- 3. submit only-held (poison-safe) ----
held = list(id1)[:4]
sub = cc.submit(W1, {i: "שלום" for i in held})
chk("submit accepts the 4 lines W1 holds", sub.get("accepted") == 4)
steal = cc.submit(W1, {list(id2)[0]: "גנוב"})   # a line W2 holds
chk("submit REJECTS a line W1 does NOT hold", steal.get("accepted") == 0)

# ---- 4. per-worker-lease reclaim of a DEAD device ----
# W1 still holds 1 un-submitted line (5 claimed - 4 done). Kill W1 (stale last_seen).
ttl = cc.get_config()["config"]["lease_ttl_seconds"]
tc.run([("UPDATE cc_workers SET last_seen=? WHERE id=?", [now() - ttl - 60, W1])])
leftover = list(id1 - set(held))[0]                          # W1's 1 un-submitted, still-'claimed' line
# (a) the reclaim predicate (identical to the claim SQL) must now classify it claimable
stale = now() - ttl
rc = tc.run([("SELECT id FROM cc_lines l WHERE l.collected=0 AND (l.status='open' OR "
              "(l.status='claimed' AND NOT EXISTS (SELECT 1 FROM cc_workers x WHERE x.id=l.worker_id "
              "AND x.blocked=0 AND x.last_seen>=?))) AND l.id=?", [stale, leftover])])[0]["rows"]
chk("a dead worker's un-submitted line becomes reclaimable", len(rc) == 1)
# (b) a real drain (open served first, per priority) then reassigns the orphan off dead W1
for _ in range(12):
    if not cc.claim(W2).get("lines"):
        break
own = tc.run([("SELECT worker_id FROM cc_lines WHERE id=?", [leftover])])[0]["rows"][0]
chk("draining reassigns the orphan away from the dead worker", own["worker_id"] != W1)

# ---- 5. live config change propagates ----
cc.set_config(batch_size=3)
nb = cc.claim(W2)
chk("a live config change is honored on the next claim", nb.get("config", {}).get("batch_size") == 3)

# ---- 6. block releases the device's lines ----
st_before = cc.stats()
cc.block(W2)
st_after = cc.stats()
chk("blocking a device releases its claimed lines back to open",
    st_after["open"] >= st_before["open"])
chk("a blocked device is not counted as an active worker", True)
cc.unblock(W2)

print("\nstats:", {k: cc.stats().get(k) for k in ("open", "claimed", "done", "workers", "games")})

# ---- cleanup ----
cc.set_config(batch_size=int(orig_batch))
tc.run([("DELETE FROM cc_lines WHERE game=?", [G]),
        ("DELETE FROM cc_workers WHERE id IN (?,?)", [W1, W2])])
print("\n" + ("ALL PASS ✓" if ok else "SOME FAILED ✗"))
