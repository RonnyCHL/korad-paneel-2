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
def klaar():
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
