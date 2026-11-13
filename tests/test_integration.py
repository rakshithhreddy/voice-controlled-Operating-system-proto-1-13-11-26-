"""
End-to-End Integration Tests for Voice-Controlled OS Assistant.
Validates multi-operation commands, hierarchical dependencies,
anaphora/context resolution, and filesystem verification.
"""

import tempfile
import shutil
import pytest
from pathlib import Path

from src.workspace.manager import WorkspaceManager
from src.nlp.context import ContextManager
from src.nlp.parser import InstructionParser
from src.planner.planner import TaskPlanner
from src.planner.executor import TaskExecutor


@pytest.fixture
def assistant_system():
    td = tempfile.mkdtemp()
    workspace = WorkspaceManager(td)
    context = ContextManager()
    parser = InstructionParser(context)
    planner = TaskPlanner()
    executor = TaskExecutor(workspace, context)

    yield {
        "workspace": workspace,
        "context": context,
        "parser": parser,
        "planner": planner,
        "executor": executor,
        "root": Path(td)
    }
    shutil.rmtree(td, ignore_errors=True)


def test_scenario_college_projects(assistant_system):
    """
    Scenario 1:
    'Create a folder called College Projects, create another folder inside it called Python, and create a Python file called calculator.py.'
    """
    cmd = "Create a folder called College Projects, create another folder inside it called Python, and create a Python file called calculator.py."
    sys = assistant_system

    parsed = sys["parser"].parse(cmd)
    plan = sys["planner"].create_plan(cmd, parsed)
    result = sys["executor"].execute_plan(plan)

    assert result.overall_success is True
    assert result.total == 3
    assert len(result.succeeded) == 3

    # Verification of disk state
    college_dir = sys["root"] / "College Projects"
    python_dir = college_dir / "Python"
    calc_file = python_dir / "calculator.py"

    assert college_dir.is_dir()
    assert python_dir.is_dir()
    assert calc_file.is_file()


def test_scenario_semester_seven_nested(assistant_system):
    """
    Scenario 2:
    'Create a folder named Semester 7, create three folders inside it called SNA, AI, and Projects, then create a README file inside the Projects folder.'
    """
    cmd = "Create a folder named Semester 7, create three folders inside it called SNA, AI, and Projects, then create a README file inside the Projects folder."
    sys = assistant_system

    parsed = sys["parser"].parse(cmd)
    plan = sys["planner"].create_plan(cmd, parsed)
    result = sys["executor"].execute_plan(plan)

    assert result.overall_success is True
    assert result.total == 5

    # Verification on disk
    sem7 = sys["root"] / "Semester 7"
    assert sem7.is_dir()
    assert (sem7 / "SNA").is_dir()
    assert (sem7 / "AI").is_dir()
    assert (sem7 / "Projects").is_dir()
    assert (sem7 / "Projects" / "README.md").is_file()


def test_conversational_followup_turn(assistant_system):
    """
    Scenario 3:
    Turn 1: 'Create a folder called Projects.'
    Turn 2: 'Inside it, create a folder called College.'
    """
    sys = assistant_system

    # Turn 1
    t1_cmd = "Create a folder called Projects."
    p1 = sys["parser"].parse(t1_cmd)
    res1 = sys["executor"].execute_plan(sys["planner"].create_plan(t1_cmd, p1))
    assert res1.overall_success is True
    assert (sys["root"] / "Projects").is_dir()

    # Turn 2
    t2_cmd = "Inside it, create a folder called College."
    p2 = sys["parser"].parse(t2_cmd)
    res2 = sys["executor"].execute_plan(sys["planner"].create_plan(t2_cmd, p2))
    assert res2.overall_success is True
    assert (sys["root"] / "Projects" / "College").is_dir()


def test_workspace_boundary_enforcement_end_to_end(assistant_system):
    """
    Attempts directory traversal in command to modify external directory.
    Must be blocked and reported as failed.
    """
    sys = assistant_system
    malicious_cmd = "Create a file called ../../../escaped.txt with content 'hack'"

    parsed = sys["parser"].parse(malicious_cmd)
    plan = sys["planner"].create_plan(malicious_cmd, parsed)
    result = sys["executor"].execute_plan(plan)

    assert result.overall_success is False
    assert len(result.failed) > 0
    assert not (sys["root"].parent / "escaped.txt").exists()


def test_caop_advanced_acceptance_scenario_12_turns(assistant_system):
    """
    Complete 12-turn CAOP 2.0 advanced acceptance scenario from specification:
    1. 'Create a folder called College.'
    2. 'Inside it create a folder called Semester Seven.'
    3. 'Inside Semester Seven create AI, SNA and Projects.'
    4. 'Create a text file in SNA explaining social network analysis.'
    5. 'Create a Python calculator inside Projects.'
    6. 'Write working code into it and verify that the calculator works.'
    7. 'Rename Projects to Development.'
    8. 'Move the calculator into AI.'
    9. 'Move it back to Development.'
    10. 'Show me everything inside Semester Seven.'
    11. 'Delete the SNA notes file.'
    12. 'Undo that.'
    """
    sys = assistant_system
    parser = sys["parser"]
    planner = sys["planner"]
    executor = sys["executor"]
    root = sys["root"]

    turns = [
        "Create a folder called College.",
        "Inside it create a folder called Semester Seven.",
        "Inside Semester Seven create AI, SNA and Projects.",
        "Create a text file in SNA explaining social network analysis.",
        "Create a Python calculator inside Projects.",
        "Write working code into it and verify that the calculator works.",
        "Rename Projects to Development.",
        "Move the calculator into AI.",
        "Move it back to Development.",
        "Show me everything inside Semester Seven.",
        "Delete the SNA notes file.",
        "Undo that."
    ]

    for turn in turns:
        parsed = parser.parse(turn)
        plan = planner.create_plan(turn, parsed)
        res = executor.execute_plan(plan)
        assert res.overall_success is True, f"Failed turn: {turn}"

    # Verify final disk state
    college = root / "College"
    assert college.is_dir()
    sem7 = college / "Semester Seven"
    assert sem7.is_dir()
    ai = sem7 / "AI"
    assert ai.is_dir()
    dev = sem7 / "Development"
    assert dev.is_dir()
    calc = dev / "calculator.py"
    assert calc.is_file()
    # SNA notes restored by undo
    sna_notes = sem7 / "SNA" / "notes.txt"
    assert sna_notes.is_file()
