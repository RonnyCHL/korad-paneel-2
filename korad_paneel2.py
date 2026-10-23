#!/usr/bin/env python3
"""Korad paneel 2: starten.

    py korad_paneel2.py                       de Korad op de poort uit de instellingen (of zelf zoeken)
    py korad_paneel2.py --poort COM10
    py korad_paneel2.py --nagebootst          zonder voeding: de nagebootste, met een gewone belasting
    py korad_paneel2.py --nagebootst tbeam    ... met het T-Beam-bordje als belasting (zie voeding/nagebootst.py);
                                              de startproef leest dan een nagebootst bordje (elke derde start dood)
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from koradpaneel.apparaat.bordje import Bordje, NagebootstBordje
from koradpaneel.apparaat.monitor import Monitor, NagebootstMonitor
from koradpaneel.ui.hoofdvenster import Hoofdvenster
from koradpaneel.voeding import korad, nagebootst


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Korad paneel 2")
    p.add_argument("--poort", help="seriële poort van de voeding, bv. COM10")
    p.add_argument("--nagebootst", nargs="?", const="belasting", metavar="MODEL",
                   help="geen echte voeding maar de nagebootste; MODEL: " + ", ".join(nagebootst.MODELLEN))
    a = p.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName("Korad paneel 2")
    app.setStyle("Fusion")

    if a.nagebootst:
        maak = lambda _poort: nagebootst.Nagebootst(a.nagebootst)
        maak_bordje = lambda _poort: NagebootstBordje("wissel")
        maak_monitor = lambda adres: NagebootstMonitor(adres)
    else:
        maak = lambda poort: korad.Korad(a.poort or poort or "COM10")
        maak_bordje = lambda poort: Bordje(poort)
        maak_monitor = lambda adres: Monitor(adres)
    venster = Hoofdvenster(maak, maak_bordje=maak_bordje, maak_monitor=maak_monitor)
    venster.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
