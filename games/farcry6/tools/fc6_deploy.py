"""
Far Cry 6 Hebrew deploy  (games/farcry6/tools)

Writes one or more edited resources into common.dat as FAT scheme-0 (stored, raw --
no compressor needed) and repoints their entries in common.fat, WD2-style:

  * append each new resource to common.dat at a 16-byte-aligned EOF offset
    (original bytes are never overwritten -- only appended)
  * rewrite each resource's FatEntry in common.fat: scheme=0, new offset/size (v11)
  * back up common.fat -> common.fat.he_backup and journal the original common.dat
    length in common.fat.he_journal.json

Revert = restore common.fat from the backup and truncate common.dat back to its
original length.  Never touches the exe (Denuvo) -- data archive only.

The full proof deploys BOTH:
  - the oasis with Hebrew menu strings (fc6_oasis.edit)
  - the UI fonts with injected Hebrew glyphs (fc6_font.inject_all)

  python fc6_deploy.py --proof            # deploy Hebrew menu text + Hebrew fonts
  python fc6_deploy.py --revert
  python fc6_deploy.py --status
"""
import sys, os, json, struct, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fc6_fat import Fat
import fc6_oasis as O
import fc6_font

GAME = os.environ.get("FC6_GAME", r"F:/Game Lab/Far Cry 6")
FAT = os.path.join(GAME, "data_final", "pc", "common.fat")
DAT = FAT[:-4] + ".dat"
BACKUP = FAT + ".he_backup"
JOURNAL = FAT + ".he_journal.json"

# Hebrew menu proof (stored LOGICAL -- FC6 bidi is engine-native).  (sectionCRC, id) -> Hebrew.
PROOF_EDITS = {
    (0x1514b7d7, 1125303): "המשך משחק",     # متابعة اللعب  (Continue)
    (0xc4f75272, 947941):  "המשך משחק",     # second Continue
    (0x69d07cfc, 353129):  "חזרה למשחק",    # استئناف اللعب (Resume -- pause menu)
    (0x039bee69, 1129539): "יציאה",         # خروج          (Exit / Quit)
    (0x30fe9cec, 160791):  "כן",            # نعم           (Yes)
}


def _pack_entry_v11(hash, unc, scheme, offset, comp):
    assert offset % 16 == 0, offset
    o16 = offset >> 4
    dwUnc = ((unc << 2) & 0xFFFFFFFC) | (scheme & 3)
    dwUnresolvedOffset = o16 >> 3
    dwComp = (((o16 & 7) << 29) | (comp & 0x1FFFFFFF)) & 0xFFFFFFFF
    return struct.pack("<IIIII", (hash >> 32) & 0xFFFFFFFF, hash & 0xFFFFFFFF,
                       dwUnc, dwUnresolvedOffset, dwComp)


def deploy(replacements):
    """replacements: {entry_hash: new_raw_bytes}.  Deploy all as scheme-0 stored."""
    if os.path.exists(BACKUP):
        print("[!] a deploy is already applied. Run --revert first."); return False
    fat = Fat(FAT)
    for h in replacements:
        if h not in fat.by_hash:
            print(f"[!] entry {h:016x} not in fat -- abort"); return False

    shutil.copy2(FAT, BACKUP)
    orig_dat_len = os.path.getsize(DAT)
    json.dump({"orig_dat_len": orig_dat_len}, open(JOURNAL, "w"))

    buf = bytearray(open(FAT, "rb").read())
    with open(DAT, "r+b") as f:
        cur = orig_dat_len
        for h, data in replacements.items():
            f.seek(cur)
            pad = (16 - (cur % 16)) % 16
            if pad:
                f.write(b"\x00" * pad); cur += pad
            f.write(data)
            en = fat.by_hash[h]
            buf[en.pos:en.pos + 20] = _pack_entry_v11(h, len(data), 0, cur, len(data))
            print(f"  {h:016x}: scheme=0 off={cur} size={len(data)}")
            cur += len(data)
    open(FAT, "wb").write(buf)
    print(f"deployed {len(replacements)} resources; common.dat {orig_dat_len} -> {cur}")

    # verify
    f2 = Fat(FAT)
    ok = all(f2.by_hash[h].scheme == 0 and len(f2.read_data(f2.by_hash[h])) == len(replacements[h])
             for h in replacements)
    print(f"VERIFY re-read: {'OK' if ok else 'FAIL'}")
    if not ok:
        revert()
    return ok


def deploy_archive(fat_path, replacements):
    """Generic scheme-0 deploy to ANY archive (fat_path + sibling .dat).
    Each archive keeps its own .he_backup / .he_journal.json."""
    dat = fat_path[:-4] + ".dat"
    bak = fat_path + ".he_backup"
    jrn = fat_path + ".he_journal.json"
    if os.path.exists(bak):
        print(f"[!] {os.path.basename(fat_path)} already deployed -- revert first"); return False
    fat = Fat(fat_path)
    for h in replacements:
        if h not in fat.by_hash:
            print(f"[!] {h:016x} not in {os.path.basename(fat_path)} -- abort"); return False
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
            buf[en.pos:en.pos + 20] = _pack_entry_v11(h, len(data), 0, cur, len(data))
            print(f"  [{os.path.basename(fat_path)}] {h:016x}: off={cur} size={len(data)}")
            cur += len(data)
    open(fat_path, "wb").write(buf)
    f2 = Fat(fat_path)
    ok = all(f2.by_hash[h].scheme == 0 and len(f2.read_data(f2.by_hash[h])) == len(replacements[h])
             for h in replacements)
    print(f"  [{os.path.basename(fat_path)}] deployed {len(replacements)}, VERIFY {'OK' if ok else 'FAIL'}")
    if not ok:
        revert_archive(fat_path)
    return ok


def revert_archive(fat_path):
    dat = fat_path[:-4] + ".dat"; bak = fat_path + ".he_backup"; jrn = fat_path + ".he_journal.json"
    if not os.path.exists(bak):
        return
    j = json.load(open(jrn)) if os.path.exists(jrn) else {}
    shutil.copy2(bak, fat_path)
    if "orig_dat_len" in j:
        with open(dat, "r+b") as f:
            f.truncate(j["orig_dat_len"])
    os.remove(bak)
    if os.path.exists(jrn):
        os.remove(jrn)
    print(f"reverted {os.path.basename(fat_path)}")


def full_proof():
    fat = Fat(FAT)
    # oasis with Hebrew menu strings
    oasis = fat.read_data(fat.by_hash[O.OASIS_HASH])
    new_oasis, applied = O.edit(oasis, PROOF_EDITS)
    print(f"oasis: {applied} Hebrew edits, {len(oasis)} -> {len(new_oasis)} B")
    reps = {O.OASIS_HASH: new_oasis}
    # UI fonts with injected Hebrew
    print("fonts:")
    reps.update(fc6_font.inject_all(fat))
    print(f"total resources to deploy: {len(reps)} (1 oasis + {len(reps)-1} fonts)")
    if deploy(reps):
        print("\n  DEPLOY OK.  Launch Far Cry 6 (Text language = Arabic):")
        print("    - main menu 'Continue' should read Hebrew  המשך משחק  (no more '?')")
        print("    - pause menu: Resume -> חזרה למשחק , Quit -> יציאה")
        print("    revert: python fc6_deploy.py --revert")


def revert():
    if not os.path.exists(BACKUP):
        print("nothing to revert"); return
    j = json.load(open(JOURNAL)) if os.path.exists(JOURNAL) else {}
    shutil.copy2(BACKUP, FAT)
    if "orig_dat_len" in j:
        with open(DAT, "r+b") as f:
            f.truncate(j["orig_dat_len"])
    os.remove(BACKUP)
    if os.path.exists(JOURNAL):
        os.remove(JOURNAL)
    print("reverted: common.fat restored, common.dat truncated")


def status():
    fat = Fat(FAT)
    en = fat.by_hash[O.OASIS_HASH]
    print(f"deployed={os.path.exists(BACKUP)}  oasis scheme={en.scheme} off={en.off} unc={en.unc}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--status"
    if cmd == "--proof":
        full_proof()
    elif cmd == "--revert":
        revert()
    else:
        status()
