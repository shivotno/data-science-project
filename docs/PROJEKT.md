# Lego-Scanner: Projektstand und Anleitung

## Was wir bisher gemacht haben

1. **Modellwahl:** YOLO26 s, zweistufig: erst Steine finden (Detektor), dann Teil bestimmen (Klassifikator)
2. **Echte Fotos sortiert:** 400 Fotos von 155 Steinen, 17 Teile, mit dem Sortier-Tool. Pro Stein oben/unten oder oben/Seite/unten, alle mit Farbe. Zusätzlich 22 Gruppenfotos mit vielen Steinen (noch ohne Boxen).
3. **Namen angeglichen** an Rebrickable und die Renders:
   - Farben: dark_gray → dark_bluish_gray, light_gray → light_bluish_gray, brown → reddish_brown
   - Teile: 4073 (durchsichtige runde 1×1-Platten, geschlossene Noppe) mit 6141 zusammengelegt
4. **Train/Test-Split pro Stein** (`brick_id`): Alle Fotos eines Steins liegen immer im selben Teil. Pro Teil kommen ca. 30 % der Steine in den Test, mindestens einer. Neue Fotos erweitern den Split, bereits zugeordnete Steine bleiben, wo sie sind. Ergebnis: 276 Fotos (107 Steine) train, 124 Fotos (48 Steine) test, jedes Teil hat Teststeine.
5. **Boxen:** Für jedes Foto wurde automatisch eine Box vorgeschlagen (ohne Schatten) und dann von Hand geprüft oder korrigiert. Alle 400 sind geprüft.
6. **Komprimiert:** Fotos von 3024 px auf 1600 px, 1 GB → 157 MB (Gruppenfotos 51 MB → 8,5 MB).
7. **Renders:** 82 Teile × 300 Bilder = 24 600 Renders, JPEG 1024 px, ca. 600 MB. Alle 17 Teile der echten Fotos sind enthalten. (Ein erster Render-Satz mit 50 Teilen × 1000 Bildern wurde ersetzt.)
8. **Datensätze für den Vergleich:**

   | Modell | Training | Test | Teile zur Auswahl | Zufallstreffer |
   |---|---|---|---|---|
   | A | nur echte Fotos (276) | 124 echte Testfotos | 17 | ca. 6 % |
   | B | nur Renders (24 600) | dieselben 124 | 82 | ca. 1,2 % |
   | C | Renders + echte Fotos (24 876) | dieselben 124 | 82 | ca. 1,2 % |

   C ist das Modell mit allen Steinen. B und C wählen aus deutlich mehr Teilen als A, die Aufgabe ist für sie also schwerer.

## Ordner (`data/`, nicht in Git)

```
data/
├── renders_small/<teil>/        Renders als JPEG + labels.csv (Box, Farbe, Kamera …)
├── real/sorted/<teil>/          sortierte Originalfotos, labels.csv, boxes.csv (nur zum Sortieren nötig)
├── real/split/{train,test}/     Split der Originalfotos
├── real_small/                  dasselbe auf 1600 px (sorted inkl. boxes.csv, split, gruppen)
└── datasets/modell_{a,b,c}/
    ├── detect/                  Stufe 1: images/, labels/ (YOLO-Format), data.yaml
    └── classify/                Stufe 2: {train,test}/<teil>/ ausgeschnittene Steine (224 px)
```

Für Training und Auswertung reichen `renders_small` und `real_small`.

## Anleitung

**Einrichten (einmalig):** [uv](https://docs.astral.sh/uv/) installieren, dann im Projektordner:

```bash
uv sync
```

Daten aus der Cloud herunterladen und so ablegen wie oben unter `data/`.

**Sortier-Tool** (echte Fotos Teilen zuordnen, Boxen prüfen):

```bash
uv run streamlit run app/sortier_tool.py
```

Danach öffnet sich http://localhost:8501.

- **Seite „sortier tool“:** neue Fotos liegen in `data/real/unsorted`.
  1. Die Fotos desselben Steins anhaken.
  2. Optional eine Farbe wählen.
  3. Das Teil anklicken. Die Kacheln zeigen jedes Teil von oben und, falls vorhanden, von der Seite.
  - Neue Teile und Farben kann man über die aufklappbaren Felder anlegen. „Rückgängig“ legt den letzten Stein zurück.
  - Das Ergebnis landet in `data/real/sorted/<teil>/` und in `labels.csv`.
- **Seite „Boxen markieren“:** Die Box-Vorschläge seitenweise prüfen. Passt alles, „Alle passen“ klicken. Passt eine Box nicht, „Korrigieren“ klicken und mit der Maus ein Rechteck ziehen. Gespeichert wird in `data/real/sorted/boxes.csv`, relativ zur Bildgröße, also auch gültig für die verkleinerten Fotos.

**Komprimieren** (legt immer einen neuen Ordner an, die Originale bleiben; fertige Bilder werden übersprungen):

```bash
uv run python -m lego_scanner.preprocessing.compress data/real/sorted data/real_small/sorted --max-size 1600
```

**Train/Test-Split erweitern** (nach neuen Fotos; alter Split vorher umbenennen, seine Zuordnung bleibt erhalten):

```bash
mv data/real/split data/real/split_alt
mv data/real_small/split data/real_small/split_alt
uv run python -m lego_scanner.preprocessing.split --previous data/real_small/split_alt
```

**Datensätze A/B/C bauen** (ca. 1 Minute; einen vorhandenen Ordner `data/datasets` vorher umbenennen oder löschen):

```bash
uv run python -m lego_scanner.preprocessing.build_datasets
```

- Gleiche Bilder werden per Hardlink geteilt und belegen kaum zusätzlichen Platz.
- Den Ordner `data/datasets` nicht in die Cloud hochladen. Jede Person baut ihn selbst, weil in `data.yaml` lokale Pfade stehen.
- `val` zeigt auf test, weil es keinen eigenen Validierungsdatensatz gibt. Einstellungen deshalb vorher festlegen und nicht auf den Testergebnissen optimieren.

**Code:**

| Datei | Inhalt |
|---|---|
| `src/lego_scanner/preprocessing/sorting.py` | Logik des Sortier-Tools: Fotos verschieben, `labels.csv`, Rückgängig |
| `src/lego_scanner/preprocessing/boxes.py` | Box-Vorschlag (Farbe, Helligkeit und Kanten gegenüber dem weißen Papier, ohne Schatten) und `boxes.csv` |
| `src/lego_scanner/preprocessing/compress.py` | Komprimieren |
| `src/lego_scanner/preprocessing/split.py` | Train/Test-Split pro Stein |
| `src/lego_scanner/preprocessing/build_datasets.py` | Ordner für Modell A/B/C |
| `app/sortier_tool.py` | Oberfläche Sortieren |
| `app/pages/Boxen_markieren.py` | Oberfläche Boxen |
| `app/vorschaubilder.csv` | Pro Teil ein von Hand gewähltes Render, das den Stein von oben zeigt (Beispielbild im Tool, falls es kein eigenes Foto „oben“ gibt) |

## Einsatz von KI

Wir haben **Claude** (Anthropic, Modell Opus 5.5) über Claude Code in der Claude-Desktop-App genutzt.

**Wofür:**
- **Beratung:** Modellwahl und Vergleich der YOLO-Varianten, Kompression, Aufbau des fairen A/B/C-Vergleichs (Split pro Stein, gemeinsamer Testdatensatz)
- **Code:** Sortier-Tool, Box-Seite mit automatischen Vorschlägen, Kompressions-, Split- und Datensatz-Skripte, Angleichung der Farb- und Teilenamen.
- **Prüfen:** Daten gezählt und abgeglichen (z. B. Teile und Farben in Fotos vs. Renders, Ansichten pro Stein), Box-Vorschläge an allen Fotos angesehen, alles erst an Kopien getestet.

**Warum:** Damit wir die Werkzeuge rund um die Daten schnell bauen konnten und mehr Zeit für Datenerhebung und Auswertung bleibt.

**Was von uns kam:**
- alle Fotos, die Renders und alle Zuordnungen (Teil, Farbe, Ansicht)
- die Prüfung bzw. Korrektur aller Boxen
- die inhaltlichen Entscheidungen: Testumgebung, Teilenummern, Vergleich A/B/C

**Wie geprüft:** Jede Änderung wurde an Testkopien ausprobiert, bevor sie auf unsere Daten angewendet wurde. Die Ergebnisse (Boxen, Ausschnitte, Zählungen) haben wir stichprobenartig angesehen.
