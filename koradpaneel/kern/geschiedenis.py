"""De meetgeschiedenis: een ring van metingen, de energieteller en de getallen van een tijdvenster.

Alles hier is rekenwerk op (tijd, spanning, stroom); er zit geen scherm en geen voeding in, dus het is tot op de
milliampère te toetsen. De grafiek, de meters, de rapporten en de meetcursors lezen allemaal uit dezelfde ring.
"""

from __future__ import annotations

import bisect
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Meting:
    t: float          # unix-tijd in seconden
    v: float          # volt, gemeten
    i: float          # ampère, gemeten

    @property
    def w(self) -> float:
        return self.v * self.i


@dataclass
class Venster:
    """De getallen van een stuk geschiedenis, zoals de meetcursors en het rapport ze tonen."""
    van: float
    tot: float
    n: int
    i_min: float
    i_max: float
    i_gem: float
    v_min: float
    v_max: float
    v_gem: float
    mah: float
    wh: float

    @property
    def duur(self) -> float:
        return self.tot - self.van


class Geschiedenis:
    """Ring van metingen op tijd; `maxlen` ruim genoeg voor een nacht bij ~5 metingen per seconde."""

    def __init__(self, maxlen: int = 400_000):
        self._m: deque[Meting] = deque(maxlen=maxlen)
        self._t: deque[float] = deque(maxlen=maxlen)

    def __len__(self) -> int:
        return len(self._m)

    @property
    def laatste(self) -> Meting | None:
        return self._m[-1] if self._m else None

    def voeg(self, m: Meting) -> None:
        self._m.append(m)
        self._t.append(m.t)

    def tussen(self, van: float, tot: float) -> list[Meting]:
        """Alle metingen met van <= t <= tot; O(log n) om te vinden dankzij de tijdring."""
        t = self._t
        a = bisect.bisect_left(t, van)
        b = bisect.bisect_right(t, tot)
        return [self._m[k] for k in range(a, b)]

    def venster(self, van: float, tot: float) -> Venster | None:
        pts = self.tussen(van, tot)
        if len(pts) < 1:
            return None
        return venster_uit(pts)


def venster_uit(pts: list[Meting]) -> Venster:
    """Getallen uit een lijst metingen; lading en energie als trapeziumsom over de tijd."""
    vs = [p.v for p in pts]
    cs = [p.i for p in pts]
    mah = wh = 0.0
    for a, b in zip(pts, pts[1:]):
        dt = b.t - a.t
        if dt <= 0 or dt > 5:          # een gat van meer dan 5 s telt niet mee: dat was geen meting
            continue
        mah += (a.i + b.i) / 2 * dt / 3.6
        wh += (a.w + b.w) / 2 * dt / 3600
    return Venster(van=pts[0].t, tot=pts[-1].t, n=len(pts),
                   i_min=min(cs), i_max=max(cs), i_gem=sum(cs) / len(cs),
                   v_min=min(vs), v_max=max(vs), v_gem=sum(vs) / len(vs),
                   mah=mah, wh=wh)


class Energieteller:
    """mAh en Wh sinds een moment; de knop 'Op nul' zet hem terug. Telt alleen opeenvolgende metingen op."""

    def __init__(self):
        self.sinds: float | None = None
        self.mah = 0.0
        self.wh = 0.0
        self._vorige: Meting | None = None

    def op_nul(self, t: float) -> None:
        self.sinds, self.mah, self.wh, self._vorige = t, 0.0, 0.0, None

    def tel(self, m: Meting) -> None:
        if self.sinds is None:
            self.sinds = m.t
        v = self._vorige
        if v is not None:
            dt = m.t - v.t
            if 0 < dt <= 5:
                self.mah += (v.i + m.i) / 2 * dt / 3.6
                self.wh += (v.w + m.w) / 2 * dt / 3600
        self._vorige = m

    @property
    def duur(self) -> float:
        return 0.0 if self.sinds is None or self._vorige is None else self._vorige.t - self.sinds
