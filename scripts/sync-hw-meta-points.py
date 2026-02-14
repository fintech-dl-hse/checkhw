#!/usr/bin/env python3
"""
Compute max points and feedback form URL for each homework from
.github/classroom/autograding-*.json and sync them into
terraform/functions/grades/hw-meta.json.

Run from the checkhw repo root.
"""

import json
import re
from pathlib import Path
from typing import Optional


def repo_root():
    return Path(__file__).resolve().parent.parent


# Match first https:// URL in a string (e.g. from feedback test run command)
FEEDBACK_URL_RE = re.compile(r"https://[^\s)\]\"]+")


def _feedback_url_from_tests(tests: list) -> Optional[str]:
    """Extract feedback form URL from the test with name 'feedback'."""
    for t in tests:
        if t.get("name") == "feedback":
            run = t.get("run", "")
            m = FEEDBACK_URL_RE.search(run)
            if m:
                return m.group(0).rstrip("'\"")
    return None


def collect_from_autograding(path: Path) -> tuple[int, Optional[str]]:
    """
    Read one autograding JSON; return (total_points, feedback_form_url or None).
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    tests = data.get("tests", [])
    points = sum(t.get("points", 0) for t in tests)
    feedback_url = _feedback_url_from_tests(tests)
    return points, feedback_url


def collect_autograding_data(classroom_dir: Path) -> tuple[dict[str, int], dict[str, str]]:
    """
    Collect max points and feedback_form_url per homework from autograding-<name>.json.
    Filename autograding-<name>.json maps to homework id hw-<name>.
    Returns (points_by_hw, feedback_url_by_hw).
    """
    points_by_hw = {}
    feedback_url_by_hw = {}
    for path in sorted(classroom_dir.glob("autograding-*.json")):
        name = path.stem.removeprefix("autograding-")
        hw_id = f"hw-{name}"
        points, feedback_url = collect_from_autograding(path)
        points_by_hw[hw_id] = points
        if feedback_url is not None:
            feedback_url_by_hw[hw_id] = feedback_url
    return points_by_hw, feedback_url_by_hw


def sync_hw_meta_points() -> None:
    root = repo_root()
    classroom_dir = root / ".github" / "classroom"
    meta_path = root / "terraform" / "functions" / "grades" / "hw-meta.json"

    if not classroom_dir.is_dir():
        raise SystemExit(f"Classroom dir not found: {classroom_dir}")
    if not meta_path.is_file():
        raise SystemExit(f"hw-meta.json not found: {meta_path}")

    points_by_hw, feedback_url_by_hw = collect_autograding_data(classroom_dir)

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    for hw_id, max_points in points_by_hw.items():
        if hw_id == "hw-template":
            continue
        if hw_id not in meta:
            meta[hw_id] = {}
        meta[hw_id]["max_points"] = max_points
        if hw_id in feedback_url_by_hw:
            meta[hw_id]["feedback_form_url"] = feedback_url_by_hw[hw_id]
        elif "feedback_form_url" in meta[hw_id]:
            # Remove if no longer present in autograding
            del meta[hw_id]["feedback_form_url"]

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Synced max_points and feedback_form_url from autograding files into hw-meta.json:")
    for hw_id in sorted(points_by_hw.keys()):
        if hw_id == "hw-template":
            continue
        line = f"  {hw_id}: {points_by_hw[hw_id]} pts"
        if hw_id in feedback_url_by_hw:
            line += f", feedback: {feedback_url_by_hw[hw_id]}"
        print(line)


if __name__ == "__main__":
    sync_hw_meta_points()
