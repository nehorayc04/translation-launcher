#!/usr/bin/env python3
"""Broad scan: decode every small/medium resource in a v50 forge, tally FADE9F44
loc records by (nameHash, script), AND independently flag any resource whose
decoded bytes contain a real Arabic-letter run (in case Arabic loc uses another
tag). Finds which nameHash holds the Arabic slot."""
import importlib.util, os, sys, struct, json, time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "acshadows", "tools"))
os.environ.setdefault("ACS_OODLE_DLL", r"C:\Games\Battlefield 6\oo2core_9_win64.dll")
from acs_oodle import Oodle

def _load(name):
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py")
    s = importlib.util.spec_from_file_location(name, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
L = _load("acbf_loc"); AF = _load("acbf_forge")


def real_arabic_run(d, run=5):
    n = len(d) - 1; i = 0
    while i < n - run * 2:
        if d[i + 1] == 0x06 and 0x21 <= d[i] <= 0x4a:
            k = 0
            while i + k * 2 + 1 < n:
                lo, hi = d[i + k * 2], d[i + k * 2 + 1]
                if hi == 0x06 and lo <= 0x52: k += 1
                elif hi == 0x00 and lo == 0x20: k += 1
                else: break
            if k >= run: return True
            i += (k + 1) * 2
        else: i += 1
    return False


def main():
    fn = sys.argv[1]
    maxsize = int(sys.argv[2], 0) if len(sys.argv) > 2 else 2_000_000
    o = Oodle()
    info = AF.parse(fn); recs = info["recs"]
    print(f"START {os.path.basename(fn)} count={len(recs)} maxsize=0x{maxsize:x}", flush=True)
    hash_script = defaultdict(Counter)
    arab_hash = Counter()
    hb = open("/tmp/acbf_hb.txt", "w")
    t0 = time.time(); f = open(fn, "rb"); probed = 0; withloc = 0
    for n, r in enumerate(recs):
        if r["size"] < 40 or r["size"] > maxsize:
            continue
        probed += 1
        hb.seek(0); hb.write(f"{n} {probed}\n"); hb.flush()
        if probed % 10000 == 0:
            print(f"  probed {probed} ({n}/{len(recs)})  locHashes={len(hash_script)} "
                  f"arabHashes={len(arab_hash)} ({time.time()-t0:.0f}s)", flush=True)
        f.seek(r["offset"]); blob = f.read(r["size"])
        if blob[:4] != b"\x33\xaa\xfb\x57":
            continue
        try:
            dec = L.decode_blob(blob, o)
        except Exception:
            continue
        if not dec:
            continue
        if real_arabic_run(dec):
            arab_hash[r["hash"]] += 1
        if L.TAG in dec:
            withloc += 1
            for lid, gid, txt in L.records_in(dec):
                hash_script[r["hash"]][L.classify(txt)] += 1
    f.close()
    print(f"\nprobed={probed} locRes={withloc} ({time.time()-t0:.0f}s)")
    rows = sorted(((h, sum(c.values()), dict(c)) for h, c in hash_script.items()), key=lambda x: -x[1])
    print("\nFADE9F44 loc hashes (hash : total : script-mix):")
    for h, tot, mix in rows[:25]:
        print(f"  0x{h:08x} : {tot:>7,} : {mix}")
    print("\nHashes whose resources contain REAL Arabic letter runs (hash : #res):")
    for h, c in arab_hash.most_common(25):
        print(f"  0x{h:08x} : {c}")
    json.dump({"loc": [(f"0x{h:08x}", tot, mix) for h, tot, mix in rows],
               "arab": [(f"0x{h:08x}", c) for h, c in arab_hash.most_common()]},
              open("/tmp/acbf_hashfind.json", "w"), indent=0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
