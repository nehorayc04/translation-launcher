"""
Marvel's Spider-Man 2 - native Hebrew-mod applier (no Overstrike).

Insomniac's engine resolves every asset through a Table-of-Contents file
(`<game>/toc`, format I29 / "TOC2": an UNCOMPRESSED DAT1 wrapped as
[u32 magic 0x34E89035][u32 logical_len][raw DAT1 '1TAD'…]). Each asset's
location is one `RcraSizeEntry` {value=size, archive_index, offset,
header_offset} indexed parallel to the asset-id table, grouped into spans.

Overstrike applies a mod by (1) writing the patched asset bytes as a RAW
DAT1 file under `<game>/d/mods/`, (2) appending an archive entry naming
that file to the TOC's ArchivesSection, and (3) redirecting the asset's
size-entry to {archive_index=<new>, offset=0, value=<len>}. No big archive
is ever repacked. We replicate exactly that, in Python, via the vendored
`dat1lib` parser (which round-trips the inner DAT1 byte-for-byte under the
RECALCULATE_ORIGINAL_ORDER strategy - verified against the pristine TOC).

A `.stage`/`.modular` is a ZIP: each patched asset is an entry named
`{span}/{UPPER_HEX_ASSET_ID}` holding raw DAT1 bytes; `info.json` is
metadata; a `.modular` nests its `.stage`(s) under `modules/`.

Everything is reversible: the live TOC is backed up before the first write,
and our mod files + a manifest let `revert()` restore the exact prior state
(any other mods the user had stay intact - we only append + redirect).
Never raises out of the public API; returns structured dicts.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import struct
import sys
import zipfile
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

ProgressCB = Callable[[str, float, str], None]

TOC_MAGIC_I29 = 0x34E89035
_MODS_SUBDIR  = ("d", "mods")          # <game>/d/mods/
_OUR_PREFIX   = "tm_he_"               # our mod-archive filenames live here
_BACKUP_NAME  = "toc.tm_he_backup"     # pristine-before-our-apply TOC copy
_MANIFEST     = ".tm_he_manifest.json" # under d/mods/ - tracks what we wrote


# ─────────────────────────────────────────────────────────────
# dat1lib loader - vendored under translation_manager/vendor/ in the
# shipped build; falls back to the in-repo research copy for dev.
# ─────────────────────────────────────────────────────────────
def _load_dat1lib():
    # dat1lib uses absolute internal imports (`import dat1lib.types…`), so it
    # must resolve as a TOP-LEVEL package. Add its parent dir to sys.path and
    # import plainly - for the frozen build (vendored under
    # translation_manager/vendor/) and dev (the in-repo research copy).
    here = Path(__file__).resolve().parent
    base = getattr(sys, "_MEIPASS", None)
    cands = [here / "vendor"]
    if base:
        cands.append(Path(base) / "translation_manager" / "vendor")
    cands.append(here.parent / "games" / "spiderman2" / "tools" / "ALERT")
    for cand in cands:
        if (cand / "dat1lib").is_dir():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            import dat1lib  # type: ignore
            return dat1lib
    import dat1lib  # type: ignore - last resort (already on sys.path?)
    return dat1lib


# ─────────────────────────────────────────────────────────────
# .stage / .modular parsing
# ─────────────────────────────────────────────────────────────
def _parse_one_stage(zf: zipfile.ZipFile) -> list[tuple[int, int, bytes]]:
    """Read every '{span}/{HEXID}' asset entry from an open .stage zip."""
    out: list[tuple[int, int, bytes]] = []
    for name in zf.namelist():
        base = name.replace("\\", "/")
        if base.endswith("/") or base.rsplit("/", 1)[-1] == "info.json":
            continue
        parts = base.split("/")
        if len(parts) < 2:
            continue
        span_s, id_s = parts[-2], parts[-1]
        try:
            span = int(span_s)
            asset_id = int(id_s, 16)
        except ValueError:
            continue
        out.append((span, asset_id, zf.read(name)))
    return out


def parse_payload(path: Path) -> list[tuple[int, int, bytes]]:
    """Parse a .stage OR .modular into [(span, asset_id, dat1_bytes)].

    A .modular nests its .stage(s) under 'modules/'; we take every asset
    from every contained stage (the Hebrew mod's stages are disjoint)."""
    assets: list[tuple[int, int, bytes]] = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        inner_stages = [n for n in names if n.replace("\\", "/").lower().endswith(".stage")]
        if inner_stages:
            for sname in inner_stages:
                with zipfile.ZipFile(__import__("io").BytesIO(zf.read(sname))) as inner:
                    assets.extend(_parse_one_stage(inner))
        else:
            assets.extend(_parse_one_stage(zf))
    return assets


# ─────────────────────────────────────────────────────────────
# TOC helpers
# ─────────────────────────────────────────────────────────────
def _toc_path(game_root: Path) -> Path:
    return Path(game_root) / "toc"


def _mods_dir(game_root: Path) -> Path:
    return Path(game_root).joinpath(*_MODS_SUBDIR)


def _read_toc(dat1lib, toc_path: Path):
    with open(toc_path, "rb") as f:
        t = dat1lib.read(f)
    # Preserve the original section order + padding so the serialized inner
    # DAT1 is byte-faithful to what the engine expects.
    import dat1lib.types.dat1 as _d1
    t.dat1.set_recalculation_strategy(_d1.RECALCULATE_ORIGINAL_ORDER)
    return t


def _write_toc(t, toc_path: Path) -> None:
    """Serialize the modified TOC2 and write [magic][logical_len][raw DAT1].
    (dat1lib's own .save() zlib-compresses - wrong for I29 - so we wrap the
    raw DAT1 ourselves, atomically.)"""
    import io
    buf = io.BytesIO()
    t.dat1.save(buf)
    raw = buf.getvalue()
    blob = struct.pack("<II", TOC_MAGIC_I29, len(raw)) + raw
    tmp = toc_path.with_suffix(".tm_he_tmp")
    with open(tmp, "wb") as f:
        f.write(blob)
    os.replace(tmp, toc_path)


def _find_size_index(t, span: int, asset_id: int) -> int:
    """Resolve the size-entry index for (span, asset_id) by scanning the
    asset-id table within the span's [asset_index, +count) range."""
    spans = t.get_spans_section()
    if span >= len(spans.entries):
        return -1
    sp = spans.entries[span]
    lo, cnt = sp.asset_index, sp.count
    assets = t.get_assets_section()
    ids = getattr(assets, "ids", None) or getattr(assets, "values", None) or []
    for i in range(lo, min(lo + cnt, len(ids))):
        if ids[i] == asset_id:
            return i
    return -1


def _serialize_sizes_rcra(sec) -> bytearray:
    """Correct RCRA SizesSection serializer (dat1lib's own save() emits the
    older 12-byte MSMR layout and corrupts I29 size entries)."""
    out = bytearray()
    for e in sec.entries:
        out += struct.pack("<IIIi", e.value, e.archive_index, e.offset, e.header_offset)
    return out


def _serialize_archives_rcra(sec) -> bytearray:
    """Correct RCRA ArchivesSection serializer (66-byte entries:
    filename[40] + <QQIHI>)."""
    out = bytearray()
    for e in sec.archives:
        fn = bytes(e.filename)[:40].ljust(40, b"\x00")
        out += fn + struct.pack("<QQIHI", e.a, e.b, e.c, e.d, e.e)
    return out


def _append_archive(t, rel_name: str) -> int:
    """Append an ArchiveFileEntry naming a mod file (e.g. 'd\\mods\\tm_he_0'),
    cloning the fixed a/b/c/d/e fields from an existing entry. Returns the
    new archive index."""
    import copy
    arch = t.get_archives_section()
    template = arch.archives[-1]
    entry = copy.deepcopy(template)
    width = len(template.filename)               # fixed 40-byte name field
    raw = rel_name.encode("ascii", "replace")[:width]
    entry.filename = bytearray(raw + b"\x00" * (width - len(raw)))
    new_index = len(arch.archives)
    arch.archives.append(entry)
    return new_index


# ─────────────────────────────────────────────────────────────
# Game-update awareness - never restore a stale (pre-update) backup over a
# freshly-patched toc (that would downgrade the toc vs. the updated archives and
# can crash the updated game). The toc is "ours" iff it still references our
# tm_he_* mod archives; a game patch rewrites the toc and drops those.
# ─────────────────────────────────────────────────────────────
def _toc_is_ours(t) -> bool:
    try:
        arch = t.get_archives_section()
    except Exception:
        return False
    for e in getattr(arch, "archives", []) or []:
        fn = bytes(getattr(e, "filename", b"") or b"").split(b"\x00", 1)[0]
        if b"tm_he_" in fn:
            return True
    return False


def _discard_stale(game_root: Path) -> None:
    """Drop our manifest + mod files + the (now-stale) backup WITHOUT restoring
    the backup - used when a game update already reset the toc to clean vanilla,
    so restoring the old backup would downgrade the fresh toc."""
    game_root = Path(game_root)
    mods = _mods_dir(game_root)
    for p in (game_root / _BACKUP_NAME, mods / _MANIFEST):
        try: p.unlink()
        except OSError: pass
    if mods.is_dir():
        for f in mods.glob(_OUR_PREFIX + "*"):
            try: f.unlink()
            except OSError: pass


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────
def is_applied(game_root: Path) -> bool:
    """Applied = our manifest exists AND the live toc still matches the toc we
    wrote (size + mtime). A game update rewrites the toc → the stat differs →
    we report NOT applied, so the UI prompts a clean reinstall and never trusts
    the now-stale backup. (Cheap: one os.stat, no toc parse.)"""
    man = _mods_dir(game_root) / _MANIFEST
    if not man.is_file():
        return False
    try:
        meta = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True  # manifest present but unreadable → assume applied (conservative)
    rec = meta.get("toc_stat")
    if not rec:
        return True  # legacy manifest (no stat recorded) → prior behavior
    try:
        st = _toc_path(game_root).stat()
    except OSError:
        return False
    return rec.get("size") == st.st_size and rec.get("mtime_ns") == st.st_mtime_ns


def apply(game_root: Path, payload_files: list[Path], cb: ProgressCB | None = None) -> dict:
    """Apply the Hebrew mod (one or more .stage/.modular files) to the game's
    TOC + a fresh raw mod archive per asset. Idempotent: re-applying reverts
    a prior apply first so we never stack redirects.

    Returns {ok, count, error}."""
    try:
        dat1lib = _load_dat1lib()
    except Exception as e:                                  # pragma: no cover
        return {"ok": False, "error": f"dat1lib לא זמין: {e}"}

    game_root = Path(game_root)
    toc = _toc_path(game_root)
    if not toc.is_file():
        return {"ok": False, "error": "קובץ ה-toc של המשחק לא נמצא - ודא את נתיב ההתקנה"}

    # Collect all (span, asset_id, bytes) across every payload file.
    assets: list[tuple[int, int, bytes]] = []
    for p in payload_files:
        p = Path(p)
        if not p.is_file():
            return {"ok": False, "error": f"קובץ מוד חסר: {p.name}"}
        assets.extend(parse_payload(p))
    if not assets:
        return {"ok": False, "error": "לא נמצאו נכסים בקבצי המוד"}

    if cb:
        cb("apply", 5.0, "קורא את טבלת הנכסים…")
    t = _read_toc(dat1lib, toc)

    # GAME-UPDATE-AWARE clean slate. Decide from the toc ITSELF, not the
    # (possibly stale) manifest:
    #   • toc still references our tm_he_* archives → a prior apply is live and
    #     the backup is the valid clean base → revert to it, then re-read.
    #   • toc does NOT reference them → either never applied, or a game update
    #     already reset the toc to clean vanilla → DROP any stale backup/manifest
    #     WITHOUT restoring (restoring would downgrade the fresh toc → crash).
    if _toc_is_ours(t):
        if (game_root / _BACKUP_NAME).is_file():
            revert(game_root)
            t = _read_toc(dat1lib, toc)
        else:
            # The live toc is already OURS (references tm_he_*) but the pristine
            # backup is gone (deleted out-of-band). Proceeding would (a) capture
            # this MODDED toc as the "original" backup and (b) stack new archive
            # redirects on top of the old ones → an ever-growing, un-restorable
            # toc. Refuse and point the user at a game-file verify (which restores
            # a clean vanilla toc) instead of corrupting further.
            return {"ok": False, "error":
                    "קובץ ה-toc כבר ממודל אך גיבוי הווניל חסר. אמת את קבצי המשחק "
                    "(Steam → אימות שלמות הקבצים) ואז התקן מחדש."}
    elif is_applied(game_root) or (game_root / _BACKUP_NAME).is_file():
        _discard_stale(game_root)

    mods = _mods_dir(game_root)
    mods.mkdir(parents=True, exist_ok=True)

    # Back up the CURRENT (now-clean) TOC once (captures any OTHER mods present).
    backup = game_root / _BACKUP_NAME
    if not backup.exists():
        shutil.copy2(toc, backup)

    sizes = t.get_sizes_section()

    written: list[str] = []
    redirected = 0
    for i, (span, asset_id, blob) in enumerate(assets):
        idx = _find_size_index(t, span, asset_id)
        if idx < 0:
            log.warning("spiderman2_mod: asset %d/%X not found in toc (skipped)", span, asset_id)
            continue
        name = f"{_OUR_PREFIX}{i}"
        rel = "d\\mods\\" + name
        archive_path = mods / name
        with open(archive_path, "wb") as f:
            f.write(blob)
        written.append(name)
        arc_idx = _append_archive(t, rel)
        se = sizes.entries[idx]
        se.archive_index = arc_idx
        se.offset = 0
        se.value = len(blob)
        redirected += 1
        if cb:
            cb("apply", 5.0 + 90.0 * (i + 1) / len(assets), f"מחיל נכס {i + 1}/{len(assets)}")

    if redirected == 0:
        # Nothing matched - back the writes out so we don't leave junk.
        for n in written:
            try: (mods / n).unlink()
            except OSError: pass
        return {"ok": False, "error": "אף נכס במוד לא תאם ל-toc של המשחק (ייתכן שהמשחק עודכן)"}

    # Re-serialize the two sections we mutated back into the DAT1 byte buffer.
    # dat1lib's stock SizesSection/ArchivesSection.save() emit the older MSMR
    # layout, so override them with correct RCRA serializers before refresh.
    arch_sec = t.get_archives_section()
    sizes.save    = lambda s=sizes:    _serialize_sizes_rcra(s)
    arch_sec.save = lambda s=arch_sec: _serialize_archives_rcra(s)
    t.dat1.refresh_section_data(sizes.TAG)
    t.dat1.refresh_section_data(arch_sec.TAG)

    if cb:
        cb("apply", 97.0, "כותב toc מעודכן…")
    _write_toc(t, toc)

    try:
        _st = toc.stat()
        _toc_stat = {"size": _st.st_size, "mtime_ns": _st.st_mtime_ns}
    except OSError:
        _toc_stat = None
    (mods / _MANIFEST).write_text(
        json.dumps({"archives": written, "redirected": redirected, "toc_stat": _toc_stat},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if cb:
        cb("apply", 100.0, "הותקן")
    return {"ok": True, "count": redirected, "error": ""}


def revert(game_root: Path) -> dict:
    """Restore the TOC backup taken before our apply and delete our mod files.
    Leaves any other mods that were present intact. {ok, error}."""
    game_root = Path(game_root)
    toc = _toc_path(game_root)
    backup = game_root / _BACKUP_NAME
    mods = _mods_dir(game_root)
    try:
        if backup.is_file():
            # Restore ONLY if the live toc is still ours. If a game update reset
            # the toc (not ours), the backup is STALE → dropping our files is
            # enough (the current toc is already clean vanilla - never downgrade
            # it, that would mismatch the updated archives and can crash).
            restore = True
            try:
                if not _toc_is_ours(_read_toc(_load_dat1lib(), toc)):
                    restore = False
            except Exception:
                restore = True   # unsure → restore (prior behavior)
            if restore:
                shutil.copy2(backup, toc)
            backup.unlink()
        # Remove our mod archives + manifest.
        man = mods / _MANIFEST
        names: list[str] = []
        if man.is_file():
            try:
                names = json.loads(man.read_text(encoding="utf-8")).get("archives", [])
            except (OSError, json.JSONDecodeError):
                names = []
        for n in names:
            try: (mods / n).unlink()
            except OSError: pass
        # Defensive sweep for any stray tm_he_* we wrote.
        if mods.is_dir():
            for f in mods.glob(_OUR_PREFIX + "*"):
                try: f.unlink()
                except OSError: pass
        try: man.unlink()
        except OSError: pass
        return {"ok": True, "error": ""}
    except Exception as e:                                  # pragma: no cover
        return {"ok": False, "error": str(e)}
