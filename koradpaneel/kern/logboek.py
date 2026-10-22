"""Het CSV-log: elke meting een regel, zolang het log loopt. Markeringen gaan als aparte regel mee.

Kolommen: tijd (ISO), unix, volt, ampere, watt, markering. De database (SQLite) komt in een latere stap; het
CSV-formaat blijft, want dat lezen Excel en het oude paneel.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .geschiedenis import Meting

MAP = Path(__file__).resolve().parents[2] / "logs"


class CsvLog:
    def __init__(self):
        self.pad: Path | None = None
        self._f = None
        self._w = None
        self.regels = 0

    @property
    def loopt(self) -> bool:
        return self._f is not None

    def start(self, naam: str = "", map_: Path = MAP) -> Path:
        map_.mkdir(parents=True, exist_ok=True)
        stam = naam or datetime.now().strftime("log_%Y%m%d_%H%M%S")
        self.pad = map_ / f"{stam}.csv"
        self._f = open(self.pad, "w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f, delimiter=";")
        self._w.writerow(["tijd", "unix", "volt", "ampere", "watt", "markering"])
        self.regels = 0
        return self.pad

    def schrijf(self, m: Meting) -> None:
        if self._w is None:
            return
        self._w.writerow([datetime.fromtimestamp(m.t).isoformat(timespec="milliseconds"), f"{m.t:.3f}",
                          f"{m.v:.3f}", f"{m.i:.4f}", f"{m.w:.4f}", ""])
        self.regels += 1
        if self.regels % 50 == 0:
            self._f.flush()

    def markeer(self, t: float, tekst: str) -> None:
        if self._w is None:
            return
        self._w.writerow([datetime.fromtimestamp(t).isoformat(timespec="milliseconds"), f"{t:.3f}", "", "", "",
                          tekst])

    def stop(self) -> Path | None:
        pad, f, self._f, self._w = self.pad, self._f, None, None
        if f is not None:
            f.close()
        return pad


def lees(pad: Path) -> tuple[list[Meting], list[tuple[float, str]]]:
    """Een log terugleden: de metingen en de markeringen."""
    metingen, markeringen = [], []
    with open(pad, newline="", encoding="utf-8") as f:
        r = csv.reader(f, delimiter=";")
        next(r, None)
        for rij in r:
            if len(rij) < 6:
                continue
            t = float(rij[1])
            if rij[5]:
                markeringen.append((t, rij[5]))
            elif rij[2]:
                metingen.append(Meting(t=t, v=float(rij[2]), i=float(rij[3])))
    return metingen, markeringen
