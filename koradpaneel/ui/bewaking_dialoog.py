"""Het venster Bewaking instellen: drie regels, elk met aan/uit, wat, boven/onder, waarde, duur en actie."""

from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGridLayout, QLabel, QLineEdit,
                               QVBoxLayout)

from ..kern.bewaking import ACTIES, EENHEID, Bewaking, Regel
from .eenvoudig import getal, nl


class BewakingDialoog(QDialog):
    def __init__(self, bewaking: Bewaking, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bewaking instellen")
        self.bewaking = bewaking
        root = QVBoxLayout(self)
        uitleg = QLabel("Een regel gaat af als de meting de hele duur ononderbroken over de grens is, en daarna pas "
                        "opnieuw nadat hij er weer onder (of boven) is geweest.")
        uitleg.setObjectName("zacht")
        uitleg.setWordWrap(True)
        root.addWidget(uitleg)
        rooster = QGridLayout()
        rooster.setHorizontalSpacing(10)
        for c, kop in enumerate(("aan", "wat", "richting", "waarde", "", "duur (s)", "actie")):
            l = QLabel(kop)
            l.setObjectName("kopje")
            rooster.addWidget(l, 0, c)
        self.rijen = []
        for r, regel in enumerate(bewaking.regels, 1):
            aan = QCheckBox()
            aan.setChecked(regel.aan)
            wat = QComboBox()
            wat.addItems(list(EENHEID))
            wat.setCurrentText(regel.wat)
            richting = QComboBox()
            richting.addItems(["boven", "onder"])
            richting.setCurrentText(regel.richting)
            waarde = QLineEdit(nl(regel.waarde, 3).rstrip("0").rstrip(","))
            waarde.setFixedWidth(90)
            eenheid = QLabel(EENHEID[regel.wat])
            eenheid.setObjectName("zacht")
            wat.currentTextChanged.connect(lambda t, e=eenheid: e.setText(EENHEID[t]))
            duur = QLineEdit(nl(regel.duur, 1).rstrip("0").rstrip(","))
            duur.setFixedWidth(70)
            actie = QComboBox()
            actie.addItems(list(ACTIES))
            actie.setCurrentText(regel.actie)
            for c, w in enumerate((aan, wat, richting, waarde, eenheid, duur, actie)):
                rooster.addWidget(w, r, c)
            self.rijen.append((aan, wat, richting, waarde, duur, actie))
        root.addLayout(rooster)
        knoppen = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoppen.button(QDialogButtonBox.Ok).setText("Bewaren")
        knoppen.button(QDialogButtonBox.Cancel).setText("Annuleren")
        knoppen.accepted.connect(self._bewaren)
        knoppen.rejected.connect(self.reject)
        root.addWidget(knoppen)

    def _bewaren(self) -> None:
        regels = []
        for aan, wat, richting, waarde, duur, actie in self.rijen:
            try:
                regels.append(Regel(aan.isChecked(), wat.currentText(), richting.currentText(),
                                    getal(waarde.text()), max(0.0, getal(duur.text())), actie.currentText()))
            except ValueError:
                waarde.setFocus()
                return
        self.bewaking.regels = regels
        self.bewaking.bewaar()
        self.accept()
