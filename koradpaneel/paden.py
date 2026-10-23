"""Waar het paneel zijn bestanden zoekt: naast het programma. Als .exe (PyInstaller) is dat de map van de .exe,
anders de map van de repository. Instellingen, logs, rapporten, werkboek en testprogramma's staan daar."""

from __future__ import annotations

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASIS = Path(sys.executable).resolve().parent
    BUNDEL = Path(getattr(sys, "_MEIPASS", BASIS))        # de meegebakken bestanden (testprogramma's, icoon)
else:
    BASIS = Path(__file__).resolve().parents[1]
    BUNDEL = BASIS
