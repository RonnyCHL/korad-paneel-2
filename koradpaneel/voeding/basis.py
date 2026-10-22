"""De abstracte voeding: wat het paneel van ELKE voeding verwacht.

Het paneel praat alleen via deze klasse. De Korad vult hem in met zijn seriële protocol; de nagebootste voeding
met natuurkunde; een Riden of Owon later met het hunne. Alles wat een voeding niet kan, meldt hij eerlijk via
`kan` -- het paneel verbergt die knop dan, in plaats van te gokken.

Alle aanroepen zijn blokkerend en thread-veilig; het paneel roept ze aan vanuit één werkthread (zie
kern/werker.py), nooit vanuit de schermthread.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Stand:
    """Wat de voeding meldt bij één uitlezing."""
    v_uit: float            # gemeten spanning op de uitgang
    i_uit: float            # gemeten stroom
    v_set: float | None     # ingestelde spanning (None = niet gelezen)
    i_set: float | None     # ingestelde stroomgrens
    uitgang: bool
    cc: bool                # True = stroom begrensd (CC), False = vaste spanning (CV)


@dataclass(frozen=True)
class Vermogens:
    """Wat deze voeding kan; de meetbereiken in volt/ampère en de stapgrootte van instellen."""
    v_max: float
    i_max: float
    v_stap: float = 0.01
    i_stap: float = 0.001
    geheugens: int = 0                      # aantal M-knoppen (RCL/SAV)
    ocp: bool = False                       # overstroombeveiliging instelbaar
    ovp: bool = False
    kanalen: int = 1
    extra: dict = field(default_factory=dict)


class Voeding:
    """Basisklasse. Een echte voeding overschrijft alles; de standaardimplementaties zeggen 'kan ik niet'."""

    naam = "onbekende voeding"

    def verbind(self) -> str:
        """Verbinding maken; geeft de identiteit (zoals *IDN?) terug. Gooit OSError als het niet lukt."""
        raise NotImplementedError

    def sluit(self) -> None:
        raise NotImplementedError

    def kan(self) -> Vermogens:
        raise NotImplementedError

    def lees(self) -> Stand:
        """Eén uitlezing: gemeten spanning en stroom, uitgang en CV/CC. Minstens een paar keer per seconde."""
        raise NotImplementedError

    def lees_instellingen(self) -> tuple[float, float]:
        """(ingestelde spanning, ingestelde stroomgrens)."""
        raise NotImplementedError

    def zet_spanning(self, v: float) -> None:
        raise NotImplementedError

    def zet_stroomgrens(self, i: float) -> None:
        raise NotImplementedError

    def zet_uitgang(self, aan: bool) -> None:
        raise NotImplementedError

    def geheugen_ophalen(self, n: int) -> None:
        raise NotImplementedError

    def geheugen_bewaren(self, n: int) -> None:
        raise NotImplementedError
