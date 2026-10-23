"""Meldingen uit één hand: piepjes (winsound), gesproken meldingen (de stem van Windows via een verborgen
PowerShell-proces, zoals het oude paneel) en ntfy naar de telefoon. Wat er aan staat komt uit de instellingen.

Alles loopt in eigen threads; niets hier blokkeert het scherm. Zonder Windows of zonder stem doet het stil niets.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

_EENHEDEN = {"mAh": "milliampère-uur", "mA": "milliampère", "Wh": "wattuur", "V": "volt", "A": "ampère",
             "W": "watt", "Ω": "ohm", "%": "procent"}


def gesproken(tekst: str) -> str:
    """Eenheden voluit voor de stem: '13,8 V' wordt '13,8 volt' (maar 1.5KE18A blijft staan)."""
    return re.sub(r"(?<![\w.,])(\d+(?:,\d+)?)\s*(mAh|mA|Wh|V|A|W|Ω|%)(?!\w)",
                  lambda m: f"{m.group(1)} {_EENHEDEN[m.group(2)]}", str(tekst))


# ---------------------------------------------------------------- ntfy
def ntfy_stuur(server: str, onderwerp: str, titel: str, tekst: str, prioriteit: int = 3, tags=(),
               klaar=None, wacht: bool = False) -> None:
    """Melding naar de telefoon via ntfy: JSON naar de hoofd-URL, zodat titel en tekst UTF-8 mogen zijn.
    In een eigen thread; klaar(ok, fout) wordt daar aangeroepen. wacht=True voor de toetsen."""

    def run():
        try:
            body = json.dumps({"topic": onderwerp, "title": titel, "message": tekst, "priority": prioriteit,
                               "tags": list(tags)}).encode("utf-8")
            req = urllib.request.Request(server.rstrip("/"), data=body, method="POST",
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            ok, fout = True, ""
        except Exception as e:  # noqa: BLE001
            ok, fout = False, str(e)
        if klaar:
            klaar(ok, fout)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    if wacht:
        t.join(15)


# ---------------------------------------------------------------- piep
PIEPEN = {"cc": ((1100, 90), (1100, 90)), "noodstop": ((520, 220), (390, 320)), "alarm": ((880, 160),),
          "klaar": ((660, 120), (880, 160))}


def piep(soort: str) -> None:
    reeks = PIEPEN.get(soort)
    if not reeks or sys.platform != "win32":
        return

    def run():
        try:
            import winsound
            for f, d in reeks:
                winsound.Beep(f, d)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------- spraak
SPREEK_PS = r'''param([string]$Taal = 'nl', [switch]$Stil, [string]$Wav = '')
$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime] | Out-Null
    $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
        Where-Object { $_.Language -like ($Taal + '*') } |
        Sort-Object { $_.Language -ne 'nl-NL' } | Select-Object -First 1
} catch { [Console]::Out.WriteLine('FOUT ' + $_.Exception.Message); [Console]::Out.Flush(); exit 3 }
if (-not $voice) { [Console]::Out.WriteLine('GEEN_STEM'); [Console]::Out.Flush(); exit 2 }
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$synth.Voice = $voice
$path = if ($Wav) { $Wav } else { Join-Path $env:TEMP ('korad_spraak_' + $PID + '.wav') }
[Console]::Out.WriteLine('KLAAR ' + $voice.DisplayName + ' (' + $voice.Language + ')')
[Console]::Out.Flush()
while ($true) {
    $line = [Console]::In.ReadLine()
    if ($null -eq $line) { break }
    if ($line.Trim() -eq '') { continue }
    try {
        $t = $asTask.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]).Invoke(
            $null, @($synth.SynthesizeTextToStreamAsync($line)))
        $t.Wait(-1) | Out-Null
        $rs = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($t.Result)
        $fs = [System.IO.File]::Create($path); $rs.CopyTo($fs); $fs.Close(); $rs.Close()
        if (-not $Stil) { (New-Object System.Media.SoundPlayer $path).PlaySync() }
        [Console]::Out.WriteLine('GESPROKEN ' + $line); [Console]::Out.Flush()
    } catch { [Console]::Out.WriteLine('FOUT ' + $_.Exception.Message); [Console]::Out.Flush() }
}
if (-not $Wav) { Remove-Item $path -ErrorAction SilentlyContinue }
'''


class Spreker:
    """Gesproken meldingen in een eigen PowerShell-proces. toestand: start, ok, geen_stem of fout.
    Wat binnenkomt terwijl het proces nog opstart, wordt bewaard en daarna uitgesproken."""

    def __init__(self, taal: str = "nl", stil: bool = False, wav: Path | None = None):
        self.taal, self.stil, self.wav = taal, stil, wav
        self.proc = None
        self.toestand, self.stem = "start", ""
        self.gesproken_n, self.laatste = 0, ""
        self._wachtend: list[str] = []
        self._lock = threading.Lock()
        if sys.platform == "win32":
            threading.Thread(target=self._run, daemon=True).start()
        else:
            self.toestand, self.stem = "geen_stem", "alleen op Windows"

    def _run(self) -> None:
        try:
            script = Path(tempfile.gettempdir()) / "korad2_spraak.ps1"
            script.write_text(SPREEK_PS, encoding="utf-8-sig")
            args = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script),
                    "-Taal", self.taal] + (["-Stil"] if self.stil else []) + (["-Wav", str(self.wav)] if self.wav else [])
            self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,  # noqa: S603
                                         stderr=subprocess.DEVNULL, creationflags=0x08000000,
                                         text=True, encoding="utf-8", errors="replace")
            eerste = (self.proc.stdout.readline() or "").strip().lstrip("﻿")
            if eerste.startswith("KLAAR"):
                with self._lock:
                    self.stem, self.toestand = eerste[6:], "ok"
                    wachtend, self._wachtend = self._wachtend, []
                for tekst in wachtend:
                    self._schrijf(tekst)
                for regel in self.proc.stdout:
                    if regel.startswith("GESPROKEN"):
                        self.laatste = regel[10:].rstrip("\r\n")
                        self.gesproken_n += 1
            else:
                self.toestand = "geen_stem" if eerste == "GEEN_STEM" else "fout"
                self.stem = eerste or "PowerShell gaf geen antwoord"
                self.stop()
        except Exception as e:  # noqa: BLE001
            self.toestand, self.stem = "fout", str(e)

    def _schrijf(self, tekst: str) -> bool:
        try:
            self.proc.stdin.write(tekst + "\n")
            self.proc.stdin.flush()
            return True
        except (OSError, ValueError, AttributeError):
            self.toestand = "fout"
            return False

    def zeg(self, tekst: str) -> bool:
        tekst = " ".join(str(tekst).split())
        with self._lock:
            if self.toestand == "start":
                self._wachtend.append(tekst)
                return True
        if self.toestand != "ok" or not self.proc:
            return False
        return self._schrijf(tekst)

    def stop(self) -> None:
        p, self.proc = self.proc, None
        if p:
            try:
                p.stdin.close()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------- alles samen
class Meldingen:
    """Eén loket: alarm(), klaar(), noodstop(), cc() kijken in de instellingen wat er mag (geluid, spraak, ntfy)."""

    def __init__(self, inst: dict):
        self.inst = inst
        self.spreker: Spreker | None = None
        self._gezegd = ("", 0.0)
        self.laatste_ntfy = ""          # voor de toetsen en het instellingenvenster: wat er is verstuurd
        self.stil = False               # nachttest: geen geluid

    # ---- bouwstenen
    def zeg(self, tekst: str) -> None:
        if not self.inst.get("spraak") or self.stil:
            return
        nu = time.time()
        if tekst == self._gezegd[0] and nu - self._gezegd[1] < 4:
            return
        self._gezegd = (tekst, nu)
        if self.spreker is None or self.spreker.toestand in ("geen_stem", "fout"):
            if self.spreker is not None and self.spreker.toestand == "fout":
                self.spreker.stop()
            if self.spreker is None or self.spreker.toestand == "fout":
                self.spreker = Spreker()
        self.spreker.zeg(gesproken(tekst))

    def piep(self, soort: str) -> None:
        if self.stil or (soort == "cc" and not self.inst.get("geluid_cc", True)):
            return
        piep(soort)

    def ntfy(self, titel: str, tekst: str, prioriteit: int = 3, tags=(), klaar=None) -> bool:
        n = self.inst.get("ntfy") or {}
        if not (n.get("aan") and (n.get("onderwerp") or "").strip()):
            return False
        self.laatste_ntfy = f"{titel}: {tekst}"
        ntfy_stuur(n.get("server") or "https://ntfy.sh", n["onderwerp"].strip(), f"Korad: {titel}", tekst,
                   prioriteit, tags, klaar)
        return True

    # ---- gebeurtenissen
    def alarm(self, tekst: str) -> None:
        self.piep("alarm")
        self.zeg("Alarm. " + tekst)
        self.ntfy("alarm", tekst, 5, ("rotating_light",))

    def noodstop(self, reden: str = "") -> None:
        self.piep("noodstop")
        self.zeg("Noodstop. Uitgang uit.")
        self.ntfy("noodstop", f"Uitgang uit{(' (' + reden + ')') if reden else ''}", 4, ("octagonal_sign",))

    def klaar(self, titel: str, tekst: str) -> None:
        self.piep("klaar")
        self.zeg(f"{titel}. {tekst}")
        self.ntfy(titel, tekst, 3, ("white_check_mark",))

    def cc(self) -> None:
        self.piep("cc")

    def stop(self) -> None:
        if self.spreker is not None:
            self.spreker.stop()
