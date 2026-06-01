"""Диагностика мини-SWE-bench харнесса (без API_KEY, не скорится).

Проверяет, что пайплайн «копируем -> чиним -> прогоняем скрытые тесты -> скор»
корректен, и что студенческие FileLools.write_file реально правят файлы:
  - no-op агент   -> score 0   (скрытые тесты ловят баги),
  - perfect агент -> score 100 (скоринг и тесты корректны при починке).

Реальный агент на модели прогоняется отдельно в run_evaluation.py (нужен ключ).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))        # run_evaluation
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))    # корень репо (student)

import run_evaluation as rev  # noqa: E402
from tools import FileTools  # noqa: E402

CORRECT = {
    "calc.py": "def subtract(a, b):\n    return a - b\n",
    "numbers_util.py": "def is_even(n):\n    return n % 2 == 0\n",
    "strutil.py": "def reverse_string(s):\n    return s[::-1]\n",
    "mathx.py": "def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n",
    "fizz.py": ("def fizzbuzz(n):\n"
                "    if n % 15 == 0:\n        return 'FizzBuzz'\n"
                "    if n % 3 == 0:\n        return 'Fizz'\n"
                "    if n % 5 == 0:\n        return 'Buzz'\n"
                "    return str(n)\n"),
    "vowels.py": "def count_vowels(s):\n    return sum(1 for c in s.lower() if c in 'aeiou')\n",
}


class _Noop:
    def __init__(self, workdir):
        self.workdir = workdir

    def run(self, task):
        return "noop"


class _Perfect:
    def __init__(self, workdir):
        self.fs = FileTools(workdir)
        self.workdir = workdir

    def run(self, task):
        for fname, content in CORRECT.items():
            if os.path.exists(os.path.join(self.workdir, fname)):
                self.fs.write_file(fname, content)
        return "fixed"


def test_noop_agent_scores_zero():
    assert rev.evaluate_all(agent_factory=lambda wd: _Noop(wd)) == 0


def test_perfect_agent_scores_hundred():
    assert rev.evaluate_all(agent_factory=lambda wd: _Perfect(wd)) == 100
