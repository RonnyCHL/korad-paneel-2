"""Het venster Testprogramma's: de lijst, de omschrijving, de voorbeeldgrafiek van het verloop, en Start."""

from __future__ import annotations

from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QVBoxLayout)

from ..kern import programma as pr
from .eenvoudig import nl
from .thema import Thema


class ProgrammaVenster(QDialog):
    start = Signal(object)         # Programma

    def __init__(self, thema: Thema, grens_v: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Testprogramma's")
        self.thema = thema
        self.grens_v = grens_v
        self.resize(980, 620)
        root = QHBoxLayout(self)
        root.setSpacing(16)
        links = QVBoxLayout()
        kop = QLabel("PROGRAMMA'S")
        kop.setObjectName("kopje")
        links.addWidget(kop)
        self.lijst = QListWidget()
        self.lijst.setStyleSheet(f"QListWidget {{ background: {thema.kaart}; border: 1px solid {thema.kaart_rand}; "
                                 f"border-radius: 10px; padding: 6px; }} QListWidget::item {{ padding: 8px; }}"
                                 f"QListWidget::item:selected {{ background: {thema.accent}; color: white; border-radius: 6px; }}")
        self.lijst.setMinimumWidth(320)
        links.addWidget(self.lijst, 1)
        self.k_openen = QPushButton("Ander bestand…")
        self.k_openen.setObjectName("geheugen")
        links.addWidget(self.k_openen, 0, Qt.AlignLeft)
        root.addLayout(links)

        rechts = QVBoxLayout()
        self.l_naam = QLabel("")
        self.l_naam.setStyleSheet("font-size: 18px; font-weight: 600")
        self.l_om = QLabel("")
        self.l_om.setObjectName("zacht")
        self.l_om.setWordWrap(True)
        self.l_feiten = QLabel("")
        self.l_feiten.setObjectName("zacht")
        rechts.addWidget(self.l_naam)
        rechts.addWidget(self.l_om)
        rechts.addWidget(self.l_feiten)
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setBackground(thema.kaart)
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.plot.getAxis("left").setLabel("V")
        self.plot.getAxis("bottom").setLabel("s")
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.lijn = self.plot.plot([], [], pen=pg.mkPen(thema.spanning, width=2))
        self.grens = pg.InfiniteLine(angle=0, pos=grens_v, pen=pg.mkPen(thema.gevaar, width=1, style=Qt.DashLine),
                                     label=f"grens {nl(grens_v, 1)} V", labelOpts={"position": 0.05, "color": thema.inkt_zacht})
        self.plot.addItem(self.grens)
        rechts.addWidget(self.plot, 1)
        self.l_stappen = QLabel("")
        self.l_stappen.setObjectName("zacht")
        self.l_stappen.setWordWrap(True)
        rechts.addWidget(self.l_stappen)
        knoppen = QHBoxLayout()
        knoppen.addStretch(1)
        self.k_start = QPushButton("Start")
        self.k_start.setObjectName("primair")
        self.k_sluit = QPushButton("Sluiten")
        knoppen.addWidget(self.k_sluit)
        knoppen.addWidget(self.k_start)
        rechts.addLayout(knoppen)
        root.addLayout(rechts, 1)

        self.programmas: dict[str, pr.Programma] = {}
        self.lijst.currentItemChanged.connect(lambda cur, _prev: self._toon(cur))
        self.k_start.clicked.connect(self._start)
        self.k_sluit.clicked.connect(self.reject)
        self.k_openen.clicked.connect(self._ander)
        self.vul()

    def vul(self) -> None:
        self.lijst.clear()
        for pad in pr.lijst():
            try:
                p = pr.Programma.laad(pad)
            except (OSError, ValueError) as e:
                it = QListWidgetItem(f"{pad.stem}  (onleesbaar: {e})")
                it.setFlags(Qt.NoItemFlags)
                self.lijst.addItem(it)
                continue
            self.programmas[pad.stem] = p
            it = QListWidgetItem(pad.stem)
            it.setData(Qt.UserRole, pad.stem)
            self.lijst.addItem(it)
        if self.lijst.count():
            self.lijst.setCurrentRow(0)

    def _ander(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        pad, _ = QFileDialog.getOpenFileName(self, "Programma openen", str(pr.MAP), "JSON (*.json)")
        if not pad:
            return
        try:
            p = pr.Programma.laad(Path(pad))
        except (OSError, ValueError) as e:
            self.l_om.setText(f"Onleesbaar: {e}")
            return
        stam = Path(pad).stem
        self.programmas[stam] = p
        it = QListWidgetItem(stam)
        it.setData(Qt.UserRole, stam)
        self.lijst.addItem(it)
        self.lijst.setCurrentItem(it)

    def huidig(self) -> pr.Programma | None:
        it = self.lijst.currentItem()
        return self.programmas.get(it.data(Qt.UserRole)) if it else None

    def _toon(self, it) -> None:
        p = self.programmas.get(it.data(Qt.UserRole)) if it else None
        if p is None:
            return
        self.l_naam.setText(p.naam)
        self.l_om.setText(p.omschrijving)
        d = int(p.duur)
        self.l_feiten.setText(f"{len(p.stappen)} stappen · {p.herhalen}x · duur {d // 60} min {d % 60} s · "
                              f"{'uitgang uit na afloop' if p.uit_na_afloop else 'uitgang blijft zoals hij is'}"
                              + (f" · {sum(1 for s in p.stappen if s.verwacht)} verwachtingen" if any(s.verwacht for s in p.stappen) else ""))
        v = p.verloop()
        self.lijn.setData([x[0] for x in v], [x[1] for x in v])
        self.plot.setYRange(0, max(self.grens_v, max((x[1] for x in v), default=1.0)) * 1.1, padding=0)
        regels = []
        for n, s in enumerate(p.stappen[:12], 1):
            regels.append(f"{n}. {'uit' if not s.aan else ('helling naar ' if s.overgang == 'helling' else '') + nl(s.v, 2) + ' V'}"
                          f", grens {nl(s.i, 3)} A, {s.duur:g} s"
                          + (f" (verwacht {s.verwacht.i_min:g}–{s.verwacht.i_max if s.verwacht.i_max is not None else '…'} mA na {s.verwacht.na:g} s)"
                             if s.verwacht and (s.verwacht.i_min is not None or s.verwacht.i_max is not None) else ""))
        if len(p.stappen) > 12:
            regels.append(f"… en nog {len(p.stappen) - 12} stappen")
        self.l_stappen.setText("\n".join(regels))

    def _start(self) -> None:
        p = self.huidig()
        if p is not None:
            self.start.emit(p)
            self.accept()
