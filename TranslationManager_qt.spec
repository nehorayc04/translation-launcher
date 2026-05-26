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
