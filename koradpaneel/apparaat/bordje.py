"""Het EMSN-auto-bordje (T-Beam) via zijn seriële log, en een nagebootst bordje voor toetsen en oefenen.

DE POORT KOMT EN GAAT MET DE STROOM (gemeten 22-10-2026): de USB-chip van het bordje wordt uit dezelfde 5 V
gevoed, dus 'auto uit' laat COM6 uit Windows verdwijnen (PermissionError op een open poort). Daarom sluit de
proef de poort voor elke 'auto uit' (pauze) en zoekt hij hem na 'auto aan' terug (hervat), met geduld: Windows
doet er een paar seconden over om de poort terug te vinden. DTR en RTS blijven laag, anders reset het openen van
de poort het bordje.
"""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import QTimer

from .basis import Apparaat

BAUD = 115200


class Bordje(Apparaat):
    naam = "EMSN-auto-bordje"

    def __init__(self, poort: str = "COM6"):
        super().__init__()
        self.poort = poort
        self._s = None
        self._lopen = False
        self._gepauzeerd = True
        self._thread: threading.Thread | None = None
        self.fout = ""

    @property
    def open(self) -> bool:
        return self._s is not None

    def start(self) -> None:
        self._lopen = True
        self._gepauzeerd = False
        self._thread = threading.Thread(target=self._lus, daemon=True, name="bordje")
        self._thread.start()

    def pauze(self) -> None:
        self._gepauzeerd = True
        self._sluit("pauze")

    def hervat(self) -> None:
        self._gepauzeerd = False

    def stop(self) -> None:
        self._lopen = False
        self._sluit("gestopt")

    # ---- in de leesthread
    def _probeer_open(self) -> bool:
        import serial
        try:
            s = serial.Serial()
            s.port, s.baudrate, s.timeout = self.poort, BAUD, 0.2
            s.dtr = False
            s.rts = False
            s.open()
        except Exception as e:  # noqa: BLE001 - poort nog niet terug
            self.fout = str(e)
            return False
        self._s, self.fout = s, ""
        self.verbonden.emit(True, self.poort)
        return True

    def _sluit(self, reden: str) -> None:
        s, self._s = self._s, None
        if s is not None:
            try:
                s.close()
            except Exception:  # noqa: BLE001
                pass
            self.verbonden.emit(False, reden)

    def _lus(self) -> None:
        while self._lopen:
            if self._gepauzeerd:
                time.sleep(0.1)
                continue
            if self._s is None:
                if not self._probeer_open():
                    time.sleep(0.5)
                continue
            s = self._s
            try:
                r = s.readline()
            except Exception as e:  # noqa: BLE001 - de stroom ging eraf: de poort is weg
                self.fout = str(e)
                if self._s is s:
                    self._s = None
                try:
                    s.close()
                except Exception:  # noqa: BLE001
                    pass
                self.verbonden.emit(False, f"poort weg: {e}"[:80])
                time.sleep(0.5)
                continue
            if r:
                self.regel.emit(time.time(), r.decode("utf-8", "replace").strip())


BOOT_GOED = ["=== EMSN-auto 0.9.8 — NAGEBOOTST ===",
             "i2c-keuring: sda=1 scl=1 herstel=0->sda=1 bb jjj ack 34:j 68:j 76:j"]
BOOT_DOOD = ["=== EMSN-auto 0.9.8 — NAGEBOOTST ===",
             "i2c-keuring: sda=1 scl=1 herstel=1->sda=1 bb nnn ack 34:n 68:n 76:n"]
BOOT_HALF = ["=== EMSN-auto 0.9.8 — NAGEBOOTST ===",
             "i2c-keuring: sda=1 scl=1 herstel=0->sda=1 bb jjn ack 34:j 68:j 76:n"]
ROM = ["ets Jul 29 2019 12:21:46", "rst:0x1 (POWERON_RESET),boot:0x12 (SPI_FAST_FLASH_BOOT)", "entry 0x400805e4"]


class NagebootstBordje(Apparaat):
    """Doet het bordje na: na hervat() komt de poort na ~1,5 s terug en volgt de boot-log.

    gedrag: 'goed' (altijd goed), 'dood', 'half', 'wissel' (elke derde start dood, zoals het echte bordje in
    oktober 2026), 'lus' (herstartlus: alleen de ROM-bootloader, steeds opnieuw)."""

    naam = "nagebootst bordje"

    def __init__(self, gedrag: str = "wissel", poort_s: float = 1.5, boot_s: float = 2.5):
        super().__init__()
        self.gedrag = gedrag
        self.poort_s, self.boot_s = poort_s, boot_s
        self._open = False
        self._starts = 0
        self._timers: list[QTimer] = []

    @property
    def open(self) -> bool:
        return self._open

    def _later(self, ms: int, fn) -> None:
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(fn)
        t.start(ms)
        self._timers.append(t)

    def _wis(self) -> None:
        for t in self._timers:
            t.stop()
        self._timers.clear()

    def start(self) -> None:
        self._wis()
        self._later(int(self.poort_s * 1000), self._poort_terug)

    def pauze(self) -> None:
        self._wis()
        if self._open:
            self._open = False
            self.verbonden.emit(False, "pauze")

    def hervat(self) -> None:
        self._wis()
        self._starts += 1
        self._later(int(self.poort_s * 1000), self._poort_terug)

    def stop(self) -> None:
        self.pauze()

    def _poort_terug(self) -> None:
        self._open = True
        self.verbonden.emit(True, "COM6 (nagebootst)")
        self._later(int((self.boot_s - self.poort_s) * 1000), self._boot)

    def _rom(self) -> None:
        for r in ROM:
            self.regel.emit(time.time(), r)

    def _boot(self) -> None:
        g = self.gedrag
        if g == "wissel":
            g = "dood" if self._starts % 3 == 0 else "goed"
        if g == "lus":
            for k in range(12):
                self._later(200 * k, self._rom)
            return
        regels = {"goed": BOOT_GOED, "dood": BOOT_DOOD, "half": BOOT_HALF}.get(g, BOOT_GOED)
        for r in ROM + regels:
            self.regel.emit(time.time(), r)
