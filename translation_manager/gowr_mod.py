"""God of War: Ragnarök - native Hebrew localization applier for the launcher.

The mod is a SINGLE file swap: the game reads its Arabic-slot text from
`exec/wad/pc_le/r_lang_ar.wad`; we replace it with our bundled Hebrew build and
keep the ORIGINAL backed up in the launcher cache (OUTSIDE the game folder) so a
Program-Files / read-only-parent install still reverts. Design goals (max-safe,
never harm the user's game):

* ONLY that one file is ever touched - the rest of the game is never modified.
* ATOMIC writes (temp on the same volume + os.replace) → an interrupted apply or
  revert can never leave a half-written / corrupt WAD; the live file flips in one
  step or not at all.
* Reversible: revert restores the EXACT original bytes from the backup.
* Game-update aware: if the live WAD is neither our Hebrew nor the stored backup
  (a game patch rewrote it), the backup is refreshed so revert stays exact.
* Portable: pure `os`/`shutil` file ops → every Windows version; the only signal
  is the WAD at its fixed relative path → every store/version (Steam/Epic/FitGirl).

Activation is in-game (Settings → Text Language = العربية); we never touch a game
setting here.
"""
from __future__ import annotations
import hashlib
import os
import shutil
from pathlib import Path

WAD_REL = os.path.join("exec", "wad", "pc_le", "r_lang_ar.wad")
BACKUP_NAME = "r_lang_ar.wad.orig"


def wad_path(game_root) -> Path:
    return Path(game_root) / WAD_REL


# Memo for the language-WAD digest, keyed by identity (path, size, mtime).
# is_applied() hashes a MULTI-GIGABYTE .wad, and it is called on every state
# read - opening the panel, the catalog poller, and every update check. Re-
# hashing it each time is what made get_mod_updates blow past its off-thread
# guard (real reports: "get_mod_updates did not return within 120/180s"). The
# key changes the moment the file does, so a stale answer is impossible.
_SHA_MEMO: dict[tuple[str, int, int], tuple[str, int]] = {}


def _sha_size(p: Path) -> tuple[str, int]:
    key = None
    try:
        st = p.stat()
        key = (str(p), st.st_size, st.st_mtime_ns)
        hit = _SHA_MEMO.get(key)
        if hit is not None:
            return hit
    except OSError:
        key = None
    h = hashlib.sha256()
    n = 0
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    out = (h.hexdigest(), n)
    if key is not None:
        if len(_SHA_MEMO) > 32:                 # bounded; identity-keyed anyway
            _SHA_MEMO.clear()
        _SHA_MEMO[key] = out
    return out


def sha256_of(p) -> str:
    return _sha_size(Path(p))[0]


def _atomic_copy(src: Path, dst: Path) -> None:
    """Copy src → dst atomically: write a sibling temp on dst's volume, fsync-ish
    via copy2, then os.replace (atomic same-volume rename)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.parent / (dst.name + ".tmp_he")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def is_applied(backup_dir, game_root, hebrew_sha: str | None = None) -> bool:
    """Applied iff a backup exists AND the live WAD is our Hebrew build.

    With a known hebrew_sha we verify by CONTENT (robust). Without one we fall
    back to comparing the live WAD against the backup: different = our build is
    in place, identical = reverted. The old fallback was a bare "backup exists +
    live present", which is TRUE forever once a backup has ever been taken - and
    since `revert` deliberately keeps the backup, removal looked like it silently
    failed (the panel stayed "תרגום מותקן" and clear-cache refused with "the
    removal is still running"). That only surfaced when the bundled payload was
    dropped: `_gowr_bundled_sha()` used to supply the sha even after state was
    cleared, so the content check always ran.
    """
    bkp = Path(backup_dir) / BACKUP_NAME
    wad = wad_path(game_root)
    if not (bkp.is_file() and wad.is_file()):
        return False
    try:
        if hebrew_sha:
            return _sha_size(wad)[0] == hebrew_sha
        # No known Hebrew sha: live == backup means the original is restored.
        return _sha_size(wad)[0] != _sha_size(bkp)[0]
    except Exception:                                       # pragma: no cover
        return True


def apply(game_root, hebrew_wad, backup_dir, progress=None,
          prev_hebrew_sha: str | None = None) -> dict:
    """Back up the ORIGINAL WAD (once / on game-update) then atomically swap in the
    Hebrew WAD. Returns {ok, error?}. Never partially writes the live file.

    prev_hebrew_sha = the sha of a PREVIOUSLY-applied Hebrew build (from state).
    On a mod UPDATE the live WAD is our OLD Hebrew, whose sha differs from BOTH
    the new bundled sha AND the vanilla backup - without this it looks like a
    fresh game-patched original and the vanilla backup gets overwritten with old
    Hebrew (revert could then never restore vanilla)."""
    def _p(ph, pct, msg=""):
        if progress:
            try:
                progress(ph, pct, msg)
            except Exception:
                pass

    wad = wad_path(game_root)
    if not wad.is_file():
        return {"ok": False,
                "error": "לא נמצא קובץ השפה של המשחק (exec\\wad\\pc_le\\r_lang_ar.wad) - בדוק את הנתיב"}
    hebrew_wad = Path(hebrew_wad)
    if not hebrew_wad.is_file():
        return {"ok": False, "error": "קובץ המוד לא נמצא"}

    bdir = Path(backup_dir)
    bkp = bdir / BACKUP_NAME
    try:
        heb_sha = _sha_size(hebrew_wad)[0]
        live_sha = _sha_size(wad)[0]
        if live_sha == heb_sha and bkp.is_file():
            # already our Hebrew and we hold a backup → nothing to do (idempotent)
            _p("done", 100, "")
            return {"ok": True, "already": True}

        _p("backup", 15, "מגבה את הקובץ המקורי…")
        need_backup = not bkp.is_file()
        if not need_backup:
            try:
                bak_sha = _sha_size(bkp)[0]
                # live is a FRESH original (game patched it): neither our Hebrew nor
                # the stored backup → refresh the backup so revert stays exact. But
                # NOT if live is a PREVIOUSLY-applied Hebrew build (a mod update) -
                # that must never overwrite the vanilla backup.
                if (live_sha != heb_sha and live_sha != bak_sha
                        and live_sha != prev_hebrew_sha):
                    need_backup = True
            except Exception:                               # pragma: no cover
                need_backup = False
        # never back up OUR OWN Hebrew (current or previous) as the "original"
        if need_backup and live_sha != heb_sha and live_sha != prev_hebrew_sha:
            _atomic_copy(wad, bkp)

        _p("apply", 60, "מתקין את התרגום…")
        _atomic_copy(hebrew_wad, wad)
        _p("done", 100, "")
        return {"ok": True}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                         "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב."}
    except Exception as e:                                  # pragma: no cover
        return {"ok": False, "error": f"שגיאה: {e}"}


def revert(game_root, backup_dir) -> dict:
    """Restore the original WAD from the backup (atomic), then DROP the backup.

    The live file now IS the original, so the copy adds nothing - and keeping it
    is what made "backup exists" a sticky installed-marker. Dropping it also
    keeps the marker honest across a later game update (live=new vanilla vs a
    stale backup=old vanilla would otherwise read as "applied"). A re-install
    takes a fresh backup from the restored file. Returns {ok, error?}.
    """
    wad = wad_path(game_root)
    bkp = Path(backup_dir) / BACKUP_NAME
    if not bkp.is_file():
        return {"ok": False, "error": "לא נמצא גיבוי לשחזור"}
    try:
        _atomic_copy(bkp, wad)
        try:
            bkp.unlink()
        except OSError:                                     # pragma: no cover
            pass        # restored either way; is_applied's content check covers it
        return {"ok": True}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל ונסה שוב."}
    except Exception as e:                                  # pragma: no cover
        return {"ok": False, "error": f"שגיאה: {e}"}
