# Korad paneel 2

Het nieuwe bedieningspaneel voor de Korad KA3005PS labvoeding (en later andere voedingen), in Python met Qt
(PySide6). Opvolger van `D:\Ronny\Tools\korad` (tkinter); dat paneel blijft werken tot dit alles kan.

Besloten op 22-10-2026:

- **Qt (PySide6)**, Python blijft; de Korad-laag los, zodat een andere voeding er later bij kan.
- **Alle functies van het oude paneel blijven.** De lijst staat in `docs/inventaris.md` en wordt afgevinkt.
- **Vier indelingen** (Eenvoudig, Uitgebreid, Meetbank, Presentatie) plus Mini; thema's donker en licht.
- **Eerst ontwerp, dan bouwen.** Het klikbare ontwerp staat op het canvas "Korad paneel 2 ontwerp".

## Volgorde van bouwen

1. Kern zonder scherm: protocol, nagebootste voeding, grenzen, programma's, logboek, rapporten, meldingen.
2. Scherm Eenvoudig; daarna grafiek, programma's, bewaking, logboek, rapporten (Uitgebreid, Meetbank).
3. Projecten als insteekmodules: CaraVan Guard, EMSN-auto, Vrij.
4. Thema's, indelingen, afstandsbediening, spraak, Presentatie, Mini.
5. Eén .exe met icoon; overstap zodra rooktest en startproef foutloos lopen.
