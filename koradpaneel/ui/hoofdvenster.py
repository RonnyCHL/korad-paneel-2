"""Het hoofdvenster: kopbalk met menu en project, de gekozen indeling in het midden, voetbalk met de toetsen.

Veiligheid zit HIER en niet in de indelingen: elke opdracht naar de voeding gaat door `_zet()` dat de grens van
het project toepast, en elke uitlezing door `_op_instellingen()` dat ingrijpt als de voeding aan de voorkant hoger
staat dan de grens terwijl de uitgang aan is. Esc is in elk venster de noodstop.
"""

from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import VERSIE
from ..kern import grenzen, instellingen
from ..kern.geschiedenis import Energieteller, Geschiedenis, Meting
from ..kern.logboek import CsvLog
from ..voeding import poorten
from ..voeding.basis import Stand, Voeding
from ..werker import Werker
from .eenvoudig import Eenvoudig, nl
from .thema import THEMAS, qss
from .uitgebreid import Uitgebreid

INDELINGEN = [("eenvoudig", "Eenvoudig"), ("uitgebreid", "Uitgebreid"), ("meetbank", "Meetbank"),
              ("presentatie", "Presentatie")]


class Hoofdvenster(QMainWindow):
    def __init__(self, maak_voeding, inst: dict | None = None):
        """`maak_voeding(poort) -> Voeding`: de fabriek, zodat het venster niet weet of het de Korad of de
        nagebootste voeding is."""
        super().__init__()
        self.maak_voeding = maak_voeding
        self.inst = inst if inst is not None else instellingen.laad()
        self.project = grenzen.project(self.inst["project"])
        self.thema = THEMAS.get(self.inst["thema"], THEMAS["donker"])
        self.werker: Werker | None = None
        self.voeding: Voeding | None = None
        self.geschiedenis = Geschiedenis()
        self.energie = Energieteller()
        self.log = CsvLog()
        self.v_set = self.i_set = None
        self.uitgang = False
        self.laatste_grens_t = 0.0
        self._bouw()
        self.verbind()

    # ---------------------------------------------------------------- opbouw
    def _bouw(self) -> None:
        self.setWindowTitle(f"Korad paneel {VERSIE}")
        self.setStyleSheet(qss(self.thema))
        grond = QWidget()
        grond.setObjectName("grond")
        self.setCentralWidget(grond)
        root = QVBoxLayout(grond)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        kop = QWidget()
        kop.setObjectName("kop")
        kl = QHBoxLayout(kop)
        kl.setContentsMargins(24, 10, 24, 10)
        kl.setSpacing(14)
        titel = QLabel("KORAD")
        titel.setObjectName("titel")
        self.l_apparaat = QLabel("niet verbonden")
        self.l_apparaat.setObjectName("zacht")
        kl.addWidget(titel)
        kl.addWidget(self.l_apparaat)
        kl.addSpacing(12)
        self.menu = self.menuBar()
        self.menu.setNativeMenuBar(False)
        kl.addWidget(self.menu)
        kl.addStretch(1)
        lp = QLabel("Project")
        lp.setObjectName("zacht")
        self.c_project = QComboBox()
        for p in grenzen.PROJECTEN.values():
            self.c_project.addItem(p.titel, p.sleutel)
        self.c_project.setCurrentIndex(list(grenzen.PROJECTEN).index(self.project.sleutel))
        self.c_project.currentIndexChanged.connect(self._project_gekozen)
        self.l_verbinding = QLabel()
        self.k_verbinden = QPushButton("Verbinden")
        self.k_verbinden.clicked.connect(self._verbinden_knop)
        for w in (lp, self.c_project, self.l_verbinding, self.k_verbinden):
            kl.addWidget(w)
        root.addWidget(kop)

        self.stapel = QStackedWidget()
        self.eenvoudig = Eenvoudig(self.thema, self.project.vmax, self.project.imax, self.inst["geheugens"])
        self.eenvoudig.instellen.connect(self._zet)
        self.eenvoudig.uitgang.connect(self._uitgang)
        self.eenvoudig.geheugen.connect(self._geheugen)
        self.stapel.addWidget(self.eenvoudig)
        self.uitgebreid = Uitgebreid(self.thema, self.project.vmax, self.project.imax, self.inst["geheugens"],
                                     self.geschiedenis)
        self.uitgebreid.instellen.connect(self._zet)
        self.uitgebreid.uitgang.connect(self._uitgang)
        self.uitgebreid.geheugen.connect(self._geheugen)
        self.uitgebreid.markering.connect(self.markeer)
        self.uitgebreid.log.connect(self._log)
        self.uitgebreid.k_nul.clicked.connect(lambda: self.energie.op_nul(time.time()))
        self.stapel.addWidget(self.uitgebreid)
        self.indelingen = [self.eenvoudig, self.uitgebreid]
        for sleutel, naam in INDELINGEN[2:]:
            w = QLabel(f"{naam}: komt in stap 2b")
            w.setObjectName("zacht")
            w.setAlignment(Qt.AlignCenter)
            self.stapel.addWidget(w)
        root.addWidget(self.stapel, 1)
        self.tikker = QTimer(self)                    # de grafiek en de vensterstatistiek, 4x per seconde
        self.tikker.timeout.connect(self._tik)
        self.tikker.start(250)

        voet = QWidget()
        voet.setObjectName("voet")
        vl = QHBoxLayout(voet)
        vl.setContentsMargins(24, 8, 24, 8)
        for tekst in ("Esc = noodstop", "spatie = uitgang", "Ctrl+K = zoeken"):
            l = QLabel(tekst)
            l.setObjectName("zacht")
            vl.addWidget(l)
            vl.addSpacing(10)
        vl.addStretch(1)
        self.l_voet = QLabel("")
        self.l_voet.setObjectName("zacht")
        vl.addWidget(self.l_voet)
        root.addWidget(voet)

        self._menus()
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.noodstop)
        QShortcut(QKeySequence(Qt.Key_Space), self, lambda: self._uitgang(not self.uitgang))
        self.resize(1440, 900)
        self._toon_verbinding(False)
        self._kies_indeling(self.inst["indeling"].get(self.project.sleutel, "eenvoudig"))

    def _menus(self) -> None:
        m = self.menu.addMenu("Bestand")
        m.addAction("Verbinden…", self._verbinden_knop)
        m.addAction("Afsluiten", self.close)
        b = self.menu.addMenu("Beeld")
        self.a_indeling = {}
        for n, (sleutel, naam) in enumerate(INDELINGEN, 1):
            a = QAction(naam, self, checkable=True)
            a.setShortcut(QKeySequence(f"F{n}"))
            a.triggered.connect(lambda _=False, s=sleutel: self._kies_indeling(s))
            b.addAction(a)
            self.a_indeling[sleutel] = a
        b.addSeparator()
        for sleutel, naam in (("donker", "Thema donker"), ("licht", "Thema licht")):
            b.addAction(naam, lambda s=sleutel: self._kies_thema(s))
        self.menu.addMenu("Proeven").addAction("komt in stap 3").setEnabled(False)
        self.menu.addMenu("Logboek").addAction("komt in stap 2").setEnabled(False)
        self.menu.addMenu("Gereedschap").addAction("komt in stap 3").setEnabled(False)
        self.menu.addMenu("Instellingen").addAction("komt in stap 4").setEnabled(False)

    # ---------------------------------------------------------------- verbinding
    def verbind(self) -> None:
        poort = self.inst.get("poort") or poorten.korad_poort() or ""
        try:
            self.voeding = self.maak_voeding(poort)
        except Exception as e:  # noqa: BLE001
            self._toon_verbinding(False, str(e))
            return
        self.werker = Werker(self.voeding)
        self.werker.verbonden.connect(self._op_verbonden)
        self.werker.verbroken.connect(self._op_verbroken)
        self.werker.meting.connect(self._op_meting)
        self.werker.stand.connect(self._op_stand)
        self.werker.instellingen.connect(self._op_instellingen)
        self.werker.opdracht_fout.connect(lambda t: self.l_voet.setText(f"fout: {t}"))
        self.werker.start()

    def _verbinden_knop(self) -> None:
        if self.werker is not None:
            self.werker.stop()
            self.werker = None
            self._toon_verbinding(False)
        else:
            self.verbind()

    def _toon_verbinding(self, aan: bool, tekst: str = "") -> None:
        t = self.thema
        bol = t.goed if aan else t.uit
        self.l_verbinding.setText(f'<span style="color:{bol}">●</span>&nbsp; {"verbonden" if aan else (tekst or "niet verbonden")}')
        self.k_verbinden.setText("Verbreken" if aan else "Verbinden")

    def _op_verbonden(self, idn: str) -> None:
        self.l_apparaat.setText(idn or self.voeding.naam)
        self._toon_verbinding(True)
        self.energie.op_nul(time.time())

    def _op_verbroken(self, reden: str) -> None:
        self._toon_verbinding(False, reden[:60])
        self.werker = None

    # ---------------------------------------------------------------- uitlezing
    def _op_meting(self, m: Meting) -> None:
        self.geschiedenis.voeg(m)
        self.energie.tel(m)
        self.log.schrijf(m)
        for w in self.indelingen:
            w.toon_meting(m)
        if self.energie.sinds:
            self.eenvoudig.toon_energie(self.energie.mah, datetime.fromtimestamp(self.energie.sinds).strftime("%H:%M"))

    def _op_stand(self, s: Stand) -> None:
        self.uitgang = s.uitgang
        for w in self.indelingen:
            w.toon_stand(s)

    def _tik(self) -> None:
        if self.stapel.currentWidget() is self.uitgebreid:
            self.uitgebreid.ververs()
            nu = time.time()
            self.uitgebreid.toon_energie(self.energie, self.geschiedenis.venster(nu - self.uitgebreid.grafiek.venster_s, nu))

    def markeer(self, tekst: str) -> None:
        t = time.time()
        self.uitgebreid.grafiek.markeer(t, tekst)
        self.log.markeer(t, tekst)
        self.l_voet.setText(f"markering {datetime.fromtimestamp(t):%H:%M:%S}: {tekst}")

    def _log(self, aan: bool) -> None:
        if aan:
            pad = self.log.start()
            self.l_voet.setText(f"log: {pad.name}")
        else:
            pad = self.log.stop()
            self.l_voet.setText(f"log gesloten: {pad.name if pad else ''} ({self.log.regels} metingen)")
        self.uitgebreid.toon_log(aan)

    def _op_instellingen(self, v: float, i: float) -> None:
        self.v_set, self.i_set = v, i
        for w in self.indelingen:
            w.toon_instellingen(v, i)
        # De voeding kan aan de voorkant hoger gezet zijn dan de grens: dan grijpt het paneel in.
        if self.uitgang and v > self.project.vmax + 0.005 and time.time() - self.laatste_grens_t > 3:
            self.laatste_grens_t = time.time()
            self._stuur(self.voeding.zet_uitgang, False)
            QMessageBox.warning(self, "Boven de grens",
                                f"De voeding staat op {nl(v, 2)} V, boven de grens van {nl(self.project.vmax, 1)} V "
                                f"(draaiknop of geheugenknop op de voeding?). De uitgang is uitgezet.\n\n"
                                + self.project.uitleg())
        if i > self.project.imax + 0.0005 and time.time() - self.laatste_grens_t > 3:
            self.laatste_grens_t = time.time()
            self._stuur(self.voeding.zet_stroomgrens, self.project.imax)

    # ---------------------------------------------------------------- opdrachten
    def _stuur(self, fn, *args) -> bool:
        if self.werker is None:
            QMessageBox.information(self, "Niet verbonden", "Verbind eerst met de voeding.")
            return False
        self.werker.opdracht(fn, *args)
        return True

    def _zet(self, v: float, i: float) -> None:
        if not self.project.binnen(v, i):
            QMessageBox.warning(self, "Buiten de grens", f"{nl(v, 2)} V / {nl(i, 3)} A past niet.\n\n" + self.project.uitleg())
            return
        if self.uitgang and self.v_set is not None and v > self.v_set + 0.05:
            if QMessageBox.question(self, "Hogere spanning op de uitgang",
                                    f"De uitgang staat aan. De spanning gaat van {nl(self.v_set, 2)} V naar "
                                    f"{nl(v, 2)} V, direct op wat er nu is aangesloten.\n\nDoorgaan?") != QMessageBox.Yes:
                return
        if self._stuur(self.voeding.zet_stroomgrens, i):       # eerst de stroomgrens, dan de spanning
            self._stuur(self.voeding.zet_spanning, v)

    def _uitgang(self, aan: bool) -> None:
        self._stuur(self.voeding.zet_uitgang, aan)

    def _geheugen(self, n: int) -> None:
        self._stuur(self.voeding.geheugen_ophalen, n)

    def noodstop(self) -> None:
        if self.werker is not None:
            self.werker.opdracht(self.voeding.zet_uitgang, False)
        self.l_voet.setText(f"NOODSTOP {datetime.now():%H:%M:%S}: uitgang uit")

    # ---------------------------------------------------------------- keuzes
    def _project_gekozen(self, idx: int) -> None:
        self.project = grenzen.project(self.c_project.itemData(idx))
        self.inst["project"] = self.project.sleutel
        instellingen.bewaar(self.inst)
        for w in self.indelingen:
            w.zet_grens(self.project.vmax, self.project.imax)
        self._kies_indeling(self.inst["indeling"].get(self.project.sleutel, "eenvoudig"))

    def _kies_indeling(self, sleutel: str) -> None:
        sleutels = [s for s, _ in INDELINGEN]
        if sleutel not in sleutels:
            sleutel = "eenvoudig"
        self.stapel.setCurrentIndex(sleutels.index(sleutel))
        for s, a in self.a_indeling.items():
            a.setChecked(s == sleutel)
        self.inst["indeling"][self.project.sleutel] = sleutel
        instellingen.bewaar(self.inst)

    def _kies_thema(self, sleutel: str) -> None:
        self.thema = THEMAS[sleutel]
        self.inst["thema"] = sleutel
        instellingen.bewaar(self.inst)
        QMessageBox.information(self, "Thema", "Het thema wisselt bij de volgende start van het paneel.")

    # ---------------------------------------------------------------- sluiten
    def closeEvent(self, ev) -> None:
        if self.werker is not None and self.uitgang:
            keuze = QMessageBox.question(self, "Uitgang staat aan", "De uitgang staat nog aan. Uitzetten bij het sluiten?",
                                         QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if keuze == QMessageBox.Cancel:
                ev.ignore()
                return
            if keuze == QMessageBox.Yes:
                self.werker.opdracht(self.voeding.zet_uitgang, False)
                QApplication.processEvents()
                time.sleep(0.3)
        if self.werker is not None:
            self.werker.stop()
        self.log.stop()
        instellingen.bewaar(self.inst)
        ev.accept()
