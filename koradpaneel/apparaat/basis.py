from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class Apparaat(QObject):
    """Basis: regels komen binnen als signaal `regel(t, tekst)`, de verbinding als `verbonden(open, tekst)`.

    pauze() laat de verbinding los (bij het bordje: de poort sluiten voor de stroom eraf gaat), hervat() zoekt
    hem geduldig terug. Alle signalen komen in de schermthread aan, ook als het apparaat in een eigen thread
    leest (Qt zet ze in de wachtrij)."""

    regel = Signal(float, str)
    verbonden = Signal(bool, str)
    naam = "apparaat"

    @property
    def open(self) -> bool:
        return False

    def start(self) -> None:
        pass

    def pauze(self) -> None:
        pass

    def hervat(self) -> None:
        pass

    def stop(self) -> None:
        pass
