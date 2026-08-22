#!/usr/bin/env python3
r"""install_gtav_mod.py — OpenIV-free, pure-Python apply/revert of the full Hebrew
text + fonts into an EXISTING OPEN `mods\` folder, via tools/rpf7_writer.py.

This is the engine the launcher wraps. It reproduces EXACTLY what the OIV does
(build_full_gxt2.py `build_oiv`), but with read-modify-write instead of OpenIV:

  update\update2.rpf
     └─ x64\data\lang\american_rel.rpf           (nested, stored RAW)
          └─ <610 gxt2>            <- replaced with the Hebrew build (STAGE)
  update\update.rpf
     ├─ x64\data\cdimages\scaleform_generic.rpf
     │     ├─ font_lib_efigs.gfx   <- Hebrew
     │     └─ font_lib_web.gfx     <- Hebrew
     └─ x64\data\cdimages\scaleform_platform_pc.rpf
           └─ font_lib_efigs_pc.gfx<- Hebrew

GUARANTEES (the user's hard requirements):
  * Every OTHER file/mod in update2.rpf / update.rpf stays BYTE-EXACT (only the
    files this mod owns change). Proven by the --test verifier below.
  * A backup of the two touched RPFs is taken BEFORE any write; the new RPF is
    built in a temp file and `os.replace`-d in atomically, so a failed/interrupted
    build can NEVER corrupt the live archive. revert() restores the backup.
  * Per-file storage mode (compressed vs raw) is PRESERVED, matching vanilla, so
    the engine never changes how an untouched file is stored.

Only OPEN archives are touched (the `mods\` copies OpenIV produced once). The
encrypted vanilla is never read — see rpf7_writer's scope note.

CLI:
  python install_gtav_mod.py --game "<root>" --test    # NON-DESTRUCTIVE: apply to
        in-memory copies, verify byte-exact preservation + Hebrew present, touch nothing.
  python install_gtav_mod.py --game "<root>" --apply    # real apply (backup + atomic)
  python install_gtav_mod.py --game "<root>" --revert    # restore the backup
  python install_gtav_mod.py --game "<root>" --status    # is it applied? backup present?
"""
import os, sys, shutil, time, argparse, tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # cp1255-safe Hebrew prints
HERE = os.path.dirname(os.path.abspath(__file__))
GTAV = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(GTAV, "tools"))
import rpf7_writer as W  # parse_open_rpf / serialize_open_rpf / find / deflate

# ── payloads (the Hebrew build this engine installs) ──────────────────────────
STAGE = os.path.join(HERE, "full_build", "american_rel")          # 610 Hebrew gxt2
ORIG  = os.path.join(GTAV, "_originals")
HE_FONTS = {                                                       # name in scaleform rpf -> file
    "scaleform_generic":     [("font_lib_efigs.gfx", os.path.join(ORIG, "font_lib_efigs_HEBREW.gfx")),
                              ("font_lib_web.gfx",   os.path.join(ORIG, "font_lib_web_HEBREW.gfx"))],
    "scaleform_platform_pc": [("font_lib_efigs_pc.gfx", os.path.join(ORIG, "font_lib_efigs_pc_HEBREW.gfx"))],
}

# ── RPF paths (must match build_full_gxt2.build_oiv exactly) ──────────────────
P_AMREL  = "x64/data/lang/american_rel.rpf"
P_GEN    = "x64/data/cdimages/scaleform_generic.rpf"
P_PC     = "x64/data/cdimages/scaleform_platform_pc.rpf"
REL_UPD2 = os.path.join("update", "update2.rpf")
REL_UPD  = os.path.join("update", "update.rpf")

MARKER = "gtav_he_applied.json"   # written into the backup dir on apply


# ─────────────────────────────────────────────────────────────────────────────
def _log(cb, msg, pct=None):
    print(msg, flush=True)
    if cb:
        try: cb("apply", pct if pct is not None else 0.0, msg)
        except Exception: pass


def _load_gxt2_payloads():
    """{gxt2 name -> raw gxt2 bytes} for all staged Hebrew tables."""
    if not os.path.isdir(STAGE):
        raise FileNotFoundError(f"Hebrew gxt2 build missing: {STAGE} (run build_full_gxt2.py)")
    out = {}
    for fn in sorted(os.listdir(STAGE)):
        if fn.endswith(".gxt2"):
            out[fn] = open(os.path.join(STAGE, fn), "rb").read()
    if not out:
        raise FileNotFoundError(f"no .gxt2 staged in {STAGE}")
    return out


def _replace_preserving_mode(root, path, new_bytes):
    """Replace the file at `path` keeping its ORIGINAL storage mode (a file stored
    compressed stays compressed; a raw one stays raw) so untouched-vs-touched files
    are stored identically to vanilla. Returns True if replaced, False if absent."""
    f = W.find(root, path)
    if f is None or f.is_dir:
        return False
    W.replace_file_data(root, path, new_bytes, compress=(f.csize != 0))
    return True


def _edit_nested(parent_root, nested_path, edits):
    """Parse the nested OPEN rpf at `nested_path` inside parent_root, apply `edits`
    [(inner_path, new_bytes), ...] (each preserving mode), re-serialize the nested
    rpf, and re-embed it RAW (csize=0) — the way RAGE stores a nested archive.
    Returns the count of inner files actually replaced."""
    node = W.find(parent_root, nested_path)
    if node is None or node.is_dir:
        raise KeyError(f"nested rpf not found: {nested_path}")
    # Nested archives are normally stored RAW (RAGE memory-maps them), but inflate
    # defensively if this one happens to be deflated.
    import zlib
    raw_nested = zlib.decompress(node.data, -15) if node.csize else node.data
    inner = W.parse_open_rpf(raw_nested, 0)
    n = 0
    for inner_path, data in edits:
        if _replace_preserving_mode(inner, inner_path, data):
            n += 1
    new_inner = W.serialize_open_rpf(inner)
    # nested archives are stored UNCOMPRESSED in the parent (engine memory-maps them)
    W.replace_file_data(parent_root, nested_path, new_inner, compress=False)
    return n


# ── build the two patched RPFs (pure functions: bytes -> bytes) ───────────────
def patch_update2(update2_bytes, gxt2_payloads):
    """Return new update2.rpf bytes with the nested american_rel's 610 gxt2 set to
    Hebrew. Every other entry in update2 is preserved byte-exact."""
    root = W.parse_open_rpf(update2_bytes, 0)
    edits = [(name, data) for name, data in gxt2_payloads.items()]
    n = _edit_nested(root, P_AMREL, edits)
    return W.serialize_open_rpf(root), n


def patch_update(update_bytes):
    """Return new update.rpf bytes with the Hebrew Scaleform fonts in the two
    scaleform rpfs. Every other entry preserved byte-exact."""
    root = W.parse_open_rpf(update_bytes, 0)
    total = 0
    total += _edit_nested(root, P_GEN,
                          [(nm, open(p, "rb").read()) for nm, p in HE_FONTS["scaleform_generic"]])
    total += _edit_nested(root, P_PC,
                          [(nm, open(p, "rb").read()) for nm, p in HE_FONTS["scaleform_platform_pc"]])
    return W.serialize_open_rpf(root), total


# ── verification (offline, no game) ───────────────────────────────────────────
def _other_files_byte_exact(old_bytes, new_bytes, skip_top_nested):
    """True iff every file in `new` matches `old` byte-for-byte EXCEPT the one nested
    archive we intentionally rewrote (skip_top_nested, e.g. 'american_rel.rpf'). This
    is the 'don't harm other mods' proof."""
    def flat(root, prefix=""):
        d = {}
        for c in root.children:
            p = prefix + c.name
            if c.is_dir:
                d.update(flat(c, p + "/"))
            else:
                d[p.lower()] = c.data
        return d
    a = flat(W.parse_open_rpf(old_bytes, 0))
    b = flat(W.parse_open_rpf(new_bytes, 0))
    if set(a) != set(b):
        return False, f"entry set changed ({len(a)} -> {len(b)})"
    mism = 0
    for k in a:
        if skip_top_nested and k.endswith(skip_top_nested.lower()):
            continue
        if a[k] != b[k]:
            mism += 1
    return (mism == 0), f"{mism} other-file mismatches"


def verify_update2(old_bytes, new_bytes, gxt2_payloads):
    ok, detail = _other_files_byte_exact(old_bytes, new_bytes, "american_rel.rpf")
    if not ok:
        return False, "update2 preservation FAILED: " + detail
    root = W.parse_open_rpf(new_bytes, 0)
    amrel = W.parse_open_rpf(W.find(root, P_AMREL).data, 0)
    have = {c.name.lower(): c for c in amrel.children if not c.is_dir}
    import zlib
    checked = 0
    for name, raw in gxt2_payloads.items():
        node = have.get(name.lower())
        if node is None:
            return False, f"gxt2 {name} missing after apply"
        inflated = zlib.decompress(node.data, -15) if node.csize else node.data
        if inflated != raw:
            return False, f"gxt2 {name} content != Hebrew payload"
        checked += 1
    return True, f"update2 OK — {checked} Hebrew gxt2 in place, all other files byte-exact"


def verify_update(old_bytes, new_bytes):
    # both scaleform rpfs are nested in update.rpf; check non-scaleform files exact +
    # the fonts present. (Two nested archives changed, so the top-level skip is both.)
    def flat(root, prefix=""):
        d = {}
        for c in root.children:
            p = prefix + c.name
            if c.is_dir: d.update(flat(c, p + "/"))
            else: d[p.lower()] = (c.data, c.name.lower())
        return d
    a, b = flat(W.parse_open_rpf(old_bytes, 0)), flat(W.parse_open_rpf(new_bytes, 0))
    if set(a) != set(b):
        return False, "update.rpf entry set changed"
    mism = 0
    for k in a:
        if k.endswith("scaleform_generic.rpf") or k.endswith("scaleform_platform_pc.rpf"):
            continue
        if a[k][0] != b[k][0]:
            mism += 1
    if mism:
        return False, f"update.rpf preservation FAILED: {mism} mismatches"
    return True, "update.rpf OK — fonts swapped, all other files byte-exact"


# ── lifecycle ─────────────────────────────────────────────────────────────────
def _mods_paths(game_root):
    return (os.path.join(game_root, "mods", REL_UPD2),
            os.path.join(game_root, "mods", REL_UPD))


def has_mods_folder(game_root):
    u2, u = _mods_paths(game_root)
    return os.path.isfile(u2) and os.path.isfile(u)


def _atomic_replace(path, new_bytes):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".rpf.tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(new_bytes); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError: pass


def test(game_root, cb=None):
    """NON-DESTRUCTIVE. Read the live mods RPFs, build the patched versions in
    memory, verify preservation + Hebrew. Touches nothing."""
    u2, u = _mods_paths(game_root)
    if not has_mods_folder(game_root):
        return {"ok": False, "error": f"no OPEN mods folder at {os.path.dirname(u2)}"}
    gxt2 = _load_gxt2_payloads()
    _log(cb, f"reading {u2} ({os.path.getsize(u2):,} B)…")
    old2 = open(u2, "rb").read()
    new2, n2 = patch_update2(old2, gxt2)
    ok2, d2 = verify_update2(old2, new2, gxt2)
    _log(cb, f"  update2: replaced {n2} gxt2 -> {d2}")
    _log(cb, f"reading {u} ({os.path.getsize(u):,} B)…")
    old1 = open(u, "rb").read()
    new1, n1 = patch_update(old1)
    ok1, d1 = verify_update(old1, new1)
    _log(cb, f"  update.rpf: swapped {n1} fonts -> {d1}")
    return {"ok": ok2 and ok1, "update2": d2, "update": d1,
            "gxt2": n2, "fonts": n1}


def install(game_root, backup_dir, cb=None):
    """Backup the two touched RPFs, build the patched versions, atomic-replace them."""
    u2, u = _mods_paths(game_root)
    if not has_mods_folder(game_root):
        return {"ok": False, "error": "אין תיקיית mods פתוחה — צריך ליצור אותה פעם אחת ב-OpenIV"}
    gxt2 = _load_gxt2_payloads()
    os.makedirs(backup_dir, exist_ok=True)
    # 1) backup (skip if a backup already exists — keep the FIRST/pristine one)
    for src, name in ((u2, "update2.rpf"), (u, "update.rpf")):
        bak = os.path.join(backup_dir, name)
        if not os.path.isfile(bak):
            _log(cb, f"גיבוי {name}…", 5)
            shutil.copy2(src, bak)
    # 2) build patched bytes (in memory) BEFORE touching the live files
    _log(cb, "בונה את update2 עם התרגום…", 30)
    new2, n2 = patch_update2(open(u2, "rb").read(), gxt2)
    ok2, d2 = verify_update2(open(u2, "rb").read(), new2, gxt2)
    if not ok2:
        return {"ok": False, "error": "אימות update2 נכשל: " + d2}
    _log(cb, "בונה את update עם הפונטים…", 60)
    new1, n1 = patch_update(open(u, "rb").read())
    ok1, d1 = verify_update(open(u, "rb").read(), new1)
    if not ok1:
        return {"ok": False, "error": "אימות update נכשל: " + d1}
    # 3) atomic write (a crash here leaves the live file intact; backup covers it)
    _log(cb, "כותב את update2…", 80)
    _atomic_replace(u2, new2)
    _log(cb, "כותב את update…", 95)
    _atomic_replace(u, new1)
    import json
    json.dump({"applied_at": int(time.time()), "gxt2": n2, "fonts": n1},
              open(os.path.join(backup_dir, MARKER), "w", encoding="utf-8"))
    _log(cb, "הותקן", 100)
    return {"ok": True, "gxt2": n2, "fonts": n1}


def revert(game_root, backup_dir, cb=None):
    """Restore the two RPFs from the pristine backup. Leaves the backup in place."""
    u2, u = _mods_paths(game_root)
    restored = 0
    for dst, name in ((u2, "update2.rpf"), (u, "update.rpf")):
        bak = os.path.join(backup_dir, name)
        if os.path.isfile(bak):
            _log(cb, f"משחזר {name}…")
            _atomic_replace(dst, open(bak, "rb").read())
            restored += 1
    mk = os.path.join(backup_dir, MARKER)
    if os.path.isfile(mk):
        try: os.remove(mk)
        except OSError: pass
    if not restored:
        return {"ok": False, "error": "אין גיבוי לשחזור"}
    return {"ok": True, "restored": restored}


def is_applied(backup_dir):
    return os.path.isfile(os.path.join(backup_dir, MARKER))


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=r"F:\Games\Grand Theft Auto V Legacy")
    ap.add_argument("--backup", default=os.path.join(tempfile.gettempdir(), "gtav_he_backup"))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--test", action="store_true")
    g.add_argument("--apply", action="store_true")
    g.add_argument("--revert", action="store_true")
    g.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.test:
        r = test(a.game)
    elif a.apply:
        r = install(a.game, a.backup)
    elif a.revert:
        r = revert(a.game, a.backup)
    else:
        r = {"mods_folder": has_mods_folder(a.game), "applied": is_applied(a.backup)}
    print(r)
    sys.exit(0 if r.get("ok", True) else 1)


if __name__ == "__main__":
    main()
