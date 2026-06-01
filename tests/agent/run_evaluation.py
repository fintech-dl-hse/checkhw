"""Мини-SWE-bench: прогон кодового агента студента по курируемым баг-фикс задачам.

Для каждой задачи:
  1. копируем workspace/ (сломанный код) во временную песочницу;
  2. создаём CodeAgent студента и даём ему текст issue (агент чинит код);
  3. докладываем в песочницу скрытые tests/ и прогоняем pytest;
  4. задача решена, если скрытые тесты прошли.

Скор = round(100 * solved / total). Пишется в файл (--out).

LLM берётся из окружения (по умолчанию — Cloud.ru Foundation Models):
  LLM_BASE_URL  (default https://foundation-models.api.cloud.ru/v1)
  LLM_MODEL     (default Qwen/Qwen3-Coder-Next)
  API_KEY       (обязателен для реального прогона)

Студент НЕ запускает этот скрипт для сдачи — он крутится в автограде checkhw.
Локально можно запустить при наличии API_KEY, чтобы прикинуть свой скор.
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


def run_one_task(
    task_dir: Path,
    agent_factory: Callable[[str], object],
    task_timeout: int = 120,
) -> bool:
    """Прогнать одну задачу. Возвращает True, если скрытые тесты прошли."""
    task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix=f"swe_{task['id']}_") as tmp:
        workdir = Path(tmp)
        # 1. сломанный код -> песочница
        shutil.copytree(task_dir / "workspace", workdir, dirs_exist_ok=True)

        # 2. агент чинит (исключения агента не должны рушить весь прогон)
        try:
            agent = agent_factory(str(workdir))
            agent.run(task["issue"])
        except Exception as exc:  # noqa: BLE001
            print(f"[{task['id']}] агент упал: {exc}")

        # 3. докладываем скрытые тесты
        shutil.copytree(task_dir / "tests", workdir, dirs_exist_ok=True)

        # 4. прогон скрытых тестов
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=task_timeout,
            )
        except subprocess.TimeoutExpired:
            print(f"[{task['id']}] таймаут тестов")
            return False
        solved = proc.returncode == 0
        print(f"[{task['id']}] {'SOLVED' if solved else 'FAILED'}")
        if not solved:
            print(proc.stdout[-600:])
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
        agent_factory = lambda wd: CodeAgent(shared_client, wd, max_steps=20)  # noqa: E731

    task_dirs = sorted(p for p in tasks_dir.iterdir() if (p / "task.json").exists())
    solved = sum(run_one_task(p, agent_factory) for p in task_dirs)
    total = len(task_dirs)
    score = round(100 * solved / total) if total else 0
    print(f"\nИтог: solved {solved}/{total} -> score {score}")

    # Сколько «стоил» агент (если клиент умеет считать usage).
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
