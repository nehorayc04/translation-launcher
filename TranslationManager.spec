# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import copy_metadata

datas = [
    ('frontend\\dist', 'frontend/dist'),
    ('games.json',   '.'),
    ('news.json',    '.'),
    ('updates.json', '.'),
    ('translation_manager', 'translation_manager'),
    # Bundle the tray icon explicitly so translation_manager.tray
    # finds it via _MEIPASS in the frozen build.
    ('build_assets\\app.ico', 'build_assets'),
]
hiddenimports = [
    'bottle', 'bottle_websocket',
    'gevent', 'gevent.monkey', 'gevent.queue',
    'geventwebsocket', 'geventwebsocket.handler',
    'keyring.backends.Windows', 'keyring.backends.macOS', 'keyring.backends.SecretService',
    'cryptography.fernet', 'cryptography.hazmat.backends.openssl',
    # System tray (pystray + its Windows backend).
    'pystray', 'pystray._win32', 'PIL', 'PIL.Image',
    # HTTPS stack — listed explicitly so PyInstaller never relies on
    # transitive auto-detection. `certifi` ships the cacert.pem data
    # file that requests needs at every TLS handshake; if that file is
    # missing on disk every HTTPS call dies with OSError. Real-world
    # case (Build D, 2026-05-23): IObit Uninstaller selectively deleted
    # _internal/certifi/cacert.pem while leaving most of the launcher
    # intact; the launcher booted fine then every catalog/auth/install
    # HTTPS call started failing with "Could not find a suitable TLS CA
    # certificate bundle".
    'requests', 'urllib3', 'idna', 'charset_normalizer', 'certifi',
]
datas += collect_data_files('eel')
# cacert.pem must live at _internal/certifi/cacert.pem. PyInstaller's
# transitive scan does pull it in via `requests` → `certifi` in
# practice, but calling out the data file here makes the bundling
# explicit and survives an out-of-order import chain.
datas += collect_data_files('certifi')
datas += copy_metadata('keyring')
hiddenimports += collect_submodules('eel')
hiddenimports += collect_submodules('translation_manager.auth')
hiddenimports += collect_submodules('keyring')
hiddenimports += collect_submodules('keyring.backends')
hiddenimports += collect_submodules('cryptography')
hiddenimports += collect_submodules('pystray')


a = Analysis(
    ['main_eel.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# --onedir layout: the EXE is a thin bootstrap that points at a sibling
# directory of binaries + data. This gives Inno Setup a tree of small
# files to copy at install time (so the install progress bar streams
# nicely) instead of one giant 160 MB encrypted blob.
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
