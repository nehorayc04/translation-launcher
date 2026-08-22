# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — Community Compute desktop worker (one file, no console).

Widgets-only PySide6 (the heavy Qt modules are excluded so the one-file EXE stays
small). Bundles the Heebo TTFs + the local modules; keyring's Windows backend and
cryptography are pulled in explicitly so the encrypted keystore works frozen.
"""
import os

HERE = os.path.abspath(os.getcwd())
ICON = os.path.abspath(os.path.join(HERE, "..", "..", "build_assets", "app.ico"))

a = Analysis(
    ["app.py"],
    pathex=[HERE],
    binaries=[],
    # The icon is BOTH the EXE icon and a runtime data file: the tray/window icon is
    # loaded at runtime from _MEIPASS, and `icon=` alone does not put it there — an
    # empty tray icon is invisible in the notification area, which is exactly where a
    # background app has to be findable.
    datas=[("fonts/Heebo-Regular.ttf", "fonts"), ("fonts/Heebo-Medium.ttf", "fonts"),
           ("fonts/Heebo-Bold.ttf", "fonts"), ("fonts/Heebo-Black.ttf", "fonts"),
           (ICON, ".")],
    hiddenimports=[
        "config", "keystore", "state", "providers", "client", "engine", "bigtoggle", "ui", "single",
        "stagering",
        "keyring.backends.Windows", "keyring.backends.chainer", "keyring.backends.fail",
        "win32ctypes.pywin32", "cryptography.fernet",
    ],
    excludes=[
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.Qt3DCore",
        "PySide6.Qt3DRender", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtBluetooth",
        "PySide6.QtNetworkAuth", "PySide6.QtPositioning", "PySide6.QtSerialPort",
        "PySide6.QtTextToSpeech", "PySide6.QtDesigner", "PySide6.QtUiTools", "PySide6.QtTest",
        "PySide6.QtSql", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "tkinter", "numpy", "matplotlib", "PIL",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="CommunityCompute",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon=ICON if os.path.exists(ICON) else None,
)
