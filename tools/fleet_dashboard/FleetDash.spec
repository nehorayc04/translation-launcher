# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the personal fleet dashboard (one file, no console).

Deliberately excludes the heavy Qt modules PySide6 ships (WebEngine/3D/Charts/Multimedia): the app
is QtWidgets only, and without the excludes the one-file EXE is ~4x larger and slower to unpack.
"""
import os

HERE = os.path.abspath(os.getcwd())
ICON = os.path.abspath(os.path.join(HERE, "..", "..", "build_assets", "app.ico"))

a = Analysis(
    ["dash.py"],
    pathex=[HERE],
    binaries=[],
    datas=[("fleet_config.json", "."),          # a copy next to the EXE overrides this one
           ("fonts/Heebo-Regular.ttf", "fonts"), ("fonts/Heebo-Medium.ttf", "fonts"),
           ("fonts/Heebo-Bold.ttf", "fonts"), ("fonts/Heebo-Black.ttf", "fonts")],
    hiddenimports=["collector", "health", "prefs", "ui"],   # imported after a sys.path.insert
    excludes=[
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
        "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.Qt3DCore",
        "PySide6.Qt3DRender", "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtBluetooth",
        "PySide6.QtNetworkAuth", "PySide6.QtPositioning", "PySide6.QtSerialPort",
        "PySide6.QtTextToSpeech", "PySide6.QtDesigner", "PySide6.QtUiTools", "PySide6.QtTest",
        "PySide6.QtSql", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets", "tkinter", "numpy", "matplotlib", "PIL",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="FleetDash",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,                               # no console window ever (standing rule)
    icon=ICON if os.path.exists(ICON) else None,
)
