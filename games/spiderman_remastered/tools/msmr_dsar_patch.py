"""In-place DSAR block overwrite for MSMR — ZERO toc changes, ZERO new archive
table rows, ZERO changes to the archive's own block-map header. Overwrites only
the raw compressed bytes of the blocks an existing asset already occupies.

Round 4c (2026-08-11): both the append-new-archive mechanism (apply()) AND the
append-into-an-existing-archive mechanism (apply_inplace(), DSAR-incompatible)
were ruled out for the officially-updated v3.618 exe: the FIRST is proven
(user 3x A/B) to correlate with the boot stall, the SECOND cannot even be
written (DSAR block-map doesn't cover appended bytes). This module tests a
THIRD, more conservative option: don't touch the toc or the archive's structure
AT ALL — only overwrite the SAME bytes an asset already legitimately occupies,
in place, using the exact same LZ4-block compression the game already uses.

Feasibility proven for span 8's localization asset in g00s019: the asset is
PERFECTLY block-aligned (24 whole 262144-byte blocks, last one 10068), and a
test patch (marker-only, same shape as the failed minimal archive-row test)
recompresses to fit inside every one of the 24 blocks' ORIGINAL comp_size
budget with room to spare. Standard `lz4.block.compress(..., store_size=False)`
round-trips through dat1lib's own decompression.decompress() byte-for-byte.

If the asset is NOT block-aligned for some other target, this refuses instead
of guessing at a riskier partial-block overwrite.

🔴 DO NOT ZERO-PAD a shrunk block's leftover comp_size space. dat1lib's own
`decompression.decompress()` loop condition is `while real_i <= real_size and
comp_i < comp_size` — note `<=`, not `<`. The instant the block is fully
reconstructed (`real_i == real_size`), the loop still re-enters ONE more time
(since `real_i <= real_size` is still True at equality) and tries to parse
whatever byte sits at `comp_i` as another token — if that's zero-padding, it
either produces silent garbage or, as observed live, an out-of-bounds
IndexError reading the reverse-offset's second byte at the very end of the
buffer. **The fix: when the new compressed data is SHORTER than the block's
original comp_size, patch the block-map header's own `comp_size` field down
to the new (exact) length instead of padding** — the bytes between
`comp_offset + new_len` and `comp_offset + orig_comp_size` become inert dead
space (never addressed by any OTHER block's comp_offset, since blocks are
read independently by their own {comp_offset, comp_size} pair), and the
decompressor's loop now terminates cleanly at `comp_i == comp_size` exactly
when `real_i == real_size`, matching the un-padded shape the game's own
encoder always produces. Confirmed live: zero-padding crashed extract_asset()
with an IndexError; header-comp_size-patch is now the only method used.
"""
import json
import os
import shutil
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DAT1LIB_ROOT = HERE.parents[1] / "spiderman2" / "tools" / "ALERT"
sys.path.insert(0, str(DAT1LIB_ROOT))
sys.path.insert(0, str(HERE))

import dat1lib.decompression as decompression  # noqa: E402
import lz4.block as lz4b                        # noqa: E402
import msmr_deploy                              # noqa: E402

BACKUP_NAME = ".tm_he_dsar_backup.json"  # per game-root, holds byte-range snapshots


COMP_SIZE_FIELD_OFFSET_IN_RECORD = 20  # 5th u32 (0-based idx 5) of the 32-byte record


def _lz4_literal_only(data: bytes) -> bytes:
    """Hand-built raw LZ4 block: ONE sequence, pure literals, zero match
    length -- the exact shape every real LZ4 encoder uses for the FINAL
    sequence of a block (no back-references at all). Round-trips through
    dat1lib's own software decompressor identically to a normal compressed
    block, but has zero LZ77 match/offset structure for anything (e.g. a
    stricter/different hardware DirectStorage GPU decompressor) to reject.

    Round 4e test: is our own valid-but-`high_compression`-mode LZ4 output
    (which passed our own decoder's self-check every time) nonetheless
    hitting some GPU-decompression-path edge case that a real match-free
    stream would not? Content-different-from-vanilla in-place block
    overwrites have stalled the game 100% of the time so far (2/2); a
    byte-IDENTICAL in-place rewrite (no compression difference at all,
    since it's literally the original bytes) was the only one that opened
    cleanly. This isolates "shape of the compressed stream" as the one
    remaining untested variable."""
    n = len(data)
    out = bytearray()
    if n < 15:
        out.append(n << 4)
    else:
        out.append(0xF0)
        rem = n - 15
        while rem >= 255:
            out.append(255)
            rem -= 255
        out.append(rem)
    out.extend(data)
    return bytes(out)


def _read_block_map(f):
    """Returns a list of dicts, one per block, each carrying its own absolute
    file offset for the comp_size header field (needed to shrink it in
    place if the recompressed payload is smaller than the original)."""
    f.seek(12)
    blocks_header_end = struct.unpack("<I", f.read(4))[0]
    f.seek(32)
    blocks = []
    idx = 0
    while f.tell() < blocks_header_end:
        rec_off = 32 + idx * 32
        real_offset, _, comp_offset, _, real_size, comp_size, _, _ = struct.unpack(
            "<IIIIIIII", f.read(32)
        )
        blocks.append({
            "real_offset": real_offset,
            "comp_offset": comp_offset,
            "real_size": real_size,
            "comp_size": comp_size,
            "comp_size_field_offset": rec_off + COMP_SIZE_FIELD_OFFSET_IN_RECORD,
        })
        idx += 1
    return blocks


def _covering_blocks(blocks, asset_offset, asset_size):
    asset_end = asset_offset + asset_size
    return [
        b for b in blocks
        if (b["real_offset"] + b["real_size"]) > asset_offset and b["real_offset"] < asset_end
    ]


def plan(game_root: Path, span: int, asset_id: int, new_blob: bytes,
         compress_mode: str = "high_compression") -> dict:
    """Resolve the target archive+blocks for (span, asset_id) and check whether
    new_blob (already including any container header the format needs) fits
    in place. Returns a dict describing the plan; raises if infeasible.

    compress_mode: "high_compression" (default, real LZ4 match-based
    compression via lz4.block) or "literal_only" (Round 4e test -- a
    hand-built zero-match LZ4 stream, see _lz4_literal_only above)."""
    t = msmr_deploy.read_toc(msmr_deploy.toc_path(game_root))
    t.set_archives_dir(str(msmr_deploy.arch_dir(game_root)))
    slot = msmr_deploy.find_asset_index(t, span, asset_id)
    return _plan_slot(t, game_root, slot, new_blob, compress_mode)


def plan_by_path(game_root: Path, asset_path: str, new_blob: bytes,
                  compress_mode: str = "high_compression") -> dict:
    """Same as plan(), but for assets that are NOT part of the localization
    span system (e.g. fonts) -- resolved directly by their crc64(path) asset
    id via t.get_asset_entries_by_assetid(), the same lookup 10_font_hunt.py
    uses. No span/variant concept applies to these assets."""
    msmr_deploy._dat1lib()
    import dat1lib.crc64 as crc64
    t = msmr_deploy.read_toc(msmr_deploy.toc_path(game_root))
    t.set_archives_dir(str(msmr_deploy.arch_dir(game_root)))
    aid = crc64.hash(asset_path)
    ents = [e for e in (t.get_asset_entries_by_assetid(aid, stop_on_first=True) or []) if e]
    if not ents:
        raise ValueError(f"asset path {asset_path!r} (aid=0x{aid:016X}) not found in toc")
    slot = ents[0].index
    return _plan_slot(t, game_root, slot, new_blob, compress_mode)


def _plan_slot(t, game_root: Path, slot: int, new_blob: bytes,
               compress_mode: str = "high_compression") -> dict:
    off = t.get_offsets_section().entries[slot]
    sz = t.get_sizes_section().entries[slot]
    arch = t.get_archives_section().archives[off.archive_index]
    arch_name = bytes(arch.filename).split(b"\x00", 1)[0].decode()
    arch_path = msmr_deploy.arch_dir(game_root) / arch_name

    if len(new_blob) > sz.value:
        raise ValueError(
            f"new content {len(new_blob)} B > asset size {sz.value} B -- "
            f"cannot fit without growing the asset (not supported by this path)"
        )
    padded = new_blob + b"\x00" * (sz.value - len(new_blob))

    with open(arch_path, "rb") as f:
        magic = f.read(4)
        if magic != b"DSAR":
            raise ValueError(f"{arch_name} is not DSAR-compressed (magic={magic!r})")
        blocks = _read_block_map(f)
    covering = _covering_blocks(blocks, off.offset, sz.value)
    total_real = sum(b["real_size"] for b in covering)
    if total_real != sz.value:
        raise ValueError(
            f"asset [{off.offset}, {off.offset + sz.value}) is NOT block-aligned "
            f"in {arch_name} (covering blocks sum to {total_real} real bytes, "
            f"expected exactly {sz.value}) -- refusing, too risky to guess a "
            f"partial-block overwrite"
        )

    chunks = []
    o = 0
    for b in covering:
        real_size = b["real_size"]
        comp_size = b["comp_size"]
        chunk = padded[o:o + real_size]
        o += real_size
        if compress_mode == "literal_only":
            comp = _lz4_literal_only(chunk)
        else:
            comp = lz4b.compress(chunk, mode="high_compression", store_size=False)
        fits = len(comp) <= comp_size
        # self-check NOW, offline, with the EXACT (comp, real_size) pair we'd
        # write -- if this doesn't round-trip, we must not touch the real file
        roundtrip_ok = bytes(decompression.decompress(comp, real_size)) == chunk
        chunks.append({
            "comp_offset": b["comp_offset"],
            "orig_comp_size": comp_size,
            "comp_size_field_offset": b["comp_size_field_offset"],
            "real_size": real_size,
            "new_compressed": comp,
            "fits": fits,
            "roundtrip_ok": roundtrip_ok,
        })

    all_fit = all(c["fits"] and c["roundtrip_ok"] for c in chunks)
    return {
        "archive_path": str(arch_path),
        "archive_name": arch_name,
        "archive_index": off.archive_index,
        "asset_offset": off.offset,
        "asset_size": sz.value,
        "slot": slot,
        "n_blocks": len(chunks),
        "all_fit": all_fit,
        "chunks": chunks,
    }


def apply_plan(game_root: Path, plan_result: dict) -> dict:
    """Write plan_result's recompressed chunks in place, backing up the exact
    byte ranges touched first (so revert is a pure byte-range restore, no
    knowledge of block-map structure needed).

    🔴 NEVER zero-pad a shrunk block -- see the module docstring. When
    new_compressed is shorter than orig_comp_size, the block-map header's own
    comp_size field is patched down to the exact new length instead; the
    leftover bytes are left untouched (dead space, never read by anyone)."""
    if not plan_result["all_fit"]:
        raise ValueError("plan says NOT all blocks fit -- refusing to apply")

    arch_path = Path(plan_result["archive_path"])
    backups = []
    with open(arch_path, "r+b") as f:
        # snapshot everything we're about to touch FIRST
        for c in plan_result["chunks"]:
            f.seek(c["comp_offset"])
            orig_bytes = f.read(c["orig_comp_size"])
            f.seek(c["comp_size_field_offset"])
            orig_header = f.read(4)
            backups.append({
                "comp_offset": c["comp_offset"],
                "orig_comp_size": c["orig_comp_size"],
                "orig_hex": orig_bytes.hex(),
                "comp_size_field_offset": c["comp_size_field_offset"],
                "orig_header_hex": orig_header.hex(),
            })
        # then write: exact-length compressed payload, no padding, and shrink
        # the header's comp_size field to match whenever we wrote less
        for c in plan_result["chunks"]:
            new_len = len(c["new_compressed"])
            f.seek(c["comp_offset"])
            f.write(c["new_compressed"])
            if new_len != c["orig_comp_size"]:
                f.seek(c["comp_size_field_offset"])
                f.write(struct.pack("<I", new_len))

    backup_path = game_root / BACKUP_NAME
    manifest = {
        "archive_path": plan_result["archive_path"],
        "archive_name": plan_result["archive_name"],
        "backups": backups,
    }
    # append (don't clobber) so multiple assets in one session all revert cleanly
    existing = []
    if backup_path.exists():
        existing = json.loads(backup_path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = [existing]
    existing.append(manifest)
    backup_path.write_text(json.dumps(existing, indent=1), encoding="utf-8")

    return {"ok": True, "n_blocks_written": len(plan_result["chunks"]),
            "archive": plan_result["archive_name"]}


def revert(game_root: Path) -> dict:
    backup_path = game_root / BACKUP_NAME
    if not backup_path.exists():
        return {"ok": True, "result": "no dsar backup present, nothing to revert"}
    manifests = json.loads(backup_path.read_text(encoding="utf-8"))
    if not isinstance(manifests, list):
        manifests = [manifests]
    restored = 0
    for m in reversed(manifests):
        arch_path = Path(m["archive_path"])
        with open(arch_path, "r+b") as f:
            for b in m["backups"]:
                f.seek(b["comp_offset"])
                f.write(bytes.fromhex(b["orig_hex"]))
                f.seek(b["comp_size_field_offset"])
                f.write(bytes.fromhex(b["orig_header_hex"]))
                restored += 1
    backup_path.unlink()
    return {"ok": True, "blocks_restored": restored}


def status(game_root: Path) -> dict:
    backup_path = game_root / BACKUP_NAME
    if not backup_path.exists():
        return {"backup": False}
    manifests = json.loads(backup_path.read_text(encoding="utf-8"))
    if not isinstance(manifests, list):
        manifests = [manifests]
    return {
        "backup": True,
        "archives_touched": [m["archive_name"] for m in manifests],
        "total_blocks": sum(len(m["backups"]) for m in manifests),
    }


def plan_reencode_block(archive_path: Path, block_index: int,
                         compress_mode: str = "literal_only") -> dict:
    """Round 4e isolation test: take ONE block's EXISTING content (decompressed
    from what's already on disk, so it is byte-for-byte the vanilla content --
    nothing about the DECOMPRESSED bytes differs at all) and re-encode it with
    a DIFFERENT compression shape than the game's own encoder used. Tests
    whether the boot stall depends on the COMPRESSED BYTE STREAM's shape/
    algorithm (a hardware DirectStorage decompressor being pickier than our
    software one, or some check on the compressed bytes themselves) rather
    than on the decompressed CONTENT differing from vanilla -- which is the
    one variable every prior test conflated with "content changed"."""
    with open(archive_path, "rb") as f:
        magic = f.read(4)
        if magic != b"DSAR":
            raise ValueError(f"{archive_path} is not DSAR (magic={magic!r})")
        blocks = _read_block_map(f)
    b = blocks[block_index]
    with open(archive_path, "rb") as f:
        f.seek(b["comp_offset"])
        orig_comp = f.read(b["comp_size"])
    orig_content = bytes(decompression.decompress(orig_comp, b["real_size"]))

    if compress_mode == "literal_only":
        new_comp = _lz4_literal_only(orig_content)
    else:
        new_comp = lz4b.compress(orig_content, mode=compress_mode, store_size=False)

    fits = len(new_comp) <= b["comp_size"]
    roundtrip_ok = bytes(decompression.decompress(new_comp, b["real_size"])) == orig_content
    return {
        "archive_path": str(archive_path),
        "archive_name": archive_path.name,
        "block_index": block_index,
        "comp_offset": b["comp_offset"],
        "orig_comp_size": b["comp_size"],
        "comp_size_field_offset": b["comp_size_field_offset"],
        "real_size": b["real_size"],
        "new_compressed": new_comp,
        "content_unchanged": True,  # by construction -- we decoded THEN re-encoded the same bytes
        "fits": fits,
        "roundtrip_ok": roundtrip_ok,
        "all_fit": fits and roundtrip_ok,
    }


def plan_reencode_asset(game_root: Path, span: int, asset_id: int) -> dict:
    """Round 4f isolation: re-encode EVERY block of an asset with a compressor
    that beats the game's own, so the DECOMPRESSED content stays byte-for-byte
    vanilla while `comp_size` shrinks and therefore the block-map header field
    gets PATCHED -- exactly the shape of the failing content-different deploys,
    with the content difference removed.

    Every failing test so far patched comp_size; every passing test did not.
    Content-difference and comp_size-patching have been CONFOUNDED in all seven
    prior experiments. This separates them: identical content, patched header."""
    t = msmr_deploy.read_toc(msmr_deploy.toc_path(game_root))
    t.set_archives_dir(str(msmr_deploy.arch_dir(game_root)))
    slot = msmr_deploy.find_asset_index(t, span, asset_id)
    off = t.get_offsets_section().entries[slot]
    sz = t.get_sizes_section().entries[slot]
    arch = t.get_archives_section().archives[off.archive_index]
    arch_name = bytes(arch.filename).split(b"\x00", 1)[0].decode()
    arch_path = msmr_deploy.arch_dir(game_root) / arch_name

    with open(arch_path, "rb") as f:
        if f.read(4) != b"DSAR":
            raise ValueError(f"{arch_name} is not DSAR")
        blocks = _read_block_map(f)
        covering = _covering_blocks(blocks, off.offset, sz.value)
        chunks = []
        for b in covering:
            f.seek(b["comp_offset"])
            orig_comp = f.read(b["comp_size"])
            content = bytes(decompression.decompress(orig_comp, b["real_size"]))
            best = None
            for lvl in (12, 9, 6):
                c = lz4b.compress(content, mode="high_compression",
                                  compression=lvl, store_size=False)
                if best is None or len(c) < len(best):
                    best = c
            # only rewrite where we actually shrink it (that's the variable under
            # test); leave a block alone if we can't beat the game's encoder
            if len(best) >= b["comp_size"]:
                continue
            roundtrip_ok = bytes(decompression.decompress(best, b["real_size"])) == content
            chunks.append({
                "comp_offset": b["comp_offset"],
                "orig_comp_size": b["comp_size"],
                "comp_size_field_offset": b["comp_size_field_offset"],
                "real_size": b["real_size"],
                "new_compressed": best,
                "fits": True,
                "roundtrip_ok": roundtrip_ok,
            })
    return {
        "archive_path": str(arch_path), "archive_name": arch_name,
        "archive_index": off.archive_index, "asset_offset": off.offset,
        "asset_size": sz.value, "slot": slot, "n_blocks": len(chunks),
        "all_fit": all(c["roundtrip_ok"] for c in chunks) and bool(chunks),
        "chunks": chunks,
    }


def apply_reencode_block(game_root: Path, plan_result: dict) -> dict:
    """Same write discipline as apply_plan(): backup, exact-length write,
    shrink comp_size header field only if the new length differs."""
    if not plan_result["all_fit"]:
        raise ValueError("plan says NOT fit/roundtrip-ok -- refusing to apply")
    arch_path = Path(plan_result["archive_path"])
    c = plan_result
    with open(arch_path, "r+b") as f:
        f.seek(c["comp_offset"])
        orig_bytes = f.read(c["orig_comp_size"])
        f.seek(c["comp_size_field_offset"])
        orig_header = f.read(4)
        backup = {
            "comp_offset": c["comp_offset"],
            "orig_comp_size": c["orig_comp_size"],
            "orig_hex": orig_bytes.hex(),
            "comp_size_field_offset": c["comp_size_field_offset"],
            "orig_header_hex": orig_header.hex(),
        }
        new_len = len(c["new_compressed"])
        f.seek(c["comp_offset"])
        f.write(c["new_compressed"])
        if new_len != c["orig_comp_size"]:
            f.seek(c["comp_size_field_offset"])
            f.write(struct.pack("<I", new_len))

    backup_path = game_root / BACKUP_NAME
    manifest = {"archive_path": plan_result["archive_path"],
                "archive_name": plan_result["archive_name"], "backups": [backup]}
    existing = []
    if backup_path.exists():
        existing = json.loads(backup_path.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = [existing]
    existing.append(manifest)
    backup_path.write_text(json.dumps(existing, indent=1), encoding="utf-8")
    return {"ok": True, "archive": plan_result["archive_name"],
            "block_index": plan_result["block_index"]}


# ------------------------------------------------------------------ ASSET GROWTH
# Round 5 (2026-08-12): the no-growth constraint above ("len(new_blob) > sz.value
# -- cannot fit") is now lifted for the case that matters -- growing a SPAN/ASSET
# whose covering blocks can be RECLAIMED and re-pointed at a fresh, unclaimed
# region of the archive's own virtual (real) address space, entirely WITHOUT
# touching the toc's Archives section (no new archive_index/filename/chunkmap --
# the two mechanisms already proven to correlate with the boot stall on the
# updated v3.618+ exe, see msmr_deploy.py's apply()/apply_inplace() docstrings).
#
# Measured on the live g00s019/span-8 loc asset before building this (see
# msmr_growth_probe.py/probe2.py in scratch): the archive's real (virtual)
# address space is PACKED with zero gaps end to end -- growing an asset's LAST
# block in place always collides with whatever asset immediately follows it in
# real-space (confirmed: a real block starts at exactly our asset's old end).
# There is also zero free slack in the block-map TABLE region (first block's
# comp_offset sits immediately at blocks_header_end) and zero trailing slack on
# disk (file size == last block's comp_offset+comp_size exactly) -- so neither
# "extend the last block" nor "append a genuinely new table record for free" is
# available without a much larger whole-archive comp_offset shift.
#
# The mechanism actually used instead: RELOCATE the whole asset to a fresh
# address at the END of the archive's virtual space (V_END = the max
# real_offset+real_size across every block in the table -- guaranteed unclaimed,
# confirmed by the same probe: 0 gaps anywhere else in the table means nothing
# else could possibly claim it either). The asset's OWN currently-covering block
# records are REUSED IN PLACE (same 32-byte table positions, same table size,
# same blocks_header_end -- ZERO shift of any OTHER block's comp_offset) to
# describe the NEW content instead; if fewer new blocks are needed than the
# asset used to occupy, the leftover old records are left completely untouched
# (they keep describing the OLD, now-orphaned real-address range and the OLD,
# still-intact compressed bytes on disk -- dead, unreferenced, harmless, exactly
# the same "dead space" pattern already used elsewhere in this file for a
# shrunk comp_size's leftover bytes). New block content is compressed with the
# same LZ4 the game's own encoder uses and simply APPENDED at the current
# physical end of the archive file (a pure append -- no existing byte moves).
#
# toc footprint: exactly TWO u32 fields change, both for OUR OWN asset's single
# slot -- Offsets.offset (relocated to V_END) and Sizes.value (the new total
# length). The Archives section is completely untouched (same archive_index,
# no new row); every OTHER asset's Offsets/Sizes/Spans/ids entries are
# byte-identical before and after, since none of their real_offset/comp_offset
# values move.
#
# 🔴 LIMIT (documented, not yet implemented): this can reclaim at most as many
# new blocks as the asset's OWN current block count (n_reclaim). If the grown
# content ever needs MORE 262144-byte blocks than that, plan_growth() refuses
# with a clear error rather than guess at the much riskier whole-archive
# comp_offset-shift extension (insert K new table records -> every block's
# comp_offset after the table shifts by 32*K, requiring a full-file rewrite).
# For span 8 today that ceiling is 24 blocks = up to ~6.29 MB of total content
# (vs. the current ~6.04 MB) -- ample headroom for the growth needed so far.
GROWTH_BACKUP_NAME = ".tm_he_dsar_growth_backup.json"
GROWTH_TOC_BACKUP_NAME = "toc.tm_he_dsar_growth_toc_backup"
GROWTH_BLOCK_SIZE = 262144          # matches the game's own vanilla block size
GROWTH_U6_CONST = 1431655683        # constant across all 12,722 blocks in g00s019 (measured)
GROWTH_U7_CONST = 1431655765        # == 0x55555555, likewise constant everywhere


def _plan_growth_slot(t, game_root: Path, slot: int, new_blob: bytes,
                       compress_mode: str = "high_compression") -> dict:
    off = t.get_offsets_section().entries[slot]
    sz = t.get_sizes_section().entries[slot]
    arch = t.get_archives_section().archives[off.archive_index]
    arch_name = bytes(arch.filename).split(b"\x00", 1)[0].decode()
    arch_path = msmr_deploy.arch_dir(game_root) / arch_name

    with open(arch_path, "rb") as f:
        magic = f.read(4)
        if magic != b"DSAR":
            raise ValueError(f"{arch_name} is not DSAR-compressed (magic={magic!r})")
        blocks = _read_block_map(f)
        f.seek(0, 2)
        orig_file_size = f.tell()

    covering = sorted(
        ((i, b) for i, b in enumerate(blocks)
         if (b["real_offset"] + b["real_size"]) > off.offset and b["real_offset"] < off.offset + sz.value),
        key=lambda pair: pair[1]["real_offset"],
    )
    n_reclaim = len(covering)
    n_blocks_needed = -(-len(new_blob) // GROWTH_BLOCK_SIZE) if new_blob else 1  # ceil, min 1
    if n_blocks_needed > n_reclaim:
        raise ValueError(
            f"growth needs {n_blocks_needed} blocks ({len(new_blob):,} B / "
            f"{GROWTH_BLOCK_SIZE:,} B per block) but only {n_reclaim} reclaimable "
            f"table slots exist for this asset (its own current block count) -- "
            f"the whole-archive comp_offset-shift extension is not implemented, "
            f"refusing rather than guess at it"
        )

    v_end = max(b["real_offset"] + b["real_size"] for b in blocks)
    reclaim_rec_offsets = [32 + i * 32 for i, _b in covering[:n_blocks_needed]]

    chunks = []
    real_cursor, comp_cursor, o = v_end, orig_file_size, 0
    for rec_off in reclaim_rec_offsets:
        chunk = new_blob[o:o + GROWTH_BLOCK_SIZE]
        o += len(chunk)
        if compress_mode == "literal_only":
            comp = _lz4_literal_only(chunk)
        else:
            comp = lz4b.compress(chunk, mode="high_compression", store_size=False)
        roundtrip_ok = bytes(decompression.decompress(comp, len(chunk))) == chunk
        chunks.append({
            "table_record_offset": rec_off,
            "real_offset": real_cursor,
            "comp_offset": comp_cursor,
            "real_size": len(chunk),
            "comp_size": len(comp),
            "new_compressed": comp,
            "roundtrip_ok": roundtrip_ok,
        })
        real_cursor += len(chunk)
        comp_cursor += len(comp)

    all_fit = o == len(new_blob) and all(c["roundtrip_ok"] for c in chunks)
    return {
        "archive_path": str(arch_path),
        "archive_name": arch_name,
        "archive_index": off.archive_index,
        "slot": slot,
        "old_offset": off.offset,
        "old_size": sz.value,
        "new_offset": v_end,
        "new_size": len(new_blob),
        "orig_file_size": orig_file_size,
        "n_blocks": n_blocks_needed,
        "n_reclaimable": n_reclaim,
        "all_fit": all_fit,
        "chunks": chunks,
    }


def plan_growth(game_root: Path, span: int, asset_id: int, new_blob: bytes,
                 compress_mode: str = "high_compression") -> dict:
    """Like plan(), but relocates the asset to a fresh address if new_blob is
    LARGER than its current declared size -- see the module-level comment
    above for the full mechanism and its documented limit."""
    t = msmr_deploy.read_toc(msmr_deploy.toc_path(game_root))
    t.set_archives_dir(str(msmr_deploy.arch_dir(game_root)))
    slot = msmr_deploy.find_asset_index(t, span, asset_id)
    return _plan_growth_slot(t, game_root, slot, new_blob, compress_mode)


def plan_growth_by_path(game_root: Path, asset_path: str, new_blob: bytes,
                         compress_mode: str = "high_compression") -> dict:
    """plan_growth() for a path-addressed asset (e.g. a font), same lookup as
    plan_by_path()."""
    msmr_deploy._dat1lib()
    import dat1lib.crc64 as crc64
    t = msmr_deploy.read_toc(msmr_deploy.toc_path(game_root))
    t.set_archives_dir(str(msmr_deploy.arch_dir(game_root)))
    aid = crc64.hash(asset_path)
    ents = [e for e in (t.get_asset_entries_by_assetid(aid, stop_on_first=True) or []) if e]
    if not ents:
        raise ValueError(f"asset path {asset_path!r} (aid=0x{aid:016X}) not found in toc")
    slot = ents[0].index
    return _plan_growth_slot(t, game_root, slot, new_blob, compress_mode)


def apply_growth(game_root: Path, plan_result: dict) -> dict:
    """Write plan_result: append new compressed blocks at the archive's current
    EOF, overwrite the reclaimed table records in place (same 32-byte
    positions -- no shift of anything else), then relocate the asset's toc
    Offsets/Sizes entries to the new address/size. Backs up the exact table
    bytes touched + the original file length (for a clean truncate-back) +
    (once) the whole toc, so revert_growth() is a pure undo with no knowledge
    of block-map structure needed at revert time."""
    if not plan_result["all_fit"]:
        raise ValueError("plan_growth says NOT all blocks fit -- refusing to apply")

    game_root = Path(game_root)
    arch_path = Path(plan_result["archive_path"])
    orig_size = plan_result["orig_file_size"]

    record_backups = []
    with open(arch_path, "r+b") as f:
        for c in plan_result["chunks"]:
            f.seek(c["table_record_offset"])
            record_backups.append({
                "table_record_offset": c["table_record_offset"],
                "orig_hex": f.read(32).hex(),
            })
        f.seek(0, 2)
        if f.tell() != orig_size:
            raise ValueError(
                f"archive size changed ({f.tell():,} != planned {orig_size:,}) since "
                f"plan_growth() was called -- refusing to apply a stale plan"
            )
        for c in plan_result["chunks"]:
            f.write(c["new_compressed"])
        for c in plan_result["chunks"]:
            f.seek(c["table_record_offset"])
            f.write(struct.pack(
                "<IIIIIIII", c["real_offset"], 0, c["comp_offset"], 0,
                c["real_size"], c["comp_size"], GROWTH_U6_CONST, GROWTH_U7_CONST,
            ))
        f.flush()
        os.fsync(f.fileno())

    toc = msmr_deploy.toc_path(game_root)
    toc_backup = game_root / GROWTH_TOC_BACKUP_NAME
    if not toc_backup.is_file():
        shutil.copy2(toc, toc_backup)
    t = msmr_deploy.read_toc(toc)
    off = t.get_offsets_section().entries[plan_result["slot"]]
    sz = t.get_sizes_section().entries[plan_result["slot"]]
    off.offset = plan_result["new_offset"]
    sz.value = plan_result["new_size"]
    msmr_deploy.refresh(t, msmr_deploy.TAG_SIZES, msmr_deploy.TAG_OFFSETS)
    msmr_deploy.write_toc(t, toc)

    growth_backup = game_root / GROWTH_BACKUP_NAME
    manifest = {
        "archive_path": plan_result["archive_path"],
        "archive_name": plan_result["archive_name"],
        "slot": plan_result["slot"],
        "old_offset": plan_result["old_offset"],
        "old_size": plan_result["old_size"],
        "orig_file_size": orig_size,
        "record_backups": record_backups,
    }
    existing = []
    if growth_backup.is_file():
        existing = json.loads(growth_backup.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            existing = [existing]
    existing.append(manifest)
    growth_backup.write_text(json.dumps(existing, indent=1), encoding="utf-8")

    return {"ok": True, "archive": plan_result["archive_name"],
            "new_offset": plan_result["new_offset"], "new_size": plan_result["new_size"],
            "n_blocks_written": len(plan_result["chunks"])}


def revert_growth(game_root: Path) -> dict:
    game_root = Path(game_root)
    growth_backup = game_root / GROWTH_BACKUP_NAME
    toc_backup = game_root / GROWTH_TOC_BACKUP_NAME
    if not growth_backup.is_file():
        return {"ok": True, "result": "no growth backup present, nothing to revert"}
    manifests = json.loads(growth_backup.read_text(encoding="utf-8"))
    if not isinstance(manifests, list):
        manifests = [manifests]
    restored = 0
    for m in reversed(manifests):
        arch_path = Path(m["archive_path"])
        with open(arch_path, "r+b") as f:
            for rb in m["record_backups"]:
                f.seek(rb["table_record_offset"])
                f.write(bytes.fromhex(rb["orig_hex"]))
                restored += 1
            f.truncate(m["orig_file_size"])
    growth_backup.unlink()
    if toc_backup.is_file():
        shutil.copy2(toc_backup, msmr_deploy.toc_path(game_root))
        toc_backup.unlink()
    return {"ok": True, "records_restored": restored}


def status_growth(game_root: Path) -> dict:
    game_root = Path(game_root)
    growth_backup = game_root / GROWTH_BACKUP_NAME
    if not growth_backup.is_file():
        return {"backup": False}
    manifests = json.loads(growth_backup.read_text(encoding="utf-8"))
    if not isinstance(manifests, list):
        manifests = [manifests]
    return {"backup": True, "n_growths": len(manifests),
            "archives_touched": [m["archive_name"] for m in manifests]}


def verify_readback(game_root: Path, span: int, asset_id: int) -> bytes:
    """Re-read the asset the normal way (through dat1lib's own extract_asset,
    which is the exact code path the game engine's reader logic mirrors) and
    return the raw bytes -- proves the in-place block overwrite decodes
    correctly, not just that the write happened."""
    t = msmr_deploy.read_toc(msmr_deploy.toc_path(game_root))
    t.set_archives_dir(str(msmr_deploy.arch_dir(game_root)))
    slot = msmr_deploy.find_asset_index(t, span, asset_id)
    return bytes(t.extract_asset(slot))
