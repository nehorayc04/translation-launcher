"""The Witcher 3: Wild Hunt - native Hebrew applier for the launcher.

The published mod is NOT a simple Mods-folder overlay - it is a DIRECT base-game
patch driven by the mod's own self-contained ``install.py`` (+ a ``lib/`` of pure
REDengine codecs). Its five mechanisms:

  1. TEXT       - writes 34 Hebrew ``ar.w3strings`` (base game + every DLC).
  2. FONTS      - injects Hebrew glyphs into the font bundles (``r4gui.bundle``).
  3. CINEMATICS - patches the cinematic subtitles + the in-video recap (``movies.bundle``).
  4. LANGUAGE   - renames the selector "Arabic" -> "Hebrew" across every language file.
  5. DLC ART    - swaps the expansion banner art so the Arabic slot resolves to English.

Every file it touches is backed up as ``<file>.he_backup`` and it reverts itself
exactly. Rather than re-implement (and risk drifting from) that logic, the launcher
**runs the mod's OWN install.py in-process**: the file is pure stdlib plus its bundled
``lib/`` (imports = struct / re only), so we load it via importlib and call
``install()`` / ``revert()``. This guarantees the launcher deploys EXACTLY what the mod
author shipped, and inherits the author's own revert. Activation is in-game
(Options -> Text = Hebrew; the selector literally says "Hebrew" after install).
"""
from __future__ import annotations

import glob
import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path

BAK = ".he_backup"
# lib modules the mod's install.py imports - popped before each load so a stale
# copy (or a same-named module from another game's mod) never shadows the W3 one.
_LIB_MODULES = ("potato_bundle", "w3strings", "w3strings_patch", "subs_codec")

# What install.py's five phases are doing, in words a player understands. Keyed by
# the "N/5" it logs. Phase 3 is the long one - it rewrites the 2.5 GB movie bundle.
_PHASE_LABEL = {
    0: "מתקין את התרגום…",
    1: "כותב את קובצי הטקסט…",
    2: "מזריק פונטים עבריים…",
    3: "מטמיע כתוביות בסרטונים… (השלב הארוך, כמה דקות)",
    4: "מעדכן את בורר השפה…",
    5: "מסיים…",
}


def _mod_root(mod_src_dir) -> "Path | None":
    """The extracted mod dir holding install.py + lib/ + data/. Accepts that dir
    directly, or any parent that contains such a layout."""
    if not mod_src_dir:
        return None
    src = Path(mod_src_dir)
    if (src / "install.py").is_file() and (src / "lib").is_dir():
        return src
    hit = next(
        (p.parent for p in src.rglob("install.py")
         if (p.parent / "lib").is_dir() and (p.parent / "data").is_dir()),
        None,
    )
    return hit


def _load_lib(root: Path, name: str):
    """Load one of the mod's ``lib/*.py`` helpers under its OWN module name."""
    spec = importlib.util.spec_from_file_location(name, str(root / "lib" / f"{name}.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the mod helper {name}")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m               # registered BEFORE exec: w3strings_patch
    spec.loader.exec_module(m)          # imports w3strings and must find it here
    return m


def _load_installer(root: Path):
    """Load the mod's own install.py in-process, pinned to THIS extracted copy.

    ⚠️ install.py is written to run as a plain script OR as its own frozen exe:

        def _base():
            if getattr(sys, "frozen", False): return sys._MEIPASS
            return os.path.dirname(os.path.abspath(__file__))
        HERE = _base(); sys.path.insert(0, HERE + "/lib"); import potato_bundle
        DATA = HERE + "/data"

    Inside OUR frozen launcher `sys.frozen` is True and `sys._MEIPASS` is the
    LAUNCHER's bundle - so `HERE` pointed at the launcher instead of the mod, and
    the install died with "No module named 'potato_bundle'" (and `DATA`, which
    every one of its five phases reads, would have been wrong too). It only ever
    failed in the SHIPPED build; a dev run resolves `__file__` and works.

    So we do not rely on install.py's own path guess:
      1. pre-seed its lib modules from THIS root, so the imports resolve
         regardless of what `HERE` computes (dependency order matters -
         w3strings_patch imports w3strings);
      2. after exec, pin `HERE`/`DATA` to the extracted mod root. They are plain
         module globals read at CALL time, so patching them post-import is what
         actually decides where the payload is read from.
    We deliberately do NOT touch sys.frozen/sys._MEIPASS: they are process-global
    and other threads resolve bundled assets through them.
    """
    for m in _LIB_MODULES:
        sys.modules.pop(m, None)
    for name in ("potato_bundle", "w3strings", "subs_codec", "w3strings_patch"):
        if (root / "lib" / f"{name}.py").is_file():
            _load_lib(root, name)

    spec = importlib.util.spec_from_file_location("_w3_installer", str(root / "install.py"))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the mod installer")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.HERE = str(root)
    mod.DATA = str(root / "data")
    return mod


def is_applied(game_root) -> bool:
    """Applied iff the mod's text backup exists (install.py backs up every base file
    it overwrites as ``<file>.he_backup``; the base-game text is the first thing it
    writes, so its backup is the reliable 'installed' marker)."""
    try:
        return (Path(game_root) / "content" / "content0" / ("ar.w3strings" + BAK)).exists()
    except Exception:                                   # pragma: no cover
        return False


def _looks_like_game(root: Path) -> bool:
    return (root / "content").is_dir() or (root / "bin").is_dir()


def apply(game_root, mod_src_dir, backup_dir=None, progress=None) -> dict:
    """Run the mod's install.py against the game (all 5 parts + backups). ``backup_dir``
    is accepted for signature-parity but unused (the installer backs up in place)."""
    def _p(ph, pct, msg=""):
        if progress:
            try:
                progress(ph, pct, msg)
            except Exception:
                pass

    root = Path(game_root)
    if not _looks_like_game(root):
        return {"ok": False,
                "error": "הנתיב אינו נראה כמו תיקיית Witcher 3 (חסרה content/bin) - בדוק את הנתיב"}
    mroot = _mod_root(mod_src_dir)
    if mroot is None:
        return {"ok": False, "error": "קובצי המוד (install.py) לא נמצאו בארכיון"}
    try:
        _p("apply", 25, "מתקין את התרגום…")
        installer = _load_installer(mroot)
        # install() is ONE blocking call that can run for MINUTES (it rewrites the
        # 2.5 GB movies.bundle and touches the 8.4 GB texture.cache). Reporting a
        # single 55% and then nothing made the bar creep to its ~96% cap and sit
        # there - indistinguishable from a hang, and a user who kills it there
        # leaves the game mid-write. install.py already narrates itself through a
        # `log` callback ("1/5 …" … "5/5 …"), so bridge that to real progress.
        phase_re = re.compile(r"\s*([1-5])\s*/\s*5")
        seen = {"n": 0}

        def _log(line) -> None:
            text = str(line).strip()
            if not text:
                return
            m = phase_re.match(text)
            if m:
                seen["n"] = int(m.group(1))
            # 55 → 95 across the five phases, so the bar keeps MOVING and the
            # label says which part is running.
            pct = 55 + (seen["n"] / 5.0) * 40.0
            _p("apply", pct, _PHASE_LABEL.get(seen["n"], "מתקין…"))

        installer.install(str(root), _log)   # 5 parts + backups + state (in the game)
        _p("done", 100, "")
        return {"ok": True}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה לתיקיית המשחק. הפעל את התוכנה כמנהל, "
                         "או העבר את המשחק מחוץ ל-Program Files, ונסה שוב."}
    except OSError as e:                                # WinError 2/3, file missing/locked
        return {"ok": False,
                "error": ("קובץ שנדרש להתקנה לא נמצא או שאין גישה אליו - ייתכן שהמשחק "
                          "מותקן חלקית, שחסרים קבצים, או שקובץ ננעל על-ידי תוכנה אחרת. "
                          "אמת את קבצי המשחק (Steam/GOG: אימות שלמות הקבצים), ודא שהמשחק "
                          f"סגור, ונסה שוב. (פרטים: {e})")}
    except BaseException as e:                          # pragma: no cover
        # CRITICAL: catch BaseException, NOT Exception. `installer.install()`
        # above is the DOWNLOADED mod's own install.py, which - like
        # SignalRGB's patch_exe.py - can `raise SystemExit(...)` on an
        # unrecognised game/file layout. SystemExit is a BaseException; a bare
        # `except Exception` lets it escape apply() uncaught, which skips this
        # error message entirely and can crash the whole launcher further up
        # the call chain (see the note on _BackgroundRunnable in bridge.py).
        return {"ok": False, "error": f"שגיאה בהתקנה: {e}"}


def _glob_restore(root: Path) -> int:
    """Cache-independent revert: restore every ``.he_backup`` the installer left (text,
    language files, font/movie bundles, epilepsy video). Mirrors install.py's revert
    glob so a cleared mod cache never blocks removal. (The DLC-banner byte-swap needs
    the installer's installed.json and is handled by the installer path below.)"""
    r = str(root)
    pats = [
        os.path.join(r, "content", "content*", "*" + BAK),
        os.path.join(r, "dlc", "*", "content", "*" + BAK),
        os.path.join(r, "content", "content0", "bundles", "*" + BAK),
        os.path.join(r, "content", "content0", "movies", "cutscenes", "gamestart", "epilepsy", "*" + BAK),
    ]
    n = 0
    for pat in pats:
        for f in glob.glob(pat):
            orig = f[:-len(BAK)]
            shutil.copy2(f, orig)
            os.remove(f)
            n += 1
    return n


def revert(game_root, mod_src_dir=None, backup_dir=None) -> dict:
    """Undo the mod. Prefers the mod's own revert (restores backups AND reverts the
    DLC-banner byte-swap via installed.json) when the mod cache is still present;
    otherwise falls back to a pure ``.he_backup`` restore so removal always works."""
    root = Path(game_root)
    try:
        mroot = _mod_root(mod_src_dir)
        if mroot is not None:
            try:
                installer = _load_installer(mroot)
                installer.revert(str(root))
                return {"ok": True}
            except BaseException:
                # BaseException (not Exception): the downloaded installer's own
                # revert() can `raise SystemExit(...)` (see apply()'s note above).
                # We WANT that caught here too - it should fall through to the
                # cache-independent _glob_restore below, exactly like any other
                # failure of the mod's own revert, not escape uncaught.
                pass                                    # fall through to the local restore
        _glob_restore(root)
        return {"ok": True}
    except PermissionError:
        return {"ok": False,
                "error": "אין הרשאת כתיבה לתיקיית המשחק. האם המשחק פתוח? סגור אותו/הפעל כמנהל ונסה שוב."}
    except Exception as e:                              # pragma: no cover
        try:
            _glob_restore(root)
            return {"ok": True}
        except Exception:
            return {"ok": False, "error": f"שגיאה: {e}"}
