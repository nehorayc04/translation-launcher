"""
signalrgb_mod.py — local lifecycle for the SignalRGB Hebrew translation.

SignalRGB is Qt-6 software; the translation spans FOUR surfaces (the embedded
.qm inside SignalRgb.exe, the exe's language-picker literal, the loose
Macroscripts\\*.js, and every device-plugin label) plus a registry locale flag.
That whole apply/revert is already implemented, self-contained and proven, by
the mod package's own `install.py` (+ the bundled codecs) — so this module
DOWNLOADS that package from the cloud (Worker slug `signalrgb-hebrew` → GitHub
release) and runs its `deploy()` / `revert()` in-process, exactly like the
Witcher-3 applier runs the mod's own installer.

Cloud, NOT bundled: only the tiny catalog metadata ships in the launcher.  A
pristine copy of every touched file is kept by the package OUTSIDE the app
folder (`%LOCALAPPDATA%\\WhirlwindFX\\SignalRgb\\hebrew_backup`), so a SignalRGB
update — which replaces the app folder — is handled by simply re-running the
install (the package always rebuilds from that backup).
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

ProgressCB = Callable[[str, float, str], None]

_CREATE_NO_WINDOW = 0x08000000


class _NoConsole:
    """Suppress the console window a DOWNLOADED installer's child process
    flashes when spawned from the launcher's windowless GUI. patch_exe's
    is_running() runs `subprocess.run(['tasklist', ...])` with no window flag,
    which pops a terminal. Patch subprocess.Popen for the duration so every
    child inherits CREATE_NO_WINDOW on Windows (subprocess.run/call/check_* all
    go through Popen)."""

    def __enter__(self):
        self._orig = subprocess.Popen.__init__
        if sys.platform == "win32":
            _orig = self._orig

            def _patched(s, *a, **kw):
                kw["creationflags"] = kw.get("creationflags", 0) | _CREATE_NO_WINDOW
                return _orig(s, *a, **kw)

            subprocess.Popen.__init__ = _patched
        return self

    def __exit__(self, *exc):
        subprocess.Popen.__init__ = self._orig
        return False

CACHE_DIR = Path.home() / ".translation_manager" / "mod_cache" / "signalrgb"
PKG_DIR = CACHE_DIR / "pkg"                     # the extracted installer package
STATE_FILE = CACHE_DIR / "state.json"


# ── state ─────────────────────────────────────────────────────
def read_state() -> dict:
    try:
        d = json.loads(STATE_FILE.read_text("utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_state(state: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def is_cached() -> bool:
    return STATE_FILE.exists() and (PKG_DIR / "install.py").is_file()


# ── the bundled installer (loaded from the cache) ─────────────
def _load_installer():
    """Import the cached package's install.py as a module.

    install.py inserts its own dir on sys.path and imports its sibling codecs
    (patch_exe / macro_scripts / build_macros / build_plugins), so loading it
    wires the whole package up.  Returns the module; caller uses .deploy()/
    .revert().  A previous load is discarded so a fresh cache is always used.
    """
    for name in ("install", "patch_exe", "macro_scripts",
                 "build_macros", "build_plugins", "qm"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(PKG_DIR))
    spec = importlib.util.spec_from_file_location("install", PKG_DIR / "install.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["install"] = mod
    spec.loader.exec_module(mod)
    return mod


def _exe_is_hebrew() -> bool:
    """Is the live SignalRgb.exe currently patched?  Read the .qm slot."""
    if not (PKG_DIR / "patch_exe.py").is_file():
        return bool(read_state().get("enabled"))
    try:
        sys.path.insert(0, str(PKG_DIR))
        sys.modules.pop("patch_exe", None)
        sys.modules.pop("qm", None)
        import patch_exe as P  # type: ignore
        import qm as Q         # type: ignore
        data = open(P.find_exe(), "rb").read()
        off, size, kind = P.find_slot(data)          # 3-tuple: (off, size, kind)
        info = Q.load(P.slot_qm(data[off:off + size], kind))   # raw or zlib slot
        heb = sum(1 for m in info["messages"] for t in m["translations"]
                  if t and any("֐" <= c <= "׿" for c in t))
        return heb > 100
    except BaseException:
        # CRITICAL: catch BaseException, NOT Exception. The DOWNLOADED package's
        # patch_exe.find_slot() does `raise SystemExit(...)` when the exe layout
        # is unrecognised (e.g. the SignalRGB app auto-updated to a new app-<ver>
        # whose .qm slot moved). SystemExit is a BaseException, so `except
        # Exception` let it escape _exe_is_hebrew → status() → the _mod_state
        # `except Exception` guard → and it TERMINATED the whole launcher at boot
        # with no traceback and no crash report (the interpreter never calls the
        # crash_reporter excepthook for SystemExit). Reconcile-against-the-exe is
        # advisory; on ANY failure fall back to the recorded state, never die.
        return bool(read_state().get("enabled"))


# ── status ────────────────────────────────────────────────────
def status() -> dict:
    st = read_state()
    enabled = bool(st.get("enabled", False))
    if is_cached():                    # reconcile against the real exe
        enabled = _exe_is_hebrew()
    return {"cached": is_cached(), "enabled": enabled, "version": st.get("version")}


# ── cache population (from a cloud download) ──────────────────
def populate_cache(src: Path, version: str) -> dict:
    """Copy the freshly-extracted installer package into the cache. `src` is
    the mod_source.fetch_and_extract output; we accept either src/install.py or
    the first install.py found under it."""
    inst = src / "install.py"
    if not inst.is_file():
        found = next(iter(src.rglob("install.py")), None)
        inst = found if found else inst
    if not inst.is_file():
        return {"ok": False, "error": "לא נמצא install.py בחבילה שהורדה"}
    root = inst.parent
    shutil.rmtree(PKG_DIR, ignore_errors=True)
    PKG_DIR.mkdir(parents=True, exist_ok=True)
    for f in root.iterdir():
        if f.is_file():
            shutil.copy2(f, PKG_DIR / f.name)
    _write_state({"version": version, "cached_at": int(time.time()),
                  "enabled": False})
    return {"ok": True}


# ── apply / revert ────────────────────────────────────────────
def enable(cb: ProgressCB | None = None) -> dict:
    if not is_cached():
        return {"ok": False, "error": "אין מטמון מקומי - יש להתקין קודם"}
    if cb:
        cb("apply", 15.0, "מחיל את התרגום")
    try:
        with _NoConsole():             # patch_exe.is_running() -> tasklist would flash a console
            _load_installer().deploy()
    except SystemExit as e:            # install.py exits on find_exe/find_slot failure
        # The downloaded installer raises SystemExit with EITHER a bare exit code
        # ("1") OR a raw English message ("no Arabic/Hebrew .qm slot found ..."):
        # both surfaced in-app in English. NEVER leak either - always a clear,
        # actionable Hebrew message.
        low = str(e or "").strip().lower()
        if "slot" in low or ".qm" in low:
            m = ("גרסת SignalRGB המותקנת אצלך חדשה מכפי שגרסת התרגום הזו תומכת "
                 "(לא נמצא סלוט תרגום מתאים בקובץ ההרצה). המתינו לעדכון תרגום תואם, "
                 "או ודאו שהתרגום עודכן לגרסה האחרונה.")
        elif "running" in low:
            m = "SignalRGB עדיין פועל. סגרו אותו לגמרי מהמגש (Quit) ונסו שוב."
        elif "not found" in low:
            m = "SignalRGB לא נמצא במחשב. ודאו שהוא מותקן ונסו שוב."
        else:
            m = ("ההתקנה נכשלה. ודאו ש-SignalRGB סגור לגמרי (כולל ממגש המערכת), "
                 "שהתרגום מעודכן לגרסה האחרונה, ושגרסת SignalRGB נתמכת - ונסו שוב.")
        return {"ok": False, "error": m}
    except Exception as e:             # pragma: no cover
        return {"ok": False, "error": f"כשל בהתקנה: {e}"}
    st = read_state(); st["enabled"] = True; _write_state(st)
    if cb:
        cb("apply", 100.0, "הושלם")
    return {"ok": True}


def disable(cb: ProgressCB | None = None) -> dict:
    if not is_cached():
        return {"ok": True}
    try:
        with _NoConsole():             # patch_exe.is_running() -> tasklist would flash a console
            _load_installer().revert()
    except SystemExit as e:            # Hebraize - never leak the raw English message
        low = str(e or "").strip().lower()
        if "running" in low:
            m = "SignalRGB עדיין פועל. סגרו אותו לגמרי מהמגש (Quit) ונסו שוב."
        else:
            m = "לא ניתן היה להסיר את התרגום. ודאו ש-SignalRGB סגור ונסו שוב."
        return {"ok": False, "error": m}
    except Exception as e:             # pragma: no cover
        return {"ok": False, "error": f"כשל בהסרה: {e}"}
    st = read_state(); st["enabled"] = False; _write_state(st)
    return {"ok": True}


def clear_cache() -> dict:
    """Revert SignalRGB, then wipe the local cache (leaves the machine pristine)."""
    r = disable()
    if not r.get("ok"):
        return r                       # do NOT wipe if the revert failed
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    return {"ok": True}
