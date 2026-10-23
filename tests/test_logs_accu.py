"""Oude logs lezen, logs vergelijken en de accu nabootsen."""

from pathlib import Path

import pytest

from koradpaneel.kern import logboek, vergelijk
from koradpaneel.kern.accu import Accu
from koradpaneel.kern.geschiedenis import Meting

OUDE_LOGS = Path(r"D:\Ronny\Tools\korad\logs")


def test_nieuw_log_schrijft_en_leest_rond(tmp_path):
    log = logboek.CsvLog()
    pad = log.start("proef", tmp_path)
    log.schrijf(Meting(100.0, 5.0, 0.1))
    log.markeer(100.5, "hier")
    log.schrijf(Meting(101.0, 5.0, 0.2))
    assert log.stop() == pad
    pts, markers = logboek.lees(pad)
    assert [p.i for p in pts] == [0.1, 0.2] and markers == [(100.5, "hier")]


def test_oud_logformaat_leest(tmp_path):
    pad = tmp_path / "oud.csv"
    pad.write_text("tijd,spanning_V,stroom_A,vermogen_W,modus,uitgang,lading_mAh,energie_Wh,markering,monitor_V,monitor_A,ups_V\n"
                   "2026-10-16T19:57:30.291,13.80,0.232,3.202,CV,aan,44.58,0.6152,\"telefoon: aan | nachttest: start\",13.44,0.230,4.18\n"
                   "2026-10-16T19:57:30.552,13.80,0.228,3.146,CV,aan,44.60,0.6155,,13.44,0.230,4.18\n", encoding="utf-8")
    pts, markers = logboek.lees(pad)
    assert len(pts) == 2 and pts[0].v == 13.8 and pts[1].i == 0.228
    assert [m for _, m in markers] == ["telefoon: aan", "nachttest: start"]


@pytest.mark.skipif(not OUDE_LOGS.exists(), reason="oude logs niet op deze pc")
def test_de_echte_oude_logs_lezen():
    for pad in sorted(OUDE_LOGS.glob("*.csv"))[-3:]:
        pts, _ = logboek.lees(pad)
        assert len(pts) >= 2, pad.name


def test_vergelijken():
    a = [Meting(0 + k, 13.8, 0.100) for k in range(11)]
    b = [Meting(50 + k, 13.8, 0.120) for k in range(11)]
    r = vergelijk.reeks(b, "stroom")
    assert r[0] == (0.0, 120.0) and r[-1][0] == 10.0
    rijen = vergelijk.rijen(a, b)
    assert rijen[0] == ("Duur", "0:10", "0:10", "")
    assert rijen[1] == ("Gemiddelde stroom", "100 mA", "120 mA", "+20 mA (+20,0 %)")
    html = vergelijk.rapport_html("a.csv", a, "b.csv", b, "stroom")
    assert "<polyline" in html and "+20 mA" in html
    assert vergelijk.rijen(a, None)[1][2] == "-"


def test_accu_nabootsen_zakt_mee_met_de_stroom():
    acc = Accu(13.8, 11.0, 100.0, r_ohm=0.5, grens_v=15.0)
    ops = acc.start(0.0)
    assert ops[0].v == 13.8 and "start 13,8 V" in ops[0].markering and "500 mΩ" in ops[0].markering
    ops = acc.tik(1.0, Meting(1.0, 13.8, 1.0))          # 1 A door 0,5 ohm: 0,5 V lager (eerste meting ongefilterd)
    assert ops and ops[0].v == pytest.approx(13.8 - 0.028 - 0.5, abs=0.02)
    assert acc.tik(1.1, Meting(1.1, 13.8, 1.0)) == []    # hooguit 4x per seconde
    for t in range(2, 101):
        ops = acc.tik(float(t), Meting(float(t), 13.0, 1.0))
    assert acc.klaar and "klaar op" in ops[-1].markering
    assert acc.v_laatst == pytest.approx(11.0 - 0.5, abs=0.01)
    assert "nog 0:00" in acc.status(100.0)


def test_accu_grenzen():
    with pytest.raises(ValueError):
        Accu(16.0, 11.0, 60, 0, grens_v=15.0)
    with pytest.raises(ValueError):
        Accu(13.0, 11.0, 0, 0)
