"""Accu nabootsen: de spanning loopt in `duur_s` seconden lineair van v0 naar v1, en zakt daarbij mee met de
stroom door een inwendige weerstand R (bronspanning min stroom maal R), zoals een echte accu onder belasting.

Hetzelfde als de accusimulatie van het oude paneel: de stroom wordt licht gefilterd (0,6/0,4) en er gaat hooguit
vier keer per seconde een nieuwe spanning naar de voeding, en alleen als die 0,01 V of meer verschilt.
"""

from __future__ import annotations

from .programma import Opdracht
from .proeven import Ctx, Proef


class Accu(Proef):
    soort = "accu"

    def __init__(self, v0: float, v1: float, duur_s: float, r_ohm: float = 0.0, grens_v: float = 30.0):
        if duur_s <= 0 or r_ohm < 0 or not (0 <= v0 <= grens_v and 0 <= v1 <= grens_v):
            raise ValueError("buiten bereik")
        super().__init__()
        self.v0, self.v1, self.duur_s, self.r, self.grens_v = v0, v1, duur_s, r_ohm, grens_v
        self.t_start = 0.0
        self.i_f: float | None = None
        self.v_bron = v0
        self.v_laatst: float | None = None
        self.t_gestuurd = 0.0

    @property
    def naam(self) -> str:
        return f"Accu nabootsen {self.v0:g} → {self.v1:g} V".replace(".", ",")

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = t
        self.v_bron = self.v0
        v = self._spanning()
        self.v_laatst, self.t_gestuurd = v, t
        r = f", R {self.r * 1000:g} mΩ" if self.r else ""
        return [Opdracht(v=v, markering=f"accu nabootsen: start {v:g} V{r}".replace(".", ","))]

    @property
    def voortgang(self) -> float:
        return 0.0 if self.duur_s <= 0 else min(1.0, self._frac)

    @property
    def _frac(self) -> float:
        return getattr(self, "_f", 0.0)

    def _spanning(self) -> float:
        return round(max(0.0, min(self.grens_v, self.v_bron - (self.i_f or 0.0) * self.r)), 2)

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar:
            return []
        t, m = ctx.t, ctx.meting
        if m is not None:
            self.i_f = m.i if self.i_f is None else 0.6 * self.i_f + 0.4 * m.i
        self._f = min(1.0, (t - self.t_start) / self.duur_s)
        self.v_bron = self.v0 + (self.v1 - self.v0) * self._f
        v = self._spanning()
        uit: list[Opdracht] = []
        if (self.v_laatst is None or abs(v - self.v_laatst) >= 0.005) and t - self.t_gestuurd >= 0.25:
            self.v_laatst, self.t_gestuurd = v, t
            uit.append(Opdracht(v=v))
        if self._f >= 1.0:
            self.klaar = True
            self.tekst = f"Klaar op {v:g} V.".replace(".", ",")
            uit.append(Opdracht(markering=f"accu nabootsen: klaar op {v:g} V".replace(".", ",")))
        return uit

    def melding(self):
        return None

    def status(self, t: float) -> str:
        rest = int(max(0.0, self.duur_s * (1 - self._frac)))
        v = self.v_laatst if self.v_laatst is not None else self.v0
        val = self.v_bron - v
        extra = f" (-{val:.2f} door R)".replace(".", ",") if self.r > 0 and val >= 0.005 else ""
        return f"nu {v:.2f} V{extra}, nog {rest // 60}:{rest % 60:02d}".replace(".", ",")
