import sys
import os
import asyncio
import pytest

# Ensure root stack path is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
stack_dir = os.path.dirname(backend_dir)
if stack_dir not in sys.path:
    sys.path.insert(0, stack_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from evals.e2e.runner import run_e2e_evaluation, run_single_e2e_task
from evals.e2e.dataset import get_default_e2e_tasks

def test_e2e_tasks_dataset_completeness():
    tasks = get_default_e2e_tasks()
    assert len(tasks) >= 8 and len(tasks) <= 12, f"Expected 8-12 E2E task cases, found {len(tasks)}"
    for task in tasks:
        assert task.id.startswith("E2E-")
        assert len(task.verification_criteria) > 0

def test_e2e_evaluation_harness_trajectory_run():
    report = asyncio.run(run_e2e_evaluation())
    assert report.total_tasks >= 8
    assert report.passed_tasks == report.total_tasks
    assert report.pass_rate == 1.0
    for res in report.results:
        assert res.passed is True
        assert res.score == 1.0
        assert len(res.failure_reasons) == 0
