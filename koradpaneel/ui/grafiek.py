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
