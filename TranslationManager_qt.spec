# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the Qt-shell build.
#
# Parallel to TranslationManager.spec (the Eel build) - same data files
# + auth/crypto/HTTPS stack, but the transport flips from Eel/gevent-
# WebSocket to PySide6 QWebChannel. The Eel package itself is shimmed
# out at runtime by translation_manager.qt_shell.eel_shim, so we
# exclude bottle + geventwebsocket + eel + pystray here to keep the
# bundle smaller.
#
# Notes:
#   * gevent stays in hiddenimports - main_eel.py monkey-patches
#     socket/ssl/select at module-load time. Removing it would break
#     the first import; the patches themselves are harmless under Qt
#     because no gevent hub runs.
#   * PySide6's PyInstaller hook (shipped via pyinstaller-hooks-contrib)
#     handles the QtWebEngine binaries + qwebchannel.js Qt resource
#     automatically. We still list the explicit submodules so a missing
#     hook can't silently produce a launcher that crashes on import.
#   * Output name stays "TranslationManager" so installer.iss can host
#     either build with no diff to the [Files] / [Icons] sections.

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import copy_metadata

datas = [
    ('frontend\\dist',          'frontend/dist'),
    ('games.json',              '.'),
    ('news.json',               '.'),
    ('updates.json',            '.'),
    ('translation_manager',     'translation_manager'),
    ('build_assets\\app.ico',   'build_assets'),
]
# Same certifi rationale as TranslationManager.spec - without
# cacert.pem on disk every HTTPS call dies with "Could not find a
# suitable TLS CA certificate bundle".
datas += collect_data_files('certifi')
datas += copy_metadata('keyring')

hiddenimports = [
    # ── PySide6 stack ────────────────────────────────────────
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebChannel',
    'shiboken6',

    # ── gevent (see header note) ─────────────────────────────
    'gevent', 'gevent.monkey',

    # ── Auth + DRM ───────────────────────────────────────────
    'keyring.backends.Windows',
    'keyring.backends.macOS',
    'keyring.backends.SecretService',
    'cryptography.fernet',
    'cryptography.hazmat.backends.openssl',

    # ── HTTPS stack (explicit so PyInstaller's transitive scan
    #    never has a chance to drop them) ─────────────────────
    'requests', 'urllib3', 'idna', 'charset_normalizer', 'certifi',

    # ── "Brain" + plugin system (all lazily imported inside functions,
    #    so PyInstaller's static scan can miss them — pin explicitly) ──
    'translation_manager.resilience',
    'translation_manager.perf_manager',
    'translation_manager.plugins',
    'translation_manager.plugins.registry',
    'translation_manager.plugins.save_backup',
    'translation_manager.plugins.host',
]
hiddenimports += collect_submodules('keyring')
hiddenimports += collect_submodules('keyring.backends')
hiddenimports += collect_submodules('cryptography')
hiddenimports += collect_submodules('PySide6')

# Drop the entire Eel transport chain. The Qt shell never imports
# these at runtime - eel is replaced by qt_shell.eel_shim via
# sys.modules['eel'] before main_eel.py is loaded.
excludes = [
    'eel',
    'bottle', 'bottle_websocket',
    'geventwebsocket',
    'pystray',
    'customtkinter',
    # opencv was a CTk-era dep (video_background) - deleted with
    # translation_manager/ui/. The Qt shell uses no video background.
    'cv2', 'opencv-python', 'opencv',
    # numpy (~27 MB with its bundled OpenBLAS) is pulled in ONLY by PIL's
    # type hints (`PIL._typing` does `try: import numpy.typing / except
    # ImportError`) and by two lazy helpers in PIL.Image/PIL.ImageFilter we
    # never call. Nothing in this app imports numpy - dropping it is free.
    'numpy',
    # tkinter/tcl/tk (~9 MB) - the ONLY use is main_eel's
    # _show_no_internet_dialog(), a first-run dialog on the Eel dev path.
    # The Qt shell shows its own window and never calls it.
    'tkinter', '_tkinter', 'tcl', 'tk',
]


a = Analysis(
    ['main_qt.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

# ── Trim the bundle to shrink the installer ──────────────────────────────
# Large payloads an end-user release never needs:
#   * qtwebengine_devtools_resources.debug.pak (~72 MB) — DevTools DEBUG
#     resources; never loaded by a release window.
#   * PySide6/translations/*.qm (~57 MB) — Qt's own native-widget UI strings
#     for ~40 languages. Our entire UI is the React frontend, and Windows'
#     native file/dialog chrome is localized by the OS, not these .qm files,
#     so dropping them has no visible effect.
#   * Qt6Designer / Qt6Pdf — unused modules (we use QtWidgets + WebEngine).
#   * qtwebengine_locales/*.pak (~44 MB, 53 languages) — Chromium's OWN chrome
#     strings (context menu, print/save dialogs). Our UI is the React frontend;
#     Chromium falls back to en-US for a missing locale, so Hebrew + English
#     is everything a user can actually see.
#   * every *.debug.pak / *.debug.bin (~5 MB) — Qt loads the non-.debug file.
#   * qtwebengine_devtools_resources.pak (~11 MB) — read only when the remote
#     inspector is attached (QTWEBENGINE_REMOTE_DEBUGGING), never in a release.
# Keeps opengl32sw (software-GL fallback) + the whole Quick/QML stack:
# Qt6 QWebEngineView is backed by a QQuickWidget, so dropping Qt6Quick/Qt6Qml
# would break the webview - do NOT "optimise" those away.
def _keep(entry):
    dest = str(entry[0]).replace("\\", "/").lower()
    name = dest.rsplit("/", 1)[-1]
    if "/qtwebengine_locales/" in dest:
        return name in ("en-us.pak", "he.pak")
    if name.endswith(".debug.pak") or name.endswith(".debug.bin"):
        return False
    if name == "qtwebengine_devtools_resources.pak":
        return False
    if "/translations/" in dest and dest.endswith(".qm"):
        return False
    if name in (
        "qt6designer.dll", "qtdesigner.pyd", "qt6pdf.dll", "qtpdf.pyd",
    ):
        return False
    # Guard: the launcher ships ZERO video/audio media. The whole
    # translation_manager/ dir is bundled as data, so a stray .mp4 (e.g. the
    # 59 MB junk clip that once landed there) would silently pad the installer.
    # Mod payloads use .wad/.modular/.loc/.xbt/.zip - never these containers.
    # __pycache__/*.pyc are NEVER needed in the bundle: the real modules are
    # compiled into the PYZ, and this datas copy of translation_manager/ exists
    # only for the ASSETS. Worse, they ship STALE bytecode - a .pyc built from a
    # since-edited source kept a personal name inside the installer long after
    # the .py was cleaned (extractable with `strings`). Drop them all; it also
    # trims a lot of dead weight (the whole vendor/dat1lib cache tree).
    if "/__pycache__/" in dest or dest.endswith(".pyc"):
        return False
    # NO MOD PAYLOAD SHIPS INSIDE THE INSTALLER. Every translation (GTA V,
    # Spider-Man 2, Watch Dogs 2, God of War: Ragnarök) is downloaded from the
    # Worker on first install and then kept in the launcher cache, so a new mod
    # version reaches users with no launcher update and the download stays ~22 MB
    # smaller. A machine with no/weak internet uses the OFFLINE PACKAGE
    # (tools/build_offline_bundle.py) instead of a stale copy baked in here.
    # assets/app_icons + ubisoft_games.json are NOT mods - they stay.
    if any(f"assets/{g}/" in dest for g in
           ("gtav", "spiderman2", "watchdogs2", "godofwar_ragnarok")):
        return False
    if dest.rsplit(".", 1)[-1] in ("mp4", "mkv", "mov", "avi", "webm", "m4v", "flv", "wmv"):
        return False
    return True

a.datas    = [e for e in a.datas    if _keep(e)]
a.binaries = [e for e in a.binaries if _keep(e)]

pyz = PYZ(a.pure)

# --onedir layout: small bootstrap EXE + sibling tree of binaries +
# data. Inno Setup gets a streamable file list for the install bar
# instead of one giant blob.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TranslationManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['build_assets\\app.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TranslationManager',
)
