"""De CaraVan Guard-monitor via wifi (`/api/status`, `/api/events`, `/api/cmd`), en een nagebootste monitor.

De echte leest in een eigen thread en geeft alles als signaal door; het paneel houdt het beeld bij in
`MonitorBeeld` (laatste velden, wanneer, fouten, gebeurtenissen, geschiedenis van 12 V, stroom en UPS-cel).
De nagebootste doet de print na: hij krijgt via voed() de stand van de (nagebootste) voeding en reageert daarop:
'12 V weg' en '12 V terug', een UPS-cel die leegloopt zonder 12 V, strips die een commando volgen, een herstart.
"""

from __future__ import annotations

import json
import queue
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from PySide6.QtCore import QTimer, Signal

from .basis import Apparaat

EXPECTED_I2C = (   # adres, naam, op de print zelf (True) of aan een stekker of kabel (False)
    (0x40, "INA219 (stroom en 12 V)", True), (0x41, "PCA9685 (ledstrips)", True),
    (0x48, "ADS1115 (gas, vlotter, regen)", True), (0x68, "DS3231 (klok)", True),
    (0x57, "EEPROM op de klokmodule", True), (0x20, "MCP23017 (reed, buzzer)", True),
    (0x76, "BME280 aan J27", False), (0x23, "BH1750 aan J28", False),
    (0x69, "MPU-6050 aan J29", False), (0x44, "SHT31 via kabel 1", False))


def velden(st: dict) -> dict:
    """De velden uit /api/status die het paneel gebruikt. bat.a is daar negatief bij verbruik."""
    bat, bak, lt = st.get("bat") or {}, st.get("bak") or {}, st.get("lt") or {}
    a = bat.get("a")
    return {"v": bat.get("v"), "a": None if a is None else -a, "w": bat.get("w"), "src": bat.get("src"),
            "ups_ok": bool(bak.get("ok")), "ups_v": bak.get("v"), "ups_pct": bak.get("pct"),
            "lt_ok": bool(lt.get("ok")), "lt": list(lt.get("v") or []), "f2": lt.get("fuse"),
            "fw": str(st.get("fw") or ""), "up": st.get("up"),
            "i2c": list((st.get("sys") or {}).get("i2c") or []), "sd": (st.get("sys") or {}).get("sd")}


def nieuwe_gebeurtenissen(vorige: list, huidige: list) -> list:
    """Nieuwe regels in het logboek van de monitor. Beide lijsten: nieuwste eerst, ring van 10 in RAM.
    Zoek de kleinste k waarbij huidige[k:] aansluit op het begin van vorige; huidige[:k] is dan nieuw."""
    sleutel = lambda e: (e.get("t"), e.get("s"), e.get("v"))
    p, c = [sleutel(e) for e in vorige], [sleutel(e) for e in huidige]
    for k in range(len(c) + 1):
        staart = c[k:]
        if staart == p[:len(staart)]:
            return huidige[:k]
    return huidige


@dataclass
class MonitorBeeld:
    """Wat het paneel van de monitor weet; de proeven lezen hieruit."""
    adres: str = ""
    laatste: dict | None = None
    t: float = 0.0
    fout: str = ""
    fw: str = ""
    up: float | None = None
    gebeurtenissen: list = field(default_factory=list)      # (t, tekst)
    hist: list = field(default_factory=list)                # (t, v, a, ups_v)
    herstarts: list = field(default_factory=list)           # (t, draaide_s)

    def vers(self, t: float | None = None) -> bool:
        return bool(self.laatste) and (t or time.time()) - self.t < 5

    def tussen(self, van: float, tot: float) -> list:
        return [m for m in self.hist if van <= m[0] <= tot]

    def verwerk_stand(self, t: float, f: dict) -> str | None:
        """Nieuwe velden: geeft een markeringstekst terug als de monitor herstart blijkt."""
        self.laatste, self.t, self.fout = f, t, ""
        self.fw = f.get("fw") or self.fw
        up = f.get("up")
        tekst = None
        if up is not None and self.up is not None and up + 5 < self.up:
            self.herstarts.append((t, self.up))
            tekst = f"monitor herstart (draaide {int(self.up // 60)} min)"
        if up is not None:
            self.up = up
        self.hist.append((t, f.get("v"), f.get("a"), f.get("ups_v") if f.get("ups_ok") else None))
        del self.hist[:-200_000]
        return tekst

    def regel(self) -> str:
        """Eén regel voor in het scherm."""
        if not self.adres:
            return "Monitor: niet gekoppeld"
        if self.vers():
            f = self.laatste
            delen = [f"Monitor {self.adres}", f"fw {f['fw']}" if f.get("fw") else None,
                     f"{f['v']:.2f} V".replace(".", ",") if f.get("v") is not None else "12 V: geen meting",
                     f"{f['a'] * 1000:.0f} mA" if f.get("a") is not None else None,
                     f"UPS-cel {f['ups_v']:.2f} V".replace(".", ",") if f.get("ups_ok") and f.get("ups_v") is not None else None]
            return "  ·  ".join(d for d in delen if d)
        sinds = f" sinds {time.strftime('%H:%M:%S', time.localtime(self.t))}" if self.t else ""
        return f"Monitor {self.adres}: geen antwoord{sinds}" + (f" ({self.fout[:40]})" if self.fout else "")


class Monitor(Apparaat):
    """De echte monitor: elke seconde /api/status, elke twee seconden /api/events, commando's via /api/cmd."""

    stand = Signal(float, dict)
    fout = Signal(float, str)
    gebeurtenis = Signal(float, str)
    opdracht_klaar = Signal(bool, dict)
    naam = "CaraVan Guard-monitor"

    def __init__(self, adres: str):
        super().__init__()
        self.adres = adres
        self._q: queue.Queue = queue.Queue()
        self._lopen = False
        self._open = False

    @property
    def open(self) -> bool:
        return self._open

    def start(self) -> None:
        self._lopen = True
        threading.Thread(target=self._lus, daemon=True, name="monitor").start()

    def stop(self) -> None:
        self._lopen = False

    def stuur(self, obj: dict) -> None:
        self._q.put(obj)

    def _url(self, pad: str) -> str:
        return f"http://{self.adres}{pad}"

    def _get(self, pad: str):
        with urllib.request.urlopen(self._url(pad), timeout=2.5) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8"))

    def _post(self, obj: dict, timeout: float = 2.5) -> bool:
        data = urllib.parse.urlencode({"j": json.dumps(obj, separators=(",", ":"))}).encode("ascii")
        req = urllib.request.Request(self._url("/api/cmd"), data=data, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read().decode("utf-8")).get("ok") == 1

    def _lus(self) -> None:
        t_stat = t_ev = 0.0
        vorige = None
        while self._lopen:
            while not self._q.empty():
                obj = self._q.get_nowait()
                try:
                    ok = self._post(obj)
                except Exception:  # noqa: BLE001
                    ok = False
                self.opdracht_klaar.emit(ok, obj)
            nu = time.time()
            if nu - t_stat >= 1.0:
                t_stat = nu
                try:
                    f = velden(self._get("/api/status"))
                    if not self._open:
                        self._open = True
                        self.verbonden.emit(True, self.adres)
                    self.stand.emit(time.time(), f)
                except Exception as e:  # noqa: BLE001
                    if self._open:
                        self._open = False
                        self.verbonden.emit(False, str(e)[:80])
                    self.fout.emit(time.time(), str(e))
            if nu - t_ev >= 2.0:
                t_ev = nu
                try:
                    cur = self._get("/api/events")
                    if isinstance(cur, list):
                        if vorige is not None:
                            for e in reversed(nieuwe_gebeurtenissen(vorige, cur)):   # oudste eerst
                                tekst = str(e.get("s") or "").strip()
                                if tekst:
                                    self.gebeurtenis.emit(time.time(), tekst)
                        vorige = cur
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0.1)


class NagebootstMonitor(Apparaat):
    """Doet de CaraVan Guard-print na. voed(v, i, uitgang) komt van het paneel; elke seconde een stand."""

    stand = Signal(float, dict)
    fout = Signal(float, str)
    gebeurtenis = Signal(float, str)
    opdracht_klaar = Signal(bool, dict)
    naam = "nagebootste monitor"

    def __init__(self, adres: str = "caravan.local", fw: str = "2.4.0", cel_v: float = 4.10, cel_per_s: float = 0.02,
                 stil_ms: int = 1000):
        super().__init__()
        self.adres, self.fw = adres, fw
        self.v, self.i, self.uitgang = 0.0, 0.0, False
        self.cel_v, self.cel_per_s = cel_v, cel_per_s
        self.up = 0.0
        self.lt = [0, 0, 0]
        self.leeft = True
        self._open = False
        self._t_vorig = time.time()
        self._stil_ms = stil_ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tik)
        self.events: list[dict] = []

    @property
    def open(self) -> bool:
        return self._open

    def start(self) -> None:
        self.timer.start(self._stil_ms)

    def stop(self) -> None:
        self.timer.stop()
        self._open = False

    def stuur(self, obj: dict) -> None:
        ok = self.leeft and obj.get("c") == "light" and 0 <= int(obj.get("i", -1)) < 3
        if ok:
            self.lt[int(obj["i"])] = int(obj.get("v", 0))
        self.opdracht_klaar.emit(ok, obj)

    def voed(self, v: float, i: float, uitgang: bool) -> None:
        """De stand van de voeding, zoals de print die ziet."""
        aan_nu = uitgang and v > 9.0
        if aan_nu != (self.uitgang and self.v > 9.0) and self.leeft:
            self.gebeurtenis.emit(time.time(), "12 V terug" if aan_nu else "12 V weg")
        self.v, self.i, self.uitgang = v, i, uitgang

    def _tik(self) -> None:
        nu = time.time()
        dt, self._t_vorig = nu - self._t_vorig, nu
        twaalf = self.uitgang and self.v > 9.0
        if twaalf:
            self.cel_v = min(4.15, self.cel_v + 0.01 * dt)
            if not self.leeft:                       # de print start weer op de 12 V
                self.leeft, self.up = True, 0.0
                self.gebeurtenis.emit(nu, "opgestart")
        else:
            self.cel_v -= self.cel_per_s * dt
            if self.cel_v < 3.0 and self.leeft:
                self.leeft = False                   # de UPS-cel is leeg: de monitor zwijgt
                if self._open:
                    self._open = False
                    self.verbonden.emit(False, "stil (UPS-cel leeg)")
        if not self.leeft:
            self.fout.emit(nu, "geen verbinding (nagebootst: de print staat uit)")
            return
        self.up += dt
        if not self._open:
            self._open = True
            self.verbonden.emit(True, self.adres)
        strips = sum(self.lt) / 300 * 1.0
        f = {"v": round(self.v if twaalf else 0.0, 2), "a": round((self.i if twaalf else 0.0) * 0.98 + strips * 0, 3),
             "w": None, "src": "12v" if twaalf else "ups",
             "ups_ok": True, "ups_v": round(self.cel_v, 2), "ups_pct": max(0.0, min(100.0, (self.cel_v - 3.0) / 1.15 * 100)),
             "lt_ok": True, "lt": list(self.lt), "f2": True, "fw": self.fw, "up": round(self.up, 1),
             "i2c": [a for a, _, req in EXPECTED_I2C if req] + [0x76], "sd": True}
        self.stand.emit(nu, f)
