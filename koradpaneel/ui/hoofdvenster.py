"""Het hoofdvenster: kopbalk met menu en project, de gekozen indeling in het midden, voetbalk met de toetsen.

Veiligheid zit HIER en niet in de indelingen: elke opdracht naar de voeding gaat door `_zet()` dat de grens van
het project toepast, en elke uitlezing door `_op_instellingen()` dat ingrijpt als de voeding aan de voorkant hoger
staat dan de grens terwijl de uitgang aan is. Esc is in elk venster de noodstop.
"""

from __future__ import annotations

import time
import webbrowser
from datetime import datetime

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QHBoxLayout, QInputDialog, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from .. import VERSIE
from ..kern import grenzen, instellingen
from ..kern.geschiedenis import Energieteller, Geschiedenis, Meting
from ..kern import rapport as rapport_mod
from ..kern import programma as pr
from ..kern import startproef as sp_mod
from ..kern import proeven as pv
from ..kern.accu import Accu
from ..apparaat.monitor import Monitor, MonitorBeeld
from ..kern.meldingen import Meldingen
from ..kern.telefoon import Telefoon
from ..kern.bewaking import Bewaking
from ..kern.werkboek import Werkboek
from ..apparaat.bordje import Bordje
from ..kern.logboek import CsvLog
from ..voeding import poorten
from ..voeding.basis import Stand, Voeding
from ..werker import Werker
from .bewaking_dialoog import BewakingDialoog
from .eenvoudig import Eenvoudig, nl
from .meetbank import Meetbank
from .mini import Mini
from .presentatie import Presentatie
from .programmas import ProgrammaVenster
from .startproef import StartproefVenster
from .accu_dialoog import AccuDialoog
from .logvenster import LogVenster, VergelijkVenster, kies_log, laad_log
from .werkboek_venster import WerkboekVenster
from .instellingen_dialoog import InstellingenDialoog
from .caravan import CaraVanVenster
from .onderdelen import OnderdelenVenster
from .zoek_dialoog import ZoekDialoog
from .thema import THEMAS, qss
from .uitgebreid import Uitgebreid

INDELINGEN = [("eenvoudig", "Eenvoudig"), ("uitgebreid", "Uitgebreid"), ("meetbank", "Meetbank"),
              ("presentatie", "Presentatie")]


class Rolinhoud(QWidget):
    """Een laag zonder layout tussen het rolgebied en de stapel indelingen.

    QScrollArea kijkt naar `widget()->layout()->hasHeightForWidth()`: de labels met regelafbreking in de indelingen
    geven die eigenschap door, en dan maakt het rolgebied de inhoud zo hoog als de *wenselijke* hoogte (de grafiek
    wil 960 px) in plaats van de minimale, met een rolbalk tot gevolg. Zonder layout valt het terug op de minimale
    maat, en pas daaronder komen er rolbalken. Gemeten op 23-10-2026 (1440x852 werkruimte)."""

    def __init__(self, kind: QWidget):
        super().__init__()
        self.kind = kind
        kind.setParent(self)

    def minimumSizeHint(self):  # noqa: N802
        return self.kind.minimumSizeHint()

    def sizeHint(self):  # noqa: N802
        return self.kind.sizeHint()

    def resizeEvent(self, ev) -> None:  # noqa: N802
        self.kind.setGeometry(self.rect())
        super().resizeEvent(ev)


class Hoofdvenster(QMainWindow):
    def __init__(self, maak_voeding, inst: dict | None = None, maak_bordje=None, maak_monitor=None):
        """`maak_voeding(poort) -> Voeding`: de fabriek, zodat het venster niet weet of het de Korad of de
        nagebootste voeding is. `maak_bordje(poort) -> Apparaat`: idem voor het bordje onder test."""
        super().__init__()
        self.maak_voeding = maak_voeding
        self.maak_bordje = maak_bordje or (lambda poort: Bordje(poort))
        self.maak_monitor = maak_monitor or (lambda adres: Monitor(adres))
        self.inst = inst if inst is not None else instellingen.laad()
        self.project = grenzen.project(self.inst["project"])
        self.thema = THEMAS.get(self.inst["thema"], THEMAS["donker"])
        self.werker: Werker | None = None
        self.voeding: Voeding | None = None
        self.geschiedenis = Geschiedenis()
        self.energie = Energieteller()
        self.log = CsvLog()
        self.bewaking = Bewaking()
        self.bewaking.laad()
        self.loop = None
        self.laatste_meting = None
        self.proef: pv.Proef | None = None          # de ene lopende proef (startproef, accu, curve, ...)
        self.apparaat = None                         # het bordje onder test (startproef)
        self._regels: list[str] = []
        self.sp_venster = None
        self.cv_venster = None
        self.od_venster = None
        self.monitor = None                          # de CaraVan Guard-monitor (apparaat)
        self.mon = MonitorBeeld()
        self.bouw = pv.Bouwstappen()
        self.laatste_rook: pv.Rooktest | None = None
        self.nacht_log = False
        self.werkboek = Werkboek()
        self.werkboek.laad()
        self.rcl_wacht: tuple[int, float] | None = None     # (geheugenplaats, tijdstip) na RCL/SAV
        self.vensters: list = []                               # open vensters (logs, werkboek) in leven houden
        self.v_set = self.i_set = None
        self.uitgang = False
        self.laatste_grens_t = 0.0
        self.laatste_stand: Stand | None = None
        self.apparaat_naam = ""
        self.markeringen: list[tuple[float, str]] = []
        self.cc_sinds: float | None = None
        self.cc_gepiept = False
        self.meldingen = Meldingen(self.inst)
        web = self.inst.setdefault("web", {})
        self.telefoon = Telefoon(web.get("poort") or 8085, web.get("code") or "")
        web["code"] = self.telefoon.code
        self._tel_t = 0.0
        self._bouw()
        QShortcut(QKeySequence(Qt.Key_Escape), self, self.noodstop)
        QShortcut(QKeySequence(Qt.Key_Space), self, lambda: self._uitgang(not self.uitgang))
        QShortcut(QKeySequence("Ctrl+K"), self, self._zoeken)
        if web.get("aan"):
            try:
                self.telefoon.start()
            except OSError as e:
                self.l_voet.setText(f"telefoon: webserver kon niet starten ({e})")
        self.verbind()

    # ---------------------------------------------------------------- opbouw
    def _bouw(self, eerste: bool = True) -> None:
        self.setWindowTitle(f"Korad paneel {VERSIE}")
        self.setStyleSheet(qss(self.thema))
        grond = QWidget()
        grond.setObjectName("grond")
        self.setCentralWidget(grond)
        root = QVBoxLayout(grond)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        kop = QWidget()
        self.kop = kop
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
        # Standaard is een menubalk MinimumExpanding: dan eist hij zijn volle wenselijke breedte (550 px) als minimum
        # en wordt het venster breder dan het scherm. Preferred laat hem krimpen.
        self.menu.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
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
        self.eenvoudig.geheugen_bewaren.connect(self._geheugen_bewaren)
        self.stapel.addWidget(self.eenvoudig)
        self.uitgebreid = Uitgebreid(self.thema, self.project.vmax, self.project.imax, self.inst["geheugens"],
                                     self.geschiedenis)
        self.uitgebreid.instellen.connect(self._zet)
        self.uitgebreid.uitgang.connect(self._uitgang)
        self.uitgebreid.geheugen.connect(self._geheugen)
        self.uitgebreid.geheugen_bewaren.connect(self._geheugen_bewaren)
        self.uitgebreid.markering.connect(self.markeer)
        self.uitgebreid.log.connect(self._log)
        self.uitgebreid.bewaking_instellen.connect(self._bewaking_dialoog)
        self.uitgebreid.rapport.connect(lambda a, b: self._rapport(a, b, "Grafiek in beeld"))
        self.uitgebreid.k_nul.clicked.connect(lambda: self.energie.op_nul(time.time()))
        self.uitgebreid.k_proef_stop.clicked.connect(self._stop_alles)
        self.uitgebreid.toon_bewaking(self.bewaking.regels, self.bewaking.actief)
        self.stapel.addWidget(self.uitgebreid)
        self.meetbank = Meetbank(self.thema, self.project.vmax, self.project.imax, self.geschiedenis)
        self.meetbank.rapport.connect(lambda a, b: self._rapport(a, b, "Tussen cursor A en B"))
        self.stapel.addWidget(self.meetbank)
        self.presentatie = Presentatie(self.thema, self.project.vmax, self.project.imax, self.project.titel)
        self.stapel.addWidget(self.presentatie)
        self.indelingen = [self.eenvoudig, self.uitgebreid, self.meetbank, self.presentatie]
        self.mini: Mini | None = None
        self.vorige_indeling = "eenvoudig"
        # De indelingen in een rolgebied: op een klein scherm komen er rolbalken in plaats van dat er iets
        # buiten beeld valt. Op een gewoon scherm zie je er niets van.
        self.rol = QScrollArea()
        self.rol.setWidgetResizable(True)
        self.rol.setFrameShape(QFrame.NoFrame)
        self.rol.setWidget(Rolinhoud(self.stapel))
        root.addWidget(self.rol, 1)
        self.tikker = QTimer(self)                    # de grafiek en de vensterstatistiek, 4x per seconde
        self.tikker.timeout.connect(self._tik)
        self.tikker.start(250)

        voet = QWidget()
        self.voet = voet
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
        if eerste:
            self._plaats_venster()
        self._toon_verbinding(False)
        self._toon_geheugens()
        self._kies_indeling(self.inst["indeling"].get(self.project.sleutel, "eenvoudig"))

    def _herbouw(self) -> None:
        """Alles opnieuw opbouwen in het (nieuwe) thema en de toestand terugzetten: thema wisselen zonder herstart."""
        if self.mini is not None:
            self.mini.close()
            self.mini = None
        self.sp_venster = None
        self.cv_venster = None
        self.od_venster = None
        self._bouw(eerste=False)
        self._toon_verbinding(self.werker is not None)
        if self.apparaat_naam:
            self.l_apparaat.setText(self.apparaat_naam if len(self.apparaat_naam) <= 34 else self.apparaat_naam[:33] + "…")
        if self.v_set is not None:
            for w in self.indelingen:
                w.toon_instellingen(self.v_set, self.i_set)
        if self.laatste_stand is not None:
            self._op_stand(self.laatste_stand)
        self.uitgebreid.toon_bewaking(self.bewaking.regels, self.bewaking.actief)
        self.eenvoudig.l_bew.tekst = "bewaking aan" if self.bewaking.actief else "bewaking uit"
        self.eenvoudig.l_bew.zet(self.bewaking.actief)
        self.uitgebreid.toon_log(self.log.loopt, self.log.pad.name if self.log.pad else "")
        self.a_log.setText("Log stoppen" if self.log.loopt else "Log starten")
        for t, tekst in self.markeringen:
            self.uitgebreid.grafiek.markeer(t, tekst)
            self.meetbank.grafiek.markeer(t, tekst)
        self._toon_proef()

    def _plaats_venster(self) -> None:
        """Passend op het scherm (de werkruimte zonder taakbalk), en zoals de vorige keer als dat nog past."""
        scherm = QGuiApplication.primaryScreen()
        werk = scherm.availableGeometry() if scherm is not None else QRect(0, 0, 1440, 852)
        g = self.inst.get("venster", {}).get("hoofd") or {}
        titelbalk = 40                                  # de Windows-titelbalk zit niet in geometry()
        b = max(900, min(int(g.get("b", 1400)), werk.width() - 16))
        h = max(560, min(int(g.get("h", 840)), werk.height() - titelbalk - 8))
        self.resize(b, h)
        x, y = g.get("x"), g.get("y")
        if x is None or y is None or not werk.contains(QRect(int(x), int(y), b, h + titelbalk)):
            x = werk.x() + (werk.width() - b) // 2
            y = werk.y() + max(0, (werk.height() - h - titelbalk) // 2)
        self.move(int(x), int(y))
        if g.get("max"):
            self.setWindowState(Qt.WindowMaximized)

    def _onthoud_venster(self) -> None:
        g = self.inst.setdefault("venster", {}).setdefault("hoofd", {})
        if self.isMaximized() or self.isFullScreen():
            g["max"] = self.isMaximized()
            return
        g.update({"x": self.pos().x(), "y": self.pos().y(), "b": self.width(), "h": self.height(), "max": False})

    def _menus(self) -> None:
        m = self.menu.addMenu("Bestand")
        m.addAction("Verbinden…", self._verbinden_knop)
        m.addAction("Zoeken…", self._zoeken).setShortcut(QKeySequence("Ctrl+K"))
        m.addSeparator()
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
        b.addAction("Mini-venster (altijd bovenop)", self._mini).setShortcut(QKeySequence("F5"))
        b.addSeparator()
        for sleutel, naam in (("donker", "Thema donker"), ("licht", "Thema licht")):
            b.addAction(naam, lambda s=sleutel: self._kies_thema(s))
        pm = self.menu.addMenu("Proeven")
        pm.addAction("Testprogramma's…", self._programmas).setShortcut(QKeySequence("Ctrl+P"))
        pm.addAction("Programma stoppen", lambda: self._stop_programma("Gestopt"))
        pm.addSeparator()
        pm.addAction("EMSN-auto: bordje starten…", self._startproef_venster).setShortcut(QKeySequence("Ctrl+B"))
        pm.addAction("CaraVan Guard…", self._caravan_venster).setShortcut(QKeySequence("Ctrl+G"))
        pm.addAction("Proef stoppen", lambda: self._stop_proef("Gestopt"))
        lm = self.menu.addMenu("Logboek")
        lm.addAction("Werkboek…", self._werkboek).setShortcut(QKeySequence("Ctrl+W"))
        lm.addSeparator()
        lm.addAction("Log openen…", self._log_openen).setShortcut(QKeySequence("Ctrl+O"))
        lm.addAction("Logs vergelijken…", self._logs_vergelijken)
        lm.addSeparator()
        self.a_log = lm.addAction("Log starten", lambda: self._log(not self.log.loopt))
        self.a_log.setShortcut(QKeySequence("Ctrl+L"))
        gm = self.menu.addMenu("Gereedschap")
        gm.addAction("Accu nabootsen…", self._accu_dialoog)
        gm.addAction("Onderdelentester…", self._onderdelen_venster)
        im = self.menu.addMenu("Instellingen")
        im.addAction("Instellingen…", self._instellingen_dialoog).setShortcut(QKeySequence("Ctrl+,"))
        im.addAction("Telefoon als afstandsbediening…", self._instellingen_dialoog)

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
        naam = (idn or self.voeding.naam).strip()
        self.apparaat_naam = naam
        self.l_apparaat.setToolTip(naam)
        self.l_apparaat.setText(naam if len(naam) <= 34 else naam[:33] + "…")   # de hele *IDN? past niet in de kop
        self._toon_verbinding(True)
        self.energie.op_nul(time.time())

    def _op_verbroken(self, reden: str) -> None:
        self._toon_verbinding(False, reden[:60])
        self.werker = None

    # ---------------------------------------------------------------- uitlezing
    def _op_meting(self, m: Meting) -> None:
        self.laatste_meting = m
        self.geschiedenis.voeg(m)
        self.energie.tel(m)
        self.log.schrijf(m)
        for g in self.bewaking.evalueer(m):
            self.markeer(g.tekst)
            if g.regel.actie == "uitgang uit":
                self._uitgang(False)
            self._alarm(g.tekst + (": uitgang uitgezet" if g.regel.actie == "uitgang uit" else ""))
        for w in self.indelingen:
            w.toon_meting(m)
        if self.mini is not None and self.mini.isVisible():
            self.mini.toon_meting(m)
        if self.energie.sinds:
            self.eenvoudig.toon_energie(self.energie.mah, datetime.fromtimestamp(self.energie.sinds).strftime("%H:%M"))

    def _op_stand(self, s: Stand) -> None:
        self.uitgang = s.uitgang
        self.laatste_stand = s
        if self.monitor is not None and hasattr(self.monitor, "voed"):
            self.monitor.voed(s.v_uit, s.i_uit, s.uitgang)
        nu = time.time()
        if s.uitgang and s.cc:                      # piep als het begrenzen langer dan een halve seconde duurt
            if self.cc_sinds is None:
                self.cc_sinds = nu
            elif nu - self.cc_sinds > 0.5 and not self.cc_gepiept:
                self.cc_gepiept = True
                self.meldingen.cc()
        else:
            self.cc_sinds, self.cc_gepiept = None, False
        for w in self.indelingen:
            w.toon_stand(s)
        if self.mini is not None and self.mini.isVisible():
            self.mini.toon_stand(s)

    # ---------------------------------------------------------------- testprogramma's
    def _programmas(self) -> None:
        d = ProgrammaVenster(self.thema, self.project.vmax, self)
        d.setStyleSheet(qss(self.thema))
        d.start.connect(self._start_programma)
        d.exec()

    def _start_programma(self, p: pr.Programma) -> None:
        if self.werker is None:
            QMessageBox.information(self, "Niet verbonden", "Verbind eerst met de voeding.")
            return
        self._stop_programma("Gestopt: nieuw programma")
        self.loop = pr.Loop(p, self.project.vmax, self.project.imax)
        self.markeer(f"programma: {p.naam}")
        self._voer_uit(self.loop.start(time.time()))
        self._toon_proef()

    def _voer_uit(self, ops: list) -> None:
        for o in ops:
            if o.i is not None:
                self._stuur(self.voeding.zet_stroomgrens, o.i)
            if o.v is not None:
                self._stuur(self.voeding.zet_spanning, o.v)
            if o.uit is not None:
                self._stuur(self.voeding.zet_uitgang, o.uit)
            if o.markering:
                self.markeer(o.markering)
            if o.apparaat and self.apparaat is not None:
                (self.apparaat.pauze if o.apparaat == "pauze" else self.apparaat.hervat)()
            if o.monitor is not None and self.monitor is not None:
                self.monitor.stuur(o.monitor)

    def _toon_proef(self) -> None:
        l = self.loop
        p = self.proef
        if p is not None:
            self.uitgebreid.toon_proef(p.naam, p.voortgang, p.status(time.time()), True)
            return
        if l is None:
            self.uitgebreid.toon_proef("geen proef", 0.0, "Kies een programma via het menu Proeven.", False)
            return
        s = l.stap
        g, f = l.samenvatting()
        rest = int(max(0.0, l.p.duur * (1 - l.voortgang)))
        delen = [f"stap {l.idx + 1} van {len(l.p.stappen)}"]
        if l.p.herhalen > 1:
            delen[0] += f", herhaling {l.herhaling} van {l.p.herhalen}"
        if s is not None:
            delen.append("uit" if not s.aan else nl(min(s.v, self.project.vmax), 2) + " V")
        delen.append(f"nog ongeveer {rest // 60} min {rest % 60} s")
        if g + f:
            delen.append(f"{g} goed, {f} fout")
        self.uitgebreid.toon_proef(l.p.naam, l.voortgang, " · ".join(delen), True)

    def _stop_alles(self) -> None:
        self._stop_programma("Gestopt")
        self._stop_proef("Gestopt")

    def _stop_programma(self, reden: str, rapport: bool = False) -> None:
        l, self.loop = self.loop, None
        if l is None:
            return
        g, f = l.samenvatting()
        uitslag = f"{reden}: {l.p.naam}" + (f" · {g} goed, {f} fout" if g + f else "")
        self.markeer(uitslag)
        if not l.klaar and l.p.uit_na_afloop:
            self._uitgang(False)
        self._toon_proef()
        if rapport:
            t1 = time.time()
            pts = self.geschiedenis.tussen(l.t_start, t1)
            markers = [(t, x) for t, x in self.uitgebreid.grafiek.markers if l.t_start <= t <= t1]
            regels = []
            for u in l.uitslagen:
                kop = f"stap {u.stap}" + (f" (herhaling {u.herhaling})" if l.p.herhalen > 1 else "")
                regels.append(f"{kop}: {u.tekst}")
            pagina = rapport_mod.maak(l.p.naam, pts, markers, apparaat=self.l_apparaat.text(), project=self.project.naam,
                                      v_set=self.v_set, i_set=self.i_set, oordeel=uitslag,
                                      oordeel_klasse="fout" if f else "goed", toelichting="\n".join(regels),
                                      soort="testprogramma")
            pad = rapport_mod.bewaar(pagina, "programma")
            self.werkboek.voeg("programma", uitslag, pad, "\n".join(regels))
            self.l_voet.setText(f"rapport: {pad.name}")
            self.meldingen.klaar("Programma klaar", f"{l.p.naam}: {g} goed, {f} fout" if g + f else l.p.naam)
            webbrowser.open(pad.resolve().as_uri())

    # ---------------------------------------------------------------- de lopende proef (algemeen)
    def _ctx(self) -> pv.Ctx:
        regels, self._regels = self._regels, []
        return pv.Ctx(t=time.time(), meting=self.laatste_meting, cc=bool(self.laatste_stand.cc) if self.laatste_stand else False,
                      uitgang=self.uitgang, v_set=self.v_set, i_set=self.i_set, geschiedenis=self.geschiedenis,
                      monitor=self.mon if self.monitor is not None else None, regels=regels,
                      vmax=self.project.vmax, imax=self.project.imax)

    def _start_proef(self, proef: pv.Proef, apparaat=None) -> bool:
        if self.werker is None:
            QMessageBox.information(self, "Niet verbonden", "Verbind eerst met de voeding.")
            return False
        self._stop_programma(f"Gestopt: {proef.naam.lower()} gestart")
        self._stop_proef(f"Gestopt: {proef.naam.lower()} gestart")
        self.proef = proef
        if apparaat is not None:
            self.apparaat = apparaat
            self.apparaat.regel.connect(lambda t, r: self._regels.append(r))
            self.apparaat.verbonden.connect(self._op_apparaat)
            self.apparaat.start()
        self._voer_uit(proef.start(time.time()))
        self._toon_proef()
        self._vensters_ververs()
        return True

    def _stop_proef(self, reden: str) -> None:
        if self.proef is None:
            return
        ctx = self._ctx()
        self._voer_uit(self.proef.stop(reden, ctx))
        self._proef_klaar(reden, ctx)

    def _proef_klaar(self, reden: str, ctx: pv.Ctx | None = None) -> None:
        p, self.proef = self.proef, None
        ap, self.apparaat = self.apparaat, None
        if ap is not None:
            ap.stop()
        if p is None:
            return
        ctx = ctx or self._ctx()
        tekst = p.afronden(reden, ctx)
        self.markeer(f"{p.naam.lower()}: {reden.lower()}" if reden != "Klaar" else f"{p.naam.lower()}: klaar")
        pad = None
        if p.rapport:
            pts = self.geschiedenis.tussen(p.t_start, p.t1)
            markers = [(t, x) for t, x in self.markeringen if p.t_start <= t <= p.t1]
            pagina = rapport_mod.maak(p.naam, pts, markers, apparaat=self.apparaat_naam, project=self.project.naam,
                                      v_set=self.v_set, i_set=self.i_set, oordeel=tekst, oordeel_klasse=p.oordeel,
                                      soort=p.soort, extra_html=p.tabel_html(ctx))
            pad = rapport_mod.bewaar(pagina, p.soort)
            self.l_voet.setText(f"rapport: {pad.name}")
        self.werkboek.voeg(p.soort, f"{p.naam}: {tekst}"[:160], pad, tekst)
        # bijzondere nazorg per soort
        if isinstance(p, pv.Opstartcurve) and p.label.startswith("bouwstap"):
            nr = int(p.label.split()[1])
            oordeel, uitleg = self.bouw.verwerk(nr, p, self.mon if self.monitor else None)
            self.markeer(f"bouwstap {nr}: {oordeel.upper()}, {pv.fmt_ma(p.i_end or 0)}")
            self.werkboek.voeg("bouwstap", f"Stap {nr}: {pv.BOUWSTAPPEN[nr]['titel']}: {oordeel}", None, uitleg)
            self.meldingen.zeg(f"Stap {nr}: {oordeel}. {pv.fmt_ma(p.i_end or 0)}.")
        elif isinstance(p, pv.Rooktest):
            self.laatste_rook = p
        elif isinstance(p, pv.Nachttest) and self.nacht_log:
            self.nacht_log = False
            self._log(False)
        elif isinstance(p, pv.Onderdeel):
            self.meldingen.zeg(p.kop)
        if reden == "Klaar":
            m = p.melding()
            if m:
                self.meldingen.klaar(*m)
            if not p.ok if isinstance(p, pv.Opstartcurve) else False:
                self.meldingen.piep("alarm")
        if self.sp_venster is not None and isinstance(p, sp_mod.Startproef):
            self.sp_venster.klaar(p, pad)
        if self.od_venster is not None and isinstance(p, pv.Onderdeel):
            self.od_venster.proef_klaar(p)
        if self.cv_venster is not None:
            self.cv_venster.proef_klaar(p, pad)
        self._toon_proef()
        if pad is not None:
            webbrowser.open(pad.resolve().as_uri())

    def _vensters_ververs(self) -> None:
        if self.cv_venster is not None and self.cv_venster.isVisible():
            self.cv_venster.ververs()
        if self.od_venster is not None and self.od_venster.isVisible():
            self.od_venster.ververs()
        if self.sp_venster is not None and isinstance(self.proef, sp_mod.Startproef):
            self.sp_venster.toon(self.proef)

    # ---------------------------------------------------------------- startproef (EMSN-auto-bordje)
    def _startproef_venster(self) -> None:
        if self.sp_venster is None:
            self.sp_venster = StartproefVenster(self.thema, self.inst.get("emsn", {}).get("poort") or "COM6", self)
            self.sp_venster.setStyleSheet(qss(self.thema))
            self.sp_venster.start.connect(self._start_startproef)
            self.sp_venster.stop.connect(lambda: self._stop_proef("Gestopt"))
        self.sp_venster.show()
        self.sp_venster.raise_()

    def _start_startproef(self, n: int, uit_s: float, aan_s: float, poort: str) -> None:
        if self.project.vmax < sp_mod.VOLT or self.project.imax < 1.0:
            QMessageBox.information(self, "Grens", 'Kies bovenin het project "EMSN-auto" (max 5,5 V, 2 A) of "Vrij".')
            return
        self.inst.setdefault("emsn", {})["poort"] = poort
        instellingen.bewaar(self.inst)
        sp = sp_mod.Startproef(n, uit_s, aan_s, volt=min(sp_mod.VOLT, self.project.vmax), amp=min(sp_mod.AMP, self.project.imax))
        if self._start_proef(sp, self.maak_bordje(poort)) and self.sp_venster is not None:
            self.sp_venster.begonnen()

    def _op_apparaat(self, open_: bool, tekst: str) -> None:
        if isinstance(self.proef, sp_mod.Startproef):
            self.proef.poort(time.time(), open_, tekst)
        self.l_voet.setText(f"bordje: {'poort open' if open_ else 'poort weg'} ({tekst})")

    # ---------------------------------------------------------------- CaraVan Guard: monitor en proeven
    def _caravan_venster(self) -> None:
        if self.cv_venster is None:
            d = CaraVanVenster(self.thema, self, self)
            d.setStyleSheet(qss(self.thema))
            d.koppel.connect(self._koppel_monitor)
            d.ontkoppel.connect(self._ontkoppel_monitor)
            d.start_curve.connect(self._start_curve)
            d.meet_stap.connect(self._meet_stap)
            d.uitvaltest.connect(self._uitvaltest)
            d.start_vcheck.connect(self._start_vcheck)
            d.start_ijken.connect(self._start_ijken)
            d.start_ups.connect(self._start_ups)
            d.start_rook.connect(self._start_rook)
            d.start_nacht.connect(self._start_nacht)
            d.rook_basis.connect(self._rook_basis)
            d.stop.connect(lambda: self._stop_proef("Gestopt"))
            self.cv_venster = d
            if self.monitor is None and self.inst.get("monitor", {}).get("aan") and self.inst["monitor"].get("adres"):
                self._koppel_monitor(self.inst["monitor"]["adres"])
        self.cv_venster.show()
        self.cv_venster.raise_()

    def _koppel_monitor(self, adres: str) -> None:
        self._ontkoppel_monitor()
        self.mon = MonitorBeeld(adres=adres)
        self.monitor = self.maak_monitor(adres)
        self.monitor.stand.connect(self._op_monitor_stand)
        self.monitor.fout.connect(lambda t, f: setattr(self.mon, "fout", f))
        self.monitor.gebeurtenis.connect(self._op_monitor_gebeurtenis)
        self.monitor.opdracht_klaar.connect(lambda ok, obj: None if ok else self.markeer(f"monitor: commando {obj.get('c')} niet aangekomen"))
        self.monitor.start()
        self.inst.setdefault("monitor", {}).update(adres=adres, aan=True)
        instellingen.bewaar(self.inst)
        self.markeer(f"monitor gekoppeld: {adres}")
        self._vensters_ververs()

    def _ontkoppel_monitor(self) -> None:
        if self.monitor is None:
            return
        self.monitor.stop()
        self.monitor = None
        self.inst.setdefault("monitor", {})["aan"] = False
        instellingen.bewaar(self.inst)
        self._vensters_ververs()

    def _op_monitor_stand(self, t: float, f: dict) -> None:
        m = self.mon.verwerk_stand(t, f)
        if m:
            self.markeer(m)

    def _op_monitor_gebeurtenis(self, t: float, tekst: str) -> None:
        self.mon.gebeurtenissen.append((t, tekst))
        del self.mon.gebeurtenissen[:-500]
        self.markeer(f"monitor: {tekst}")
        if self.loop is not None:
            self.loop.meld(tekst)

    def _monitor_nodig(self) -> bool:
        if not (self.monitor is not None and self.mon.vers()):
            QMessageBox.information(self, "Monitor nodig", "Koppel eerst de monitor (venster CaraVan Guard); hij moet antwoorden.")
            return False
        return True

    def _start_curve(self, v_end: float, i_lim: float, label: str = "opstartcurve", **kw) -> bool:
        if not (0.5 <= v_end <= self.project.vmax + 1e-6 and 0.001 <= i_lim <= self.project.imax + 1e-6):
            QMessageBox.warning(self, "Buiten de grens", self.project.uitleg())
            return False
        return self._start_proef(pv.Opstartcurve(v_end, i_lim, label=label, **kw))

    def _meet_stap(self, nr: int) -> None:
        s = pv.BOUWSTAPPEN[nr]
        if s["v"] is None or self.werker is None:
            return
        if QMessageBox.question(self, "Stap meten", f"Stap {nr}: {s['titel']}.\n\nDe uitgang gaat uit en daarna met een zachte "
                                f"start van 0 naar {nl(s['v'], 1)} V, met een stroomgrens van {pv.fmt_ma(s['i'])}. Dat duurt "
                                "ongeveer een kwart minuut.\n\nZit alleen wat bij deze stap hoort op de print?") != QMessageBox.Yes:
            return
        self._start_curve(s["v"], s["i"], label=f"bouwstap {nr}", stap_v=0.5, wacht=0.4, hold=4.0)

    def _uitvaltest(self) -> None:
        if self.werker is None or not self.uitgang:
            QMessageBox.information(self, "Uitgang staat uit", "Meet eerst deze stap; daarna staat de uitgang aan.")
            return
        if QMessageBox.question(self, "Uitvaltest", "De uitgang gaat 5 seconden uit en daarna weer aan. Meet in die 5 "
                                "seconden J23 'UPS' (hoort 5 V te blijven) en J23 '5V' (zakt weg).\n\nStarten?") == QMessageBox.Yes:
            self._start_proef(pv.Uitvaltest())

    def _start_vcheck(self) -> None:
        if self.werker is None or not self._monitor_nodig():
            return
        if not self.uitgang:
            QMessageBox.information(self, "Uitgang staat uit", "Zet de uitgang eerst aan, zodat de monitor op de voeding draait.")
            return
        p = pv.Spanningscontrole(self.project.vmax, self.v_set or 13.8)
        if QMessageBox.question(self, "Spanningsmeting controleren",
                                f"De spanning loopt van {nl(p.stappen[0], 1)} tot {nl(p.stappen[-1], 1)} V in {len(p.stappen)} "
                                f"stappen; per stap 4 s wachten en 3 s meten, samen ongeveer {pv.fmt_duur(p.duur)}. Daarna gaat "
                                f"de spanning terug naar {nl(p.v_terug, 1)} V.\n\nAlles wat aan de voeding hangt krijgt die "
                                "spanningen. Starten?") == QMessageBox.Yes:
            self._start_proef(p)

    def _start_ijken(self, cal_nu: float) -> None:
        if self.werker is None or not self._monitor_nodig():
            return
        if not self.mon.laatste.get("lt_ok"):
            QMessageBox.warning(self, "Geen ledsturing", "De monitor meldt geen PCA9685 (lt.ok is 0); de strips kunnen dan niet aan.")
            return
        if not self.uitgang:
            QMessageBox.information(self, "Uitgang staat uit", "Zet de uitgang eerst aan.")
            return
        if (self.i_set or 0) < 3.0:
            nieuw = min(4.0, self.project.imax)
            if QMessageBox.question(self, "Stroomgrens te laag", f"De stroomgrens staat op {nl(self.i_set or 0, 3)} A. Met drie "
                                    f"strips vol is meer nodig, anders gaat de voeding begrenzen.\n\nStroomgrens naar {nl(nieuw, 1)} A "
                                    "zetten?") != QMessageBox.Yes:
                return
            self._stuur(self.voeding.zet_stroomgrens, nieuw)
        if QMessageBox.question(self, "Stroommeting ijken", "De drie strips gaan samen naar 0, 25, 50, 75 en 100 %. Per stand 4 s "
                                "wachten en 5 s meten, samen ongeveer 50 s. Daarna gaan de strips uit.\n\nRaak het scherm en de "
                                "lichtknoppen zolang niet aan.\n\nStarten?") == QMessageBox.Yes:
            self._start_proef(pv.IJken(cal_nu))

    def _start_ups(self, terug_aan: bool) -> None:
        if self.werker is None or not self._monitor_nodig():
            return
        f = self.mon.laatste
        if not f.get("ups_ok") or f.get("ups_v") is None:
            QMessageBox.warning(self, "Geen UPS-cel", "De monitor meldt geen meting van de 18650 (bak.ok is 0). Zit de cel erin "
                                "en staat BACKUP_ADC_PRESENT op 1?")
            return
        if not self.uitgang:
            QMessageBox.information(self, "Uitgang staat uit", "Zet de uitgang eerst aan, zodat de monitor op de voeding draait en de cel vol is.")
            return
        pct = f" ({f['ups_pct']:.0f} %)" if f.get("ups_pct") is not None else ""
        if QMessageBox.question(self, "UPS-duurtest starten", f"De cel staat nu op {nl(f['ups_v'], 2)} V{pct}.\n\nDe uitgang gaat uit; "
                                "de monitor draait verder op de 18650. Het paneel volgt hem tot hij 30 s niet meer antwoordt. Dat kan "
                                "uren duren; laat het paneel zolang open." + ("\n\nDaarna gaat de uitgang weer aan, zodat je de "
                                "laadstroom ziet." if terug_aan else "") + "\n\nStarten?") == QMessageBox.Yes:
            self._start_proef(pv.UpsDuurtest(f["ups_v"], terug_aan))

    def _start_rook(self, fw: str, strips: bool, uitval: bool) -> None:
        if self.werker is None:
            QMessageBox.information(self, "Niet verbonden", "Verbind eerst met de voeding.")
            return
        if self.monitor is None:
            QMessageBox.information(self, "Monitor nodig", "Koppel eerst de monitor (tabblad Monitor).")
            return
        if not self.uitgang:
            QMessageBox.information(self, "Uitgang staat uit", "Zet eerst de print op de voeding: uitgang aan op 13,8 V, bijvoorbeeld met de opstartcurve.")
            return
        delen = ["firmware, modules en metingen"] + (["strip 1 kort op 20 %"] if strips else [])
        if uitval:
            delen.append("een uitval van de 12 V (15 s uitgang uit, daarna weer aan op dezelfde spanning)")
        if QMessageBox.question(self, "Rooktest", "Het paneel loopt na: " + ", ".join(delen[:-1]) + (" en " if len(delen) > 1 else "")
                                + delen[-1] + ". Dat duurt " + ("ongeveer een minuut" if uitval else "ongeveer een halve minuut")
                                + ".\n\nStarten?") != QMessageBox.Yes:
            return
        r = self.inst.setdefault("rook", {})
        r.update(fw=fw.strip(), strips=strips, uitval=uitval)
        instellingen.bewaar(self.inst)
        self._start_proef(pv.Rooktest(fw, strips, uitval, r.get("basis")))

    def _rook_basis(self) -> None:
        p = self.laatste_rook
        if p is None or p.i is None:
            return
        self.inst.setdefault("rook", {})["basis"] = round(p.i, 4)
        instellingen.bewaar(self.inst)
        self.markeer(f"rooktest: basis {pv.fmt_ma(p.i)} bewaard")
        self.l_voet.setText(f"rooktest: basis {pv.fmt_ma(p.i)} bewaard")

    def _start_nacht(self, cfg: dict) -> None:
        if self.werker is None:
            QMessageBox.information(self, "Niet verbonden", "Verbind eerst met de voeding.")
            return
        if not self.project.binnen(cfg["v"], cfg["i"]):
            QMessageBox.warning(self, "Buiten de grens", self.project.uitleg())
            return
        omhoog = self.uitgang and self.v_set is not None and cfg["v"] > self.v_set + 0.05
        if QMessageBox.question(self, "Nachttest starten", f"{pv.fmt_duur(cfg['uren'] * 3600)} meten op {nl(cfg['v'], 1)} V met een "
                                f"stroomgrens van {pv.fmt_ma(cfg['i'])}." + (f"\n\nDe uitgang staat aan en de spanning gaat omhoog van "
                                f"{nl(self.v_set, 1)} naar {nl(cfg['v'], 1)} V." if omhoog else "") + "\n\nDe uitgang gaat aan (of blijft aan). Starten?") != QMessageBox.Yes:
            return
        self.inst["nacht"] = dict(cfg)
        instellingen.bewaar(self.inst)
        p = pv.Nachttest(cfg["uren"], cfg["v"], cfg["i"], cfg["piek"], cfg["stil"], cfg["uit"])
        if self._start_proef(p) and cfg.get("log") and not self.log.loopt:
            self.nacht_log = True
            pad = self.log.start(f"nachttest_{datetime.now():%Y%m%d_%H%M}")
            self.uitgebreid.toon_log(True, pad.name)
            self.a_log.setText("Log stoppen")

    # ---------------------------------------------------------------- onderdelentester
    def _onderdelen_venster(self) -> None:
        if self.od_venster is None:
            d = OnderdelenVenster(self.thema, self, self)
            d.setStyleSheet(qss(self.thema))
            d.start.connect(self._start_onderdeel)
            d.stop.connect(lambda: self._stop_proef("Gestopt"))
            self.od_venster = d
        self.od_venster.show()
        self.od_venster.raise_()

    def _start_onderdeel(self, soort: str) -> None:
        if self.werker is None:
            QMessageBox.information(self, "Niet verbonden", "Verbind eerst met de voeding.")
            return
        m = pv.ONDERDELEN[soort]
        extra = ("\n\nDe spanning mag hier tot 25 V, boven de grens CaraVan Guard, omdat de stroom op 1 mA staat. Veilig voor een "
                 "losse TVS, nooit voor de print." if soort == "tvs" else "")
        if QMessageBox.question(self, "Onderdeel meten", f"{m['naam']}: de uitgang gaat uit, dan een paar seconden aan met {m['kort']}, "
                                "en daarna weer uit. Je instellingen komen terug.\n\nZit alleen het losse onderdeel aan de klemmen, "
                                f"niet de print?{extra}") != QMessageBox.Yes:
            return
        vmax = max(self.project.vmax, 25.0) if soort == "tvs" else self.project.vmax
        self._start_proef(pv.Onderdeel(soort, self.v_set, self.i_set, vmax, self.project.imax))

    # ---------------------------------------------------------------- instellingen, zoeken, telefoon
    def _zoeken(self) -> None:
        d = ZoekDialoog(self.menu, self)
        d.setStyleSheet(qss(self.thema))
        d.move(self.geometry().center().x() - d.width() // 2, self.geometry().top() + 80)
        d.exec()

    def _instellingen_dialoog(self) -> None:
        d = InstellingenDialoog(self.thema, self.inst, self.meldingen, self.telefoon, self)
        d.setStyleSheet(qss(self.thema))
        if d.exec() and d.uitkomst:
            u = d.uitkomst
            for k, v in u.items():
                if isinstance(v, dict) and isinstance(self.inst.get(k), dict):
                    self.inst[k].update(v)
                else:
                    self.inst[k] = v
            instellingen.bewaar(self.inst)
            if u["thema"] != self.thema.naam:
                self._kies_thema(u["thema"])
        else:
            self.inst["web"]["aan"] = self.telefoon.loopt      # de telefoon kan in het venster al geschakeld zijn
            self.inst["web"]["code"] = self.telefoon.code
            instellingen.bewaar(self.inst)

    def _telefoon_tik(self) -> None:
        tel = self.telefoon
        while True:
            try:
                op = tel.opdrachten.get_nowait()
            except Exception:  # noqa: BLE001
                break
            if op[0] == "uit":
                self.noodstop("telefoon")
            elif op[0] == "markering":
                self.markeer(f"telefoon: {op[1]}")
        if not tel.loopt:
            return
        nu = time.time()
        if nu - self._tel_t < 1.0:
            return
        self._tel_t = nu
        recent = self.geschiedenis.tussen(nu - 300, nu)
        stap = max(1, len(recent) // 150)
        m = self.laatste_meting if self.werker is not None else None
        tel.momentopname = {
            "t": nu, "verbonden": self.werker is not None, "v": m.v if m else None, "i": m.i if m else None,
            "vset": self.v_set if self.werker is not None else None, "iset": self.i_set if self.werker is not None else None,
            "uit": bool(self.uitgang and self.werker is not None),
            "cc": bool(self.laatste_stand.cc) if self.laatste_stand else False, "grens": self.project.naam,
            "alarm": self.l_voet.text() if self.l_voet.text().startswith(("ALARM", "NOODSTOP")) else "",
            "programma": self.uitgebreid.l_proef_naam.text() + " · " + self.uitgebreid.l_proef_tekst.text()
            if self.uitgebreid.l_proef_naam.text() != "geen proef" else "",
            "punten": [[round(nu - p.t, 1), round(p.v, 2), round(p.i, 4)] for p in recent[::stap]]}

    def _tik(self) -> None:
        self._telefoon_tik()
        if self.proef is not None:
            ctx = self._ctx()
            self._voer_uit(self.proef.tik(ctx))
            if isinstance(self.proef, pv.Nachttest):
                for tekst in self.proef.nieuwe_meldingen:
                    self.meldingen.ntfy("Nachttest", tekst, 4, ("warning",))
                self.proef.nieuwe_meldingen.clear()
            if self.proef is not None and self.proef.klaar:
                self._proef_klaar("Klaar", ctx)
            else:
                self._toon_proef()
                self._vensters_ververs()
        if self.loop is not None:
            self._voer_uit(self.loop.tik(time.time(), self.laatste_meting))
            if self.loop.klaar:
                self._stop_programma("Klaar", rapport=True)
            else:
                self._toon_proef()
        w = self.stapel.currentWidget()
        if w is self.uitgebreid:
            self.uitgebreid.ververs()
            nu = time.time()
            self.uitgebreid.toon_energie(self.energie, self.geschiedenis.venster(nu - self.uitgebreid.grafiek.venster_s, nu))
        elif w is self.meetbank:
            self.meetbank.ververs()

    def _mini(self) -> None:
        if self.mini is None:
            self.mini = Mini(self.thema, self.project.naam)
            self.mini.setStyleSheet(qss(self.thema))
            self.mini.uit.connect(lambda: self._uitgang(False))
        self.mini.show()
        self.mini.raise_()

    def markeer(self, tekst: str) -> None:
        t = time.time()
        self.markeringen.append((t, tekst))
        self.uitgebreid.grafiek.markeer(t, tekst)
        self.meetbank.grafiek.markeer(t, tekst)
        self.log.markeer(t, tekst)
        self.l_voet.setText(f"markering {datetime.fromtimestamp(t):%H:%M:%S}: {tekst}")

    def _alarm(self, tekst: str) -> None:
        self.l_voet.setText(f"ALARM {datetime.now():%H:%M:%S}: {tekst}")
        self.meldingen.alarm(tekst)
        box = QMessageBox(QMessageBox.Warning, "Bewaking", tekst, QMessageBox.Ok, self)
        box.setModal(False)
        box.show()

    def _bewaking_dialoog(self) -> None:
        d = BewakingDialoog(self.bewaking, self)
        d.setStyleSheet(qss(self.thema))
        if d.exec():
            self.uitgebreid.toon_bewaking(self.bewaking.regels, self.bewaking.actief)
            self.eenvoudig.l_bew.tekst = "bewaking aan" if self.bewaking.actief else "bewaking uit"
            self.eenvoudig.l_bew.zet(self.bewaking.actief)

    def _rapport(self, van: float, tot: float, titel: str) -> None:
        pts = self.geschiedenis.tussen(van, tot)
        if len(pts) < 2:
            QMessageBox.information(self, "Geen metingen", "Er zijn te weinig metingen in dit stuk.")
            return
        markers = [(t, x) for t, x in self.uitgebreid.grafiek.markers if van <= t <= tot]
        pagina = rapport_mod.maak(titel, pts, markers, apparaat=self.l_apparaat.text(), project=self.project.naam,
                                  v_set=self.v_set, i_set=self.i_set)
        pad = rapport_mod.bewaar(pagina, "rapport")
        self.l_voet.setText(f"rapport: {pad.name}")
        webbrowser.open(pad.resolve().as_uri())

    def _log(self, aan: bool) -> None:
        if aan:
            pad = self.log.start()
            self.l_voet.setText(f"log: {pad.name}")
        else:
            pad = self.log.stop()
            self.l_voet.setText(f"log gesloten: {pad.name if pad else ''} ({self.log.regels} metingen)")
        self.uitgebreid.toon_log(aan)
        self.a_log.setText("Log stoppen" if aan else "Log starten")

    def _op_instellingen(self, v: float, i: float) -> None:
        eerste = self.v_set is None
        self.v_set, self.i_set = v, i
        if eerste and not self.uitgang and (v > self.project.vmax + 0.005 or i > self.project.imax + 0.0005):
            # Meteen na het verbinden: de voeding onthoudt zijn laatste instelling. Boven de grens? Dan alvast
            # omlaag, zodat een draai aan de knop of 'uitgang aan' nooit meer de grens overschrijdt.
            v2, i2 = self.project.knip(v, i)
            self._stuur(self.voeding.zet_stroomgrens, i2)
            self._stuur(self.voeding.zet_spanning, v2)
            self.l_voet.setText(f"bij het verbinden stond de voeding op {nl(v, 2)} V / {nl(i, 3)} A, buiten de grens: "
                                f"teruggezet naar {nl(v2, 2)} V / {nl(i2, 3)} A")
            self.markeer(f"verbonden: voeding stond op {nl(v, 2)} V, teruggezet naar {nl(v2, 2)} V")
        if self.rcl_wacht is not None and time.time() > self.rcl_wacht[1]:
            n, self.rcl_wacht = self.rcl_wacht[0], None      # na een geheugenknop: onthoud wat erin zit
            self._geheugen_label(n, v, i)
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
        """De uitgang aan mag alleen als de instelling van de voeding binnen de grens van het project valt.
        GEMETEN 23-10-2026: de Korad onthoudt 13,8 V van de caravan; 'uitgang aan' bij project EMSN-auto zette die
        13,8 V twee seconden op het T-Beam-bordje voordat de terugkoppeling ingreep. Daarom hier vooraf weigeren."""
        if aan:
            if self.v_set is None or self.i_set is None:
                QMessageBox.information(self, "Even wachten", "De instelling van de voeding is nog niet gelezen.")
                return
            if not self.project.binnen(self.v_set, self.i_set):
                QMessageBox.warning(self, "Uitgang blijft uit",
                                    f"De voeding staat op {nl(self.v_set, 2)} V en {nl(self.i_set, 3)} A, buiten de grens "
                                    f"van het project. Stel eerst een spanning en stroomgrens binnen de grens in.\n\n"
                                    + self.project.uitleg())
                return
        self._stuur(self.voeding.zet_uitgang, aan)

    # ---------------------------------------------------------------- vaste knoppen
    def _voorinstellingen(self) -> list[tuple[str, float, float]] | None:
        """De vier vaste knoppen van dit project, of None als het de geheugens M1-M4 van de voeding zijn (Vrij)."""
        standaard = grenzen.VOORINSTELLINGEN.get(self.project.sleutel)
        if standaard is None:
            return None
        eigen = (self.inst.get("voorinstellingen") or {}).get(self.project.sleutel)
        uit = list(standaard)
        for k, d in enumerate((eigen or [])[:4]):
            try:
                uit[k] = (str(d["naam"])[:18], float(d["v"]), float(d["i"]))
            except (KeyError, TypeError, ValueError):
                pass
        return uit

    def _toon_geheugens(self) -> None:
        vi = self._voorinstellingen()
        for n in range(1, 5):
            if vi is None:
                tekst = self.inst["geheugens"].get(str(n), f"M{n}")
                tip = f"Geheugen M{n} van de voeding: klik = ophalen, rechtsklik = huidige instelling hier bewaren"
            else:
                naam, v, i = vi[n - 1]
                tekst = f"{naam}\n{nl(v, 2).rstrip('0').rstrip(',')} V · {nl(i, 3).rstrip('0').rstrip(',')} A"
                tip = f"{naam}: {nl(v, 2)} V, stroomgrens {nl(i, 3)} A. Rechtsklik = huidige instelling hier bewaren"
            for w in (self.eenvoudig, self.uitgebreid):
                w.k_geheugen[n - 1].setText(tekst)
                w.k_geheugen[n - 1].setToolTip(tip)

    def _geheugen(self, n: int) -> None:
        vi = self._voorinstellingen()
        if vi is not None:                      # een vaste knop van het project: gewoon instellen, met alle vangnetten
            naam, v, i = vi[n - 1]
            if isinstance(self.proef, Accu):
                self._stop_proef("Gestopt: vaste knop gebruikt")
            self._stop_programma("Gestopt: vaste knop gebruikt")
            self._zet(v, i)
            return
        tekst = self.inst["geheugens"].get(str(n), "")
        try:                                   # de grens vooraf toetsen op wat we van deze plaats weten
            v_t, i_t = (float(x.split()[0].replace(",", ".")) for x in tekst.split("\n")[:2])
        except (ValueError, IndexError):
            v_t = i_t = None
        if v_t is not None and not self.project.binnen(v_t, i_t):
            QMessageBox.warning(self, "Buiten de grens", f"Geheugen M{n} staat op {tekst.replace(chr(10), ' / ')}.\n\n"
                                + self.project.uitleg())
            return
        if v_t is not None and self.uitgang and self.v_set is not None and v_t > self.v_set + 0.05:
            if QMessageBox.question(self, "Hogere spanning op de uitgang",
                                    f"De uitgang staat aan. Deze knop verhoogt de spanning van {nl(self.v_set, 2)} V "
                                    f"naar {nl(v_t, 2)} V, direct op wat er nu is aangesloten.\n\nDoorgaan?") != QMessageBox.Yes:
                return
        if isinstance(self.proef, Accu):
            self._stop_proef("Gestopt: geheugenknop gebruikt")
        self._stop_programma("Gestopt: geheugenknop gebruikt")
        if self._stuur(self.voeding.geheugen_ophalen, n):
            self.rcl_wacht = (n, time.time())

    def _geheugen_bewaren(self, n: int) -> None:
        if self.v_set is None:
            return
        vi = self._voorinstellingen()
        if vi is not None:
            naam, ok = QInputDialog.getText(self, f"Vaste knop {n}", f"Naam voor {nl(self.v_set, 2)} V / {nl(self.i_set, 3)} A:",
                                            text=vi[n - 1][0])
            if not ok:
                return
            eigen = self.inst.setdefault("voorinstellingen", {}).setdefault(self.project.sleutel,
                                                                              [{"naam": a, "v": b, "i": c} for a, b, c in vi])
            eigen[n - 1] = {"naam": (naam.strip() or vi[n - 1][0])[:18], "v": self.v_set, "i": self.i_set}
            instellingen.bewaar(self.inst)
            self._toon_geheugens()
            return
        if QMessageBox.question(self, f"Bewaren in M{n}", f"De huidige instelling ({nl(self.v_set, 2)} V, "
                                f"{nl(self.i_set, 3)} A) bewaren in geheugen M{n} van de voeding?") != QMessageBox.Yes:
            return
        if self._stuur(self.voeding.geheugen_bewaren, n):
            self.rcl_wacht = (n, time.time())

    def _geheugen_label(self, n: int, v: float, i: float) -> None:
        tekst = f"{nl(v, 2).rstrip('0').rstrip(',')} V\n{nl(i, 3).rstrip('0').rstrip(',')} A"
        self.inst["geheugens"][str(n)] = tekst
        instellingen.bewaar(self.inst)
        for w in (self.eenvoudig, self.uitgebreid):
            w.k_geheugen[n - 1].setText(tekst)

    # ---------------------------------------------------------------- logboek, logs, werkboek
    def _werkboek(self) -> None:
        d = WerkboekVenster(self.thema, self.werkboek, self)
        d.setStyleSheet(qss(self.thema))
        d.open_log.connect(self._log_openen)
        d.show()
        self.vensters.append(d)

    def _log_openen(self, pad=None) -> None:
        if pad is None:
            pad = kies_log(self, "Log openen")
            if pad is None:
                return
        uit = laad_log(self, pad)
        if uit is None:
            return
        d = LogVenster(self.thema, pad, uit[0], uit[1], self)
        d.setStyleSheet(qss(self.thema))
        d.show()
        self.vensters.append(d)

    def _logs_vergelijken(self) -> None:
        d = VergelijkVenster(self.thema, self)
        d.setStyleSheet(qss(self.thema))
        d.show()
        self.vensters.append(d)

    # ---------------------------------------------------------------- accu nabootsen
    def _accu_dialoog(self) -> None:
        if self.werker is None:
            QMessageBox.information(self, "Niet verbonden", "Verbind eerst met de voeding.")
            return
        d = AccuDialoog(self.project.vmax, self.v_set, self)
        d.setStyleSheet(qss(self.thema))
        if d.exec() and d.uitkomst:
            v0, v1, duur_s, r = d.uitkomst
            if self.uitgang and self.v_set is not None and v0 > self.v_set + 0.05:
                if QMessageBox.question(self, "Hogere spanning op de uitgang",
                                        f"De uitgang staat aan. De accu begint op {nl(v0, 2)} V, hoger dan de huidige "
                                        f"{nl(self.v_set, 2)} V, direct op wat er nu is aangesloten.\n\nDoorgaan?") != QMessageBox.Yes:
                    return
            self._start_proef(Accu(v0, v1, duur_s, r, self.project.vmax))

    def noodstop(self, reden: str = "") -> None:
        self._stop_programma("NOODSTOP")
        self._stop_proef("NOODSTOP")
        self.meldingen.noodstop(reden)
        if self.werker is not None:
            self.werker.opdracht(self.voeding.zet_uitgang, False)
        self.l_voet.setText(f"NOODSTOP {datetime.now():%H:%M:%S}: uitgang uit")
        if self.stapel.currentWidget() is self.presentatie:      # Esc in Presentatie: ook terug naar het paneel
            self.showNormal()
            self._kies_indeling(self.vorige_indeling)

    # ---------------------------------------------------------------- keuzes
    def _project_gekozen(self, idx: int) -> None:
        self.project = grenzen.project(self.c_project.itemData(idx))
        self.inst["project"] = self.project.sleutel
        instellingen.bewaar(self.inst)
        for w in self.indelingen:
            w.zet_grens(self.project.vmax, self.project.imax)
        self._toon_geheugens()
        self._kies_indeling(self.inst["indeling"].get(self.project.sleutel, "eenvoudig"))

    def _kies_indeling(self, sleutel: str) -> None:
        sleutels = [s for s, _ in INDELINGEN]
        if sleutel not in sleutels:
            sleutel = "eenvoudig"
        huidig = sleutels[self.stapel.currentIndex()]
        if huidig != "presentatie":
            self.vorige_indeling = huidig
        self.stapel.setCurrentIndex(sleutels.index(sleutel))
        for s, a in self.a_indeling.items():
            a.setChecked(s == sleutel)
        self.kop.setVisible(sleutel != "presentatie")
        self.voet.setVisible(sleutel != "presentatie")
        if sleutel == "presentatie":
            self.showFullScreen()
        elif self.isFullScreen():
            self.showNormal()
        if sleutel != "presentatie":
            self.inst["indeling"][self.project.sleutel] = sleutel
            instellingen.bewaar(self.inst)

    def _kies_thema(self, sleutel: str) -> None:
        if sleutel == self.thema.naam:
            return
        self.thema = THEMAS[sleutel]
        self.inst["thema"] = sleutel
        instellingen.bewaar(self.inst)
        self._herbouw()

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
        if self.proef is not None:
            self._stop_proef("Gestopt: paneel gesloten")
        self._ontkoppel_monitor()
        if self.werker is not None:
            self.werker.stop()
        self.log.stop()
        self.telefoon.stop()
        self.meldingen.stop()
        self._onthoud_venster()
        instellingen.bewaar(self.inst)
        ev.accept()
