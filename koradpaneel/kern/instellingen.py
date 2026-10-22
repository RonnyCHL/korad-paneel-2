"""Instellingen: één JSON-bestand naast het programma, met standaardwaarden voor alles.

Onbekende sleutels in het bestand blijven staan (een nieuwere versie van het paneel mag er meer in zetten), en
ontbrekende sleutels krijgen de standaardwaarde. Het bestand staat niet in git: er staan adressen en codes in.
"""

from __future__ import annotations

import json
from pathlib import Path

MAP = Path(__file__).resolve().parents[2]
BESTAND = MAP / "korad_instellingen.json"

STANDAARD: dict = {
    "project": "caravan",
    "poort": "",                     # leeg = zelf zoeken
    "thema": "donker",
    "accent": "#3D7BF2",
    "indeling": {"caravan": "eenvoudig", "emsn": "eenvoudig", "vrij": "eenvoudig"},
    "geheugens": {"1": "3,3 V\n0,5 A", "2": "5 V\n1 A", "3": "12 V\n0,5 A", "4": "13,8 V\n0,5 A"},
    "geluid_cc": True,
    "spraak": False,
    "ntfy": {"server": "https://ntfy.sh", "onderwerp": "", "aan": False},
    "web": {"poort": 8085, "code": "", "aan": False},
    "monitor": {"adres": "", "aan": False},
    "emsn": {"poort": "COM6"},
    "venster": {},                   # geometrie per indeling
}


def _vul(doel: dict, bron: dict) -> dict:
    for k, v in bron.items():
        if isinstance(v, dict) and isinstance(doel.get(k), dict):
            _vul(doel[k], v)
        else:
            doel[k] = v
    return doel


def laad(pad: Path = BESTAND) -> dict:
    uit = json.loads(json.dumps(STANDAARD))     # diepe kopie
    try:
        data = json.loads(pad.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _vul(uit, data)
    except (OSError, ValueError):
        pass
    return uit


def bewaar(inst: dict, pad: Path = BESTAND) -> None:
    try:
        tijdelijk = pad.with_suffix(".nieuw")
        tijdelijk.write_text(json.dumps(inst, indent=1, ensure_ascii=False), encoding="utf-8")
        tijdelijk.replace(pad)
    except OSError:
        pass
