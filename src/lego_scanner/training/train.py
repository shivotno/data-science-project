"""Trainiert den Klassifikator (Stufe 2) für Modell A, B oder C.

Alle drei Modelle nutzen dieselben Einstellungen (``SETTINGS``), damit sich
nur die Trainingsdaten unterscheiden und der Vergleich fair bleibt.

Für die Bewertung ``last.pt`` verwenden, nicht ``best.pt``.

Start:
    uv run python -m lego_scanner.training.train --modell a
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

from lego_scanner.paths import DATA_DIR, PROJECT_ROOT

BASE_MODEL = "yolo26s-cls.pt"
RUNS_DIR = PROJECT_ROOT / "runs" / "classify"

# Gemeinsame Einstellungen für A, B und C. Nur in Absprache mit der Gruppe ändern.
SETTINGS = {
    "imgsz": 224,
    "epochs": 30,
    "batch": 16,
    "seed": 42,
    "optimizer": "AdamW",
    "lr0": 0.0005,
}


def train(modell: str, data: Path):
    """Trainiert den Klassifikator und gibt den Pfad zu last.pt zurück."""
    model = YOLO(BASE_MODEL)
    model.train(
        data=str(data), project=str(RUNS_DIR), name=f"modell_{modell}", **SETTINGS
    )
    return Path(model.trainer.save_dir) / "weights" / "last.pt"


def main():
    parser = argparse.ArgumentParser(description="Modell A, B oder C trainieren.")
    parser.add_argument(
        "--modell", choices=["a", "b", "c"], required=True, help="welcher Datensatz (a, b oder c)"
    )
    args = parser.parse_args()
    data = DATA_DIR / "datasets" / f"modell_{args.modell}" / "classify"
    if not data.is_dir():
        raise SystemExit(f"{data} fehlt. Erst build_datasets ausführen.")

    weights = train(args.modell, data)
    print(f"\nFertig. Für die Bewertung verwenden: {weights}")


if __name__ == "__main__":
    main()
