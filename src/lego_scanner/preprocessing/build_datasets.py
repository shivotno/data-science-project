import argparse
import csv
import os
import shutil
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from lego_scanner.preprocessing.boxes import load_boxes

LABEL_FIELDS = ["file", "part", "color", "source", "brick_id"]


@dataclass
class Sample:
    image: Path
    rel: str
    part: str
    color: str
    source: str
    brick_id: str
    box: tuple[float, float, float, float]


def link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def crop(src: Path, dst: Path, box: tuple[float, float, float, float], size: int) -> None:
    img = Image.open(src).convert("RGB")
    w, h = img.size
    x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
    side = min(max(x1 - x0, y1 - y0) * 1.2, w, h)
    cx = min(max((x0 + x1) / 2, side / 2), w - side / 2)
    cy = min(max((y0 + y1) / 2, side / 2), h - side / 2)
    img = img.crop((round(cx - side / 2), round(cy - side / 2), round(cx + side / 2), round(cy + side / 2)))
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.resize((size, size), Image.LANCZOS).save(dst, quality=90)


def _crop_job(args):
    crop(*args)


def load_renders(render_dir: Path) -> list[Sample]:
    samples = []
    for labels in sorted(render_dir.glob("*/labels.csv")):
        with labels.open(newline="") as f:
            for r in csv.DictReader(f):
                image = labels.parent / r["file"]
                if not image.is_file():
                    continue
                w, h = Image.open(image).size
                box = (float(r["x_min"]) / w, float(r["y_min"]) / h, float(r["x_max"]) / w, float(r["y_max"]) / h)
                samples.append(
                    Sample(image, f"{r['part']}/{Path(r['file']).name}", r["part"], r["color"], "render", "", box)
                )
    return samples


def load_real(split_dir: Path, boxes_csv_dir: Path) -> list[Sample]:
    boxes = load_boxes(boxes_csv_dir)
    samples = []
    with (split_dir / "labels.csv").open(newline="") as f:
        for r in csv.DictReader(f):
            b = boxes.get(r["file"])
            if b is None:
                raise SystemExit(f"Keine Box für {r['file']}. Erst im Tool 'Boxen markieren' prüfen.")
            samples.append(
                Sample(split_dir / r["file"], r["file"], r["part"], r["color"], "real", r["brick_id"],
                       (b.x_min, b.y_min, b.x_max, b.y_max))
            )
    return samples


def write_detect(root: Path, split: str, samples: list[Sample]) -> None:
    for s in samples:
        link(s.image, root / "images" / split / s.rel)
        x0, y0, x1, y1 = s.box
        label = root / "labels" / split / Path(s.rel).with_suffix(".txt")
        label.parent.mkdir(parents=True, exist_ok=True)
        label.write_text(f"0 {(x0 + x1) / 2:.6f} {(y0 + y1) / 2:.6f} {x1 - x0:.6f} {y1 - y0:.6f}\n")


def write_yaml(root: Path) -> None:
    (root / "data.yaml").write_text(
        f"# Stufe 1: Steine finden (eine Klasse)\n"
        f"path: {root.resolve()}\n"
        f"train: images/train\n"
        f"val: images/test  # kein eigener Validierungsdatensatz: nicht auf test optimieren\n"
        f"test: images/test\n"
        f"names:\n  0: lego\n"
    )


def write_classify_labels(split_dir: Path, samples: list[Sample]) -> None:
    split_dir.mkdir(parents=True, exist_ok=True)
    with (split_dir / "labels.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
        writer.writeheader()
        for s in samples:
            writer.writerow({"file": s.rel, "part": s.part, "color": s.color, "source": s.source, "brick_id": s.brick_id})


def build(render_dir: Path, real_split: Path, boxes_dir: Path, out: Path, crop_size: int) -> None:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} ist nicht leer. Bitte einen neuen Zielordner angeben oder den alten umbenennen.")

    renders = load_renders(render_dir)
    real_train = load_real(real_split / "train", boxes_dir)
    real_test = load_real(real_split / "test", boxes_dir)
    print(f"{len(renders)} Renders, {len(real_train)} echte Trainingsfotos, {len(real_test)} echte Testfotos")

    a, b, c = out / "modell_a", out / "modell_b", out / "modell_c"

    jobs = [(s.image, a / "classify/train" / s.rel, s.box, crop_size) for s in real_train]
    jobs += [(s.image, a / "classify/test" / s.rel, s.box, crop_size) for s in real_test]
    jobs += [(s.image, b / "classify/train" / s.rel, s.box, crop_size) for s in renders]
    print(f"Schneide {len(jobs)} Steine aus …")
    with ProcessPoolExecutor() as pool:
        for i, _ in enumerate(pool.map(_crop_job, jobs, chunksize=64), 1):
            if i % 5000 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)}", flush=True)
    for s in real_test:
        link(a / "classify/test" / s.rel, b / "classify/test" / s.rel)
        link(a / "classify/test" / s.rel, c / "classify/test" / s.rel)
    for s in renders:
        link(b / "classify/train" / s.rel, c / "classify/train" / s.rel)
    for s in real_train:
        link(a / "classify/train" / s.rel, c / "classify/train" / s.rel)

    print("Lege Detektor-Datensätze an …")
    plan = {a: (real_train, real_test), b: (renders, real_test), c: (renders + real_train, real_test)}
    for model, (train, test) in plan.items():
        write_detect(model / "detect", "train", train)
        write_detect(model / "detect", "test", test)
        write_yaml(model / "detect")
        write_classify_labels(model / "classify/train", train)
        write_classify_labels(model / "classify/test", test)

    rows = []
    for model, (train, test) in plan.items():
        for split, samples in (("train", train), ("test", test)):
            parts = Counter(s.part for s in samples)
            rows.append({"modell": model.name, "split": split, "teile": len(parts), "bilder": len(samples),
                         "renders": sum(s.source == "render" for s in samples),
                         "echte_fotos": sum(s.source == "real" for s in samples)})
    with (out / "uebersicht.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for r in rows:
        print(f"  {r['modell']} {r['split']:5}: {r['bilder']:6} Bilder, {r['teile']} Teile")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ordner für Modell A, B und C bauen (siehe docs/PROJEKT.md).")
    parser.add_argument("--renders", type=Path, default=Path("data/renders_small"), help="komprimierte Renders")
    parser.add_argument("--real", type=Path, default=Path("data/real_small/split"), help="echte Fotos, train/test")
    parser.add_argument("--boxes", type=Path, default=Path("data/real/sorted"), help="Ordner mit boxes.csv")
    parser.add_argument("--out", type=Path, default=Path("data/datasets"), help="Zielordner")
    parser.add_argument("--crop-size", type=int, default=224, help="Kantenlänge der Ausschnitte in Pixeln")
    args = parser.parse_args()
    build(args.renders, args.real, args.boxes, args.out, args.crop_size)


if __name__ == "__main__":
    main()
