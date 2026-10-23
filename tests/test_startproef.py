"""De startproef van het bordje als toestandsmachine, en het werkboek."""

from pathlib import Path

from koradpaneel.kern import startproef as sp_mod
from koradpaneel.kern.geschiedenis import Meting
from koradpaneel.kern.proeven import Ctx
from koradpaneel.kern.startproef import Startproef, oordeel, tabel_html


def tik(sp, t, m, regels):
    return sp.tik(Ctx(t=t, meting=m, regels=list(regels)))


def af(sp, reden, t):
    return sp.afronden(reden, Ctx(t=t))
from koradpaneel.kern.werkboek import Werkboek

GOED = "i2c-keuring: sda=1 scl=1 herstel=0->sda=1 bb jjj ack 34:j 68:j 76:j"
DOOD = "i2c-keuring: sda=1 scl=1 herstel=1->sda=1 bb nnn ack 34:n 68:n 76:n"
STATUS = "  i2c: sda=1 scl=1 herstel=0->sda=1 bb jjj ack 34:j 68:j 76:n | 2x herkeurd, nog dood"


def test_oordeel():
    assert oordeel("ack 34:j 68:j 76:j") == "goed"
    assert oordeel("ack 34:n 68:n 76:n") == "dood"
    assert oordeel("ack 34:j 68:j 76:n") == "half"


def test_statusregel_levert_ook_een_keuring():
    m = sp_mod.STATUS_I2C.search(STATUS)
    assert m and m.group(1).strip() == "sda=1 scl=1 herstel=0->sda=1 bb jjj ack 34:j 68:j 76:n"


def _ops(ops):
    return [(o.v, o.i, o.uit, o.apparaat, o.markering) for o in ops]


def test_een_hele_proef_van_twee_starts():
    sp = Startproef(2, uit_s=2, aan_s=40, momenten=(3.0, 10.0, 30.0))
    ops = sp.start(0.0)
    assert [(o.i, o.v) for o in ops[:2]] == [(2.0, None), (None, 5.0)]
    assert ops[2].apparaat == "pauze" and ops[3].uit is False
    assert tik(sp, 1.0, None, []) == []
    ops = tik(sp, 2.0, None, [])                          # start 1: hervat, uitgang aan
    assert [o.apparaat for o in ops][0] == "hervat" and ops[1].uit is True and ops[1].markering == "start 1"
    sp.poort(3.5, True, "COM6")
    assert sp.rij.poort_s == 1.5
    ops = tik(sp, 5.0, Meting(5.0, 5.0, 0.12), ["=== EMSN-auto 0.9.8 — X ===", GOED])
    assert ops == [] and sp.fw == "0.9.8" and sp.rij.oordeel == "goed" and sp.rij.boot_s == 3.0
    assert sp.rij.i == {3.0: 0.12}
    tik(sp, 13.0, Meting(13.0, 5.0, 0.08), [])
    tik(sp, 33.0, Meting(33.0, 5.0, 0.07), [])
    assert sp.rij.i == {3.0: 0.12, 10.0: 0.08, 30.0: 0.07}
    ops = tik(sp, 42.0, Meting(42.0, 5.0, 0.07), [])      # start 1 klaar: pauze, uitgang uit
    assert [o.apparaat for o in ops][0] == "pauze" and ops[1].uit is False
    assert len(sp.rijen) == 1 and sp.rijen[0].oordeel == "goed"
    sp.poort(42.1, False, "pauze")
    ops = tik(sp, 44.0, None, [])                         # start 2
    assert ops[1].markering == "start 2"
    sp.poort(46.0, True, "COM6")
    tik(sp, 47.0, Meting(47.0, 5.0, 0.3), [DOOD])
    ops = tik(sp, 84.0, Meting(84.0, 5.0, 0.3), [])
    assert sp.klaar and ops == []
    assert [r.oordeel for r in sp.rijen] == ["goed", "dood"]
    tekst = af(sp, "Klaar", 84.0)
    assert tekst == "Klaar: 2 starts, 1 goed, 1 dood, firmware 0.9.8." and sp.oordeel == "fout"
    html = tabel_html(sp)
    assert "<b>dood</b>" in html and "120 mA" in html and "1,5 s" in html


def test_herstartlus_en_geen_poort():
    sp = Startproef(2, uit_s=1, aan_s=32)
    sp.start(0.0)
    tik(sp, 1.0, None, [])
    sp.poort(2.0, True, "COM6")
    rom = ["ets Jul 29 2019 12:21:46", "rst:0x1 (POWERON_RESET),boot:0x12 (SPI_FAST_FLASH_BOOT)", "entry 0x400805e4"]
    for t in (3.0, 3.2, 3.4, 3.6):
        tik(sp, t, Meting(t, 5.0, 0.05), rom)
    tik(sp, 33.0, Meting(33.0, 5.0, 0.05), [])
    assert sp.rijen[0].oordeel == "lus" and sp.rijen[0].resets == 4
    sp.poort(33.1, False, "pauze")
    tik(sp, 34.0, None, [])
    sp.poort(35.0, False, "could not open port 'COM6'")
    tik(sp, 67.0, Meting(67.0, 5.0, 0.0), [])
    assert sp.klaar and sp.rijen[1].oordeel == "?" and "geen seriële poort" in sp.rijen[1].keuring
    af(sp, "Klaar", 67.0)
    assert "1 herstartlus" in sp.tekst and "1 onbekend" in sp.tekst and sp.oordeel == "fout"


def test_gestopt_halverwege_telt_de_lopende_start_mee_als_er_een_keuring_was():
    sp = Startproef(5, uit_s=1, aan_s=32)
    sp.start(0.0)
    tik(sp, 1.0, None, [])
    tik(sp, 3.0, Meting(3.0, 5.0, 0.1), [GOED])
    assert af(sp, "Gestopt", 4.0) == "Gestopt: 1 start, 1 goed, 0 dood."
    assert sp.oordeel == "goed" and sp.status(5.0) == sp.tekst


def test_status_tekst():
    sp = Startproef(3, uit_s=5, aan_s=45)
    sp.start(0.0)
    assert sp.status(2.0) == "start 1 van 3: uitgang uit, nog 3 s"
    tik(sp, 5.0, None, [])
    assert sp.status(7.0) == "start 1 van 3: aan sinds 2 s, poort terugzoeken, ?"
    sp.poort(8.0, True, "COM6")
    assert sp.status(9.0) == "start 1 van 3: aan sinds 4 s, poort na 3 s, ?"


def test_werkboek_leest_het_oude_formaat_en_bewaart(tmp_path):
    oud = tmp_path / "oud.json"
    oud.write_text('[{"t": 1791133637.05, "soort": "log", "titel": "korad_20261004_1905.csv", "pad": "x", '
                   '"uitleg": "gevonden"}, {"t": 1791135627.38, "soort": "rapport", "titel": "r.html"}, {"kapot": 1}]',
                   encoding="utf-8")
    wb = Werkboek(tmp_path / "werkboek.json")
    assert wb.laad(oud) == 2 and wb.laad(oud) == 0
    wb.voeg("startproef", "EMSN-auto startproef: Klaar", tmp_path / "r2.html", "3 starts")
    wb2 = Werkboek(tmp_path / "werkboek.json")
    assert wb2.laad() == 3 and wb2.regels[-1].soort == "startproef" and wb2.zoek("emsn")[0].titel.startswith("EMSN")
    (tmp_path / "rapporten").mkdir()
    (tmp_path / "rapporten" / "a.html").write_text("x")
    assert wb2.scan([(tmp_path / "rapporten", "*.html", "rapport")]) == 1 and len(wb2.per_dag()) >= 1


OUD_WERKBOEK = Path(r"D:\Ronny\Tools\korad\korad_werkboek.json")


def test_het_echte_oude_werkboek_leest(tmp_path):
    if not OUD_WERKBOEK.exists():
        return
    wb = Werkboek(tmp_path / "w.json")
    assert wb.laad(OUD_WERKBOEK) > 0
