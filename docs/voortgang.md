# Voortgang Korad paneel 2

## Nacht van 22 op 23 oktober 2026

Gebouwd en vastgelegd (zie `git log`):

1. **Kern en voedingen** (`koradpaneel/kern`, `koradpaneel/voeding`): grenzen per project, de meetgeschiedenis
   (ring, vensterstatistiek, energieteller), de Korad-driver (protocol zoals gemeten), de nagebootste voeding met
   belastingsmodellen (gewone belasting, CaraVan-print, T-Beam-bordje, accu, kortsluiting, lekstroom, diode, led,
   weerstand, TVS), poorten zoeken. 14 toetsen (`py -m pytest`).
2. **Stap 1**: de werker (eigen thread voor de voeding), thema's donker en licht, de ringmeter (QPainter), de
   indeling **Eenvoudig**, het hoofdvenster met project, grens, noodstop (Esc), uitgang (spatie), F1–F4 voor de
   indelingen, F5 voor Mini, instellingen in `korad_instellingen.json`.
3. **Stap 2**: de grafiek (spanning en stroom gekoppeld onder elkaar, markeringen, meetcursor, zoomen, dubbelklik
   terug naar live), de indeling **Uitgebreid** (kleine meters, status, verbruik met "in beeld", bediening,
   plek voor de lopende proef, notitie als markering, CSV-log starten/stoppen).
4. **Stap 2b**: de indeling **Meetbank** (cursors A en B, de getallen van de selectie, export als CSV),
   **Presentatie** (volledig scherm, alleen de meters, Esc = noodstop en terug) en het **Mini-venster** (altijd
   bovenop, met verloopgrafiekje en uit-knop).

Schermafdrukken maken zonder het venster op het scherm te zetten: `py tests/schermafdruk.py tbeam uit.png
[eenvoudig|uitgebreid|meetbank|presentatie] [ms]`.

## Nog te doen (volgorde)

- Stap 2c: bewaking (drie regels), rapport (HTML) van een stuk grafiek, oude logs openen en vergelijken,
  werkboek, geheugenknoppen met labels uit de voeding (SAV/RCL).
- Stap 3: proeven als één systeem met een "apparaat onder test" (CaraVan Guard via wifi, EMSN-auto via de
  seriële log); testprogramma's (JSON van het oude paneel inlezen), UPS-duurtest, ijken, spanningscontrole,
  bouwstappen, opstartcurve, rooktest, nachttest, startproef bordje, onderdelentester.
- Stap 4: ntfy, spraak, telefoon-afstandsbediening, Ctrl+K zoekvenster, instellingenvenster, accu nabootsen 2.0,
  thema wisselen zonder herstart.
- Stap 5: één .exe met icoon; handboek; overstap.

## Eerste keer starten

    cd D:\Ronny\Tools\korad-paneel-2
    .venv\Scripts\python korad_paneel2.py --nagebootst tbeam     zonder voeding
    .venv\Scripts\python korad_paneel2.py                         met de Korad (zoekt de poort zelf)
