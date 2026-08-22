import json, os, glob
# Equal reslice of the REMAINDER: union every bank -> take what's left in corpus
# (visibility) order -> round-robin across all 21 (machine,provider) streams.
# Disjoint + equal + same visibility mix. Re-runnable. [[fleet-equal-reslice]]
HERE = os.path.dirname(os.path.abspath(__file__))
corpus = json.load(open(os.path.join(HERE, "corpus.json"), encoding="utf-8"))
done = set()
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
MAX_EN_CHARS = 9000

# 🔴 A line with NO translatable letter once the engine tokens are stripped (`<p
# align='center'>\r\n</p>`, `<img src='img://...'>`) has NO legal output: any Hebrew the model
# invents changes the token multiset, and returning it unchanged trips `no-hebrew`. So the
# guard refuses it forever, the strike counter parks it, and meanwhile it is re-served to a
# stream on every single pass. Measured 2026-08-09: 367 of the 694 lines still outstanding
# were exactly this — more than half the "remaining work" was not work at all. drain_books.py
# writes the list; the reslice keeps them OUT of the round-robin, exactly like `oversized`.
# 🔑 `noncontent.json` is decided by the GAME'S OWN TRANSLATORS, not by a regex: a line that
# every one of the 6-7 shipped professional locales left BYTE-IDENTICAL to the English is a
# Creation-Kit editor identifier, not player-facing text (`dunRannveigQSTBLEEDOUT`,
# `Cubemaps\CaveGreenCube_e.dds`, `xxx`). It carries lowercase letters, so `no-hebrew` can
# never pass and it loops forever. ⚠️ The test must be ALL languages: `(Sharedinfo)` is 6/7
# and `Rrrrraaaaaarrrrr!!!!!` is 3/7 — those ARE content and stay in the fleet.
empty_only = set()
for _fn in ("empty.json", "noncontent.json"):
    try:
        empty_only |= set(json.load(open(os.path.join(HERE, _fn), encoding="utf-8")))
    except Exception:
        pass


def _en(v):
    return v if isinstance(v, str) else (v.get("en") or v.get("src") or "")


remainder, oversized, skipped_empty = [], [], 0
for k, v in corpus.items():                      # corpus order = visibility
    if k in done:
        continue
    if k in empty_only:
        skipped_empty += 1
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
# the desktop, SM2 review on the other six), and a script that still assumes "all 7" would
# either hand a machine a shard for a game it is not running or resurrect the game that left.
MACHINES = ["desktop", "laptop", "vm4", "vm5", "vm", "vm2", "vm3"]
_mf = os.path.join(HERE, "machines.json")
if os.path.exists(_mf):
    MACHINES = json.load(open(_mf, encoding="utf-8"))
PROVIDERS = ["groq", "sambanova", "nim"]
streams = [(m, p) for m in MACHINES for p in PROVIDERS]
n = len(streams)
buckets = {s: {} for s in streams}
# ⚠️ round-robin the HARDNESS-SORTED list, so each stream gets the same easy:hard mix. A
# plain slice-by-index would hand one machine the entire book tail.
for i, (k, v) in enumerate(remainder):
    buckets[streams[i % n]][k] = v
print(f"corpus={len(corpus):,}  done={len(done):,}  remainder={len(remainder):,}  "
      f"oversized(excluded)={len(oversized):,}  markup-only(excluded)={skipped_empty:,}  "
      f"streams={n}  ~{len(remainder)//n} each")

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
    dst = os.path.join(HERE, "shards", f"corpus_{m}_{p}.json")
    tmp = dst + ".tmp"                       # atomic: never hand a worker a truncated shard
    json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, dst)
json.dump([k for k, _ in oversized],
          open(os.path.join(HERE, "oversized.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"disjoint + complete: OK  ({min(sizes)}-{max(sizes)} per stream)")
