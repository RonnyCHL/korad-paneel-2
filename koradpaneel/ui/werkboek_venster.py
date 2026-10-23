"""Het werkboek: alles wat gemeten is op datum, met zoeken, een staafje per dag, openen van het bestand, een
notitie toevoegen, en het oude werkboek (tkinter-paneel) inlezen."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog,
                               QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)

from ..kern import logboek, rapport as rapport_mod
from ..kern.werkboek import Regel, Werkboek
from .thema import Thema

OUD_WERKBOEK = Path(r"D:\Ronny\Tools\korad\korad_werkboek.json")
SOORT_KLEUR = {"log": "#6FB1FF", "rapport": "#3DDC97", "programma": "#3D7BF2", "startproef": "#F5B544",
               "vergelijking": "#5BB8F5", "notitie": "#E8EBF0", "nachttest": "#C084FC", "rooktest": "#FF6B6B"}


class WerkboekVenster(QDialog):
    open_log = Signal(object)        # Path: een CSV-log in het paneel openen

    def __init__(self, thema: Thema, werkboek: Werkboek, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Werkboek")
        self.setModal(False)
        self.thema = thema
        self.wb = werkboek
        root = QVBoxLayout(self)
        kop = QHBoxLayout()
        t = QLabel("Werkboek")
        t.setStyleSheet("font-size: 18px; font-weight: 600")
        kop.addWidget(t)
        self.l_aantal = QLabel("")
        self.l_aantal.setObjectName("zacht")
        kop.addSpacing(12)
        kop.addWidget(self.l_aantal)
        kop.addStretch(1)
        self.zoek = QLineEdit()
        self.zoek.setPlaceholderText("Zoeken…")
        self.zoek.setStyleSheet("font-family: inherit; font-size: 13px; padding: 8px 10px")
        self.zoek.setFixedWidth(240)
        self.zoek.textChanged.connect(self._ververs)
        kop.addWidget(self.zoek)
        root.addLayout(kop)

        pg.setConfigOptions(antialias=True)
        self.staven = pg.PlotWidget()
        self.staven.setBackground(thema.kaart)
        self.staven.setFixedHeight(110)
        self.staven.setMenuEnabled(False)
        self.staven.setMouseEnabled(x=False, y=False)
        self.staven.hideAxis("left")
        self.staven.getAxis("bottom").setStyle(showValues=False)
        root.addWidget(self.staven)

        self.tabel = QTableWidget(0, 4)
        self.tabel.setHorizontalHeaderLabels(["wanneer", "soort", "titel", "uitleg"])
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabel.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabel.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabel.setShowGrid(False)
        h = self.tabel.horizontalHeader()
        for c in (0, 1):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Interactive)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        self.tabel.setColumnWidth(2, 360)
        self.tabel.doubleClicked.connect(lambda _i: self._openen())
        root.addWidget(self.tabel, 1)

        knoppen = QHBoxLayout()
        for tekst, fn in (("Openen", self._openen), ("Map openen", self._map), ("Notitie…", self._notitie),
                          ("Verwijderen", self._verwijderen), ("Mappen doorzoeken", self._scan),
                          ("Oude werkboek inlezen", self._oud)):
            k = QPushButton(tekst)
            k.setObjectName("geheugen")
            k.clicked.connect(fn)
            knoppen.addWidget(k)
        knoppen.addStretch(1)
        root.addLayout(knoppen)
        self.resize(1100, 680)
        self._ververs()

    # ---- tonen
    def _gefilterd(self) -> list[Regel]:
        return list(reversed(self.wb.zoek(self.zoek.text())))

    def _ververs(self) -> None:
        regels = self._gefilterd()
        self.l_aantal.setText(f"{len(regels)} van {len(self.wb.regels)} regels")
        self.tabel.setRowCount(0)
        for r in regels:
            rij = self.tabel.rowCount()
            self.tabel.insertRow(rij)
            cellen = [datetime.fromtimestamp(r.t).strftime("%d-%m-%Y %H:%M"), r.soort, r.titel, r.uitleg]
            for c, tekst in enumerate(cellen):
                it = QTableWidgetItem(tekst)
                if c == 1:
                    it.setForeground(pg.mkColor(SOORT_KLEUR.get(r.soort, self.thema.inkt)))
                it.setData(Qt.UserRole, r.t)
                self.tabel.setItem(rij, c, it)
        self._staven()

    def _staven(self) -> None:
        self.staven.clear()
        per_dag = self.wb.per_dag()
        if not per_dag:
            return
        dagen = sorted(per_dag)[-60:]
        x = list(range(len(dagen)))
        y = [per_dag[d] for d in dagen]
        self.staven.addItem(pg.BarGraphItem(x=x, height=y, width=0.7, brush=self.thema.accent, pen=None))
        self.staven.setXRange(-0.5, max(14, len(dagen)) - 0.5, padding=0)
        self.staven.setYRange(0, max(y) * 1.2 or 1, padding=0)
        tekst = pg.TextItem(f"{dagen[0][8:]}-{dagen[0][5:7]} … {dagen[-1][8:]}-{dagen[-1][5:7]}: metingen per dag",
                            color=self.thema.inkt_zacht, anchor=(0, 0))
        tekst.setPos(-0.4, max(y) * 1.2 or 1)
        self.staven.addItem(tekst)

    def _gekozen(self) -> Regel | None:
        it = self.tabel.item(self.tabel.currentRow(), 0)
        if it is None:
            return None
        t = it.data(Qt.UserRole)
        for r in self.wb.regels:
            if r.t == t:
                return r
        return None

    # ---- knoppen
    def _openen(self) -> None:
        r = self._gekozen()
        if r is None:
            return
        if not r.pad:
            QMessageBox.information(self, "Geen bestand", r.uitleg or r.titel)
            return
        pad = Path(r.pad)
        if not pad.exists():
            QMessageBox.information(self, "Bestand weg", f"{pad} bestaat niet meer.")
            return
        if pad.suffix.lower() == ".csv":
            self.open_log.emit(pad)
        else:
            webbrowser.open(pad.resolve().as_uri())

    def _map(self) -> None:
        r = self._gekozen()
        map_ = Path(r.pad).parent if r and r.pad else rapport_mod.MAP
        map_.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(map_))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(map_)])  # noqa: S603, S607

    def _notitie(self) -> None:
        tekst, ok = QInputDialog.getMultiLineText(self, "Notitie", "Wat wil je vastleggen?")
        if ok and tekst.strip():
            regel = tekst.strip().splitlines()[0][:160]
            self.wb.voeg("notitie", regel, None, tekst.strip())
            self._ververs()

    def _verwijderen(self) -> None:
        r = self._gekozen()
        if r is None:
            return
        if QMessageBox.question(self, "Verwijderen", f"Deze regel uit het werkboek halen?\n\n{r.titel}\n\n"
                                "Het bestand zelf blijft staan.") == QMessageBox.Yes:
            self.wb.regels.remove(r)
            self.wb.bewaar()
            self._ververs()

    def _scan(self) -> None:
        n = self.wb.scan([(rapport_mod.MAP, "*.html", "rapport"), (logboek.MAP, "*.csv", "log")])
        self._ververs()
        QMessageBox.information(self, "Mappen doorzocht", f"{n} nieuwe regel{'s' if n != 1 else ''} gevonden.")

    def _oud(self) -> None:
        pad = OUD_WERKBOEK
        if not pad.exists():
            p, _ = QFileDialog.getOpenFileName(self, "Oude werkboek kiezen", str(Path.home()), "JSON (*.json)")
            if not p:
                return
            pad = Path(p)
        n = self.wb.laad(pad)
        self.wb.bewaar()
        self._ververs()
        QMessageBox.information(self, "Oude werkboek", f"{n} regel{'s' if n != 1 else ''} overgenomen uit {pad.name}.")
