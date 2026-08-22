"""Switchable launcher app-icon (window / taskbar / tray + launch shortcuts).

The user picks one of 12 brand-icon variants in Settings. A variant is a
`.ico` (multi-size, bundled under `translation_manager/assets/app_icons/`) plus
a `.png` thumbnail served to the web UI. Two axes, exactly what the user asked
for:

  * style  ∈ {5c, 5e, 5g}   (three letterform treatments)
  * shape  ∈ {circle, square(=rounded-square)}
  * corner ∈ {sharp, round} (the M-glyph corner treatment)

Applying a variant:
  * LIVE, no restart - QApplication + the running window's title-bar/taskbar
    icon (setWindowIcon) and the system-tray icon (setIcon).
  * The Start-menu / Desktop / pinned-taskbar SHORTCUTS get their IconLocation
    repointed at the chosen `.ico` (best-effort, hidden PowerShell). A distinct
    per-variant filename busts Explorer's icon cache.

NOT changeable at runtime: the raw `.exe` file icon in Explorer (baked into the
PE at build time) - that stays the build default (5g-circle-round). The launch
shortcut the user actually clicks DOES reflect their choice.

Pure stdlib + a lazy PySide6 import; safe no-op off Windows / when frozen data
is missing. Never raises to the caller.
"""

from __future__ import annotations

import base64
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# id -> (style, shape, corner). MUST match the generated asset filenames
# (scratchpad/gen_all_assets.py + gen_brand_app.py) and the frontend picker.
# "brand" = the standalone chrome-badge logo (the default; matches the website),
# rendered separately from the 5c/5e/5g style grid in the picker.
VARIANTS: dict[str, tuple[str, str, str]] = {
    # The two chrome brand badges the picker offers (circle / rounded-square).
    "brand":           ("brand", "circle", "round"),
    "brand-square":    ("brand", "square", "round"),
    "5c-circle-sharp": ("5c", "circle", "sharp"),
    "5c-circle-round": ("5c", "circle", "round"),
    "5c-square-sharp": ("5c", "square", "sharp"),
    "5c-square-round": ("5c", "square", "round"),
    "5e-circle-sharp": ("5e", "circle", "sharp"),
    "5e-circle-round": ("5e", "circle", "round"),
    "5e-square-sharp": ("5e", "square", "sharp"),
    "5e-square-round": ("5e", "square", "round"),
    "5g-circle-sharp": ("5g", "circle", "sharp"),
    "5g-circle-round": ("5g", "circle", "round"),
    "5g-square-sharp": ("5g", "square", "sharp"),
    "5g-square-round": ("5g", "square", "round"),
}
DEFAULT = "brand"

# ── Windows app identity (native toasts + taskbar) ────────────
# The AUMID must match the `AppUserModelID` installer.iss stamps on the
# shortcuts. NOTE: this string is USER-VISIBLE - Windows falls back to showing
# the raw AUMID as the toast's app name until DisplayName is registered below,
# so it must carry the PROJECT's name only, never a personal one.
APP_USER_MODEL_ID = "HebrewTranslationHub.TranslationManager"
# What the native Windows notification actually shows as the sender.
TOAST_DISPLAY_NAME = "מנהל התרגומים"

_CREATE_NO_WINDOW = 0x08000000


def is_valid(variant: str) -> bool:
    return variant in VARIANTS


# ── resolution ────────────────────────────────────────────────
def _assets_dir() -> Path:
    """`.../assets/app_icons` in a PyInstaller bundle (via _MEIPASS) or dev."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = Path(base) / "translation_manager" / "assets" / "app_icons"
        if p.exists():
            return p
    return Path(__file__).resolve().parent / "assets" / "app_icons"


def ico_path(variant: str) -> Path | None:
    if not is_valid(variant):
        variant = DEFAULT
    p = _assets_dir() / f"{variant}.ico"
    if p.exists():
        return p
    # fall back to the build default that ships at the app root
    base = getattr(sys, "_MEIPASS", None)
    if base:
        alt = Path(base) / "build_assets" / "app.ico"
        if alt.exists():
            return alt
    return None


# The Settings picker no longer offers the 5c/5e/5g letterform styles - it is
# just circle / rounded-square, both showing the chrome brand badge. A value
# persisted BEFORE that change (e.g. "5g-square-round") is therefore ORPHANED:
# it still wins over DEFAULT, so the app keeps showing the old gradient-M icon
# on the window/taskbar/tray/toast, and the picker can't even show it as
# selected - the user sees a stale icon with no way to understand why. Map any
# legacy id onto the brand badge of the SAME SHAPE, preserving their choice.
_LEGACY_STYLES = ("5c", "5e", "5g")


def _migrate(variant: str) -> str:
    """Legacy style variant → the brand badge of the same shape."""
    if not isinstance(variant, str) or not variant:
        return DEFAULT
    if variant.split("-", 1)[0] in _LEGACY_STYLES:
        return "brand-square" if "-square" in variant else "brand"
    return variant


def current() -> str:
    try:
        from . import launcher_prefs
        v = _migrate(launcher_prefs.get_app_icon())
        return v if is_valid(v) else DEFAULT
    except Exception:
        return DEFAULT


def options() -> list[dict]:
    """Metadata for the Settings picker. `thumb` is relative to the web root
    (frontend/public/app_icons/<id>.png)."""
    out = []
    for vid, (style, shape, corner) in VARIANTS.items():
        out.append({
            "id": vid, "style": style, "shape": shape, "corner": corner,
            "thumb": f"app_icons/{vid}.png",
        })
    return out


# ── live apply (window / taskbar / tray) ──────────────────────
def qicon(variant: str):
    """QIcon for a variant (lazy PySide6). None if unavailable."""
    try:
        from PySide6.QtGui import QIcon
        p = ico_path(variant)
        return QIcon(str(p)) if p else None
    except Exception:
        log.debug("app_icon.qicon failed", exc_info=True)
        return None


def apply_live(variant: str, window=None, tray=None) -> None:
    """Set the app/window/tray icon NOW (no restart). Best-effort."""
    ic = qicon(variant)
    if ic is None:
        return
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setWindowIcon(ic)
    except Exception:
        log.debug("app_icon: setWindowIcon(app) failed", exc_info=True)
    if window is not None:
        try:
            window.setWindowIcon(ic)
        except Exception:
            log.debug("app_icon: window.setWindowIcon failed", exc_info=True)
    if tray is not None:
        try:
            # Tray wrapper exposes the underlying QSystemTrayIcon as `_tray`.
            t = getattr(tray, "_tray", tray)
            t.setIcon(ic)
        except Exception:
            log.debug("app_icon: tray.setIcon failed", exc_info=True)


# ── launch-shortcut repoint (best-effort, hidden) ─────────────
def _exe_path() -> str | None:
    """The installed launcher exe (frozen only). None in dev."""
    if getattr(sys, "frozen", False):
        return sys.executable
    return None


def repoint_shortcuts(variant: str) -> None:
    """Point every Start-menu/Desktop/pinned shortcut that launches us at the
    chosen variant's .ico. Hidden PowerShell; no window, never blocks/raises."""
    exe = _exe_path()
    ico = ico_path(variant)
    if not exe or ico is None:
        return
    exe_name = os.path.basename(exe)
    # Escape single quotes for PowerShell single-quoted string literals (a lone '
    # in an install path like  D:\Dave's Games\...  would otherwise TRUNCATE the
    # -Command string and silently corrupt the whole repoint, invisibly).
    def _q(s) -> str:
        return str(s).replace("'", "''")
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        f"$exe='{_q(exe)}';$exeName='{_q(exe_name)}';$ico='{_q(ico)}';"
        "$roots=@("
        "[Environment]::GetFolderPath('Desktop'),"
        "[Environment]::GetFolderPath('CommonDesktopDirectory'),"
        "[Environment]::GetFolderPath('Programs'),"
        "[Environment]::GetFolderPath('CommonPrograms'),"
        "(Join-Path $env:APPDATA 'Microsoft\\Internet Explorer\\Quick Launch')"
        ");"
        "$sh=New-Object -ComObject WScript.Shell;"
        "foreach($r in $roots){ if($r -and (Test-Path $r)){"
        "  Get-ChildItem -Path $r -Filter *.lnk -Recurse -ErrorAction SilentlyContinue | ForEach-Object {"
        "    $lnk=$sh.CreateShortcut($_.FullName);"
        "    if($lnk.TargetPath -and ($lnk.TargetPath -ieq $exe -or ([System.IO.Path]::GetFileName($lnk.TargetPath) -ieq $exeName))){"
        "      $lnk.IconLocation=$ico+',0'; $lnk.Save() } } } }"
    )
    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", ps],
            creationflags=_CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        )
    except Exception:
        log.debug("app_icon.repoint_shortcuts spawn failed", exc_info=True)


# ── native-toast identity (name + icon on the Windows notification) ──
# The round, transparent brand mark used for the notification logo, independent
# of the user's chosen taskbar-icon SHAPE (Windows circle-crops the toast logo).
_TOAST_LOGO = "brand"


def _toast_icon(variant: str | None = None) -> str | None:
    """A STABLE on-disk image for the toast icon.

    Must NOT be a temp path: the registry value outlives the process. Under
    PyInstaller ONEDIR `_MEIPASS` is the installed `_internal` folder (not a
    temp dir), so both candidates below are permanent. Prefer the PNG the web UI
    already ships (Windows renders PNG toast icons most reliably), else the .ico.
    """
    v = variant or current()
    base = getattr(sys, "_MEIPASS", None)
    if base:
        png = Path(base) / "frontend" / "dist" / "app_icons" / f"{v}.png"
        if png.exists():
            return str(png)
    p = ico_path(v)
    return str(p) if p else None


def register_toast_identity(variant: str | None = None) -> None:
    """Give our native Windows notifications a real NAME and ICON.

    Windows resolves a non-packaged app's toast identity from
    HKCU\\Software\\Classes\\AppUserModelId\\<AUMID>. WITHOUT this key the toast
    header falls back to the raw AUMID string ("Company.App") and a generic
    icon - which is exactly what a user sees as "why is that text my app name?".
    With it, the toast shows TOAST_DISPLAY_NAME + our icon, and the app appears
    under Settings → System → Notifications so it can be toggled per-app.
    Safe no-op off Windows; never raises."""
    if sys.platform != "win32":
        return
    try:
        import winreg
        with winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            rf"Software\Classes\AppUserModelId\{APP_USER_MODEL_ID}",
        ) as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, TOAST_DISPLAY_NAME)
            winreg.SetValueEx(k, "ShowInSettings", 0, winreg.REG_DWORD, 1)
            # The notification logo is Windows chrome, NOT the taskbar-icon shape
            # the user picked. Windows circle-crops the toast app-logo, so a SQUARE
            # variant (brand-square.png is flattened on WHITE for the installer
            # wizard) shows cut + white corners. Always use the round, transparent
            # `brand` mark so the circle crop looks right regardless of the choice.
            icon = _toast_icon(_TOAST_LOGO) or _toast_icon(variant)
            if icon:
                winreg.SetValueEx(k, "IconUri", 0, winreg.REG_SZ, icon)
    except Exception:
        log.debug("register_toast_identity failed (non-fatal)", exc_info=True)


# ── native Windows Toast (persists in the notification history) ──
# A FIXED PowerShell script. Untrusted values (title/body/icon) are passed via
# ENV VARS - never interpolated into the script - so there is zero PS/XML
# injection surface. The script XML-escapes each value before building the toast.
#
# WHY a real Toast instead of QSystemTrayIcon.showMessage: showMessage emits a
# legacy Shell_NotifyIcon BALLOON tip - it pops for a few seconds and is GONE;
# Windows does NOT keep it in the Action Center / notification history. A real
# ToastNotification shown through a notifier tied to our AUMID (registered via a
# Start-menu shortcut + register_toast_identity) DOES persist in the history and
# shows TOAST_DISPLAY_NAME + our icon. Windows PowerShell 5.1 (`powershell.exe`,
# NOT `pwsh`) is required for the WinRT projection.
_TOAST_PS = r"""
$ErrorActionPreference='SilentlyContinue'
try {
  $null=[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
  $null=[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime]
  $aumid=[string]$env:TM_TOAST_AUMID
  $title=[System.Security.SecurityElement]::Escape([string]$env:TM_TOAST_TITLE)
  $body=[System.Security.SecurityElement]::Escape([string]$env:TM_TOAST_BODY)
  $icon=[string]$env:TM_TOAST_ICON
  $img=''
  if($icon -and (Test-Path -LiteralPath $icon)){ $s=[System.Security.SecurityElement]::Escape($icon); $img="<image placement='appLogoOverride' hint-crop='circle' src='$s'/>" }
  $x="<toast><visual><binding template='ToastGeneric'>$img<text>$title</text><text>$body</text></binding></visual></toast>"
  $doc=[Windows.Data.Xml.Dom.XmlDocument]::new()
  $doc.LoadXml($x)
  $t=[Windows.UI.Notifications.ToastNotification]::new($doc)
  [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($aumid).Show($t)
} catch {}
"""


def show_toast(title: str, body: str = "") -> bool:
    """Show a NATIVE Windows Toast that stays in the notification history.

    Returns True if the toast process was spawned (essentially always on
    Windows), False if it couldn't even spawn - the caller then falls back to
    the tray balloon so a notification is never lost. Fire-and-forget, hidden,
    never blocks/raises. No-op (False) off Windows."""
    if sys.platform != "win32":
        return False
    try:
        enc = base64.b64encode(_TOAST_PS.encode("utf-16-le")).decode("ascii")
        env = dict(os.environ)
        env["TM_TOAST_AUMID"] = APP_USER_MODEL_ID
        env["TM_TOAST_TITLE"] = (title or TOAST_DISPLAY_NAME)[:200]
        env["TM_TOAST_BODY"] = (body or "")[:400]
        env["TM_TOAST_ICON"] = _toast_icon(_TOAST_LOGO) or _toast_icon() or ""
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive",
             "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass",
             "-EncodedCommand", enc],
            creationflags=_CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            env=env,
        )
        return True
    except Exception:
        log.debug("app_icon.show_toast spawn failed", exc_info=True)
        return False


# ── the one call the RPC uses ─────────────────────────────────
def set_variant(variant: str, window=None, tray=None) -> str:
    """Persist + apply live + repoint shortcuts. Returns the effective variant
    (the requested one if valid, else the current/default). Never raises."""
    if not is_valid(variant):
        return current()
    try:
        from . import launcher_prefs
        launcher_prefs.set_app_icon(variant)
    except Exception:
        log.debug("app_icon.set_variant persist failed", exc_info=True)
    apply_live(variant, window, tray)
    repoint_shortcuts(variant)
    register_toast_identity(variant)   # keep the toast icon in sync with the pick
    return variant
