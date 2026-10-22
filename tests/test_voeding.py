"""De voedingen: de nagebootste met zijn natuurkunde, en de Korad-driver tegen een nagebootste seriële poort."""

import pytest

from koradpaneel.voeding import korad, nagebootst
from koradpaneel.voeding.basis import Stand


# ---------------------------------------------------------------- nagebootst
def test_gewone_belasting_in_cv():
    v = nagebootst.Nagebootst("belasting")
    v.verbind()
    v.zet_spanning(5.0)
    v.zet_stroomgrens(1.0)
    v.zet_uitgang(True)
    s = v.lees()
    assert (s.v_uit, s.i_uit, s.cc, s.uitgang) == (5.0, 0.15, False, True)


def test_kortsluiting_dwingt_cc_af():
    v = nagebootst.Nagebootst("kort")
    v.zet_spanning(13.8)
    v.zet_stroomgrens(0.5)
    v.zet_uitgang(True)
    s = v.lees()
    assert s.cc is True and s.i_uit == 0.5 and s.v_uit == pytest.approx(0.25, abs=0.01)


def test_uitgang_uit_is_nul():
    v = nagebootst.Nagebootst("print")
    v.zet_uitgang(False)
    s = v.lees()
    assert s.v_uit == 0.0 and s.i_uit == 0.0 and not s.uitgang


def test_een_led_in_cc_zit_op_zijn_doorlaatspanning():
    v = nagebootst.Nagebootst("led")
    v.zet_spanning(5.0)
    v.zet_stroomgrens(0.010)
    v.zet_uitgang(True)
    s = v.lees()
    assert s.cc and s.i_uit == 0.010 and 1.88 <= s.v_uit <= 1.92


def test_het_tbeam_bordje_trekt_80_ma_op_5_volt_en_niets_op_3_volt():
    v = nagebootst.Nagebootst("tbeam")
    v.zet_stroomgrens(2.0)
    v.zet_spanning(5.0)
    v.zet_uitgang(True)
    assert v.lees().i_uit == pytest.approx(0.080, abs=0.001)
    v.zet_spanning(3.0)
    assert v.lees().i_uit == 0.0


def test_geheugenknoppen_en_commandolog():
    v = nagebootst.Nagebootst()
    v.geheugen_ophalen(2)
    assert v.lees_instellingen() == (5.0, 1.0)
    v.zet_spanning(7.5)
    v.geheugen_bewaren(2)
    assert v.geheugen[2] == (7.5, 1.0)
    assert v.geschreven == ["RCL2", "VSET1:07.50", "SAV2"]


def test_een_voeding_die_weigert_gooit_oserror():
    v = nagebootst.Nagebootst()
    v.weigert = True
    with pytest.raises(OSError):
        v.lees()


# ---------------------------------------------------------------- korad-driver
class NepPoort:
    """Doet de seriële poort van de Korad na: commando's zonder regeleinde, antwoorden zonder regeleinde."""

    def __init__(self):
        self.vset, self.iset, self.out = 13.8, 0.5, False
        self.geschreven = []
        self._uit = b""

    @property
    def in_waiting(self):
        return len(self._uit)

    def reset_input_buffer(self):
        self._uit = b""

    def write(self, data: bytes):
        cmd = data.decode("ascii")
        self.geschreven.append(cmd)
        if cmd.startswith("VSET1:"):
            self.vset = float(cmd[6:])
        elif cmd.startswith("ISET1:"):
            self.iset = float(cmd[6:])
        elif cmd in ("OUT0", "OUT1"):
            self.out = cmd == "OUT1"
        self._uit = {"*IDN?": b"KORAD KA3005PS V1.5 SN:00106344", "VSET1?": f"{self.vset:05.2f}".encode(),
                     "ISET1?": f"{self.iset:.3f}".encode(),
                     "VOUT1?": f"{self.vset if self.out else 0:05.2f}".encode(),
                     "IOUT1?": b"0.131" if self.out else b"0.000",
                     "STATUS?": bytes([0x01 | (0x40 if self.out else 0)])}.get(cmd, b"")

    def read(self, n):
        d, self._uit = self._uit[:n], self._uit[n:]
        return d

    def close(self):
        pass


def test_de_korad_driver_praat_het_protocol(monkeypatch):
    nep = NepPoort()
    monkeypatch.setattr(korad.serial, "Serial", lambda *a, **k: nep)
    monkeypatch.setattr(korad.time, "sleep", lambda s: None)
    k = korad.Korad("COMX")
    assert k.verbind() == "KORAD KA3005PS V1.5 SN:00106344"
    k.zet_stroomgrens(2.0)
    k.zet_spanning(5.0)
    k.zet_uitgang(True)
    s = k.lees()
    assert isinstance(s, Stand)
    assert (s.v_uit, s.i_uit, s.uitgang, s.cc) == (5.0, 0.131, True, False)
    assert k.lees_instellingen() == (5.0, 2.0)
    assert nep.geschreven[1:4] == ["ISET1:2.000", "VSET1:05.00", "OUT1"]
    k.sluit()
    with pytest.raises(OSError):
        k.lees()
