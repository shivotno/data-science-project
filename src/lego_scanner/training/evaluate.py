"""Bewertet einen Trainingslauf eines Modells.

Gibt die Leistungsmaße für den A/B/C-Vergleich aus: Top-1 Accuracy,
Top-5 Accuracy und Macro-Recall. Die Konfusionsmatrix speichert
Ultralytics als Grafik im Ergebnisordner.

Für den Vergleich last.pt bewerten.

Ultralytics überspringt Testbilder von Teilen, die das Modell nicht kennt.
Deshalb wird die Zahl der bewerteten Testbilder mit ausgegeben. Sie muss
bei allen Modellen gleich sein, sonst sind die Ergebnisse nicht vergleichbar.

Start:
    uv run python -m lego_scanner.training.evaluate --modell a --gewichte pfad/zu/last.pt
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

from lego_scanner.paths import DATA_DIR
from lego_scanner.training.train import RUNS_DIR, SETTINGS


def evaluate(modell: str, data: Path, weights: Path):
    """Bewertet die Gewichte auf den Testbildern und gibt die Leistungsmaße aus."""
    model = YOLO(weights)
    metrics = model.val(
        data=str(data),
        split="test",
        imgsz=SETTINGS["imgsz"],
        batch=SETTINGS["batch"],
        project=str(RUNS_DIR),
        name=f"modell_{modell}_test",
        exist_ok=True,
    )

    matrix = metrics.confusion_matrix.matrix
    testbilder = int(matrix.sum())

    print(f"Gewichte:       {weights}")
    print(f"Testbilder:     {testbilder}")
    print(f"Top-1 Accuracy: {metrics.top1:.1%}")
    print(f"Top-5 Accuracy: {metrics.top5:.1%}")
    print(f"Macro-Recall:   {macro_recall(matrix):.1%}")


def macro_recall(matrix):
    """Berechnet den Macro-Recall aus einer Konfusionsmatrix.

    Die Matrix ist wie bei Ultralytics als [vorhergesagt, wahr] aufgebaut,
    die Spalten sind also die wahren Teile. Pro Teil wird der Recall
    (richtig erkannt / Testbilder des Teils) berechnet und dann gemittelt.
    Teile ohne Testbilder werden ausgelassen, sonst würde durch 0 geteilt.
    """
    testbilder_pro_teil = matrix.sum(axis=0)
    richtig_pro_teil = matrix.diagonal()
    im_test = testbilder_pro_teil > 0
    recall_pro_teil = richtig_pro_teil[im_test] / testbilder_pro_teil[im_test]
    return recall_pro_teil.mean()


def main():
    parser = argparse.ArgumentParser(description="Modell A, B oder C")
    parser.add_argument(
        "--modell", choices=["a", "b", "c"], required=True, help="Welches Modell?"
    )
    parser.add_argument(
        "--gewichte", required=True, type=Path, help="Pfad zur last.pt Datei"
    )
    args = parser.parse_args()

    data = DATA_DIR / "datasets" / f"modell_{args.modell}" / "classify"
    if not data.is_dir():
        raise SystemExit(f"{data} fehlt. Erst build_datasets ausführen.")

    if not args.gewichte.is_file():
        raise SystemExit(f"{args.gewichte} wurde nicht gefunden.")

    if args.gewichte.suffix != ".pt":
        raise SystemExit(f"{args.gewichte} ist keine .pt Datei.")

    evaluate(args.modell, data, args.gewichte)


if __name__ == "__main__":
    main()
