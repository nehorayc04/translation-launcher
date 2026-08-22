# -*- coding: utf-8 -*-
"""ONE deploy for EVERY W3 motion-comic subtitle — combines the two mechanisms:

  1. STORYBOOK (st_N.usm) + finalboards: NO embedded subtitle -> the engine reads the loose/bundled
     `.subs` files. Fix = rebuild those 72 *_ar.subs with Hebrew and CONTIGUOUS-repack movies.bundle
     (subs_deploy.patch_contiguous, pack mode preserved).
  2. RECAP (recap_wip.usm): subtitle is MULTIPLEXED into the video as @SBT channel-14 -> the .subs is
     ignored. Fix = patch the @SBT chunks in-place (usm_recap_deploy.patch_usm).

Order matters: the contiguous repack rewrites the whole bundle from the pristine backup (relocating the
recap USM), so it runs FIRST; then we patch the recap USM @SBT at its NEW offset in the rebuilt bundle.

Backup: movies.bundle.he_backup (pristine). Revert: --revert. GAME MUST BE CLOSED.
"""
import os, sys, struct, shutil
import potato_bundle as PB
import subs_deploy as SD
import usm_recap_deploy as UR

BUNDLE = SD.BUNDLE
BAK = SD.BAK


def deploy():
    # ---- 1. Hebrew .subs (storybook + finalboards + recap's vestigial copy) via contiguous repack ----
    new_map, st = SD.build_hebrew_subs()
    print(f"[.subs] files={st['files']} he={st['he']} reuse={st['reuse']} keep={st['keep']} "
          f"| stored={st['stored']} zlib={st['zlib']}")
    if not os.path.exists(BAK):
        shutil.copy2(BUNDLE, BAK); print(f"backed up -> {os.path.basename(BAK)}")
    total, old, n = SD.patch_contiguous(new_map)          # rebuilds BUNDLE from BAK
    print(f"[.subs] contiguous repack: {n} entries; {old} -> {total} ({total-old:+d})")

    # ---- 2. recap USM @SBT channel-14 -> Hebrew, patched IN the just-rebuilt bundle (no revert) ----
    he = UR.hebrew_by_start()
    d, e = UR._usm_entry(BUNDLE)                            # current (relocated) offset
    off, zsize = e["offs"], e["zsize"]
    with open(BUNDLE, "rb") as f:
        f.seek(off); usm = f.read(zsize)
    patched, nn, over = UR.patch_usm(usm, he)
    assert len(patched) == len(usm), "usm length changed"
    with open(BUNDLE, "r+b") as f:
        f.seek(off); f.write(patched)
    print(f"[recap USM] patched {nn} @SBT channel-14 chunks in-place ({over} over-capacity)")

    # ---- verify both ----
    d, ents = PB.list_entries(BUNDLE)
    byn = {x["name"].lower(): x for x in ents}
    import subs_codec as SC
    HE = lambda s: any('֐' <= c <= '׿' for c in s)
    # a storybook .subs
    sb = byn.get(r"movies\cutscenes\storybook\subs\st_1_ar.subs".lower())
    if sb:
        _, rows = SC.parse(PB.extract(d, sb))
        hebrows = sum(1 for r in rows if HE(r[2] or ""))
        print(f"verify storybook st_1_ar.subs: hebrew rows = {hebrows}/{len(rows)}")
    # recap USM channel 14
    ue = byn[UR.USM_NAME]
    with open(BUNDLE, "rb") as f:
        f.seek(ue["offs"]); back = f.read(ue["zsize"])
    pos = heb = ar = 0
    while True:
        pos = back.find(b"@SBT", pos)
        if pos == -1:
            break
        size = struct.unpack_from(">I", back, pos + 4)[0]; p0 = pos + 8
        if struct.unpack_from("<I", back, p0 + 8 + 16)[0] == UR.AR_CHANNEL:
            tl = struct.unpack_from("<I", back, p0 + 40)[0]
            t = back[p0 + 44:p0 + 44 + tl].decode("utf-8", "replace")
            if HE(t): heb += 1
            elif any('؀' <= c <= 'ۿ' for c in t): ar += 1
        pos += 4
    print(f"verify recap USM channel-14: hebrew={heb} arabic={ar}")
    print("DEPLOYED. Fully restart the game (Text Language = Arabic).")


def revert():
    if os.path.exists(BAK):
        shutil.copy2(BAK, BUNDLE); print("reverted movies.bundle from .he_backup")
    else:
        print("no backup found")


if __name__ == "__main__":
    if "--revert" in sys.argv:
        revert()
    elif "--deploy" in sys.argv:
        deploy()
    else:
        _, st = SD.build_hebrew_subs()
        print(f"(dry-run) .subs files={st['files']} he={st['he']} reuse={st['reuse']} keep={st['keep']}")
        print("Re-run with --deploy (GAME MUST BE CLOSED).")
