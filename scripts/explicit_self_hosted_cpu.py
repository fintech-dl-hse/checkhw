#!/usr/bin/env python3
"""
Replace `runs-on: self-hosted` with `runs-on: self-hosted-cpu` in .github/workflows/classroom.yml
for all homework template repos. Uses GITHUB_TOKEN from environment. Run from checkhw repo root
or set CHECKHW_ROOT. Use --dry-run to print diffs for all repos that would change, without
updating any repo. Use --repos to limit to specific repos by full path owner/repo
(e.g. --repos fintech-dl-hse/hw-mlp fintech-dl-hse/fintech-dl-hse-2026-...-hw-weight-init).
"""
import argparse
import base64
import difflib
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

REPO_OWNER = "fintech-dl-hse"
REPO_PREFIX = "hw-"
WORKFLOW_PATH = ".github/workflows/classroom.yml"

# Only replace exact runner tag "self-hosted", not "self-hosted-gpu" etc.
RUNNER_REPLACE = re.compile(r"runs-on:\s*self-hosted(?!-)")
REPLACEMENT = "runs-on: self-hosted-cpu"


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


def get_default_branch(token: str, repo: str) -> str:
    url = f"https://api.github.com/repos/{repo}"
    out = api_request(token, "GET", url)
    return out.get("default_branch", "main")


def get_file_content_and_sha(token: str, repo: str, path: str) -> tuple[str, str] | None:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        out = api_request(token, "GET", url)
        raw = base64.b64decode(out["content"]).decode("utf-8")
        return raw, out["sha"]
    except HTTPError as e:
        if e.code == 404:
            return None
        raise


def put_file(
    token: str,
    repo: str,
    path: str,
    content: str,
    sha: str,
    message: str,
    branch: str,
) -> None:
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    payload = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    api_request(token, "PUT", url, payload)


def workflow_passed(token: str, repo: str, branch: str) -> bool:
    """True if the classroom workflow has a successful completed run on the given branch."""
    try:
        workflows_url = f"https://api.github.com/repos/{repo}/actions/workflows"
        out = api_request(token, "GET", workflows_url)
        workflows = out.get("workflows", [])
        workflow_id = None
        for w in workflows:
            if w.get("path") == WORKFLOW_PATH:
                workflow_id = w.get("id")
                break
        if workflow_id is None:
            return False
        runs_url = (
            f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/runs"
            f"?branch={branch}&per_page=1&status=completed"
        )
        runs_out = api_request(token, "GET", runs_url)
        runs = runs_out.get("workflow_runs", [])
        if not runs:
            return False
        return runs[0].get("conclusion") == "success"
    except (HTTPError, URLError, KeyError):
        print(f"FAIL {repo}: {e}", file=sys.stderr)
        return False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Replace runs-on: self-hosted with runs-on: self-hosted-cpu in classroom.yml for homework repos.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print diffs only, do not update any repo.",
    )
    p.add_argument(
        "--repos",
        nargs="*",
        default=None,
        metavar="OWNER/REPO",
        help="Full repo paths to process (e.g. fintech-dl-hse/hw-mlp owner/repo-name). If omitted, use all from .github/classroom.",
    )
    p.add_argument(
        "--skip-if-passed",
        action="store_true",
        help="Do not modify workflow file if the classroom workflow has a successful run on the default branch.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is not set", file=sys.stderr)
        return 1

    if args.repos is not None:
        repos = [x.strip() for x in args.repos if x.strip()]
        if not repos:
            print("No repos to process (empty --repos)", file=sys.stderr)
            return 1
        for r in repos:
            if "/" not in r:
                print(f"Invalid repo path (expected owner/repo): {r!r}", file=sys.stderr)
                return 1
    else:
        checkhw_root = get_checkhw_root()
        names = list_homework_names(checkhw_root)
        if not names:
            print("No autograding-*.json found in .github/classroom", file=sys.stderr)
            return 1
        repos = [f"{REPO_OWNER}/{REPO_PREFIX}{name}" for name in names]

    print("Repos", "\n".join(repos))
    if args.dry_run:
        print("Dry run: will print diffs only, no updates.\n")
    elif input("Continue? (y/n) ") != "y":
        print("Aborting")
        return 1

    ok = 0
    skip = 0
    err = 0
    for repo in repos:
        try:
            result = get_file_content_and_sha(token, repo, WORKFLOW_PATH)
            if result is None:
                print(f"SKIP {repo}: no {WORKFLOW_PATH}")
                skip += 1
                continue
            content, sha = result
            new_content = RUNNER_REPLACE.sub(REPLACEMENT, content)
            if new_content == content:
                print(f"SKIP {repo}: no 'runs-on: self-hosted' to replace")
                skip += 1
                continue
            branch = get_default_branch(token, repo)
            if args.skip_if_passed and workflow_passed(token, repo, branch):
                print(f"SKIP {repo}: pipelines passed")
                skip += 1
                continue
            if args.dry_run:
                old_lines = content.splitlines()
                new_lines = new_content.splitlines()
                diff = difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"{repo}/{WORKFLOW_PATH}",
                    tofile=f"{repo}/{WORKFLOW_PATH}",
                    lineterm="",
                )
                print(f"\n--- {repo} ---")
                for line in diff:
                    print(line)
                ok += 1
                continue
            put_file(
                token,
                repo,
                WORKFLOW_PATH,
                new_content,
                sha,
                "Use explicit self-hosted-cpu runner in classroom workflow",
                branch,
            )
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
                    if e.code == 404 and "update" in body.lower():
                        print(
                            "Hint: 404 on update often means no write access to the repo "
                            "or token lacks push permission.",
                            file=sys.stderr,
                        )
                except Exception:
                    pass
            err += 1
        except URLError as e:
            print(f"FAIL {repo}: {e}", file=sys.stderr)
            err += 1

    if args.dry_run:
        print(f"\nDone (dry run): {ok} would be updated, {skip} skipped, {err} failed")
    else:
        print(f"\nDone: {ok} updated, {skip} skipped, {err} failed")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
