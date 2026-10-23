"""Het paneel starten tegen de nagebootste voeding, even laten draaien en een schermafdruk maken (voor de bouw)."""
import os, sys, time
import faulthandler; faulthandler.dump_traceback_later(25, exit=True)
# Het echte platform (lettertypen!), maar het venster komt niet op het scherm: WA_DontShowOnScreen.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from koradpaneel.ui.hoofdvenster import Hoofdvenster
from koradpaneel.voeding import nagebootst

model = sys.argv[1] if len(sys.argv) > 1 else "tbeam"
uit = sys.argv[2] if len(sys.argv) > 2 else "schermafdruk.png"
indeling = sys.argv[3] if len(sys.argv) > 3 else "eenvoudig"
wacht_ms = int(sys.argv[4]) if len(sys.argv) > 4 else 2500
app = QApplication([])
app.setStyle("Fusion")
v = nagebootst.Nagebootst(model)
v.v_set, v.i_set, v.uitgang = 5.0, 2.0, True
venster = Hoofdvenster(lambda _p: v, inst={"project": "emsn", "thema": "donker", "poort": "",
    "indeling": {"emsn": indeling}, "geheugens": {"1": "3,3 V\n0,5 A", "2": "5 V\n1 A", "3": "12 V\n0,5 A", "4": "13,8 V\n0,5 A"}})
venster.setAttribute(Qt.WA_DontShowOnScreen, True)
venster.show()
if os.environ.get("KP_PROEF"):
    # bewaking en rapport beproeven zonder vensters op het scherm
    from koradpaneel.kern.bewaking import Regel
    import webbrowser
    venster.bewaking.regels[0] = Regel(True, "stroom", "boven", 50.0, 2.0, "waarschuwen")
    venster.uitgebreid.toon_bewaking(venster.bewaking.regels, venster.bewaking.actief)
    venster._alarm = lambda tekst: print("ALARM:", tekst)
    webbrowser.open = lambda url: print("RAPPORT:", url)
    QTimer.singleShot(wacht_ms - 300, lambda: venster._rapport(time.time() - 60, time.time(), "Proef"))
if os.environ.get("KP_PROGRAMMA"):
    # een kort testprogramma draaien tegen de nagebootste voeding, met een verwachting
    from koradpaneel.kern import programma as pr
    import webbrowser
    webbrowser.open = lambda url: print("RAPPORT:", url)
    prog = pr.Programma(naam="proef kort", stappen=[
        pr.Stap("sprong", 5.0, 1.0, "aan", 2.0, pr.Verwachting(i_min=50, i_max=150, na=0.5)),
        pr.Stap("sprong", 5.0, 1.0, "uit", 1.0),
        pr.Stap("helling", 3.0, 1.0, "aan", 2.0)])
    QTimer.singleShot(600, lambda: venster._start_programma(prog))
    QTimer.singleShot(2200, lambda: print("LOPEND:", venster.uitgebreid.l_proef_tekst.text()))
if os.environ.get("KP_STARTPROEF"):
    # de startproef tegen het nagebootste bordje: 3 starts, kort
    from koradpaneel.apparaat.bordje import NagebootstBordje
    from koradpaneel.kern import startproef as sp_mod
    import webbrowser
    webbrowser.open = lambda url: print("RAPPORT:", url)
    _Orig = sp_mod.Startproef
    class _Kort(_Orig):                      # korte momenten, maar wel een echte klasse (isinstance in het paneel)
        def __init__(self, n, u, a, **kw):
            super().__init__(n, u, a, momenten=(0.5, 1.0, 2.0), **kw)
    sp_mod.Startproef = _Kort
    venster.maak_bordje = lambda _p: NagebootstBordje("wissel", poort_s=0.3, boot_s=0.6)
    venster.inst.setdefault("emsn", {})
    QTimer.singleShot(400, lambda: (venster._startproef_venster(), venster.sp_venster.setAttribute(Qt.WA_DontShowOnScreen, True)))
    QTimer.singleShot(600, lambda: venster._start_startproef(3, 1.0, 3.0, "COM6"))
    QTimer.singleShot(wacht_ms - 400, lambda: print("STARTPROEF:", venster.l_voet.text(), "| rijen:",
                                                     [(r.nr, r.oordeel, r.poort_s) for r in (venster.startproef.rijen if venster.startproef else [])]))
if os.environ.get("KP_VENSTERS"):
    # de vensters van stap 2d: werkboek, log bekijken, logs vergelijken (met de oude logs van het tkinter-paneel)
    from pathlib import Path
    from koradpaneel.kern import logboek
    oude = sorted(Path(r"D:\Ronny\Tools\korad\logs").glob("*.csv"))
    def vensters():
        venster._werkboek()
        venster._log(True)
    def vensters2():
        venster._log(False)
        if oude:
            venster._log_openen(oude[-1])
        venster._logs_vergelijken()
        d = venster.vensters[-1]
        for s, pad in zip(("A", "B"), oude[-2:]):
            d.logs[s] = (pad, logboek.lees(pad)[0])
        d._ververs()
        for k, d in enumerate(venster.vensters):
            d.setAttribute(Qt.WA_DontShowOnScreen, True)
    QTimer.singleShot(300, vensters)
    QTimer.singleShot(wacht_ms - 900, vensters2)
if os.environ.get("KP_STAP4"):
    # instellingen, zoeken, en thema wisselen zonder herstart
    def open_dialogen():
        venster.telefoon.poort = 0
        d = InstellingenDialoog(venster.thema, venster.inst, venster.meldingen, venster.telefoon, venster)
        d.setStyleSheet(qss(venster.thema))
        d.setAttribute(Qt.WA_DontShowOnScreen, True)
        d.show()
        d._web_schakel()
        z = ZoekDialoog(venster.menu, venster)
        z.setStyleSheet(qss(venster.thema))
        z.setAttribute(Qt.WA_DontShowOnScreen, True)
        z.veld.setText("rap")
        z.show()
        venster.vensters += [d, z]
        print("ZOEK:", [z.lijst.item(k).text() for k in range(z.lijst.count())])
        print("TELEFOON:", venster.telefoon.url())
    def wissel():
        for d in venster.vensters:
            d.grab().save(uit.replace(".png", f"-{type(d).__name__.lower()}.png"))
            d.close()
        venster.markeer("voor de wissel")
        venster._kies_thema("licht")
        print("THEMA:", venster.thema.naam, "| markeringen in grafiek:", len(venster.uitgebreid.grafiek.markers),
              "| stapel:", venster.stapel.currentWidget().__class__.__name__)
    from koradpaneel.ui.instellingen_dialoog import InstellingenDialoog
    from koradpaneel.ui.zoek_dialoog import ZoekDialoog
    from koradpaneel.ui.thema import qss
    QTimer.singleShot(500, open_dialogen)
    QTimer.singleShot(wacht_ms - 1200, wissel)
if os.environ.get("KP_CARAVAN"):
    # CaraVan Guard met de nagebootste monitor: koppelen, opstartcurve, rooktest; en de onderdelentester
    from koradpaneel.apparaat.monitor import NagebootstMonitor
    from koradpaneel.kern import proeven as pv
    import webbrowser
    webbrowser.open = lambda url: print("RAPPORT:", url)
    venster.maak_monitor = lambda adres: NagebootstMonitor(adres, stil_ms=300)
    venster.inst["project"] = "caravan"
    venster._project_gekozen(0)
    QMessageBox_ja = lambda *a, **k: 16384
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.question = staticmethod(QMessageBox_ja)
    def open_cv():
        venster._caravan_venster()
        venster.cv_venster.setAttribute(Qt.WA_DontShowOnScreen, True)
        venster._koppel_monitor("caravan.local")
        venster._onderdelen_venster()
        venster.od_venster.setAttribute(Qt.WA_DontShowOnScreen, True)
        venster.vensters += [venster.cv_venster, venster.od_venster]
    def curve():
        ok = venster._start_curve(13.8, 0.5, stap_v=2.0, wacht=0.3)
        print("CURVE GESTART:", ok, type(venster.proef).__name__, "| uitgang", v.uitgang, "| v_set", v.v_set)
    def rook():
        print("CURVE:", venster.cv_venster.laatste_curve and venster.cv_venster.laatste_curve.tekst, "| proef nu:", type(venster.proef).__name__, "| uitgang", v.uitgang, v.v_set, "| mon:", venster.mon.laatste and venster.mon.laatste.get("v"))
        venster._start_rook("2.4.0", True, False)
    def onderdeel():
        print("ROOK:", venster.laatste_rook and venster.laatste_rook.tekst)
        venster.cv_venster.tabs.setCurrentIndex(4)
        venster._start_onderdeel("weerstand")
    QTimer.singleShot(400, open_cv)
    QTimer.singleShot(1500, curve)
    QTimer.singleShot(6000, rook)
    QTimer.singleShot(14000, onderdeel)
def klaar():
    if os.environ.get("KP_CARAVAN"):
        print("ONDERDEEL:", venster.od_venster.l_kop.text(), "| monitor:", venster.mon.regel())
        for d in venster.vensters:
            d.grab().save(uit.replace(".png", f"-{type(d).__name__.lower()}.png"))
    if os.environ.get("KP_VENSTERS"):
        for k, d in enumerate(venster.vensters):
            d.grab().save(uit.replace(".png", f"-{type(d).__name__.lower()}.png"))
            print("venster", type(d).__name__, d.size())
    if os.environ.get("KP_STARTPROEF") and venster.sp_venster is not None:
        venster.sp_venster.grab().save(uit.replace(".png", "-venster.png"))
        print("UITSLAG:", venster.sp_venster.l_uitslag.text())
    if os.environ.get("KP_PROGRAMMA"):
        print("UITSLAG:", venster.l_voet.text(), "| markeringen:", [m[1] for m in venster.uitgebreid.grafiek.markers][-6:])
    venster.grab().save(uit)
    print("geschreven", uit, "| metingen", len(venster.geschiedenis), "| v_set", venster.v_set, "| uitgang", venster.uitgang)
    venster.werker.stop()
    venster.werker = None          # anders vraagt closeEvent (modaal) of de uitgang uit mag
    app.quit()
def tussendoor():
    venster.markeer("proef: markering")
    v.zet_uitgang(False)
    QTimer.singleShot(1500, lambda: v.zet_uitgang(True))
if indeling in ("uitgebreid", "meetbank"):
    QTimer.singleShot(max(500, wacht_ms // 2), tussendoor)
if indeling == "meetbank":
    QTimer.singleShot(wacht_ms - 600, venster.meetbank._cursors)
QTimer.singleShot(wacht_ms, klaar)
sys.exit(app.exec())
