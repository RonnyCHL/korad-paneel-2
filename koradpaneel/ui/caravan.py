"""Het venster CaraVan Guard: de monitor koppelen, opstartcurve, bouwstappen, controles (ijken, spanning,
UPS-duurtest), rooktest en nachttest. Het venster start proeven via signalen; het hoofdvenster drijft ze."""

from __future__ import annotations

import time
import webbrowser
from datetime import datetime
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMessageBox, QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget)

from ..apparaat.monitor import EXPECTED_I2C
from ..kern import proeven as pv
from .eenvoudig import getal, nl
from .thema import Thema
from .uitgebreid import kaart

KLEUR_STATUS = {"goed": "goed", "let op": "stroom", "zoeken": "gevaar", "fout": "gevaar", "info": "accent",
                "bezig": "accent", "overgeslagen": "inkt_vaag", "wacht": "inkt_vaag"}


def _bol(thema: Thema, st: str | None, tekst: str) -> str:
    k = getattr(thema, KLEUR_STATUS.get(st or "", "inkt_vaag"))
    return f'<span style="color:{k}">●</span>&nbsp; {tekst}'


def _veld(waarde: str, breedte: int = 90) -> QLineEdit:
    e = QLineEdit(waarde)
    e.setFixedWidth(breedte)
    e.setStyleSheet("font-size: 15px; padding: 6px 8px")
    return e


class CaraVanVenster(QDialog):
    koppel = Signal(str)
    ontkoppel = Signal()
    start_curve = Signal(float, float)
    meet_stap = Signal(int)
    uitvaltest = Signal()
    start_vcheck = Signal()
    start_ijken = Signal(float)
    start_ups = Signal(bool)
    start_rook = Signal(str, bool, bool)
    start_nacht = Signal(dict)
    rook_basis = Signal()
    stop = Signal()

    def __init__(self, thema: Thema, hv, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CaraVan Guard")
        self.setModal(False)
        self.thema, self.hv = thema, hv
        self.laatste_curve: pv.Opstartcurve | None = None
        self.laatste_rook: pv.Rooktest | None = None
        self.laatste_nacht: pv.Nachttest | None = None
        self.rapporten: dict[str, Path] = {}
        root = QVBoxLayout(self)
        kop = QHBoxLayout()
        t = QLabel("CaraVan Guard")
        t.setStyleSheet("font-size: 18px; font-weight: 600")
        kop.addWidget(t)
        self.l_monitor = QLabel("")
        self.l_monitor.setObjectName("zacht")
        kop.addSpacing(12)
        kop.addWidget(self.l_monitor, 1)
        self.k_stop = QPushButton("Proef stoppen")
        self.k_stop.setObjectName("gevaar")
        self.k_stop.clicked.connect(self.stop.emit)
        kop.addWidget(self.k_stop)
        root.addLayout(kop)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self._tab_monitor()
        self._tab_curve()
        self._tab_bouw()
        self._tab_controles()
        self._tab_rook()
        self._tab_nacht()
        self.resize(1100, 720)
        self.ververs()

    # ---- tabblad monitor
    def _tab_monitor(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        u = QLabel("De monitor (de ESP32 op de draagprint) via wifi: elke seconde zijn status, elke twee seconden zijn "
                   "logboek. Adres: het IP of caravan.local. De proeven hiernaast lezen de 12 V, de stroom en de UPS-cel "
                   "die hij meet, en sturen de ledstrips.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        lay.addWidget(u)
        rij = QHBoxLayout()
        rij.addWidget(QLabel("Adres"))
        self.e_adres = _veld(self.hv.inst.get("monitor", {}).get("adres") or "caravan.local", 220)
        rij.addWidget(self.e_adres)
        self.k_koppel = QPushButton("Koppelen")
        self.k_koppel.setObjectName("primair")
        self.k_koppel.clicked.connect(self._koppel)
        rij.addWidget(self.k_koppel)
        rij.addStretch(1)
        lay.addLayout(rij)
        k, lk = kaart("Nu")
        self.l_mon_velden = QLabel("")
        self.l_mon_velden.setObjectName("cijfer")
        self.l_mon_velden.setWordWrap(True)
        lk.addWidget(self.l_mon_velden)
        lay.addWidget(k)
        k, lk = kaart("Modules op de I2C-bus")
        self.l_i2c = QLabel("")
        self.l_i2c.setWordWrap(True)
        lk.addWidget(self.l_i2c)
        lay.addWidget(k)
        k, lk = kaart("Logboek van de monitor")
        self.lijst_ev = QListWidget()
        lk.addWidget(self.lijst_ev, 1)
        lay.addWidget(k, 1)
        self.tabs.addTab(w, "Monitor")

    def _koppel(self) -> None:
        if self.hv.monitor is not None:
            self.ontkoppel.emit()
        else:
            self.koppel.emit(self.e_adres.text().strip() or "caravan.local")

    # ---- tabblad opstartcurve
    def _tab_curve(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        u = QLabel("Zachte start: de uitgang gaat uit, dan op 0 V aan en de spanning loopt in stapjes op terwijl de stroom "
                   "wordt gemeten. Bij de stroomgrens gaat de uitgang uit. Zo zie je een kortsluiting of een verkeerd "
                   "onderdeel voordat er iets warm wordt.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        lay.addWidget(u)
        rij = QHBoxLayout()
        rij.addWidget(QLabel("Tot"))
        self.e_curve_v = _veld("13,8")
        rij.addWidget(self.e_curve_v)
        rij.addWidget(QLabel("V, stroomgrens"))
        self.e_curve_i = _veld("100")
        rij.addWidget(self.e_curve_i)
        rij.addWidget(QLabel("mA"))
        k = QPushButton("Opstartcurve starten")
        k.setObjectName("primair")
        k.clicked.connect(self._curve)
        rij.addWidget(k)
        self.k_curve_csv = QPushButton("CSV")
        self.k_curve_csv.setObjectName("geheugen")
        self.k_curve_csv.clicked.connect(self._curve_csv)
        rij.addWidget(self.k_curve_csv)
        rij.addStretch(1)
        lay.addLayout(rij)
        self.l_curve = QLabel("")
        self.l_curve.setObjectName("zacht")
        self.l_curve.setWordWrap(True)
        lay.addWidget(self.l_curve)
        kk, lk = kaart()
        pg.setConfigOptions(antialias=True)
        self.plot_curve = pg.PlotWidget()
        self.plot_curve.setBackground(self.thema.kaart)
        self.plot_curve.showGrid(x=True, y=True, alpha=0.12)
        self.plot_curve.getAxis("left").setLabel("mA")
        self.plot_curve.getAxis("left").enableAutoSIPrefix(False)
        self.plot_curve.getAxis("bottom").setLabel("V")
        self.plot_curve.setMenuEnabled(False)
        self.lijn_curve = self.plot_curve.plot([], [], pen=pg.mkPen(self.thema.stroom, width=2), symbol="o", symbolSize=5,
                                               symbolBrush=self.thema.stroom, symbolPen=None)
        self.lijn_grens = pg.InfiniteLine(angle=0, pen=pg.mkPen(self.thema.gevaar, style=Qt.DashLine))
        self.plot_curve.addItem(self.lijn_grens)
        lk.addWidget(self.plot_curve, 1)
        lay.addWidget(kk, 1)
        self.l_curve_uitleg = QLabel("")
        self.l_curve_uitleg.setWordWrap(True)
        lay.addWidget(self.l_curve_uitleg)
        self.tabs.addTab(w, "Opstartcurve")

    def _curve(self) -> None:
        try:
            v, i = getal(self.e_curve_v.text()), getal(self.e_curve_i.text()) / 1000
        except ValueError:
            QMessageBox.information(self, "Invoer", "Vul getallen in, bijvoorbeeld 13,8 en 100.")
            return
        self.start_curve.emit(v, i)

    def _curve_csv(self) -> None:
        c = self.laatste_curve
        if c is None or not c.pts:
            return
        from PySide6.QtWidgets import QFileDialog
        pad, _ = QFileDialog.getSaveFileName(self, "Opstartcurve bewaren", f"opstartcurve_{datetime.now():%Y%m%d_%H%M}.csv",
                                             "CSV (*.csv)")
        if pad:
            Path(pad).write_text("v_set;v;ampere\n" + "".join(f"{a:.2f};{b:.3f};{d:.4f}\n" for a, b, d in c.pts),
                                 encoding="utf-8")

    # ---- tabblad bouwstappen
    def _tab_bouw(self) -> None:
        w = QWidget()
        lay = QHBoxLayout(w)
        links = QVBoxLayout()
        self.lijst_bouw = QListWidget()
        self.lijst_bouw.setFixedWidth(300)
        self.lijst_bouw.currentRowChanged.connect(lambda _r: self._bouw_toon())
        links.addWidget(self.lijst_bouw, 1)
        knoppen = QHBoxLayout()
        for tekst, fn in (("Bouwrapport", self._bouw_rapport), ("Opnieuw beginnen", self._bouw_opnieuw)):
            k = QPushButton(tekst)
            k.setObjectName("geheugen")
            k.clicked.connect(fn)
            knoppen.addWidget(k)
        links.addLayout(knoppen)
        lay.addLayout(links)
        rechts = QVBoxLayout()
        self.l_bouw_titel = QLabel("")
        self.l_bouw_titel.setStyleSheet("font-size: 16px; font-weight: 600")
        rechts.addWidget(self.l_bouw_titel)
        self.l_bouw_print = QLabel("")
        self.l_bouw_print.setObjectName("zacht")
        self.l_bouw_print.setWordWrap(True)
        rechts.addWidget(self.l_bouw_print)
        rij = QHBoxLayout()
        self.k_bouw_meet = QPushButton("Stap meten")
        self.k_bouw_meet.setObjectName("primair")
        self.k_bouw_meet.clicked.connect(lambda: self.meet_stap.emit(self.lijst_bouw.currentRow()))
        self.k_bouw_uitval = QPushButton("Uitvaltest (5 s)")
        self.k_bouw_uitval.setObjectName("geheugen")
        self.k_bouw_uitval.clicked.connect(self.uitvaltest.emit)
        rij.addWidget(self.k_bouw_meet)
        rij.addWidget(self.k_bouw_uitval)
        self.l_bouw_live = QLabel("")
        self.l_bouw_live.setObjectName("zacht")
        rij.addWidget(self.l_bouw_live, 1)
        rechts.addLayout(rij)
        self.l_bouw_uitslag = QLabel("")
        self.l_bouw_uitslag.setWordWrap(True)
        rechts.addWidget(self.l_bouw_uitslag)
        self.l_bouw_checks_kop = QLabel("CONTROLES MET DE MULTIMETER")
        self.l_bouw_checks_kop.setObjectName("kopje")
        rechts.addWidget(self.l_bouw_checks_kop)
        self.bouw_checks: list[QCheckBox] = []
        self.box_checks = QVBoxLayout()
        rechts.addLayout(self.box_checks)
        self.e_bouw_notitie = QTextEdit()
        self.e_bouw_notitie.setPlaceholderText("Notitie bij deze stap…")
        self.e_bouw_notitie.setFixedHeight(70)
        self.e_bouw_notitie.textChanged.connect(self._bouw_notitie)
        rechts.addWidget(self.e_bouw_notitie)
        self.l_bouw_i2c = QLabel("")
        self.l_bouw_i2c.setObjectName("zacht")
        self.l_bouw_i2c.setWordWrap(True)
        rechts.addWidget(self.l_bouw_i2c)
        rechts.addStretch(1)
        lay.addLayout(rechts, 1)
        self.tabs.addTab(w, "Bouwstappen")
        self._bouw_lijst()
        self.lijst_bouw.setCurrentRow(0)

    def _bouw_lijst(self) -> None:
        rij = self.lijst_bouw.currentRow()
        self.lijst_bouw.blockSignals(True)
        self.lijst_bouw.clear()
        for s in pv.BOUWSTAPPEN:
            st = self.hv.bouw.status(s["nr"])
            it = QListWidgetItem(f"{s['nr']}  {s['titel']}" + (f"   [{st}]" if st else ""))
            it.setForeground(pg.mkColor(getattr(self.thema, KLEUR_STATUS.get(st or "", "inkt"))))
            self.lijst_bouw.addItem(it)
        self.lijst_bouw.blockSignals(False)
        self.lijst_bouw.setCurrentRow(max(0, rij))

    def _bouw_toon(self) -> None:
        nr = max(0, self.lijst_bouw.currentRow())
        s = pv.BOUWSTAPPEN[nr]
        st = self.hv.bouw.stand(nr)
        self.l_bouw_titel.setText(f"Stap {nr}: {s['titel']}" + (f"  ·  {nl(s['v'], 1)} V, grens {pv.fmt_ma(s['i'])}" if s["v"] is not None else "  ·  alleen de multimeter"))
        self.l_bouw_print.setText(s["print"])
        self.k_bouw_meet.setEnabled(s["v"] is not None)
        self.k_bouw_uitval.setVisible(bool(s.get("uitval")))
        if st.get("oordeel"):
            self.l_bouw_uitslag.setText(_bol(self.thema, st["oordeel"], f"<b>{st['oordeel'].upper()}</b> "
                                             f"({datetime.fromtimestamp(st['t']):%d-%m %H:%M}): {st['tekst']}<br>"
                                             + "<br>".join(st.get("uitleg", []))))
        else:
            self.l_bouw_uitslag.setText("Nog niet gemeten." if s["v"] is not None else "")
        for k in self.bouw_checks:
            k.deleteLater()
        self.bouw_checks = []
        for n, (tekst, ok) in enumerate(zip(s["checks"], st["checks"])):
            cb = QCheckBox(tekst)
            cb.setChecked(ok)
            cb.toggled.connect(lambda aan, n=n: self._bouw_check(n, aan))
            self.box_checks.addWidget(cb)
            self.bouw_checks.append(cb)
        self.e_bouw_notitie.blockSignals(True)
        self.e_bouw_notitie.setPlainText(st.get("notitie", ""))
        self.e_bouw_notitie.blockSignals(False)
        self._bouw_i2c(s)

    def _bouw_i2c(self, s: dict) -> None:
        if not s.get("monitor"):
            self.l_bouw_i2c.setText("")
            return
        mon = self.hv.mon
        if not mon.vers():
            self.l_bouw_i2c.setText("Koppel de monitor (tabblad Monitor) om te zien welke modules hij op de I2C-bus vindt.")
            return
        gevonden = set(mon.laatste.get("i2c") or [])
        delen = []
        for a, naam, req in EXPECTED_I2C:
            ok = a in gevonden
            delen.append(_bol(self.thema, "goed" if ok else ("fout" if req else "let op"),
                              f"0x{a:02X} {naam}: {'gevonden' if ok else ('niet gevonden' if req else 'niet gevonden (nog niet aangesloten?)')}"))
        delen.append(_bol(self.thema, "goed" if mon.laatste.get("sd") else "let op", f"microSD: {'gevonden' if mon.laatste.get('sd') else 'niet gevonden'}"))
        self.l_bouw_i2c.setText("<br>".join(delen))

    def _bouw_check(self, n: int, aan: bool) -> None:
        nr = max(0, self.lijst_bouw.currentRow())
        self.hv.bouw.stand(nr)["checks"][n] = aan
        self.hv.bouw.bewaar()
        self._bouw_lijst()

    def _bouw_notitie(self) -> None:
        nr = max(0, self.lijst_bouw.currentRow())
        self.hv.bouw.stand(nr)["notitie"] = self.e_bouw_notitie.toPlainText()[:700]
        self.hv.bouw.bewaar()

    def _bouw_rapport(self) -> None:
        from ..kern import rapport as rapport_mod
        pagina = self.hv.bouw.rapport_html(self.hv.apparaat_naam)
        pad = rapport_mod.bewaar(pagina, "bouwrapport")
        self.hv.werkboek.voeg("bouwrapport", "Bouwrapport draagprint", pad)
        self.hv.markeer("bouwrapport gemaakt")
        webbrowser.open(pad.resolve().as_uri())

    def _bouw_opnieuw(self) -> None:
        if QMessageBox.question(self, "Opnieuw beginnen", "Alle uitkomsten, vinkjes en notities van de bouwstappen wissen?") == QMessageBox.Yes:
            self.hv.bouw.opnieuw()
            self._bouw_lijst()
            self._bouw_toon()

    # ---- tabblad controles
    def _tab_controles(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        for titel, uitleg, knop, fn, extra in (
                ("Spanningsmeting controleren",
                 "De spanning loopt van 10,5 tot 14,8 V in elf stappen; per stap 4 s wachten en 3 s meten. De 12 V-meting "
                 "van de monitor naast die van de voeding. Alles wat aan de voeding hangt krijgt die spanningen.",
                 "Controleren", lambda: self.start_vcheck.emit(), None),
                ("Stroommeting ijken",
                 "De drie strips gaan samen naar 0, 25, 50, 75 en 100 %; per stand 4 s wachten en 5 s meten, samen "
                 "ongeveer 50 s. De verhouding voeding/monitor geeft de nieuwe INA219_SHUNT_CAL.",
                 "IJken", self._ijken, "cal"),
                ("UPS-duurtest",
                 "De uitgang gaat uit; de monitor draait verder op de 18650. Het paneel volgt hem tot hij 30 s niet meer "
                 "antwoordt. Dat kan uren duren; laat het paneel zolang open.",
                 "Starten", self._ups, "ups")):
            k, lk = kaart(titel)
            u = QLabel(uitleg)
            u.setObjectName("zacht")
            u.setWordWrap(True)
            lk.addWidget(u)
            rij = QHBoxLayout()
            if extra == "cal":
                rij.addWidget(QLabel("INA219_SHUNT_CAL nu"))
                self.e_cal = _veld("0,1000", 110)
                rij.addWidget(self.e_cal)
            if extra == "ups":
                self.k_ups_terug = QCheckBox("Daarna de uitgang weer aan (laadstroom zien)")
                self.k_ups_terug.setChecked(True)
                rij.addWidget(self.k_ups_terug)
            kn = QPushButton(knop)
            kn.setObjectName("primair")
            kn.clicked.connect(fn)
            rij.addWidget(kn)
            rij.addStretch(1)
            lk.addLayout(rij)
            l = QLabel("")
            l.setWordWrap(True)
            lk.addWidget(l)
            setattr(self, {"Spanningsmeting controleren": "l_vcheck", "Stroommeting ijken": "l_ijken", "UPS-duurtest": "l_ups"}[titel], l)
            lay.addWidget(k)
        lay.addStretch(1)
        self.tabs.addTab(w, "Controles")

    def _ijken(self) -> None:
        try:
            self.start_ijken.emit(getal(self.e_cal.text()))
        except ValueError:
            QMessageBox.information(self, "Invoer", "Vul de huidige INA219_SHUNT_CAL in, bijvoorbeeld 0,1000.")

    def _ups(self) -> None:
        self.start_ups.emit(self.k_ups_terug.isChecked())

    # ---- tabblad rooktest
    def _tab_rook(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        u = QLabel("Na een update: antwoordt de monitor, klopt de firmware, zijn alle modules er, klopt de 12 V- en de "
                   "stroommeting, volgen de strips een commando, en overleeft hij een uitval van de 12 V zonder herstart. "
                   "Ongeveer een halve minuut; met uitval een minuut.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        lay.addWidget(u)
        rij = QHBoxLayout()
        rij.addWidget(QLabel("Verwachte firmware"))
        r = self.hv.inst.get("rook", {})
        self.e_rook_fw = _veld(r.get("fw", ""), 110)
        rij.addWidget(self.e_rook_fw)
        self.k_rook_strips = QCheckBox("strip 1 kort op 20 %")
        self.k_rook_strips.setChecked(bool(r.get("strips", True)))
        self.k_rook_uitval = QCheckBox("uitval van de 12 V (15 s)")
        self.k_rook_uitval.setChecked(bool(r.get("uitval", False)))
        rij.addWidget(self.k_rook_strips)
        rij.addWidget(self.k_rook_uitval)
        k = QPushButton("Rooktest starten")
        k.setObjectName("primair")
        k.clicked.connect(lambda: self.start_rook.emit(self.e_rook_fw.text(), self.k_rook_strips.isChecked(), self.k_rook_uitval.isChecked()))
        rij.addWidget(k)
        self.k_rook_basis = QPushButton("Basis bewaren")
        self.k_rook_basis.setObjectName("geheugen")
        self.k_rook_basis.clicked.connect(self.rook_basis.emit)
        rij.addWidget(self.k_rook_basis)
        self.k_rook_rapport = QPushButton("Rapport")
        self.k_rook_rapport.setObjectName("geheugen")
        self.k_rook_rapport.clicked.connect(lambda: self._open("rook"))
        rij.addWidget(self.k_rook_rapport)
        rij.addStretch(1)
        lay.addLayout(rij)
        self.l_rook = QLabel("")
        self.l_rook.setWordWrap(True)
        lay.addWidget(self.l_rook)
        k, lk = kaart("Controles")
        self.rook_items: dict[str, QLabel] = {}
        rooster = QGridLayout()
        for n, (sleutel, naam) in enumerate(pv.ROOK_ITEMS):
            l = QLabel(_bol(self.thema, "wacht", naam))
            l.setWordWrap(True)
            rooster.addWidget(l, n, 0)
            self.rook_items[sleutel] = l
        lk.addLayout(rooster)
        lk.addStretch(1)
        lay.addWidget(k, 1)
        self.tabs.addTab(w, "Rooktest")

    # ---- tabblad nachttest
    def _tab_nacht(self) -> None:
        w = QWidget()
        lay = QVBoxLayout(w)
        u = QLabel("Uren achter elkaar meten, bijvoorbeeld een nacht. Het paneel houdt een log bij, zet bijzonderheden als "
                   "markering in de grafiek, stuurt een melding naar je telefoon en maakt aan het eind vanzelf een rapport. "
                   "Laat het paneel en de laptop zolang aan staan.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        lay.addWidget(u)
        rooster = QGridLayout()
        cfg = self.hv.inst.get("nacht", {"uren": 8.0, "v": 13.8, "i": 1.5, "piek": 1200.0, "stil": 60.0, "log": True, "uit": False})
        self.e_nacht = {}
        for r, (sleutel, tekst, eenheid) in enumerate((("uren", "Duur", "uur"), ("v", "Spanning", "V"), ("i", "Stroomgrens", "A"),
                                                      ("piek", "Melden bij stroom boven", "mA"),
                                                      ("stil", "Melden als de monitor zwijgt langer dan", "s"))):
            rooster.addWidget(QLabel(tekst), r, 0)
            e = _veld(nl(float(cfg.get(sleutel, 0)), 2).rstrip("0").rstrip(","), 90)
            rooster.addWidget(e, r, 1)
            l = QLabel(eenheid)
            l.setObjectName("zacht")
            rooster.addWidget(l, r, 2)
            self.e_nacht[sleutel] = e
        rooster.setColumnStretch(3, 1)
        lay.addLayout(rooster)
        self.k_nacht_log = QCheckBox("Log opslaan in de map logs")
        self.k_nacht_log.setChecked(bool(cfg.get("log", True)))
        self.k_nacht_uit = QCheckBox("Uitgang uit na afloop")
        self.k_nacht_uit.setChecked(bool(cfg.get("uit", False)))
        lay.addWidget(self.k_nacht_log)
        lay.addWidget(self.k_nacht_uit)
        rij = QHBoxLayout()
        k = QPushButton("Nachttest starten")
        k.setObjectName("primair")
        k.clicked.connect(self._nacht)
        rij.addWidget(k)
        self.k_nacht_rapport = QPushButton("Rapport")
        self.k_nacht_rapport.setObjectName("geheugen")
        self.k_nacht_rapport.clicked.connect(lambda: self._open("nacht"))
        rij.addWidget(self.k_nacht_rapport)
        self.l_nacht = QLabel("")
        self.l_nacht.setWordWrap(True)
        rij.addWidget(self.l_nacht, 1)
        lay.addLayout(rij)
        k, lk = kaart("Bijzonderheden")
        self.lijst_nacht = QListWidget()
        lk.addWidget(self.lijst_nacht, 1)
        lay.addWidget(k, 1)
        self.tabs.addTab(w, "Nachttest")

    def _nacht(self) -> None:
        try:
            cfg = {k: getal(e.text()) for k, e in self.e_nacht.items()}
        except ValueError:
            QMessageBox.information(self, "Invoer", "Vul overal een getal in.")
            return
        if not (0.005 <= cfg["uren"] <= 48 and cfg["piek"] >= 0 and cfg["stil"] >= 10):
            QMessageBox.information(self, "Invoer", "Duur tussen 0,005 en 48 uur, piekgrens 0 of meer (0 = niet melden), "
                                                    "monitor minstens 10 s.")
            return
        cfg["log"], cfg["uit"] = self.k_nacht_log.isChecked(), self.k_nacht_uit.isChecked()
        self.start_nacht.emit(cfg)

    def _open(self, sleutel: str) -> None:
        pad = self.rapporten.get(sleutel)
        if pad and pad.exists():
            webbrowser.open(pad.resolve().as_uri())

    # ---- vanuit het hoofdvenster
    def proef_klaar(self, proef: pv.Proef, pad: Path | None) -> None:
        if isinstance(proef, pv.Opstartcurve):
            self.laatste_curve = proef
            if proef.label.startswith("bouwstap"):
                self._bouw_lijst()
                self._bouw_toon()
        elif isinstance(proef, pv.Rooktest):
            self.laatste_rook = proef
            if pad:
                self.rapporten["rook"] = pad
        elif isinstance(proef, pv.Nachttest):
            self.laatste_nacht = proef
            if pad:
                self.rapporten["nacht"] = pad
        elif isinstance(proef, pv.Spanningscontrole):
            self.l_vcheck.setText(_bol(self.thema, "goed" if proef.ok else "let op", proef.tekst))
        elif isinstance(proef, pv.IJken):
            self.l_ijken.setText(_bol(self.thema, "goed" if proef.verhouding else "let op", proef.tekst))
        elif isinstance(proef, pv.UpsDuurtest):
            self.l_ups.setText(_bol(self.thema, "goed", proef.tekst))
        self.ververs()

    def ververs(self) -> None:
        hv, t = self.hv, time.time()
        mon = hv.mon
        self.l_monitor.setText(mon.regel())
        self.k_koppel.setText("Loskoppelen" if hv.monitor is not None else "Koppelen")
        if mon.vers():
            f = mon.laatste
            delen = [f"12 V: {nl(f['v'], 2)} V" if f.get("v") is not None else "12 V: geen meting",
                     f"stroom: {pv.fmt_ma(f['a'])}" if f.get("a") is not None else "stroom: -",
                     f"UPS-cel: {nl(f['ups_v'], 2)} V" + (f" ({f['ups_pct']:.0f} %)" if f.get("ups_pct") is not None else "") if f.get("ups_ok") and f.get("ups_v") is not None else "UPS-cel: geen meting",
                     f"strips: {', '.join(f'{x} %' for x in f.get('lt') or [])}" if f.get("lt_ok") else "strips: geen ledsturing",
                     f"firmware {f.get('fw') or '?'}", f"draait {pv.fmt_duur(f['up'])}" if f.get("up") is not None else ""]
            self.l_mon_velden.setText("  ·  ".join(d for d in delen if d))
            gevonden = set(f.get("i2c") or [])
            self.l_i2c.setText("<br>".join(_bol(self.thema, "goed" if a in gevonden else ("fout" if req else "let op"),
                                                 f"0x{a:02X} {naam}") for a, naam, req in EXPECTED_I2C))
        else:
            self.l_mon_velden.setText("geen antwoord" if mon.adres else "niet gekoppeld")
        if self.lijst_ev.count() != len(mon.gebeurtenissen[-200:]):
            self.lijst_ev.clear()
            for et, s in mon.gebeurtenissen[-200:]:
                self.lijst_ev.addItem(f"{datetime.fromtimestamp(et):%H:%M:%S}  {s}")
            self.lijst_ev.scrollToBottom()
        p = hv.proef
        self.k_stop.setEnabled(p is not None)
        c = p if isinstance(p, pv.Opstartcurve) else self.laatste_curve
        if c is not None:
            self.lijn_curve.setData([a for a, _, _ in c.pts], [i * 1000 for _, _, i in c.pts])
            self.lijn_grens.setPos(c.i_lim * 1000)
            self.l_curve.setText(c.status(t) if not c.klaar else c.tekst)
            self.l_curve_uitleg.setText(" ".join(c.uitleg) if c.klaar else "")
        if isinstance(p, pv.Opstartcurve) and p.label.startswith("bouwstap"):
            self.l_bouw_live.setText(p.status(t))
        elif isinstance(p, pv.Uitvaltest):
            self.l_bouw_live.setText(p.status(t))
        else:
            self.l_bouw_live.setText("")
        r = p if isinstance(p, pv.Rooktest) else self.laatste_rook
        if r is not None:
            for sleutel, naam in pv.ROOK_ITEMS:
                it = r.items[sleutel]
                self.rook_items[sleutel].setText(_bol(self.thema, it["st"], f"<b>{naam}</b>: {it['st']}" + (f" · {it['txt']}" if it["txt"] else "")))
            self.l_rook.setText(r.status(t) if not r.klaar else r.tekst)
            self.k_rook_basis.setEnabled(r.klaar and r.i is not None)
        n = p if isinstance(p, pv.Nachttest) else self.laatste_nacht
        if n is not None:
            self.l_nacht.setText(n.status(t) if not n.klaar else n.tekst)
            if self.lijst_nacht.count() != len(n.events):
                self.lijst_nacht.clear()
                for et, s in n.events:
                    self.lijst_nacht.addItem(f"{datetime.fromtimestamp(et):%H:%M:%S}  {s}")
        for soort, l in ((pv.Spanningscontrole, self.l_vcheck), (pv.IJken, self.l_ijken), (pv.UpsDuurtest, self.l_ups)):
            if isinstance(p, soort):
                l.setText(_bol(self.thema, "bezig", p.status(t)))
