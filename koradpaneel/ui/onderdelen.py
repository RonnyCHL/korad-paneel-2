"""De onderdelentester: diode of led, weerstand, TVS-diode. Kies een soort, Meten, en lees de uitslag."""

from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from ..kern import proeven as pv
from .eenvoudig import nl
from .meters import RingMeter
from .thema import Thema
from .uitgebreid import kaart

SCHAAL = {"diode": (5.0, 12.0), "weerstand": (1.0, 120.0), "tvs": (25.0, 6.0)}   # V en mA per soort


class OnderdelenVenster(QDialog):
    start = Signal(str)
    stop = Signal()

    def __init__(self, thema: Thema, hv, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Onderdelentester")
        self.setModal(False)
        self.thema, self.hv = thema, hv
        self.soort = "diode"
        self.uitslagen: list[pv.Onderdeel] = []
        root = QVBoxLayout(self)
        t = QLabel("Onderdelentester")
        t.setStyleSheet("font-size: 18px; font-weight: 600")
        root.addWidget(t)
        u = QLabel("De voeding als meetinstrument voor een los onderdeel: de doorlaatspanning en de richting van een diode "
                   "of led, de waarde van een kleine weerstand, of de doorslagspanning van de TVS-diode D2. De uitgang gaat "
                   "een paar seconden aan met een lage stroomgrens en daarna weer uit; je instellingen komen terug. Alleen "
                   "losse onderdelen aan de klemmen, nooit de print.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        root.addWidget(u)
        kaarten = QHBoxLayout()
        self.knoppen: dict[str, QPushButton] = {}
        for sleutel, m in pv.ONDERDELEN.items():
            k = QPushButton(f"{m['naam']}\n{m['kort']}")
            k.setObjectName("geheugen")
            k.setCheckable(True)
            k.setMinimumHeight(60)
            k.clicked.connect(lambda _=False, s=sleutel: self._kies(s))
            kaarten.addWidget(k)
            self.knoppen[sleutel] = k
        root.addLayout(kaarten)
        self.l_hoe = QLabel("")
        self.l_hoe.setObjectName("zacht")
        self.l_hoe.setWordWrap(True)
        root.addWidget(self.l_hoe)
        rij = QHBoxLayout()
        self.k_meet = QPushButton("Meten")
        self.k_meet.setObjectName("primair")
        self.k_meet.clicked.connect(self._meet_of_stop)
        rij.addWidget(self.k_meet)
        self.l_status = QLabel("")
        self.l_status.setObjectName("zacht")
        rij.addWidget(self.l_status, 1)
        root.addLayout(rij)
        midden = QHBoxLayout()
        self.m_v = RingMeter(thema, "Spanning", "V", "spanning", 2, 5.0)
        self.m_i = RingMeter(thema, "Stroom", "mA", "stroom", 1, 12.0)
        for m in (self.m_v, self.m_i):
            k, lk = kaart()
            m.setMinimumSize(200, 200)
            lk.addWidget(m)
            midden.addWidget(k)
        k, lk = kaart("Uitslag")
        self.l_kop = QLabel("")
        self.l_kop.setStyleSheet("font-size: 22px; font-weight: 700")
        self.l_uitleg = QLabel("")
        self.l_uitleg.setWordWrap(True)
        lk.addWidget(self.l_kop)
        lk.addWidget(self.l_uitleg)
        lk.addStretch(1)
        midden.addWidget(k, 1)
        root.addLayout(midden)
        k, lk = kaart("Eerdere metingen")
        self.lijst = QListWidget()
        lk.addWidget(self.lijst)
        root.addWidget(k, 1)
        self.resize(980, 720)
        self._kies("diode")

    def _kies(self, soort: str) -> None:
        self.soort = soort
        for s, k in self.knoppen.items():
            k.setChecked(s == soort)
        self.l_hoe.setText(pv.ONDERDELEN[soort]["hoe"])
        vmax, imax = SCHAAL[soort]
        self.m_v.zet_maximum(vmax)
        self.m_i.zet_maximum(imax)

    def _meet_of_stop(self) -> None:
        if isinstance(self.hv.proef, pv.Onderdeel):
            self.stop.emit()
        else:
            self.start.emit(self.soort)

    def proef_klaar(self, p: pv.Onderdeel) -> None:
        self.uitslagen.append(p)
        self.l_kop.setText(p.kop)
        self.l_uitleg.setText(p.uitleg)
        if p.v is not None:
            self.m_v.zet(p.v)
            self.m_i.zet(p.i * 1000)
        self.lijst.insertItem(0, f"{datetime.now():%H:%M:%S}  {p.m['naam']}: {p.kop}"
                              + (f"  ({nl(p.v, 2)} V, {nl(p.i * 1000, 1)} mA, {'CC' if p.cc else 'CV'})" if p.v is not None else ""))
        self.ververs()

    def ververs(self) -> None:
        p = self.hv.proef
        bezig = isinstance(p, pv.Onderdeel)
        self.k_meet.setText("Stop" if bezig else "Meten")
        self.k_meet.setObjectName("gevaar" if bezig else "primair")
        self.k_meet.style().unpolish(self.k_meet)
        self.k_meet.style().polish(self.k_meet)
        if bezig:
            self.l_status.setText(p.status(time.time()))
            m = self.hv.laatste_meting
            if m is not None:
                self.m_v.zet(m.v)
                self.m_i.zet(m.i * 1000)
        else:
            self.l_status.setText("")
