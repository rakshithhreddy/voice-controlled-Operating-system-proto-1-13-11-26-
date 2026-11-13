"""
Workspace Manager Module.
Executes and verifies file, folder, text, search, and script operations
strictly within the safe workspace boundary.
"""

import os
import shutil
import hashlib
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

from src.workspace.security import SecurityManager, SecurityException
from src.config import WORKSPACE_DIR, LOG_FILE, MAX_FILE_SIZE_READ_BYTES

logger = logging.getLogger("VoiceOS.Workspace")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [Workspace] %(message)s"))
    logger.addHandler(fh)


class WorkspaceManager:
    """
    Manages all filesystem and developmental operations within the authorized workspace.
    Verifies actual filesystem state before reporting success.
    """

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None):
        self.security = SecurityManager(workspace_root)
        self.root = self.security.get_workspace_root()
        # Virtual current working directory relative to root
        self._current_subpath: Path = Path(".")

    @property
    def current_directory(self) -> Path:
        """Returns the full Path of the current active directory in the workspace."""
        return (self.root / self._current_subpath).resolve()

    def get_relative_cwd(self) -> str:
        """Returns string representation of current directory relative to workspace root."""
        rel = self.current_directory.relative_to(self.root)
        return "." if str(rel) == "." else str(rel)

    def change_directory(self, target_path: str) -> Dict[str, Any]:
        """Changes the active subfolder within the workspace."""
        if target_path in ["..", "parent", "up"]:
            if self._current_subpath != Path("."):
                self._current_subpath = self._current_subpath.parent
                return {
                    "success": True,
                    "cwd": self.get_relative_cwd(),
                    "message": f"Navigated up to '{self.get_relative_cwd()}'."
                }
            return {
                "success": True,
                "cwd": ".",
                "message": "Already at workspace root."
            }
        
        target = self.resolve_path(target_path)
        if not target.exists() or not target.is_dir():
            return {
                "success": False,
                "error": f"Directory '{target_path}' does not exist.",
                "cwd": self.get_relative_cwd()
            }
        
        self._current_subpath = target.relative_to(self.root)
        return {
            "success": True,
            "cwd": self.get_relative_cwd(),
            "message": f"Navigated to '{self.get_relative_cwd()}'."
        }

    def resolve_path(self, user_path: Union[str, Path]) -> Path:
        """Resolves path relative to current active directory and validates safety."""
        path_str = str(user_path).strip()
        if not path_str:
            return self.current_directory

        p = Path(path_str)
        if p.is_absolute():
            return self.security.validate_path(p)
        else:
            # Relative to current directory
            combined = (self.current_directory / p).resolve()
            return self.security.validate_path(combined)

    # -------------------------------------------------------------
    # FOLDER OPERATIONS
    # -------------------------------------------------------------

    def create_directory(self, dir_path: str) -> Dict[str, Any]:
        """Creates a directory or nested directory structure with verification."""
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

            # Independent verification
            if target.exists() and target.is_dir():
                logger.info(f"Created directory: {target}")
                return {
                    "success": True,
                    "path": str(target.relative_to(self.root)),
                    "created": True,
                    "message": f"Folder '{dir_path}' created successfully."
                }
            else:
                return {
                    "success": False,
                    "error": f"Filesystem verification failed for folder '{dir_path}'."
                }
        except SecurityException as se:
            return {"success": False, "error": str(se)}
        except Exception as e:
            logger.error(f"Error creating directory {dir_path}: {e}")
            return {"success": False, "error": str(e)}

    def delete_directory(self, dir_path: str, force: bool = False) -> Dict[str, Any]:
        """Deletes a directory with verification."""
        try:
            target = self.resolve_path(dir_path)
            if not target.exists():
                return {"success": False, "error": f"Directory '{dir_path}' does not exist."}
            if not target.is_dir():
                return {"success": False, "error": f"'{dir_path}' is not a directory."}
            if target == self.root:
                return {"success": False, "error": "Cannot delete the workspace root directory."}

            shutil.rmtree(target)

            # Verification
            if not target.exists():
                logger.info(f"Deleted directory: {target}")
                return {
                    "success": True,
                    "path": str(dir_path),
                    "message": f"Folder '{dir_path}' deleted successfully."
                }
            else:
                return {"success": False, "error": f"Failed to delete '{dir_path}'; folder still exists."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_directory(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """Renames a directory with verification."""
        try:
            old_target = self.resolve_path(old_name)
            if not old_target.exists() or not old_target.is_dir():
                return {"success": False, "error": f"Directory '{old_name}' does not exist."}

            new_target = self.resolve_path(new_name)
            if new_target.exists():
                return {"success": False, "error": f"Target '{new_name}' already exists."}

            old_target.rename(new_target)

            # Verification
            if new_target.exists() and new_target.is_dir() and not old_target.exists():
                return {
                    "success": True,
                    "old_path": str(old_target.relative_to(self.root)),
                    "new_path": str(new_target.relative_to(self.root)),
                    "message": f"Folder renamed from '{old_name}' to '{new_name}'."
                }
            return {"success": False, "error": "Verification failed after directory rename."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_directory(self, dir_path: str = ".") -> Dict[str, Any]:
        """Lists directory contents with categorization."""
        try:
            target = self.resolve_path(dir_path)
            if not target.exists() or not target.is_dir():
                return {"success": False, "error": f"Directory '{dir_path}' does not exist."}

            items = []
            for item in sorted(target.iterdir()):
                items.append({
                    "name": item.name,
                    "type": "folder" if item.is_dir() else "file",
                    "size_bytes": item.stat().st_size if item.is_file() else 0
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

    # -------------------------------------------------------------
    # FILE OPERATIONS
    # -------------------------------------------------------------

    def create_file(self, file_path: str, initial_content: str = "") -> Dict[str, Any]:
        """Creates a file with optional initial content and verification."""
        try:
            target = self.resolve_path(file_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            target.write_text(initial_content, encoding="utf-8")

            # Verification
            if target.exists() and target.is_file():
                logger.info(f"Created file: {target}")
                return {
                    "success": True,
                    "path": str(target.relative_to(self.root)),
                    "message": f"File '{file_path}' created successfully."
                }
            return {"success": False, "error": f"Verification failed: '{file_path}' does not exist."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_file(self, file_path: str) -> Dict[str, Any]:
        """Deletes a file with verification."""
        try:
            target = self.resolve_path(file_path)
            if not target.exists():
                return {"success": False, "error": f"File '{file_path}' does not exist."}
            if not target.is_file():
                return {"success": False, "error": f"'{file_path}' is not a file."}

            target.unlink()

            if not target.exists():
                return {
                    "success": True,
                    "path": str(file_path),
                    "message": f"File '{file_path}' deleted successfully."
                }
            return {"success": False, "error": f"File '{file_path}' could not be deleted."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_file(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """Renames a file with verification."""
        try:
            old_target = self.resolve_path(old_name)
            if not old_target.exists() or not old_target.is_file():
                return {"success": False, "error": f"File '{old_name}' does not exist."}

            new_target = self.resolve_path(new_name)
            if new_target.exists():
                return {"success": False, "error": f"Destination file '{new_name}' already exists."}

            old_target.rename(new_target)

            if new_target.exists() and not old_target.exists():
                return {
                    "success": True,
                    "old_path": str(old_target.relative_to(self.root)),
                    "new_path": str(new_target.relative_to(self.root)),
                    "message": f"File renamed from '{old_name}' to '{new_name}'."
                }
            return {"success": False, "error": "Verification failed after file rename."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_item(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Copies a file or directory to a destination."""
        try:
            src = self.resolve_path(source_path)
            dst = self.resolve_path(dest_path)

            if not src.exists():
                return {"success": False, "error": f"Source '{source_path}' does not exist."}

            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                if dst.is_dir():
                    dst = dst / src.name
                shutil.copy2(src, dst)

            if dst.exists():
                return {
                    "success": True,
                    "source": str(src.relative_to(self.root)),
                    "destination": str(dst.relative_to(self.root)),
                    "message": f"Copied '{source_path}' to '{dest_path}'."
                }
            return {"success": False, "error": "Copy verification failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_item(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """Moves a file or directory to a new location."""
        try:
            src = self.resolve_path(source_path)
            dst = self.resolve_path(dest_path)

            if not src.exists():
                return {"success": False, "error": f"Source '{source_path}' does not exist."}

            if dst.is_dir() and not (dst / src.name).exists():
                final_dst = dst / src.name
            else:
                final_dst = dst

            shutil.move(src, final_dst)

            if final_dst.exists() and not src.exists():
                return {
                    "success": True,
                    "source": str(source_path),
                    "destination": str(final_dst.relative_to(self.root)),
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
        """Overwrites content to a file."""
        try:
            target = self.resolve_path(file_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            # Verification
            read_back = target.read_text(encoding="utf-8")
            if read_back == content:
                return {
                    "success": True,
                    "path": str(target.relative_to(self.root)),
                    "bytes_written": len(content.encode("utf-8")),
                    "message": f"Successfully wrote to '{file_path}'."
                }
            return {"success": False, "error": "File content verification failed after write."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def append_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Appends content to an existing or new file."""
        try:
            target = self.resolve_path(file_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            
            initial_size = target.stat().st_size if target.exists() else 0
            with open(target, "a", encoding="utf-8") as f:
                f.write(content)

            new_size = target.stat().st_size
            if new_size >= initial_size:
                return {
                    "success": True,
                    "path": str(target.relative_to(self.root)),
                    "message": f"Appended content to '{file_path}'."
                }
            return {"success": False, "error": "Append verification failed."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------
    # SEARCH & DISCOVERY
    # -------------------------------------------------------------

    def search_files(self, query: str, search_path: str = ".") -> Dict[str, Any]:
        """Searches for files and directories matching a query pattern."""
        try:
            target = self.resolve_path(search_path)
            query_lower = query.lower()
            matches = []

            for p in target.rglob("*"):
                if query_lower in p.name.lower():
                    matches.append({
                        "path": str(p.relative_to(self.root)),
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
        """Finds all files with a given extension (e.g. '.py', 'txt')."""
        try:
            target = self.resolve_path(search_path)
            ext = extension.strip()
            if not ext.startswith("."):
                ext = f".{ext}"

            matches = []
            for p in target.rglob(f"*{ext}"):
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
        """Searches for text content inside text files (like grep)."""
        try:
            target = self.resolve_path(search_path)
            results = []

            for p in target.rglob("*"):
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
        """Identifies duplicate files based on MD5 checksums."""
        try:
            target = self.resolve_path(search_path)
            hashes: Dict[str, List[str]] = {}

            for p in target.rglob("*"):
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

    def organize_files(self, target_folder: str = ".") -> Dict[str, Any]:
        """
        Organizes files in the target directory into subfolders by their file extensions
        (e.g., .py -> 'Python', .txt -> 'Text_Documents', .png/.jpg -> 'Images').
        """
        try:
            target = self.resolve_path(target_folder)
            category_map = {
                ".py": "Python_Scripts",
                ".txt": "Text_Documents",
                ".md": "Markdown_Docs",
                ".json": "Data_JSON",
                ".csv": "Data_CSV",
                ".html": "Web_HTML",
                ".css": "Web_CSS",
                ".js": "JavaScript",
                ".log": "Logs"
            }

            moved_count = 0
            for item in list(target.iterdir()):
                if item.is_file():
                    ext = item.suffix.lower()
                    subfolder_name = category_map.get(ext, "Other_Files")
                    dest_dir = target / subfolder_name
                    dest_dir.mkdir(exist_ok=True)
                    shutil.move(item, dest_dir / item.name)
                    moved_count += 1

            return {
                "success": True,
                "moved_count": moved_count,
                "message": f"Organized {moved_count} files into structured subfolders."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------
    # DOCUMENT SUMMARIZATION
    # -------------------------------------------------------------

    def summarize_document(self, file_path: str) -> Dict[str, Any]:
        """Generates an extractive summary and statistics for a text document."""
        read_res = self.read_file(file_path)
        if not read_res["success"]:
            return read_res

        content = read_res["content"]
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        words = content.split()
        char_count = len(content)

        # Extractive summary: first 3 non-empty lines + last non-empty line
        key_points = lines[:3]
        if len(lines) > 3 and lines[-1] not in key_points:
            key_points.append(lines[-1])

        return {
            "success": True,
            "path": file_path,
            "total_lines": len(lines),
            "total_words": len(words),
            "char_count": char_count,
            "summary_points": key_points,
            "message": f"Summary for '{file_path}': {len(words)} words, {len(lines)} lines."
        }

    # -------------------------------------------------------------
    # DEVELOPMENT / SCRIPT EXECUTION
    # -------------------------------------------------------------

    def execute_python_script(self, script_path: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """Safely executes a Python script contained within the workspace."""
        try:
            target = self.resolve_path(script_path)
            if not target.exists() or not target.is_file():
                return {"success": False, "error": f"Script '{script_path}' does not exist."}

            if target.suffix != ".py":
                return {"success": False, "error": f"'{script_path}' is not a Python (.py) file."}

            cmd = ["python", str(target)]
            if args:
                cmd.extend(args)

            self.security.validate_command_safety(cmd)

            logger.info(f"Executing Python script: {cmd}")
            proc = subprocess.run(
                cmd,
                cwd=str(target.parent),
                capture_output=True,
                text=True,
                timeout=15
            )

            is_success = proc.returncode == 0
            return {
                "success": is_success,
                "exit_code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "message": f"Script exited with code {proc.returncode}."
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Execution timed out (15 second limit exceeded)."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_with_default_app(self, item_path: str) -> Dict[str, Any]:
        """Opens a file or directory using the OS default application."""
        try:
            target = self.resolve_path(item_path)
            if not target.exists():
                return {"success": False, "error": f"'{item_path}' does not exist."}

            # Windows safe launch
            os.startfile(str(target))
            return {
                "success": True,
                "path": str(target.relative_to(self.root)),
                "message": f"Opened '{item_path}' with default application."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
