import csv
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

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


def part_sort_key(part: str) -> tuple[int, str]:
    match = re.match(r"\d+", part)
    return (int(match.group()) if match else 10**9, part)


def normalize_color(name: str) -> str:
    return re.sub(r"[\s-]+", "_", name.strip().lower())


def load_preview_choices(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    with path.open(newline="") as f:
        return {r["part"]: r["render"] for r in csv.DictReader(f)}


def reference_image(render_dir: Path, part: str, size: int = 160, prefer: str | None = None) -> Image.Image | None:
    part_dir = render_dir / part
    labels = part_dir / LABELS_FILE
    if labels.is_file():
        with labels.open(newline="") as f:
            rows = [r for r in csv.DictReader(f) if (part_dir / r["file"]).is_file()]
        chosen = [r for r in rows if Path(r["file"]).stem == prefer]
        row = chosen[0] if chosen else max(rows, key=lambda r: float(r.get("cam_elevation") or 0), default=None)
        if row:
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


def load_labels(sorted_dir: Path) -> list[dict[str, str]]:
    labels = sorted_dir / LABELS_FILE
    if not labels.is_file():
        return []
    with labels.open(newline="") as f:
        return list(csv.DictReader(f))


def _is_black(row: dict[str, str]) -> bool:
    return row.get("color") in ("black", "", None)


def pick_photo(
    sorted_dir: Path,
    rows: list[dict[str, str]],
    part: str,
    view: str | None = None,
    colored_only: bool = False,
    brick_id: str = "",
) -> dict[str, str] | None:
    candidates = [
        r for r in rows
        if r["part"] == part
        and (view is None or r.get("view") == view)
        and not (colored_only and _is_black(r))
        and (sorted_dir / r["file"]).is_file()
    ]
    candidates.sort(key=lambda r: (bool(brick_id) and r.get("brick_id") != brick_id, _is_black(r), r.get("view") != "oben"))
    return candidates[0] if candidates else None


def stack_previews(top: Image.Image | None, side: Image.Image | None, size: int = 160) -> Image.Image:
    gap = 6
    canvas = Image.new("RGB", (size, 2 * size + gap), "white")
    for i, img in enumerate((top, side)):
        y = i * (size + gap)
        if img is not None:
            canvas.paste(ImageOps.pad(img, (size, size), color="white"), (0, y))
        else:
            draw = ImageDraw.Draw(canvas)
            draw.rectangle((0, y, size - 1, y + size - 1), fill=(245, 245, 245))
            draw.text((size / 2, y + size / 2), "keine Seitenansicht", fill=(150, 150, 150), anchor="mm")
    return canvas


def photo_thumbnail(
    path: Path, size: int = 160, crop: float = 0.5, box: tuple[float, float, float, float] | None = None
) -> Image.Image:
    img = load_photo(path, max_size=800)
    w, h = img.size
    if box:
        x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
        side = min(max(x1 - x0, y1 - y0) * 1.3, w, h)
        cx = min(max((x0 + x1) / 2, side / 2), w - side / 2)
        cy = min(max((y0 + y1) / 2, side / 2), h - side / 2)
        img = img.crop((cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2))
    else:
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
