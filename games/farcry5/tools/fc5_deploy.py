"""
Far Cry 5 Hebrew deploy  (games/farcry5/tools)

Writes edited resources into <archive>.dat as FAT scheme-0 (stored, raw -- no
compressor needed) and repoints their entries in <archive>.fat:

  * append each new resource at the .dat EOF (original bytes are NEVER overwritten)
  * rewrite that resource's FatEntry as scheme=0 with the new offset/size (v10 packing)
  * back up <archive>.fat -> .he_backup and journal the original .dat length

Revert = restore the .fat from the backup and truncate the .dat back.  The exe is
never touched.

v10 entry packing (validated: max(off+comp) == .dat size exactly on 3 archives):
    off  = (e >> 29) | (dd << 3)      -> dd = off >> 3, e_top3 = off & 7
    comp = e & 0x1FFFFFFF             (29 bits)
    c    = (unc << 2) | scheme
  NOTE the offset spans 35 bits -- that is why an 8.9 GB patch.dat is addressable.

  IMPORTANT (base+patch stack): FC5 carries languages/<lang>/oasisstrings.oasis.bin in
  BOTH common.fat AND patch.fat, and patch overrides common.  Always deploy to EVERY
  archive that holds the resource, then verify the copy the engine wins with.

  python fc5_deploy.py --status
  python fc5_deploy.py --revert
"""
import sys, os, json, struct, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fc5_fat import Fat
from fc5_crc64 import name_hash

GAME = os.environ.get("FC5_GAME", r"F:/SteamLibrary/steamapps/common/FarCry5")
PC = os.path.join(GAME, "data_final", "pc")

# every archive that can carry a text/font resource we patch
ARCHIVES = ["common.fat", "patch.fat", "worlds/farcry5.fat", "worlds/installpkg.fat",
            # the story DLCs carry their OWN copy of the font -- revert must reach them
            "downloadcontent/dlc_mars/dlc_mars.fat",
            "downloadcontent/dlc_vietnam/dlc_vietnam.fat"]

MAX_COMP = 0x1FFFFFFF


def pack_entry_v10(hash, unc, scheme, offset, comp):
    """Build the 20-byte v10 FatEntry."""
    assert comp <= MAX_COMP, f"comp {comp} exceeds the 29-bit field"
    assert offset < (1 << 35), f"offset {offset} exceeds the 35-bit field"
    dwUnc = ((unc << 2) & 0xFFFFFFFC) | (scheme & 3)
    dwUnresolvedOffset = offset >> 3
    dwComp = (((offset & 7) << 29) | (comp & MAX_COMP)) & 0xFFFFFFFF
    return struct.pack("<IIIII", (hash >> 32) & 0xFFFFFFFF, hash & 0xFFFFFFFF,
                       dwUnc, dwUnresolvedOffset, dwComp)


def _selftest_pack():
    """Round-trip the packer against the reader's own decode on real entries."""
    fat = Fat(os.path.join(PC, "common.fat"))
    bad = 0
    for e in fat.entries[:4000]:
        blob = pack_entry_v10(e.hash, e.unc, e.scheme, e.off, e.comp)
        a, b, c, dd, ee = struct.unpack("<IIIII", blob)
        h = (a << 32) | b
        off = (ee >> 29) | (dd << 3)
        comp = ee & MAX_COMP
        unc = c >> 2
        sch = c & 3
        if (h, off, comp, unc, sch) != (e.hash, e.off, e.comp, e.unc, e.scheme):
            bad += 1
        if blob != fat.raw[e.pos:e.pos + 20]:
            bad += 1
    print(f"pack_entry_v10 self-test over 4000 real entries: {'PASS' if bad == 0 else f'FAIL ({bad})'}")
    return bad == 0


def deploy_archive(fat_rel, replacements):
    """replacements: {entry_hash: new_raw_bytes}.  Deploy all as scheme-0 stored."""
    fat_path = os.path.join(PC, fat_rel)
    dat = fat_path[:-4] + ".dat"
    bak = fat_path + ".he_backup"
    jrn = fat_path + ".he_journal.json"
    if os.path.exists(bak):
        print(f"[!] {fat_rel} already deployed -- revert first"); return False
    fat = Fat(fat_path)
    missing = [h for h in replacements if h not in fat.by_hash]
    if missing:
        print(f"[!] {fat_rel}: entries not present: {[f'{h:016x}' for h in missing]}"); return False

    shutil.copy2(fat_path, bak)
    orig = os.path.getsize(dat)
    json.dump({"orig_dat_len": orig}, open(jrn, "w"))

    buf = bytearray(open(fat_path, "rb").read())
    with open(dat, "r+b") as f:
        cur = orig
        for h, data in replacements.items():
            pad = (16 - (cur % 16)) % 16
            if pad:
                f.seek(cur); f.write(b"\x00" * pad); cur += pad
            f.seek(cur); f.write(data)
            en = fat.by_hash[h]
            buf[en.pos:en.pos + 20] = pack_entry_v10(h, len(data), 0, cur, len(data))
            print(f"  [{fat_rel}] {h:016x}: scheme=0 off={cur:,} size={len(data):,}")
            cur += len(data)
    open(fat_path, "wb").write(buf)

    f2 = Fat(fat_path)
    ok = True
    for h, data in replacements.items():
        e = f2.by_hash[h]
        if e.scheme != 0 or f2.read_data(e) != data:
            ok = False
    print(f"  [{fat_rel}] deployed {len(replacements)} resources, .dat {orig:,} -> {cur:,}, "
          f"VERIFY re-read {'OK' if ok else 'FAIL'}")
    if not ok:
        revert_archive(fat_rel)
    return ok


def revert_archive(fat_rel):
    fat_path = os.path.join(PC, fat_rel)
    dat = fat_path[:-4] + ".dat"; bak = fat_path + ".he_backup"; jrn = fat_path + ".he_journal.json"
    if not os.path.exists(bak):
        return False
    j = json.load(open(jrn)) if os.path.exists(jrn) else {}
    shutil.copy2(bak, fat_path)
    if "orig_dat_len" in j:
        with open(dat, "r+b") as f:
            f.truncate(j["orig_dat_len"])
    os.remove(bak)
    if os.path.exists(jrn):
        os.remove(jrn)
    print(f"reverted {fat_rel}")
    return True


def revert_all():
    n = sum(1 for a in ARCHIVES if revert_archive(a))
    print(f"reverted {n} archive(s)" if n else "nothing to revert")


def status():
    for a in ARCHIVES:
        p = os.path.join(PC, a)
        if not os.path.exists(p):
            continue
        print(f"{a:28s} deployed={os.path.exists(p + '.he_backup')}  "
              f"dat={os.path.getsize(p[:-4] + '.dat'):,}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--status"
    if cmd == "--revert":
        revert_all()
    elif cmd == "--selftest":
        _selftest_pack()
    else:
        status()
