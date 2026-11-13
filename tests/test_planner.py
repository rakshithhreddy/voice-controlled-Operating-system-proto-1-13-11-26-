"""
Unit tests for Task Planner and Task Executor.
"""

import tempfile
import shutil
import pytest
from pathlib import Path

from src.workspace.manager import WorkspaceManager
from src.nlp.parser import InstructionParser, ParsedInstruction
from src.nlp.intents import IntentType
from src.nlp.context import ContextManager
from src.planner.planner import TaskPlanner
from src.planner.executor import TaskExecutor
from src.planner.task import TaskItem, TaskStatus


@pytest.fixture
def execution_env():
    td = tempfile.mkdtemp()
    wm = WorkspaceManager(td)
    cm = ContextManager()
    yield wm, cm, Path(td)
    shutil.rmtree(td, ignore_errors=True)


def test_planner_creates_dependencies(execution_env):
    wm, cm, _ = execution_env
    parser = InstructionParser(cm)
    planner = TaskPlanner()

    cmd = "Create a folder called Master, and create a folder inside it called Worker"
    parsed = parser.parse(cmd)
    plan = planner.create_plan(cmd, parsed)

    assert plan.total_tasks() == 2
    task1, task2 = plan.tasks[0], plan.tasks[1]
    assert task1.target_path == "Master"
    assert task2.target_path == "Master/Worker"
    assert task1.task_id in task2.dependencies


def test_independent_verification_detects_creation(execution_env):
    wm, cm, td = execution_env
    planner = TaskPlanner()
    executor = TaskExecutor(wm, cm)

    task = TaskItem(
        task_id=1,
        intent=IntentType.CREATE_FOLDER,
        description="Create folder TestVerification",
        target_path="TestVerification"
    )

    from src.planner.planner import ExecutionPlan
    plan = ExecutionPlan("Create folder TestVerification", [task])
    result = executor.execute_plan(plan)

    assert result.overall_success is True
    assert task.verified is True
    assert (td / "TestVerification").is_dir()


def test_partial_failure_skips_dependent_tasks(execution_env):
    wm, cm, td = execution_env
    executor = TaskExecutor(wm, cm)

    # Task 1: Invalid folder (e.g., trying to write to an illegal destination)
    # We will simulate task 1 failing
    task1 = TaskItem(
        task_id=1,
        intent=IntentType.CREATE_FILE,
        description="Create file with invalid path outside workspace",
        target_path="../../illegal.txt"
    )

    # Task 2: Depends on Task 1
    task2 = TaskItem(
        task_id=2,
        intent=IntentType.APPEND_FILE,
        description="Append to illegal file",
        target_path="../../illegal.txt",
        dependencies=[1]
    )

    from src.planner.planner import ExecutionPlan
    plan = ExecutionPlan("Failure chain", [task1, task2])
    result = executor.execute_plan(plan)

    assert result.overall_success is False
    assert task1.status == TaskStatus.FAILED
    assert task2.status == TaskStatus.SKIPPED
    assert "Skipped because dependent task(s)" in task2.error_message
