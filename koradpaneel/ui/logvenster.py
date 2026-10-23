"""Oude logs: een log bekijken in de grafiek (met markeringen en de getallen), en twee logs vergelijken."""

from __future__ import annotations

import webbrowser
from datetime import datetime
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QVBoxLayout)

from ..kern import logboek, rapport as rapport_mod, vergelijk
from ..kern.geschiedenis import Geschiedenis, Meting, venster_uit
from .eenvoudig import nl
from .grafiek import Grafiek
from .thema import Thema
from .uitgebreid import kaart

LOGS = logboek.MAP
OUDE_LOGS = Path(r"D:\Ronny\Tools\korad\logs")


def kies_log(parent, titel: str) -> Path | None:
    start = str(LOGS if LOGS.exists() else (OUDE_LOGS if OUDE_LOGS.exists() else Path.home()))
    pad, _ = QFileDialog.getOpenFileName(parent, titel, start, "CSV-log (*.csv)")
    return Path(pad) if pad else None


def laad_log(parent, pad: Path) -> tuple[list[Meting], list[tuple[float, str]]] | None:
    try:
        pts, markers = logboek.lees(pad)
    except (OSError, ValueError, KeyError):
        QMessageBox.warning(parent, "Kan log niet openen", "Dit bestand is geen log van het Korad paneel, of het is beschadigd.")
        return None
    if len(pts) < 2:
        QMessageBox.warning(parent, "Te weinig metingen", "Dit log bevat minder dan twee metingen.")
        return None
    return pts, markers


class LogVenster(QDialog):
    """Eén log in de grafiek, met de markeringen en de getallen van het hele log."""

    def __init__(self, thema: Thema, pad: Path, pts: list[Meting], markers: list[tuple[float, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Log: {pad.name}")
        self.setModal(False)
        self.thema = thema
        self.pad, self.pts, self.markers = pad, pts, markers
        root = QVBoxLayout(self)
        kop = QHBoxLayout()
        t = QLabel(pad.name)
        t.setStyleSheet("font-size: 18px; font-weight: 600")
        kop.addWidget(t)
        w = venster_uit(pts)
        feiten = QLabel(f"{datetime.fromtimestamp(w.van):%d-%m-%Y %H:%M:%S} tot {datetime.fromtimestamp(w.tot):%H:%M:%S} · "
                        f"{vergelijk.duur_tekst(w.duur)} · {w.n} metingen · {len(markers)} markeringen")
        feiten.setObjectName("zacht")
        kop.addSpacing(12)
        kop.addWidget(feiten)
        kop.addStretch(1)
        self.k_rapport = QPushButton("Rapport")
        self.k_rapport.setObjectName("geheugen")
        self.k_rapport.clicked.connect(self._rapport)
        kop.addWidget(self.k_rapport)
        root.addLayout(kop)
        self.geschiedenis = Geschiedenis(maxlen=max(1000, len(pts) + 10))
        for p in pts:
            self.geschiedenis.voeg(p)
        k_graf, lg = kaart()
        self.grafiek = Grafiek(thema, self.geschiedenis)
        self.grafiek.zet_bereik(max(p.v for p in pts) or 1.0, max(p.i for p in pts) or 0.1)
        self.grafiek.live = False
        self.grafiek.boven.setXRange(w.van, w.tot, padding=0.01)
        for t_, tekst in markers:
            self.grafiek.markeer(t_, tekst)
        self.grafiek.ververs()
        lg.addWidget(self.grafiek, 1)
        root.addWidget(k_graf, 1)
        getallen = QLabel(f"spanning gemiddeld {nl(w.v_gem, 2)} V · stroom gemiddeld {nl(w.i_gem * 1000, 0)} mA, "
                          f"hoogste {nl(w.i_max * 1000, 0)} mA, laagste {nl(w.i_min * 1000, 0)} mA · "
                          f"lading {nl(w.mah, 1)} mAh · energie {nl(w.wh, 3)} Wh")
        getallen.setObjectName("zacht")
        getallen.setWordWrap(True)
        root.addWidget(getallen)
        self.resize(1100, 640)

    def _rapport(self) -> None:
        pagina = rapport_mod.maak(self.pad.stem, self.pts, self.markers, soort="log")
        pad = rapport_mod.bewaar(pagina, "log")
        webbrowser.open(pad.resolve().as_uri())


class VergelijkVenster(QDialog):
    """Twee logs over elkaar, allebei vanaf hun eigen begin, met de tabel van verschillen."""

    KLEUR = {"A": "#F5B544", "B": "#6FB1FF"}

    def __init__(self, thema: Thema, parent=None, a: tuple[Path, list[Meting]] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Logs vergelijken")
        self.setModal(False)
        self.thema = thema
        self.logs: dict[str, tuple[Path, list[Meting]] | None] = {"A": a, "B": None}
        self.wat = "stroom"
        self.rapport_pad: Path | None = None
        root = QVBoxLayout(self)
        t = QLabel("Logs vergelijken")
        t.setStyleSheet("font-size: 18px; font-weight: 600")
        root.addWidget(t)
        uitleg = QLabel("Twee logs van het paneel over elkaar, allebei vanaf hun eigen begin. Bijvoorbeeld het verbruik "
                        "voor en na een firmware-update, of met en zonder scherm.")
        uitleg.setObjectName("zacht")
        uitleg.setWordWrap(True)
        root.addWidget(uitleg)
        self.l_naam: dict[str, QLabel] = {}
        for sleutel in ("A", "B"):
            rij = QHBoxLayout()
            bol = QLabel(f'<span style="color:{self.KLEUR[sleutel]}">━</span> <b>Meting {sleutel}</b>')
            k = QPushButton("Kiezen…")
            k.setObjectName("geheugen")
            k.clicked.connect(lambda _=False, s=sleutel: self._kies(s))
            l = QLabel("nog niet gekozen")
            l.setObjectName("zacht")
            self.l_naam[sleutel] = l
            rij.addWidget(bol)
            rij.addWidget(k)
            rij.addWidget(l, 1)
            root.addLayout(rij)
        keuze = QHBoxLayout()
        self.groep = QButtonGroup(self)
        for sleutel, naam in (("stroom", "Stroom"), ("spanning", "Spanning"), ("vermogen", "Vermogen")):
            k = QPushButton(naam)
            k.setObjectName("geheugen")
            k.setCheckable(True)
            k.setChecked(sleutel == self.wat)
            k.clicked.connect(lambda _=False, s=sleutel: self._wat(s))
            self.groep.addButton(k)
            keuze.addWidget(k)
        keuze.addStretch(1)
        self.k_rapport = QPushButton("Rapport maken")
        self.k_rapport.setObjectName("primair")
        self.k_rapport.clicked.connect(self._rapport)
        keuze.addWidget(self.k_rapport)
        root.addLayout(keuze)
        k_graf, lg = kaart()
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setBackground(thema.kaart)
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.getAxis("bottom").setLabel("s sinds het begin")
        self.plot.setMenuEnabled(False)
        self.lijnen = {s: self.plot.plot([], [], pen=pg.mkPen(self.KLEUR[s], width=2)) for s in ("A", "B")}
        lg.addWidget(self.plot, 1)
        root.addWidget(k_graf, 1)
        self.tabel = QGridLayout()
        self.tabel.setHorizontalSpacing(26)
        root.addLayout(self.tabel)
        self.resize(1000, 700)
        self._ververs()

    def _kies(self, sleutel: str) -> None:
        pad = kies_log(self, f"Meting {sleutel} kiezen")
        if pad is None:
            return
        uit = laad_log(self, pad)
        if uit is None:
            return
        self.logs[sleutel] = (pad, uit[0])
        self._ververs()

    def _wat(self, wat: str) -> None:
        self.wat = wat
        self._ververs()

    def _ververs(self) -> None:
        for s in ("A", "B"):
            log = self.logs[s]
            if log is None:
                self.l_naam[s].setText("nog niet gekozen")
                self.lijnen[s].setData([], [])
                continue
            pad, pts = log
            self.l_naam[s].setText(f"{pad.name}  ({vergelijk.duur_tekst(pts[-1].t - pts[0].t)})")
            r = vergelijk.reeks(pts, self.wat)
            stap = max(1, len(r) // 4000)
            self.lijnen[s].setData([x for x, _ in r[::stap]], [y for _, y in r[::stap]])
        self.plot.getAxis("left").setLabel(vergelijk.WAT[self.wat])
        while self.tabel.count():
            w = self.tabel.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        for c, kop in enumerate(("", "Meting A", "Meting B", "Verschil B - A")):
            l = QLabel(kop)
            l.setObjectName("kopje")
            self.tabel.addWidget(l, 0, c)
        a = self.logs["A"][1] if self.logs["A"] else None
        b = self.logs["B"][1] if self.logs["B"] else None
        for r, rij in enumerate(vergelijk.rijen(a, b), 1):
            for c, tekst in enumerate(rij):
                l = QLabel(tekst)
                if c == 0:
                    l.setObjectName("zacht")
                elif c == 3 and tekst:
                    l.setObjectName("cijfer")
                self.tabel.addWidget(l, r, c)

    def _rapport(self) -> None:
        if not (self.logs["A"] and self.logs["B"]):
            QMessageBox.information(self, "Twee logs nodig", "Kies eerst meting A en meting B.")
            return
        (pa, a), (pb, b) = self.logs["A"], self.logs["B"]
        pagina = vergelijk.rapport_html(pa.name, a, pb.name, b, self.wat)
        self.rapport_pad = rapport_mod.bewaar(pagina, "vergelijking")
        webbrowser.open(self.rapport_pad.resolve().as_uri())
