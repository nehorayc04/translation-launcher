#!/usr/bin/env python3
r"""
validate_offline.py — exercise the ENTIRE deploy chain against a COPY of the real
forge before a single byte of the game is touched (§8f / the Odyssey lesson).

Runs the same mutate -> encode -> append-relocate -> re-parse path the live deploy
uses, then re-reads the result OUT of the mutated file and asserts:

  1. the forge still parses, with the SAME entry count
  2. every edited resource is reachable and carries its proof rows
  3. every injected font re-reads with 27/27 Hebrew AND its original cmap intact
  4. resources we did NOT touch are byte-identical to the pristine copy
  5. the header is byte-identical
  6. `revert` restores the file byte-for-byte

    python work/validate_offline.py [--keep]
"""
import argparse
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import aor_forge                                        # noqa: E402
import aor_cfd                                          # noqa: E402
import aor_loc                                          # noqa: E402
import aor_deploy                                       # noqa: E402
import aor_font                                         # noqa: E402
import build_proof as P                                 # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRATCH = os.environ.get("SCRATCH", os.path.join(os.environ.get("TEMP", "."), "aor_validate"))


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    src = P.FORGE
    os.makedirs(SCRATCH, exist_ok=True)
    dst = os.path.join(SCRATCH, "aor_validate.forge")
    print(f"copying {src}\n     -> {dst}")
    shutil.copy2(src, dst)
    pristine = open(dst, "rb").read()

    od = aor_cfd.oodle()
    fg0 = aor_forge.Forge(dst)
    n0 = len(fg0.entries)
    head0 = pristine[:2048]
    ids = set(P.all_blobs())
    others = [e for e in fg0.entries if e.id not in ids]
    sample = others[:: max(1, len(others) // 300)][:300]
    before = {e.id: sha(fg0.read(e)) for e in sample}
    print(f"  entries {n0:,d} · editing {len(ids)} · fingerprinting {len(sample)} others")

    for rid in sorted(ids):
        blob = open(os.path.join(P.BLOBS, f"{rid}.bin"), "rb").read()
        aor_deploy.apply(dst, rid, blob, make_backup=True)

    ok = True

    def chk(cond, msg):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'ok  ' if cond else 'FAIL'}] {msg}")

    fg1 = aor_forge.Forge(dst)
    chk(len(fg1.entries) == n0, f"entry count unchanged  {n0:,d} -> {len(fg1.entries):,d}")
    chk(open(dst, "rb").read(2048) == head0, "header (first 2 KB) byte-identical")

    for name, marker in ((P.PKG_EN_UI, "ZZ-AOR-ENUI-ZZ"), (P.PKG_AR_UI, "ZZ-AOR-ARUI-ZZ")):
        p = aor_loc.find(fg1, name, od)
        st = p.strings()
        chk(st.get(456221) == marker, f"{name}: marker present ({len(st):,d} strings)")
        chk(st.get(456219) == P.V("שלום"), f"{name}: VISUAL A/B row intact")
        chk(P.ALEFBET[0] in st.get(456233, ""), f"{name}: 27-letter row intact")

    ps = aor_loc.find(fg1, P.PKG_AR_SUB, od)
    sst = ps.strings()
    # ⚠️ the id%3==2 rows are stored VISUAL, so the literal "אבגד" is NOT a
    # substring of them — match the reversed form too, or a correct build reads
    # as a 2/3 failure (this predicate was wrong on the first run, not the data).
    alef_v = P.V(P.ALEFBET)[:4]
    nproof = sum(1 for v in sst.values()
                 if "ZZ-SUB-" in v or P.ALEFBET[:4] in v or alef_v in v)
    kinds = {m: sum(1 for k in sst if int(k) % 3 == m) for m in (0, 1, 2)}
    chk(len(sst) == 12844, f"subtitles: record count unchanged ({len(sst):,d})")
    chk(nproof == len(sst),
        f"subtitles: {nproof:,d}/{len(sst):,d} rows carry the proof "
        f"(VISUAL {kinds[0]:,d} · LOGICAL {kinds[1]:,d} · paragraph {kinds[2]:,d})")

    heb = lat = nfont = 0
    for e, blob in aor_font.font_entries(fg1, od):
        fr = aor_font.FontRes(e, blob, od)
        nm, ncm, h = aor_font.describe(fr.ttf)
        nfont += 1
        heb += (h == 27)
        lat += (ncm > 100)
    chk(nfont == 9 and heb == 9, f"fonts: {heb}/{nfont} at 27/27 Hebrew")
    chk(lat == 9, "fonts: all keep their original cmap (Latin/Cyrillic/Arabic)")

    byid = {e.id: e for e in fg1.entries}
    bad = [e.id for e in sample if sha(fg1.read(byid[e.id])) != before[e.id]]
    chk(not bad, f"{len(sample)} untouched resources byte-identical ({len(bad)} changed)")

    print(f"  file grew by {os.path.getsize(dst) - len(pristine):,d} B (append-relocate)")

    aor_deploy.revert(dst)
    chk(open(dst, "rb").read() == pristine, "revert restores the forge BYTE-IDENTICALLY")

    if not a.keep:
        del fg0, fg1, ps                    # drop the readers' open handles first
        for f in (dst, aor_deploy.backup_path(dst), aor_deploy.journal_path(dst)):
            try:
                os.remove(f)
            except OSError:
                pass                        # AV/indexer lock — harmless, it is a temp copy
    print("\nVALIDATE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
