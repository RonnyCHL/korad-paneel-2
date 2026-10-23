"""Indeling Presentatie: alleen de drie meters, groot, voor een foto of een filmpje. Esc = noodstop én terug."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..kern.geschiedenis import Meting
from ..voeding.basis import Stand
from .eenvoudig import nl
from .meters import RingMeter
from .thema import Thema


class Presentatie(QWidget):
    def __init__(self, thema: Thema, vmax: float, imax: float, projectnaam: str):
        super().__init__()
        self.thema = thema
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 18, 40, 14)
        root.setSpacing(10)
        kop = QHBoxLayout()
        t = QLabel("KORAD KA3005PS")
        t.setStyleSheet("font-size: 22px; font-weight: 700; letter-spacing: 2px")
        self.l_project = QLabel(projectnaam)
        self.l_project.setObjectName("zacht")
        self.l_project.setStyleSheet("font-size: 16px")
        self.l_status = QLabel("")
        self.l_status.setStyleSheet("font-size: 16px")
        self.l_tijd = QLabel("")
        self.l_tijd.setObjectName("cijfer")
        self.l_tijd.setStyleSheet(f"font-size: 16px; color: {thema.inkt_zacht}")
        kop.addWidget(t)
        kop.addSpacing(16)
        kop.addWidget(self.l_project)
        kop.addStretch(1)
        kop.addWidget(self.l_status)
        kop.addSpacing(20)
        kop.addWidget(self.l_tijd)
        root.addLayout(kop)
        rij = QHBoxLayout()
        rij.setSpacing(48)
        self.m_v = RingMeter(thema, "", "volt", "spanning", 2, vmax)
        self.m_i = RingMeter(thema, "", "ampère", "stroom", 3, imax)
        self.m_w = RingMeter(thema, "", "watt", "vermogen", 2, round(vmax * imax * 1.05, 1))
        for m in (self.m_v, self.m_i, self.m_w):
            m.setMinimumSize(280, 280)
            rij.addWidget(m, 1)
        root.addLayout(rij, 1)
        voet = QHBoxLayout()
        v = QLabel("Esc = noodstop en terug naar het paneel")
        v.setObjectName("zacht")
        self.l_voet = QLabel("")
        self.l_voet.setObjectName("zacht")
        voet.addWidget(v)
        voet.addStretch(1)
        voet.addWidget(self.l_voet)
        root.addLayout(voet)
        self.klok = QTimer(self)
        self.klok.timeout.connect(lambda: self.l_tijd.setText(datetime.now().strftime("%H:%M:%S")))
        self.klok.start(1000)

    def toon_meting(self, m: Meting) -> None:
        self.m_v.zet(m.v)
        self.m_i.zet(m.i)
        self.m_w.zet(m.w)

    def toon_stand(self, s: Stand) -> None:
        t = self.thema
        bol = t.goed if s.uitgang else t.uit
        woord = ("CC · stroom begrensd" if s.cc else "CV · vaste spanning") if s.uitgang else "uitgang uit"
        self.l_status.setText(f'<span style="color:{bol}">●</span>&nbsp; {woord}')

    def toon_instellingen(self, v: float, i: float) -> None:
        self.m_v.zet(self.m_v.waarde, merk=v, ondertekst=f"ingesteld {nl(v, 2)} V")
        self.m_i.zet(self.m_i.waarde, merk=i, ondertekst=f"grens {nl(i, 3)} A")

    def zet_grens(self, vmax: float, imax: float) -> None:
        self.m_v.zet_maximum(vmax)
        self.m_i.zet_maximum(imax)
        self.m_w.zet_maximum(round(vmax * imax * 1.05, 1))
