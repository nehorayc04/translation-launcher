import json, os, glob
# Equal reslice of the REMAINDER: union every bank -> take what's left in corpus
# (visibility) order -> round-robin across all 21 (machine,provider) streams.
# Disjoint + equal + same visibility mix. Re-runnable. [[fleet-equal-reslice]]
HERE = os.path.dirname(os.path.abspath(__file__))
corpus = json.load(open(os.path.join(HERE, "corpus.json"), encoding="utf-8"))
# 🔴 A REVIEW guard hard-requires Hebrew in the answer (review_ok: `not HEB -> no-hebrew`), so a
# line whose SHIPPING value is deliberately a Latin brand (`NYC`, `SPIDER-BOT`) has NO answer the
# guard can accept: "keep it" is refused, and inventing Hebrew would be the regression. Three
# strikes park it on every machine and the reslice re-serves it forever. These are already
# translated (the decision was "stay Latin") -- treat them as non-work, never as missing.
# [[guard-accept-set-must-contain-a-correct-answer]]
done = set()
for _fn in ("noncontent.json",):
    try:
        done |= set(json.load(open(os.path.join(HERE, _fn), encoding="utf-8")))
    except Exception:
        pass
for f in glob.glob(os.path.join(HERE, "banks", "out_*.json")):
    try:
        done |= set(json.load(open(f, encoding="utf-8")).keys())
    except Exception:
        pass

# 🔴 An EN longer than this cannot be produced inside a provider's output ceiling in ONE
# call, so it is NOT fleet work: leaving it in the shards is what pinned 15 of 21 streams
# at 0 lines/min (each monster times out, earns no strike because a transport failure is
# blameless, and is re-served on every pass forever). Keep them OUT of the round-robin and
# list them separately so a dedicated chunked pass can take them -- never fake-banked.
# A REVIEW never excludes a line for length: it already ships Hebrew, so the worst case is
# "we could not improve it", never "it is missing". Nothing is held back from the round-robin.
MAX_EN_CHARS = 10**9


def _en(v):
    return v if isinstance(v, str) else (v.get("en") or v.get("src") or "")


remainder, oversized = [], []
for k, v in corpus.items():                      # corpus order = visibility
    if k in done:
        continue
    (oversized if len(_en(v)) > MAX_EN_CHARS else remainder).append((k, v))


def _hardness(v):
    # easy plain lines translate instantly; books/multiline reject a lot -> push to the tail
    s = _en(v)
    if "$HandwrittenFont" in s or "<font" in s:
        return 3
    nl = s.count("\r\n") + s.count("\n")
    if nl >= 4 or len(s) > 300:
        return 2
    if len(s) > 140:
        return 1
    return 0


# stable sort by hardness keeps visibility order WITHIN each tier -> easy content first,
# so every worker banks the plain 98% immediately and the hard tail parks at the end.
remainder.sort(key=lambda kv: _hardness(kv[1]))
# 🔑 WHICH MACHINES THIS GAME OWNS — one source of truth, read by the reslice, the push, the
# pull, the watchdog and the dashboard. Two games now share the 7 machines (Skyrim finishing on
# the desktop, CD review on the other six), and a script that still assumes "all 7" would
# either hand a machine a shard for a game it is not running or resurrect the game that left.
MACHINES = ["desktop", "laptop", "vm4", "vm5", "vm", "vm2", "vm3"]
_mf = os.path.join(HERE, "machines.json")
if os.path.exists(_mf):
    MACHINES = json.load(open(_mf, encoding="utf-8"))
PROVIDERS = ["groq", "sambanova", "nim"]
streams = [(m, p) for m in MACHINES for p in PROVIDERS]
# 🔑 COMMUNITY DEVICES ARE STREAMS TOO. A volunteer phone/PC running the app pulls its share
# from the Turso cc queue, so it must be counted in the SAME equal split as the fleet — else
# the device competes for lines already assigned to a machine (duplicate work) or sits idle.
# devices.json = {"streams": N}; each device stream gets its own shard file, and cc_push.py
# seeds those into the queue. N is just a number — raise it as more volunteers connect.
DEVICES = 0
_df = os.path.join(HERE, "devices.json")
if os.path.exists(_df):
    try:
        DEVICES = int(json.load(open(_df, encoding="utf-8")).get("streams", 0))
    except Exception:
        DEVICES = 0
streams += [("device", str(i)) for i in range(DEVICES)]
n = len(streams)
buckets = {s: {} for s in streams}
# ⚠️ round-robin the HARDNESS-SORTED list, so each stream gets the same easy:hard mix. A
# plain slice-by-index would hand one machine the entire book tail.
for i, (k, v) in enumerate(remainder):
    buckets[streams[i % n]][k] = v
print(f"corpus={len(corpus):,}  done={len(done):,}  remainder={len(remainder):,}  "
      f"oversized(excluded)={len(oversized):,}  streams={n}  ~{len(remainder)//n} each")

# 🔴 VALIDATE BEFORE WRITING. The invariants used to run AFTER the dump loop, so a failed
# assert would leave the fleet with half-written shards — and this script is now called
# UNATTENDED from the pull, where nobody is watching the traceback. Check first, write second.
sizes = [len(d) for d in buckets.values()]
seen = set()
for d in buckets.values():
    assert not (seen & d.keys()), "shards OVERLAP"
    seen |= d.keys()
assert len(seen) == len(remainder), f"lost lines: {len(remainder) - len(seen)}"
assert max(sizes) - min(sizes) <= 1, f"uneven: {min(sizes)}..{max(sizes)}"

os.makedirs(os.path.join(HERE, "shards"), exist_ok=True)
for (m, p), d in buckets.items():
    # a device stream's shard is seeded into the cc queue by cc_push.py, not scp'd to a machine
    name = f"corpus_device_{p}.json" if m == "device" else f"corpus_{m}_{p}.json"
    dst = os.path.join(HERE, "shards", name)
    tmp = dst + ".tmp"                       # atomic: never hand a worker a truncated shard
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, dst)
json.dump([k for k, _ in oversized],
          open(os.path.join(HERE, "oversized.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"disjoint + complete: OK  ({min(sizes)}-{max(sizes)} per stream)")
