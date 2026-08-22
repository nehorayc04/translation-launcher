#!/usr/bin/env python3
"""
acs_identity.py — IDENTITY-repack diagnostic. Re-encode a forge resource with
NO content change (same decompressed data, freshly Oodle-compressed), same
on-disk size, in place. Isolates "does my home-built repack produce a forge the
GAME will load?" from "does a content change break an integrity hash?".

  python acs_identity.py verify "<forge>" <index>   # offline: re-decode == orig?
  python acs_identity.py deploy "<forge>" <index>   # backup + in-place identity
  python acs_identity.py revert "<forge>" <index>
"""
import sys, os, struct


def _tools():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import acs_forge as F, acs_cfd as C
    return F, C


def rebuild(forge, index):
    F, C = _tools()
    o = C._oodle()
    r = F.parse(forge)["recs"][index]
    with open(forge, "rb") as f:
        f.seek(r["offset"]); orig = f.read(r["size"])
    cfds, _ = C.decode_resource(orig, o)
    blob = b"".join(C.build_cfd(d, ci, o) for d, ci in cfds)
    # offline self-check: the re-encoded blob must decode to the SAME data
    back, _ = C.decode_resource(blob, o)
    same = [d for d, _ in back] == [d for d, _ in cfds]
    return r, orig, blob, same


def cmd_verify(forge, index):
    r, orig, blob, same = rebuild(forge, index)
    print(f"resource {index}: orig {len(orig)}B -> re-encoded {len(blob)}B "
          f"(fits={'Y' if len(blob)<=len(orig) else 'N'}) decode-identical={'Y' if same else 'N'}")
    return 0 if same and len(blob) <= len(orig) else 1


def cmd_deploy(forge, index):
    r, orig, blob, same = rebuild(forge, index)
    if not same or len(blob) > len(orig):
        print("ABORT: identity check failed or too big"); return 1
    blob = blob + b"\x00" * (len(orig) - len(blob))
    bak = f"{forge}.tmbak_{index}"
    if not os.path.exists(bak):
        open(bak, "wb").write(orig); print(f"backup -> {bak} ({len(orig)}B)")
    with open(forge, "r+b") as f:
        f.seek(r["offset"]); f.write(blob)
    print(f"identity-deployed {len(blob)}B at 0x{r['offset']:x} in {os.path.basename(forge)}")
    return 0


def cmd_revert(forge, index):
    bak = f"{forge}.tmbak_{index}"
    if not os.path.exists(bak):
        print(f"no backup {bak}"); return 1
    F, _ = _tools()
    r = F.parse(forge)["recs"][index]
    orig = open(bak, "rb").read()
    with open(forge, "r+b") as f:
        f.seek(r["offset"]); f.write(orig)
    print(f"reverted resource {index} ({len(orig)}B)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) >= 4:
        cmd = {"verify": cmd_verify, "deploy": cmd_deploy, "revert": cmd_revert}.get(sys.argv[1])
        if cmd:
            sys.exit(cmd(sys.argv[2], int(sys.argv[3])))
    print(__doc__)
