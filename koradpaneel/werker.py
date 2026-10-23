"""De werker: de enige die met de voeding praat, in een eigen thread.

Het scherm stuurt opdrachten (functie + argumenten) in een wachtrij; de werker voert ze uit en leest daarna de
voeding uit, een paar keer per seconde. Alles wat terugkomt gaat als Qt-signaal naar de schermthread. Zo kan een
trage of zwijgende voeding het scherm nooit laten hangen, en raakt de seriële poort nooit twee opdrachten tegelijk.
"""

from __future__ import annotations

import queue
import time

from PySide6.QtCore import QObject, QThread, Signal

from .kern.geschiedenis import Meting
from .voeding.basis import Voeding


class Werker(QObject):
    meting = Signal(object)            # Meting
    stand = Signal(object)             # voeding.basis.Stand
    instellingen = Signal(float, float)
    verbonden = Signal(str)            # identiteit
    verbroken = Signal(str)            # reden
    opdracht_fout = Signal(str)

    def __init__(self, voeding: Voeding, interval: float = 0.2):
        super().__init__()
        self.voeding = voeding
        self.interval = interval
        self._q: queue.Queue = queue.Queue()
        self._thread = QThread()
        self._stop = False
        self.moveToThread(self._thread)
        self._thread.started.connect(self._lus)

    # ---- vanuit de schermthread
    def start(self) -> None:
        self._stop = False
        self._thread.start()

    def stop(self, wacht_s: float = 2.0) -> None:
        self._stop = True
        self._thread.quit()
        self._thread.wait(int(wacht_s * 1000))

    def opdracht(self, fn, *args) -> None:
        """Een aanroep op de voeding inplannen; wordt in de werkthread uitgevoerd, in volgorde."""
        self._q.put((fn, args))

    # ---- in de werkthread
    def _lus(self) -> None:
        try:
            idn = self.voeding.verbind()
        except Exception as e:  # noqa: BLE001
            self.verbroken.emit(f"verbinden mislukt: {e}")
            self._thread.quit()
            return
        self.verbonden.emit(idn)
        teller = 9                                  # meteen de instellingen lezen: staat de voeding boven de grens?
        while not self._stop:
            t0 = time.time()
            try:
                while True:
                    try:
                        fn, args = self._q.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        fn(*args)
                    except OSError:
                        raise
                    except Exception as e:  # noqa: BLE001
                        self.opdracht_fout.emit(str(e))
                    teller = 9                                  # na een opdracht meteen de instellingen lezen
                s = self.voeding.lees()
                self.meting.emit(Meting(t=time.time(), v=s.v_uit, i=s.i_uit))
                self.stand.emit(s)
                teller += 1
                if teller >= 10:
                    teller = 0
                    v, i = self.voeding.lees_instellingen()
                    self.instellingen.emit(v, i)
            except OSError as e:
                self.verbroken.emit(str(e))
                break
            rest = self.interval - (time.time() - t0)
            if rest > 0:
                time.sleep(rest)
        try:
            self.voeding.sluit()
        except Exception:  # noqa: BLE001
            pass
        self._thread.quit()
