"""Het instellingenvenster: thema, geluid en spraak, ntfy, de telefoon als afstandsbediening, poorten.

Werkt op een kopie van de instellingen; pas bij OK gaan ze terug naar het paneel (dat ze bewaart en toepast).
De telefoon kan hier meteen aan en uit, met de link en de QR-code in beeld."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from ..kern import meldingen as md
from ..kern.telefoon import Telefoon, nieuwe_code
from .thema import THEMAS, Thema


def qr_pixmap(tekst: str, module_px: int = 4) -> QPixmap | None:
    try:
        from ..qrcodegen import QrCode
    except ImportError:
        return None
    qr = QrCode.encode_text(tekst, QrCode.Ecc.MEDIUM)
    n, rand = qr.get_size(), 4
    maat = (n + 2 * rand) * module_px
    im = QImage(maat, maat, QImage.Format_RGB32)
    im.fill(0xFFFFFFFF)
    for y in range(n):
        for x in range(n):
            if qr.get_module(x, y):
                for dy in range(module_px):
                    for dx in range(module_px):
                        im.setPixel((x + rand) * module_px + dx, (y + rand) * module_px + dy, 0xFF000000)
    return QPixmap.fromImage(im)


def _kop(tekst: str) -> QLabel:
    l = QLabel(tekst.upper())
    l.setObjectName("kopje")
    return l


def _lijn() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color: #262B36")
    return f


class InstellingenDialoog(QDialog):
    def __init__(self, thema: Thema, inst: dict, meldingen: md.Meldingen, telefoon: Telefoon, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Instellingen")
        self.thema = thema
        self.inst = inst
        self.meldingen = meldingen
        self.telefoon = telefoon
        self.uitkomst: dict | None = None
        buiten = QVBoxLayout(self)
        rol = QScrollArea()
        rol.setWidgetResizable(True)
        rol.setFrameShape(QFrame.NoFrame)
        binnen = QWidget()
        rol.setWidget(binnen)
        root = QVBoxLayout(binnen)
        root.setSpacing(10)
        buiten.addWidget(rol, 1)

        # ---- uiterlijk
        root.addWidget(_kop("Uiterlijk"))
        rij = QHBoxLayout()
        rij.addWidget(QLabel("Thema"))
        self.c_thema = QComboBox()
        for sleutel in THEMAS:
            self.c_thema.addItem(sleutel, sleutel)
        self.c_thema.setCurrentIndex(list(THEMAS).index(inst.get("thema", "donker")))
        rij.addWidget(self.c_thema)
        rij.addSpacing(16)
        rij.addWidget(QLabel("Accentkleur"))
        self.e_accent = QLineEdit(inst.get("accent", "#3D7BF2"))
        self.e_accent.setFixedWidth(120)
        rij.addWidget(self.e_accent)
        rij.addStretch(1)
        root.addLayout(rij)
        u = QLabel("Het thema wisselt meteen, zonder herstart. De accentkleur is de kleur van knoppen en cursors.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        root.addWidget(u)
        root.addWidget(_lijn())

        # ---- geluid en spraak
        root.addWidget(_kop("Geluid en spraak"))
        self.k_geluid = QCheckBox("Piep als de voeding langer dan een halve seconde begrenst (CC)")
        self.k_geluid.setChecked(bool(inst.get("geluid_cc", True)))
        root.addWidget(self.k_geluid)
        rij = QHBoxLayout()
        self.k_spraak = QCheckBox("Gesproken meldingen (de Nederlandse stem van Windows)")
        self.k_spraak.setChecked(bool(inst.get("spraak", False)))
        rij.addWidget(self.k_spraak)
        k = QPushButton("Test spraak")
        k.setObjectName("geheugen")
        k.clicked.connect(self._test_spraak)
        rij.addWidget(k)
        self.l_spraak = QLabel("")
        self.l_spraak.setObjectName("zacht")
        rij.addWidget(self.l_spraak, 1)
        root.addLayout(rij)
        u = QLabel("Geen stem? Windows: Instellingen > Tijd en taal > Spraak > Stemmen beheren > Nederlands toevoegen.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        root.addWidget(u)
        root.addWidget(_lijn())

        # ---- ntfy
        root.addWidget(_kop("Meldingen op je telefoon (ntfy)"))
        n = inst.get("ntfy") or {}
        rooster = QGridLayout()
        rooster.addWidget(QLabel("Server"), 0, 0)
        self.e_ntfy_server = QLineEdit(n.get("server") or "https://ntfy.sh")
        rooster.addWidget(self.e_ntfy_server, 0, 1)
        rooster.addWidget(QLabel("Onderwerp"), 1, 0)
        self.e_ntfy_onderwerp = QLineEdit(n.get("onderwerp") or "")
        self.e_ntfy_onderwerp.setPlaceholderText("bijvoorbeeld korad-ronny-8f3k2")
        rooster.addWidget(self.e_ntfy_onderwerp, 1, 1)
        for e in (self.e_ntfy_server, self.e_ntfy_onderwerp):
            e.setStyleSheet("font-family: inherit; font-size: 14px; padding: 8px 10px")
        root.addLayout(rooster)
        rij = QHBoxLayout()
        self.k_ntfy = QCheckBox("Meldingen versturen (alarm, proef klaar, noodstop)")
        self.k_ntfy.setChecked(bool(n.get("aan")))
        rij.addWidget(self.k_ntfy)
        k = QPushButton("Testmelding")
        k.setObjectName("geheugen")
        k.clicked.connect(self._test_ntfy)
        rij.addWidget(k)
        self.l_ntfy = QLabel("")
        self.l_ntfy.setObjectName("zacht")
        rij.addWidget(self.l_ntfy, 1)
        root.addLayout(rij)
        u = QLabel("Installeer de app ntfy op je telefoon en abonneer je op hetzelfde onderwerp. Het onderwerp werkt als "
                   "wachtwoord: kies iets dat niemand raadt.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        root.addWidget(u)
        root.addWidget(_lijn())

        # ---- telefoon
        root.addWidget(_kop("Telefoon als afstandsbediening"))
        w = inst.get("web") or {}
        rij = QHBoxLayout()
        rij.addWidget(QLabel("Poort"))
        self.e_web_poort = QLineEdit(str(w.get("poort") or 8085))
        self.e_web_poort.setFixedWidth(90)
        rij.addWidget(self.e_web_poort)
        self.k_web = QPushButton("")
        self.k_web.setObjectName("primair")
        self.k_web.clicked.connect(self._web_schakel)
        rij.addWidget(self.k_web)
        k = QPushButton("Nieuwe code")
        k.setObjectName("geheugen")
        k.clicked.connect(self._web_code)
        rij.addWidget(k)
        rij.addStretch(1)
        root.addLayout(rij)
        self.l_web = QLabel("")
        self.l_web.setObjectName("zacht")
        self.l_web.setWordWrap(True)
        root.addWidget(self.l_web)
        self.e_web_url = QLineEdit("")
        self.e_web_url.setReadOnly(True)
        self.e_web_url.setStyleSheet("font-family: inherit; font-size: 13px; padding: 6px 10px")
        root.addWidget(self.e_web_url)
        self.l_qr = QLabel("")
        root.addWidget(self.l_qr, 0, Qt.AlignLeft)
        u = QLabel("Scan de code met de camera van je telefoon (zelfde wifi als de laptop). De eerste keer vraagt "
                   "Windows of Python verbindingen mag ontvangen: kies Privénetwerken en Toestaan. De code in de link "
                   "werkt als wachtwoord; met Nieuwe code werken oude links niet meer.")
        u.setObjectName("zacht")
        u.setWordWrap(True)
        root.addWidget(u)
        root.addWidget(_lijn())

        # ---- apparaten
        root.addWidget(_kop("Apparaten"))
        rooster = QGridLayout()
        rooster.addWidget(QLabel("Poort van de Korad (leeg = zelf zoeken)"), 0, 0)
        self.e_poort = QLineEdit(inst.get("poort") or "")
        self.e_poort.setFixedWidth(110)
        rooster.addWidget(self.e_poort, 0, 1)
        rooster.addWidget(QLabel("Seriële poort van het EMSN-auto-bordje"), 1, 0)
        self.e_emsn = QLineEdit((inst.get("emsn") or {}).get("poort") or "COM6")
        self.e_emsn.setFixedWidth(110)
        rooster.addWidget(self.e_emsn, 1, 1)
        rooster.addWidget(QLabel("CaraVan Guard-monitor (adres of caravan.local)"), 2, 0)
        self.e_monitor = QLineEdit((inst.get("monitor") or {}).get("adres") or "")
        self.e_monitor.setFixedWidth(220)
        rooster.addWidget(self.e_monitor, 2, 1)
        rooster.setColumnStretch(2, 1)
        root.addLayout(rooster)
        root.addStretch(1)

        knoppen = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        knoppen.button(QDialogButtonBox.Ok).setText("Bewaren")
        knoppen.button(QDialogButtonBox.Cancel).setText("Annuleren")
        knoppen.accepted.connect(self._ok)
        knoppen.rejected.connect(self.reject)
        buiten.addWidget(knoppen)
        self.resize(760, 760)
        self._web_toon()

    # ---- knoppen
    def _test_spraak(self) -> None:
        sp = self.meldingen.spreker
        if sp is None or sp.toestand in ("geen_stem", "fout"):
            self.meldingen.spreker = sp = md.Spreker()
        sp.zeg(md.gesproken("Dit is een test. 13,8 V en 230 mA."))
        self.l_spraak.setText("gesproken…" if sp.toestand in ("start", "ok") else f"stem: {sp.stem}")

    def _test_ntfy(self) -> None:
        onderwerp = self.e_ntfy_onderwerp.text().strip()
        if not onderwerp:
            self.l_ntfy.setText("vul eerst een onderwerp in")
            return
        self.l_ntfy.setText("versturen…")

        def klaar(ok, fout):
            self.l_ntfy.setText("verstuurd, kijk op je telefoon" if ok else f"mislukt: {fout[:60]}")

        md.ntfy_stuur(self.e_ntfy_server.text().strip() or "https://ntfy.sh", onderwerp, "Korad: testmelding",
                      "Als je dit leest, werken de meldingen.", 3, ("white_check_mark",), klaar)

    def _web_schakel(self) -> None:
        tel = self.telefoon
        if tel.loopt:
            tel.stop()
            self.inst.setdefault("web", {})["aan"] = False
        else:
            try:
                tel.poort = int(self.e_web_poort.text())
                tel.start()
                self.inst.setdefault("web", {})["aan"] = True
            except (OSError, ValueError) as e:
                self.l_web.setText(f"De webserver kon niet starten: {e}")
                return
        self._web_toon()

    def _web_code(self) -> None:
        self.telefoon.code = nieuwe_code()
        self.inst.setdefault("web", {})["code"] = self.telefoon.code
        self._web_toon()

    def _web_toon(self) -> None:
        tel = self.telefoon
        aan = tel.loopt
        self.k_web.setText("Uitzetten" if aan else "Aanzetten")
        self.l_web.setText("Aan: bereikbaar op het thuisnetwerk." if aan else "Uit.")
        self.e_web_url.setText(tel.url() if aan else "")
        px = qr_pixmap(tel.url(), 4) if aan else None
        self.l_qr.setPixmap(px if px is not None else QPixmap())

    def _ok(self) -> None:
        try:
            poort = int(self.e_web_poort.text())
        except ValueError:
            poort = 8085
        self.uitkomst = {
            "thema": self.c_thema.currentData(), "accent": self.e_accent.text().strip() or "#3D7BF2",
            "geluid_cc": self.k_geluid.isChecked(), "spraak": self.k_spraak.isChecked(),
            "ntfy": {"server": self.e_ntfy_server.text().strip() or "https://ntfy.sh",
                     "onderwerp": self.e_ntfy_onderwerp.text().strip(), "aan": self.k_ntfy.isChecked()},
            "web": {"poort": poort, "code": self.telefoon.code, "aan": self.telefoon.loopt},
            "poort": self.e_poort.text().strip(),
            "emsn": {"poort": self.e_emsn.text().strip() or "COM6"},
            "monitor": {"adres": self.e_monitor.text().strip(), "aan": bool(self.e_monitor.text().strip())},
        }
        self.accept()
