"""Bewaking: regels die de uitgang uitzetten of waarschuwen als een meting te lang over een grens gaat.

Drie regels, zoals in het oude paneel (zelfde bestandsformaat, `korad_bewaking.json`): stroom (mA), spanning (V) of
vermogen (W), boven of onder een waarde, gedurende een aantal seconden, en dan "uitgang uit" of "waarschuwen". Een
regel gaat pas af als de voorwaarde de hele duur ONONDERBROKEN waar is, en gaat daarna pas opnieuw af nadat de
voorwaarde een keer niet meer waar was.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .geschiedenis import Meting

from ..paden import BASIS as MAP
BESTAND = MAP / "korad_bewaking.json"
EENHEID = {"stroom": "mA", "spanning": "V", "vermogen": "W"}
ACTIES = ("uitgang uit", "waarschuwen")


@dataclass
class Regel:
    aan: bool = False
    wat: str = "stroom"            # stroom | spanning | vermogen
    richting: str = "boven"        # boven | onder
    waarde: float = 300.0          # in mA, V of W (zie EENHEID)
    duur: float = 5.0              # seconden
    actie: str = "uitgang uit"

    def tekst(self) -> str:
        w = f"{self.waarde:g}".replace(".", ",")
        return f"{self.wat} {self.richting} {w} {EENHEID[self.wat]} {self.duur:g} s → {self.actie}"

    def waar(self, m: Meting) -> bool:
        x = {"stroom": m.i * 1000.0, "spanning": m.v, "vermogen": m.w}[self.wat]
        return x > self.waarde if self.richting == "boven" else x < self.waarde


STANDAARD = [
    Regel(False, "stroom", "boven", 300.0, 5.0, "uitgang uit"),
    Regel(False, "stroom", "onder", 40.0, 10.0, "waarschuwen"),
    Regel(False, "spanning", "onder", 4.5, 2.0, "waarschuwen"),
]


@dataclass
class Gebeurtenis:
    regel: Regel
    t: float
    meting: Meting

    @property
    def tekst(self) -> str:
        return f"bewaking: {self.regel.tekst()}"


class Bewaking:
    def __init__(self, regels: list[Regel] | None = None):
        self.regels: list[Regel] = regels if regels is not None else [Regel(**asdict(r)) for r in STANDAARD]
        self._sinds: dict[int, float | None] = {}     # per regel: sinds wanneer de voorwaarde waar is
        self._afgegaan: dict[int, bool] = {}

    @property
    def actief(self) -> bool:
        return any(r.aan for r in self.regels)

    def evalueer(self, m: Meting) -> list[Gebeurtenis]:
        uit = []
        for k, r in enumerate(self.regels):
            if not r.aan:
                self._sinds[k] = None
                self._afgegaan[k] = False
                continue
            if r.waar(m):
                if self._sinds.get(k) is None:
                    self._sinds[k] = m.t
                elif m.t - self._sinds[k] >= r.duur and not self._afgegaan.get(k):
                    self._afgegaan[k] = True
                    uit.append(Gebeurtenis(r, m.t, m))
            else:
                self._sinds[k] = None
                self._afgegaan[k] = False
        return uit

    # ---- bestand (hetzelfde formaat als het oude paneel)
    def laad(self, pad: Path = BESTAND) -> None:
        try:
            data = json.loads(pad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, list):
            return
        regels = []
        for d, s in zip(data, STANDAARD):
            if isinstance(d, dict):
                velden = {kk: d.get(kk, vv) for kk, vv in asdict(s).items()}
                if velden["wat"] in EENHEID and velden["richting"] in ("boven", "onder") and velden["actie"] in ACTIES:
                    regels.append(Regel(bool(velden["aan"]), velden["wat"], velden["richting"],
                                        float(velden["waarde"]), float(velden["duur"]), velden["actie"]))
                    continue
            regels.append(Regel(**asdict(s)))
        self.regels = regels + [Regel(**asdict(s)) for s in STANDAARD[len(regels):]]

    def bewaar(self, pad: Path = BESTAND) -> None:
        try:
            pad.write_text(json.dumps([asdict(r) for r in self.regels], indent=1, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
