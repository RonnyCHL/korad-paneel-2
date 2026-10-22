"""De Korad KA3005PS over de seriële poort.

Protocol (gemeten met de echte voeding, zie het oude paneel): 9600 baud 8N1, commando's zonder regeleinde, antwoorden
zonder regeleinde. `VOUT1?` geeft bv. `05.00`, `IOUT1?` `0.131`, `STATUS?` één byte met bit 0 = CV (1) of CC (0)
en bit 6 = uitgang aan. Tussen twee commando's hoort een korte pauze, anders slikt de voeding er een in.

De poort kan maar door één programma tegelijk open zijn.
"""

from __future__ import annotations

import re
import threading
import time

import serial

from .basis import Stand, Vermogens, Voeding

_GETAL = re.compile(r"\d+\.\d+")


class Korad(Voeding):
    naam = "Korad KA3005PS"

    def __init__(self, poort: str, *, pauze: float = 0.08):
        self.poort = poort
        self.pauze = pauze
        self._s: serial.Serial | None = None
        self._lock = threading.Lock()
        self.idn = ""

    # ---- verbinding
    def verbind(self) -> str:
        self._s = serial.Serial(self.poort, 9600, timeout=0.1)
        time.sleep(0.2)
        self.idn = self._vraag("*IDN?").decode("ascii", "ignore").strip("\x00 \r\n")
        if not self.idn:
            self.sluit()
            raise OSError(f"geen antwoord op *IDN? op {self.poort}")
        return self.idn

    def sluit(self) -> None:
        s, self._s = self._s, None
        if s is not None:
            try:
                s.close()
            except Exception:  # noqa: BLE001
                pass

    def kan(self) -> Vermogens:
        return Vermogens(v_max=30.0, i_max=5.0, v_stap=0.01, i_stap=0.001, geheugens=4, ocp=True, ovp=True)

    # ---- laag niveau
    def _vraag(self, cmd: str, max_wacht: float = 0.5) -> bytes:
        s = self._s
        if s is None:
            raise OSError("niet verbonden")
        with self._lock:
            s.reset_input_buffer()
            s.write(cmd.encode("ascii"))
            data, start, laatst = b"", time.time(), None
            while time.time() - start < max_wacht:
                n = s.in_waiting
                if n:
                    data += s.read(n)
                    laatst = time.time()
                elif laatst and time.time() - laatst > 0.03:
                    break
                else:
                    time.sleep(0.005)
            time.sleep(0.02)
            return data

    def _schrijf(self, cmd: str) -> None:
        s = self._s
        if s is None:
            raise OSError("niet verbonden")
        with self._lock:
            s.write(cmd.encode("ascii"))
            time.sleep(self.pauze)

    def _getal(self, cmd: str) -> float | None:
        m = _GETAL.search(self._vraag(cmd).decode("ascii", "ignore"))
        return float(m.group()) if m else None

    # ---- de voeding
    def lees(self) -> Stand:
        v, i = self._getal("VOUT1?"), self._getal("IOUT1?")
        raw = self._vraag("STATUS?")
        if v is None or i is None or not raw:
            raise OSError("de voeding antwoordt niet")
        b = raw[0]
        return Stand(v_uit=v, i_uit=i, v_set=None, i_set=None, uitgang=bool(b & 0x40), cc=not (b & 0x01))

    def lees_instellingen(self) -> tuple[float, float]:
        v, i = self._getal("VSET1?"), self._getal("ISET1?")
        if v is None or i is None:
            raise OSError("de voeding antwoordt niet")
        return v, i

    def zet_spanning(self, v: float) -> None:
        self._schrijf(f"VSET1:{v:05.2f}")

    def zet_stroomgrens(self, i: float) -> None:
        self._schrijf(f"ISET1:{i:.3f}")

    def zet_uitgang(self, aan: bool) -> None:
        self._schrijf("OUT1" if aan else "OUT0")

    def geheugen_ophalen(self, n: int) -> None:
        self._schrijf(f"RCL{n}")

    def geheugen_bewaren(self, n: int) -> None:
        self._schrijf(f"SAV{n}")
