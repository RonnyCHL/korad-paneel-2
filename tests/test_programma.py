"""Testprogramma's: het bestandsformaat van het oude paneel, en de loop die ze uitvoert."""

import json
from pathlib import Path

import pytest

from koradpaneel.kern import programma as pr
from koradpaneel.kern.geschiedenis import Meting

OUD = Path(r"D:\Ronny\Tools\korad\testprogrammas")


def test_duur_in_alle_spellingen():
    assert pr.duur_s(60) == 60 and pr.duur_s("1:30") == 90 and pr.duur_s("45 s") == 45 and pr.duur_s("2 min") == 120
    with pytest.raises(ValueError):
        pr.duur_s("straks")


def test_het_oude_formaat_leest_en_schrijft_rond(tmp_path):
    d = {"naam": "proef", "omschrijving": "x", "herhalen": 2, "uit_na_afloop": False,
         "stappen": [{"overgang": "sprong", "v": 13.8, "i": 1.5, "uit": "aan", "duur": "0:10",
                      "verwacht": {"i_min": 20, "i_max": None, "na": 2, "melding": ""}},
                     {"overgang": "helling", "v": 11.0, "i": 1.5, "uit": "aan", "duur": 20}]}
    p = pr.Programma.uit_dict(d)
    assert p.herhalen == 2 and p.stappen[0].duur == 10 and p.stappen[0].verwacht.i_min == 20
    assert p.stappen[1].verwacht is None and p.duur == 60
    pad = tmp_path / "p.json"
    p.bewaar(pad)
    assert pr.Programma.laad(pad).naar_dict()["stappen"][0]["verwacht"]["na"] == 2


@pytest.mark.skipif(not OUD.exists(), reason="oude programma's niet op deze pc")
def test_alle_programmas_van_het_oude_paneel_laden():
    paden = pr.lijst(OUD)
    assert len(paden) >= 9
    for pad in paden:
        p = pr.Programma.laad(pad)
        assert p.stappen and p.duur > 0, pad.name


def test_de_loop_doorloopt_sprong_helling_en_herhaling():
    p = pr.Programma(herhalen=2, uit_na_afloop=True, stappen=[
        pr.Stap("sprong", 5.0, 1.0, "aan", 2.0), pr.Stap("helling", 1.0, 1.0, "aan", 4.0), pr.Stap("sprong", 5.0, 1.0, "uit", 1.0)])
    loop = pr.Loop(p, grens_v=30.0, grens_i=5.0)
    ops = loop.start(0.0)
    assert ops[0].v == 5.0 and ops[0].i == 1.0 and ops[0].uit is True and "stap 1" in ops[0].markering
    alle = []
    for k in range(1, 20):
        alle += loop.tik(float(k), Meting(float(k), 5.0, 0.1))
    spanningen = [o.v for o in alle if o.v is not None]
    assert 3.0 in spanningen and 1.0 in spanningen            # de helling van 5 naar 1 passeert 3 V
    assert loop.klaar and alle[-1].uit is False               # uit na afloop
    assert loop.herhaling == 2


def test_verwachtingen_worden_beoordeeld_na_het_wachten():
    p = pr.Programma(stappen=[pr.Stap("sprong", 5.0, 1.0, "aan", 10.0, pr.Verwachting(i_min=50, i_max=150, na=5)),
                              pr.Stap("sprong", 5.0, 1.0, "aan", 4.0, pr.Verwachting(melding="12 V weg"))])
    loop = pr.Loop(p, 30.0, 5.0)
    loop.start(0.0)
    for k in range(1, 11):                                     # eerste 5 s 500 mA (telt niet), daarna 100 mA
        loop.tik(float(k), Meting(float(k), 5.0, 0.5 if k < 5 else 0.1))
    assert loop.uitslagen[0].goed is True and "100 mA" in loop.uitslagen[0].tekst
    loop.meld("Monitor: 12 V weg")
    for k in range(11, 16):
        loop.tik(float(k), Meting(float(k), 5.0, 0.1))
    assert loop.klaar and loop.uitslagen[1].goed is True
    assert loop.samenvatting() == (2, 0)


def test_de_grens_knipt_een_programma_af():
    p = pr.Programma(stappen=[pr.Stap("sprong", 13.8, 1.5, "aan", 1.0)])
    loop = pr.Loop(p, grens_v=5.5, grens_i=2.0)
    op = loop.start(0.0)[0]
    assert op.v == 5.5 and op.i == 1.5


def test_het_verloop_voor_de_voorbeeldgrafiek():
    p = pr.Programma(stappen=[pr.Stap("sprong", 4.0, 1.0, "aan", 2.0), pr.Stap("helling", 0.0, 1.0, "aan", 4.0),
                              pr.Stap("sprong", 4.0, 1.0, "uit", 1.0)])
    v = p.verloop()
    assert [x[1] for x in v] == [4.0, 4.0, 3.0, 2.0, 1.0, 0.0, 0.0] and v[-1][2] is False
