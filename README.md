# data-science-project

Das Programm erkennt Lego-Steine auf Bildern oder live per Kamera, erstellt daraus ein Inventar und schlägt vor, was sich damit bauen lässt und aus welchen Sets die Steine stammen könnten.

## Projektidee

1. **Lego-Erkennung:** Das Programm erkennt, welcher Lego-Stein zu sehen ist, entweder live über die Kamera oder auf einem hochgeladenen Bild.
2. **Bestandsaufnahme:** Aus den erkannten Steinen entsteht ein Inventar. Dieses wird mit den bekannten Lego-Sets abgeglichen. Das Ergebnis sind mögliche Sets, aus denen die Steine stammen könnten.

## Technischer Ansatz

| Bereich | Umsetzung |
|---|---|
| Sprache | Python |
| Set- und Teiledaten | Frei verfügbare CSV-Dateien von [Rebrickable](https://rebrickable.com/downloads/), daraus eine eigene lokale Datenbank mit DuckDB. |
| Trainingsdaten | Synthetische Bilder, die mit Blender (`bpy`) aus 3D-Modellen gerendert werden, dazu echte Fotos |
| Training | PyTorch |
| Oberfläche | Streamlit |

Die 3D-Modelle selbst kommen nicht ins Repo. Wer rendert, hält sie lokal außerhalb des Projekts vor. Im Projekt landen nur die fertig gerenderten Bilder.

## Ablauf

```
Rebrickable-CSVs ──► DuckDB ───────────────────────────────┐
                                                           ▼
3D-Modelle ──► Blender-Rendering ─┐                   Set-Abgleich ──► Streamlit-App
                                  ├─► Aufbereitung ──► Training ──► Erkennung ──► Inventar ─┘
Echte Fotos ──────────────────────┘
```

## Ordnerstruktur

```
data-science-project/
├── src/
│   └── lego_scanner/            
│       ├── database/            # CSVs einlesen, DuckDB aufbauen, Abfragen
│       ├── rendering/           # Blender-/bpy-Skripte für synthetische Bilder
│       ├── preprocessing/       # Bilder aufbereiten, Augmentierung, Datensplits
│       ├── training/            # PyTorch-Datasets, Modell, Trainingsschleife
│       ├── inference/           # Erkennung aus Kamerabild oder Upload
│       ├── inventory/           # Erkannte Steine zu einem Inventar zusammenführen
│       └── matching/            # Gewichteter Set-Abgleich und Bauvorschläge
└── app/                         # Streamlit-Oberfläche
```

Die `.gitkeep`-Dateien sorgen nur dafür, dass die leeren Ordner im Repo erhalten bleiben.

## Daten und Modelle

Im Repo liegt nur Code. Daten und trainierte Modelle sind zu groß für Git und liegen deshalb in einem gemeinsamen Cloud-Speicher. Wer mit den Daten arbeitet, lädt sich den benötigten Teil aus der Cloud herunter. Neue Daten und Modelle werden wieder dort hochgeladen und nicht ins Repo committet.

## Zusammenarbeit

- Die Aufgaben planen wir im GitHub-Kanban-Board des Repos.