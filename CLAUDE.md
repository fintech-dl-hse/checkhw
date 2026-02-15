# CLAUDE.md — checkhw

## Project Overview

Central autograding and infrastructure management system for the **"Deep Learning for FinTech"** course at HSE. Manages homework assignments via GitHub Classroom, automated testing/grading, grade aggregation, and self-hosted runner infrastructure on Yandex Cloud.

## Repository Structure

```
.github/classroom/          # Autograding JSON configs (one per homework)
.github/workflows/          # CI/CD: sync-hw-meta, terraform-apply, runner management
ansible/                    # Ansible playbooks for runner setup (CPU/GPU)
terraform/                  # Yandex Cloud IaC
  functions/grades/         # Grade aggregation (Python) + hw-meta.json
  functions/compute/        # Compute instance management (Go)
  functions/giga-review/    # AI code review via GigaChat (Python)
  functions/github_actions_hook/  # GitHub event logging (Python)
tests/                      # Pytest suites per homework (tests/<hw-name>/)
scripts/                    # Utility scripts (sync metadata, extract notebook code, etc.)
```

## Tech Stack

- **Python 3** — tests, serverless functions, utility scripts
- **Go 1.19** — compute management functions
- **Terraform** (Yandex provider) — infrastructure
- **Ansible** — runner provisioning
- **pytest** — test framework
- **PyTorch, NumPy, Pandas** — ML/DL libraries used in tests
- **YDB** — database for grades/events
- **GitHub Actions + GitHub Classroom** — CI/CD and autograding

## Key Commands

```bash
# Run homework tests locally
PYTHONPATH=. pytest -vs tests/<hw-name>/

# Sync hw-meta.json from autograding configs
python3 scripts/sync-hw-meta-points.py

# Bump Terraform function version after hw-meta changes
python3 scripts/update-homeworks-info-version.py

# Terraform (from terraform/ directory)
make zip-functions && terraform plan
make zip-functions && terraform apply

# Extract code from student notebook
python3 scripts/extract_class_from_notebook.py --notebook nb.ipynb --class_definition ClassName --out_filename out.py
```

## Naming Conventions

- Homework IDs: `hw-<name>` (e.g., `hw-mlp`, `hw-pytorch-basics`)
- Test directories: `tests/<name>/` (name without `hw-` prefix)
- Autograding configs: `.github/classroom/autograding-<name>.json`
- HW repos: `https://github.com/fintech-dl-hse/hw-<name>`
- Student repos: `fintech-dl-hse-hw-<name>-{github_nickname}`

## Test Patterns

- Tests import student code directly (e.g., `from mymlp import MyMLP`)
- Always run with `PYTHONPATH=.` so imports resolve from homework repo root
- Use `seed_everything()` for reproducible randomness
- Validate shapes, dtypes, gradient computation, and comparison with PyTorch reference implementations
- Timeouts: typically 5–30 seconds per test

## Autograding Config Format

Each `.github/classroom/autograding-<name>.json` contains a `tests` array with `name`, `run` (pytest command), `points`, and `timeout`. The `sync-hw-meta-points.py` script reads these to populate `hw-meta.json` with `max_points` and `feedback_form_url`.

## Homework Metadata

Centralized in `terraform/functions/grades/hw-meta.json`. Each entry has: `id`, `deadline`, `bonus`, `max_points`, `feedback_form_url`, `classroom_invite_link`. Deadlines have a 3h5m1s grace offset.

## Runner Tags

In workflow files, always use `self-hosted-cpu` or `self-hosted-gpu`. Never use bare `self-hosted`.

## Creating New Homeworks

See `.cursor/rules/homeworks-process-overview.mdc` for the full step-by-step process. Key points:
1. Create repo from template `fintech-dl-hse/hw-template`
2. One task per notebook cell (for extraction)
3. Math: `$ ... $` inline, `$$ ... $$` display (not `\( \)` or `\[ \]`)
4. Add autograding config, tests in `checkhw/tests/<name>/`, and metadata in `hw-meta.json`

## Git Workflow

- Push to `main` auto-triggers Terraform apply (if `terraform/` changed) and hw-meta sync (if `.github/classroom/` or grades function changed)
- The sync workflow auto-commits and pushes hw-meta.json + version bumps
