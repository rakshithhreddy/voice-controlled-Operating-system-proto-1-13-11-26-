"""
Unit tests for Workspace Operations Manager.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

from src.workspace.manager import WorkspaceManager


@pytest.fixture
def ws():
    td = tempfile.mkdtemp()
    wm = WorkspaceManager(td)
    yield wm
    shutil.rmtree(td, ignore_errors=True)


def test_directory_creation_and_nesting(ws):
    res = ws.create_directory("Alpha/Beta/Gamma")
    assert res["success"] is True
    assert (ws.root / "Alpha" / "Beta" / "Gamma").is_dir()

    # Re-creating should succeed gracefully
    res2 = ws.create_directory("Alpha/Beta/Gamma")
    assert res2["success"] is True
    assert res2["created"] is False


def test_directory_deletion(ws):
    ws.create_directory("ToDelete")
    assert (ws.root / "ToDelete").exists()

    res = ws.delete_directory("ToDelete")
    assert res["success"] is True
    assert not (ws.root / "ToDelete").exists()


def test_directory_renaming(ws):
    ws.create_directory("OldDir")
    res = ws.rename_directory("OldDir", "NewDir")
    assert res["success"] is True
    assert not (ws.root / "OldDir").exists()
    assert (ws.root / "NewDir").is_dir()


def test_file_crud_and_content_verification(ws):
    # 1. Create
    res_create = ws.create_file("notes.txt", initial_content="First line\n")
    assert res_create["success"] is True
    assert (ws.root / "notes.txt").is_file()

    # 2. Read
    res_read = ws.read_file("notes.txt")
    assert res_read["success"] is True
    assert "First line" in res_read["content"]

    # 3. Append
    res_app = ws.append_file("notes.txt", "Second line\n")
    assert res_app["success"] is True
    assert ws.read_file("notes.txt")["lines"] == 2

    # 4. Overwrite
    res_write = ws.write_file("notes.txt", "Overwritten completely")
    assert res_write["success"] is True
    assert ws.read_file("notes.txt")["content"] == "Overwritten completely"

    # 5. Rename
    res_rename = ws.rename_file("notes.txt", "renamed_notes.txt")
    assert res_rename["success"] is True
    assert (ws.root / "renamed_notes.txt").exists()
    assert not (ws.root / "notes.txt").exists()

    # 6. Delete
    res_del = ws.delete_file("renamed_notes.txt")
    assert res_del["success"] is True
    assert not (ws.root / "renamed_notes.txt").exists()


def test_copy_and_move(ws):
    ws.create_directory("FolderA")
    ws.create_directory("FolderB")
    ws.create_file("FolderA/item.txt", "Sample Data")

    # Copy
    res_copy = ws.copy_item("FolderA/item.txt", "FolderB/item_copy.txt")
    assert res_copy["success"] is True
    assert (ws.root / "FolderB" / "item_copy.txt").exists()
    assert (ws.root / "FolderA" / "item.txt").exists()

    # Move
    res_move = ws.move_item("FolderA/item.txt", "FolderB/item_moved.txt")
    assert res_move["success"] is True
    assert (ws.root / "FolderB" / "item_moved.txt").exists()
    assert not (ws.root / "FolderA" / "item.txt").exists()


def test_search_and_find_by_extension(ws):
    ws.create_file("script1.py", "print(1)")
    ws.create_file("script2.py", "print(2)")
    ws.create_file("document.txt", "hello text")
    ws.create_directory("sub")
    ws.create_file("sub/script3.py", "print(3)")

    # Find py files
    res_py = ws.find_by_extension(".py")
    assert res_py["success"] is True
    assert res_py["count"] == 3

    # Search query
    res_search = ws.search_files("script")
    assert res_search["success"] is True
    assert res_search["count"] == 3


def test_search_text_in_files(ws):
    ws.create_file("a.txt", "Target keyword is here")
    ws.create_file("b.txt", "Nothing interesting")
    ws.create_file("c.txt", "Another target keyword line")

    res = ws.search_text_in_files("target keyword")
    assert res["success"] is True
    assert res["count"] == 2


def test_identify_duplicate_files(ws):
    content = "Identical content for duplicate check"
    ws.create_file("doc1.txt", content)
    ws.create_file("doc2.txt", content)
    ws.create_file("doc3.txt", "Unique content")

    res = ws.identify_duplicate_files()
    assert res["success"] is True
    assert res["group_count"] == 1


def test_organize_files(ws):
    ws.create_file("code.py", "print(1)")
    ws.create_file("doc.txt", "text")
    ws.create_file("notes.md", "# Notes")

    res = ws.organize_files(".")
    assert res["success"] is True
    assert (ws.root / "Python_Scripts" / "code.py").exists()
    assert (ws.root / "Text_Documents" / "doc.txt").exists()
    assert (ws.root / "Markdown_Docs" / "notes.md").exists()


def test_summarize_document(ws):
    doc_content = "Line one introduction.\nLine two details.\nLine three expansion.\nConclusion line."
    ws.create_file("report.txt", doc_content)

    res = ws.summarize_document("report.txt")
    assert res["success"] is True
    assert res["total_lines"] == 4
    assert len(res["summary_points"]) >= 3


def test_python_script_execution(ws):
    code = "import sys\nprint('Execution successful')\nsys.exit(0)\n"
    ws.create_file("runner.py", code)

    res = ws.execute_python_script("runner.py")
    assert res["success"] is True
    assert res["exit_code"] == 0
    assert "Execution successful" in res["stdout"]
