"""Мини-SWE-bench v2: прогон кодового агента студента по баг-фикс задачам.

Отличия от v1:
- Агенту НЕ даётся описание ошибки. Промт generic («почини, чтобы тесты прошли»),
  а тесты кладутся в песочницу — агент сам запускает их (тул run_tests),
  читает трейсбек и итеративно чинит исходники.
- Задачи бывают многофайловыми (нужно прочитать несколько файлов).
- Грейдинг устойчив к жульничеству: оценка идёт в ОТДЕЛЬНОЙ чистой папке, куда
  кладутся только декларированные исходники агента (task.json["files"]) и
  ЭТАЛОННЫЕ тесты. Если агент правил тесты или подкинул conftest.py — это
  игнорируется.

Для каждой задачи:
  1. workspace/ (сломанный код) -> песочница;
  2. tests/ -> та же песочница (чтобы агент мог их прогонять);
  3. агент работает: run_tests -> read_file -> edit_file -> ... до зелёных тестов;
  4. грейдинг: в чистую папку копируем правки агента (только "files") + эталонные
     tests/ и прогоняем pytest. Задача решена, если pytest вернул 0.

Скор = round(100 * solved / total). Пишется в файл (--out).

LLM из окружения (по умолчанию — Cloud.ru Foundation Models):
  LLM_BASE_URL (default https://foundation-models.api.cloud.ru/v1)
  LLM_MODEL    (default Qwen/Qwen3-Coder-Next)
  API_KEY      (обязателен для реального прогона)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

# Student-код (llm_client.py / agent.py) лежит в корне репозитория -> PYTHONPATH=.
from agent import CodeAgent  # noqa: E402
from llm_client import LLMClient  # noqa: E402

DEFAULT_BASE_URL = "https://foundation-models.api.cloud.ru/v1"
DEFAULT_MODEL = "Qwen/Qwen3-Coder-Next"
TASKS_DIR = Path(__file__).resolve().parent / "tasks"

# Generic-инструкция: одна на все задачи, без описания конкретного бага.
GENERIC_TASK = (
    "В рабочей директории — проект со сломанным кодом и тесты, которые сейчас "
    "падают. Найди причину сам (запусти тесты, почитай трейсбек и код) и почини "
    "исходники так, чтобы все тесты проходили. Тесты не редактируй."
)


def make_client_from_env() -> LLMClient:
    """Собрать LLMClient студента из переменных окружения."""
    api_key = os.environ.get("API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("Не задан API_KEY — нужен ключ Cloud.ru для прогона агента.")
    return LLMClient(
        base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
        model=os.environ.get("LLM_MODEL", DEFAULT_MODEL),
        temperature=0.0,
        max_tokens=1024,
    )


def _grade(task_dir: Path, agent_workdir: Path, files: list[str],
           task_timeout: int = 120) -> bool:
    """Оценить правки агента эталонными тестами в ЧИСТОЙ папке.

    Берём только декларированные исходники (агентовы версии) + pristine tests/,
    чтобы агент не мог сжульничать через conftest.py/правку тестов.
    """
    with tempfile.TemporaryDirectory(prefix="grade_") as clean:
        clean_dir = Path(clean)
        # только объявленные исходники — в их версии после работы агента
        for rel in files:
            src = agent_workdir / rel
            if not src.is_file():
                continue
            dst = clean_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        # эталонные тесты (агентовы версии игнорируются)
        shutil.copytree(task_dir / "tests", clean_dir, dirs_exist_ok=True)

        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env["PYTHONNOUSERSITE"] = "1"
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
                cwd=str(clean_dir),
                capture_output=True,
                text=True,
                timeout=task_timeout,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return False
        if proc.returncode != 0:
            print(proc.stdout[-600:])
        return proc.returncode == 0


def run_one_task(task_dir: Path, agent_factory: Callable[[str], object]) -> bool:
    """Прогнать одну задачу. Возвращает True, если эталонные тесты прошли."""
    task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix=f"swe_{task['id']}_") as tmp:
        workdir = Path(tmp)
        # 1. сломанный исходник + 2. тесты -> песочница (агент может их прогонять)
        shutil.copytree(task_dir / "workspace", workdir, dirs_exist_ok=True)
        shutil.copytree(task_dir / "tests", workdir, dirs_exist_ok=True)

        # 3. агент чинит (исключения агента не должны рушить весь прогон)
        try:
            agent = agent_factory(str(workdir))
            agent.run(GENERIC_TASK)
        except Exception as exc:  # noqa: BLE001
            print(f"[{task['id']}] агент упал: {exc}")

        # 4. грейдинг в чистой папке по эталонным тестам
        solved = _grade(task_dir, workdir, task["files"])
        print(f"[{task['id']}] {'SOLVED' if solved else 'FAILED'}")
        return solved


def evaluate_all(
    agent_factory: Callable[[str], object] | None = None,
    tasks_dir: Path = TASKS_DIR,
    out_path: str | None = None,
) -> int:
    """Прогнать все задачи, вернуть скор 0..100 и (опц.) записать его в файл.

    Если agent_factory не задан — собираем реального CodeAgent студента на одном
    общем LLMClient (чтобы посчитать суммарный расход токенов). Для тестов можно
    передать свою фабрику (тогда учёт токенов пропускается).
    """
    shared_client = None
    if agent_factory is None:
        shared_client = make_client_from_env()
        agent_factory = lambda wd: CodeAgent(shared_client, wd)  # noqa: E731

    task_dirs = sorted(p for p in tasks_dir.iterdir() if (p / "task.json").exists())
    solved = sum(run_one_task(p, agent_factory) for p in task_dirs)
    total = len(task_dirs)
    score = round(100 * solved / total) if total else 0
    print(f"\nИтог: solved {solved}/{total} -> score {score}")

    usage = getattr(shared_client, "total_usage", None)
    if usage and usage.get("total_tokens"):
        n_req = getattr(shared_client, "n_requests", 0)
        per_task = usage["total_tokens"] / total if total else 0
        print(
            "Расход токенов: "
            f"prompt={usage['prompt_tokens']}, "
            f"completion={usage['completion_tokens']}, "
            f"total={usage['total_tokens']} "
            f"({n_req} запросов к модели, ~{per_task:.0f} токенов/задача)"
        )

    if out_path:
        Path(out_path).write_text(str(score), encoding="utf-8")
    return score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="куда записать числовой скор")
    args = parser.parse_args()
    evaluate_all(out_path=args.out)


if __name__ == "__main__":
    main()
