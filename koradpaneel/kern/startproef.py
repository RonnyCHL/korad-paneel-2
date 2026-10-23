"""De startproef voor het EMSN-auto-bordje: N keer 'auto uit' en 'auto aan', en per start de boot-log lezen.

Overgenomen uit emsn_auto.py van het oude paneel (22-10-2026), maar nu als toestandsmachine zonder scherm en
zonder seriële poort, net als programma.Loop: tik() krijgt de tijd, de laatste meting en de nieuwe regels van het
bordje, en geeft terug wat er naar de voeding moet. Daardoor is de hele proef tot op de seconde te toetsen.

Per start: de uitgang gaat `uit_s` seconden uit, dan `aan_s` seconden aan op 5,00 V (grens 2 A). In de boot-log
staat 'i2c-keuring: ... ack 34:j 68:j 76:j' (goed) of 'ack 34:n ...' (dood: de laadchip zwijgt, het bordje slaapt
dan niet en laadt niet). Daarbij de stroom na 3, 10 en 30 s. De USB-chip van het bordje wordt uit dezelfde 5 V
gevoed, dus de poort verdwijnt bij 'auto uit': de proef zegt wanneer de poort losgelaten (pauze) en teruggezocht
(hervat) moet worden.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from .programma import Opdracht
from .proeven import Ctx, Proef

VOLT, AMP = 5.00, 2.0
MOMENTEN = (3.0, 10.0, 30.0)
POORT_WACHT_S = 25.0                                        # zo lang mag Windows doen over het terugvinden
KEURING = re.compile(r"i2c-keuring:\s*(.*)")                # de boot-log (firmware 0.9.5+)
STATUS_I2C = re.compile(r"\bi2c:\s*(.*?)(?:\s*\|.*)?$")     # de 's'-statusregel: dezelfde keuring
VERSIE = re.compile(r"=== EMSN-auto (\S+)")
RESET = re.compile(r"^rst:0x\w+ \((\w+)\)")                 # de ROM-bootloader: reden van de herstart


def oordeel(keuring: str) -> str:
    """'goed' als alle drie antwoorden, 'dood' als de AXP2101 (0x34) zwijgt, anders 'half'."""
    if "34:n" in keuring:
        return "dood"
    if "34:j" in keuring and "68:j" in keuring and "76:j" in keuring:
        return "goed"
    return "half"


@dataclass
class Rij:
    nr: int
    t: float
    keuring: str = ""
    oordeel: str = "?"
    i: dict = field(default_factory=dict)       # moment (s) -> ampère of None
    poort_s: float | None = None                # na hoeveel seconden de poort terug was
    boot_s: float | None = None                 # na hoeveel seconden de eerste regel kwam
    resets: int = 0                             # herstarts van de ROM-bootloader in deze start


class Startproef(Proef):
    soort = "startproef"
    rapport = True

    def __init__(self, n: int = 20, uit_s: float = 5.0, aan_s: float = 45.0, *, volt: float = VOLT,
                 amp: float = AMP, momenten: tuple = MOMENTEN):
        super().__init__()
        self.n = max(1, int(n))
        self.uit_s = max(1.0, float(uit_s))
        self.aan_s = max(momenten[-1] + 2, float(aan_s))
        self.volt, self.amp, self.momenten = volt, amp, momenten
        self.k = 0
        self.fase = "uit"
        self.t_fase = 0.0
        self.rij: Rij | None = None
        self.rijen: list[Rij] = []
        self.fw = ""
        self.klaar = False
        self.poort_open = False
        self.poort_fout = ""

    @property
    def naam(self) -> str:
        return f"Bordje: {self.n} starts"

    @property
    def duur(self) -> float:
        return self.n * (self.uit_s + self.aan_s)

    @property
    def voortgang(self) -> float:
        gedaan = len(self.rijen) * (self.uit_s + self.aan_s)
        return min(1.0, gedaan / self.duur) if self.duur else 1.0

    # ---- verloop
    def start(self, t: float) -> list[Opdracht]:
        self.t_start = self.t_fase = t
        self.fase = "uit"
        return [Opdracht(i=self.amp), Opdracht(v=self.volt), Opdracht(apparaat="pauze"),
                Opdracht(uit=False, markering=f"EMSN-auto: startproef, {self.n} starts")]

    def poort(self, t: float, open_: bool, fout: str = "") -> None:
        """Het apparaat meldt dat de poort open is of weg."""
        self.poort_open = open_
        self.poort_fout = fout
        if open_ and self.rij is not None and self.fase == "aan" and self.rij.poort_s is None:
            self.rij.poort_s = round(t - self.t_fase, 1)

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar:
            return []
        t, m, regels = ctx.t, ctx.meting, ctx.regels
        el = t - self.t_fase
        uit: list[Opdracht] = []
        if self.fase == "uit":
            if el >= self.uit_s:
                self.k += 1
                self.rij = Rij(nr=self.k, t=t)
                self.fase, self.t_fase = "aan", t
                uit += [Opdracht(apparaat="hervat"), Opdracht(uit=True, markering=f"start {self.k}")]
            return uit
        rij = self.rij
        for regel in regels:
            if rij.boot_s is None and regel.strip():
                rij.boot_s = round(el, 1)
            mv = VERSIE.search(regel)
            if mv:
                self.fw = mv.group(1)
            if RESET.search(regel):
                rij.resets += 1
            mk = KEURING.search(regel) or STATUS_I2C.search(regel)
            if mk and not rij.keuring:
                rij.keuring = mk.group(1).strip()
                rij.oordeel = oordeel(rij.keuring)
        for mom in self.momenten:
            if el >= mom and mom not in rij.i:
                rij.i[mom] = m.i if m is not None else None
        if el >= self.aan_s:
            self._rij_klaar(rij)
            if self.k >= self.n:
                self.klaar = True
                return uit
            self.fase, self.t_fase = "uit", t
            uit += [Opdracht(apparaat="pauze"), Opdracht(uit=False)]
        return uit

    def _rij_klaar(self, rij: Rij) -> None:
        if not rij.keuring:
            if rij.resets >= 3 and rij.boot_s is not None:
                rij.keuring = f"(herstartlus: {rij.resets} herstarts, geen boot-log)"
                rij.oordeel = "lus"
            elif not self.poort_open and rij.poort_s is None:
                rij.keuring = f"(geen seriële poort: {(self.poort_fout or '?')[:50]})"
            elif rij.boot_s is None:
                rij.keuring = "(poort open, maar het bordje zei niets)"
        if rij not in self.rijen:
            self.rijen.append(rij)
        if self.rij is rij:
            self.rij = None

    def status(self, t: float) -> str:
        if self.klaar or self.tekst:
            return self.tekst
        el = int(t - self.t_fase)
        if self.fase == "uit":
            return f"start {self.k + 1} van {self.n}: uitgang uit, nog {max(0, int(self.uit_s) - el)} s"
        rij = self.rij
        if rij is not None and rij.poort_s is not None:
            poort = f"poort na {rij.poort_s:g} s".replace(".", ",")
        else:
            poort = "poort terugzoeken" if el < POORT_WACHT_S else "geen poort"
        return f"start {self.k} van {self.n}: aan sinds {el} s, {poort}, {rij.oordeel if rij else '?'}"

    # ---- afronden
    def telling(self) -> dict[str, int]:
        uit = {s: 0 for s in ("goed", "dood", "half", "lus", "?")}
        for r in self.rijen:
            uit[r.oordeel if r.oordeel in uit else "?"] += 1
        return uit

    def stop(self, reden: str, ctx: Ctx) -> list[Opdracht]:
        return [Opdracht(apparaat="pauze")]

    def afronden(self, reden: str, ctx: Ctx) -> str:
        """De lopende start meetellen als er al een keuring was; de uitslag in één zin."""
        self.t1 = ctx.t
        if self.rij is not None and self.rij.keuring:
            self._rij_klaar(self.rij)
        self.rij = None
        self.klaar = True
        n = self.telling()
        tot = len(self.rijen)
        delen = [f"{n['goed']} goed", f"{n['dood']} dood"]
        if n["half"]:
            delen.append(f"{n['half']} half")
        if n["lus"]:
            delen.append(f"{n['lus']} herstartlus")
        if n["?"]:
            delen.append(f"{n['?']} onbekend")
        self.tekst = (f"{reden}: {tot} start{'s' if tot != 1 else ''}, " + ", ".join(delen)
                      + (f", firmware {self.fw}" if self.fw else "") + ".")
        self.oordeel = "fout" if n["dood"] or n["lus"] else ("letop" if n["half"] or n["?"] or not tot else "goed")
        return self.tekst

    def tabel_html(self, ctx: Ctx) -> str:
        return tabel_html(self)

    def melding(self):
        n = self.telling()
        return ("Startproef klaar", f"{n['goed']} goed, {n['dood']} dood" + (f", {n['lus']} herstartlus" if n["lus"] else ""))


def _ma(x) -> str:
    return f"{x * 1000:.0f} mA" if x is not None else "-"


def _s(x) -> str:
    return "-" if x is None else f"{x:g} s".replace(".", ",")


def tabel_html(sp: Startproef) -> str:
    """De tabel met alle starts, voor het rapport."""
    esc = html.escape
    kl = {"goed": "goed", "dood": "fout", "lus": "fout", "half": "letop", "?": "letop"}
    rijen = []
    for r in sp.rijen:
        cellen = [f"<td>{r.nr}</td>", f"<td class='{kl.get(r.oordeel, 'letop')}'><b>{esc(r.oordeel)}</b></td>",
                  f"<td>{_s(r.poort_s)}</td>"]
        cellen += [f"<td>{_ma(r.i.get(mom))}</td>" for mom in sp.momenten]
        cellen.append(f"<td><code>{esc(r.keuring)}</code></td>")
        rijen.append("<tr>" + "".join(cellen) + "</tr>")
    kop = "".join(f"<th>{_s(mom)}</th>" for mom in sp.momenten)
    uitleg = ("goed = AXP2101, MPU-6050 en BME680 antwoorden; dood = de laadchip (0x34) zwijgt, het bordje slaapt "
              "dan niet en laadt niet; half = een van de sensoren ontbreekt; herstartlus = de ROM-bootloader "
              "herstart steeds (de 3,3 V valt weg) en de firmware komt niet aan het woord.")
    return (f"<h2>Per start</h2><table><tr><th>#</th><th>Boot</th><th>Poort</th>{kop}"
            f"<th>i2c-keuring (uit de seriële log)</th></tr>{''.join(rijen)}</table>"
            f"<p class='meta'>{uitleg}</p>")
