#!/usr/bin/env python3
"""
Bump user_hash (version) for all homeworks-info-* yandex_function resources
in terraform/main.tf so that Terraform redeploys the grades function when
index.py or hw-meta.json changes.

Run from the checkhw repo root.
"""

import re
import sys
from pathlib import Path


def repo_root():
    return Path(__file__).resolve().parent.parent


def update_homeworks_info_versions(main_tf_path: Path) -> bool:
    """
    Find user_hash in homeworks-info-* resource blocks (v0.0.N), increment N,
    and write the new version to all three blocks.
    Returns True if main.tf was modified.
    """
    content = main_tf_path.read_text(encoding="utf-8")

    # Find first homeworks-info block and get current version
    block_match = re.search(
        r'resource\s+"yandex_function"\s+"homeworks-info-[^"]+"\s*\{.*?'
        r'user_hash\s*=\s*"v0\.0\.(\d+)"',
        content,
        re.DOTALL,
    )
    if not block_match:
        return False

    current = int(block_match.group(1))
    new_version = current + 1

    # Replace only the version number in user_hash lines that match v0.0.<current>
    # (all three homeworks-info blocks use the same version)
    pattern = re.compile(
        r'(user_hash\s*=\s*"v0\.0\.)' + str(current) + r'(")',
    )
    new_content, n = pattern.subn(r'\g<1>' + str(new_version) + r'\g<2>', content, count=3)
    if n == 0:
        return False

    main_tf_path.write_text(new_content, encoding="utf-8")
    print(f"Bumped homeworks-info-* user_hash from v0.0.{current} to v0.0.{new_version} ({n} resources)")
    return True


def main():
    root = repo_root()
    main_tf_path = root / "terraform" / "main.tf"
    if not main_tf_path.is_file():
        print(f"Not found: {main_tf_path}", file=sys.stderr)
        sys.exit(1)
    update_homeworks_info_versions(main_tf_path)


if __name__ == "__main__":
    main()
