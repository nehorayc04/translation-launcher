"""Hogwarts Legacy - native Hebrew applier for the launcher.

The mod is a NON-DESTRUCTIVE additive override pak: Unreal Engine 4 mounts any
`*_P.pak` dropped in `Phoenix\\Content\\Paks\\~mods\\` at a HIGHER priority than the
base `pakchunk0` for every path it contains - so the base game files are NEVER
touched (Steam/Epic/GOG "Verify Integrity" never reverts vanilla). Design goals
(max-safe, never harm the user's game):

* ONLY our single override pak is ever written / deleted - the rest of the game
  (incl. pakchunk0) is never modified.
* ATOMIC writes (temp on the same volume + os.replace) → an interrupted apply can
  never leave a half-written pak; it appears in one step or not at all.
* Reversible: revert just deletes our pak - vanilla is already intact underneath.
* Portable: pure `os`/`shutil` file ops → every Windows version; the only signal
  is the `~mods` dir at its fixed relative path → every store/version.

Activation is in-game (Settings → Text Language → English — the Hebrew rides the
English text slot; the Arabic slot is deliberately left untouched, so it must be
selected explicitly). We never touch a game setting here.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path

# The ~mods override dir + the fixed name we deploy under. `zzz_` sorts LAST (loads
# after pakchunk0…N) and the `_P` suffix marks it a patch → highest override
# priority; a fixed name means revert/is_applied need no external state.
MODS_REL = os.path.join("Phoenix", "Content", "Paks", "~mods")
DEPLOYED_NAME = "zzz_hebrew-WindowsNoEditor_P.pak"


def mods_dir(game_root) -> Path:
    return Path(game_root) / MODS_REL


def pak_path(game_root) -> Path:
    return mods_dir(game_root) / DEPLOYED_NAME


def _atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.parent / (dst.name + ".tmp_he")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def is_applied(game_root) -> bool:
    """Applied iff our override pak is present in ~mods."""
    try:
        return pak_path(game_root).is_file()
    except Exception:                                   # pragma: no cover
        return False


def apply(game_root, hebrew_pak, backup_dir=None, progress=None) -> dict:
    """Drop the Hebrew override pak into ~mods (atomic). `backup_dir` is accepted
    for signature-parity but unused (additive override → nothing to back up).
    Returns {ok, error?}."""
    def _p(ph, pct, msg=""):
        if progress:
            try:
                progress(ph, pct, msg)
            except Exception:
                pass

    root = Path(game_root)
    if not (root / "Phoenix" / "Content" / "Paks").is_dir():
        return {"ok": False,
                "error": "לא נמצאה תיקיית Phoenix\\Content\\Paks בנתיב המשחק - בדוק את הנתיב"}
    hebrew_pak = Path(hebrew_pak)
    if not hebrew_pak.is_file():
        return {"ok": False, "error": "קובץ המוד לא נמצא"}
    try:
        _p("apply", 60, "מתקין את התרגום…")
        _atomic_copy(hebrew_pak, pak_path(root))
        _p("done", 100, "")
        return {"ok": True}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                         "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב."}
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": f"שגיאה: {e}"}


def revert(game_root, backup_dir=None) -> dict:
    """Remove our override pak (vanilla is untouched underneath). Idempotent."""
    p = pak_path(game_root)
    try:
        if p.is_file():
            p.unlink()
        # also drop a stale temp if an apply was interrupted
        tmp = p.parent / (p.name + ".tmp_he")
        if tmp.is_file():
            tmp.unlink()
        return {"ok": True}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל ונסה שוב."}
    except Exception as e:                              # pragma: no cover
        return {"ok": False, "error": f"שגיאה: {e}"}
