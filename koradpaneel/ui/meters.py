"""De ringmeter uit het ontwerp: een boog van 270 graden met de waarde in het midden en een merkteken voor de
ingestelde waarde. Geschilderd met QPainter, dus scherp op elke schaal."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen


def _font(families: str, punten: int, gewicht=QFont.Normal) -> QFont:
    """Een lettertype uit een lijst families ('Inter, Segoe UI, ...'): Qt pakt de eerste die er is."""
    f = QFont()
    f.setFamilies([x.strip().strip("'\"") for x in families.split(",")])
    f.setPointSize(punten)
    f.setWeight(gewicht)
    return f
from PySide6.QtWidgets import QSizePolicy, QWidget

from .thema import Thema


class RingMeter(QWidget):
    def __init__(self, thema: Thema, titel: str, eenheid: str, kleur_attr: str, decimalen: int = 2,
                 maximum: float = 10.0, parent=None):
        super().__init__(parent)
        self.thema = thema
        self.titel = titel
        self.eenheid = eenheid
        self.kleur_attr = kleur_attr
        self.decimalen = decimalen
        self.maximum = maximum
        self.waarde = 0.0
        self.merk: float | None = None          # ingestelde waarde
        self.ondertekst = ""
        self.setMinimumSize(220, 230)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def zet(self, waarde: float, merk: float | None = None, ondertekst: str | None = None) -> None:
        self.waarde = waarde
        if merk is not None:
            self.merk = merk
        if ondertekst is not None:
            self.ondertekst = ondertekst
        self.update()

    def zet_thema(self, thema: Thema) -> None:
        self.thema = thema
        self.update()

    def zet_maximum(self, maximum: float) -> None:
        self.maximum = max(maximum, 1e-6)
        self.update()

    @staticmethod
    def _nl(x: float, d: int) -> str:
        return f"{x:.{d}f}".replace(".", ",")

    def paintEvent(self, _ev):
        t = self.thema
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QColor(t.inkt_zacht))
        p.setFont(_font(t.letters, 10, QFont.DemiBold))
        p.drawText(QRectF(8, 4, w - 16, 20), Qt.AlignLeft | Qt.AlignVCenter, self.titel.upper())

        # de ring: 270 graden met de opening onderaan, in het midden van de kaart
        dik = max(10, int(min(w, h) * 0.06))
        r = min(w - 60, h - 110) / 2
        cx, cy = w / 2, 30 + (h - 60) / 2
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        pen = QPen(QColor(t.spoor), dik, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 225 * 16, -270 * 16)
        frac = max(0.0, min(1.0, self.waarde / self.maximum))
        if frac > 0:
            pen.setColor(QColor(getattr(t, self.kleur_attr)))
            p.setPen(pen)
            p.drawArc(rect, 225 * 16, int(-270 * 16 * frac))
        if self.merk is not None and 0 <= self.merk <= self.maximum:
            # merkteken: een streepje op de ring bij de ingestelde waarde
            import math
            hoek = math.radians(225 - 270 * (self.merk / self.maximum))
            x1, y1 = cx + (r + dik * 0.9) * math.cos(hoek), cy - (r + dik * 0.9) * math.sin(hoek)
            x2, y2 = cx + (r + dik * 1.6) * math.cos(hoek), cy - (r + dik * 1.6) * math.sin(hoek)
            p.setPen(QPen(QColor(t.inkt), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(int(x1), int(y1), int(x2), int(y2))

        # de getallen
        p.setPen(QColor(t.inkt))
        tekst = self._nl(self.waarde, self.decimalen)
        p.setFont(_font(t.cijfers, max(16, int(r * (0.36 if len(tekst) <= 4 else 0.3))), QFont.DemiBold))
        p.drawText(QRectF(cx - r, cy - r * 0.45, 2 * r, r * 0.7), Qt.AlignCenter, tekst)
        p.setPen(QColor(t.inkt_zacht))
        p.setFont(_font(t.letters, max(10, int(r * 0.14))))
        p.drawText(QRectF(cx - r, cy + r * 0.22, 2 * r, r * 0.3), Qt.AlignCenter, self.eenheid)
        p.setPen(QColor(t.inkt_vaag))
        p.setFont(_font(t.letters, 9))
        p.drawText(QRectF(cx - r - 10, cy + r * 0.72, r * 0.8, 20), Qt.AlignLeft | Qt.AlignVCenter, "0")
        p.drawText(QRectF(cx + r * 0.3, cy + r * 0.72, r * 0.8, 20), Qt.AlignRight | Qt.AlignVCenter,
                   self._nl(self.maximum, 1).rstrip("0").rstrip(","))
        if self.ondertekst:
            p.setPen(QColor(t.inkt_zacht))
            p.setFont(_font(t.letters, 10))
            p.drawText(QRectF(8, h - 26, w - 16, 22), Qt.AlignCenter, self.ondertekst)
        p.end()
