#!/usr/bin/env python3
"""
Compute max points for each homework from .github/classroom/autograding-*.json
and sync them into terraform/functions/grades/hw-meta.json.

Run from the checkhw repo root.
"""

import json
import os
from pathlib import Path


def repo_root():
    return Path(__file__).resolve().parent.parent


def points_from_autograding(path: Path) -> int:
    """Sum test points from a single autograding JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    tests = data.get("tests", [])
    return sum(t.get("points", 0) for t in tests)


def collect_autograding_points(classroom_dir: Path) -> dict[str, int]:
    """
    Collect max points per homework from autograding-<name>.json.
    Filename autograding-<name>.json maps to homework id hw-<name>.
    """
    result = {}
    for path in sorted(classroom_dir.glob("autograding-*.json")):
        name = path.stem.removeprefix("autograding-")
        hw_id = f"hw-{name}"
        result[hw_id] = points_from_autograding(path)
    return result


def sync_hw_meta_points() -> None:
    root = repo_root()
    classroom_dir = root / ".github" / "classroom"
    meta_path = root / "terraform" / "functions" / "grades" / "hw-meta.json"

    if not classroom_dir.is_dir():
        raise SystemExit(f"Classroom dir not found: {classroom_dir}")
    if not meta_path.is_file():
        raise SystemExit(f"hw-meta.json not found: {meta_path}")

    points_by_hw = collect_autograding_points(classroom_dir)

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    for hw_id, max_points in points_by_hw.items():
        if hw_id == 'hw-template':
            continue
        if hw_id not in meta:
            meta[hw_id] = {}
        meta[hw_id]["max_points"] = max_points

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Synced max_points from autograding files into hw-meta.json:")
    for hw_id in sorted(points_by_hw.keys()):
        print(f"  {hw_id}: {points_by_hw[hw_id]}")


if __name__ == "__main__":
    sync_hw_meta_points()
