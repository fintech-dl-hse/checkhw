#!/usr/bin/env python3
"""
Add .github/workflows/opencode_review.yml to all homework template repos.
Uses GITHUB_TOKEN from environment. Run from checkhw repo root or set CHECKHW_ROOT.
"""
import base64
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

REPO_OWNER = "fintech-dl-hse"
REPO_PREFIX = "hw-"
WORKFLOW_PATH = ".github/workflows/opencode_review.yml"

WORKFLOW_CONTENT = """name: OpenCode Homework Review

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  opencode-review:
    if: |
      contains(github.event.comment.body, ' /review') ||
      startsWith(github.event.comment.body, '/review')
    runs-on: self-hosted-opencode
    permissions:
      id-token: write
      contents: read
      pull-requests: write
      issues: write
    steps:
      - name: OpenCode review
        uses: fintech-dl-hse/action-opencode-review@main
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
"""


def get_checkhw_root() -> Path:
    root = os.environ.get("CHECKHW_ROOT")
    if root:
        return Path(root).resolve()
    script_dir = Path(__file__).resolve().parent
    return script_dir.parent


def list_homework_names(checkhw_root: Path) -> list[str]:
    classroom = checkhw_root / ".github" / "classroom"
    if not classroom.is_dir():
        return []
    names = []
    for f in classroom.glob("autograding-*.json"):
        # autograding-mlp.json -> hw-mlp
        name = f.stem.removeprefix("autograding-")
        if name:
            names.append(name)
    return sorted(names)


def api_request(token: str, method: str, url: str, data: dict | None = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        body = None
    req = Request(url, data=body, method=method, headers=headers)
    with urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_file_sha(token: str, repo: str, path: str) -> str | None:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        out = api_request(token, "GET", url)
        return out.get("sha")
    except HTTPError as e:
        if e.code == 404:
            return None
        raise


def put_file(token: str, repo: str, path: str, content: str, sha: str | None) -> None:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": "Add or update OpenCode review workflow",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": "main",
    }
    if sha:
        payload["sha"] = sha
    api_request(token, "PUT", url, payload)


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is not set", file=sys.stderr)
        return 1

    checkhw_root = get_checkhw_root()
    names = list_homework_names(checkhw_root)
    if not names:
        print("No autograding-*.json found in .github/classroom", file=sys.stderr)
        return 1

    print("HW Names", "\n".join(names))
    if input("Continue? (y/n)") != "y":
        print("Aborting")
        return 1

    ok = 0
    err = 0
    for name in names:
        repo = f"{REPO_OWNER}/{REPO_PREFIX}{name}"
        try:
            sha = get_file_sha(token, repo, WORKFLOW_PATH)
            put_file(token, repo, WORKFLOW_PATH, WORKFLOW_CONTENT, sha)
            print(f"OK {repo}")
            ok += 1
        except HTTPError as e:
            print(f"FAIL {repo}: HTTP {e.code} {e.reason}", file=sys.stderr)
            if e.fp:
                try:
                    body = e.fp.read().decode()
                    print(body[:500], file=sys.stderr)
                    if e.code == 403 and "personal access token" in body.lower():
                        print(
                            "Hint: token needs 'repo' scope (or Contents R/W for fine-grained), "
                            "and org SSO authorization if enabled.",
                            file=sys.stderr,
                        )
                except Exception:
                    pass
            err += 1
        except URLError as e:
            print(f"FAIL {repo}: {e}", file=sys.stderr)
            err += 1

    print(f"\nDone: {ok} updated, {err} failed")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
