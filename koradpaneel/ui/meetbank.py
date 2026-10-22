"""Indeling Meetbank: de grafiek groot, met de meetcursors A en B en direct de getallen van het stuk ertussen."""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..kern.geschiedenis import Geschiedenis, Meting, venster_uit
from ..voeding.basis import Stand
from .eenvoudig import nl
from .grafiek import Grafiek
from .thema import Thema
from .uitgebreid import kaart


class Tegel(QFrame):
    """Een klein vakje met een label en een getal, zoals in het ontwerp."""

    def __init__(self, thema: Thema, label: str, kleur: str):
        super().__init__()
        self.setStyleSheet(f"QFrame {{ background: {thema.grond}; border-radius: 10px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        l = QLabel(label)
        l.setObjectName("zacht")
        l.setStyleSheet("font-size: 11px")
        self.w = QLabel("–")
        self.w.setObjectName("cijfer")
        self.w.setStyleSheet(f"font-size: 19px; font-weight: 600; color: {kleur}")
        lay.addWidget(l)
        lay.addWidget(self.w)

    def zet(self, tekst: str) -> None:
        self.w.setText(tekst)


class Meetbank(QWidget):
    uitgang = Signal(bool)

    def __init__(self, thema: Thema, vmax: float, imax: float, geschiedenis: Geschiedenis):
        super().__init__()
        self.thema = thema
        self.geschiedenis = geschiedenis
        self.uitgang_aan = False
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(14)

        k_graf, lg = kaart()
        kop = QHBoxLayout()
        self.l_titel = QLabel("Live")
        self.l_titel.setStyleSheet("font-weight: 600")
        kop.addWidget(self.l_titel)
        uitleg = QLabel("slepen = zoomen · dubbelklik = live · A en B zijn de meetcursors")
        uitleg.setObjectName("zacht")
        uitleg.setStyleSheet("font-size: 12px")
        kop.addWidget(uitleg)
        kop.addStretch(1)
        self.k_live = QPushButton("Live")
        self.k_cursors = QPushButton("Cursors")
        self.k_export = QPushButton("Exporteer selectie")
        self.k_rapport = QPushButton("Rapport van dit stuk")
        self.k_rapport.setEnabled(False)
        for k in (self.k_live, self.k_cursors, self.k_export, self.k_rapport):
            k.setObjectName("geheugen")
            kop.addWidget(k)
        lg.addLayout(kop)
        self.grafiek = Grafiek(thema, geschiedenis)
        self.grafiek.zet_bereik(vmax, imax)
        self.grafiek.cursors_veranderd.connect(self._ab)
        lg.addWidget(self.grafiek, 1)
        root.addWidget(k_graf, 3)

        zij = QVBoxLayout()
        zij.setSpacing(14)
        k_ab, lab = kaart("Tussen A en B")
        self.l_ab = QLabel("zet de cursors aan")
        self.l_ab.setObjectName("zacht")
        lab.addWidget(self.l_ab)
        rooster = QGridLayout()
        rooster.setSpacing(10)
        self.t = {
            "i_max": Tegel(thema, "stroom hoogste", thema.stroom), "i_gem": Tegel(thema, "stroom gemiddeld", thema.stroom),
            "i_min": Tegel(thema, "stroom laagste", thema.stroom), "v_gem": Tegel(thema, "spanning gemiddeld", thema.spanning),
            "mah": Tegel(thema, "lading", thema.inkt), "wh": Tegel(thema, "energie", thema.vermogen),
        }
        for n, k in enumerate(self.t.values()):
            rooster.addWidget(k, n // 2, n % 2)
        lab.addLayout(rooster)
        zij.addWidget(k_ab)

        k_cur, lc = kaart("Op cursor A")
        self.l_a = QLabel("–")
        self.l_a.setObjectName("cijfer")
        lc.addWidget(self.l_a)
        kb = QLabel("OP CURSOR B")
        kb.setObjectName("kopje")
        lc.addWidget(kb)
        self.l_b = QLabel("–")
        self.l_b.setObjectName("cijfer")
        lc.addWidget(self.l_b)
        zij.addWidget(k_cur)

        k_mark, lm = kaart("Markeringen in beeld")
        self.l_markers = QLabel("geen")
        self.l_markers.setObjectName("zacht")
        self.l_markers.setWordWrap(True)
        lm.addWidget(self.l_markers)
        zij.addWidget(k_mark)
        zij.addStretch(1)
        root.addLayout(zij, 1)

        self.k_live.clicked.connect(self.grafiek.naar_live)
        self.k_cursors.clicked.connect(self._cursors)
        self.k_export.clicked.connect(self._export)

    # ---- cursors
    def _cursors(self) -> None:
        aan = not self.grafiek.cursors_aan
        self.grafiek.zet_cursors(aan)
        self.k_cursors.setObjectName("primair" if aan else "geheugen")
        self.k_cursors.style().unpolish(self.k_cursors)
        self.k_cursors.style().polish(self.k_cursors)
        if not aan:
            self.l_ab.setText("zet de cursors aan")

    def _dichtst(self, t: float) -> Meting | None:
        pts = self.geschiedenis.tussen(t - 1, t + 1)
        return min(pts, key=lambda p: abs(p.t - t)) if pts else None

    def _ab(self, a: float, b: float) -> None:
        a, b = min(a, b), max(a, b)
        w = self.geschiedenis.venster(a, b)
        self.l_ab.setText(f"{datetime.fromtimestamp(a):%H:%M:%S} tot {datetime.fromtimestamp(b):%H:%M:%S} · "
                          f"{nl(b - a, 1)} s" + (f" · {w.n} metingen" if w else " · geen metingen"))
        if w:
            self.t["i_max"].zet(f"{nl(w.i_max * 1000, 0)} mA")
            self.t["i_gem"].zet(f"{nl(w.i_gem * 1000, 0)} mA")
            self.t["i_min"].zet(f"{nl(w.i_min * 1000, 0)} mA")
            self.t["v_gem"].zet(f"{nl(w.v_gem, 2)} V")
            self.t["mah"].zet(f"{nl(w.mah, 2)} mAh")
            self.t["wh"].zet(f"{nl(w.wh * 1000, 1)} mWh")
        for t, lab in ((a, self.l_a), (b, self.l_b)):
            m = self._dichtst(t)
            lab.setText(f"{datetime.fromtimestamp(m.t):%H:%M:%S} · {nl(m.v, 2)} V · {nl(m.i, 3)} A · {nl(m.w, 2)} W"
                        if m else "geen meting")
        in_beeld = [f"{datetime.fromtimestamp(t):%H:%M:%S}  {tekst}" for t, tekst in self.grafiek.markers if a - 60 <= t <= b + 60]
        self.l_markers.setText("\n".join(in_beeld[-8:]) if in_beeld else "geen")

    def _export(self) -> None:
        if not self.grafiek.cursors_aan:
            return
        a, b = self.grafiek.ab()
        pts = self.geschiedenis.tussen(a, b)
        if not pts:
            return
        naam = f"selectie_{datetime.fromtimestamp(a):%Y%m%d_%H%M%S}.csv"
        pad, _ = QFileDialog.getSaveFileName(self, "Selectie opslaan", naam, "CSV (*.csv)")
        if not pad:
            return
        with open(pad, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["tijd", "unix", "volt", "ampere", "watt"])
            for p in pts:
                w.writerow([datetime.fromtimestamp(p.t).isoformat(timespec="milliseconds"), f"{p.t:.3f}",
                            f"{p.v:.3f}", f"{p.i:.4f}", f"{p.w:.4f}"])

    # ---- uit
    def toon_meting(self, m: Meting) -> None:
        pass

    def toon_stand(self, s: Stand) -> None:
        self.uitgang_aan = s.uitgang

    def toon_instellingen(self, v: float, i: float) -> None:
        pass

    def zet_grens(self, vmax: float, imax: float) -> None:
        self.grafiek.zet_bereik(vmax, imax)

    def ververs(self) -> None:
        self.grafiek.ververs()
        if self.grafiek.cursors_aan and self.grafiek.live:
            pass
