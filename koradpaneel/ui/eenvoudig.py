"""Indeling Eenvoudig: drie grote ringmeters, de statuslampjes, instellen, uitgang en de geheugenknoppen."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton, QVBoxLayout,
                               QWidget)

from ..kern.geschiedenis import Meting
from ..voeding.basis import Stand
from .meters import RingMeter
from .thema import Thema


def nl(x: float, d: int) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def getal(tekst: str) -> float:
    return float(tekst.replace(",", ".").strip())


class Lampje(QLabel):
    """Een statuslampje met een woord: nooit alleen kleur."""

    def __init__(self, thema: Thema, tekst: str):
        super().__init__()
        self.thema, self.tekst, self.aan_kleur = thema, tekst, thema.goed
        self.setObjectName("chip")
        self.zet(False)

    def zet(self, aan: bool, kleur: str | None = None) -> None:
        t = self.thema
        k = kleur or self.aan_kleur
        bol = k if aan else t.uit
        inkt = t.inkt if aan else t.inkt_zacht
        self.setText(f'<span style="color:{bol}">●</span>&nbsp; <span style="color:{inkt}">{self.tekst}</span>')


def geheugenknop(tekst: str, n: int, ophalen: Signal, bewaren: Signal) -> QPushButton:
    """Een geheugenknop: klik = ophalen (RCL), rechtsklik = de huidige instelling hier bewaren (SAV)."""
    k = QPushButton(tekst)
    k.setObjectName("geheugen")
    k.setToolTip(f"Geheugen M{n}: klik = ophalen, rechtsklik = huidige instelling hier bewaren")
    k.clicked.connect(lambda _=False: ophalen.emit(n))
    k.setContextMenuPolicy(Qt.CustomContextMenu)

    def menu(pos):
        m = QMenu(k)
        m.addAction(f"Huidige instelling bewaren in M{n}", lambda: bewaren.emit(n))
        m.exec(k.mapToGlobal(pos))

    k.customContextMenuRequested.connect(menu)
    return k


class Eenvoudig(QWidget):
    instellen = Signal(float, float)      # spanning, stroomgrens
    uitgang = Signal(bool)                # gewenste stand
    geheugen = Signal(int)
    geheugen_bewaren = Signal(int)

    def __init__(self, thema: Thema, vmax: float, imax: float, geheugens: dict):
        super().__init__()
        self.thema = thema
        self.uitgang_aan = False
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(24)

        rij = QHBoxLayout()
        rij.setSpacing(28)
        self.m_v = RingMeter(thema, "Spanning", "V", "spanning", 2, vmax)
        self.m_i = RingMeter(thema, "Stroom", "A", "stroom", 3, imax)
        self.m_w = RingMeter(thema, "Vermogen", "W", "vermogen", 2, round(vmax * imax * 1.05, 1))
        for m in (self.m_v, self.m_i, self.m_w):
            kaart = QFrame()
            kaart.setObjectName("kaart")
            lay = QVBoxLayout(kaart)
            lay.setContentsMargins(14, 12, 14, 12)
            lay.addWidget(m)
            rij.addWidget(kaart, 1)
        root.addLayout(rij, 1)

        lampjes = QHBoxLayout()
        lampjes.setSpacing(12)
        lampjes.addStretch(1)
        self.l_cv = Lampje(thema, "CV · vaste spanning")
        self.l_cc = Lampje(thema, "CC · stroom begrensd")
        self.l_cc.aan_kleur = thema.stroom
        self.l_uit = Lampje(thema, "uitgang aan")
        self.l_bew = Lampje(thema, "bewaking uit")
        for l in (self.l_cv, self.l_cc, self.l_uit, self.l_bew):
            lampjes.addWidget(l)
        lampjes.addStretch(1)
        root.addLayout(lampjes)

        bed = QHBoxLayout()
        bed.setSpacing(12)
        bed.addStretch(1)
        lv = QLabel("Spanning")
        lv.setObjectName("zacht")
        self.v_veld = QLineEdit("5,00")
        self.v_veld.setFixedWidth(104)
        self.v_veld.setAlignment(Qt.AlignRight)
        lv.setBuddy(self.v_veld)
        li = QLabel("Stroomgrens")
        li.setObjectName("zacht")
        self.i_veld = QLineEdit("1,000")
        self.i_veld.setFixedWidth(114)
        self.i_veld.setAlignment(Qt.AlignRight)
        li.setBuddy(self.i_veld)
        self.k_instellen = QPushButton("Instellen")
        self.k_instellen.setObjectName("primair")
        self.k_uitgang = QPushButton("Uitgang aanzetten")
        self.k_uitgang.setObjectName("primair")
        for w in (lv, self.v_veld, QLabel("V"), li, self.i_veld, QLabel("A"), self.k_instellen, self.k_uitgang):
            if isinstance(w, QLabel) and w.text() in ("V", "A"):
                w.setObjectName("zacht")
            bed.addWidget(w)
        bed.addSpacing(10)
        self.k_geheugen: list[QPushButton] = []
        for n in range(1, 5):
            k = geheugenknop(geheugens.get(str(n), f"M{n}"), n, self.geheugen, self.geheugen_bewaren)
            bed.addWidget(k)
            self.k_geheugen.append(k)
        bed.addStretch(1)
        root.addLayout(bed)

        self.k_instellen.clicked.connect(self._instellen)
        self.v_veld.returnPressed.connect(self._instellen)
        self.i_veld.returnPressed.connect(self._instellen)
        self.k_uitgang.clicked.connect(lambda: self.uitgang.emit(not self.uitgang_aan))

    # ---- in
    def _instellen(self) -> None:
        try:
            v, i = getal(self.v_veld.text()), getal(self.i_veld.text())
        except ValueError:
            return
        self.instellen.emit(v, i)

    # ---- uit
    def toon_meting(self, m: Meting) -> None:
        self.m_v.zet(m.v)
        self.m_i.zet(m.i)
        self.m_w.zet(m.w)

    def toon_stand(self, s: Stand) -> None:
        self.uitgang_aan = s.uitgang
        self.l_uit.zet(s.uitgang)
        self.l_cv.zet(s.uitgang and not s.cc)
        self.l_cc.zet(s.uitgang and s.cc)
        self.k_uitgang.setText("Uitgang uit" if s.uitgang else "Uitgang aanzetten")
        self.k_uitgang.setObjectName("gevaar" if s.uitgang else "primair")
        self.k_uitgang.style().unpolish(self.k_uitgang)
        self.k_uitgang.style().polish(self.k_uitgang)

    def toon_instellingen(self, v: float, i: float) -> None:
        self.m_v.zet(self.m_v.waarde, merk=v, ondertekst=f"ingesteld {nl(v, 2)} V")
        self.m_i.zet(self.m_i.waarde, merk=i, ondertekst=f"grens {nl(i, 3)} A")
        self.m_w.zet(self.m_w.waarde, ondertekst=f"maximaal {nl(v * i, 1)} W")
        if not self.v_veld.hasFocus():
            self.v_veld.setText(nl(v, 2))
        if not self.i_veld.hasFocus():
            self.i_veld.setText(nl(i, 3))

    def toon_energie(self, mah: float, sinds: str) -> None:
        self.m_w.zet(self.m_w.waarde, ondertekst=f"energie {nl(mah, 1)} mAh sinds {sinds}")

    def zet_grens(self, vmax: float, imax: float) -> None:
        self.m_v.zet_maximum(vmax)
        self.m_i.zet_maximum(imax)
        self.m_w.zet_maximum(round(vmax * imax * 1.05, 1))
