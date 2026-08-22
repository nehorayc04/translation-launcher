"""
iso_test.py — ISOLATION harness for the 007 First Light boot failure.

Two full deploys failed to boot. This splits the deploy into its independent subsystems so ONE
launch per mode tells us exactly which one crashes boot:

  pkgonly   deploy ONLY the re-encrypted packagedefinition (super partition patchlevel 0->1),
            NO chunk0patch1.rpkg at all.
              boots  -> the packagedefinition re-encrypt + patchlevel bump are SAFE; the killer is
                        the patch RPKG.  Next: run `identity`.
              crashes-> the mount codec / patchlevel approach itself breaks boot.

  identity  deploy the packagedefinition (super=1) + a chunk0patch1.rpkg that overrides the SAME
            4 resources as the real menu-proof (3 menu LOCRs + the UI GFXF) but with their
            EXACT ORIGINAL decompressed bytes (LZ4+XOR, no edits).
              boots (menu unchanged, English) -> mount + patch FORMAT work; the killer is my
                        EDITED CONTENT (LOCR re-encode / GFXF Hebrew injection).
              crashes -> the patch FORMAT itself is rejected by the engine.

  revert    remove the patch + restore the original packagedefinition.

Run:  python iso_test.py pkgonly     (launch game, report)
      python iso_test.py revert
      python iso_test.py identity    (launch game, report)
      python iso_test.py revert
"""
import os
import sys
import shutil
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..", "tools")
sys.path.insert(0, TOOLS)

from gl_rpkg import RPKG
import gl_rpkg_write as W
import gl_pkgdef as PKG

GAME = r"F:\Game Lab\007 First Light"
RUNTIME = os.path.join(GAME, "Runtime")
CHUNK0 = os.path.join(RUNTIME, "chunk0.rpkg")
CHUNK1 = os.path.join(RUNTIME, "chunk1.rpkg")
PKGDEF = os.path.join(RUNTIME, "packagedefinition.txt")
PATCH_NAME = "chunk0patch1.rpkg"
PATCH1_NAME = "chunk1patch1.rpkg"
CHUNK1_LOCR = 0x012C2C6E00407DD5   # a small (400 B) chunk1 LOCR for the non-boot patch test

# same resource set as the real menu-proof
RES_HASHES = [
    0x01C76A08493EEE11,   # LOCR (Continue)
    0x01CF5B1F67C9AC83,   # LOCR (Resume/Load/Credits)
    0x01B4B8D71B46C3B8,   # LOCR (Options/Language)
    0x01DD9580958CDC9B,   # GFXF (UI font)
]
LOCR_ONLY = RES_HASHES[:3]         # the 3 menu LOCRs, no GFXF
ONE_LOCR = [0x01C76A08493EEE11]    # a single small LOCR — the most minimal possible patch


def _deploy_pkgdef(chunk_index=0):
    bak = PKGDEF + ".he_backup"
    if not os.path.exists(bak):
        shutil.copy2(PKGDEF, bak)
        print(f"  backed up packagedefinition -> {bak}")
    plain, _, hdr = PKG.decrypt(PKGDEF)
    enc = PKG.encrypt(PKG.set_patchlevel(plain, 1, chunk_index=chunk_index), hdr)
    open(PKGDEF, "wb").write(enc)
    print(f"  wrote packagedefinition (partition {chunk_index} patchlevel -> 1)")


def chunk1():
    # patch a NON-boot partition (base = chunk1) to see if boot-partition patching is the problem
    base = RPKG(CHUNK1)
    overrides = {CHUNK1_LOCR: base.read(base._by_hash[CHUNK1_LOCR])}   # ORIGINAL bytes
    out = os.path.join(RUNTIME, PATCH1_NAME)
    W.build_patch(base, overrides, out, lz4ed=True)
    print(f"  built {PATCH1_NAME} ({os.path.getsize(out)} bytes, 1 chunk1 LOCR, identity)")
    _deploy_pkgdef(chunk_index=1)   # bump the `base` partition
    print("DEPLOYED: chunk1patch1 (non-boot partition). BOOTS = format WORKS, the boot partition "
          "(super/chunk0) is what rejects patches. CRASHES = my patch FORMAT is fundamentally wrong.")


def pkgonly():
    # make sure no stale patch is present
    p = os.path.join(RUNTIME, PATCH_NAME)
    if os.path.exists(p):
        os.remove(p); print(f"  removed stale {PATCH_NAME}")
    _deploy_pkgdef()
    print("DEPLOYED: packagedefinition ONLY (no patch RPKG).")
    print("Launch the game. BOOTS = pkgdef mechanism is safe (killer is the patch). "
          "CRASHES = the pkgdef re-encrypt/patchlevel is the killer.")


def _deploy_identity(hashes, label, bump_pkg=True):
    base = RPKG(CHUNK0)
    overrides = {h: base.read(base._by_hash[h]) for h in hashes}       # ORIGINAL bytes, no edits
    out = os.path.join(RUNTIME, PATCH_NAME)
    W.build_patch(base, overrides, out, lz4ed=True)
    print(f"  built {label} {PATCH_NAME} ({os.path.getsize(out)} bytes, {len(overrides)} res, "
          f"ORIGINAL content, LZ4+XOR)")
    if bump_pkg:
        _deploy_pkgdef()
    else:
        print("  packagedefinition UNCHANGED (patchlevel stays 0)")


def identity():
    _deploy_identity(RES_HASHES, "IDENTITY(4 res: 3 LOCR + GFXF)")
    print("DEPLOYED. BOOTS = mount+format WORK, my EDITS are the killer. CRASHES = format rejected.")


def mini():
    _deploy_identity(ONE_LOCR, "MINI(1 LOCR, identity)")
    print("DEPLOYED. BOOTS = the patch mechanism works; the issue is GFXF/multi-res. "
          "CRASHES = even a 1-resource chunk0 patch is rejected (fundamental).")


def locronly():
    _deploy_identity(LOCR_ONLY, "LOCR-ONLY(3 LOCR, identity)")
    print("DEPLOYED. BOOTS = LOCR patches fine -> the GFXF override is the killer. "
          "CRASHES = LOCR patching itself is rejected.")


def nopkg():
    # identity patch present, but packagedefinition left at patchlevel 0 (NOT bumped)
    _deploy_identity(ONE_LOCR, "MINI(1 LOCR) WITHOUT pkg bump", bump_pkg=False)
    print("DEPLOYED. BOOTS = game does NOT auto-load patches (needs patchlevel) -> patch is inert. "
          "CRASHES = game auto-loads chunk0patch1 regardless of patchlevel.")


def revert():
    for name in (PATCH_NAME, PATCH1_NAME):
        p = os.path.join(RUNTIME, name)
        if os.path.exists(p):
            os.remove(p); print(f"  removed {p}")
    bak = PKGDEF + ".he_backup"
    if os.path.exists(bak):
        shutil.copy2(bak, PKGDEF); print(f"  restored packagedefinition from {bak}")
    print("REVERTED.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["pkgonly", "identity", "mini", "locronly", "nopkg",
                                     "chunk1", "revert"])
    a = ap.parse_args()
    {"pkgonly": pkgonly, "identity": identity, "mini": mini, "locronly": locronly,
     "nopkg": nopkg, "chunk1": chunk1, "revert": revert}[a.mode]()
