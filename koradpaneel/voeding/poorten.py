"""Seriële poorten vinden, en herkennen welke de Korad is (USB Serial Device, VID 0416 / PID 5011)."""

from __future__ import annotations

from dataclasses import dataclass

from serial.tools import list_ports

KORAD_VID, KORAD_PID = 0x0416, 0x5011


@dataclass(frozen=True)
class Poort:
    naam: str           # COM10
    omschrijving: str   # USB Serial Device (COM10)
    korad: bool         # lijkt dit de Korad?


def lijst() -> list[Poort]:
    uit = []
    for p in sorted(list_ports.comports(), key=lambda p: p.device):
        korad = (p.vid == KORAD_VID and p.pid == KORAD_PID)
        uit.append(Poort(p.device, p.description or p.device, korad))
    return uit


def korad_poort() -> str | None:
    """De eerste poort die op de Korad lijkt, of None."""
    for p in lijst():
        if p.korad:
            return p.naam
    return None
