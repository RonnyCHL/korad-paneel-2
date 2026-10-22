# Inventaris: alles wat het oude Korad paneel kan

Opgemaakt 22-10-2026 uit de README en de code van `D:\Ronny\Tools\korad\korad_paneel.py` (6.700 regels, tkinter).
Afspraak: **niets vervalt**. Elke regel krijgt in het nieuwe paneel een plek; afvinken zodra het nieuwe paneel
het aantoonbaar kan (met de nagebootste voeding, en daarna aan de echte).

Legenda: `[ ]` nog te bouwen, `[x]` klaar in het nieuwe paneel, `[~]` anders opgelost (staat erbij hoe).

## Verbinding en veiligheid

- [ ] Poort kiezen (COM-lijst, Vernieuwen), verbinden, verbreken; `*IDN?` tonen (model, versie, serienummer).
- [ ] De poort kan maar door één programma open zijn: duidelijke melding als een ander script hem heeft.
- [ ] Grens per project (CaraVan Guard 15 V/4 A, EMSN-auto 5,5 V/2 A, Vrij 30 V/5 A): alles daarboven geweigerd
      (instellen, geheugenknoppen, programma's, accusimulatie); hoger gezet aan de voorkant met uitgang aan →
      uitgang uit en alarm. Uitzondering: de TVS-meting van de onderdelentester (met stroomgrens ≤ 1,5 mA).
- [ ] Esc = noodstop in elk venster: uitgang uit en alles stoppen.
- [ ] Vangnet: bij sluiten met uitgang aan vragen; bij verbinden melden dat de uitgang nog aan stond; een
      onverwachte fout stopt de proef, zet de uitgang uit en schrijft `korad_fouten.log`.
- [ ] Bij spanning verhogen terwijl de uitgang aan staat: bevestiging vragen.
- [ ] Stroomgrens eerst, dan spanning, dan pas uitgang (volgorde van de commando's).

## Meters en status

- [ ] Ringmeters spanning, stroom, vermogen, met de waarde in het midden en de ingestelde waarde als merkteken.
- [ ] CV/CC-lampjes, uitgang aan/uit, bewaking actief.
- [ ] Energieteller sinds een moment (mAh, Wh, duur), op nul te zetten.
- [ ] "Stroom in beeld": hoogste, gemiddelde, laagste, lading in het zichtbare venster (1, 5, 30 min).
- [ ] Piep bij langer dan een halve seconde begrenzen (CC), uit te zetten.
- [ ] Scherp op schaal 150/200 % (DPI-bewust), vensters binnen het scherm houden.

## Bediening

- [ ] Spanning en stroomgrens invullen en Instellen.
- [ ] Uitgang aan/uit.
- [ ] Vier geheugenknoppen (M1–M4) met labels die uit de voeding gelezen worden na gebruik.
- [ ] Accu nabootsen: van … V naar … V in … minuten met inwendige weerstand R (spanning zakt mee met de stroom).
- [ ] Notitie als markering in grafiek, log en rapport.
- [ ] Mini-venster, altijd bovenop: spanning, stroom, CC en een uit-knop.

## Grafiek en logboek

- [ ] Grafiek spanning + stroom, meetcursor, slepen/scrollen om te zoomen, dubbelklik terug naar live; vensters
      1 min, 5 min, 30 min.
- [ ] Markeringen in de grafiek (eigen notities, stappen van programma's, meldingen van de monitor, grens).
- [ ] CSV-log starten/stoppen (kolommen tijd, V, A, en monitor_V, monitor_A, ups_V als de monitor gekoppeld is).
- [ ] Oude logs openen in de grafiek; logs vergelijken (twee over elkaar, tabel van verschillen, rapport).
- [ ] HTML-rapport van een stuk grafiek (afdrukbaar als PDF).
- [ ] Werkboek: alles wat gemeten is op datum (soort, titel, bestand, uitleg), staafgrafiek per dag, zoeken,
      dubbelklik opent log of rapport; map scannen voor oude rapporten/logs.

## Bewaking

- [ ] Drie regels: stroom/spanning/vermogen boven/onder een waarde gedurende … s → uitgang uit of waarschuwen.
- [ ] Opgeslagen in `korad_bewaking.json`.

## Testprogramma's

- [ ] Stappen met sprong of helling, spanning, stroomgrens, uitgang aan/uit, duur; herhalen; uit na afloop.
- [ ] Verwachting per stap: gemiddelde stroom tussen grenzen vanaf … s, en/of een melding van de monitor.
- [ ] Opslaan, openen (`testprogrammas/*.json`, `laatste.json`), duur ook als ':30' of '45 s'.
- [ ] Uitslag na afloop: hoeveel controles goed, in grafiek, rapport en melding.

## Projecten

### CaraVan Guard (monitor via wifi, `/api/status` en `/api/events`)

- [ ] Koppelen op adres/`caravan.local`; 12 V, stroom en UPS-cel gestippeld in de grafiek; meldingen als markering.
- [ ] Caravanproeven (testprogramma's): walstroom weg, wiebelende stekker, zakkende spanning, rijden, lader
      drietraps, auto starten.
- [ ] UPS-duurtest (uitgang uit, 18650 volgen tot de monitor 30 s zwijgt; daarna desgewenst weer aan).
- [ ] Stroommeting ijken (strips 0/25/50/75/100 %, nieuwe `INA219_SHUNT_CAL`).
- [ ] Spanningsmeting controleren (10,5–14,8 V in elf stappen).
- [ ] Bouwstappen draagprint (stap 0–6 uit hoofdstuk 3, zachte start, oordeel per stap, meetpunten J23,
      uitvaltest, I2C-adressen; voortgang in `korad_bouwstappen.json`; bouwrapport).
- [ ] Opstartcurve (spanning in stapjes omhoog, stroom getekend, uitleg in gewone taal).
- [ ] Rooktest na een update (monitor, firmware, zes I2C-modules, SD, 12 V- en stroommeting, stroom tegen basis,
      strip 1 op 20 %, 15 s zonder 12 V; ring voor de uitslag; rapport).
- [ ] Nachttest (uren meten, log in `logs/`, meldingen, rapport aan het eind; stil).

### EMSN-auto (T-Beam, seriële log op COM6)

- [ ] Startproef "Bordje: N starts" (uit/aan, i2c-keuring goed/dood/half, stroom na 3/10/30 s, poort sluiten
      vóór uit en terugzoeken na aan; rapport; werkboek).
- [ ] Programma's: auto aan-uit (20x), laadt het (30 min), wiebelende stekker.

### Vrij

- [ ] Alleen de grens van de voeding.

## Gereedschap

- [ ] Onderdelentester: diode/led (5 V, 10 mA), weerstand (1 V, 100 mA), TVS-diode (14 V/5 mA, dan tot 25 V/1 mA,
      uitval bij > 4 mA); ringmeters, schaal met zones, grafiekje; vorige instellingen terug.

## Meldingen

- [ ] ntfy (server, onderwerp): alarm, programma/duurtest/ijking klaar, voeding onbereikbaar met uitgang aan.
- [ ] Gesproken meldingen (Windows-stem, Nederlands) bij stroomgrens, noodstop/alarm, uitslagen; nachttest stil.
- [ ] Telefoon als afstandsbediening: webpagina op het thuisnetwerk (poort 8085, code in de link, QR-code);
      kijken, markering, uitgang UIT (aanzetten alleen aan de laptop).

## Overig

- [ ] Instellingen in `korad_instellingen.json` (project, monitor, ntfy, geluid, web, spraak, rooktest, poorten).
- [ ] Proef van het hele paneel met een nagebootste voeding en monitor (`tests/proef_paneel.py`, met
      belastingsmodellen: gewone belasting, print met LM2596, kortsluiting, lekstroom, diode, led, weerstand, TVS).
- [ ] Handboek (PDF uit HTML, met voorbeeldschermen uit de nagebootste voeding).
- [ ] Snelkoppeling/icoon; starten zonder console.

## Nieuw in paneel 2 (afgesproken 22-10-2026)

- [ ] Qt (PySide6); Korad-laag los, zodat een andere voeding erbij kan.
- [ ] Indelingen: Eenvoudig, Uitgebreid, Meetbank, Presentatie, Mini; onthouden per project.
- [ ] Thema's donker/licht, accentkleur, kleurenblindveilig (status nooit alleen met kleur).
- [ ] Toetsen: Esc noodstop, spatie uitgang, pijltjes spanning, cijfers geheugen; Ctrl+K zoekvenster.
- [ ] Proeven als één systeem met een "apparaat onder test" (wifi of seriële log).
- [ ] Stappen-editor met voorbeeldgrafiek; opnamestand.
- [ ] Accu nabootsen 2.0 (ontlaadkrommen lood/LiFePO₄/Li-ion, inwendige-weerstandsproef).
- [ ] Logboek in SQLite, met CSV-export.
- [ ] Bewaker die de uitgang uitzet als het programma zelf vastloopt.
- [ ] Eén .exe met icoon.
