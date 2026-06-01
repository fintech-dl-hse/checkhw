"""Диагностика мини-SWE-bench харнесса (без API_KEY, не скорится).

Проверяет САМ пайплайн (копируем -> чиним -> грейдим в чистой папке по эталонным
тестам), не завязываясь на эталонные решения задач:
  - на синтетической задаче: no-op агент -> не решено, «правильный» агент -> решено;
  - на реальных задачах: no-op агент даёт скор 0 (значит все задачи реально сломаны
    и грейдинг их ловит).

Реальный прогон агента на модели — в run_evaluation.py (нужен ключ).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))        # run_evaluation
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))    # корень репо (student)

import run_evaluation as rev  # noqa: E402


class _Noop:
    def __init__(self, workdir):
        self.workdir = workdir

    def run(self, task):
        return "noop"


class _PerfectSynthetic:
    """Чинит синтетическую задачу: пишет верную версию m.py (через open, без student-кода)."""

    def __init__(self, workdir):
        self.workdir = Path(workdir)

    def run(self, task):
        (self.workdir / "m.py").write_text("def f():\n    return 42\n", encoding="utf-8")
        return "fixed"


def _make_synthetic_task(tmp_path) -> Path:
    d = tmp_path / "syn"
    (d / "workspace").mkdir(parents=True)
    (d / "tests").mkdir(parents=True)
    (d / "workspace" / "m.py").write_text("def f():\n    return 0\n", encoding="utf-8")
    (d / "tests" / "test_m.py").write_text(
        "from m import f\n\ndef test_f():\n    assert f() == 42\n", encoding="utf-8"
    )
    (d / "task.json").write_text(json.dumps({"id": "syn", "files": ["m.py"]}),
                                 encoding="utf-8")
    return d


def test_pipeline_noop_fails(tmp_path):
    task = _make_synthetic_task(tmp_path)
    assert rev.run_one_task(task, lambda wd: _Noop(wd)) is False


def test_pipeline_perfect_solves(tmp_path):
    task = _make_synthetic_task(tmp_path)
    assert rev.run_one_task(task, lambda wd: _PerfectSynthetic(wd)) is True


def test_real_tasks_are_broken_noop_scores_zero():
    assert rev.evaluate_all(agent_factory=lambda wd: _Noop(wd)) == 0
