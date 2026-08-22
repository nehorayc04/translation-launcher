"""A Plague Tale: Requiem - native Hebrew applier for the launcher.

The Asobo "Zouna" engine reads localization LOOSE from `TRTEXT\\tt23.pc` (the
Arabic text slot; `.IGN` is the divergent sibling variant) and the Hebrew glyphs
from the font pack `FONT\\ENGLISH.DPC` - no repack, no compression. So the mod is a
straight overwrite of 3 files, with the ORIGINALS backed up OUTSIDE the game (in
the launcher cache) so a Program-Files / read-only-parent install still reverts.
Design goals (max-safe, never harm the user's game):

* ONLY these 3 files are ever touched.
* ATOMIC writes (temp on the same volume + os.replace) → no half-written file.
* Reversible: revert restores the EXACT original bytes from the backups.
* Game-update aware: if a live file is neither ours nor the stored backup (a patch
  rewrote it), its backup is refreshed so revert stays exact.

Activation is in-game (Options → Text language = العربية / Arabic; English VO kept).
"""
from __future__ import annotations
import hashlib
import os
import shutil
from pathlib import Path

# (relative-in-game path, backup basename). tt23 = the Arabic slot = our Hebrew;
# ENGLISH.DPC = the font pack carrying the injected Hebrew glyphs.
TARGETS: tuple[tuple[str, str], ...] = (
    (os.path.join("TRTEXT", "tt23.pc"),  "tt23.pc.orig"),
    (os.path.join("TRTEXT", "tt23.IGN"), "tt23.IGN.orig"),
    (os.path.join("FONT", "ENGLISH.DPC"), "ENGLISH.DPC.orig"),
)
# the one file we content-check to decide "installed" (the text slot).
KEY_REL = os.path.join("TRTEXT", "tt23.pc")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of(p) -> str:
    return _sha(Path(p))


def _atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.parent / (dst.name + ".tmp_he")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def is_applied(backup_dir, game_root, key_sha: str | None = None) -> bool:
    """Applied iff the live tt23.pc is OUR build, verified by content against the
    key_sha recorded at install. Without a key_sha we CANNOT confirm our build is
    live, so we conservatively report NOT-installed - critically, after a revert
    the backup is deliberately kept AND the original tt23.pc is restored, so a
    'backup exists + live present' heuristic would falsely report installed. Since
    install always records the sha and revert clears state, a genuine install
    always has a key_sha here; a missing one means removed / never-installed
    (and a re-install is idempotent, so defaulting to False is safe)."""
    bkp = Path(backup_dir) / "tt23.pc.orig"
    live = Path(game_root) / KEY_REL
    if not (bkp.is_file() and live.is_file()):
        return False
    if not key_sha:
        return False
    try:
        return _sha(live) == key_sha
    except Exception:                                   # pragma: no cover
        return True


def apply(game_root, payload_map, backup_dir, progress=None,
          prev_shas: set[str] | None = None) -> dict:
    """Back up each ORIGINAL (once / on game-update) then atomically overwrite it
    with our Hebrew file. `payload_map` = [(src_path, in_game_rel)]; only the rels
    in TARGETS are honored. Returns {ok, error?}. Never partially writes a file.

    prev_shas = shas of PREVIOUSLY-applied Hebrew files (from state). On a mod
    UPDATE a live file is our OLD Hebrew (sha ≠ the new payload AND ≠ the vanilla
    backup); without this it looks like a game-patched original and the vanilla
    backup gets overwritten with old Hebrew (revert could never restore vanilla)."""
    prev = prev_shas or set()
    def _p(ph, pct, msg=""):
        if progress:
            try:
                progress(ph, pct, msg)
            except Exception:
                pass

    root = Path(game_root)
    if not (root / "TRTEXT").is_dir():
        return {"ok": False,
                "error": "לא נמצאה תיקיית TRTEXT בנתיב המשחק - בדוק את הנתיב"}
    bdir = Path(backup_dir)
    bak_of = {rel: name for rel, name in TARGETS}
    try:
        n = len(payload_map)
        for i, (src, rel) in enumerate(payload_map):
            src = Path(src)
            if rel not in bak_of or not src.is_file():
                continue
            live = root / rel
            if not live.is_file():
                # a target the game doesn't have (e.g. no .IGN) - skip quietly
                continue
            bkp = bdir / bak_of[rel]
            heb_sha = _sha(src)
            live_sha = _sha(live)
            _p("backup", 10 + int(60 * i / max(1, n)), "מגבה את הקבצים המקוריים…")
            need_backup = not bkp.is_file()
            if not need_backup:
                try:
                    bak_sha = _sha(bkp)
                    # game patched it → refresh; but NOT if live is a previously-
                    # applied Hebrew build (a mod update) - that must never
                    # overwrite the vanilla backup.
                    if (live_sha != heb_sha and live_sha != bak_sha
                            and live_sha not in prev):
                        need_backup = True
                except Exception:                       # pragma: no cover
                    need_backup = False
            if need_backup and live_sha != heb_sha and live_sha not in prev:
                _atomic_copy(live, bkp)
            if live_sha != heb_sha:
                _atomic_copy(src, live)
        _p("done", 100, "")
        return {"ok": True}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                         "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב."}
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": f"שגיאה: {e}"}


def revert(game_root, backup_dir) -> dict:
    """Restore each backed-up original (atomic). Keeps the backups so a later
    re-install is still safe. Returns {ok, error?}."""
    root = Path(game_root)
    bdir = Path(backup_dir)
    restored = 0
    try:
        for rel, name in TARGETS:
            bkp = bdir / name
            live = root / rel
            if bkp.is_file() and live.parent.is_dir():
                _atomic_copy(bkp, live)
                restored += 1
        if restored == 0:
            return {"ok": False, "error": "לא נמצא גיבוי לשחזור"}
        return {"ok": True}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל ונסה שוב."}
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": f"שגיאה: {e}"}
