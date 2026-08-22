"""MSMR deploy — index-redirect, the SM2 mechanism ported to the older MSMR toc.

Insomniac resolves every asset through `asset_archive/toc`. On MSMR that toc is
[u32 magic 0x77AF12AF][u32 decompressed_len][zlib DAT1], and an asset's location is
split across TWO parallel sections (unlike RCRA, where one 16-byte entry holds it all):

    0xDCD720B5 Offsets  8 B  <II>  archive_index, offset
    0x65BCF461 Sizes   12 B  <III> always1, value(=size), index
    0x398ABFF0 Archives 72 B  <II> install_bucket, chunkmap + char[64] filename
    0xEDE8ADA9 Spans    8 B  <II> asset_index, count

So a deploy is: (1) write the rebuilt asset as a RAW file under asset_archive/mods/,
(2) APPEND an archive entry naming it, (3) point that asset's Offsets entry at
{archive_index=new, offset=0} and set its Sizes entry `value` to the new length.
No archive is ever repacked; every other asset keeps its exact offset.

MSMR has no header_offset field, so the blob written is the WHOLE asset file
(36-byte header + DAT1) — see tools/msmr_loc.py.

Fully reversible: the pristine toc is copied to toc.tm_he_backup before the first
write and a manifest records what we wrote. `--revert` restores it and deletes our
mod files. A game update rewrites the toc and drops our archive entries, which
`_toc_is_ours()` detects so a stale backup is never restored over a fresh toc.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import struct
import sys
from pathlib import Path

TOC_MAGIC_MSMR = 0x77AF12AF
MODS_SUBDIR    = "mods"                    # relative to asset_archive/
OUR_PREFIX     = "tm_he_"
BACKUP_NAME    = "toc.tm_he_backup"
MANIFEST       = ".tm_he_manifest.json"

TAG_ARCHIVES = 0x398ABFF0
TAG_SIZES    = 0x65BCF461
TAG_OFFSETS  = 0xDCD720B5
TAG_SPANS    = 0xEDE8ADA9


def _dat1lib():
    root = Path(__file__).resolve().parents[3]
    alert = root / "games" / "spiderman2" / "tools" / "ALERT"
    if str(alert) not in sys.path:
        sys.path.insert(0, str(alert))
    import dat1lib  # noqa
    import dat1lib.types.toc  # noqa
    return dat1lib


def arch_dir(game_root: Path) -> Path:
    return Path(game_root) / "asset_archive"


def toc_path(game_root: Path) -> Path:
    return arch_dir(game_root) / "toc"


def mods_dir(game_root: Path) -> Path:
    return arch_dir(game_root) / MODS_SUBDIR


def read_toc(path: Path):
    dat1lib = _dat1lib()
    import dat1lib.types.dat1 as d1
    with open(path, "rb") as f:
        t = dat1lib.read(f)
    t.dat1.set_recalculation_strategy(d1.RECALCULATE_ORIGINAL_ORDER)
    return t


def write_toc(t, path: Path) -> None:
    """Serialize + zlib exactly as dat1lib.types.toc.TOC.save does, atomically."""
    tmp = Path(str(path) + ".tm_he_tmp")
    with open(tmp, "wb") as f:
        t.save(f)
    os.replace(tmp, path)


def refresh(t, *tags: int) -> None:
    for tag in tags:
        t.dat1.refresh_section_data(tag)


def find_asset_index(t, span: int, asset_id: int) -> int:
    """Resolve the slot index for (span, asset_id) inside that span's range."""
    spans = t.get_spans_section()
    if span >= len(spans.entries):
        return -1
    sp = spans.entries[span]
    ids = t.get_assets_section().ids
    lo, hi = sp.asset_index, min(sp.asset_index + sp.count, len(ids))
    for i in range(lo, hi):
        if ids[i] == asset_id:
            return i
    return -1


def append_archive(t, rel_name: str) -> int:
    """Append a 72-byte MSMR ArchiveFileEntry naming `rel_name`.

    2026-08-12: uses the EXACT header bytes the community's own field-proven
    SpidermanLocalizationTool (team-waldo/InsomniacArchive, `ArchiveDirectory.
    SaveArchives`) writes for a brand-new patch archive entry:

        flag=2 (u16), unk02=0 (u8), unk03=0 (u8), unk04=0xCCCC (u16), unk06=1 (u16)
        == raw bytes 02 00 00 00 CC CC 01 00
        == read through dat1lib's own <II> pair: install_bucket=2, chunkmap=0x0001CCCC

    NOT cloned from any existing archive entry (the prior approach cloned
    install_bucket=0 from archive[19] + set chunkmap=max(existing)+1 — that
    fixed the earlier chunkmap-COLLISION bug [multiple new entries sharing one
    id -> keys-as-fallback + hang after logos, 2026-08-10] but a later deploy
    with the collision already fixed STILL failed in-game ("לא עובד",
    2026-08-12). Community precedent is that a genuinely-new archive is
    registered by these two SENTINEL values specifically, not merely by
    chunkmap uniqueness). Their tool creates exactly ONE such entry per deploy
    (every patched asset shares it via its own byte offset) — see apply()'s
    single-archive-file consolidation — so this fixed pair is never reused for
    a second new entry within one apply()."""
    arch = t.get_archives_section()
    template = arch.archives[19] if len(arch.archives) > 19 else arch.archives[0]
    e = copy.deepcopy(template)
    width = len(bytes(template.filename))          # 64 on MSMR
    raw = rel_name.encode("ascii", "replace")[:width]
    e.filename = bytearray(raw + b"\x00" * (width - len(raw)))
    e.install_bucket = 2
    e.chunkmap = 0x0001CCCC
    arch.archives.append(e)
    return len(arch.archives) - 1


def redirect(t, slot: int, archive_index: int, offset: int, size: int) -> None:
    off = t.get_offsets_section().entries[slot]
    sz = t.get_sizes_section().entries[slot]
    off.archive_index, off.offset = archive_index, offset
    sz.value = size


def toc_is_ours(t) -> bool:
    for e in t.get_archives_section().archives:
        if OUR_PREFIX.encode() in bytes(e.filename).split(b"\x00", 1)[0]:
            return True
    return False


# ------------------------------------------------------------------ public API
def apply(game_root: Path, assets: list[tuple[int, int, bytes]]) -> dict:
    """assets = [(span, asset_id, blob_bytes)]. Idempotent: reverts a prior apply first.

    2026-08-12: matches team-waldo/InsomniacArchive's `ArchiveDirectory.
    SaveArchives` shape — ONE new archive file + ONE new ArchiveFileEntry
    (sentinel header, see append_archive()), every patched asset appended
    sequentially into that ONE file at its own byte offset. The prior version
    gave each asset its OWN archive file + its OWN ArchiveFileEntry, which no
    proven-working real-world deploy does this way."""
    game_root = Path(game_root)
    toc = toc_path(game_root)
    if not toc.is_file():
        return {"ok": False, "error": f"toc not found: {toc}"}

    backup = arch_dir(game_root) / BACKUP_NAME
    md = mods_dir(game_root)

    # idempotency: if we already applied, restore the pristine toc first
    if backup.is_file():
        t_now = read_toc(toc)
        if toc_is_ours(t_now):
            shutil.copy2(backup, toc)
        else:
            backup.unlink()                       # stale (game updated) -> re-baseline

    if not backup.is_file():
        shutil.copy2(toc, backup)

    md.mkdir(parents=True, exist_ok=True)
    t = read_toc(toc)

    name = f"{OUR_PREFIX}patch"
    ai = append_archive(t, f"{MODS_SUBDIR}/{name}")

    redirects = []
    cur = 0
    with open(md / name, "wb") as f:
        for span, aid, blob in assets:
            slot = find_asset_index(t, span, aid)
            if slot < 0:
                return {"ok": False, "error": f"asset {aid:016X} not found in span {span}"}
            off_here = cur
            f.write(blob)
            cur += len(blob)
            redirect(t, slot, ai, off_here, len(blob))
            redirects.append({"span": span, "asset_id": f"{aid:016X}", "slot": slot,
                              "archive_index": ai, "offset": off_here, "size": len(blob)})

    refresh(t, TAG_ARCHIVES, TAG_SIZES, TAG_OFFSETS)
    write_toc(t, toc)

    st = toc.stat()
    (md / MANIFEST).write_text(json.dumps(
        {"files": [name], "redirects": redirects,
         "toc_stat": {"size": st.st_size, "mtime_ns": st.st_mtime_ns}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(assets)}


def revert(game_root: Path) -> dict:
    game_root = Path(game_root)
    toc = toc_path(game_root)
    backup = arch_dir(game_root) / BACKUP_NAME
    md = mods_dir(game_root)
    if not backup.is_file():
        return {"ok": False, "error": "no backup — nothing to revert"}
    t = read_toc(toc)
    if toc_is_ours(t):
        shutil.copy2(backup, toc)
        result = "toc restored from backup"
    else:
        result = "toc is not ours (game updated?) — backup DISCARDED, toc left alone"
    backup.unlink()
    if md.is_dir():
        for p in list(md.glob(OUR_PREFIX + "*")) + [md / MANIFEST]:
            try:
                p.unlink()
            except OSError:
                pass
    return {"ok": True, "result": result}


def status(game_root: Path) -> dict:
    game_root = Path(game_root)
    md = mods_dir(game_root)
    man = md / MANIFEST
    out = {"backup": (arch_dir(game_root) / BACKUP_NAME).is_file(),
           "manifest": man.is_file()}
    if man.is_file():
        out["manifest_data"] = json.loads(man.read_text(encoding="utf-8"))
    return out


# --------------------------------------------------------------- offline check
def validate_offline(game_root: Path, scratch: Path) -> int:
    """Prove the write path on a COPY of the real toc. The game folder is untouched."""
    scratch = Path(scratch)
    (scratch / "asset_archive" / MODS_SUBDIR).mkdir(parents=True, exist_ok=True)
    src = toc_path(game_root)
    dst = toc_path(scratch)
    print(f"[*] copying {src} -> {dst} ({src.stat().st_size:,} B)")
    shutil.copy2(src, dst)

    t0 = read_toc(dst)
    n_arch0 = len(t0.get_archives_section().archives)
    n_off0 = len(t0.get_offsets_section().entries)
    n_sz0 = len(t0.get_sizes_section().entries)
    n_id0 = len(t0.get_assets_section().ids)
    n_sp0 = len(t0.get_spans_section().entries)
    print(f"[*] pristine: archives={n_arch0} offsets={n_off0} sizes={n_sz0} "
          f"ids={n_id0} spans={n_sp0}")

    # (a) no-op save/reload round-trip
    write_toc(t0, dst)
    t1 = read_toc(dst)
    same = (len(t1.get_archives_section().archives) == n_arch0
            and len(t1.get_offsets_section().entries) == n_off0
            and len(t1.get_sizes_section().entries) == n_sz0
            and len(t1.get_assets_section().ids) == n_id0
            and len(t1.get_spans_section().entries) == n_sp0)
    drift = sum(1 for a, b in zip(read_toc(src).get_offsets_section().entries,
                                  t1.get_offsets_section().entries)
                if (a.archive_index, a.offset) != (b.archive_index, b.offset))
    print(f"[{'PASS' if same and drift == 0 else 'FAIL'}] no-op save/reload: "
          f"counts_ok={same} offset_drift={drift}  size={dst.stat().st_size:,} B")

    # (b) redirect one asset, save, reload, verify
    shutil.copy2(src, dst)
    blob = b"MSMR-DEPLOY-OFFLINE-VALIDATION-BLOB" * 64
    res = apply(scratch, [(0, 0xBE55D94F171BF8DE, blob)])
    print(f"[*] apply -> {res}")
    if not res.get("ok"):
        return 1
    t2 = read_toc(dst)
    arch2 = t2.get_archives_section().archives
    slot = find_asset_index(t2, 0, 0xBE55D94F171BF8DE)
    off2 = t2.get_offsets_section().entries[slot]
    sz2 = t2.get_sizes_section().entries[slot]
    nm = bytes(arch2[off2.archive_index].filename).split(b"\x00")[0].decode()
    new_entry = arch2[off2.archive_index]
    ok_r = (len(arch2) == n_arch0 + 1 and off2.offset == 0
            and sz2.value == len(blob) and nm == f"{MODS_SUBDIR}/{OUR_PREFIX}patch"
            and new_entry.install_bucket == 2 and new_entry.chunkmap == 0x0001CCCC)
    print(f"[{'PASS' if ok_r else 'FAIL'}] redirect: archives={len(arch2)} slot={slot} "
          f"-> archive[{off2.archive_index}]='{nm}' offset={off2.offset} size={sz2.value} "
          f"install_bucket={new_entry.install_bucket} chunkmap={new_entry.chunkmap:#x}")

    # (c) untouched assets kept their exact location
    t_src = read_toc(src)
    a_src = t_src.get_offsets_section().entries
    b_new = t2.get_offsets_section().entries
    s_src = t_src.get_sizes_section().entries
    s_new = t2.get_sizes_section().entries
    moved = sum(1 for i in range(len(a_src)) if i != slot and
                ((a_src[i].archive_index, a_src[i].offset) !=
                 (b_new[i].archive_index, b_new[i].offset)
                 or s_src[i].value != s_new[i].value))
    print(f"[{'PASS' if moved == 0 else 'FAIL'}] {len(a_src)-1:,} untouched assets unmoved "
          f"(drifted={moved})")

    # (d) the engine can actually read our raw blob back through the toc
    t2.set_archives_dir(str(arch_dir(scratch)))
    got = bytes(t2.extract_asset(slot))
    print(f"[{'PASS' if got == blob else 'FAIL'}] read-back through toc: "
          f"{len(got)} B, equal={got == blob}")

    # (e) revert
    shutil.copy2(src, dst)                       # emulate: pristine still in backup
    rv = revert(scratch)
    print(f"[*] revert -> {rv}")
    return 0 if (same and drift == 0 and ok_r and moved == 0 and got == blob) else 1


# --------------------------------------------------------- append-into-existing variant
# Diagnostic/fallback deploy: instead of appending a BRAND-NEW archive entry (a new
# archive_index/chunkmap/filename the updated exe has never seen before), append our
# blobs onto the END of an EXISTING, already-trusted archive file and redirect into
# THAT SAME archive_index. No new Archives-section row is created at all -- the toc's
# archive table (names/buckets/chunkmap) is byte-identical to pristine except for the
# 4 redirected Offsets/Sizes entries. Same append-relocate technique already proven
# elsewhere in this project (AC Unity, RDR2, 007 First Light) for engines that reject a
# freshly-registered archive but accept a same-archive_index growth.
INPLACE_BACKUP_NAME = "toc.tm_he_inplace_backup"
INPLACE_MANIFEST = ".tm_he_inplace_manifest.json"


def apply_inplace(game_root: Path, assets: list[tuple[int, int, bytes]],
                   target_archive_index: int = 0) -> dict:
    """assets = [(span, asset_id, blob_bytes)]. Appends every blob onto the END of the
    SAME existing archive file (archive_index=target_archive_index) and redirects each
    slot's Offsets/Sizes entry there. No archive/chunkmap/filename entry is added or
    touched. Idempotent (reverts a prior apply_inplace first). Mutually exclusive with
    apply()/revert() -- do not mix the two mechanisms on one toc."""
    game_root = Path(game_root)
    toc = toc_path(game_root)
    if not toc.is_file():
        return {"ok": False, "error": f"toc not found: {toc}"}

    backup = arch_dir(game_root) / INPLACE_BACKUP_NAME
    man_path = mods_dir(game_root) / INPLACE_MANIFEST

    if backup.is_file():
        rv = revert_inplace(game_root)
        if not rv.get("ok"):
            return rv

    shutil.copy2(toc, backup)
    t = read_toc(toc)

    arch = t.get_archives_section()
    if target_archive_index >= len(arch.archives):
        return {"ok": False, "error": f"archive_index {target_archive_index} out of range"}
    arch_name = bytes(arch.archives[target_archive_index].filename).split(b"\x00", 1)[0].decode()
    arch_path = arch_dir(game_root) / arch_name
    if not arch_path.is_file():
        return {"ok": False, "error": f"target archive file missing: {arch_path}"}

    orig_size = arch_path.stat().st_size
    written, redirects = [], []
    with open(arch_path, "r+b") as f:
        f.seek(0, 2)  # EOF
        cur = f.tell()
        assert cur == orig_size, "archive changed size unexpectedly before append"
        for span, aid, blob in assets:
            slot = find_asset_index(t, span, aid)
            if slot < 0:
                f.truncate(orig_size)  # undo any partial appends this call made
                return {"ok": False, "error": f"asset {aid:016X} not found in span {span}"}
            off_here = cur
            f.write(blob)
            cur += len(blob)
            redirect(t, slot, target_archive_index, off_here, len(blob))
            redirects.append({"span": span, "asset_id": f"{aid:016X}", "slot": slot,
                              "archive_index": target_archive_index, "offset": off_here,
                              "size": len(blob)})
        f.flush()
        os.fsync(f.fileno())

    refresh(t, TAG_SIZES, TAG_OFFSETS)   # Archives section is UNTOUCHED -- not refreshed
    write_toc(t, toc)

    mods_dir(game_root).mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(
        {"target_archive_index": target_archive_index, "target_archive_name": arch_name,
         "orig_archive_size": orig_size, "redirects": redirects},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "count": len(assets), "archive": arch_name, "orig_size": orig_size}


def revert_inplace(game_root: Path) -> dict:
    game_root = Path(game_root)
    toc = toc_path(game_root)
    backup = arch_dir(game_root) / INPLACE_BACKUP_NAME
    man_path = mods_dir(game_root) / INPLACE_MANIFEST
    if not backup.is_file():
        return {"ok": False, "error": "no in-place backup -- nothing to revert"}

    man = json.loads(man_path.read_text(encoding="utf-8")) if man_path.is_file() else None

    t = read_toc(toc)
    if toc_is_ours(t) or (man is not None):
        shutil.copy2(backup, toc)
        result = "toc restored from in-place backup"
        if man is not None:
            arch_path = arch_dir(game_root) / man["target_archive_name"]
            if arch_path.is_file():
                cur = arch_path.stat().st_size
                orig = man["orig_archive_size"]
                if cur >= orig:
                    with open(arch_path, "r+b") as f:
                        f.truncate(orig)
                    result += f"; {arch_path.name} truncated {cur:,}->{orig:,} B"
                else:
                    result += f"; WARNING {arch_path.name} already smaller than recorded original"
    else:
        result = "toc is not ours (game updated?) -- backup DISCARDED, toc/archive left alone"
    backup.unlink()
    if man_path.is_file():
        man_path.unlink()
    return {"ok": True, "result": result}


def status_inplace(game_root: Path) -> dict:
    game_root = Path(game_root)
    backup = arch_dir(game_root) / INPLACE_BACKUP_NAME
    man_path = mods_dir(game_root) / INPLACE_MANIFEST
    out = {"backup": backup.is_file(), "manifest": man_path.is_file()}
    if man_path.is_file():
        out["manifest_data"] = json.loads(man_path.read_text(encoding="utf-8"))
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    GAME = Path(os.environ.get("MSMR_GAME", r"D:\Games\Spider-man Remastered"))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if cmd == "validate":
        scratch = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
            os.environ.get("TEMP", ".")) / "msmr_validate"
        sys.exit(validate_offline(GAME, scratch))
    elif cmd == "status":
        print(json.dumps(status(GAME), ensure_ascii=False, indent=2))
    elif cmd == "revert":
        print(revert(GAME))
    else:
        print(__doc__)
