# Lego-Scanner: Projektstand und Anleitung

**Daten (Sciebo):** https://fh-dortmund.sciebo.de/s/9ybakJH8NWNSzbo

## Offene Punkte

- [ ] `data/real/sorted/boxes.csv` auf Sciebo hochladen (ohne sie läuft `build_datasets` nicht)
- [ ] Eigenes Auswertungsskript (vergleicht nach Teilenamen, da train und test unterschiedliche Teile enthalten)
- [ ] Boxen für die 12 Gruppenfotos (`real_small/gruppen`) ziehen
- [ ] Skript für den Train/Test-Split ins Repo übernehmen (wurde einmalig außerhalb ausgeführt, Regeln siehe unten)

## Was wir bisher gemacht haben

1. **Modellwahl:** YOLO26 s, zweistufig: erst Steine finden (Detektor), dann Teil bestimmen (Klassifikator)
2. **Sortiert:** 136 Fotos von 53 Steinen, 18 Teile, mit dem Sortier-Tool. Zusätzlich 12 Gruppenfotos mit vielen Steinen.
3. **Farben angeglichen:** dark_gray → dark_bluish_gray, light_gray → light_bluish_gray, brown → reddish_brown (wie in den Renders).
4. **Train/Test-Split pro Stein** (`brick_id`): Alle Fotos eines Steins liegen immer im selben Teil. Pro Teil kommen ca. 30 % der Steine in den Test, mindestens einer. Teile mit nur einem Stein liegen nur in train. Zufall mit Seed 42. Ergebnis: 91 Fotos (35 Steine) train, 45 Fotos (18 Steine) test.
5. **Komprimiert:**
   - Renders: PNG → JPEG Qualität 90, 17 GB → 2,4 GB, Größe bleibt 512 px.
   - Fotos: auf 1600 px verkleinert, ca. 300 MB → 60 MB.
6. **Boxen:** Für jedes Foto wurde automatisch eine Box vorgeschlagen und dann von Hand geprüft oder korrigiert. Alle 136 sind geprüft.
7. **Datensätze für den Vergleich gebaut:**

   | Modell | Training | Test |
   |---|---|---|
   | A | nur echte Fotos (91) | 45 echte Testfotos |
   | B | nur Renders (50 000, 50 Teile) | dieselben 45 |
   | C | Renders + echte Fotos (54 Teile) | dieselben 45 |

   C ist das Modell mit allen Steinen.

## Ordner (`data/`, nicht in Git)

```
data/
├── renders_small/<teil>/        Renders als JPEG + labels.csv (Box, Farbe)
├── real/sorted/<teil>/          sortierte Originalfotos, labels.csv, boxes.csv
├── real/split/{train,test}/     Split der Originalfotos
├── real_small/                  dasselbe auf 1600 px (sorted, split, gruppen)
└── datasets/modell_{a,b,c}/
    ├── detect/                  Stufe 1: images/, labels/ (YOLO-Format), data.yaml
    └── classify/                Stufe 2: {train,test}/<teil>/ ausgeschnittene Steine (224 px)
```

## Anleitung

**Einrichten (einmalig):** [uv](https://docs.astral.sh/uv/) installieren, dann im Projektordner:

```bash
uv sync
```

Daten von Sciebo herunterladen und so ablegen wie oben unter `data/`.

**Sortier-Tool** (echte Fotos Teilen zuordnen, Boxen prüfen):

```bash
uv run streamlit run app/sortier_tool.py
```

Danach öffnet sich http://localhost:8501.

- **Seite „sortier tool“:** neue Fotos liegen in `data/real/unsorted`.
  1. Die Fotos desselben Steins anhaken.
  2. Optional eine Farbe wählen.
  3. Das Teil anklicken.
  - Neue Teile und Farben kann man über die aufklappbaren Felder anlegen. „Rückgängig“ legt den letzten Stein zurück.
  - Das Ergebnis landet in `data/real/sorted/<teil>/` und in `labels.csv`.
- **Seite „Boxen markieren“:** Die Box-Vorschläge seitenweise prüfen. Passt alles, „Alle passen“ klicken. Passt eine Box nicht, „Korrigieren“ klicken und mit der Maus ein Rechteck ziehen. Gespeichert wird in `data/real/sorted/boxes.csv`, relativ zur Bildgröße, also auch gültig für die verkleinerten Fotos.

**Komprimieren** (legt immer einen neuen Ordner an, die Originale bleiben):

```bash
uv run python -m lego_scanner.preprocessing.compress data/renders data/renders_small
uv run python -m lego_scanner.preprocessing.compress data/real/sorted data/real_small/sorted --max-size 1600
```

**Datensätze A/B/C bauen** (ca. 1 Minute):

```bash
uv run python -m lego_scanner.preprocessing.build_datasets
```

- Gleiche Bilder werden per Hardlink geteilt und belegen kaum zusätzlichen Platz.
- Den Ordner `data/datasets` nicht auf Sciebo hochladen. Jede Person baut ihn selbst, weil in `data.yaml` lokale Pfade stehen.
- `val` zeigt auf test, weil es keinen eigenen Validierungsdatensatz gibt. Einstellungen deshalb vorher festlegen und nicht auf den Testergebnissen optimieren.

**Code:**

| Datei | Inhalt |
|---|---|
| `src/lego_scanner/preprocessing/sorting.py` | Logik des Sortier-Tools: Fotos verschieben, `labels.csv`, Rückgängig |
| `src/lego_scanner/preprocessing/boxes.py` | Box-Vorschlag (Farbe, Helligkeit und Kanten gegenüber dem weißen Papier) und `boxes.csv` |
| `src/lego_scanner/preprocessing/compress.py` | Komprimieren |
| `src/lego_scanner/preprocessing/build_datasets.py` | Ordner für Modell A/B/C |
| `app/sortier_tool.py` | Oberfläche Sortieren |
| `app/pages/Boxen_markieren.py` | Oberfläche Boxen |

## Einsatz von KI

Wir haben **Claude** (Anthropic, Modell Opus 5.5) über Claude Code in der Claude-Desktop-App genutzt.

**Wofür:**
- **Beratung:** Modellwahl und Vergleich der YOLO-Varianten, Kompression, Aufbau des fairen A/B/C-Vergleichs (Split pro Stein, gemeinsamer Testdatensatz)
- **Code:** Sortier-Tool, Box-Seite mit automatischen Vorschlägen, Kompressions- und Datensatz-Skripte, Train/Test-Split, Angleichung der Farbnamen.
- **Prüfen:** Daten gezählt und abgeglichen (z. B. Teile in Fotos vs. Renders), Box-Vorschläge an allen Fotos angesehen, alles erst an Kopien getestet.

**Warum:** Damit wir die Werkzeuge rund um die Daten schnell bauen konnten und mehr Zeit für Datenerhebung und Auswertung bleibt.

**Was von uns kam:**
- alle Fotos, die Renders und alle Zuordnungen (Teil, Farbe, Ansicht)
- die Prüfung bzw. Korrektur aller Boxen
- die inhaltlichen Entscheidungen: Testumgebung, Teilenummern, Vergleich A/B/C

**Wie geprüft:** Jede Änderung wurde an Testkopien ausprobiert, bevor sie auf unsere Daten angewendet wurde. Die Ergebnisse (Boxen, Ausschnitte, Zählungen) haben wir stichprobenartig angesehen.
