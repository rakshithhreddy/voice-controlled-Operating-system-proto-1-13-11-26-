"""
Centralized Workspace Management Engine (CAOP Voice OS 2.0).
Provides complete file and folder manipulation, intelligent multi-attribute
organization, duplicate detection, reversible deletions via TrashManager,
and an undo recovery stack strictly confined within 'workspace_data/'.
"""

import os
import shutil
import hashlib
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

from src.workspace.security import SecurityManager, SecurityException
from src.workspace.trash import TrashManager, UndoManager
from src.workspace.content_generator import ContentGenerator
from src.config import WORKSPACE_DIR, LOG_FILE, MAX_FILE_SIZE_READ_BYTES

logger = logging.getLogger("VoiceOS.Workspace")


class WorkspaceManager:
    """
    Central operational engine for all filesystem actions within 'workspace_data/'.
    Enforces sandboxing, performs physical state verification, and records actions for undo.
    """

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None):
        if workspace_root is None:
            workspace_root = WORKSPACE_DIR
        self.security = SecurityManager(workspace_root)
        self.root = self.security.get_workspace_root()

        # Initialize recovery & trash subsystems
        self.trash = TrashManager(self.root)
        self.undo_mgr = UndoManager(self.root, self.trash)

        # Virtual current working directory relative to root
        self._current_subpath: Path = Path(".")

    @property
    def current_directory(self) -> Path:
        return (self.root / self._current_subpath).resolve()

    def get_relative_cwd(self) -> str:
        rel = self.current_directory.relative_to(self.root)
        return "." if str(rel) == "." else str(rel)

    def change_directory(self, target_path: str) -> Dict[str, Any]:
        """Navigates active directory within workspace."""
        if target_path in ["..", "parent", "up"]:
            if self._current_subpath != Path("."):
                self._current_subpath = self._current_subpath.parent
                return {
                    "success": True,
                    "cwd": self.get_relative_cwd(),
                    "message": f"Navigated up to '{self.get_relative_cwd()}'."
                }
            return {"success": True, "cwd": ".", "message": "Already at workspace root."}

        target = self.resolve_path(target_path)
        if not target.exists() or not target.is_dir():
            return {"success": False, "error": f"Directory '{target_path}' does not exist.", "cwd": self.get_relative_cwd()}

        self._current_subpath = target.relative_to(self.root)
        return {"success": True, "cwd": self.get_relative_cwd(), "message": f"Navigated to '{self.get_relative_cwd()}'."}

    def resolve_path(self, user_path: Union[str, Path]) -> Path:
        """Resolves path relative to active directory and validates sandboxing."""
        path_str = str(user_path).strip()
        if not path_str or path_str == ".":
            return self.current_directory

        p = Path(path_str)
        if p.is_absolute():
            return self.security.validate_path(p)
        else:
            combined = (self.current_directory / p).resolve()
            return self.security.validate_path(combined)

    # -------------------------------------------------------------
    # FOLDER OPERATIONS
    # -------------------------------------------------------------

    def create_directory(self, dir_path: str) -> Dict[str, Any]:
        """Creates a directory or nested directory structure with verification and undo."""
        try:
            target = self.resolve_path(dir_path)
            if target.exists():
                return {
                    "success": True,
                    "path": str(target.relative_to(self.root)),
                    "created": False,
                    "message": f"Directory '{dir_path}' already exists."
                }

            target.mkdir(parents=True, exist_ok=True)

            if target.exists() and target.is_dir():
                rel_p = str(target.relative_to(self.root))
                self.undo_mgr.record_action("CREATE_FOLDER", {"path": rel_p})
                logger.info(f"Created directory: {target}")
                return {
                    "success": True,
                    "path": rel_p,
                    "created": True,
                    "message": f"Folder '{dir_path}' created successfully."
                }
            return {"success": False, "error": f"Filesystem verification failed for folder '{dir_path}'."}
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")
            return {"success": False, "error": str(e)}

    def delete_directory(self, dir_path: str, permanent: bool = False) -> Dict[str, Any]:
        """Deletes a directory with recoverable trash support."""
        try:
            target = self.resolve_path(dir_path)
            if not target.exists():
                return {"success": False, "error": f"Directory '{dir_path}' does not exist."}
            if not target.is_dir():
                return {"success": False, "error": f"'{dir_path}' is not a directory."}
            if target == self.root:
                return {"success": False, "error": "Cannot delete the workspace root directory."}
            if target == self.trash.trash_dir:
                return {"success": False, "error": "Cannot delete the internal .trash directory directly."}

            rel_p = str(target.relative_to(self.root))

            if permanent:
                shutil.rmtree(target)
                if not target.exists():
                    return {"success": True, "path": rel_p, "message": f"Folder '{dir_path}' permanently deleted."}
                return {"success": False, "error": "Permanent deletion failed."}
            else:
                trash_id = self.trash.move_to_trash(target)
                if trash_id:
                    self.undo_mgr.record_action("DELETE_ITEM", {"path": rel_p, "trash_id": trash_id})
                    return {
                        "success": True,
                        "path": rel_p,
                        "trash_id": trash_id,
                        "message": f"Folder '{dir_path}' moved to trash (recoverable via undo)."
                    }
                return {"success": False, "error": "Failed to move folder to trash."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_directory(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """Renames a directory with verification and undo."""
        try:
            old_target = self.resolve_path(old_name)
            if not old_target.exists() or not old_target.is_dir():
                return {"success": False, "error": f"Directory '{old_name}' does not exist."}

            new_target = self.resolve_path(new_name)
            if new_target.exists():
                return {"success": False, "error": f"Target directory '{new_name}' already exists."}

            old_rel = str(old_target.relative_to(self.root))
            new_rel = str(new_target.relative_to(self.root))

            old_target.rename(new_target)

            if new_target.exists() and new_target.is_dir() and not old_target.exists():
                self.undo_mgr.record_action("RENAME_ITEM", {"old_path": old_rel, "new_path": new_rel})
                return {
                    "success": True,
                    "old_path": old_rel,
                    "new_path": new_rel,
                    "message": f"Folder renamed from '{old_name}' to '{new_name}'."
                }
            return {"success": False, "error": "Verification failed after directory rename."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_directory(self, dir_path: str = ".", recursive: bool = False) -> Dict[str, Any]:
        """Lists directory contents with details (excludes .trash from normal view)."""
        try:
            target = self.resolve_path(dir_path)
            if not target.exists() or not target.is_dir():
                return {"success": False, "error": f"Directory '{dir_path}' does not exist."}

            items = []
            iterator = target.rglob("*") if recursive else target.iterdir()

            for item in sorted(iterator):
                if ".trash" in item.parts:
                    continue

                rel_p = str(item.relative_to(self.root))
                stat = item.stat() if item.exists() else None
                items.append({
                    "name": item.name,
                    "rel_path": rel_p,
                    "type": "folder" if item.is_dir() else "file",
                    "extension": item.suffix.lower() if item.is_file() else "",
                    "size_bytes": stat.st_size if (stat and item.is_file()) else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M") if stat else ""
                })

            return {
                "success": True,
                "path": str(target.relative_to(self.root)),
                "items": items,
                "count": len(items),
                "message": f"Found {len(items)} items in '{target.relative_to(self.root)}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_workspace_tree(self) -> Dict[str, Any]:
        """Builds a nested dictionary representation of the workspace tree for the UI."""
        def build_tree(path: Path) -> Dict[str, Any]:
            node = {
                "name": path.name if path != self.root else "workspace_data",
                "rel_path": str(path.relative_to(self.root)) if path != self.root else ".",
                "type": "folder",
                "children": []
            }
            try:
                for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    if item.name == ".trash":
                        continue
                    if item.is_dir():
                        node["children"].append(build_tree(item))
                    else:
                        stat = item.stat()
                        node["children"].append({
                            "name": item.name,
                            "rel_path": str(item.relative_to(self.root)),
                            "type": "file",
                            "size_bytes": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                        })
            except Exception:
                pass
            return node

        return {"success": True, "tree": build_tree(self.root)}

    # -------------------------------------------------------------
    # FILE OPERATIONS
    # -------------------------------------------------------------

    def create_file(self, file_path: str, initial_content: str = "", topic_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Creates a file with optional meaningful synthesized content and undo."""
        try:
            target = self.resolve_path(file_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            # If meaningful topic prompt is provided and content is empty, synthesize rich content!
            content_to_write = initial_content
            if not content_to_write and topic_prompt:
                content_to_write = ContentGenerator.generate_content(target.name, topic_prompt)

            # Validate Python syntax if applicable
            if target.suffix == ".py" and content_to_write:
                valid, err = ContentGenerator.validate_code_syntax(content_to_write, "python")
                if not valid:
                    logger.warning(f"Synthesized code syntax warning: {err}")

            target.write_text(content_to_write, encoding="utf-8")

            if target.exists() and target.is_file():
                rel_p = str(target.relative_to(self.root))
                self.undo_mgr.record_action("CREATE_FILE", {"path": rel_p})
                logger.info(f"Created file: {target} ({len(content_to_write)} chars)")
                return {
                    "success": True,
                    "path": rel_p,
                    "bytes_written": len(content_to_write.encode("utf-8")),
                    "message": f"File '{file_path}' created successfully."
                }
            return {"success": False, "error": f"Verification failed: '{file_path}' does not exist on disk."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_file(self, file_path: str, permanent: bool = False) -> Dict[str, Any]:
        """Deletes a file with recoverable trash support."""
        try:
            target = self.resolve_path(file_path)
            if not target.exists():
                return {"success": False, "error": f"File '{file_path}' does not exist."}
            if not target.is_file():
                return {"success": False, "error": f"'{file_path}' is not a regular file."}

            rel_p = str(target.relative_to(self.root))

            if permanent:
                target.unlink()
                if not target.exists():
                    return {"success": True, "path": rel_p, "message": f"File '{file_path}' permanently deleted."}
                return {"success": False, "error": "Permanent deletion failed."}
            else:
                trash_id = self.trash.move_to_trash(target)
                if trash_id:
                    self.undo_mgr.record_action("DELETE_ITEM", {"path": rel_p, "trash_id": trash_id})
                    return {
                        "success": True,
                        "path": rel_p,
                        "trash_id": trash_id,
                        "message": f"File '{file_path}' moved to trash (recoverable via undo)."
                    }
                return {"success": False, "error": "Failed to move file to trash."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_file(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """Renames a file with verification and undo."""
        try:
            old_target = self.resolve_path(old_name)
            if not old_target.exists() or not old_target.is_file():
                return {"success": False, "error": f"File '{old_name}' does not exist."}

            new_target = self.resolve_path(new_name)
            if new_target.exists():
                return {"success": False, "error": f"Target file '{new_name}' already exists."}

            old_rel = str(old_target.relative_to(self.root))
            new_rel = str(new_target.relative_to(self.root))

            old_target.rename(new_target)

            if new_target.exists() and not old_target.exists():
                self.undo_mgr.record_action("RENAME_ITEM", {"old_path": old_rel, "new_path": new_rel})
                return {
                    "success": True,
                    "old_path": old_rel,
                    "new_path": new_rel,
                    "message": f"File renamed from '{old_name}' to '{new_name}'."
                }
            return {"success": False, "error": "Verification failed after file rename."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_item(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Copies a file or folder with verification and undo."""
        try:
            src = self.resolve_path(source_path)
            dst = self.resolve_path(dest_path)

            if not src.exists():
                return {"success": False, "error": f"Source '{source_path}' does not exist."}

            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
                final_dst = dst
            else:
                if dst.is_dir():
                    final_dst = dst / src.name
                else:
                    final_dst = dst
                final_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, final_dst)

            if final_dst.exists():
                rel_dst = str(final_dst.relative_to(self.root))
                self.undo_mgr.record_action("COPY_ITEM", {"created_copy": rel_dst})
                return {
                    "success": True,
                    "source": str(src.relative_to(self.root)),
                    "destination": rel_dst,
                    "message": f"Copied '{source_path}' to '{dest_path}'."
                }
            return {"success": False, "error": "Copy verification failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_item(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Moves a file or folder with verification and undo."""
        try:
            src = self.resolve_path(source_path)
            dst = self.resolve_path(dest_path)

            if not src.exists():
                return {"success": False, "error": f"Source '{source_path}' does not exist."}

            if dst.is_dir() and not (dst / src.name).exists():
                final_dst = dst / src.name
            else:
                final_dst = dst

            final_dst.parent.mkdir(parents=True, exist_ok=True)
            old_rel = str(src.relative_to(self.root))
            new_rel = str(final_dst.relative_to(self.root))

            shutil.move(src, final_dst)

            if final_dst.exists() and not src.exists():
                self.undo_mgr.record_action("MOVE_ITEM", {"source": old_rel, "destination": new_rel})
                return {
                    "success": True,
                    "source": old_rel,
                    "destination": new_rel,
                    "message": f"Moved '{source_path}' to '{dest_path}'."
                }
            return {"success": False, "error": "Move verification failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, file_path: str) -> Dict[str, Any]:
        """Reads content from a text file."""
        try:
            target = self.resolve_path(file_path)
            if not target.exists():
                return {"success": False, "error": f"File '{file_path}' does not exist."}
            if not target.is_file():
                return {"success": False, "error": f"'{file_path}' is not a regular file."}

            size = target.stat().st_size
            if size > MAX_FILE_SIZE_READ_BYTES:
                return {"success": False, "error": f"File exceeds maximum read size limit ({size} bytes)."}

            content = target.read_text(encoding="utf-8", errors="replace")
            return {
                "success": True,
                "path": str(target.relative_to(self.root)),
                "content": content,
                "lines": len(content.splitlines()),
                "size_bytes": size,
                "message": f"Read {len(content.splitlines())} lines from '{file_path}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Overwrites content to a file with previous content backup for undo."""
        try:
            target = self.resolve_path(file_path)
            prev_content = target.read_text(encoding="utf-8") if target.exists() else None

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            read_back = target.read_text(encoding="utf-8")
            if read_back == content:
                rel_p = str(target.relative_to(self.root))
                self.undo_mgr.record_action("WRITE_FILE", {"path": rel_p, "previous_content": prev_content})
                return {
                    "success": True,
                    "path": rel_p,
                    "bytes_written": len(content.encode("utf-8")),
                    "message": f"Successfully wrote to '{file_path}'."
                }
            return {"success": False, "error": "File content verification failed after write."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def append_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Appends content to a file."""
        try:
            target = self.resolve_path(file_path)
            prev_content = target.read_text(encoding="utf-8") if target.exists() else ""

            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                f.write(content)

            new_content = target.read_text(encoding="utf-8")
            if len(new_content) >= len(prev_content):
                rel_p = str(target.relative_to(self.root))
                self.undo_mgr.record_action("WRITE_FILE", {"path": rel_p, "previous_content": prev_content})
                return {
                    "success": True,
                    "path": rel_p,
                    "message": f"Appended content to '{file_path}'."
                }
            return {"success": False, "error": "Append verification failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------
    # SEARCH & DISCOVERY
    # -------------------------------------------------------------

    def search_files(self, query: str, search_path: str = ".") -> Dict[str, Any]:
        """Searches filenames across workspace."""
        try:
            target = self.resolve_path(search_path)
            query_lower = query.lower()
            matches = []

            for p in target.rglob("*"):
                if ".trash" in p.parts:
                    continue
                if query_lower in p.name.lower():
                    matches.append({
                        "name": p.name,
                        "rel_path": str(p.relative_to(self.root)),
                        "type": "folder" if p.is_dir() else "file"
                    })

            return {
                "success": True,
                "query": query,
                "matches": matches,
                "count": len(matches),
                "message": f"Found {len(matches)} matches for '{query}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def find_by_extension(self, extension: str, search_path: str = ".") -> Dict[str, Any]:
        """Finds files by extension (e.g. '.py', 'txt')."""
        try:
            target = self.resolve_path(search_path)
            ext = extension.strip().lower()
            if not ext.startswith("."):
                ext = f".{ext}"

            matches = []
            for p in target.rglob(f"*{ext}"):
                if ".trash" in p.parts:
                    continue
                if p.is_file():
                    matches.append(str(p.relative_to(self.root)))

            return {
                "success": True,
                "extension": ext,
                "matches": matches,
                "count": len(matches),
                "message": f"Found {len(matches)} files ending with '{ext}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def search_text_in_files(self, pattern: str, search_path: str = ".") -> Dict[str, Any]:
        """Searches inside text files for matching string patterns."""
        try:
            target = self.resolve_path(search_path)
            results = []

            for p in target.rglob("*"):
                if ".trash" in p.parts:
                    continue
                if p.is_file() and p.stat().st_size <= MAX_FILE_SIZE_READ_BYTES:
                    try:
                        content = p.read_text(encoding="utf-8", errors="ignore")
                        for idx, line in enumerate(content.splitlines(), start=1):
                            if pattern.lower() in line.lower():
                                results.append({
                                    "file": str(p.relative_to(self.root)),
                                    "line": idx,
                                    "text": line.strip()
                                })
                    except Exception:
                        continue

            return {
                "success": True,
                "pattern": pattern,
                "results": results,
                "count": len(results),
                "message": f"Found {len(results)} occurrences of '{pattern}'."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def identify_duplicate_files(self, search_path: str = ".") -> Dict[str, Any]:
        """Finds duplicate files based on MD5 checksums."""
        try:
            target = self.resolve_path(search_path)
            hashes: Dict[str, List[str]] = {}

            for p in target.rglob("*"):
                if ".trash" in p.parts:
                    continue
                if p.is_file() and p.stat().st_size > 0:
                    try:
                        hasher = hashlib.md5()
                        with open(p, "rb") as f:
                            while chunk := f.read(8192):
                                hasher.update(chunk)
                        digest = hasher.hexdigest()
                        hashes.setdefault(digest, []).append(str(p.relative_to(self.root)))
                    except Exception:
                        continue

            duplicates = {k: v for k, v in hashes.items() if len(v) > 1}
            return {
                "success": True,
                "duplicate_groups": duplicates,
                "group_count": len(duplicates),
                "message": f"Found {len(duplicates)} sets of duplicate files."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def find_temporary_files(self, search_path: str = ".") -> Dict[str, Any]:
        """Identifies temporary or backup files."""
        try:
            target = self.resolve_path(search_path)
            temp_files = []

            for p in target.rglob("*"):
                if ".trash" in p.parts or not p.is_file():
                    continue
                name = p.name.lower()
                if (
                    name.endswith((".tmp", ".temp", ".bak", ".swp", ".swo", "~"))
                    or name.startswith("temp_")
                    or name.startswith("tmp_")
                ):
                    temp_files.append(str(p.relative_to(self.root)))

            return {
                "success": True,
                "temp_files": temp_files,
                "count": len(temp_files),
                "message": f"Found {len(temp_files)} temporary/backup files."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------
    # INTELLIGENT ORGANIZATION
    # -------------------------------------------------------------

    def organize_directory(self, target_folder: str = ".", criteria: str = "type") -> Dict[str, Any]:
        """
        Intelligently organizes files into subfolders based on file type,
        topic, or college domain metadata without destructive overwrites.
        """
        try:
            target = self.resolve_path(target_folder)
            category_map = {
                # Code
                ".py": "Python_Scripts",
                ".js": "JavaScript",
                ".html": "Web_Development",
                ".css": "Web_Development",
                ".cpp": "C_Plus_Plus",
                ".c": "C_Code",
                ".java": "Java_Source",
                # Documents
                ".txt": "Text_Documents",
                ".md": "Markdown_Docs",
                ".pdf": "PDF_Documents",
                ".docx": "Word_Documents",
                # Data
                ".json": "Data_JSON",
                ".csv": "Data_CSV",
                ".sql": "Database_SQL",
                # Media
                ".png": "Images",
                ".jpg": "Images",
                ".jpeg": "Images",
                ".mp4": "Videos",
                ".mp3": "Audio"
            }

            moved_records = []
            for item in list(target.iterdir()):
                if ".trash" in item.parts:
                    continue
                if item.is_file():
                    ext = item.suffix.lower()
                    subfolder_name = category_map.get(ext, "Other_Files")

                    dest_dir = target / subfolder_name
                    dest_dir.mkdir(exist_ok=True)

                    dest_file = dest_dir / item.name
                    # Avoid overwrite
                    if dest_file.exists():
                        dest_file = dest_dir / f"{item.stem}_{int(datetime.now().timestamp())}{item.suffix}"

                    src_rel = str(item.relative_to(self.root))
                    dst_rel = str(dest_file.relative_to(self.root))

                    shutil.move(item, dest_file)
                    self.undo_mgr.record_action("MOVE_ITEM", {"source": src_rel, "destination": dst_rel})
                    moved_records.append({"from": src_rel, "to": dst_rel})

            return {
                "success": True,
                "moved_count": len(moved_records),
                "moved_files": moved_records,
                "message": f"Organized {len(moved_records)} files into structured directories."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def organize_files(self, target_folder: str = ".", criteria: str = "type") -> Dict[str, Any]:
        """Backward-compatible alias for organize_directory."""
        return self.organize_directory(target_folder=target_folder, criteria=criteria)

    # -------------------------------------------------------------
    # UNDO RECOVERY ACTION
    # -------------------------------------------------------------

    def undo(self) -> Dict[str, Any]:
        """Rolls back the most recent reversible action."""
        return self.undo_mgr.undo_last()

    # -------------------------------------------------------------
    # DEVELOPMENT / SCRIPT RUNNER
    # -------------------------------------------------------------

    def execute_python_script(self, script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Safely executes a Python script in workspace."""
        try:
            target = self.resolve_path(script_path)
            if not target.exists() or not target.is_file():
                return {"success": False, "error": f"Script '{script_path}' does not exist."}

            if target.suffix != ".py":
                return {"success": False, "error": f"'{script_path}' is not a Python (.py) file."}

            import sys
            cmd = [sys.executable, str(target)]
            if args:
                cmd.extend(args)
            else:
                cmd.append("--test")

            self.security.validate_command_safety(cmd)

            proc = subprocess.run(
                cmd,
                cwd=str(target.parent),
                input="",
                capture_output=True,
                text=True,
                timeout=10
            )

            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "message": f"Script exited with code {proc.returncode}."
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timed out (15 second limit exceeded)."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def summarize_document(self, file_path: str) -> Dict[str, Any]:
        """Produces extractive summary and word stats."""
        read_res = self.read_file(file_path)
        if not read_res["success"]:
            return read_res

        content = read_res["content"]
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        words = content.split()

        key_points = lines[:3]
        if len(lines) > 3 and lines[-1] not in key_points:
            key_points.append(lines[-1])

        return {
            "success": True,
            "path": file_path,
            "total_lines": len(lines),
            "total_words": len(words),
            "summary_points": key_points,
            "message": f"Summary for '{file_path}': {len(words)} words, {len(lines)} lines."
        }

    def open_with_default_app(self, item_path: str) -> Dict[str, Any]:
        """Opens item with OS default handler."""
        try:
            target = self.resolve_path(item_path)
            if not target.exists():
                return {"success": False, "error": f"'{item_path}' does not exist."}
            os.startfile(str(target))
            return {"success": True, "path": str(target.relative_to(self.root)), "message": f"Opened '{item_path}'."}
        except Exception as e:
            return {"success": False, "error": str(e)}
