"""Testprogramma's: stappen met sprong of helling, herhalen, en een verwachting per stap.

Hetzelfde JSON-formaat als het oude paneel (`testprogrammas/*.json`), zodat alle bestaande programma's (CaraVan
Guard, EMSN-auto) ongewijzigd werken:

    {"naam": "...", "omschrijving": "...", "herhalen": 1, "uit_na_afloop": true,
     "stappen": [{"overgang": "sprong"|"helling", "v": 13.8, "i": 1.5, "uit": "aan"|"uit", "duur": 60,
                  "verwacht": {"i_min": 20, "i_max": null, "na": 10, "melding": ""}}]}

De Loop hieronder is een toestandsmachine die op tik() zegt wat er naar de voeding moet (spanning, stroomgrens,
uitgang) en wanneer een stap klaar is; hij praat zelf niet met de voeding en kent geen scherm, dus hij is tot op de
seconde te toetsen. De duur mag ook als '1:30' of '45 s' in het bestand staan (zoals het oude paneel sinds zijn
laatste commit toestaat).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .geschiedenis import Meting

MAP = Path(__file__).resolve().parents[2] / "testprogrammas"


def duur_s(x) -> float:
    """60, '60', '1:30', '45 s', '2 min' -> seconden."""
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().lower().replace(",", ".")
    m = re.fullmatch(r"(\d+):(\d{1,2})", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.fullmatch(r"([\d.]+)\s*(s|sec|min|m|u|h)?", s)
    if not m:
        raise ValueError(f"duur onleesbaar: {x!r}")
    n = float(m.group(1))
    return n * {"min": 60, "m": 60, "u": 3600, "h": 3600}.get(m.group(2) or "s", 1)


@dataclass
class Verwachting:
    i_min: float | None = None       # mA, gemiddeld vanaf `na` seconden in de stap
    i_max: float | None = None
    na: float = 0.0
    melding: str = ""                # tekst die het apparaat onder test moet melden

    def leeg(self) -> bool:
        return self.i_min is None and self.i_max is None and not self.melding


@dataclass
class Stap:
    overgang: str = "sprong"         # sprong | helling
    v: float = 0.0
    i: float = 0.5
    uit: str = "aan"                 # aan | uit
    duur: float = 10.0
    verwacht: Verwachting | None = None

    @property
    def aan(self) -> bool:
        return self.uit == "aan"


@dataclass
class Programma:
    naam: str = "programma"
    omschrijving: str = ""
    herhalen: int = 1
    uit_na_afloop: bool = True
    stappen: list[Stap] = field(default_factory=list)

    @property
    def duur(self) -> float:
        return sum(s.duur for s in self.stappen) * max(1, self.herhalen)

    @staticmethod
    def uit_dict(d: dict) -> "Programma":
        stappen = []
        for k, s in enumerate(d.get("stappen") or [], 1):
            if not isinstance(s, dict):
                raise ValueError(f"stap {k} is geen object")
            vw = s.get("verwacht")
            verwachting = None
            if isinstance(vw, dict):
                verwachting = Verwachting(i_min=_getal_of_none(vw.get("i_min")), i_max=_getal_of_none(vw.get("i_max")),
                                          na=float(vw.get("na") or 0), melding=str(vw.get("melding") or ""))
                if verwachting.leeg():
                    verwachting = None
            try:
                stappen.append(Stap(overgang=str(s.get("overgang", "sprong")), v=float(s["v"]), i=float(s["i"]),
                                    uit=str(s.get("uit", "aan")), duur=duur_s(s.get("duur", 0)), verwacht=verwachting))
            except (KeyError, TypeError, ValueError) as e:
                raise ValueError(f"stap {k}: {e}") from e
            if stappen[-1].overgang not in ("sprong", "helling") or stappen[-1].uit not in ("aan", "uit"):
                raise ValueError(f"stap {k}: overgang of uit onbekend")
        return Programma(naam=str(d.get("naam") or "programma"), omschrijving=str(d.get("omschrijving") or ""),
                         herhalen=max(1, int(d.get("herhalen") or 1)), uit_na_afloop=bool(d.get("uit_na_afloop", True)),
                         stappen=stappen)

    def naar_dict(self) -> dict:
        return {"naam": self.naam, "omschrijving": self.omschrijving, "herhalen": self.herhalen,
                "uit_na_afloop": self.uit_na_afloop,
                "stappen": [{"overgang": s.overgang, "v": s.v, "i": s.i, "uit": s.uit, "duur": s.duur,
                             **({"verwacht": {"i_min": s.verwacht.i_min, "i_max": s.verwacht.i_max,
                                              "na": s.verwacht.na, "melding": s.verwacht.melding}}
                                if s.verwacht else {})} for s in self.stappen]}

    @staticmethod
    def laad(pad: Path) -> "Programma":
        return Programma.uit_dict(json.loads(Path(pad).read_text(encoding="utf-8")))

    def bewaar(self, pad: Path) -> None:
        Path(pad).write_text(json.dumps(self.naar_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def verloop(self, stap_s: float = 1.0) -> list[tuple[float, float, bool]]:
        """(tijd, spanning, uitgang) per seconde, voor de voorbeeldgrafiek in de stappen-editor."""
        uit, t, v_vorig = [], 0.0, 0.0
        for _ in range(self.herhalen):
            for s in self.stappen:
                n = max(1, int(s.duur / stap_s))
                for k in range(n):
                    frac = (k + 1) / n if s.overgang == "helling" and s.aan else 1.0
                    v = v_vorig + (s.v - v_vorig) * frac
                    uit.append((t, v if s.aan else 0.0, s.aan))
                    t += stap_s
                v_vorig = s.v
        return uit


def _getal_of_none(x):
    return None if x is None or x == "" else float(x)


def lijst(map_: Path = MAP) -> list[Path]:
    try:
        return sorted(p for p in map_.glob("*.json") if p.name != "laatste.json")
    except OSError:
        return []


# ---------------------------------------------------------------- de loop
@dataclass
class Opdracht:
    v: float | None = None
    i: float | None = None
    uit: bool | None = None
    markering: str | None = None
    apparaat: str | None = None      # 'pauze' | 'hervat': voor het apparaat onder test (de startproef)
    monitor: dict | None = None      # een commando voor de CaraVan Guard-monitor, bv. {"c": "light", "i": 0, "v": 20}


@dataclass
class Uitslag:
    stap: int                        # 1-gebaseerd
    herhaling: int
    goed: bool | None                # None = geen verwachting
    tekst: str


class Loop:
    """Voert een Programma uit op tik(t, meting): geeft de opdrachten voor de voeding terug.

    Hellingen: elke tik een nieuwe spanning, lineair van de vorige stap naar deze. De verwachting wordt beoordeeld
    aan het eind van de stap over de metingen vanaf `na` seconden.
    """

    def __init__(self, programma: Programma, grens_v: float, grens_i: float):
        self.p = programma
        self.grens_v, self.grens_i = grens_v, grens_i
        self.idx = -1
        self.herhaling = 1
        self.t_start = 0.0
        self.t_stap = 0.0
        self.v_van = 0.0
        self.v_laatst: float | None = None
        self.klaar = False
        self.uitslagen: list[Uitslag] = []
        self._metingen: list[Meting] = []
        self._meldingen: list[str] = []

    @property
    def stap(self) -> Stap | None:
        return self.p.stappen[self.idx] if 0 <= self.idx < len(self.p.stappen) else None

    @property
    def voortgang(self) -> float:
        totaal = self.p.duur or 1.0
        gedaan = sum(s.duur for s in self.p.stappen) * (self.herhaling - 1) + sum(s.duur for s in self.p.stappen[:max(0, self.idx)])
        return min(1.0, gedaan / totaal)

    def meld(self, tekst: str) -> None:
        """Een melding van het apparaat onder test (bv. '12 V weg'), voor verwachtingen met `melding`."""
        self._meldingen.append(tekst)

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = t
        if not self.p.stappen:
            self.klaar = True
            return []
        return self._naar_stap(t, 0, 1)

    def _naar_stap(self, t: float, idx: int, herhaling: int) -> list[Opdracht]:
        self.idx, self.herhaling, self.t_stap = idx, herhaling, t
        self.v_van = self.v_laatst if self.v_laatst is not None else 0.0
        self._metingen, self._meldingen = [], []
        s = self.stap
        v = min(s.v, self.grens_v)
        i = min(s.i, self.grens_i)
        helling = s.overgang == "helling" and s.aan and s.duur > 0
        op = Opdracht(i=i, v=(self.v_van if helling else v), uit=s.aan,
                      markering=f"stap {idx + 1}: " + ("uitgang uit" if not s.aan else (("helling naar " if helling else "") + f"{v:g} V".replace(".", ","))))
        if not helling:
            self.v_laatst = v
        return [op]

    def tik(self, t: float, m: Meting | None) -> list[Opdracht]:
        if self.klaar or self.stap is None:
            return []
        s = self.stap
        if m is not None:
            self._metingen.append(m)
        el = t - self.t_stap
        uit: list[Opdracht] = []
        if s.overgang == "helling" and s.aan and s.duur > 0:
            frac = min(1.0, el / s.duur)
            v = round(self.v_van + (min(s.v, self.grens_v) - self.v_van) * frac, 2)
            if self.v_laatst is None or abs(v - self.v_laatst) >= 0.005:
                self.v_laatst = v
                uit.append(Opdracht(v=v))
        if el >= s.duur:
            self._beoordeel()
            if self.idx + 1 < len(self.p.stappen):
                uit += self._naar_stap(t, self.idx + 1, self.herhaling)
            elif self.herhaling < self.p.herhalen:
                uit += self._naar_stap(t, 0, self.herhaling + 1)
            else:
                self.klaar = True
                if self.p.uit_na_afloop:
                    uit.append(Opdracht(uit=False, markering="programma klaar: uitgang uit"))
                else:
                    uit.append(Opdracht(markering="programma klaar"))
        return uit

    def _beoordeel(self) -> None:
        s = self.stap
        vw = s.verwacht
        if vw is None:
            return
        delen, goed = [], True
        pts = [m for m in self._metingen if m.t - self.t_stap >= vw.na]
        if vw.i_min is not None or vw.i_max is not None:
            if pts:
                gem = sum(m.i for m in pts) / len(pts) * 1000.0
                binnen = (vw.i_min is None or gem >= vw.i_min) and (vw.i_max is None or gem <= vw.i_max)
                goed &= binnen
                grens = " en ".join(x for x in ((f"minstens {vw.i_min:g} mA" if vw.i_min is not None else ""),
                                                 (f"hooguit {vw.i_max:g} mA" if vw.i_max is not None else "")) if x)
                delen.append(f"stroom gemiddeld {gem:.0f} mA ({grens}): {'goed' if binnen else 'FOUT'}")
            else:
                goed = False
                delen.append("geen metingen na het wachten: FOUT")
        if vw.melding:
            gezien = any(vw.melding.lower() in x.lower() for x in self._meldingen)
            goed &= gezien
            delen.append(f"melding '{vw.melding}': {'gezien' if gezien else 'NIET gezien'}")
        self.uitslagen.append(Uitslag(self.idx + 1, self.herhaling, goed, "; ".join(delen)))

    def samenvatting(self) -> tuple[int, int]:
        """(goed, fout) over alle beoordeelde stappen."""
        g = sum(1 for u in self.uitslagen if u.goed)
        return g, len(self.uitslagen) - g
