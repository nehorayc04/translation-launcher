r"""gtav_mod.py - launcher-side applier for the GTA V Hebrew mod, WITHOUT OpenIV.

Wraps the proven rpf7_writer (vendored as `gtav_rpf7`) to read-modify-write the
user's EXISTING OPEN `mods\` folder, preserving every other file/mod byte-exact:

  mods\update\update2.rpf → x64\data\lang\american_rel.rpf → 610 gxt2 (Hebrew)
  mods\update\update.rpf  → x64\data\cdimages\scaleform_generic.rpf      (2 Hebrew fonts)
                          → x64\data\cdimages\scaleform_platform_pc.rpf  (1 Hebrew font)

Payloads ride in `assets/gtav/gtav_he_payload.zip` (bundled). Backups live OUTSIDE
the game in `~/.translation_manager/mod_backups/gtav/`; apply builds the new RPF in a
temp file and `os.replace`-s it in atomically, so a crash never corrupts the live
archive, and revert() restores the pristine backup. Only OPEN archives are touched -
the encrypted vanilla is never read (a clean install with no `mods\` folder is GUIDED
through a one-time OpenIV setup; this module only runs once that folder exists).

Mirrors the SM2/WD2 native-applier shape (is_applied / apply / revert + a payload
resolver), so main_eel wires it the same way.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import zipfile
import zlib
from pathlib import Path
from typing import Callable, Optional

from . import gtav_rpf7 as W   # vendored OPEN-RPF7 read-modify-write (resource-flag safe)

ProgressCB = Callable[[str, float, str], None]

# RPF paths (must match games/gtav/work/build_full_gxt2.build_oiv exactly).
P_AMREL = "x64/data/lang/american_rel.rpf"
P_GEN   = "x64/data/cdimages/scaleform_generic.rpf"
P_PC    = "x64/data/cdimages/scaleform_platform_pc.rpf"
REL_U2  = os.path.join("update", "update2.rpf")
REL_U   = os.path.join("update", "update.rpf")
MARKER  = "gtav_he_applied.json"

# Which Hebrew fonts go into which nested scaleform rpf.
_FONT_TARGETS = {
    P_GEN: ["font_lib_efigs.gfx", "font_lib_web.gfx"],
    P_PC:  ["font_lib_efigs_pc.gfx"],
}

_ROOT = Path(__file__).resolve().parent          # …/translation_manager


# ── bundled payloads ──────────────────────────────────────────────────────────
# Two payloads ship: the HEBREW build (install) and the VANILLA English originals
# (surgical remove - swap the same files back to English IN PLACE, so removal never
# relies on the install-time full backup, which may be stale if the user changed
# other mods after installing).
_HE_ZIP  = "gtav_he_payload.zip"
_VAN_ZIP = "gtav_vanilla_payload.zip"

# Server-downloaded payload dir (set by main_eel after a successful fetch). It WINS
# over the bundled copy, so a new mod version reaches users without a launcher
# rebuild - the bundled zips stay purely as the offline / server-down fallback.
_PAYLOAD_DIR: Optional[Path] = None


def set_payload_dir(path) -> None:
    """Point the payload resolver at a downloaded dir (or None to use the bundle)."""
    global _PAYLOAD_DIR
    try:
        p = Path(path) if path else None
    except Exception:                                   # pragma: no cover
        p = None
    _PAYLOAD_DIR = p if (p and p.is_dir()) else None


def _asset(name: str) -> Optional[Path]:
    """Resolve <name>: the downloaded payload dir first, then assets/gtav/ in the
    frozen build (sys._MEIPASS), then a dev run."""
    cands = []
    if _PAYLOAD_DIR is not None:
        cands.append(_PAYLOAD_DIR / name)
    base = getattr(sys, "_MEIPASS", None)
    if base:
        cands.append(Path(base) / "translation_manager" / "assets" / "gtav" / name)
    cands.append(_ROOT / "assets" / "gtav" / name)
    for p in cands:
        if p.is_file():
            return p
    return None


def payload_available() -> bool:
    return _asset(_HE_ZIP) is not None


def vanilla_available() -> bool:
    return _asset(_VAN_ZIP) is not None


def _load_payloads(zip_name: str):
    """(gxt2 {name->bytes}, fonts {name->bytes}) from the named bundled zip."""
    zp = _asset(zip_name)
    if zp is None:
        raise FileNotFoundError(f"GTA payload not bundled: {zip_name}")
    gxt2, fonts = {}, {}
    with zipfile.ZipFile(zp) as z:
        for info in z.infolist():
            if info.filename.startswith("american_rel/") and info.filename.endswith(".gxt2"):
                gxt2[os.path.basename(info.filename)] = z.read(info)
            elif info.filename.startswith("fonts/") and info.filename.endswith(".gfx"):
                fonts[os.path.basename(info.filename)] = z.read(info)
    if not gxt2:
        raise FileNotFoundError(f"payload zip has no gxt2: {zip_name}")
    return gxt2, fonts


# ── RPF read-modify-write (the proven engine, payload-driven) ─────────────────
def _replace_preserving_mode(root, path, new_bytes) -> bool:
    f = W.find(root, path)
    if f is None or f.is_dir:
        return False
    W.replace_file_data(root, path, new_bytes, compress=(f.csize != 0))
    return True


def _edit_nested(parent_root, nested_path, edits):
    node = W.find(parent_root, nested_path)
    if node is None or node.is_dir:
        raise KeyError(f"nested rpf not found: {nested_path}")
    raw = zlib.decompress(node.data, -15) if node.csize else node.data
    inner = W.parse_open_rpf(raw, 0)
    n = 0
    for inner_path, data in edits:
        if _replace_preserving_mode(inner, inner_path, data):
            n += 1
    W.replace_file_data(parent_root, nested_path, W.serialize_open_rpf(inner), compress=False)
    return n


def _patch_update2(update2_bytes, gxt2):
    root = W.parse_open_rpf(update2_bytes, 0)
    n = _edit_nested(root, P_AMREL, list(gxt2.items()))
    # IN-PLACE: keep the original 463 MB layout, append only the rebuilt american_rel.rpf.
    # A full re-pack reorders every file (engine ERR_GEN_ZLIB_2). See serialize_inplace.
    return W.serialize_inplace(update2_bytes, root), n


def _patch_update(update_bytes, fonts):
    root = W.parse_open_rpf(update_bytes, 0)
    total = 0
    for nested, names in _FONT_TARGETS.items():
        edits = [(nm, fonts[nm]) for nm in names if nm in fonts]
        total += _edit_nested(root, nested, edits)
    # IN-PLACE: preserve the original 2.6 GB update.rpf layout + padding, append only the
    # rebuilt scaleform rpfs we touched.
    return W.serialize_inplace(update_bytes, root), total


def _flat(root, prefix=""):
    d = {}
    for c in root.children:
        p = prefix + c.name
        if c.is_dir:
            d.update(_flat(c, p + "/"))
        else:
            d[p.lower()] = c.data
    return d


def _others_byte_exact(old_bytes, new_bytes, skip_suffixes):
    a = _flat(W.parse_open_rpf(old_bytes, 0))
    b = _flat(W.parse_open_rpf(new_bytes, 0))
    if set(a) != set(b):
        return False
    for k in a:
        if any(k.endswith(s) for s in skip_suffixes):
            continue
        if a[k] != b[k]:
            return False
    return True


# ── lifecycle ─────────────────────────────────────────────────────────────────
def _mods(game_root: Path):
    g = Path(game_root)
    return g / "mods" / REL_U2, g / "mods" / REL_U


def has_mods_folder(game_root) -> bool:
    u2, u = _mods(game_root)
    return u2.is_file() and u.is_file()


def loader_connected(game_root) -> bool:
    """The OpenIV ASI loader (dinput8.dll proxy) present in the game root - the game
    reads `mods\\` only when this is active."""
    return (Path(game_root) / "dinput8.dll").is_file()


def is_applied(backup_dir) -> bool:
    return (Path(backup_dir) / MARKER).is_file()


def _log(cb, msg, pct=None):
    if cb:
        try: cb("apply", pct if pct is not None else 0.0, msg)
        except Exception: pass


def _atomic_replace(path: Path, data: bytes):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".rpf.tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError: pass


def apply(game_root, backup_dir, cb: ProgressCB | None = None) -> dict:
    """Backup the 2 RPFs, build the Hebrew versions (verified, other files byte-exact),
    atomic-write them in. Idempotent (re-apply just re-writes the same Hebrew)."""
    u2, u = _mods(game_root)
    if not has_mods_folder(game_root):
        return {"ok": False, "error": "אין תיקיית mods פתוחה - צריך ליצור אותה פעם אחת ב-OpenIV"}
    try:
        gxt2, fonts = _load_payloads(_HE_ZIP)
    except Exception as e:
        return {"ok": False, "error": f"חבילת התרגום חסרה: {e}"}
    bdir = Path(backup_dir); bdir.mkdir(parents=True, exist_ok=True)
    try:
        # 1) backup the FIRST/pristine state only (don't overwrite a prior backup)
        import shutil
        for src, name in ((u2, "update2.rpf"), (u, "update.rpf")):
            bak = bdir / name
            if not bak.is_file():
                _log(cb, f"גיבוי {name}…", 5)
                shutil.copy2(str(src), str(bak))
        # 2) build + verify in memory BEFORE touching the live files
        _log(cb, "בונה את update2 עם התרגום…", 25)
        old2 = u2.read_bytes()
        new2, n2 = _patch_update2(old2, gxt2)
        if not _others_byte_exact(old2, new2, ["american_rel.rpf"]):
            return {"ok": False, "error": "אימות update2 נכשל (קבצים אחרים השתנו)"}
        del old2
        _log(cb, "בונה את update עם הפונטים…", 55)
        old1 = u.read_bytes()
        new1, n1 = _patch_update(old1, fonts)
        if not _others_byte_exact(old1, new1, ["scaleform_generic.rpf", "scaleform_platform_pc.rpf"]):
            return {"ok": False, "error": "אימות update נכשל (קבצים אחרים השתנו)"}
        del old1
        # 3) atomic write (a crash here leaves the live file intact; backup covers it)
        _log(cb, "כותב את update2…", 80)
        _atomic_replace(u2, new2); del new2
        _log(cb, "כותב את update…", 95)
        _atomic_replace(u, new1); del new1
        (bdir / MARKER).write_text(
            json.dumps({"applied_at": int(time.time()), "gxt2": n2, "fonts": n1}),
            encoding="utf-8")
        _log(cb, "ההתקנה הושלמה", 100)
        return {"ok": True, "gxt2": n2, "fonts": n1}
    except MemoryError:
        return {"ok": False, "error": "אין מספיק זיכרון פנוי - סגור תוכנות כבדות ונסה שוב"}
    except OSError as e:                                # WinError 2/3, file missing/locked/no access
        return {"ok": False,
                "error": ("קובץ שנדרש להתקנה לא נמצא או שאין גישה אליו - ודא שקובצי ה-mods "
                          "וקובצי המשחק במקומם, שהמשחק סגור, ושהתוכנה רצה עם הרשאות מתאימות, "
                          f"ונסה שוב. (פרטים: {e})")}
    except Exception as e:
        return {"ok": False, "error": f"שגיאה בהתקנה: {e}"}


def revert(game_root, backup_dir, cb: ProgressCB | None = None) -> dict:
    """SURGICAL remove: swap the 610 gxt2 + 3 fonts back to the VANILLA English /
    original fonts INSIDE the CURRENT mods RPF - read-modify-write, so every OTHER
    file is preserved byte-exact, INCLUDING any mod the user added AFTER installing.
    Does NOT use the install-time backup (which can be stale)."""
    u2, u = _mods(game_root)
    if not has_mods_folder(game_root):
        return {"ok": False, "error": "אין תיקיית mods פתוחה"}
    try:
        gxt2, fonts = _load_payloads(_VAN_ZIP)
    except Exception as e:
        return {"ok": False, "error": f"קבצי המקור (אנגלית) חסרים: {e}"}
    try:
        _log(cb, "מחזיר את הטקסט לאנגלית המקורית…", 25)
        old2 = u2.read_bytes()
        new2, n2 = _patch_update2(old2, gxt2)
        if not _others_byte_exact(old2, new2, ["american_rel.rpf"]):
            return {"ok": False, "error": "אימות update2 נכשל (קבצים אחרים השתנו)"}
        del old2
        _log(cb, "מחזיר את הפונטים המקוריים…", 55)
        old1 = u.read_bytes()
        new1, n1 = _patch_update(old1, fonts)
        if not _others_byte_exact(old1, new1, ["scaleform_generic.rpf", "scaleform_platform_pc.rpf"]):
            return {"ok": False, "error": "אימות update נכשל (קבצים אחרים השתנו)"}
        del old1
        _log(cb, "כותב את update2…", 80)
        _atomic_replace(u2, new2); del new2
        _log(cb, "כותב את update…", 95)
        _atomic_replace(u, new1); del new1
        mk = Path(backup_dir) / MARKER
        if mk.is_file():
            try: mk.unlink()
            except OSError: pass
        _log(cb, "התרגום הוסר - הטקסט חזר לאנגלית, המודים האחרים שלך נשמרו", 100)
        return {"ok": True, "gxt2": n2, "fonts": n1}
    except MemoryError:
        return {"ok": False, "error": "אין מספיק זיכרון פנוי - סגור תוכנות כבדות ונסה שוב"}
    except Exception as e:
        return {"ok": False, "error": f"שגיאה בהסרה: {e}"}


def has_backup(backup_dir) -> bool:
    bdir = Path(backup_dir)
    return (bdir / "update2.rpf").is_file() and (bdir / "update.rpf").is_file()


def restore_backup(game_root, backup_dir, cb: ProgressCB | None = None) -> dict:
    """EMERGENCY full restore: overwrite the 2 RPFs with the install-time backup =
    the EXACT pre-install state. ⚠ Discards ANY change made to those RPFs since the
    install (newer mods included). The surgical remove() is the normal path; this is
    the separate 'restore the snapshot from before I installed' button."""
    u2, u = _mods(game_root)
    bdir = Path(backup_dir)
    if not has_backup(backup_dir):
        return {"ok": False, "error": "אין גיבוי מלא לשחזור"}
    restored = 0
    try:
        for dst, name in ((u2, "update2.rpf"), (u, "update.rpf")):
            bak = bdir / name
            if bak.is_file():
                _log(cb, f"משחזר {name} מהגיבוי המלא…")
                _atomic_replace(dst, bak.read_bytes())
                restored += 1
    except Exception as e:
        return {"ok": False, "error": f"שגיאה בשחזור: {e}"}
    mk = bdir / MARKER
    if mk.is_file():
        try: mk.unlink()
        except OSError: pass
    return {"ok": True, "restored": restored}
