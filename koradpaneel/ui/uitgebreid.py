"""Indeling Uitgebreid: kleine meters, status en verbruik bovenin, de grafiek groot, en onderin bediening,
de lopende proef en bewaking met notities."""

from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from ..kern.geschiedenis import Energieteller, Geschiedenis, Meting
from ..voeding.basis import Stand
from .eenvoudig import Lampje, getal, nl
from .grafiek import Grafiek
from .meters import RingMeter
from .thema import Thema


def kaart(titel: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    k = QFrame()
    k.setObjectName("kaart")
    lay = QVBoxLayout(k)
    lay.setContentsMargins(16, 12, 16, 12)
    lay.setSpacing(8)
    if titel:
        l = QLabel(titel.upper())
        l.setObjectName("kopje")
        lay.addWidget(l)
    return k, lay


class Uitgebreid(QWidget):
    instellen = Signal(float, float)
    uitgang = Signal(bool)
    geheugen = Signal(int)
    markering = Signal(str)
    log = Signal(bool)                 # log starten/stoppen
    bewaking_instellen = Signal()
    rapport = Signal(float, float)     # van, tot (het zichtbare venster)

    def __init__(self, thema: Thema, vmax: float, imax: float, geheugens: dict, geschiedenis: Geschiedenis):
        super().__init__()
        self.thema = thema
        self.uitgang_aan = False
        self.log_loopt = False
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(14)

        # ---- bovenste rij
        boven = QGridLayout()
        boven.setSpacing(14)
        self.m_v = RingMeter(thema, "Spanning", "V", "spanning", 2, vmax)
        self.m_i = RingMeter(thema, "Stroom", "A", "stroom", 3, imax)
        self.m_w = RingMeter(thema, "Vermogen", "W", "vermogen", 2, round(vmax * imax * 1.05, 1))
        for n, m in enumerate((self.m_v, self.m_i, self.m_w)):
            m.setMinimumSize(150, 160)
            k = QFrame()
            k.setObjectName("kaart")
            lay = QVBoxLayout(k)
            lay.setContentsMargins(8, 6, 8, 6)
            lay.addWidget(m)
            boven.addWidget(k, 0, n)
        k_status, ls = kaart("Status")
        self.l_cv = Lampje(thema, "CV · vaste spanning")
        self.l_cc = Lampje(thema, "CC · stroom begrensd")
        self.l_cc.aan_kleur = thema.stroom
        self.l_uit = Lampje(thema, "uitgang aan")
        self.l_bew = Lampje(thema, "bewaking uit")
        self.l_proef = Lampje(thema, "geen proef")
        self.l_proef.aan_kleur = thema.accent
        for l in (self.l_cv, self.l_cc, self.l_uit, self.l_bew, self.l_proef):
            l.setObjectName("zacht")
            ls.addWidget(l)
        ls.addStretch(1)
        boven.addWidget(k_status, 0, 3)
        k_verbruik, lv = kaart("Verbruik sinds --:--")
        self.l_verbruik_kop = k_verbruik.findChild(QLabel)
        self.l_mah = QLabel("0,0 mAh")
        self.l_mah.setObjectName("cijfer")
        self.l_mah.setStyleSheet(f"font-size: 28px; font-weight: 600; color: {thema.stroom}")
        self.l_wh = QLabel("0,000 Wh · 00:00:00")
        self.l_wh.setObjectName("zacht")
        self.l_beeld = QLabel("")
        self.l_beeld.setObjectName("zacht")
        self.l_beeld.setWordWrap(True)
        self.k_nul = QPushButton("Op nul")
        self.k_nul.setObjectName("geheugen")
        for w in (self.l_mah, self.l_wh, self.l_beeld):
            lv.addWidget(w)
        lv.addStretch(1)
        lv.addWidget(self.k_nul, 0, Qt.AlignLeft)
        boven.addWidget(k_verbruik, 0, 4)
        for c in range(5):
            boven.setColumnStretch(c, 1)
        root.addLayout(boven)

        # ---- grafiek
        k_graf, lg = kaart()
        kop = QHBoxLayout()
        t = QLabel("Spanning en stroom")
        t.setStyleSheet("font-weight: 600")
        kop.addWidget(t)
        legenda = QLabel(f'<span style="color:{thema.spanning}">━</span> spanning &nbsp; '
                         f'<span style="color:{thema.stroom}">━</span> stroom')
        legenda.setObjectName("zacht")
        kop.addWidget(legenda)
        self.l_cursor = QLabel("")
        self.l_cursor.setObjectName("cijfer")
        kop.addSpacing(16)
        kop.addWidget(self.l_cursor)
        kop.addStretch(1)
        self.k_venster: dict[int, QPushButton] = {}
        for sec, naam in ((60, "1 min"), (300, "5 min"), (1800, "30 min")):
            k = QPushButton(naam)
            k.setObjectName("geheugen")
            k.clicked.connect(lambda _=False, s=sec: self._venster(s))
            kop.addWidget(k)
            self.k_venster[sec] = k
        self.k_rapport = QPushButton("Rapport")
        self.k_rapport.setObjectName("geheugen")
        self.k_rapport.clicked.connect(self._rapport)
        kop.addWidget(self.k_rapport)
        lg.addLayout(kop)
        self.grafiek = Grafiek(thema, geschiedenis)
        self.grafiek.zet_bereik(vmax, imax)
        self.grafiek.cursor.connect(self._cursor)
        lg.addWidget(self.grafiek, 1)
        root.addWidget(k_graf, 1)

        # ---- onderste rij
        onder = QGridLayout()
        onder.setSpacing(14)
        k_bed, lb = kaart("Bediening")
        rij = QHBoxLayout()
        lv1 = QLabel("Spanning")
        lv1.setObjectName("zacht")
        self.v_veld = QLineEdit("5,00")
        self.v_veld.setFixedWidth(92)
        self.v_veld.setAlignment(Qt.AlignRight)
        li1 = QLabel("Grens")
        li1.setObjectName("zacht")
        self.i_veld = QLineEdit("1,000")
        self.i_veld.setFixedWidth(102)
        self.i_veld.setAlignment(Qt.AlignRight)
        self.k_instellen = QPushButton("Instellen")
        self.k_instellen.setObjectName("primair")
        self.k_uitgang = QPushButton("Uitgang aanzetten")
        self.k_uitgang.setObjectName("primair")
        for w in (lv1, self.v_veld, li1, self.i_veld, self.k_instellen, self.k_uitgang):
            rij.addWidget(w)
        rij.addStretch(1)
        lb.addLayout(rij)
        geh = QHBoxLayout()
        self.k_geheugen = []
        for n in range(1, 5):
            k = QPushButton(geheugens.get(str(n), f"M{n}"))
            k.setObjectName("geheugen")
            k.clicked.connect(lambda _=False, n=n: self.geheugen.emit(n))
            geh.addWidget(k)
            self.k_geheugen.append(k)
        geh.addStretch(1)
        lb.addLayout(geh)
        lb.addStretch(1)
        onder.addWidget(k_bed, 0, 0)

        k_proef, lp = kaart("Lopende proef")
        self.l_proef_naam = QLabel("geen proef")
        self.l_proef_naam.setStyleSheet("font-weight: 600; font-size: 15px")
        self.balk = QProgressBar()
        self.balk.setTextVisible(False)
        self.balk.setFixedHeight(8)
        self.balk.setStyleSheet(f"QProgressBar {{ background: {thema.spoor}; border: 0; border-radius: 4px; }}"
                                f"QProgressBar::chunk {{ background: {thema.accent}; border-radius: 4px; }}")
        self.l_proef_tekst = QLabel("Kies een programma via het menu Proeven.")
        self.l_proef_tekst.setObjectName("zacht")
        self.l_proef_tekst.setWordWrap(True)
        for w in (self.l_proef_naam, self.balk, self.l_proef_tekst):
            lp.addWidget(w)
        lp.addStretch(1)
        self.k_proef_stop = QPushButton("Stop")
        self.k_proef_stop.setObjectName("geheugen")
        self.k_proef_stop.setEnabled(False)
        lp.addWidget(self.k_proef_stop, 0, Qt.AlignLeft)
        onder.addWidget(k_proef, 0, 1)

        k_bew, lw = kaart("Bewaking en notitie")
        self.l_bewaking = QLabel("Geen bewakingsregels.")
        self.l_bewaking.setObjectName("zacht")
        self.l_bewaking.setWordWrap(True)
        lw.addWidget(self.l_bewaking)
        nr = QHBoxLayout()
        self.notitie = QLineEdit()
        self.notitie.setPlaceholderText("Notitie als markering…")
        self.notitie.setStyleSheet("font-family: inherit; font-size: 13px; padding: 8px 10px")
        self.k_markeer = QPushButton("Plaatsen")
        self.k_markeer.setObjectName("geheugen")
        nr.addWidget(self.notitie, 1)
        nr.addWidget(self.k_markeer)
        lw.addLayout(nr)
        kn = QHBoxLayout()
        self.k_log = QPushButton("Log starten")
        self.k_log.setObjectName("geheugen")
        self.k_bewaking = QPushButton("Bewaking instellen")
        self.k_bewaking.setObjectName("geheugen")
        self.k_bewaking.clicked.connect(self.bewaking_instellen.emit)
        kn.addWidget(self.k_log)
        kn.addWidget(self.k_bewaking)
        kn.addStretch(1)
        lw.addStretch(1)
        lw.addLayout(kn)
        onder.addWidget(k_bew, 0, 2)
        for c in range(3):
            onder.setColumnStretch(c, 1)
        root.addLayout(onder)

        self.k_instellen.clicked.connect(self._instellen)
        self.v_veld.returnPressed.connect(self._instellen)
        self.i_veld.returnPressed.connect(self._instellen)
        self.k_uitgang.clicked.connect(lambda: self.uitgang.emit(not self.uitgang_aan))
        self.k_markeer.clicked.connect(self._markeer)
        self.notitie.returnPressed.connect(self._markeer)
        self.k_log.clicked.connect(lambda: self.log.emit(not self.log_loopt))
        self._venster(300)

    # ---- in
    def _instellen(self) -> None:
        try:
            v, i = getal(self.v_veld.text()), getal(self.i_veld.text())
        except ValueError:
            return
        self.instellen.emit(v, i)

    def _markeer(self) -> None:
        tekst = self.notitie.text().strip() or f"markering {len(self.grafiek.markers) + 1}"
        self.notitie.clear()
        self.markering.emit(tekst)

    def _rapport(self) -> None:
        x0, x1 = self.grafiek.boven.getViewBox().viewRange()[0]
        self.rapport.emit(x0, x1)

    def toon_proef(self, naam: str, voortgang: float, tekst: str, loopt: bool) -> None:
        self.l_proef_naam.setText(naam)
        self.balk.setValue(int(voortgang * 100))
        self.l_proef_tekst.setText(tekst)
        self.k_proef_stop.setEnabled(loopt)
        self.l_proef.tekst = ("proef loopt · " + naam) if loopt else "geen proef"
        self.l_proef.zet(loopt)

    def toon_bewaking(self, regels, actief: bool) -> None:
        aan = [r.tekst() for r in regels if r.aan]
        self.l_bewaking.setText(" · ".join(aan) if aan else "Geen bewakingsregels aan.")
        self.l_bew.tekst = "bewaking aan" if actief else "bewaking uit"
        self.l_bew.zet(actief)

    def _venster(self, sec: int) -> None:
        for s, k in self.k_venster.items():
            k.setObjectName("primair" if s == sec else "geheugen")
            k.style().unpolish(k)
            k.style().polish(k)
        self.grafiek.zet_venster(sec)

    def _cursor(self, t: float) -> None:
        if t < 0:
            self.l_cursor.setText("")
            return
        pts = self.grafiek.geschiedenis.tussen(t - 1, t + 1)
        if pts:
            p = min(pts, key=lambda p: abs(p.t - t))
            self.l_cursor.setText(f"{datetime.fromtimestamp(p.t):%H:%M:%S} · {nl(p.v, 2)} V · {nl(p.i, 3)} A")

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

    def toon_energie(self, e: Energieteller, beeld) -> None:
        if e.sinds:
            self.l_verbruik_kop.setText(f"VERBRUIK SINDS {datetime.fromtimestamp(e.sinds):%H:%M}")
        self.l_mah.setText(f"{nl(e.mah, 1)} mAh")
        d = int(e.duur)
        self.l_wh.setText(f"{nl(e.wh, 3)} Wh · {d // 3600:02d}:{d % 3600 // 60:02d}:{d % 60:02d}")
        if beeld:
            self.l_beeld.setText(f"in beeld: hoogste {nl(beeld.i_max * 1000, 0)} mA, gemiddeld "
                                 f"{nl(beeld.i_gem * 1000, 0)} mA, laagste {nl(beeld.i_min * 1000, 0)} mA")

    def toon_log(self, loopt: bool, naam: str = "") -> None:
        self.log_loopt = loopt
        self.k_log.setText("Log stoppen" if loopt else "Log starten")

    def zet_grens(self, vmax: float, imax: float) -> None:
        self.m_v.zet_maximum(vmax)
        self.m_i.zet_maximum(imax)
        self.m_w.zet_maximum(round(vmax * imax * 1.05, 1))
        self.grafiek.zet_bereik(vmax, imax)

    def ververs(self) -> None:
        self.grafiek.ververs()
