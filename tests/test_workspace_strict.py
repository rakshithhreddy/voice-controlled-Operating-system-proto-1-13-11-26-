"""
CAOP Voice OS — Strict Workspace Integration Tests
===================================================
Tests run against REAL WorkspaceManager API using an isolated tmp_path fixture.
No NLP/parser pipeline — exercises WorkspaceManager methods directly.

Coverage:
  TC1  — Complex nested folder + file creation & content
  TC2  — Rename folder
  TC3  — Move file between folders
  TC4  — Move file back
  TC5  — List directory contents
  TC6  — Delete a file (recoverable)
  TC7  — Undo the deletion
  TC8  — Guard: create_file with empty path → no PermissionError
  TC9  — Guard: create_file with "." path → auto-assign new_file.txt
  TC10 — Guard: create_file on existing directory path → auto-assign
  TC11 — Guard: write_file with empty path → clean error
  TC12 — Guard: write_file on existing directory path → clean error
  TC13 — Guard: append_file with empty path → clean error
  TC14 — Path traversal blocked by SecurityManager
  TC15 — Copy file
  TC16 — Full nested structure verification after all operations
"""

import pytest
import ast
from pathlib import Path

from src.workspace.manager import WorkspaceManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ws(tmp_path):
    """Isolated WorkspaceManager rooted at a fresh tmp directory."""
    return WorkspaceManager(workspace_root=tmp_path)


@pytest.fixture()
def nested_ws(tmp_path):
    """
    WorkspaceManager pre-populated with:
      College/
        Semester Seven/
          AI/
          SNA/
          Projects/
    and two files:
      SNA/social_network_analysis.txt  (content about SNA)
      Projects/calculator.py           (working Python code)
    """
    mgr = WorkspaceManager(workspace_root=tmp_path)

    # Build folder hierarchy
    for folder in ["College/Semester Seven/AI",
                   "College/Semester Seven/SNA",
                   "College/Semester Seven/Projects"]:
        r = mgr.create_directory(folder)
        assert r["success"], f"Pre-setup failed creating '{folder}': {r}"

    # SNA notes file
    sna_content = (
        "Social Network Analysis (SNA)\n"
        "==============================\n"
        "SNA studies relationships and structures in social networks.\n"
        "Key concepts: nodes, edges, centrality, clustering coefficient.\n"
        "Applications: sociology, epidemiology, cybersecurity.\n"
    )
    r = mgr.create_file("College/Semester Seven/SNA/social_network_analysis.txt",
                        initial_content=sna_content)
    assert r["success"], f"Pre-setup failed creating SNA notes: {r}"

    # Python calculator
    calc_content = (
        'def add(a, b): return a + b\n'
        'def subtract(a, b): return a - b\n'
        'def multiply(a, b): return a * b\n'
        'def divide(a, b):\n'
        '    if b == 0:\n'
        '        raise ValueError("Division by zero")\n'
        '    return a / b\n'
        '\n'
        'if __name__ == "__main__":\n'
        '    import sys\n'
        '    if "--test" in sys.argv:\n'
        '        assert add(2, 3) == 5\n'
        '        assert subtract(10, 4) == 6\n'
        '        assert multiply(3, 4) == 12\n'
        '        assert divide(10, 2) == 5.0\n'
        '        print("All tests passed.")\n'
    )
    r = mgr.create_file("College/Semester Seven/Projects/calculator.py",
                        initial_content=calc_content)
    assert r["success"], f"Pre-setup failed creating calculator.py: {r}"

    return mgr, tmp_path


# ---------------------------------------------------------------------------
# TC1 — Complex nested creation & content verification
# ---------------------------------------------------------------------------

class TestTC1_NestedCreation:
    def test_folder_structure_exists(self, nested_ws):
        mgr, root = nested_ws
        assert (root / "College" / "Semester Seven" / "AI").is_dir()
        assert (root / "College" / "Semester Seven" / "SNA").is_dir()
        assert (root / "College" / "Semester Seven" / "Projects").is_dir()

    def test_sna_file_exists_and_has_content(self, nested_ws):
        mgr, root = nested_ws
        f = root / "College" / "Semester Seven" / "SNA" / "social_network_analysis.txt"
        assert f.is_file(), "SNA notes file missing"
        text = f.read_text(encoding="utf-8")
        assert "Social Network Analysis" in text
        assert "centrality" in text

    def test_calculator_py_exists_and_valid_python(self, nested_ws):
        mgr, root = nested_ws
        f = root / "College" / "Semester Seven" / "Projects" / "calculator.py"
        assert f.is_file(), "calculator.py missing"
        source = f.read_text(encoding="utf-8")
        # Must parse without SyntaxError
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"calculator.py has syntax error: {e}")

    def test_read_file_api(self, nested_ws):
        mgr, root = nested_ws
        r = mgr.read_file("College/Semester Seven/SNA/social_network_analysis.txt")
        assert r["success"]
        assert r["lines"] > 0
        assert "SNA" in r["content"]


# ---------------------------------------------------------------------------
# TC2 — Rename folder Projects → Development
# ---------------------------------------------------------------------------

class TestTC2_RenameFolder:
    def test_rename_directory(self, nested_ws):
        mgr, root = nested_ws
        r = mgr.rename_directory(
            "College/Semester Seven/Projects",
            "College/Semester Seven/Development"
        )
        assert r["success"], f"Rename failed: {r}"
        assert (root / "College" / "Semester Seven" / "Development").is_dir()
        assert not (root / "College" / "Semester Seven" / "Projects").exists()

    def test_calculator_exists_in_renamed_folder(self, nested_ws):
        mgr, root = nested_ws
        mgr.rename_directory(
            "College/Semester Seven/Projects",
            "College/Semester Seven/Development"
        )
        assert (root / "College" / "Semester Seven" / "Development" / "calculator.py").is_file()


# ---------------------------------------------------------------------------
# TC3 — Move calculator.py from Projects into AI
# ---------------------------------------------------------------------------

class TestTC3_MoveFile:
    def test_move_file_into_subfolder(self, nested_ws):
        mgr, root = nested_ws
        r = mgr.move_item(
            "College/Semester Seven/Projects/calculator.py",
            "College/Semester Seven/AI"
        )
        assert r["success"], f"Move failed: {r}"
        assert (root / "College" / "Semester Seven" / "AI" / "calculator.py").is_file()
        assert not (root / "College" / "Semester Seven" / "Projects" / "calculator.py").exists()


# ---------------------------------------------------------------------------
# TC4 — Move calculator.py back from AI into Projects
# ---------------------------------------------------------------------------

class TestTC4_MoveFileBack:
    def test_move_file_back(self, nested_ws):
        mgr, root = nested_ws
        # First move out
        mgr.move_item(
            "College/Semester Seven/Projects/calculator.py",
            "College/Semester Seven/AI"
        )
        # Then move back
        r = mgr.move_item(
            "College/Semester Seven/AI/calculator.py",
            "College/Semester Seven/Projects"
        )
        assert r["success"], f"Move back failed: {r}"
        assert (root / "College" / "Semester Seven" / "Projects" / "calculator.py").is_file()
        assert not (root / "College" / "Semester Seven" / "AI" / "calculator.py").exists()


# ---------------------------------------------------------------------------
# TC5 — List directory contents
# ---------------------------------------------------------------------------

class TestTC5_ListDirectory:
    def test_list_semester_seven(self, nested_ws):
        mgr, root = nested_ws
        r = mgr.list_directory("College/Semester Seven")
        assert r["success"], f"List failed: {r}"
        names = [item["name"] for item in r["items"]]
        assert "AI" in names
        assert "SNA" in names
        assert "Projects" in names

    def test_list_sna_contains_notes(self, nested_ws):
        mgr, root = nested_ws
        r = mgr.list_directory("College/Semester Seven/SNA")
        assert r["success"]
        names = [item["name"] for item in r["items"]]
        assert "social_network_analysis.txt" in names


# ---------------------------------------------------------------------------
# TC6 — Delete SNA notes file (recoverable)
# ---------------------------------------------------------------------------

class TestTC6_DeleteFile:
    def test_delete_sna_notes(self, nested_ws):
        mgr, root = nested_ws
        r = mgr.delete_file(
            "College/Semester Seven/SNA/social_network_analysis.txt"
        )
        assert r["success"], f"Delete failed: {r}"
        assert not (root / "College" / "Semester Seven" / "SNA" /
                    "social_network_analysis.txt").exists()

    def test_deleted_file_has_trash_id(self, nested_ws):
        mgr, root = nested_ws
        r = mgr.delete_file(
            "College/Semester Seven/SNA/social_network_analysis.txt"
        )
        assert r["success"]
        assert "trash_id" in r
        assert r["trash_id"]


# ---------------------------------------------------------------------------
# TC7 — Undo the deletion (restore the file)
# ---------------------------------------------------------------------------

class TestTC7_UndoDeletion:
    def test_undo_restores_deleted_file(self, nested_ws):
        mgr, root = nested_ws
        # Delete first
        del_r = mgr.delete_file(
            "College/Semester Seven/SNA/social_network_analysis.txt"
        )
        assert del_r["success"], f"Pre-condition delete failed: {del_r}"
        assert not (root / "College" / "Semester Seven" / "SNA" /
                    "social_network_analysis.txt").exists()

        # Undo
        undo_r = mgr.undo()
        assert undo_r["success"], f"Undo failed: {undo_r}"
        assert (root / "College" / "Semester Seven" / "SNA" /
                "social_network_analysis.txt").is_file()

    def test_undo_restored_file_has_content(self, nested_ws):
        mgr, root = nested_ws
        mgr.delete_file("College/Semester Seven/SNA/social_network_analysis.txt")
        mgr.undo()
        content = (root / "College" / "Semester Seven" / "SNA" /
                   "social_network_analysis.txt").read_text(encoding="utf-8")
        assert "Social Network Analysis" in content


# ---------------------------------------------------------------------------
# TC8–TC13 — Guard tests: no PermissionError on bad paths
# ---------------------------------------------------------------------------

class TestGuards_CreateFile:
    def test_empty_path_does_not_raise(self, ws):
        """Empty path should auto-assign new_file.txt or return clean error."""
        r = ws.create_file("")
        # Must never raise; either success with auto-name or clean error dict
        assert isinstance(r, dict)
        assert "success" in r
        # If success, a file must actually exist
        if r["success"]:
            created = ws.root / r["path"]
            assert created.is_file()

    def test_dot_path_does_not_raise(self, ws):
        """'.' path should auto-assign new_file.txt (not PermissionError)."""
        r = ws.create_file(".")
        assert isinstance(r, dict)
        assert "success" in r
        if r["success"]:
            created = ws.root / r["path"]
            assert created.is_file()

    def test_workspace_data_path_does_not_raise(self, ws):
        """'workspace_data' path should auto-assign or fail cleanly."""
        r = ws.create_file("workspace_data")
        assert isinstance(r, dict)
        assert "success" in r
        # Must NOT raise PermissionError

    def test_existing_directory_path_auto_assigns(self, ws):
        """create_file on a path that is an existing directory → auto-assign inside it."""
        ws.create_directory("my_folder")
        r = ws.create_file("my_folder")
        assert isinstance(r, dict)
        assert "success" in r
        if r["success"]:
            created = ws.root / r["path"]
            assert created.is_file()
            assert created.parent.name == "my_folder"


class TestGuards_WriteFile:
    def test_empty_path_returns_error_dict(self, ws):
        r = ws.write_file("", "some content")
        assert isinstance(r, dict)
        assert r["success"] is False
        assert "error" in r
        # Must NOT raise PermissionError
        assert "directory" in r["error"].lower() or "workspace" in r["error"].lower()

    def test_dot_path_returns_error_dict(self, ws):
        r = ws.write_file(".", "some content")
        assert isinstance(r, dict)
        # Dot resolves to workspace root (a directory) → must fail cleanly
        assert r["success"] is False

    def test_existing_directory_path_returns_error(self, ws):
        ws.create_directory("write_test_dir")
        r = ws.write_file("write_test_dir", "content")
        assert isinstance(r, dict)
        assert r["success"] is False
        assert "directory" in r["error"].lower() or "not a file" in r["error"].lower()


class TestGuards_AppendFile:
    def test_empty_path_returns_error_dict(self, ws):
        r = ws.append_file("", "extra content")
        assert isinstance(r, dict)
        assert r["success"] is False
        assert "error" in r

    def test_existing_directory_path_returns_error(self, ws):
        ws.create_directory("append_test_dir")
        r = ws.append_file("append_test_dir", "extra content")
        assert isinstance(r, dict)
        assert r["success"] is False
        assert "directory" in r["error"].lower() or "not a file" in r["error"].lower()


# ---------------------------------------------------------------------------
# TC14 — Path traversal blocked
# ---------------------------------------------------------------------------

class TestTC14_PathTraversal:
    def test_traversal_via_dotdot_blocked(self, ws):
        """Attempts to escape workspace via '../' must be blocked."""
        from src.workspace.security import SecurityException
        with pytest.raises((SecurityException, ValueError, Exception)):
            ws.resolve_path("../../etc/passwd")

    def test_absolute_outside_path_blocked(self, ws, tmp_path):
        """Absolute paths outside workspace root must be blocked."""
        from src.workspace.security import SecurityException
        import tempfile
        outside = Path(tempfile.gettempdir()) / "evil.txt"
        with pytest.raises((SecurityException, ValueError, Exception)):
            ws.resolve_path(str(outside))


# ---------------------------------------------------------------------------
# TC15 — Copy file
# ---------------------------------------------------------------------------

class TestTC15_CopyFile:
    def test_copy_file_to_sibling_folder(self, nested_ws):
        mgr, root = nested_ws
        r = mgr.copy_item(
            "College/Semester Seven/Projects/calculator.py",
            "College/Semester Seven/AI"
        )
        assert r["success"], f"Copy failed: {r}"
        # Original still exists
        assert (root / "College" / "Semester Seven" / "Projects" / "calculator.py").is_file()
        # Copy exists in AI
        assert (root / "College" / "Semester Seven" / "AI" / "calculator.py").is_file()


# ---------------------------------------------------------------------------
# TC16 — Full structure after rename + move + copy
# ---------------------------------------------------------------------------

class TestTC16_FullStructureVerification:
    def test_full_scenario(self, nested_ws):
        mgr, root = nested_ws

        # Step 1: Rename Projects → Development
        r = mgr.rename_directory(
            "College/Semester Seven/Projects",
            "College/Semester Seven/Development"
        )
        assert r["success"], f"Rename step failed: {r}"

        # Step 2: Move calculator.py from Development to AI
        r = mgr.move_item(
            "College/Semester Seven/Development/calculator.py",
            "College/Semester Seven/AI"
        )
        assert r["success"], f"Move to AI failed: {r}"

        # Step 3: Copy from AI back to Development
        r = mgr.copy_item(
            "College/Semester Seven/AI/calculator.py",
            "College/Semester Seven/Development"
        )
        assert r["success"], f"Copy back failed: {r}"

        # Step 4: Delete SNA notes file
        r = mgr.delete_file(
            "College/Semester Seven/SNA/social_network_analysis.txt"
        )
        assert r["success"], f"Delete failed: {r}"

        # Step 5: Undo the delete
        r = mgr.undo()
        assert r["success"], f"Undo failed: {r}"

        # Final assertions
        base = root / "College" / "Semester Seven"
        assert (base / "AI").is_dir()
        assert (base / "SNA").is_dir()
        assert (base / "Development").is_dir()
        assert not (base / "Projects").exists(), "Projects should be renamed to Development"

        assert (base / "AI" / "calculator.py").is_file()
        assert (base / "Development" / "calculator.py").is_file()
        assert (base / "SNA" / "social_network_analysis.txt").is_file(), \
            "File should be restored after undo"

        # Content integrity
        content = (base / "SNA" / "social_network_analysis.txt").read_text(encoding="utf-8")
        assert "Social Network Analysis" in content
