"""Het venster 'Bordje: N starts': instellingen, Start/Stop, de tabel per start en de uitslag.

Het venster doet zelf niets met de voeding of de poort: het hoofdvenster drijft de proef (kern/startproef.py)
en roept hier toon() aan. Niet-modaal, zodat het paneel bedienbaar blijft."""

from __future__ import annotations

import time
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..kern.startproef import Startproef
from .thema import Thema


class StartproefVenster(QDialog):
    start = Signal(int, float, float, str)      # n, uit_s, aan_s, poort
    stop = Signal()

    def __init__(self, thema: Thema, poort: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("EMSN-auto: bordje starten")
        self.setModal(False)
        self.thema = thema
        self.loopt = False
        self.rapport_pad: Path | None = None
        self._getoond = 0
        root = QVBoxLayout(self)
        root.setSpacing(10)
        kop = QLabel("Bordje: N keer auto uit en aan")
        kop.setStyleSheet("font-size: 18px; font-weight: 600")
        root.addWidget(kop)
        uitleg = QLabel("Per start gaat de uitgang uit, na een paar seconden weer aan op 5,00 V (grens 2 A), en het "
                        "paneel leest in de seriële log van het bordje of de I2C-bus goed opkomt (laadchip, "
                        "bewegings- en luchtsensor antwoorden) of dood. Daarbij de stroom na 3, 10 en 30 s. Nodig: "
                        "voeding verbonden, project EMSN-auto, de laptopkabel met de rode draad doorgeknipt op de "
                        "micro-USB.")
        uitleg.setObjectName("zacht")
        uitleg.setWordWrap(True)
        root.addWidget(uitleg)

        rij = QHBoxLayout()
        rij.setSpacing(10)

        def veld(label, w):
            l = QLabel(label)
            l.setObjectName("zacht")
            rij.addWidget(l)
            rij.addWidget(w)
            rij.addSpacing(8)
            return w

        self.n = veld("Aantal starts", QSpinBox())
        self.n.setRange(1, 999)
        self.n.setValue(20)
        self.uit_s = veld("Uit (s)", QDoubleSpinBox())
        self.uit_s.setRange(1, 600)
        self.uit_s.setDecimals(0)
        self.uit_s.setValue(5)
        self.aan_s = veld("Aan (s)", QDoubleSpinBox())
        self.aan_s.setRange(32, 3600)
        self.aan_s.setDecimals(0)
        self.aan_s.setValue(45)
        self.poort = veld("Poort", QLineEdit(poort or "COM6"))
        self.poort.setFixedWidth(90)
        rij.addStretch(1)
        root.addLayout(rij)

        knoppen = QHBoxLayout()
        self.k_start = QPushButton("Start")
        self.k_start.setObjectName("primair")
        self.k_start.clicked.connect(self._start_of_stop)
        self.k_rapport = QPushButton("Rapport openen")
        self.k_rapport.setObjectName("geheugen")
        self.k_rapport.setEnabled(False)
        self.k_rapport.clicked.connect(self._open_rapport)
        self.l_status = QLabel("")
        self.l_status.setObjectName("zacht")
        knoppen.addWidget(self.k_start)
        knoppen.addWidget(self.k_rapport)
        knoppen.addSpacing(10)
        knoppen.addWidget(self.l_status, 1)
        root.addLayout(knoppen)

        self.tabel = QTableWidget(0, 7)
        self.tabel.setHorizontalHeaderLabels(["#", "boot", "poort", "3 s", "10 s", "30 s", "i2c-keuring"])
        self.tabel.verticalHeader().setVisible(False)
        self.tabel.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabel.setSelectionMode(QAbstractItemView.NoSelection)
        self.tabel.setShowGrid(False)
        h = self.tabel.horizontalHeader()
        for c in range(6):
            h.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.Stretch)
        root.addWidget(self.tabel, 1)
        self.l_uitslag = QLabel("")
        self.l_uitslag.setWordWrap(True)
        self.l_uitslag.setStyleSheet("font-weight: 600")
        root.addWidget(self.l_uitslag)
        self.resize(900, 560)

    # ---- in
    def _start_of_stop(self) -> None:
        if self.loopt:
            self.stop.emit()
        else:
            self.start.emit(self.n.value(), self.uit_s.value(), self.aan_s.value(), self.poort.text().strip() or "COM6")

    def _open_rapport(self) -> None:
        if self.rapport_pad and self.rapport_pad.exists():
            webbrowser.open(self.rapport_pad.resolve().as_uri())

    # ---- uit
    def begonnen(self) -> None:
        self.loopt = True
        self.k_start.setText("Stop")
        self.k_start.setObjectName("gevaar")
        self.k_start.style().unpolish(self.k_start)
        self.k_start.style().polish(self.k_start)
        self.tabel.setRowCount(0)
        self._getoond = 0
        self.l_uitslag.setText("")
        self.rapport_pad = None
        self.k_rapport.setEnabled(False)

    def toon(self, sp: Startproef) -> None:
        t = self.thema
        self.l_status.setText(sp.status(time.time()))
        kleur = {"goed": t.goed, "dood": t.gevaar, "lus": t.gevaar, "half": t.stroom, "?": t.inkt_zacht}
        while self._getoond < len(sp.rijen):
            r = sp.rijen[self._getoond]
            self._getoond += 1
            rij = self.tabel.rowCount()
            self.tabel.insertRow(rij)
            cellen = [str(r.nr), r.oordeel, "-" if r.poort_s is None else f"{r.poort_s:g} s".replace(".", ",")]
            cellen += [("-" if r.i.get(m) is None else f"{r.i[m] * 1000:.0f} mA") for m in sp.momenten]
            cellen.append(r.keuring)
            for c, tekst in enumerate(cellen):
                it = QTableWidgetItem(tekst)
                if c == 1:
                    it.setForeground(QColor(kleur.get(r.oordeel, t.inkt)))
                if 2 <= c <= 5:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabel.setItem(rij, c, it)
            self.tabel.scrollToBottom()

    def klaar(self, sp: Startproef, rapport: Path | None) -> None:
        self.loopt = False
        self.toon(sp)
        self.k_start.setText("Start")
        self.k_start.setObjectName("primair")
        self.k_start.style().unpolish(self.k_start)
        self.k_start.style().polish(self.k_start)
        t = self.thema
        kleur = {"goed": t.goed, "letop": t.stroom, "fout": t.gevaar}.get(sp.oordeel, t.inkt)
        self.l_uitslag.setText(f'<span style="color:{kleur}">{sp.tekst}</span>')
        self.l_status.setText("")
        self.rapport_pad = rapport
        self.k_rapport.setEnabled(rapport is not None)
