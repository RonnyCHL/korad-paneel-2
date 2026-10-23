# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: één .exe met icoon, zonder console.

    .venv\\Scripts\\pyinstaller korad_paneel2.spec     ->  dist\\KoradPaneel2.exe

De .exe zet zijn instellingen, logs, rapporten en werkboek naast zichzelf (zie koradpaneel/paden.py). De
testprogramma's en het icoon zitten in de .exe gebakken; een map testprogrammas naast de .exe gaat voor.
"""
from pathlib import Path

HIER = Path(SPECPATH)

a = Analysis(
    ["korad_paneel2.py"],
    pathex=[str(HIER)],
    binaries=[],
    datas=[(str(HIER / "testprogrammas" / "*.json"), "testprogrammas"), (str(HIER / "korad.ico"), ".")],
    hiddenimports=["pyqtgraph.graphicsItems.ViewBox.axisCtrlTemplate_pyside6",
                   "pyqtgraph.graphicsItems.PlotItem.plotConfigTemplate_pyside6",
                   "pyqtgraph.imageview.ImageViewTemplate_pyside6", "serial.tools.list_ports"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
              "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtPdf", "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtRemoteObjects",
              "PySide6.QtSensors", "PySide6.QtSerialBus", "PySide6.QtTextToSpeech", "PySide6.QtWebChannel",
              "PySide6.QtWebSockets", "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtDesigner",
              "PySide6.QtHelp", "PySide6.QtUiTools", "PySide6.QtXml", "PySide6.QtSql", "PySide6.QtTest",
              "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvgWidgets", "PySide6.QtNetworkAuth",
              "PySide6.QtHttpServer", "PySide6.QtGraphs", "PySide6.QtQuick3D", "PySide6.QtScxml",
              "PySide6.QtStateMachine", "PySide6.QtSpatialAudio", "PySide6.QtQuickWidgets", "PySide6.QtWebView",
              "PySide6.QtAsyncio", "numpy.testing", "matplotlib", "scipy", "pandas", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="KoradPaneel2",
    icon=str(HIER / "korad.ico"),
    debug=False, strip=False, upx=False,
    console=False,
    disable_windowed_traceback=False,
)
