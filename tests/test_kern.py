"""De kern zonder scherm: grenzen en geschiedenis."""

from koradpaneel.kern import geschiedenis as g
from koradpaneel.kern import grenzen


def test_de_grens_van_emsn_auto_laat_5_volt_toe_en_13_8_niet():
    p = grenzen.project("emsn")
    assert p.binnen(5.0, 2.0)
    assert not p.binnen(13.8, 0.5)
    assert p.knip(13.8, 0.5) == (5.5, 0.5)
    assert "5,5 V" in p.titel and "AXP2101" in p.uitleg()


def test_een_onbekend_project_valt_terug_op_caravan():
    assert grenzen.project("bestaat-niet").sleutel == "caravan"
    assert grenzen.project(None).vmax == 15.0


def test_de_geschiedenis_telt_lading_als_trapezium():
    h = g.Geschiedenis()
    for k in range(11):                          # 10 s lang 0,36 A = 1 mAh
        h.voeg(g.Meting(t=1000 + k, v=5.0, i=0.36))
    w = h.venster(1000, 1010)
    assert w.n == 11 and w.i_gem == 0.36
    assert abs(w.mah - 1.0) < 1e-9
    assert abs(w.wh - 0.005) < 1e-9


def test_een_gat_in_de_meting_telt_niet_mee():
    h = g.Geschiedenis()
    h.voeg(g.Meting(1000, 5.0, 1.0))
    h.voeg(g.Meting(1100, 5.0, 1.0))             # 100 s later: geen meting ertussen
    assert h.venster(1000, 1100).mah == 0.0


def test_tussen_pakt_precies_het_venster():
    h = g.Geschiedenis()
    for k in range(100):
        h.voeg(g.Meting(k, 1.0, 0.1))
    assert [m.t for m in h.tussen(10, 12)] == [10, 11, 12]
    assert h.venster(500, 600) is None


def test_de_energieteller_loopt_en_gaat_op_nul():
    e = g.Energieteller()
    for k in range(4):
        e.tel(g.Meting(t=k, v=10.0, i=3.6))      # 3 s x 3,6 A = 3 mAh, 0,03 Wh
    assert abs(e.mah - 3.0) < 1e-9 and abs(e.wh - 0.03) < 1e-9 and e.duur == 3
    e.op_nul(10)
    assert e.mah == 0.0 and e.sinds == 10
