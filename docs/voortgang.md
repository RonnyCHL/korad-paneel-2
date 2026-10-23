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

5. **Stap 2c**: bewaking (drie regels, zelfde bestand als het oude paneel), HTML-rapport van het zichtbare stuk
   grafiek of van het stuk tussen de cursors (map `rapporten/`).
6. **Stap 3a/3b**: testprogramma's: het JSON-formaat van het oude paneel (alle negen programma's staan in
   `testprogrammas/` en laden ongewijzigd), hellingen, herhalen, verwachtingen per stap; het venster
   Testprogramma's (Ctrl+P) met voorbeeldgrafiek; de loop draait in het paneel met markeringen per stap, de kaart
   "Lopende proef", en een rapport met de uitslag na afloop. 27 toetsen.

7. **23-10, ochtend, eerste keer aan de echte Korad**: het venster liep rechts en onder uit beeld. Gemeten: de
   kopbalk eiste 1523 px (menubalk MinimumExpanding + de lange *IDN?), het venster 1440x900 op een werkruimte van
   1440x852. Verholpen (commit b3fd6b9): menubalk Preferred, apparaatnaam afgekapt, venster passend en onthouden,
   rolgebied als vangnet, kleinere minimummaten voor de meters.

8. **Stap 3c (deel 1), 23-10 ochtend**: het apparaat onder test (`koradpaneel/apparaat`: het bordje via de seriële
   log, en een nagebootst bordje), de startproef "Bordje: N starts" als toestandsmachine (`kern/startproef.py`)
   met venster (Ctrl+B), rapport met tabel per start, en de werkboek-kern.
9. **Stap 2d**: werkboek-venster (Ctrl+W: zoeken, staafje per dag, openen, notitie, mappen doorzoeken, het oude
   werkboek inlezen), oude logs openen in de grafiek (Ctrl+O, ook het oude CSV-formaat), logs vergelijken (A/B,
   stroom/spanning/vermogen, tabel van verschillen, rapport), geheugenknoppen met labels uit de voeding na RCL en
   rechtsklik = bewaren (SAV), accu nabootsen (Gereedschap, met inwendige weerstand). 41 toetsen.

10. **Stap 4**: meldingen uit één hand (`kern/meldingen.py`: piepjes, de Windows-stem via PowerShell zoals het
    oude paneel, ntfy), het instellingenvenster (Ctrl+, : thema, accent, geluid, spraak met test, ntfy met
    testmelding, telefoon aan/uit met link en QR-code, poorten), thema wisselen zonder herstart (het venster wordt
    opnieuw opgebouwd en de toestand teruggezet), Ctrl+K zoeken over alle menu-opdrachten, de telefoon als
    afstandsbediening (`kern/telefoon.py`, dezelfde pagina als het oude paneel), piep bij CC langer dan 0,5 s,
    meldingen bij alarm, noodstop, programma en startproef klaar. 45 toetsen.

Schermafdrukken maken zonder het venster op het scherm te zetten: `py tests/schermafdruk.py tbeam uit.png
[eenvoudig|uitgebreid|meetbank|presentatie] [ms]`.

## Nog te doen (volgorde)

- Stap 3c (rest): de CaraVan Guard-monitor via wifi (nagebootst en echt) en de proeven die daarop leunen:
  UPS-duurtest, ijken, spanningscontrole, bouwstappen, opstartcurve, rooktest, nachttest; onderdelentester.
- Stap 4 (rest): accu nabootsen 2.0 (ontlaadkrommen), accentkleur echt toepassen, logboek in SQLite.
- Stap 5: één .exe met icoon; handboek; overstap.

## Eerste keer starten

    cd D:\Ronny\Tools\korad-paneel-2
    .venv\Scripts\python korad_paneel2.py --nagebootst tbeam     zonder voeding
    .venv\Scripts\python korad_paneel2.py                         met de Korad (zoekt de poort zelf)
