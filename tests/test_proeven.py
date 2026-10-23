"""De proeven van CaraVan Guard als toestandsmachines, tegen een nagebootste geschiedenis en monitor."""

from koradpaneel.apparaat.monitor import MonitorBeeld, nieuwe_gebeurtenissen, velden
from koradpaneel.kern import proeven as pv
from koradpaneel.kern.geschiedenis import Geschiedenis, Meting


def _ctx(t, g, mon=None, v=13.8, i=0.1, cc=False, uitgang=True):
    g.voeg(Meting(t, v, i))
    return pv.Ctx(t=t, meting=g.laatste, cc=cc, uitgang=uitgang, v_set=v, i_set=1.0, geschiedenis=g, monitor=mon,
                  vmax=15.0, imax=4.0)


def test_monitor_velden_en_gebeurtenissen():
    f = velden({"bat": {"v": 13.4, "a": -0.23}, "bak": {"ok": 1, "v": 4.1}, "lt": {"ok": 1, "v": [0, 0, 0]},
                "fw": "2.4.0", "up": 120, "sys": {"i2c": [0x40], "sd": True}})
    assert f["a"] == 0.23 and f["ups_ok"] and f["i2c"] == [0x40]
    oud = [{"t": 3, "s": "c"}, {"t": 2, "s": "b"}, {"t": 1, "s": "a"}]
    nieuw = [{"t": 5, "s": "e"}, {"t": 4, "s": "d"}] + oud
    assert [e["s"] for e in nieuwe_gebeurtenissen(oud, nieuw)] == ["e", "d"]
    b = MonitorBeeld(adres="x")
    assert b.verwerk_stand(10.0, dict(f, up=100)) is None
    assert b.verwerk_stand(11.0, dict(f, up=3)) == "monitor herstart (draaide 1 min)"
    assert len(b.hist) == 2 and b.herstarts == [(11.0, 100)]


def test_opstartcurve_tot_het_eind():
    g = Geschiedenis()
    c = pv.Opstartcurve(2.0, 0.5, stap_v=1.0, wacht=0.5)
    ops = c.start(0.0)
    assert [o.uit for o in ops][:4] == [False, None, None, True] and ops[2].v == 0.0
    t = 0.0
    gestuurd = []
    while not c.klaar and t < 20:
        t += 0.25
        for o in c.tik(_ctx(t, g, v=c.v, i=0.002 * c.v)):
            if o.v is not None:
                gestuurd.append(o.v)
    assert c.klaar and c.ok and gestuurd == [1.0, 2.0] and c.i_end is not None
    assert "Geen bijzonderheden" in c.uitleg[0] and "Bij 2,0 V" in c.uitleg[-1]
    assert "<svg" in c.tabel_html(_ctx(t, g))


def test_opstartcurve_stopt_bij_de_stroomgrens():
    g = Geschiedenis()
    c = pv.Opstartcurve(13.8, 0.1, stap_v=0.5, wacht=0.4)
    c.start(0.0)
    t = 0.0
    ops = []
    while not c.klaar and t < 60:
        t += 0.2
        ops = c.tik(_ctx(t, g, v=c.v, i=min(0.1, 0.2 * c.v), cc=c.v >= 1.0))
    assert c.klaar and not c.ok and c.cc_at is not None and c.cc_at <= 1.5
    assert any(o.uit is False for o in ops) and "kortsluiting" in c.uitleg[0]


def test_bouwstappen_verwerken_en_rapport(tmp_path):
    b = pv.Bouwstappen(tmp_path / "bouw.json")
    c = pv.Opstartcurve(13.8, 0.1, label="bouwstap 1")
    c.pts, c.i_end, c.cc_at, c.uitleg, c.t1 = [(13.8, 13.8, 0.004)], 0.004, None, ["x"], 100.0
    oordeel, tekst = b.verwerk(1, c, None)
    assert oordeel == "goed" and "binnen de verwachting" in tekst and b.status(1) == "goed"
    c.i_end = 0.5
    assert b.verwerk(1, c, None)[0] == "let op"
    c.cc_at = 0.9
    assert b.verwerk(1, c, None)[0] == "zoeken"
    b.stand(0)["checks"] = [True, True, True]
    assert b.status(0) == "goed"
    html = b.rapport_html("Korad")
    assert "Stap 1" in html and "ZOEKEN" in html
    b2 = pv.Bouwstappen(tmp_path / "bouw.json")
    assert b2.status(0) is None or b2.status(1) == "zoeken"


def test_spanningscontrole():
    g, mon = Geschiedenis(), MonitorBeeld(adres="m")
    p = pv.Spanningscontrole(15.0, 13.8)
    ops = p.start(0.0)
    assert ops[-1].v == 10.5 and len(p.stappen) == 11
    t = 0.0
    while not p.klaar and t < 200:
        t += 0.5
        v = p.stappen[min(p.idx, 10)]
        mon.verwerk_stand(t, {"v": v + 0.05, "a": 0.1, "ups_ok": False, "ups_v": None})
        ops = p.tik(_ctx(t, g, mon, v=v))
    assert p.klaar and p.ok and abs(p.gem - 0.05) < 0.01 and ops[0].v == 13.8
    assert "binnen de nauwkeurigheid" in p.tekst and "<table>" in p.tabel_html(_ctx(t, g))


def test_ijken():
    g, mon = Geschiedenis(), MonitorBeeld(adres="m")
    p = pv.IJken(0.1)
    ops = p.start(0.0)
    assert len([o for o in ops if o.monitor]) == 3 and ops[1].monitor == {"c": "light", "i": 0, "v": 0}
    t = 0.0
    while not p.klaar and t < 100:
        t += 0.5
        pct = pv.CAL_STAPPEN[min(p.idx, 4)]
        i = 0.01 + pct / 100 * 3.0
        mon.verwerk_stand(t, {"v": 13.8, "a": i * 0.9, "ups_ok": False, "ups_v": None, "lt": [pct, pct, pct]})
        ops = p.tik(_ctx(t, g, mon, i=i))
    assert p.klaar and p.verhouding is not None and abs(p.verhouding - 1 / 0.9) < 0.01
    assert abs(p.cal_nieuw - 0.1 / 0.9) < 0.001 and ops[0].monitor["v"] == 0


def test_ups_duurtest():
    g, mon = Geschiedenis(), MonitorBeeld(adres="m")
    p = pv.UpsDuurtest(4.1, terug_aan=True)
    assert p.start(0.0)[0].uit is False
    for t in range(1, 50):
        mon.verwerk_stand(float(t), {"v": 0.0, "a": 0.2, "ups_ok": True, "ups_v": 4.1 - t * 0.01})
        assert p.tik(_ctx(float(t), g, mon, v=0.0, uitgang=False)) == []
    ops = p.tik(_ctx(90.0, g, mon, v=0.0, uitgang=False))
    assert p.klaar and ops[-1].uit is True and "49" in p.tekst and "3,61 V" in p.tekst


def test_nachttest_bijzonderheden():
    g, mon = Geschiedenis(), MonitorBeeld(adres="m")
    p = pv.Nachttest(1 / 3600 * 10, 13.8, 1.5, 1200, 10, uit_na=True)
    ops = p.start(0.0)
    assert ops[2].uit is True
    mon.verwerk_stand(0.5, {"v": 13.8, "a": 0.2, "ups_ok": False, "ups_v": None})
    ops = p.tik(_ctx(1.0, g, mon, i=1.5))
    assert any("stroompiek" in (o.markering or "") for o in ops)
    ops = p.tik(_ctx(2.0, g, mon, i=1.5))
    assert not any("stroompiek" in (o.markering or "") for o in ops)      # hooguit één per minuut
    p.tik(_ctx(3.0, g, mon, cc=True))
    ops = p.tik(_ctx(6.0, g, mon, cc=True))
    assert any("CC" in (o.markering or "") for o in ops)
    ops = p.tik(_ctx(11.0, g, mon))
    assert p.klaar and ops[-1].uit is False
    assert p.afronden("Klaar", _ctx(11.0, g, mon)).startswith("Nachttest klaar: 0:11, 3 bijzonderheden")


def test_rooktest_zonder_strips_en_uitval():
    g, mon = Geschiedenis(), MonitorBeeld(adres="m")
    p = pv.Rooktest("2.4.0", strips=False, uitval=False, basis=0.1)
    p.start(0.0)
    f = {"v": 13.85, "a": 0.1, "ups_ok": True, "ups_v": 4.1, "lt_ok": True, "lt": [0, 0, 0], "fw": "v2.4.0", "up": 500,
         "i2c": [0x40, 0x41, 0x48, 0x68, 0x57, 0x20, 0x76], "sd": True}
    t = 0.0
    while not p.klaar and t < 30:
        t += 0.5
        mon.verwerk_stand(t, dict(f, up=500 + t))
        p.tik(_ctx(t, g, mon))
    assert p.klaar and p.oordeel == "goed", p.items
    assert p.items["fw"]["st"] == "goed" and p.items["i2c"]["st"] == "goed" and p.items["herstart"]["st"] == "goed"
    assert p.items["strips"]["st"] == "overgeslagen" and "Rooktest GOED" in p.tekst


def test_rooktest_met_strips_en_uitval():
    g, mon = Geschiedenis(), MonitorBeeld(adres="m")
    p = pv.Rooktest("", strips=True, uitval=True, basis=None)
    p.start(0.0)
    f = {"v": 13.85, "a": 0.1, "ups_ok": True, "ups_v": 4.1, "lt_ok": True, "lt": [0, 0, 0], "fw": "2.4.0", "up": 500,
         "i2c": [0x40, 0x41, 0x48, 0x68, 0x57, 0x20], "sd": False}
    t, lt, uitgang, cmds = 0.0, [0, 0, 0], True, []
    while not p.klaar and t < 120:
        t += 0.5
        mon.verwerk_stand(t, dict(f, up=500 + t, lt=list(lt), v=13.85 if uitgang else 0.0))
        for o in p.tik(_ctx(t, g, mon, i=0.1 + 0.05 * (lt[0] / 20), uitgang=uitgang)):
            if o.monitor:
                lt[o.monitor["i"]] = o.monitor["v"]
                cmds.append(o.monitor)
            if o.uit is not None:
                uitgang = o.uit
                mon.gebeurtenissen.append((t, "12 V terug" if uitgang else "12 V weg"))
    assert p.klaar and cmds == [{"c": "light", "i": 0, "v": 20}, {"c": "light", "i": 0, "v": 0}]
    assert p.items["strips"]["st"] == "goed" and p.items["uitval"]["st"] == "goed", p.items
    assert p.items["sd"]["st"] == "let op" and p.items["stroom"]["st"] == "info" and p.oordeel == "letop"


def test_onderdeel_diode_en_weerstand():
    g = Geschiedenis()
    p = pv.Onderdeel("diode", 13.8, 1.0, 15.0, 4.0)
    ops = p.start(0.0)
    assert ops[1].i == 0.010 and ops[2].v == 5.0 and ops[3].uit is True
    t = 0.0
    while not p.klaar and t < 10:
        t += 0.25
        ops = p.tik(_ctx(t, g, v=0.68, i=0.010, cc=True))
    assert p.klaar and p.kop.startswith("Diode: 0,68 V") and ops[0].uit is False and ops[1].i == 1.0 and ops[2].v == 13.8
    assert pv.part_verdict("weerstand", 1.0, 0.030, False)[0] == "33,3 Ω"
    assert pv.part_verdict("tvs", 18.0, 0.001, True)[0] == "Doorslag bij 18,0 V"
    p = pv.Onderdeel("tvs", None, None, 15.0, 4.0)
    ops = p.start(0.0)
    assert ops[1].i == 0.005 and ops[2].v == 14.0
    t = 0.0
    while p.fase == "voor" and t < 15:
        t += 0.25
        ops = p.tik(_ctx(t, g, v=14.0, i=0.0))
    assert p.fase == "meet" and ops[0].i == 0.001 and ops[1].v == 25.0
