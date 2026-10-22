"""De grafiek: spanning en stroom onder elkaar met één tijdas, markeringen, een meetcursor en zoomen.

Twee gekoppelde grafieken (spanning boven, stroom onder) in plaats van twee assen op één grafiek: dat leest
eerlijker en de meetcursor hoort bij beide. Slepen en scrollen zoomt (pyqtgraph), dubbelklik is terug naar live.
"""

from __future__ import annotations

import time
from datetime import datetime

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..kern.geschiedenis import Geschiedenis
from .thema import Thema


class TijdAs(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [datetime.fromtimestamp(v).strftime("%H:%M:%S" if spacing < 60 else "%H:%M") for v in values]


class Grafiek(QWidget):
    cursor = Signal(float)           # tijd onder de muis (unix), of -1 als de muis weg is

    def __init__(self, thema: Thema, geschiedenis: Geschiedenis):
        super().__init__()
        self.thema = thema
        self.geschiedenis = geschiedenis
        self.venster_s = 300.0        # hoeveel seconden in beeld bij live
        self.live = True
        self.markers: list[tuple[float, str]] = []
        self._marker_items: list = []

        pg.setConfigOptions(antialias=True, background=thema.kaart, foreground=thema.inkt_zacht)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.boven = pg.PlotWidget(axisItems={"bottom": TijdAs(orientation="bottom")})
        self.onder = pg.PlotWidget(axisItems={"bottom": TijdAs(orientation="bottom")})
        for w, naam in ((self.boven, "V"), (self.onder, "A")):
            w.setBackground(thema.kaart)
            w.showGrid(x=True, y=True, alpha=0.12)
            w.getAxis("left").setWidth(56)
            w.getAxis("left").setLabel(naam)
            w.setMouseEnabled(x=True, y=False)
            w.setMenuEnabled(False)
            w.hideButtons()
        self.boven.getAxis("bottom").setStyle(showValues=False)
        self.onder.setXLink(self.boven)
        self.boven.setYRange(0, 6, padding=0.02)
        self.onder.setYRange(0, 2.2, padding=0.02)
        lay.addWidget(self.boven, 1)
        lay.addWidget(self.onder, 1)

        self.lijn_v = self.boven.plot([], [], pen=pg.mkPen(thema.spanning, width=2))
        self.lijn_i = self.onder.plot([], [], pen=pg.mkPen(thema.stroom, width=2))
        self.cursor_v = pg.InfiniteLine(angle=90, pen=pg.mkPen(thema.accent, width=1))
        self.cursor_i = pg.InfiniteLine(angle=90, pen=pg.mkPen(thema.accent, width=1))
        self.boven.addItem(self.cursor_v, ignoreBounds=True)
        self.onder.addItem(self.cursor_i, ignoreBounds=True)
        self.cursor_v.hide()
        self.cursor_i.hide()
        self.boven.scene().sigMouseMoved.connect(self._muis)
        self.onder.scene().sigMouseMoved.connect(self._muis)
        self.boven.getViewBox().sigRangeChangedManually.connect(lambda *_: self._handmatig())
        self.onder.getViewBox().sigRangeChangedManually.connect(lambda *_: self._handmatig())
        for w in (self.boven, self.onder):
            w.mouseDoubleClickEvent = lambda ev, w=w: self.naar_live()

        # de meetcursors A en B (Meetbank): versleepbaar, op beide grafieken gekoppeld
        self.cursors_aan = False
        self._ab: dict[str, list] = {"A": [], "B": []}
        for naam in ("A", "B"):
            for w in (self.boven, self.onder):
                lijn = pg.InfiniteLine(angle=90, movable=True, pen=pg.mkPen(thema.accent, width=2),
                                       label=naam if w is self.boven else None,
                                       labelOpts={"position": 0.97, "color": "#FFFFFF", "fill": thema.accent})
                lijn.hide()
                w.addItem(lijn, ignoreBounds=True)
                lijn.sigDragged.connect(lambda l, naam=naam: self._ab_gesleept(naam, l))
                self._ab[naam].append(lijn)

    # ---- meetcursors
    cursors_veranderd = Signal(float, float)   # tijd A, tijd B

    def zet_cursors(self, aan: bool) -> None:
        self.cursors_aan = aan
        if aan:
            x0, x1 = self.boven.getViewBox().viewRange()[0]
            l = self.geschiedenis.laatste
            if l is not None and x0 < l.t <= x1 + 1:          # om de laatste metingen heen, niet in het lege deel
                b = l.t - 1.0
                a = max(x0, b - min(60.0, (x1 - x0) * 0.4))
            else:
                a, b = x0 + (x1 - x0) * 0.3, x0 + (x1 - x0) * 0.7
            self.zet_ab(a, b)
        for lijnen in self._ab.values():
            for l in lijnen:
                l.setVisible(aan)

    def zet_ab(self, a: float, b: float) -> None:
        for l in self._ab["A"]:
            l.setPos(a)
        for l in self._ab["B"]:
            l.setPos(b)
        self.cursors_veranderd.emit(a, b)

    def _ab_gesleept(self, naam: str, lijn) -> None:
        x = lijn.getXPos()
        for l in self._ab[naam]:
            if l is not lijn:
                l.setPos(x)
        self.cursors_veranderd.emit(self._ab["A"][0].getXPos(), self._ab["B"][0].getXPos())

    def ab(self) -> tuple[float, float]:
        a, b = self._ab["A"][0].getXPos(), self._ab["B"][0].getXPos()
        return (a, b) if a <= b else (b, a)

    # ---- gegevens
    def zet_bereik(self, vmax: float, imax: float) -> None:
        self.boven.setYRange(0, vmax * 1.1, padding=0.02)
        self.onder.setYRange(0, imax * 1.1, padding=0.02)

    def zet_venster(self, seconden: float) -> None:
        self.venster_s = seconden
        self.naar_live()

    def naar_live(self) -> None:
        self.live = True
        self.ververs()

    def _handmatig(self) -> None:
        self.live = False

    def ververs(self) -> None:
        nu = time.time()
        van = nu - self.venster_s if self.live else self.boven.getViewBox().viewRange()[0][0]
        tot = nu if self.live else self.boven.getViewBox().viewRange()[0][1]
        pts = self.geschiedenis.tussen(van - 2, tot + 2)
        if pts:
            ts = [p.t for p in pts]
            self.lijn_v.setData(ts, [p.v for p in pts])
            self.lijn_i.setData(ts, [p.i for p in pts])
        if self.live:
            self.boven.setXRange(van, tot, padding=0)

    def markeer(self, t: float, tekst: str) -> None:
        self.markers.append((t, tekst))
        for w in (self.boven, self.onder):
            lijn = pg.InfiniteLine(pos=t, angle=90, pen=pg.mkPen(self.thema.inkt_vaag, width=1, style=Qt.DashLine),
                                   label=tekst if w is self.boven else None,
                                   labelOpts={"position": 0.92, "color": self.thema.inkt_zacht, "fill": self.thema.kaart})
            w.addItem(lijn, ignoreBounds=True)
            self._marker_items.append(lijn)

    # ---- muis
    def _muis(self, pos) -> None:
        vb = self.boven.getViewBox()
        if self.boven.sceneBoundingRect().contains(pos) or self.onder.sceneBoundingRect().contains(pos):
            t = vb.mapSceneToView(pos).x()
            self.cursor_v.setPos(t)
            self.cursor_i.setPos(t)
            self.cursor_v.show()
            self.cursor_i.show()
            self.cursor.emit(t)
        else:
            self.cursor_v.hide()
            self.cursor_i.hide()
            self.cursor.emit(-1.0)
