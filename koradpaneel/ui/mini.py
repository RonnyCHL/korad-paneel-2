"""Het Mini-venster: altijd bovenop, met spanning, stroom, vermogen, een verloopgrafiekje en een uit-knop."""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..kern.geschiedenis import Meting
from ..voeding.basis import Stand
from .eenvoudig import nl
from .thema import Thema


class Vonkje(QWidget):
    """Een klein verloopgrafiekje van de stroom in de laatste minuut."""

    def __init__(self, thema: Thema):
        super().__init__()
        self.thema = thema
        self.reeks: deque[float] = deque(maxlen=300)
        self.setFixedSize(120, 40)

    def voeg(self, i: float) -> None:
        self.reeks.append(i)
        self.update()

    def paintEvent(self, _ev):
        if len(self.reeks) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hoog = max(self.reeks) or 1e-6
        n = len(self.reeks)
        pts = [QPointF(k * (self.width() - 2) / (n - 1) + 1, self.height() - 2 - (v / hoog) * (self.height() - 6))
               for k, v in enumerate(self.reeks)]
        p.setPen(QPen(QColor(self.thema.stroom), 2))
        p.drawPolyline(QPolygonF(pts))
        p.end()


class Mini(QWidget):
    uit = Signal()

    def __init__(self, thema: Thema, projectnaam: str):
        super().__init__(None, Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Korad mini")
        self.setObjectName("grond")
        self.setFixedSize(460, 120)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 10, 16, 10)
        root.setSpacing(6)
        kop = QHBoxLayout()
        t = QLabel("KORAD")
        t.setStyleSheet("font-weight: 700; letter-spacing: 1px; font-size: 12px")
        pr = QLabel(projectnaam)
        pr.setObjectName("zacht")
        pr.setStyleSheet("font-size: 12px")
        self.l_status = QLabel("")
        self.l_status.setStyleSheet("font-size: 12px")
        r = QLabel("altijd bovenop")
        r.setObjectName("zacht")
        r.setStyleSheet("font-size: 12px")
        for w in (t, pr, self.l_status):
            kop.addWidget(w)
            kop.addSpacing(8)
        kop.addStretch(1)
        kop.addWidget(r)
        root.addLayout(kop)
        rij = QHBoxLayout()
        rij.setSpacing(18)
        self.l_v = self._getal(thema.spanning, "V")
        self.l_i = self._getal(thema.stroom, "A")
        self.l_w = self._getal(thema.vermogen, "W")
        for w in (self.l_v[0], self.l_i[0], self.l_w[0]):
            rij.addWidget(w)
        rij.addStretch(1)
        self.vonk = Vonkje(thema)
        rij.addWidget(self.vonk)
        k = QPushButton("Uit")
        k.setObjectName("gevaar")
        k.clicked.connect(self.uit.emit)
        rij.addWidget(k)
        root.addLayout(rij)
        self.thema = thema

    def _getal(self, kleur: str, eenheid: str):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        g = QLabel("–")
        g.setObjectName("cijfer")
        g.setStyleSheet(f"font-size: 26px; font-weight: 600; color: {kleur}")
        e = QLabel(eenheid)
        e.setObjectName("zacht")
        e.setStyleSheet("font-size: 11px")
        lay.addWidget(g)
        lay.addWidget(e)
        return w, g

    def toon_meting(self, m: Meting) -> None:
        self.l_v[1].setText(nl(m.v, 2))
        self.l_i[1].setText(nl(m.i, 3))
        self.l_w[1].setText(nl(m.w, 2))
        self.vonk.voeg(m.i)

    def toon_stand(self, s: Stand) -> None:
        t = self.thema
        bol = t.goed if s.uitgang else t.uit
        woord = ("CC" if s.cc else "CV") if s.uitgang else "uit"
        self.l_status.setText(f'<span style="color:{bol}">●</span>&nbsp; {woord}')
