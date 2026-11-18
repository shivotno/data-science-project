import argparse
import csv
import os
import random
import shutil
from collections import defaultdict
from pathlib import Path

from lego_scanner.preprocessing.sorting import LABEL_FIELDS, LABELS_FILE, UNCLEAR, load_labels, part_sort_key

SPLITS = ("train", "test")


def previous_assignment(split_dir: Path) -> dict[tuple[str, str], str]:
    result = {}
    for split in SPLITS:
        for row in load_labels(split_dir / split):
            result[(row["part"], row["brick_id"])] = split
    return result


def assign(rows: list[dict[str, str]], previous: dict, test_share: float = 0.3, seed: int = 42) -> dict:
    bricks = defaultdict(set)
    for row in rows:
        if row["part"] != UNCLEAR:
            bricks[row["part"]].add(row["brick_id"])
    result = {}
    for part, ids in sorted(bricks.items()):
        ids = sorted(ids)
        known_test = [b for b in ids if previous.get((part, b)) == "test"]
        new = [b for b in ids if (part, b) not in previous]
        target = max(1, round(test_share * len(ids))) if len(ids) >= 2 else 0
        need = max(0, target - len(known_test))
        chosen = set(random.Random(f"{seed}-{part}").sample(new, min(need, len(new))))
        for b in ids:
            keep = previous.get((part, b))
            result[(part, b)] = keep or ("test" if b in chosen else "train")
    return result


def link(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def write_split(sorted_dir: Path, out_dir: Path, assignment: dict) -> dict[str, int]:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"{out_dir} ist nicht leer. Bitte vorher umbenennen.")
    rows = [r for r in load_labels(sorted_dir) if r["part"] != UNCLEAR]
    per_split = defaultdict(list)
    for row in rows:
        split = assignment[(row["part"], row["brick_id"])]
        link(sorted_dir / row["file"], out_dir / split / row["file"])
        per_split[split].append(row)
    for split in SPLITS:
        (out_dir / split).mkdir(parents=True, exist_ok=True)
        with (out_dir / split / LABELS_FILE).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LABEL_FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(per_split[split])
    return {split: len(per_split[split]) for split in SPLITS}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train/Test-Split pro Stein (siehe docs/PROJEKT.md).")
    parser.add_argument("--sorted", type=Path, nargs="+", default=[Path("data/real/sorted"), Path("data/real_small/sorted")])
    parser.add_argument("--out", type=Path, nargs="+", default=[Path("data/real/split"), Path("data/real_small/split")])
    parser.add_argument("--previous", type=Path, default=None, help="alter Split, dessen Zuordnung erhalten bleibt")
    parser.add_argument("--test-share", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    previous = previous_assignment(args.previous) if args.previous else {}
    assignment = assign(load_labels(args.sorted[0]), previous, args.test_share, args.seed)
    for sorted_dir, out_dir in zip(args.sorted, args.out):
        counts = write_split(sorted_dir, out_dir, assignment)
        print(f"{out_dir}: {counts['train']} train, {counts['test']} test")
    bricks = defaultdict(lambda: defaultdict(int))
    for (part, _), split in assignment.items():
        bricks[part][split] += 1
    for part, c in sorted(bricks.items(), key=lambda x: part_sort_key(x[0])):
        print(f"  {part:6} {c['train']:3} train  {c['test']:3} test Steine")


if __name__ == "__main__":
    main()
