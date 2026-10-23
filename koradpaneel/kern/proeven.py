"""De proeven van CaraVan Guard en de onderdelentester, als toestandsmachines zonder scherm.

Elke proef heeft dezelfde vorm (zie `Proef`): start(t) en tik(ctx) geven opdrachten voor de voeding (en de
monitor) terug; `Ctx` is alles wat een proef van de buitenwereld mag weten. Het paneel drijft één proef tegelijk
op zijn tikker (4x per seconde) en maakt na afloop het rapport, de werkboekregel en de melding.

Overgenomen uit het oude paneel: opstartcurve (zachte start), bouwstappen van de draagprint, spanningsmeting
controleren, stroommeting ijken, UPS-duurtest, nachttest, rooktest na een update en de onderdelentester.
"""

from __future__ import annotations

import html
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..apparaat.monitor import EXPECTED_I2C, MonitorBeeld
from .geschiedenis import Geschiedenis, Meting, venster_uit
from .programma import Opdracht
from .rapport import nl


def fmt_ma(a: float | None) -> str:
    return "-" if a is None else f"{nl(a * 1000, 0)} mA"


def fmt_duur(s: float) -> str:
    s = int(round(s))
    if s >= 3600:
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
    return f"{s // 60}:{s % 60:02d}"


def nice_ceil(x: float) -> float:
    if x <= 0:
        return 1.0
    m = 10 ** math.floor(math.log10(x))
    for f in (1, 2, 2.5, 5, 10):
        if x <= f * m:
            return f * m
    return 10 * m


def laag(tekst: str) -> str:
    return tekst[0].lower() + tekst[1:] if tekst else tekst


# ---------------------------------------------------------------- de omgeving van een proef
@dataclass
class Ctx:
    t: float
    meting: Meting | None = None
    cc: bool = False
    uitgang: bool = False
    v_set: float | None = None
    i_set: float | None = None
    geschiedenis: Geschiedenis | None = None
    monitor: MonitorBeeld | None = None
    regels: list = field(default_factory=list)       # regels van het bordje (startproef)
    vmax: float = 30.0
    imax: float = 5.0

    def tussen(self, van: float, tot: float) -> list[Meting]:
        return self.geschiedenis.tussen(van, tot) if self.geschiedenis else []

    def mon_vers(self) -> bool:
        return self.monitor is not None and self.monitor.vers(self.t)


class Proef:
    """Basis. Een proef zet klaar=True als hij vanzelf klaar is; het paneel roept dan afronden('Klaar', ctx)."""

    naam = "proef"
    soort = "controle"          # soort in het werkboek
    rapport = False             # na afloop een rapport maken (met tabel_html())

    def __init__(self):
        self.klaar = False
        self.t_start = self.t1 = 0.0
        self.tekst = ""
        self.oordeel = "goed"   # goed | letop | fout
        self.markers: list[tuple[float, str]] = []

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = t
        return []

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        return []

    def stop(self, reden: str, ctx: Ctx) -> list[Opdracht]:
        """Door de gebruiker of de noodstop gestopt: wat er nog naar de voeding moet."""
        return []

    def afronden(self, reden: str, ctx: Ctx) -> str:
        self.t1 = ctx.t
        self.klaar = True
        if not self.tekst:
            self.tekst = f"{reden}: {self.naam}."
        return self.tekst

    @property
    def voortgang(self) -> float:
        return 0.0

    def status(self, t: float) -> str:
        return self.tekst or "bezig"

    def tabel_html(self, ctx: Ctx) -> str:
        return ""

    def melding(self) -> tuple[str, str] | None:
        """(titel, tekst) voor de melding na afloop, of None."""
        return (f"{self.naam} klaar", self.tekst) if self.tekst else None


# ---------------------------------------------------------------- opstartcurve
def curve_analysis(c: dict) -> list[str]:
    """Uitleg bij een opstartcurve in gewone taal, toegespitst op de CaraVan Guard-print."""
    pts, uit = c["pts"], []
    if c["cc_at"] is not None:
        v = c["cc_at"]
        if v < 1.5:
            uit.append(f"De stroomgrens werd al bij {nl(v, 1)} V bereikt. Dat is bijna altijd kortsluiting tussen "
                       "12 V en massa, of de dikke diode D1 zit verkeerd om (die geleidt dan vanaf ongeveer 0,7 V). "
                       "De uitgang is uitgezet.")
        else:
            uit.append(f"De stroomgrens ({fmt_ma(c['i_lim'])}) werd bereikt bij {nl(v, 1)} V. Er trekt iets meer "
                       "dan verwacht; de uitgang is uitgezet. Zoek een verkeerd geplaatst onderdeel, of de stroomgrens "
                       "is te laag voor wat er op de print zit.")
        return uit
    laag_ = [p for p in pts if p[0] <= 3.0]
    if laag_ and max(p[2] for p in laag_) > 0.010:
        uit.append(f"Onder 3 V loopt al {nl(max(p[2] for p in laag_) * 1000, 0)} mA. Een print trekt daar bijna "
                   "niets; zoek een tinbrug, of een diode of elco die verkeerd om zit.")
    if len(pts) > 4:
        end_i = pts[-1][2] if c.get("i_end") is None else c["i_end"]
        mid = [p for p in pts if 3.5 <= p[0] <= 9.0]
        if mid:
            piek = max(mid, key=lambda p: p[2])
            if piek[2] > 0.02 and piek[2] > end_i * 1.3:
                uit.append(f"Rond {nl(piek[0], 1)} V trekt de print het meest ({nl(piek[2] * 1000, 0)} mA). Dat is "
                           "normaal met de LM2596 erop: een schakelende regelaar trekt bij lage spanning meer stroom "
                           "voor hetzelfde vermogen.")
    if not uit:
        uit.append("Geen bijzonderheden: de stroom loopt rustig mee met de spanning.")
    if pts:
        end_i = pts[-1][2] if c.get("i_end") is None else c["i_end"]
        uit.append(f"Bij {nl(c['v_end'], 1)} V loopt {nl(end_i * 1000, 0)} mA.")
    return uit


def svg_curve(pts, w: int = 520, h: int = 180, i_lim=None, cc_at=None) -> str:
    """Kleine opstartcurve als SVG voor de rapporten: x = spanning, y = stroom."""
    if len(pts) < 2:
        return ""
    L, R, T, B = 46, 10, 10, 26
    pw, ph = w - L - R, h - T - B
    xmax = max(max(p[0] for p in pts), 1.0)
    ymax = nice_ceil(max(max(p[2] for p in pts) * 1000, 5) * 1.2)
    X = lambda v: L + pw * v / xmax
    Y = lambda ma: T + ph * (1 - min(ma / ymax, 1))
    o = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:{w}px;max-width:100%">',
         f'<rect x="{L}" y="{T}" width="{pw}" height="{ph}" fill="#F3EEDF"/>']
    for k in range(5):
        y = T + ph * k / 4
        o.append(f'<line x1="{L}" y1="{y:.1f}" x2="{L + pw}" y2="{y:.1f}" stroke="#DDD5C1"/>')
        o.append(f'<text x="{L - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#6E6A60">'
                 f'{nl(ymax * (1 - k / 4), 0)}</text>')
    for k in range(0, int(xmax) + 1, 2):
        o.append(f'<text x="{X(k):.1f}" y="{T + ph + 16}" text-anchor="middle" font-size="11" fill="#6E6A60">{k}</text>')
    o.append(f'<text x="{L + pw}" y="{h - 2}" text-anchor="end" font-size="11" fill="#6E6A60">V</text>')
    o.append(f'<text x="4" y="{T + 8}" font-size="11" fill="#6E6A60">mA</text>')
    if i_lim and i_lim * 1000 <= ymax:
        o.append(f'<line x1="{L}" y1="{Y(i_lim * 1000):.1f}" x2="{L + pw}" y2="{Y(i_lim * 1000):.1f}" '
                 f'stroke="#D9301F" stroke-dasharray="5 4"/>')
    lijn = " ".join(f"{X(p[0]):.1f},{Y(p[2] * 1000):.1f}" for p in pts)
    o.append(f'<polyline points="{lijn}" fill="none" stroke="#C98400" stroke-width="2"/>')
    if cc_at is not None:
        last = pts[-1]
        o.append(f'<circle cx="{X(last[0]):.1f}" cy="{Y(last[2] * 1000):.1f}" r="5" fill="#D9301F"/>')
    o.append("</svg>")
    return "".join(o)


class Opstartcurve(Proef):
    """Zachte start: uitgang uit, stroomgrens zetten, op 0 V aan en de spanning in stapjes laten oplopen terwijl
    de stroom wordt gemeten. Bij de stroomgrens gaat de uitgang uit."""

    soort = "opstartcurve"

    def __init__(self, v_end: float, i_lim: float, stap_v: float = 0.2, wacht: float = 0.5, hold: float = 0.0,
                 label: str = "opstartcurve"):
        super().__init__()
        self.v_end, self.i_lim, self.stap, self.wacht, self.hold = round(v_end, 2), i_lim, stap_v, wacht, hold
        self.label = label
        self.naam = f"Opstartcurve tot {nl(v_end, 1)} V" if label == "opstartcurve" else label
        self.v = 0.0
        self.pts: list[tuple[float, float, float]] = []     # (v_set, v_gemeten, i)
        self.cc_at: float | None = None
        self.i_end: float | None = None
        self.i_max: float | None = None
        self.fase = "ramp"
        self.t_stap = self.t_hold = 0.0
        self.uitleg: list[str] = []
        self.ok = True

    def start(self, t: float) -> list[Opdracht]:
        self.t_start, self.t_stap = t, t + 0.8
        return [Opdracht(uit=False), Opdracht(i=self.i_lim), Opdracht(v=0.0), Opdracht(uit=True),
                Opdracht(markering=f"{self.label}: start, 0 tot {nl(self.v_end, 1)} V, grens {fmt_ma(self.i_lim)}")]

    @property
    def voortgang(self) -> float:
        return min(1.0, self.v / self.v_end) if self.v_end else 1.0

    def status(self, t: float) -> str:
        if self.klaar:
            return self.tekst
        last = self.pts[-1] if self.pts else None
        s = f"bezig: {nl(last[0], 1)} V, {fmt_ma(last[2])}" if last else "bezig: start op 0 V"
        return s + ("  (vasthouden en middelen)" if self.fase == "hold" else "")

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar:
            return []
        nu = ctx.t
        if self.fase == "ramp":
            if nu - self.t_stap < self.wacht:
                return []
            ta = self.t_stap + self.wacht * 0.4
            pts = ctx.tussen(ta, nu)
            if not pts and nu - self.t_stap < self.wacht * 4:
                return []
            if pts:
                i = sum(p.i for p in pts) / len(pts)
                self.pts.append((self.v, sum(p.v for p in pts) / len(pts), i))
                if ctx.cc or i >= self.i_lim * 0.98:
                    self.cc_at = self.v
                    return self._finish(ctx) + [Opdracht(uit=False)]
            if self.v >= self.v_end - 1e-6:
                if self.hold > 0:
                    self.fase, self.t_hold = "hold", nu
                    return []
                self.i_end = self.pts[-1][2] if self.pts else None
                return self._finish(ctx)
            self.v = round(min(self.v_end, self.v + self.stap), 2)
            self.t_stap = nu
            return [Opdracht(v=self.v)]
        if nu - self.t_hold < self.hold:
            return []
        hp = ctx.tussen(self.t_hold + 1.0, nu)
        uit = []
        if ctx.cc:
            self.cc_at = self.v_end
            uit.append(Opdracht(uit=False))
        elif hp:
            self.i_end = sum(p.i for p in hp) / len(hp)
            self.i_max = max(p.i for p in hp)
        else:
            self.i_end = self.pts[-1][2] if self.pts else None
        return self._finish(ctx) + uit

    def _finish(self, ctx: Ctx) -> list[Opdracht]:
        self.klaar = True
        if self.i_end is None and self.pts:
            self.i_end = self.pts[-1][2]
        self.ok = self.cc_at is None
        self.uitleg = curve_analysis({"pts": self.pts, "cc_at": self.cc_at, "i_lim": self.i_lim, "v_end": self.v_end,
                                      "i_end": self.i_end})
        if self.ok:
            self.tekst = f"Klaar: {fmt_ma(self.i_end or 0)} bij {nl(self.v_end, 1)} V."
            self.oordeel = "goed"
            m = f"{self.label}: klaar, {fmt_ma(self.i_end or 0)} bij {nl(self.v_end, 1)} V"
        else:
            self.tekst = f"Stroomgrens bereikt bij {nl(self.cc_at, 1)} V; uitgang uit."
            self.oordeel = "fout"
            m = f"{self.label}: grens bereikt bij {nl(self.cc_at, 1)} V, uitgang uit"
        return [Opdracht(markering=m)]

    def afronden(self, reden: str, ctx: Ctx) -> str:
        if not self.klaar:
            self.tekst = f"{reden}."
            self.oordeel = "letop"
        return super().afronden(reden, ctx)

    def tabel_html(self, ctx: Ctx) -> str:
        return svg_curve(self.pts, i_lim=self.i_lim, cc_at=self.cc_at) + "".join(
            f"<p class='meta'>{html.escape(x)}</p>" for x in self.uitleg)

    def melding(self):
        return ("Opstartcurve klaar", self.tekst) if self.label == "opstartcurve" else None


# ---------------------------------------------------------------- bouwstappen
BOUWSTAPPEN = [
    {"nr": 0, "titel": "Kale print", "v": None,
     "print": "Alleen de gesoldeerde onderdelen. Nog geen zekeringen en geen modules.",
     "checks": ["Multimeter op weerstand, rood op J23 '12V' en zwart op GND: geen kortsluiting (de waarde loopt op "
                "terwijl de elco laadt).",
                "Andersom (rood op GND): je ziet de diode, dat is goed.",
                "Pootjes aan de onderkant kort geknipt, niets steekt uit boven de bodemsteunen."]},
    {"nr": 1, "titel": "Zekeringen, geen modules", "v": 13.8, "i": 0.10, "verwacht": (0.0, 0.010),
     "print": "Zekering 10 A in F1 en 5 A in F2, jumper JP1 op 2-3. Nog geen modules.",
     "hoog": "Zonder modules hoort er bijna niets te lopen. Zoek een tinbrug, of D1, D2 of de elco verkeerd om.",
     "laag": "",
     "checks": ["J23 '12V' = de voedingsspanning (ongeveer 13,8 V).",
                "Klem J13 '+12V' = dezelfde spanning.",
                "Voetje van de INA219: VIN+ en VIN- allebei ongeveer 13,8 V."]},
    {"nr": 2, "titel": "INA219 in zijn voetje", "v": 13.8, "i": 0.10, "verwacht": (0.0, 0.010),
     "print": "De verbouwde INA219 (R100 eraf, labeltje 'shunt op print') in zijn voetje: VCC links, VIN+ rechts.",
     "hoog": "Zit de INA219 verkeerd om in het voetje? Dan staat er 12 V op de 3,3 V-kant: meteen uit.",
     "laag": "",
     "checks": ["Er wordt niets warm (voel aan de INA219 en de shunt).",
                "J23 '12V' nog steeds ongeveer 13,8 V. Uitlezen kan pas vanaf stap 5."]},
    {"nr": 3, "titel": "LM2596 (5 V)", "v": 13.8, "i": 0.10, "verwacht": (0.002, 0.030),
     "print": "De LM2596 op zijn busjes, vier draden gesoldeerd: IN+, IN-, OUT+ en OUT-.",
     "hoog": "Staat er al iets anders op de 5 V? Zit een draad van de LM2596 verkeerd?",
     "laag": "Krijgt de LM2596 spanning? Controleer de draden naar IN+ en IN-.",
     "checks": ["J23 '5V' = 5,00 V. Klopt het niet, regel dan eerst af met het schroefje op de module.",
                "Nog niets anders op de 5 V aangesloten."]},
    {"nr": 4, "titel": "UPS en 18650", "v": 13.8, "i": 1.0, "verwacht": (0.005, 0.60), "uitval": True,
     "print": "De UPS-module DFR0559: twee draden naar SOLAR IN, twee van de 5V-pinnen bij USB OUT. De 18650 in de "
              "houder, polariteit eerst gemeten.",
     "hoog": "Een lege cel laadt met tot ongeveer 0,45 A aan deze kant. Meer dan dat: controleer de polariteit van "
             "de cel en de draden van de UPS.",
     "laag": "Krijgt de UPS 5 V op SOLAR IN?",
     "checks": ["J23 'UPS' = ongeveer 5 V.",
                "Uitvaltest: in de 5 seconden zonder 12 V blijft J23 'UPS' 5 V en zakt J23 '5V' weg.",
                "Meer dan 0,1 A? Dan laadt de UPS de cel; dat zakt vanzelf als de cel vol raakt."]},
    {"nr": 5, "titel": "ESP32", "v": 13.8, "i": 1.0, "verwacht": (0.03, 0.70),
     "print": "De ESP32 in zijn voetjes (USB naar de onderrand), de korte USB-kabel van de UPS naar de ESP32.",
     "hoog": "Laadt de cel nog? Haal de ESP32 eruit en meet opnieuw om te zien wat hij zelf trekt.",
     "laag": "Start de ESP32? Zit de USB-kabel van de UPS in de ESP32?",
     "checks": ["J23 '3V3' = 3,3 V.",
                "In de lege voetjes: ADS1115 VDD 3,3 V, INA219 VCC 3,3 V, klok VCC 3,3 V, SD VCC 5 V."]},
    {"nr": 6, "titel": "Alle modules", "v": 13.8, "i": 1.5, "verwacht": (0.05, 1.20), "monitor": True,
     "print": "Alle modules in hun voetjes en op hun busjes. Scherm en sensoren mogen aan hun stekkers.",
     "hoog": "Scherm, gassensoren en een ladende cel samen: tot ongeveer 1,2 A is normaal. Meer: haal modules een "
             "voor een los en meet opnieuw.",
     "laag": "Draait de ESP32? Krijgen de modules 5 V en 3,3 V?",
     "checks": ["De ESP32 start en meldt zich op het netwerk.",
                "De monitor gekoppeld (venster CaraVan Guard): de modules hieronder gevonden."]},
]
from ..paden import BASIS

BOUW_BESTAND = BASIS / "korad_bouwstappen.json"


def build_verdict(stap: dict, res: dict) -> tuple[str, str]:
    """Oordeel over een bouwstap: (goed / let op / zoeken, uitleg)."""
    lo, hi = stap["verwacht"]
    if res["cc_at"] is not None:
        return "zoeken", (f"De stroomgrens van {fmt_ma(stap['i'])} werd bereikt bij {nl(res['cc_at'], 1)} V; de "
                          "uitgang is uitgezet. Zoek eerst de oorzaak voordat je verdergaat.")
    i = res["i_end"] or 0.0
    if i > hi:
        return "let op", (f"{fmt_ma(i)}, meer dan de verwachte hooguit {fmt_ma(hi)}. Voel of er iets warm wordt. "
                          + stap.get("hoog", "")).strip()
    if i < lo:
        return "let op", (f"{fmt_ma(i)}, minder dan de verwachte minstens {fmt_ma(lo)}. " + stap.get("laag", "")).strip()
    return "goed", f"{fmt_ma(i)}, binnen de verwachting ({fmt_ma(lo)} tot {fmt_ma(hi)})."


class Bouwstappen:
    """De stand van de bouwstappen: vinkjes, notities en uitkomsten, in korad_bouwstappen.json (oud formaat)."""

    def __init__(self, pad: Path = BOUW_BESTAND):
        self.pad = pad
        self.data = {"start": time.time(), "stappen": {}}
        self.laad()

    def laad(self) -> None:
        try:
            d = json.loads(self.pad.read_text(encoding="utf-8"))
            if isinstance(d.get("stappen"), dict):
                self.data = d
        except (OSError, ValueError, AttributeError):
            pass

    def bewaar(self) -> None:
        try:
            self.pad.write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        except OSError:
            pass

    def stand(self, nr: int) -> dict:
        st = self.data["stappen"].setdefault(str(nr), {})
        n = len(BOUWSTAPPEN[nr]["checks"])
        if len(st.get("checks", [])) != n:
            st["checks"] = [False] * n
        st.setdefault("notitie", "")
        return st

    def status(self, nr: int) -> str | None:
        st = self.data["stappen"].get(str(nr), {})
        if BOUWSTAPPEN[nr]["v"] is None:
            return "goed" if st.get("checks") and all(st["checks"]) else None
        return st.get("oordeel")

    def opnieuw(self) -> None:
        self.data = {"start": time.time(), "stappen": {}}
        self.bewaar()

    def verwerk(self, nr: int, c: Opstartcurve, mon: MonitorBeeld | None) -> tuple[str, str]:
        s = BOUWSTAPPEN[nr]
        st = self.stand(nr)
        res = {"cc_at": c.cc_at, "i_end": c.i_end}
        oordeel, tekst = build_verdict(s, res)
        st.update({"t": c.t1 or time.time(), "i_end": c.i_end, "i_max": c.i_max, "cc_at": c.cc_at, "oordeel": oordeel,
                   "tekst": tekst, "uitleg": c.uitleg,
                   "pts": [[round(a, 2), round(b, 3), round(d, 4)] for a, b, d in c.pts]})
        if s.get("monitor") and mon is not None and mon.vers():
            st["i2c"] = list(mon.laatste.get("i2c") or [])
            st["sd"] = mon.laatste.get("sd")
        self.bewaar()
        return oordeel, tekst

    def rapport_html(self, apparaat: str) -> str:
        esc = html.escape
        rijen, delen = [], []
        for s in BOUWSTAPPEN:
            st = self.data["stappen"].get(str(s["nr"]), {})
            status = self.status(s["nr"]) or "open"
            meas = (esc(fmt_ma(st["i_end"] or 0)) if st.get("oordeel") else
                    ("multimeter" if s["v"] is None else "nog niet gemeten"))
            supply = "-" if s["v"] is None else f"{nl(s['v'], 1)} V, grens {esc(fmt_ma(s['i']))}"
            rijen.append(f"<tr><td>{s['nr']}</td><td>{esc(s['titel'])}</td><td>{supply}</td><td>{meas}</td>"
                         f"<td class='{status.replace(' ', '')}'>{status}</td></tr>")
            checks = "".join(f"<li class='{'ja' if ok else 'nee'}'>{'gedaan' if ok else 'open'}: {esc(txt)}</li>"
                             for txt, ok in zip(s["checks"], st.get("checks", [False] * len(s["checks"]))))
            blok = [f"<h2>Stap {s['nr']}: {esc(s['titel'])}</h2><p class='meta'>{esc(s['print'])}</p>"]
            if st.get("oordeel"):
                blok.append(f"<p><b class='{st['oordeel'].replace(' ', '')}'>{st['oordeel'].upper()}</b> "
                            f"({time.strftime('%d-%m-%Y %H:%M', time.localtime(st['t']))}): {esc(st['tekst'])}</p>")
                blok.append(svg_curve(st.get("pts", []), i_lim=s.get("i"), cc_at=st.get("cc_at")))
                blok.append("".join(f"<p class='meta'>{esc(x)}</p>" for x in st.get("uitleg", [])))
            blok.append(f"<ul class='checks'>{checks}</ul>")
            if s.get("monitor") and st.get("i2c") is not None:
                gevonden = set(st["i2c"])
                blok.append("<p class='meta'>Gevonden op de I2C-bus: " + ", ".join(
                    f"{esc(naam)} (0x{a:02X}) {'ja' if a in gevonden else 'nee'}" for a, naam, _ in EXPECTED_I2C)
                            + f"; microSD {'ja' if st.get('sd') else 'nee'}.</p>")
            if st.get("notitie"):
                blok.append(f"<p class='note'>Notitie: {esc(st['notitie'])}</p>")
            delen.append("".join(blok))
        start = self.data.get("start", time.time())
        return f"""<!doctype html><html lang="nl"><head><meta charset="utf-8"><title>Bouwrapport draagprint</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; background: #F3EFE4; color: #1F2430; margin: 0; }}
  .page {{ max-width: 980px; margin: 24px auto; background: white; padding: 28px 36px; border: 1px solid #DDD5C1; }}
  h1 {{ font-size: 22px; margin: 4px 0 8px; }} h2 {{ font-size: 16px; margin: 26px 0 4px; }}
  .meta {{ color: #6B7280; font-size: 13px; margin: 2px 0; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 14px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid #E6E0D0; }} th {{ color: #6B7280; }}
  .goed {{ color: #1E6B2E; font-weight: 700; }} .letop {{ color: #7A5A00; font-weight: 700; }}
  .zoeken {{ color: #8E1B1B; font-weight: 700; }} .open {{ color: #6B7280; }}
  ul.checks {{ font-size: 13px; padding-left: 20px; }} li.nee {{ color: #6B7280; }}
  .note {{ font-size: 13px; background: #F1EADB; padding: 8px 12px; }}
  @media print {{ body {{ background: white; }} .page {{ margin: 0; border: none; padding: 0; }} }}
</style></head><body><div class="page">
  <p class="meta">Korad paneel 2 · bouwrapport</p>
  <h1>Draagprint CaraVan Guard</h1>
  <p class="meta">Begonnen {time.strftime('%d-%m-%Y', time.localtime(start))}, gemaakt {time.strftime('%d-%m-%Y %H:%M')},
    met {esc(apparaat or 'Korad KA3005PS')}.</p>
  <table><tr><th>Stap</th><th>Wat</th><th>Voeding</th><th>Gemeten</th><th>Oordeel</th></tr>{''.join(rijen)}</table>
  {''.join(delen)}
</div></body></html>
"""


class Uitvaltest(Proef):
    """Bouwstap 4: de uitgang 5 s uit en weer aan, om J23 'UPS' en '5V' te meten."""

    naam = "Uitvaltest"
    soort = "bouwstap"

    def __init__(self, duur: float = 5.0):
        super().__init__()
        self.duur = duur

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = t
        return [Opdracht(uit=False, markering=f"uitvaltest: 12 V weg ({self.duur:g} s)")]

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar or ctx.t - self.t_start < self.duur:
            return []
        self.klaar = True
        self.tekst = "Uitvaltest klaar: 12 V terug."
        return [Opdracht(uit=True, markering="uitvaltest: 12 V terug")]

    def stop(self, reden: str, ctx: Ctx) -> list[Opdracht]:
        return [Opdracht(uit=True)] if "NOODSTOP" not in reden else []

    def status(self, t: float) -> str:
        return "Uitvaltest: 12 V weg, meet nu J23 'UPS' en '5V'"

    def melding(self):
        return None


# ---------------------------------------------------------------- spanningscontrole en ijken
VCHECK_STAPPEN = (10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 13.8, 14.2, 14.5, 14.8)
CAL_STAPPEN = (0, 25, 50, 75, 100)


class Spanningscontrole(Proef):
    """De 12 V-meting van de monitor naast de voeding: elf spanningen, per stap 4 s wachten en 3 s meten."""

    naam = "Spanningsmeting controleren"
    rapport = True

    def __init__(self, vmax: float, v_terug: float):
        super().__init__()
        self.stappen = [v for v in VCHECK_STAPPEN if v <= vmax + 1e-6]
        self.v_terug = min(v_terug, vmax)
        self.idx = -1
        self.t_stap = 0.0
        self.punten: list[dict] = []
        self.gem = self.max = 0.0
        self.ok = True

    @property
    def duur(self) -> float:
        return len(self.stappen) * 7

    @property
    def voortgang(self) -> float:
        return max(0, self.idx) / max(1, len(self.stappen))

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = t
        return [Opdracht(markering="spanningscontrole: start")] + self._volgende(t)

    def _volgende(self, t: float) -> list[Opdracht]:
        self.idx += 1
        if self.idx >= len(self.stappen):
            return self._finish(t)
        self.t_stap = t
        return [Opdracht(v=self.stappen[self.idx])]

    def status(self, t: float) -> str:
        if self.klaar:
            return self.tekst
        return f"stap {self.idx + 1} van {len(self.stappen)}: {nl(self.stappen[self.idx], 1)} V" if 0 <= self.idx < len(self.stappen) else "bezig"

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar or ctx.t - self.t_stap < 7.0:
            return []
        if ctx.cc:
            self.tekst, self.oordeel = "Gestopt: de voeding begrenst (CC).", "fout"
            self.klaar = True
            return [Opdracht(v=self.v_terug), Opdracht(markering="spanningscontrole: gestopt, CC")]
        kp = [p.v for p in ctx.tussen(self.t_stap + 4.0, ctx.t)]
        mp = [m[1] for m in (ctx.monitor.tussen(self.t_stap + 4.0, ctx.t) if ctx.monitor else []) if m[1] is not None]
        if not kp or not mp:
            self.tekst, self.oordeel = "Gestopt: geen metingen van de voeding of de monitor.", "fout"
            self.klaar = True
            return [Opdracht(v=self.v_terug), Opdracht(markering="spanningscontrole: gestopt, geen metingen")]
        self.punten.append({"v": self.stappen[self.idx], "korad": sum(kp) / len(kp), "monitor": sum(mp) / len(mp)})
        return self._volgende(ctx.t)

    def _finish(self, t: float) -> list[Opdracht]:
        self.klaar = True
        verschillen = [p["monitor"] - p["korad"] for p in self.punten]
        self.gem = sum(verschillen) / len(verschillen)
        self.max = max(verschillen, key=abs)
        self.ok = abs(self.gem) <= 0.10 and abs(self.max) <= 0.15
        self.tekst = (f"De 12 V-meting van de monitor wijkt gemiddeld {nl(self.gem, 2)} V af van de voeding, het meest "
                      f"{nl(self.max, 2)} V. " + ("Dat valt binnen de nauwkeurigheid van de INA219 (ongeveer 0,5 %) plus "
                                                  "het kleine verlies over F1 en de shunt." if self.ok else
                                                  "Dat is meer dan verwacht: controleer de draden naar J2 en vraag om "
                                                  "een correctie in de firmware."))
        self.oordeel = "goed" if self.ok else "letop"
        return [Opdracht(v=self.v_terug), Opdracht(markering=f"spanningscontrole klaar: gemiddeld {nl(self.gem, 2)} V verschil")]

    def stop(self, reden: str, ctx: Ctx) -> list[Opdracht]:
        return [] if "NOODSTOP" in reden else [Opdracht(v=self.v_terug)]

    def tabel_html(self, ctx: Ctx) -> str:
        rijen = "".join(f"<tr><td>{nl(p['v'], 1)} V</td><td>{nl(p['korad'], 2)} V</td><td>{nl(p['monitor'], 2)} V</td>"
                        f"<td>{nl(p['monitor'] - p['korad'], 2)} V</td></tr>" for p in self.punten)
        return f"<table><tr><th>Ingesteld</th><th>Voeding</th><th>Monitor</th><th>Verschil</th></tr>{rijen}</table>"

    def melding(self):
        return ("Spanningsmeting gecontroleerd", self.tekst)


class IJken(Proef):
    """Stroommeting van de monitor ijken: de drie strips naar 0, 25, 50, 75 en 100 %, per stand 4 s wachten en
    5 s meten; de verhouding voeding/monitor geeft de nieuwe INA219_SHUNT_CAL."""

    naam = "Stroommeting ijken"
    rapport = True

    def __init__(self, cal_nu: float):
        super().__init__()
        self.cal_nu = cal_nu
        self.idx = -1
        self.t_stap = 0.0
        self.punten: list[dict] = []
        self.herhaald: int | None = None
        self.verhouding: float | None = None
        self.cal_nieuw: float | None = None

    @property
    def voortgang(self) -> float:
        return max(0, self.idx) / len(CAL_STAPPEN)

    def _strips(self, pct: int) -> list[Opdracht]:
        return [Opdracht(monitor={"c": "light", "i": k, "v": pct}) for k in range(3)]

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = t
        return [Opdracht(markering="ijken stroommeting: start")] + self._volgende(t)

    def _volgende(self, t: float) -> list[Opdracht]:
        self.idx += 1
        if self.idx >= len(CAL_STAPPEN):
            return self._finish(t)
        self.t_stap = t
        pct = CAL_STAPPEN[self.idx]
        return self._strips(pct) + [Opdracht(markering=f"ijken: strips {pct} %")]

    def status(self, t: float) -> str:
        if self.klaar:
            return self.tekst
        return f"strips op {CAL_STAPPEN[self.idx]} %, meten…" if 0 <= self.idx < len(CAL_STAPPEN) else "bezig"

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar or ctx.t - self.t_stap < 9.0:
            return []
        pct = CAL_STAPPEN[self.idx]
        if ctx.cc:
            return self._stop_met("Gestopt: de voeding begrenst (CC); stroomgrens hoger zetten")
        lt = ((ctx.monitor.laatste or {}).get("lt") or []) if ctx.monitor else []
        if len(lt) >= 3 and any(x != pct for x in lt[:3]):
            if self.herhaald == self.idx:
                return self._stop_met(f"Gestopt: strips bleven niet op {pct} % (scherm of tijdklok?)")
            self.herhaald = self.idx
            self.t_stap = ctx.t
            return self._strips(pct)
        ta, tb = self.t_stap + 4.0, ctx.t
        kp = [p.i for p in ctx.tussen(ta, tb)]
        mp = [m[2] for m in (ctx.monitor.tussen(ta, tb) if ctx.monitor else []) if m[2] is not None]
        if not kp or not mp:
            return self._stop_met("Gestopt: geen metingen van de voeding of de monitor")
        self.punten.append({"pct": pct, "korad": sum(kp) / len(kp), "monitor": sum(mp) / len(mp)})
        return self._volgende(ctx.t)

    def _stop_met(self, tekst: str) -> list[Opdracht]:
        self.klaar = True
        self.tekst, self.oordeel = tekst + ".", "fout"
        return self._strips(0) + [Opdracht(markering="ijken: " + laag(tekst))]

    def _finish(self, t: float) -> list[Opdracht]:
        self.klaar = True
        bruikbaar = [p for p in self.punten if p["korad"] >= 0.2 and p["monitor"] > 0]
        self.verhouding = sum(p["korad"] / p["monitor"] for p in bruikbaar) / len(bruikbaar) if bruikbaar else None
        if self.verhouding:
            self.cal_nieuw = self.cal_nu * self.verhouding
            self.tekst = (f"Verhouding voeding/monitor gemiddeld {nl(self.verhouding, 4)}. Nieuwe INA219_SHUNT_CAL = "
                          f"{nl(self.cal_nu, 4)} × {nl(self.verhouding, 4)} = {self.cal_nieuw:.4f} (in include/config.h, met een punt).")
            self.oordeel = "goed"
            m = f"ijken klaar: verhouding {nl(self.verhouding, 4)}"
        else:
            self.tekst = "Geen bruikbare punten: er liep nergens 0,2 A of meer."
            self.oordeel = "letop"
            m = "ijken klaar: geen bruikbare punten"
        return self._strips(0) + [Opdracht(markering=m)]

    def stop(self, reden: str, ctx: Ctx) -> list[Opdracht]:
        return self._strips(0)

    def tabel_html(self, ctx: Ctx) -> str:
        rijen = "".join(f"<tr><td>{p['pct']} %</td><td>{fmt_ma(p['korad'])}</td><td>{fmt_ma(p['monitor'])}</td></tr>"
                        for p in self.punten)
        return f"<table><tr><th>Strips</th><th>Voeding</th><th>Monitor</th></tr>{rijen}</table>"

    def melding(self):
        return ("Stroommeting geijkt", self.tekst)


# ---------------------------------------------------------------- UPS-duurtest
class UpsDuurtest(Proef):
    """Uitgang uit; de monitor draait op de 18650 tot hij 30 s niet meer antwoordt."""

    naam = "UPS-duurtest"

    def __init__(self, v0: float, terug_aan: bool):
        super().__init__()
        self.v0, self.terug_aan = v0, terug_aan
        self.v_laatst = v0
        self.laatste_ok = 0.0
        self.duur = 0.0

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = self.laatste_ok = t
        return [Opdracht(uit=False, markering="UPS-duurtest: uitgang uit")]

    def status(self, t: float) -> str:
        if self.klaar:
            return self.tekst
        return f"op de cel sinds {fmt_duur(t - self.t_start)}, cel {nl(self.v_laatst, 2)} V, laatste antwoord {int(t - self.laatste_ok)} s geleden"

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar:
            return []
        mon = ctx.monitor
        if mon is not None and mon.t > self.laatste_ok:
            self.laatste_ok = mon.t
            if mon.laatste and mon.laatste.get("ups_v") is not None:
                self.v_laatst = mon.laatste["ups_v"]
        if ctx.t - self.laatste_ok > 30 and ctx.t - self.t_start > 30:
            self.klaar = True
            self.duur = self.laatste_ok - self.t_start
            self.tekst = (f"De monitor hield het {fmt_duur(self.duur)} vol op de 18650; de cel zakte van "
                          f"{nl(self.v0, 2)} V naar {nl(self.v_laatst, 2)} V.")
            uit = [Opdracht(markering=f"UPS-duurtest klaar: {fmt_duur(self.duur)}")]
            if self.terug_aan:
                self.tekst += " Uitgang weer aan."
                uit.append(Opdracht(uit=True, markering="uitgang weer aan: monitor start, cel laadt"))
            return uit
        return []

    def stop(self, reden: str, ctx: Ctx) -> list[Opdracht]:
        return [Opdracht(uit=True)] if self.terug_aan and "NOODSTOP" not in reden else []


# ---------------------------------------------------------------- nachttest
class Nachttest(Proef):
    """Uren meten: bijzonderheden (stroompiek, CC, monitor stil) als markering, hooguit één per soort per minuut."""

    naam = "Nachttest"
    soort = "nachttest"
    rapport = True

    def __init__(self, uren: float, v: float, i: float, piek_ma: float, stil_s: float, uit_na: bool):
        super().__init__()
        self.uren, self.v, self.i, self.piek, self.stil, self.uit_na = uren, v, i, piek_ma / 1000, stil_s, uit_na
        self.t_eind = 0.0
        self.events: list[tuple[float, str]] = []
        self.counts: dict[str, int] = {}
        self._last_ev: dict[str, float] = {}
        self.cc_sinds: float | None = None
        self.cc_flag = False
        self.mon_flag = False
        self.uur = 0
        self.nieuwe_meldingen: list[str] = []       # voor ntfy, door het paneel geleegd

    @property
    def voortgang(self) -> float:
        if not self.t_eind:
            return 0.0
        return min(1.0, (time.time() - self.t_start) / max(1.0, self.t_eind - self.t_start))

    def start(self, t: float) -> list[Opdracht]:
        self.t_start, self.t_eind = t, t + self.uren * 3600
        return [Opdracht(i=self.i), Opdracht(v=self.v), Opdracht(uit=True),
                Opdracht(markering=f"nachttest: start, {fmt_duur(self.uren * 3600)}")]

    def status(self, t: float) -> str:
        if self.klaar:
            return self.tekst
        return f"loopt: {fmt_duur(t - self.t_start)} van {fmt_duur(self.t_eind - self.t_start)}, {len(self.events)} bijzonderheden"

    def _event(self, t: float, soort: str, tekst: str, melden: bool = True) -> list[Opdracht]:
        self.counts[soort] = self.counts.get(soort, 0) + 1
        vorige = self._last_ev.get(soort)
        if vorige is not None and t - vorige < 60:
            return []
        self._last_ev[soort] = t
        self.events.append((t, tekst))
        if melden:
            self.nieuwe_meldingen.append(tekst)
        return [Opdracht(markering=f"nachttest: {tekst}")]

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar:
            return []
        uit: list[Opdracht] = []
        t = ctx.t
        recent = ctx.tussen(t - 1.2, t)
        if recent and self.piek > 0:
            m = max(p.i for p in recent)
            if m > self.piek:
                uit += self._event(t, "piek", f"stroompiek {nl(m * 1000, 0)} mA (grens {nl(self.piek * 1000, 0)} mA)")
        if ctx.uitgang and ctx.cc:
            if self.cc_sinds is None:
                self.cc_sinds = t
            elif t - self.cc_sinds >= 2 and not self.cc_flag:
                self.cc_flag = True
                uit += self._event(t, "cc", "de voeding begrenst de stroom (CC)")
        else:
            self.cc_sinds, self.cc_flag = None, False
        mon = ctx.monitor
        if mon is not None and mon.adres:
            laatste = mon.t or self.t_start
            if t - laatste >= self.stil:
                if not self.mon_flag:
                    self.mon_flag = True
                    uit += self._event(t, "stil", f"monitor antwoordt al {int(t - laatste)} s niet")
            elif self.mon_flag:
                self.mon_flag = False
                uit += self._event(t, "terug", "monitor antwoordt weer", melden=False)
            for ht, draaide in mon.herstarts:
                if ht > t - 1.5:
                    uit += self._event(t, "herstart", f"monitor herstart na {fmt_duur(draaide)}")
        h = int((t - self.t_start) // 3600)
        if h > self.uur:
            self.uur = h
            uit.append(Opdracht(markering=f"nachttest: {h} uur"))
        if t >= self.t_eind:
            self.klaar = True
            if self.uit_na:
                uit.append(Opdracht(uit=False))
        return uit

    def afronden(self, reden: str, ctx: Ctx) -> str:
        self.t1 = ctx.t
        waarom = "klaar" if reden == "Klaar" else "gestopt"
        pts = ctx.tussen(self.t_start, self.t1)
        w = venster_uit(pts) if len(pts) >= 2 else None
        self.tekst = f"Nachttest {waarom}: {fmt_duur(self.t1 - self.t_start)}, {len(self.events)} bijzonderheden"
        if w:
            self.tekst += (f"; gemiddeld {fmt_ma(w.i_gem)}, hoogste {fmt_ma(w.i_max)}, {nl(w.mah, 0)} mAh, "
                           f"{nl(w.wh, 2)} Wh")
        self.tekst += "."
        self.oordeel = "goed" if waarom == "klaar" and not self.events else "letop"
        self.klaar = True
        return self.tekst

    def tabel_html(self, ctx: Ctx) -> str:
        if not self.events:
            return "<p class='meta'>Geen bijzonderheden.</p>"
        rijen = "".join(f"<tr><td>{time.strftime('%H:%M:%S', time.localtime(t))}</td><td>{html.escape(x)}</td></tr>"
                        for t, x in self.events)
        return f"<h2>Bijzonderheden</h2><table><tr><th>Tijd</th><th>Wat</th></tr>{rijen}</table>"


# ---------------------------------------------------------------- rooktest
ROOK_ITEMS = (("mon", "Monitor antwoordt"), ("fw", "Firmware"), ("i2c", "Modules op de I2C-bus"),
              ("sd", "microSD-kaart"), ("v12", "12 V-meting van de monitor"), ("stroom", "Stroomverbruik van de print"),
              ("ina", "Stroommeting van de monitor"), ("strips", "Strips volgen een commando"),
              ("uitval", "12 V weg en terug"), ("herstart", "Geen herstart tijdens de controle"))


class Rooktest(Proef):
    """Na een update: monitor, firmware, modules, SD, 12 V- en stroommeting, strips, een uitval van de 12 V, en of
    de monitor niet herstartte."""

    naam = "Rooktest"
    soort = "rooktest"
    rapport = True

    def __init__(self, fw_verwacht: str, strips: bool, uitval: bool, basis: float | None):
        super().__init__()
        self.fw_verwacht, self.strips, self.uitval, self.basis = fw_verwacht.strip(), strips, uitval, basis
        self.items = {k: {"st": "wacht", "txt": ""} for k, _ in ROOK_ITEMS}
        self.fase = "mon"
        self.t_fase = 0.0
        self.up0 = None
        self.herstarts0 = 0
        self.i: float | None = None
        self.lt0 = 0
        self.i_voor = 0.0
        self.t_gezien: float | None = None
        self.stijging = 0.0
        self.t_uit = 0.0
        self.mon_bleef = True
        self.uitval_herstart = False
        self.fw = ""
        self.n = {"goed": 0, "let op": 0, "fout": 0}

    def _item(self, k: str, st: str, txt: str = "") -> None:
        self.items[k] = {"st": st, "txt": txt}

    def _fase(self, fase: str, t: float) -> None:
        self.fase, self.t_fase = fase, t

    @property
    def voortgang(self) -> float:
        volgorde = ("mon", "meet", "strip_aan", "strip_uit", "uitval_uit", "uitval_aan", "eind")
        return volgorde.index(self.fase) / len(volgorde) if self.fase in volgorde else 1.0

    def status(self, t: float) -> str:
        if self.klaar:
            return self.tekst
        return {"mon": "wachten op de monitor", "meet": "meten", "strip_aan": "strip 1 naar 20 %",
                "strip_uit": "strip 1 terug", "uitval_uit": "12 V weg (15 s)", "uitval_aan": "12 V terug, wachten op de melding",
                "eind": "afronden"}.get(self.fase, "bezig")

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = t
        self._fase("mon", t)
        self._item("mon", "bezig", "wachten op antwoord (na het flashen kan dat tot een minuut duren)")
        return [Opdracht(markering="rooktest: start")]

    def _meet(self, ctx: Ctx) -> None:
        mon = ctx.monitor
        f = (mon.laatste or {}) if mon else {}
        fw = (f.get("fw") or "").strip()
        self.fw = fw
        if self.fw_verwacht:
            ok = fw.lower().lstrip("v") == self.fw_verwacht.lower().lstrip("v")
            self._item("fw", "goed" if ok else "fout", (fw + ("" if ok else f", verwacht {self.fw_verwacht}: is de "
                       "nieuwe firmware er wel op gezet?")) if fw else "de monitor meldt geen versie")
        else:
            self._item("fw", "info", f"{fw or 'onbekend'} (geen verwachte versie ingevuld)")
        gevonden = set(f.get("i2c") or [])
        mis = [naam for a, naam, req in EXPECTED_I2C if req and a not in gevonden]
        stekker = [naam.split(" ")[0] for a, naam, req in EXPECTED_I2C if not req and a in gevonden]
        if not gevonden:
            self._item("i2c", "fout", "de monitor meldt geen enkele module (sys.i2c is leeg)")
        elif mis:
            self._item("i2c", "fout", "niet gevonden: " + ", ".join(mis))
        else:
            n_req = sum(1 for a, _, req in EXPECTED_I2C if req)
            self._item("i2c", "goed", f"alle {n_req} modules op de print gevonden"
                       + (f"; aan een stekker: {', '.join(stekker)}" if stekker else ""))
        self._item("sd", "goed" if f.get("sd") else "let op", "gevonden" if f.get("sd") else "niet gevonden: zit de kaart erin?")
        kp = ctx.tussen(ctx.t - 3.0, ctx.t)
        mp = mon.tussen(ctx.t - 3.0, ctx.t) if mon else []
        mv = [m[1] for m in mp if m[1] is not None]
        if kp and mv:
            vk, vm = sum(p.v for p in kp) / len(kp), sum(mv) / len(mv)
            d = vm - vk
            st = "goed" if abs(d) <= 0.15 else ("let op" if abs(d) <= 0.30 else "fout")
            self._item("v12", st, f"monitor {nl(vm, 2)} V, voeding {nl(vk, 2)} V (verschil {nl(d, 2)} V)")
        else:
            self._item("v12", "fout", "geen 12 V-meting van de monitor" if kp else "geen metingen van de voeding")
        if not kp:
            self._item("stroom", "fout", "geen metingen van de voeding")
            self._item("ina", "overgeslagen", "geen metingen van de voeding")
            return
        i = sum(p.i for p in kp) / len(kp)
        self.i = i
        if self.basis:
            tol = max(0.03, 0.25 * self.basis)
            d = i - self.basis
            st = "goed" if abs(d) <= tol else ("let op" if abs(d) <= 2 * tol else "fout")
            self._item("stroom", st, f"{fmt_ma(i)}; de basis is {fmt_ma(self.basis)} ({'+' if d >= 0 else '-'}"
                       f"{fmt_ma(abs(d))})" + ("" if st == "goed" else ": trekt de nieuwe firmware meer of minder?"))
        else:
            self._item("stroom", "info", f"{fmt_ma(i)}; nog geen basis. Bewaar deze met de knop als alles goed is.")
        ma = [m[2] for m in mp if m[2] is not None]
        if ma:
            a = sum(ma) / len(ma)
            d, tol = a - i, max(0.015, 0.05 * i)
            self._item("ina", "goed" if abs(d) <= tol else "let op",
                       f"monitor {fmt_ma(a)}, voeding {fmt_ma(i)}" + ("" if abs(d) <= tol else "; ijk de stroommeting"))
        else:
            self._item("ina", "fout", "de monitor geeft geen stroom (INA219?)")

    def _na_strips(self, ctx: Ctx) -> list[Opdracht]:
        if self.uitval:
            self.t_uit = ctx.t
            self._item("uitval", "bezig", "uitgang 15 s uit")
            self._fase("uitval_uit", ctx.t)
            return [Opdracht(uit=False, markering="rooktest: 12 V weg (15 s)")]
        self._item("uitval", "overgeslagen", "niet gekozen")
        self._fase("eind", ctx.t)
        return []

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar:
            return []
        t, el, mon = ctx.t, ctx.t - self.t_fase, ctx.monitor
        f = (mon.laatste or {}) if mon else {}
        lt = f.get("lt") or []
        vers = ctx.mon_vers()
        nieuw = vers and mon.t > self.t_fase
        uit: list[Opdracht] = []
        if self.fase == "mon":
            if vers and mon.t > self.t_start:
                up = f.get("up")
                self.up0, self.herstarts0 = up, len(mon.herstarts)
                txt = f"antwoordt op {mon.adres}"
                if up is not None:
                    txt += f"; draait sinds {fmt_duur(up)}" + (" (vers opgestart)" if up < 300 else "")
                self._item("mon", "goed", txt)
                self._fase("meet", t)
            elif el > 60:
                self._item("mon", "fout", f"geen antwoord binnen een minuut ({((mon.fout if mon else '') or 'geen verbinding')[:70]})")
                return self._finish(ctx)
        elif self.fase == "meet":
            if el >= 3.5:
                self._meet(ctx)
                if self.strips and f.get("lt_ok"):
                    self.lt0 = int(lt[0]) if lt else 0
                    w = ctx.tussen(t - 1.5, t)
                    self.i_voor = sum(p.i for p in w) / len(w) if w else 0.0
                    self._item("strips", "bezig", "strip 1 naar 20 %")
                    self._fase("strip_aan", t)
                    uit += [Opdracht(monitor={"c": "light", "i": 0, "v": 20}, markering="rooktest: strip 20 %")]
                else:
                    if self.strips:
                        self._item("strips", "fout", "de monitor meldt geen ledsturing (PCA9685, lt.ok is 0)")
                    else:
                        self._item("strips", "overgeslagen", "niet gekozen")
                    uit += self._na_strips(ctx)
        elif self.fase == "strip_aan":
            if nieuw and lt and lt[0] == 20:
                if self.t_gezien is None:
                    self.t_gezien = t
                if t - self.t_gezien >= 1.5:
                    w = ctx.tussen(t - 1.0, t)
                    self.stijging = (sum(p.i for p in w) / len(w) - self.i_voor) if w else 0.0
                    self._fase("strip_uit", t)
                    uit += [Opdracht(monitor={"c": "light", "i": 0, "v": self.lt0}, markering=f"rooktest: strip {self.lt0} %")]
            elif el > 8:
                self._item("strips", "fout", f"strip 1 ging niet naar 20 % (de monitor meldt {lt[0] if lt else '-'} %): commando niet aangekomen?")
                uit += [Opdracht(monitor={"c": "light", "i": 0, "v": self.lt0})] + self._na_strips(ctx)
        elif self.fase == "strip_uit":
            if nieuw and lt and lt[0] == self.lt0:
                txt = (f"strip 1 ging naar 20 % en terug naar {self.lt0} %; de stroom steeg "
                       f"{fmt_ma(max(0.0, self.stijging))}")
                if self.stijging < 0.005:
                    txt += " (er hangt waarschijnlijk geen strip aan kanaal 1)"
                self._item("strips", "goed", txt)
                uit += self._na_strips(ctx)
            elif el > 8:
                self._item("strips", "let op", f"strip 1 ging naar 20 %, maar niet terug naar {self.lt0} %")
                uit += self._na_strips(ctx)
        elif self.fase == "uitval_uit":
            if el >= 15:
                self.mon_bleef = vers
                self._item("uitval", "bezig", "12 V weer aan, wachten op de melding")
                self._fase("uitval_aan", t)
                uit += [Opdracht(uit=True, markering="rooktest: 12 V terug")]
        elif self.fase == "uitval_aan":
            ev = [(et, s.lower()) for et, s in (mon.gebeurtenissen if mon else []) if et >= self.t_uit]
            weg = any("12 v weg" in s for _, s in ev)
            terug = any("12 v terug" in s for et, s in ev if et >= self.t_fase)
            if (terug and vers and el >= 3) or el > 40:
                if not self.mon_bleef:
                    self._item("uitval", "let op", "de monitor viel weg zonder 12 V: is de UPS-cel geladen en geplaatst?"
                               + ("" if vers else " Hij antwoordt nog steeds niet."))
                    self.uitval_herstart = bool(mon) and len(mon.herstarts) > self.herstarts0
                elif weg and terug:
                    self._item("uitval", "goed", "de monitor meldde '12 V weg' en '12 V terug' en bleef bereikbaar op de UPS")
                else:
                    mis = [x for x, ok in (("'12 V weg'", weg), ("'12 V terug'", terug)) if not ok]
                    self._item("uitval", "fout", "geen melding " + " en ".join(mis))
                self._fase("eind", t)
        elif self.fase == "eind":
            if el >= 1.5:
                return uit + self._finish(ctx)
        return uit

    def _finish(self, ctx: Ctx) -> list[Opdracht]:
        self.klaar = True
        mon = ctx.monitor
        if self.items["mon"]["st"] == "goed":
            herstarts = (len(mon.herstarts) - self.herstarts0) if mon else 0
            up = (mon.laatste or {}).get("up") if mon else None
            if herstarts == 0:
                self._item("herstart", "goed", "de monitor draaide de hele controle door" + (f" (nu {fmt_duur(up)})" if up is not None else ""))
            elif self.uitval_herstart:
                self._item("herstart", "let op", "herstart door de uitval van de 12 V (UPS-cel leeg of niet geplaatst?)")
            else:
                self._item("herstart", "fout", f"de monitor is {herstarts} keer herstart tijdens de controle: kijk op de seriële monitor")
        for k, it in self.items.items():
            if it["st"] in ("wacht", "bezig"):
                self.items[k] = {"st": "overgeslagen", "txt": "niet aan toegekomen"}
        self.n = {s: sum(1 for it in self.items.values() if it["st"] == s) for s in ("goed", "let op", "fout")}
        verdict = "fout" if self.n["fout"] else ("let op" if self.n["let op"] else "goed")
        self.oordeel = {"goed": "goed", "let op": "letop", "fout": "fout"}[verdict]
        self.tekst = (f"Rooktest {verdict.upper()}: {self.n['goed']} goed, {self.n['let op']} let op, {self.n['fout']} fout"
                      + (f", firmware {self.fw}" if self.fw else "") + ".")
        slecht = [naam for k, naam in ROOK_ITEMS if self.items[k]["st"] in ("fout", "let op")]
        if slecht:
            self.tekst += " Kijk naar: " + ", ".join(slecht) + "."
        return [Opdracht(markering=f"rooktest {verdict}: {self.n['goed']} goed, {self.n['let op']} let op, {self.n['fout']} fout")]

    def stop(self, reden: str, ctx: Ctx) -> list[Opdracht]:
        uit = []
        if self.fase in ("strip_aan", "strip_uit"):
            uit.append(Opdracht(monitor={"c": "light", "i": 0, "v": self.lt0}))
        for it in self.items.values():
            if it["st"] in ("wacht", "bezig"):
                it.update(st="overgeslagen", txt="gestopt")
        self.tekst = reden + (". De uitgang staat uit." if self.fase == "uitval_uit" else ".")
        self.oordeel = "letop"
        return uit

    def tabel_html(self, ctx: Ctx) -> str:
        esc = html.escape
        kl = {"goed": "goed", "let op": "letop", "fout": "fout", "info": "info", "overgeslagen": "overgeslagen"}
        rijen = "".join(f"<tr><td>{esc(naam)}</td><td class='{kl.get(self.items[k]['st'], '')}'><b>{esc(self.items[k]['st'])}</b></td>"
                        f"<td>{esc(self.items[k]['txt'])}</td></tr>" for k, naam in ROOK_ITEMS)
        return f"<table><tr><th>Controle</th><th>Uitslag</th><th>Toelichting</th></tr>{rijen}</table>"


# ---------------------------------------------------------------- onderdelentester
ONDERDELEN = {   # per soort onderdeel: spanning, stroomgrens, uitleg; tvs eerst zacht voorladen tot 14 V (onder 15,3 V)
    "diode": {"naam": "Diode of led", "v": 5.0, "i": 0.010, "kort": "5 V, grens 10 mA", "timeout": 8.0,
              "hoe": "Rode klem aan de anode (bij een led de lange poot), zwarte klem aan de kathode: de kant met de "
                     "streep, bij een led de korte poot. Weet je de richting niet? Meet gewoon: zonder stroom zit hij "
                     "andersom. Een led brandt zacht tijdens de meting."},
    "weerstand": {"naam": "Weerstand", "v": 1.0, "i": 0.100, "kort": "1 V, grens 100 mA", "timeout": 8.0,
                  "hoe": "De weerstand tussen de rode en de zwarte klem; de richting maakt niet uit. Goed voor ongeveer "
                         "1 tot 200 Ω, zoals de verwarming van een MQ-gassensor (ongeveer 33 Ω). Hogere waarden en de "
                         "shunt (0,033 Ω) meet je met de Brymen."},
    "tvs": {"naam": "TVS-diode", "v": 25.0, "i": 0.001, "voor": (14.0, 0.005), "kort": "tot 25 V, grens 1 mA",
            "timeout": 60.0,
            "hoe": "De 1.5KE18A in sperrichting: de streep (kathode) aan de rode klem. Bij 1 mA hoort hij tussen 17,1 "
                   "en 18,9 V door te slaan. Dit mag boven de grens CaraVan Guard omdat de stroom op 1 mA staat; "
                   "daarom alleen het losse onderdeel, nooit de print. Eerst laadt het paneel de uitgang met 5 mA "
                   "tot 14 V, dan gaat het verder met 1 mA; samen meestal binnen een halve minuut."},
}


def part_verdict(soort: str, v: float, i: float, cc: bool) -> tuple[str, str]:
    """Uitleg bij een onderdeelmeting: (kop, uitleg). cc = de voeding begrensde de stroom."""
    if soort == "diode":
        if v < 0.10 and (cc or i >= 0.005):
            return "Kortsluiting", "Bijna 0 V bij 10 mA: kortsluiting, of een doorgeslagen diode."
        if not cc:
            if i < 0.002:
                return "Geen stroom", ("Bij 5 V loopt er niets: de diode zit in sperrichting (draai hem om en meet "
                                       "opnieuw), of hij is onderbroken.")
            return (f"{nl(i * 1000, 0)} mA bij {nl(v, 2)} V",
                    "De stroom komt niet aan de grens van 10 mA: een led met een ingebouwde weerstand, of een "
                    "weerstand in plaats van een diode?")
        if v < 0.45:
            return (f"Schottkydiode: {nl(v, 2)} V", "Lage doorlaatspanning: een schottkydiode, in doorlaatrichting. "
                                                   "De streep (kathode) zit aan de zwarte klem.")
        if v < 0.95:
            return (f"Diode: {nl(v, 2)} V", "Een gewone siliciumdiode in doorlaatrichting; de streep (kathode) zit "
                                           "aan de zwarte klem. De P1000M (D1) en de TVS (D2) geven hier ongeveer "
                                           "0,6 tot 0,8 V.")
        if v < 1.5:
            return f"{nl(v, 2)} V", "Meer dan een gewone diode: twee diodes in serie, of een diode met een weerstand?"
        if v < 2.4:
            return f"Led: {nl(v, 2)} V", "Een rode, oranje of gele led. De lange poot (anode) zit aan de rode klem."
        if v < 3.8:
            return f"Led: {nl(v, 2)} V", "Een groene, blauwe of witte led. De lange poot (anode) zit aan de rode klem."
        return f"{nl(v, 2)} V", "Hoger dan een led: meer leds in serie?"
    if soort == "weerstand":
        if not cc and i < 0.0015:
            return "Meer dan 700 Ω", ("Bij 1 V loopt bijna niets: een hoge weerstand, of hij is onderbroken. Meet "
                                      "deze met de Brymen.")
        if v < 0.02:
            return "Bijna 0 Ω", "Kortsluiting of een draad (minder dan 0,2 Ω)."
        r = v / max(i, 0.0005)
        if i < 0.005:
            return f"Ongeveer {nl(r, 0)} Ω", "Grof: bij 1 V loopt maar weinig stroom. Meet deze nauwkeuriger met de Brymen."
        fout = max(0.002 / i, 0.01 / v) * 100
        txt = f"Op ongeveer {nl(fout, 0)} % nauwkeurig: de voeding meet de stroom in stappen van 1 mA."
        if r < 5:
            txt += " Bij zo'n kleine waarde tellen de meetsnoeren mee (samen ongeveer 0,05 Ω)."
        if 25 <= r <= 45:
            txt += " Dat past bij de verwarming van een MQ-gassensor (ongeveer 33 Ω)."
        return f"{nl(r, 2 if r < 10 else 1 if r < 100 else 0)} Ω", txt
    if v >= 24.0:
        return "Geen doorslag onder 25 V", ("Geen TVS van 18 V, of hij zit niet goed aangesloten (klemmen, "
                                            "onderbroken draad).")
    if v < 0.10:
        return "Kortsluiting", "Bijna 0 V: de TVS is doorgeslagen (kortgesloten). Niet gebruiken."
    if v < 1.2:
        return (f"Doorlaatrichting: {nl(v, 2)} V", "De TVS zit andersom. Zet de streep (kathode) aan de rode klem "
                                                   "en meet opnieuw.")
    ok = 17.1 <= v <= 18.9
    return f"Doorslag bij {nl(v, 1)} V", ("Dat past bij de 1.5KE18A (17,1 tot 18,9 V bij 1 mA): goed voor D2."
                                          if ok else "De 1.5KE18A hoort tussen 17,1 en 18,9 V door te slaan; deze "
                                                     "wijkt af. Andere TVS, of beschadigd?")


class Onderdeel(Proef):
    """De voeding als meetinstrument voor een los onderdeel: een paar seconden aan met een lage stroomgrens tot
    de meting stilstaat, dan uit en de vorige instellingen terug."""

    soort = "onderdeel"

    def __init__(self, soort: str, v_terug: float | None, i_terug: float | None, vmax: float, imax: float):
        super().__init__()
        self.soort_onderdeel = soort
        self.m = ONDERDELEN[soort]
        self.naam = f"Onderdeel meten: {self.m['naam'].lower()}"
        self.v_terug, self.i_terug, self.vmax, self.imax = v_terug, i_terug, vmax, imax
        self.fase = "voor" if "voor" in self.m else "meet"
        self.t_meet = 0.0
        self.ccs: list[tuple[float, bool]] = []
        self.v = self.i = None
        self.cc = False
        self.kop = self.uitleg = ""
        self.pts: list[tuple[float, float, float]] = []

    def start(self, t: float) -> list[Opdracht]:
        self.t_start = self.t_meet = t
        v0, i0 = self.m.get("voor", (self.m["v"], self.m["i"]))
        return [Opdracht(uit=False), Opdracht(i=i0), Opdracht(v=v0), Opdracht(uit=True),
                Opdracht(markering=f"onderdeel meten: {self.m['naam'].lower()}, {self.m['kort']}")]

    def status(self, t: float) -> str:
        if self.klaar:
            return self.kop or self.tekst
        return "voorladen tot 14 V" if self.fase == "voor" else "meten…"

    @staticmethod
    def _venster(pts: list[Meting]) -> bool:
        if len(pts) < 3:
            return False
        vs, cs = [p.v for p in pts], [p.i for p in pts]
        return (max(vs) - min(vs) <= max(0.03, 0.004 * max(vs)) and max(cs) - min(cs) <= max(0.0015, 0.02 * max(cs)))

    def tik(self, ctx: Ctx) -> list[Opdracht]:
        if self.klaar:
            return []
        self.ccs.append((ctx.t, ctx.cc))
        t = ctx.t
        if self.fase == "voor":
            w = ctx.tussen(max(t - 1.0, self.t_start + 0.8), t)
            if (self._venster(w) and t - self.t_start > 1.6) or t - self.t_start > 12:
                self.fase, self.t_meet = "meet", t
                return [Opdracht(i=self.m["i"]), Opdracht(v=self.m["v"])]
            return []
        w = ctx.tussen(max(t - 1.0, self.t_meet + 0.8), t)
        stil = self._venster(w)
        if (stil and t - self.t_meet > 1.6) or t - self.t_start > self.m["timeout"]:
            return self._finish(ctx, w, stil)
        return []

    def _herstel(self) -> list[Opdracht]:
        uit = [Opdracht(uit=False)]
        if self.i_terug is not None:
            uit.append(Opdracht(i=min(self.i_terug, self.imax)))
        if self.v_terug is not None:
            uit.append(Opdracht(v=min(self.v_terug, self.vmax)))
        return uit

    def _finish(self, ctx: Ctx, w: list[Meting], stil: bool) -> list[Opdracht]:
        self.klaar = True
        self.pts = [(p.t - self.t_start, p.v, p.i) for p in ctx.tussen(self.t_start, ctx.t)]
        if not w:
            self.kop, self.uitleg = "Geen meting", "De voeding gaf geen metingen; is hij nog verbonden?"
        else:
            self.v, self.i = sum(p.v for p in w) / len(w), sum(p.i for p in w) / len(w)
            vlaggen = [c for tt, c in self.ccs if w[0].t <= tt <= w[-1].t]
            self.cc = bool(vlaggen) and sum(vlaggen) * 2 >= len(vlaggen)
            self.kop, self.uitleg = part_verdict(self.soort_onderdeel, self.v, self.i, self.cc)
            if not stil:
                self.uitleg += " De meting werd niet helemaal stil; meet voor de zekerheid nog een keer."
        meet = "" if self.v is None else f"{nl(self.v, 2)} V, {nl(self.i * 1000, 0)} mA, {'CC' if self.cc else 'CV'}"
        self.tekst = f"{self.uitleg} Gemeten: {meet}." if meet else self.uitleg
        self.oordeel = "goed"
        return self._herstel() + [Opdracht(markering=f"onderdeel ({self.m['naam'].lower()}): {self.kop}")]

    def stop(self, reden: str, ctx: Ctx) -> list[Opdracht]:
        self.kop = reden
        return self._herstel()

    def melding(self):
        return None
