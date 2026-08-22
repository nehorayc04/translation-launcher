#!/usr/bin/env python3
"""Re-capture the PRISTINE atlas blobs from the CURRENT forges.

Run this after a game update / a Connect "verify files" repair, once the forges are known
vanilla (discover_weights reports HEB=0 everywhere). The old backups are only valid for the
build they were taken from -- see verify_slot() for what a stale offset costs.
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import acs_forge as F            # noqa: E402
import acs_atlas_inject as AI    # noqa: E402

def main():
    weights = AI.discover_weights(verbose=True)
    print(f"discovered {len(weights)} Arabic weights")
    for path, idx in weights:
        r = next(x for x in F.parse(path)["recs"] if x["i"] == idx)
        with open(path, "rb") as f:
            f.seek(r["offset"]); blob = f.read(r["size"])
        assert len(blob) == r["size"]
        with open(AI.BAK % idx, "wb") as g:
            g.write(struct.pack("<QQ", r["offset"], r["size"]))
            g.write(path.encode() + b"\x00")
            g.write(blob)
        print(f"  saved {os.path.basename(AI.BAK % idx)}  @0x{r['offset']:x} {r['size']:,} B")
    return 0

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
