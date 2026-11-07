import csv
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

BOXES_FILE = "boxes.csv"
BOX_FIELDS = ["file", "x_min", "y_min", "x_max", "y_max", "status"]
WORK_SIZE = 400
EDGE_THRESHOLD = 15


@dataclass
class Box:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    status: str = "auto"

    def pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        return (
            round(self.x_min * width),
            round(self.y_min * height),
            round(self.x_max * width),
            round(self.y_max * height),
        )


def _components(mask: np.ndarray) -> list[np.ndarray]:
    seen = np.zeros_like(mask, dtype=bool)
    h, w = mask.shape
    result = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        queue, pts = deque([(y0, x0)]), []
        while queue:
            y, x = queue.popleft()
            pts.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        result.append(np.array(pts))
    return result


def suggest_box(path: Path) -> Box | None:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((WORK_SIZE, WORK_SIZE))
    rgb = np.asarray(img, dtype=np.float32)
    light = rgb.mean(axis=2)
    sat = rgb.max(axis=2) - rgb.min(axis=2)

    gray = Image.fromarray(light.astype(np.uint8))
    bg = np.asarray(gray.filter(ImageFilter.GaussianBlur(40)), dtype=np.float32)
    darker = (bg - light) / np.maximum(bg, 1)
    edges = np.asarray(gray.filter(ImageFilter.GaussianBlur(1.5)).filter(ImageFilter.FIND_EDGES), dtype=np.float32)

    mask = (sat > 30) | (darker > 0.5) | (edges > EDGE_THRESHOLD)
    m = 0.03
    h, w = mask.shape
    mask[: int(h * m)] = mask[-int(h * m) :] = False
    mask[:, : int(w * m)] = mask[:, -int(w * m) :] = False

    mask_img = Image.fromarray(mask.astype(np.uint8) * 255)
    mask_img = mask_img.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))
    mask = np.asarray(mask_img) > 0

    comps = [c for c in _components(mask) if len(c) >= 30]
    if not comps:
        return None
    main = max(comps, key=len)
    cy, cx = main.mean(axis=0)
    reach = 0.15 * max(h, w)
    keep = [c for c in comps if len(c) >= 0.05 * len(main) and np.hypot(*(c.mean(axis=0) - (cy, cx))) < reach]
    pts = np.concatenate(keep)
    y0, x0 = pts.min(axis=0)
    y1, x1 = pts.max(axis=0) + 1
    pad = 0.01
    return Box(
        max(0.0, x0 / w - pad),
        max(0.0, y0 / h - pad),
        min(1.0, x1 / w + pad),
        min(1.0, y1 / h + pad),
    )


def load_boxes(sorted_dir: Path) -> dict[str, Box]:
    path = sorted_dir / BOXES_FILE
    if not path.is_file():
        return {}
    with path.open(newline="") as f:
        return {
            r["file"]: Box(float(r["x_min"]), float(r["y_min"]), float(r["x_max"]), float(r["y_max"]), r["status"])
            for r in csv.DictReader(f)
        }


def save_boxes(sorted_dir: Path, boxes: dict[str, Box]) -> None:
    path = sorted_dir / BOXES_FILE
    tmp = path.with_name(path.name + ".part")
    with tmp.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BOX_FIELDS)
        writer.writeheader()
        for file in sorted(boxes):
            b = boxes[file]
            writer.writerow({
                "file": file,
                "x_min": f"{b.x_min:.5f}",
                "y_min": f"{b.y_min:.5f}",
                "x_max": f"{b.x_max:.5f}",
                "y_max": f"{b.y_max:.5f}",
                "status": b.status,
            })
    tmp.replace(path)
