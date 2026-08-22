#!/usr/bin/env python3
"""Tally content[0] (ScimitarClass hash) across all resources in a forge → class-type histogram."""
import sys, struct, json, collections
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\tools")
sys.path.insert(0, r"C:\Users\Nehoray_Cohen\Projects\Game translator\games\acunity\work")
import acu_forge as F, acu_loc as L
from scan_fd2 import peek_content_head

reg = json.load(open(r"C:/tmp/acuwork/classreg.json"))


def main():
    fg = F.Forge(sys.argv[1])
    hist = collections.Counter()
    fd_recs = []
    fail = 0
    for i in range(fg.count):
        if fg.recs[i][0] == 0:
            continue
        try:
            head = peek_content_head(fg.extract_index(i), 8)
        except Exception:
            fail += 1
            continue
        if not head or len(head) < 4:
            fail += 1
            continue
        h = struct.unpack_from("<I", head, 0)[0]
        hist[h] += 1
        if reg.get(str(h)) == "FireData":
            fd_recs.append(i)
    print(f"# {sys.argv[1].split('/')[-1]}: {sum(hist.values())} resources, {fail} unreadable")
    for h, c in hist.most_common(40):
        print(f"  {c:>6}  {h:>12}  {reg.get(str(h), '??')}")
    if fd_recs:
        print("FireData recs:", fd_recs)


if __name__ == "__main__":
    main()
