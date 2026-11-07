import csv
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
LABELS_FILE = "labels.csv"
LABEL_FIELDS = ["file", "part", "color", "brick_id", "view"]
VIEWS = ["oben", "seite", "unten", "andere"]
UNCLEAR = "_unklar"


@dataclass
class Move:

    src: Path
    dst: Path
    part: str
    color: str
    brick_id: str = ""
    view: str = ""


def list_unsorted(unsorted_dir: Path) -> list[Path]:
    if not unsorted_dir.is_dir():
        return []
    return sorted(p for p in unsorted_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


def list_parts(render_dir: Path) -> list[str]:
    if not render_dir.is_dir():
        return []
    return sorted(p.name for p in render_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def list_colors(render_dir: Path) -> list[str]:
    colors = set()
    for labels in render_dir.glob(f"*/{LABELS_FILE}"):
        with labels.open(newline="") as f:
            colors.update(row["color"] for row in csv.DictReader(f) if row.get("color"))
    return sorted(colors)


def used_colors(sorted_dir: Path) -> list[str]:
    labels = sorted_dir / LABELS_FILE
    if not labels.is_file():
        return []
    with labels.open(newline="") as f:
        return sorted({row["color"] for row in csv.DictReader(f) if row.get("color")})


def normalize_color(name: str) -> str:
    return re.sub(r"[\s-]+", "_", name.strip().lower())


def reference_image(render_dir: Path, part: str, size: int = 160) -> Image.Image | None:
    part_dir = render_dir / part
    labels = part_dir / LABELS_FILE
    if labels.is_file():
        with labels.open(newline="") as f:
            row = next(csv.DictReader(f), None)
        if row and (part_dir / row["file"]).is_file():
            img = Image.open(part_dir / row["file"]).convert("RGB")
            box = [float(row[k]) for k in ("x_min", "y_min", "x_max", "y_max")]
            margin = 0.15 * max(box[2] - box[0], box[3] - box[1])
            img = img.crop((
                max(0, box[0] - margin),
                max(0, box[1] - margin),
                min(img.width, box[2] + margin),
                min(img.height, box[3] + margin),
            ))
            return ImageOps.pad(img, (size, size), color="white")
    pngs = sorted(part_dir.glob("*.png"))
    if pngs:
        return ImageOps.pad(Image.open(pngs[0]).convert("RGB"), (size, size), color="white")
    return None


def photo_for_preview(sorted_dir: Path, part: str) -> Path | None:
    labels = sorted_dir / LABELS_FILE
    if labels.is_file():
        with labels.open(newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["part"] == part]
        rows.sort(key=lambda r: r.get("view") != "oben")
        for row in rows:
            if (sorted_dir / row["file"]).is_file():
                return sorted_dir / row["file"]
    photos = sorted(p for p in (sorted_dir / part).glob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
    return photos[0] if photos else None


def photo_thumbnail(path: Path, size: int = 160, crop: float = 0.5) -> Image.Image:
    img = load_photo(path, max_size=800)
    w, h = img.size
    cw, ch = w * crop, h * crop
    img = img.crop(((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2))
    return ImageOps.pad(img, (size, size), color="white")


def load_photo(path: Path, max_size: int = 800) -> Image.Image:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((max_size, max_size))
    return img


def default_views(n: int) -> list[str]:
    return {1: ["oben"], 2: ["oben", "unten"], 3: ["oben", "seite", "unten"]}.get(n, ["andere"] * n)


def _free_path(dst: Path) -> Path:
    candidate, i = dst, 1
    while candidate.exists():
        candidate = dst.with_name(f"{dst.stem}_{i}{dst.suffix}")
        i += 1
    return candidate


def assign(photo: Path, part: str, color: str, sorted_dir: Path, brick_id: str = "", view: str = "") -> Move:
    dst = _free_path(sorted_dir / part / photo.name)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(photo, dst)

    labels = sorted_dir / LABELS_FILE
    new_file = not labels.exists()
    with labels.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({
            "file": dst.relative_to(sorted_dir).as_posix(),
            "part": part,
            "color": color,
            "brick_id": brick_id,
            "view": view,
        })
    return Move(src=photo, dst=dst, part=part, color=color, brick_id=brick_id, view=view)


def assign_group(photos: list[Path], views: list[str], part: str, color: str, sorted_dir: Path) -> list[Move]:
    brick_id = photos[0].stem
    return [assign(p, part, color, sorted_dir, brick_id, v) for p, v in zip(photos, views)]


def undo(move: Move, sorted_dir: Path) -> None:
    shutil.move(move.dst, _free_path(move.src))

    labels = sorted_dir / LABELS_FILE
    if not labels.exists():
        return
    rel = move.dst.relative_to(sorted_dir).as_posix()
    with labels.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["file"] != rel]
    with labels.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS, restval="")
        writer.writeheader()
        writer.writerows(rows)


def count_sorted(sorted_dir: Path) -> dict[str, int]:
    if not sorted_dir.is_dir():
        return {}
    return {
        d.name: sum(1 for p in d.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
        for d in sorted(sorted_dir.iterdir())
        if d.is_dir()
    }
