"""Bewaking en rapport, zonder scherm."""

import json

from koradpaneel.kern import bewaking, rapport
from koradpaneel.kern.geschiedenis import Meting


def metingen(i_ma, n=20, t0=1000.0, v=5.0):
    return [Meting(t=t0 + k, v=v, i=i_ma / 1000.0) for k in range(n)]


def test_een_regel_gaat_pas_na_de_duur_af_en_daarna_een_keer():
    b = bewaking.Bewaking([bewaking.Regel(True, "stroom", "boven", 300.0, 5.0, "uitgang uit")])
    af = [g for m in metingen(400) for g in b.evalueer(m)]
    assert len(af) == 1 and af[0].t == 1005.0           # 5 s ononderbroken boven 300 mA
    assert af[0].tekst == "bewaking: stroom boven 300 mA 5 s → uitgang uit"


def test_een_onderbreking_zet_de_klok_terug():
    b = bewaking.Bewaking([bewaking.Regel(True, "stroom", "boven", 300.0, 5.0, "uitgang uit")])
    reeks = metingen(400, 4) + metingen(100, 1, t0=1004) + metingen(400, 4, t0=1005)
    assert not [g for m in reeks for g in b.evalueer(m)]


def test_regels_die_uit_staan_doen_niets_en_spanning_onder_werkt():
    b = bewaking.Bewaking([bewaking.Regel(False, "stroom", "boven", 1.0, 1.0),
                           bewaking.Regel(True, "spanning", "onder", 4.5, 2.0, "waarschuwen")])
    af = [g for m in metingen(50, v=4.0) for g in b.evalueer(m)]
    assert len(af) == 1 and af[0].regel.actie == "waarschuwen"


def test_het_oude_bestandsformaat_wordt_gelezen(tmp_path):
    pad = tmp_path / "korad_bewaking.json"
    pad.write_text(json.dumps([{"aan": True, "wat": "vermogen", "richting": "boven", "waarde": 12.5, "duur": 3.0,
                                "actie": "waarschuwen"}]), encoding="utf-8")
    b = bewaking.Bewaking()
    b.laad(pad)
    assert b.regels[0].aan and b.regels[0].wat == "vermogen" and b.regels[0].waarde == 12.5
    assert len(b.regels) == 3 and not b.regels[1].aan
    b.bewaar(pad)
    assert json.loads(pad.read_text(encoding="utf-8"))[0]["waarde"] == 12.5


def test_het_rapport_bevat_de_getallen_en_de_grafiek(tmp_path):
    pts = metingen(80, 30)
    pagina = rapport.maak("Proef", pts, [(1010.0, "start 3")], apparaat="KORAD KA3005PS", project="EMSN-auto",
                          v_set=5.0, i_set=2.0, oordeel="Klaar: 20 goed", toelichting="alles in orde")
    assert "<svg" in pagina and "start 3" in pagina and "80 mA" in pagina and "EMSN-auto" in pagina
    assert "0,64 mAh" in pagina                      # 29 s x 80 mA
    pad = rapport.bewaar(pagina, "proef", tmp_path)
    assert pad.exists() and pad.name.startswith("proef_")


def test_een_rapport_zonder_metingen_valt_niet_om():
    pagina = rapport.maak("Leeg", [], [])
    assert "Leeg" in pagina and "<svg" not in pagina
