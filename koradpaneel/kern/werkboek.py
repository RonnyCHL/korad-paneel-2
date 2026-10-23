"""Het werkboek: alles wat gemeten is, op datum. Zelfde bestandsformaat als het oude paneel
(`korad_werkboek.json`: t, soort, titel, pad, uitleg), zodat het oude werkboek in te lezen is."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ..paden import BASIS as MAP
BESTAND = MAP / "korad_werkboek.json"
MAX = 2000


@dataclass
class Regel:
    t: float
    soort: str                 # log | rapport | programma | startproef | nachttest | ...
    titel: str
    pad: str = ""
    uitleg: str = ""


class Werkboek:
    def __init__(self, pad: Path = BESTAND):
        self.pad = pad
        self.regels: list[Regel] = []

    def laad(self, pad: Path | None = None) -> int:
        """Leest een werkboekbestand (het eigen, of dat van het oude paneel) en voegt onbekende regels toe."""
        pad = pad or self.pad
        try:
            data = json.loads(Path(pad).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        bekend = {(round(r.t, 3), r.titel) for r in self.regels}
        n = 0
        for d in data if isinstance(data, list) else []:
            try:
                r = Regel(float(d["t"]), str(d.get("soort") or "rapport"), str(d.get("titel") or "")[:160],
                          str(d.get("pad") or ""), str(d.get("uitleg") or "")[:700])
            except (KeyError, TypeError, ValueError):
                continue
            if (round(r.t, 3), r.titel) not in bekend:
                self.regels.append(r)
                bekend.add((round(r.t, 3), r.titel))
                n += 1
        self.regels.sort(key=lambda r: r.t)
        return n

    def bewaar(self) -> None:
        del self.regels[:-MAX]
        try:
            tijdelijk = self.pad.with_suffix(".nieuw")
            tijdelijk.write_text(json.dumps([asdict(r) for r in self.regels], indent=1, ensure_ascii=False),
                                 encoding="utf-8")
            tijdelijk.replace(self.pad)
        except OSError:
            pass

    def voeg(self, soort: str, titel: str, pad: Path | str | None = None, uitleg: str = "",
             t: float | None = None) -> Regel:
        r = Regel(t or time.time(), soort, str(titel)[:160], str(Path(pad).resolve()) if pad else "",
                  str(uitleg or "")[:700])
        self.regels.append(r)
        self.bewaar()
        return r

    def scan(self, mappen: list[tuple[Path, str, str]]) -> int:
        """Rapporten en logs die al in de mappen staan erbij zetten: [(map, patroon, soort), ...]."""
        bekend = {r.pad.lower() for r in self.regels if r.pad}
        n = 0
        for map_, patroon, soort in mappen:
            try:
                bestanden = sorted(map_.glob(patroon))
            except OSError:
                continue
            for f in bestanden:
                p = str(f.resolve())
                if p.lower() in bekend:
                    continue
                try:
                    t = f.stat().st_mtime
                except OSError:
                    continue
                self.regels.append(Regel(t, soort, f.name, p, f"gevonden in de map {map_.name}"))
                bekend.add(p.lower())
                n += 1
        if n:
            self.regels.sort(key=lambda r: r.t)
            self.bewaar()
        return n

    def per_dag(self) -> dict[str, int]:
        uit: dict[str, int] = {}
        for r in self.regels:
            d = time.strftime("%Y-%m-%d", time.localtime(r.t))
            uit[d] = uit.get(d, 0) + 1
        return uit

    def zoek(self, tekst: str) -> list[Regel]:
        t = tekst.lower().strip()
        return [r for r in self.regels
                if not t or t in r.titel.lower() or t in r.uitleg.lower() or t in r.soort.lower()]
