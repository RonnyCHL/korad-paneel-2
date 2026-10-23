"""Het venster Accu nabootsen: van … V naar … V in … minuten, met inwendige weerstand R."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QLabel, QLineEdit, QVBoxLayout

from .eenvoudig import getal, nl


class AccuDialoog(QDialog):
    def __init__(self, vmax: float, v_nu: float | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Accu nabootsen")
        self.vmax = vmax
        self.uitkomst: tuple[float, float, float, float] | None = None
        root = QVBoxLayout(self)
        uitleg = QLabel(f"De spanning loopt lineair van de beginspanning naar de eindspanning, en zakt daarbij mee met "
                        f"de stroom door de inwendige weerstand (bron min stroom × R), zoals een echte accu onder "
                        f"belasting. Grens: {nl(vmax, 1)} V.")
        uitleg.setObjectName("zacht")
        uitleg.setWordWrap(True)
        root.addWidget(uitleg)
        rooster = QGridLayout()
        rooster.setHorizontalSpacing(12)
        self.velden = {}
        v0 = min(vmax, 13.8) if vmax >= 13.8 else vmax
        v1 = min(vmax, 11.0) if vmax >= 11.0 else round(vmax * 0.8, 1)
        for r, (sleutel, label, waarde, eenheid) in enumerate((
                ("v0", "Van", nl(v_nu if v_nu is not None and v_nu > 0 else v0, 2), "V"),
                ("v1", "Naar", nl(v1, 2), "V"), ("min", "In", "10", "minuten"), ("r", "Inwendige weerstand", "0", "mΩ"))):
            l = QLabel(label)
            l.setObjectName("zacht")
            e = QLineEdit(waarde)
            e.setFixedWidth(110)
            rooster.addWidget(l, r, 0)
            rooster.addWidget(e, r, 1)
            rooster.addWidget(QLabel(eenheid), r, 2)
            self.velden[sleutel] = e
        root.addLayout(rooster)
        self.l_fout = QLabel("")
        self.l_fout.setStyleSheet("color: #FF6B6B")
        root.addWidget(self.l_fout)
        knoppen = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoppen.button(QDialogButtonBox.Ok).setText("Start")
        knoppen.button(QDialogButtonBox.Cancel).setText("Annuleren")
        knoppen.accepted.connect(self._ok)
        knoppen.rejected.connect(self.reject)
        root.addWidget(knoppen)

    def _ok(self) -> None:
        try:
            v0, v1, minuten = (getal(self.velden[k].text()) for k in ("v0", "v1", "min"))
            r = getal(self.velden["r"].text() or "0")
        except ValueError:
            self.l_fout.setText("Vul getallen in, bijvoorbeeld 13,8 en 11,0 en 10, en 0 voor de weerstand.")
            return
        if not (0 <= v0 <= self.vmax and 0 <= v1 <= self.vmax and minuten > 0 and 0 <= r <= 1000):
            self.l_fout.setText(f"Spanningen 0 tot {nl(self.vmax, 1)} V (grens), tijd groter dan 0 minuten, "
                                "weerstand 0 tot 1000 mΩ.")
            return
        self.uitkomst = (v0, v1, minuten * 60, r / 1000)
        self.accept()
