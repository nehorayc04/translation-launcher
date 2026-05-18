# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import copy_metadata

datas = [('frontend\\dist', 'frontend/dist'), ('games.json', '.'), ('news.json', '.'), ('updates.json', '.'), ('translation_manager', 'translation_manager')]
hiddenimports = ['bottle', 'bottle_websocket', 'gevent', 'gevent.monkey', 'gevent.queue', 'gevent.event', 'geventwebsocket', 'geventwebsocket.handler', 'keyring.backends.Windows', 'keyring.backends.macOS', 'keyring.backends.SecretService', 'cryptography.fernet', 'cryptography.hazmat.backends.openssl']
datas += collect_data_files('eel')
datas += copy_metadata('keyring')
hiddenimports += collect_submodules('eel')
hiddenimports += collect_submodules('translation_manager.auth')
hiddenimports += collect_submodules('keyring')
hiddenimports += collect_submodules('keyring.backends')
hiddenimports += collect_submodules('cryptography')


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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TranslationManager',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['build_assets\\app.ico'],
)
