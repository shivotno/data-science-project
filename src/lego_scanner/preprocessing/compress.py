import argparse
import csv
import os
import shutil
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
LABELS_FILE = "labels.csv"


def convert(src: Path, dst: Path, max_size: int | None, quality: int) -> None:
    if dst.exists():
        return
    img = Image.open(src)
    if max_size is not None:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_size, max_size))
    tmp = dst.with_name(dst.name + ".part")
    img.convert("RGB").save(tmp, format="JPEG", quality=quality, optimize=True)
    tmp.rename(dst)


def rewrite_labels(src: Path, dst: Path) -> None:
    with src.open(newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)
    if "file" in fields:
        for row in rows:
            name = Path(row["file"])
            if name.suffix.lower() in IMAGE_SUFFIXES:
                row["file"] = name.with_suffix(".jpg").as_posix()
    with dst.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def compress_tree(src_root: Path, dst_root: Path, max_size: int | None = None, quality: int = 90) -> int:
    src_root, dst_root = src_root.expanduser().resolve(), dst_root.expanduser()
    if dst_root.resolve() == src_root or src_root in dst_root.resolve().parents:
        raise SystemExit("Der Zielordner darf nicht im Quellordner liegen.")

    jobs, others = [], []
    for folder, dirs, files in os.walk(src_root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        rel = Path(folder).relative_to(src_root)
        for name in sorted(files):
            if name.startswith("."):
                continue
            src = Path(folder) / name
            if src.suffix.lower() in IMAGE_SUFFIXES:
                jobs.append((src, dst_root / rel / Path(name).with_suffix(".jpg")))
            else:
                others.append((src, dst_root / rel / name))

    targets = [dst for _, dst in jobs]
    if len(set(targets)) != len(targets):
        raise SystemExit("Zwei Bilder würden denselben Namen bekommen (z. B. a.png und a.jpg).")

    for _, dst in jobs + others:
        dst.parent.mkdir(parents=True, exist_ok=True)

    print(f"{len(jobs)} Bilder -> {dst_root}")
    with ProcessPoolExecutor() as pool:
        futures = [pool.submit(convert, s, d, max_size, quality) for s, d in jobs]
        for i, fut in enumerate(futures, 1):
            fut.result()
            if i % 1000 == 0 or i == len(futures):
                print(f"  {i}/{len(futures)}", flush=True)

    for src, dst in others:
        if src.name == LABELS_FILE:
            rewrite_labels(src, dst)
        else:
            shutil.copy2(src, dst)
    return len(jobs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bilder als JPEG in einen neuen Ordner kopieren (siehe docs/PROJEKT.md).")
    parser.add_argument("src", type=Path, help="Quellordner (bleibt unverändert)")
    parser.add_argument("dst", type=Path, help="neuer Zielordner")
    parser.add_argument("--max-size", type=int, default=None, help="längste Seite in Pixeln (Standard: Größe behalten)")
    parser.add_argument("--quality", type=int, default=90, help="JPEG-Qualität 1–100 (Standard: 90)")
    args = parser.parse_args()
    compress_tree(args.src, args.dst, args.max_size, args.quality)


if __name__ == "__main__":
    main()
