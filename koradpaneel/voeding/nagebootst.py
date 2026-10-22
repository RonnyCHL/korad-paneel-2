"""De nagebootste voeding: dezelfde laag als de Korad, maar met natuurkunde in plaats van een kabel.

Hiermee is het hele paneel te testen zonder dat de voeding aan de pc hangt, en kan Ronny oefenen zonder risico.
De belastingsmodellen komen uit de proef van het oude paneel (tests/proef_paneel.py): gewone belasting, de
CaraVan-print met LM2596, kortsluiting, lekstroom, losse onderdelen (diode, led, weerstand, TVS), en nieuw: het
T-Beam-bordje (~80 mA, piek bij het opstarten) en een accu die geladen wordt.
"""

from __future__ import annotations

import threading
import time

from .basis import Stand, Vermogens, Voeding

MODELLEN = {
    "belasting": "Gewone belasting (0,15 A boven 0,5 V)",
    "print": "CaraVan-print met LM2596, onbelast",
    "tbeam": "T-Beam-bordje (80 mA, piek 160 mA na het opstarten)",
    "accu": "Accu aan de lader (laadstroom zakt als hij vol raakt)",
    "kort": "Kortsluiting (0,5 ohm)",
    "lek": "Lekstroom (20 mA)",
    "diode": "Siliciumdiode (10 mA bij 0,65 V)",
    "led": "Rode led (10 mA bij 1,9 V)",
    "r33": "Weerstand 33 ohm",
    "tvs": "TVS-diode 1.5KE18A (doorslag ~17,9 V)",
    "open": "Niets aangesloten",
}
NIET_LINEAIR = {"diode", "led", "tvs", "tbeam", "accu"}


class Nagebootst(Voeding):
    naam = "Nagebootste voeding"

    def __init__(self, model: str = "belasting", *, strips_pct: float = 0.0):
        self.model = model
        self.strips_pct = strips_pct        # CaraVan Guard: ledstrips 0..100 %
        self.v_set, self.i_set, self.uitgang = 13.8, 0.5, True   # zoals het oude paneel: de uitgang stond aan
        self.geheugen = {1: (3.3, 0.5), 2: (5.0, 1.0), 3: (12.0, 0.5), 4: (13.8, 0.5)}
        self.verbonden = False
        self.vertraging = 0.0               # seconden per aanroep, om de echte voeding na te doen
        self.weigert = False                # True = antwoordt niet meer (kabel eruit)
        self._aan_sinds = time.time()
        self._accu_mah = 0.0
        self._lock = threading.Lock()
        self.geschreven: list[str] = []     # voor de toetsen: wat er naar de voeding ging

    # ---- natuurkunde
    def vraagstroom(self, v: float) -> float:
        """Stroom die de belasting bij spanning v wil trekken."""
        m = self.model
        strips = self.strips_pct / 100 * 1.0 * (v / 13.8)
        if m == "open":
            return 0.0
        if m == "diode":
            return max(0.0, v - 0.60) * 0.2
        if m == "led":
            return max(0.0, v - 1.85) * 0.2
        if m == "r33":
            return v / 33.0
        if m == "tvs":
            return 1e-7 * v + max(0.0, v - 17.90) * 0.05
        if m == "kort":
            return v / 0.5
        if m == "lek":
            return 0.020 + v / 120000
        if m == "print":
            return v / 120000 + (0.25 / max(v, 4.5) if v >= 4.0 else 0.0) + strips
        if m == "tbeam":
            if v < 3.5:
                return 0.0
            t = time.time() - self._aan_sinds
            piek = 0.08 if 6 < t < 14 else 0.0     # bluetooth en wifi zoeken na het opstarten
            return 0.080 + piek
        if m == "accu":
            vol = min(1.0, self._accu_mah / 3000.0)
            return max(0.0, (v - 3.7) * 1.2) * (1.0 - vol) + 0.08 if v > 3.7 else 0.0
        return (0.15 if v > 0.5 else 0.0) + strips

    def _toestand(self) -> tuple[float, float, bool]:
        """(v_uit, i_uit, cv)"""
        if not self.uitgang:
            return 0.0, 0.0, True
        d = self.vraagstroom(self.v_set)
        if d > self.i_set:
            if self.model in NIET_LINEAIR:
                lo, hi = 0.0, self.v_set
                for _ in range(50):
                    mid = (lo + hi) / 2
                    if self.vraagstroom(mid) > self.i_set:
                        hi = mid
                    else:
                        lo = mid
                return lo, self.i_set, False
            return self.v_set * self.i_set / d, self.i_set, False
        return self.v_set, d, True

    def _wacht(self):
        if self.vertraging:
            time.sleep(self.vertraging)
        if self.weigert:
            raise OSError("de voeding antwoordt niet")

    # ---- de voeding
    def verbind(self) -> str:
        self._wacht()
        self.verbonden = True
        return "KORAD KA3005PS V1.5 SN:NAGEBOOTST"

    def sluit(self) -> None:
        self.verbonden = False

    def kan(self) -> Vermogens:
        return Vermogens(v_max=30.0, i_max=5.0, geheugens=4, ocp=True, ovp=True)

    def lees(self) -> Stand:
        self._wacht()
        with self._lock:
            v, i, cv = self._toestand()
            if self.model == "accu" and self.uitgang:
                self._accu_mah += i * 0.2 / 3.6 * 50      # de nagebootste accu laadt 50x zo snel
            return Stand(v_uit=round(v, 2), i_uit=round(i, 3), v_set=self.v_set, i_set=self.i_set,
                         uitgang=self.uitgang, cc=not cv)

    def lees_instellingen(self) -> tuple[float, float]:
        self._wacht()
        return self.v_set, self.i_set

    def zet_spanning(self, v: float) -> None:
        self._wacht()
        self.geschreven.append(f"VSET1:{v:05.2f}")
        with self._lock:
            self.v_set = round(v, 2)

    def zet_stroomgrens(self, i: float) -> None:
        self._wacht()
        self.geschreven.append(f"ISET1:{i:.3f}")
        with self._lock:
            self.i_set = round(i, 3)

    def zet_uitgang(self, aan: bool) -> None:
        self._wacht()
        self.geschreven.append("OUT1" if aan else "OUT0")
        with self._lock:
            if aan and not self.uitgang:
                self._aan_sinds = time.time()
            self.uitgang = aan

    def geheugen_ophalen(self, n: int) -> None:
        self._wacht()
        self.geschreven.append(f"RCL{n}")
        with self._lock:
            self.v_set, self.i_set = self.geheugen.get(n, (self.v_set, self.i_set))

    def geheugen_bewaren(self, n: int) -> None:
        self._wacht()
        self.geschreven.append(f"SAV{n}")
        self.geheugen[n] = (self.v_set, self.i_set)
