"""
Undo, Recovery, and Workspace Trash Manager.
Provides an internal recoverable recycle bin in '.trash/' and a reversible
action history stack for rolling back filesystem modifications.
"""

import os
import json
import uuid
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("VoiceOS.Trash")


class TrashManager:
    """
    Manages the internal workspace recycle bin located at 'workspace_data/.trash/'.
    Deletions are moved here with metadata so they can be restored.
    """

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.trash_dir = self.workspace_root / ".trash"
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.trash_dir / "metadata.json"
        self._load_metadata()

    def _load_metadata(self) -> None:
        if self.metadata_file.exists():
            try:
                self.metadata = json.loads(self.metadata_file.read_text(encoding="utf-8"))
            except Exception:
                self.metadata = {}
        else:
            self.metadata = {}

    def _save_metadata(self) -> None:
        try:
            self.metadata_file.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to save trash metadata: {e}")

    def move_to_trash(self, target: Path) -> Optional[str]:
        """Moves a target file or folder into .trash and logs metadata."""
        if not target.exists():
            return None

        # Prevent trashing the workspace root or the .trash folder itself
        if target == self.workspace_root or target == self.trash_dir:
            return None

        trash_id = str(uuid.uuid4())[:8]
        trash_name = f"{trash_id}_{target.name}"
        dest = self.trash_dir / trash_name

        rel_path = str(target.relative_to(self.workspace_root))
        is_dir = target.is_dir()

        shutil.move(target, dest)

        self.metadata[trash_id] = {
            "trash_id": trash_id,
            "trash_name": trash_name,
            "original_rel_path": rel_path,
            "is_dir": is_dir,
            "deleted_at": datetime.now().isoformat()
        }
        self._save_metadata()
        logger.info(f"Moved '{rel_path}' to trash as '{trash_name}' (ID: {trash_id}).")
        return trash_id

    def restore_from_trash(self, trash_id: str) -> Dict[str, Any]:
        """Restores a trashed item to its original location in workspace."""
        if trash_id not in self.metadata:
            return {"success": False, "error": f"Trash record '{trash_id}' not found."}

        record = self.metadata[trash_id]
        trash_item = self.trash_dir / record["trash_name"]
        orig_dest = self.workspace_root / record["original_rel_path"]

        if not trash_item.exists():
            return {"success": False, "error": f"Item '{record['trash_name']}' no longer exists in trash."}

        orig_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(trash_item, orig_dest)

        del self.metadata[trash_id]
        self._save_metadata()
        logger.info(f"Restored '{record['original_rel_path']}' from trash.")
        return {
            "success": True,
            "restored_path": record["original_rel_path"],
            "message": f"Successfully restored '{record['original_rel_path']}'."
        }


class UndoManager:
    """
    Maintains an undo stack of mutable filesystem operations to enable
    reversing recent changes.
    """

    def __init__(self, workspace_root: Path, trash_manager: TrashManager):
        self.workspace_root = workspace_root
        self.trash = trash_manager
        self.undo_stack: List[Dict[str, Any]] = []

    def record_action(self, action_type: str, details: Dict[str, Any]) -> None:
        """
        Records an operation for potential undo.
        Supported action_types:
        - CREATE_FILE: details={'path': ...}
        - CREATE_FOLDER: details={'path': ...}
        - DELETE_ITEM: details={'path': ..., 'trash_id': ...}
        - MOVE_ITEM: details={'source': ..., 'destination': ...}
        - RENAME_ITEM: details={'old_path': ..., 'new_path': ...}
        - WRITE_FILE / EDIT_FILE: details={'path': ..., 'previous_content': ...}
        - COPY_ITEM: details={'created_copy': ...}
        """
        self.undo_stack.append({
            "action_type": action_type,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"Recorded action for undo: {action_type} - {details.get('path') or details.get('source')}")

    def undo_last(self) -> Dict[str, Any]:
        """Reverses the most recent operation on the undo stack."""
        if not self.undo_stack:
            return {"success": False, "error": "No operations to undo."}

        record = self.undo_stack.pop()
        action = record["action_type"]
        d = record["details"]

        try:
            if action == "CREATE_FILE":
                target = self.workspace_root / d["path"]
                if target.exists() and target.is_file():
                    target.unlink()
                    return {"success": True, "message": f"Undid file creation: deleted '{d['path']}'."}
                return {"success": False, "error": f"File '{d['path']}' already absent."}

            elif action == "CREATE_FOLDER":
                target = self.workspace_root / d["path"]
                if target.exists() and target.is_dir():
                    shutil.rmtree(target)
                    return {"success": True, "message": f"Undid folder creation: deleted folder '{d['path']}'."}
                return {"success": False, "error": f"Folder '{d['path']}' already absent."}

            elif action == "DELETE_ITEM":
                trash_id = d.get("trash_id")
                if trash_id:
                    return self.trash.restore_from_trash(trash_id)
                return {"success": False, "error": "No trash identifier available for undoing deletion."}

            elif action == "MOVE_ITEM":
                curr_dst = self.workspace_root / d["destination"]
                orig_src = self.workspace_root / d["source"]
                if curr_dst.exists():
                    orig_src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(curr_dst, orig_src)
                    return {"success": True, "message": f"Undid move: moved '{d['destination']}' back to '{d['source']}'."}
                return {"success": False, "error": f"Item '{d['destination']}' not found."}

            elif action == "RENAME_ITEM":
                new_p = self.workspace_root / d["new_path"]
                old_p = self.workspace_root / d["old_path"]
                if new_p.exists():
                    new_p.rename(old_p)
                    return {"success": True, "message": f"Undid rename: renamed '{d['new_path']}' back to '{d['old_path']}'."}
                return {"success": False, "error": f"Item '{d['new_path']}' not found."}

            elif action in ["WRITE_FILE", "EDIT_FILE"]:
                target = self.workspace_root / d["path"]
                prev_content = d.get("previous_content")
                if prev_content is not None:
                    target.write_text(prev_content, encoding="utf-8")
                    return {"success": True, "message": f"Undid edit: restored previous content of '{d['path']}'."}
                return {"success": False, "error": "No previous content backup stored."}

            elif action == "COPY_ITEM":
                copy_p = self.workspace_root / d["created_copy"]
                if copy_p.exists():
                    if copy_p.is_dir():
                        shutil.rmtree(copy_p)
                    else:
                        copy_p.unlink()
                    return {"success": True, "message": f"Undid copy: removed '{d['created_copy']}'."}
                return {"success": False, "error": f"Copy '{d['created_copy']}' not found."}

            return {"success": False, "error": f"Unsupported undo action: '{action}'."}

        except Exception as e:
            logger.error(f"Error during undo of {action}: {e}")
            return {"success": False, "error": f"Failed to undo {action}: {str(e)}"}
