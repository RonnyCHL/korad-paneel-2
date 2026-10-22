"""Grenzen per project: wat het paneel nooit naar de voeding laat gaan.

Een project is een kaartje met een naam, een maximale spanning en stroomgrens en de reden daarvoor. Het paneel
weigert alles daarboven (instellen, geheugenknoppen, programma's, accusimulatie) en grijpt in als de voeding aan de
voorkant hoger wordt gezet terwijl de uitgang aan staat. Overgenomen uit het oude paneel (PROJECTS); de reden hoort
erbij omdat een grens zonder reden na een maand niemand meer overtuigt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Project:
    sleutel: str
    naam: str
    vmax: float
    imax: float
    reden: str

    @property
    def titel(self) -> str:
        return f"{self.naam}: max {_nl(self.vmax)} V, {_nl(self.imax)} A"

    def binnen(self, v: float, i: float) -> bool:
        return 0 <= v <= self.vmax + 1e-9 and 0 <= i <= self.imax + 1e-9

    def knip(self, v: float, i: float) -> tuple[float, float]:
        """De waarden binnen de grens brengen (voor programma's en de accusimulatie)."""
        return max(0.0, min(self.vmax, v)), max(0.0, min(self.imax, i))

    def uitleg(self) -> str:
        return (f'De grens staat op "{self.naam}": spanning hooguit {_nl(self.vmax)} V en stroomgrens hooguit '
                f"{_nl(self.imax)} A ({self.reden}).")


PROJECTEN: dict[str, Project] = {
    "caravan": Project("caravan", "CaraVan Guard", 15.0, 4.0,
                       "de TVS-diode D2 op de print gaat rond 17 V geleiden"),
    "emsn": Project("emsn", "EMSN-auto", 5.5, 2.0,
                    "de VBUS-ingang van de AXP2101 op de T-Beam verdraagt hooguit 5,5 V"),
    "vrij": Project("vrij", "Vrij", 30.0, 5.0, "het bereik van de voeding"),
}
STANDAARD = "caravan"


def project(sleutel: str | None) -> Project:
    return PROJECTEN.get(sleutel or "", PROJECTEN[STANDAARD])


def _nl(x: float) -> str:
    s = f"{x:.3f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")
