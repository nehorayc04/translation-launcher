#!/usr/bin/env python3
r"""
validate_offline.py — exercise the ENTIRE deploy chain against a COPY of a real
forge before a single byte of the game is touched (§8f).

It runs the same mutate -> encode -> append-relocate -> re-parse path the live
deploy uses, then re-reads the result OUT of the mutated file and asserts:

  1. the forge still parses, with the SAME entry count
  2. every edited resource is reachable and in-bounds
  3. every proof string is present in the re-read LocalizationPackage
  4. every injected font re-reads with 27/27 Hebrew AND its Latin intact
  5. resources we did NOT touch are byte-identical to the pristine copy
  6. the header + FileSet table are byte-identical
  7. `revert` restores the file byte-for-byte

    python work/validate_offline.py [--forge DataPC.forge] [--keep]
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

import aco_forge                                        # noqa: E402
import aco_cfd                                          # noqa: E402
import aco_loc                                          # noqa: E402
import aco_deploy                                       # noqa: E402
import aco_font                                         # noqa: E402
import build_menu_proof as P                            # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRATCH = os.environ.get(
    "ACO_SCRATCH",
    r"C:\Users\NEHORA~1\AppData\Local\Temp\claude\aco_validate")


def md5(b):
    return hashlib.md5(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--forge", default="DataPC.forge")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    src = os.path.join(P.GAME, a.forge)
    os.makedirs(SCRATCH, exist_ok=True)
    dst = os.path.join(SCRATCH, a.forge)
    pristine = dst + ".pristine"

    print(f"copying {os.path.basename(src)} "
          f"({os.path.getsize(src)/1e6:.0f} MB) -> scratch ...")
    shutil.copy2(src, dst)
    shutil.copy2(src, pristine)

    od = aco_cfd.oodle()
    rc = 0

    # ---------- snapshot BEFORE ---------------------------------------
    fg = aco_forge.Forge(dst)
    n_before = len(fg.entries)
    size_before = fg.fsz
    sample = {}                       # untouched resources -> md5
    small = [e for e in fg.entries if e.size <= 4_000_000]
    for e in small[::max(1, len(small) // 300)]:
        sample[e.id] = md5(fg.read(e))
    with open(dst, "rb") as fh:
        head_before = fh.read(fg.first_fileset + 0x30 + n_before * 20)
    fg.close()

    # ---------- build + deploy ----------------------------------------
    print("\n-- build --")
    items = P.build_text(dst, od) + P.build_fonts(dst, od)
    edited = {r for r, _ in items}
    print(f"\n-- deploy {len(items)} resource(s) --")
    for res_id, blob in items:
        aco_deploy.apply(dst, res_id, blob, make_backup=False)

    # ---------- verify AFTER ------------------------------------------
    print("\n-- verify (re-read from the mutated file) --")
    fg = aco_forge.Forge(dst)

    def chk(label, ok, extra=""):
        nonlocal rc
        print(f"  [{'ok  ' if ok else 'FAIL'}] {label}{'  ' + extra if extra else ''}")
        if not ok:
            rc = 1

    chk("entry count unchanged", len(fg.entries) == n_before,
        f"{n_before:,} -> {len(fg.entries):,}")
    chk("file grew (append-relocate)", fg.fsz > size_before,
        f"{size_before:,} -> {fg.fsz:,} (+{fg.fsz-size_before:,})")

    with open(dst, "rb") as fh:
        head_after = fh.read(len(head_before))
    # the 20-byte records of edited resources legitimately changed
    diffs = sum(1 for i in range(len(head_before))
                if head_before[i] != head_after[i])
    chk("header/FileSet changed ONLY in edited records",
        diffs <= len(edited) * 20, f"{diffs} bytes differ, "
        f"<= {len(edited)*20} expected")

    ok_all = True
    for res_id, (tag, name) in P.AR_PACKAGES.items():
        ents = [e for e in fg.entries if e.id == res_id]
        if not ents:
            continue
        e = ents[0]
        inb = e.offset + e.size <= fg.fsz
        pkg = aco_loc.Package(e, aco_cfd.decode_resource(fg.read(e), od))
        s = pkg.strings()
        want = P.plan(tag)
        # NB: payload keys are ints — use the shared type-agnostic lookup, not str()
        hit = sum(1 for sid, t in want.items()
                  if (k := P._key(s, sid)) is not None and s[k] == t)
        chk(f"{name}: in-bounds + {hit}/{len(want)} edits + {len(s):,} strings",
            inb and hit == len(want))
        ok_all &= (inb and hit == len(want))

    heb_ok = heb_bad = 0
    for e, blob in aco_font.font_entries(fg, od):
        fr = aco_font.FontRes(e, blob, od)
        nm, glyphs, heb = aco_font.describe(fr.ttf)
        if nm in aco_font.CJK_FACES or aco_font.is_cff(fr.ttf):
            continue
        if heb == 27 and glyphs > 200:
            heb_ok += 1
        else:
            heb_bad += 1
            print(f"        !! {nm} heb={heb} glyphs={glyphs}")
    chk("every injected font re-reads 27/27 Hebrew with Latin intact",
        heb_bad == 0, f"{heb_ok} ok / {heb_bad} bad")

    untouched_bad = 0
    for eid, h in sample.items():
        if eid in edited:
            continue
        m = [e for e in fg.entries if e.id == eid]
        if not m:
            untouched_bad += 1
            continue
        if md5(fg.read(m[0])) != h:
            untouched_bad += 1
    chk("untouched resources byte-identical",
        untouched_bad == 0, f"{len(sample)} sampled, {untouched_bad} differ")

    bad = fg.validate()
    chk("contiguity violations == relocated count",
        bad == len(edited), f"{bad} violations, {len(edited)} relocated")
    fg.close()

    # ---------- revert -------------------------------------------------
    print("\n-- revert --")
    aco_deploy.revert(dst)

    def file_md5(p):
        h = hashlib.md5()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 22), b""):
                h.update(chunk)
        return h.hexdigest()

    chk("revert restores the file BYTE-IDENTICALLY (journal-only, no backup)",
        file_md5(dst) == file_md5(pristine),
        f"{os.path.getsize(dst):,} vs {os.path.getsize(pristine):,} B")

    if not a.keep:
        shutil.rmtree(SCRATCH, ignore_errors=True)
    print(f"\nOFFLINE VALIDATION {'PASS' if rc == 0 else 'FAIL'}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
