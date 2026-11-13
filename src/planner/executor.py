"""
Task Executor Module (CAOP Voice OS 2.0).
Executes planned tasks, enforces dependencies, resolves dynamic workspace targets,
independently verifies physical filesystem state, and handles undo rollbacks.
"""

import os
import logging
from typing import Callable, Optional, Dict, Any, List
from pathlib import Path

from src.workspace.manager import WorkspaceManager
from src.nlp.intents import IntentType
from src.nlp.context import ContextManager
from src.planner.task import TaskItem, TaskStatus
from src.planner.planner import ExecutionPlan
from src.config import LOG_FILE

logger = logging.getLogger("VoiceOS.Executor")


class ExecutionResult:
    """Holds summary and detailed results of plan execution."""

    def __init__(self, plan: ExecutionPlan):
        self.plan = plan
        self.total = len(plan.tasks)
        self.succeeded: List[TaskItem] = []
        self.failed: List[TaskItem] = []
        self.skipped: List[TaskItem] = []
        self.overall_success: bool = False
        self.summary_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_success": self.overall_success,
            "total_tasks": self.total,
            "succeeded_count": len(self.succeeded),
            "failed_count": len(self.failed),
            "skipped_count": len(self.skipped),
            "summary_message": self.summary_message,
            "tasks": [t.to_dict() for t in self.plan.tasks]
        }


class TaskExecutor:
    """
    Executes tasks sequentially, resolves relative items, verifies disk state,
    and updates dialogue context.
    """

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        context_manager: Optional[ContextManager] = None,
        status_callback: Optional[Callable[[str, Optional[TaskItem]], None]] = None
    ):
        self.workspace = workspace_manager
        self.context = context_manager or ContextManager()
        self.status_callback = status_callback

    def notify(self, status: str, task: Optional[TaskItem] = None) -> None:
        if self.status_callback:
            try:
                self.status_callback(status, task)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def execute_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        result = ExecutionResult(plan)
        if plan.is_empty():
            result.overall_success = True
            result.summary_message = "No actionable operations detected."
            return result

        successful_task_ids = set()
        executed_targets = []

        for task in plan.tasks:
            # Check dependencies
            unmet_deps = [dep for dep in task.dependencies if dep not in successful_task_ids]
            if unmet_deps:
                task.status = TaskStatus.SKIPPED
                task.error_message = f"Skipped because dependent task(s) {unmet_deps} failed."
                result.skipped.append(task)
                self.notify("SKIPPED", task)
                continue

            task.status = TaskStatus.RUNNING
            self.notify("EXECUTING", task)

            task_outcome = self._dispatch_task(task)
            task.result = task_outcome

            # Independent verification phase
            task.status = TaskStatus.VERIFYING
            self.notify("VERIFYING", task)

            is_verified, verify_msg = self._verify_task(task, task_outcome)
            task.verified = is_verified

            if task_outcome.get("success", False) and is_verified:
                task.status = TaskStatus.COMPLETED
                successful_task_ids.add(task.task_id)
                result.succeeded.append(task)
                self.notify("COMPLETED", task)

                # Track created/modified target
                target_p = task_outcome.get("path") or task.target_path
                executed_targets.append(target_p)
                self._update_context_for_task(task, target_p)
            else:
                task.status = TaskStatus.FAILED
                err = task_outcome.get("error", verify_msg or "Execution or verification failed.")
                task.error_message = err
                result.failed.append(task)
                self.notify("FAILED", task)

        result.overall_success = (len(result.failed) == 0 and len(result.skipped) == 0)
        result.summary_message = self._build_natural_response(result)

        # Update turn context
        self.context.update_context(
            intent=plan.tasks[0].intent.value if plan.tasks else None,
            targets=executed_targets,
            success=result.overall_success,
            raw_text=plan.raw_instruction,
            response_text=result.summary_message
        )

        return result

    def _find_item_in_workspace(self, name_or_path: str, is_dir_only: bool = False) -> Optional[str]:
        """Locates an item anywhere in the workspace if only a base name was provided."""
        clean = name_or_path.strip().strip("'\"")
        # Direct check first
        direct = self.workspace.root / clean
        if direct.exists():
            return clean

        # Recursive search for matching relative item
        for p in self.workspace.root.rglob("*"):
            if ".trash" in p.parts:
                continue
            if is_dir_only and not p.is_dir():
                continue
            if p.name.lower() == clean.lower() or str(p.relative_to(self.workspace.root)).lower().endswith(clean.lower()):
                return str(p.relative_to(self.workspace.root))

        return None

    def _dispatch_task(self, task: TaskItem) -> Dict[str, Any]:
        """Executes task through WorkspaceManager with smart target resolution."""
        intent = task.intent
        target = task.target_path
        params = task.params

        try:
            if intent == IntentType.CREATE_FOLDER:
                return self.workspace.create_directory(target)

            elif intent == IntentType.CREATE_FILE:
                content = params.get("content", "")
                topic = params.get("topic_prompt", "")
                return self.workspace.create_file(target, initial_content=content, topic_prompt=topic)

            elif intent == IntentType.DELETE_FOLDER or intent == IntentType.DELETE_FILE:
                resolved_target = self._find_item_in_workspace(target) or target
                if intent == IntentType.DELETE_FOLDER:
                    return self.workspace.delete_directory(resolved_target)
                return self.workspace.delete_file(resolved_target)

            elif intent == IntentType.RENAME_FOLDER or intent == IntentType.RENAME_FILE:
                resolved_old = self._find_item_in_workspace(target) or target
                new_name = params.get("new_name", "")
                if not new_name and "to" in task.description:
                    new_name = task.description.split("to")[-1].strip().strip("'\"")

                # If old item is nested, keep in the same parent folder
                old_p = Path(resolved_old)
                if old_p.parent != Path("."):
                    final_new = str(old_p.parent / new_name)
                else:
                    final_new = new_name

                if intent == IntentType.RENAME_FOLDER:
                    return self.workspace.rename_directory(resolved_old, final_new)
                return self.workspace.rename_file(resolved_old, final_new)

            elif intent == IntentType.MOVE_ITEM:
                # Resolve source item
                resolved_src = self._find_item_in_workspace(target) or target
                # Resolve destination folder
                raw_dest = params.get("destination") or target
                resolved_dst = self._find_item_in_workspace(raw_dest, is_dir_only=True) or raw_dest

                return self.workspace.move_item(resolved_src, resolved_dst)

            elif intent == IntentType.COPY_ITEM:
                resolved_src = self._find_item_in_workspace(target) or target
                raw_dest = params.get("destination") or target
                resolved_dst = self._find_item_in_workspace(raw_dest, is_dir_only=True) or raw_dest
                return self.workspace.copy_item(resolved_src, resolved_dst)

            elif intent == IntentType.READ_FILE:
                resolved_file = self._find_item_in_workspace(target) or target
                return self.workspace.read_file(resolved_file)

            elif intent == IntentType.WRITE_FILE:
                resolved_file = self._find_item_in_workspace(target) or target
                return self.workspace.write_file(resolved_file, params.get("content", ""))

            elif intent == IntentType.APPEND_FILE:
                resolved_file = self._find_item_in_workspace(target) or target
                return self.workspace.append_file(resolved_file, params.get("content", ""))

            elif intent == IntentType.LIST_FOLDER:
                resolved_dir = self._find_item_in_workspace(target, is_dir_only=True) if target != "." else "."
                return self.workspace.list_directory(resolved_dir or ".")

            elif intent == IntentType.NAVIGATE_FOLDER:
                return self.workspace.change_directory(target)

            elif intent == IntentType.SEARCH_FILES:
                query = params.get("query") or target
                return self.workspace.search_files(query)

            elif intent == IntentType.FIND_BY_EXTENSION:
                ext = params.get("extension") or target
                return self.workspace.find_by_extension(ext)

            elif intent == IntentType.SEARCH_TEXT:
                pattern = params.get("query") or target
                return self.workspace.search_text_in_files(pattern)

            elif intent == IntentType.ORGANIZE_FILES:
                resolved_dir = self._find_item_in_workspace(target, is_dir_only=True) or target or "."
                return self.workspace.organize_directory(resolved_dir)

            elif intent == IntentType.FIND_DUPLICATES:
                return self.workspace.identify_duplicate_files(target or ".")

            elif intent == IntentType.FIND_TEMP:
                return self.workspace.find_temporary_files(target or ".")

            elif intent == IntentType.EXECUTE_SCRIPT:
                resolved_file = self._find_item_in_workspace(target) or target
                return self.workspace.execute_python_script(resolved_file)

            elif intent == IntentType.SUMMARIZE_FILE:
                resolved_file = self._find_item_in_workspace(target) or target
                return self.workspace.summarize_document(resolved_file)

            elif intent == IntentType.UNDO:
                return self.workspace.undo()

            elif intent == IntentType.OPEN_ITEM:
                resolved_item = self._find_item_in_workspace(target) or target
                return self.workspace.open_with_default_app(resolved_item)

            else:
                return {"success": False, "error": f"Unsupported or unknown intent: {intent}"}

        except Exception as e:
            logger.error(f"Execution error on task {task.task_id}: {e}")
            return {"success": False, "error": str(e)}

    def _verify_task(self, task: TaskItem, outcome: Dict[str, Any]) -> (bool, str):
        if not outcome.get("success", False):
            return False, outcome.get("error", "Operation indicated failure.")

        intent = task.intent

        try:
            if intent == IntentType.CREATE_FOLDER:
                resolved = self.workspace.resolve_path(outcome.get("path") or task.target_path)
                exists = resolved.exists() and resolved.is_dir()
                return exists, "Directory verified on disk." if exists else "Directory does not exist after creation."

            elif intent in [IntentType.CREATE_FILE, IntentType.WRITE_FILE, IntentType.APPEND_FILE]:
                resolved = self.workspace.resolve_path(outcome.get("path") or task.target_path)
                exists = resolved.exists() and resolved.is_file()
                return exists, "File verified on disk." if exists else "File does not exist after creation."

            elif intent in [IntentType.DELETE_FOLDER, IntentType.DELETE_FILE]:
                # If deleted, original path should not exist
                orig = self.workspace.root / (outcome.get("path") or task.target_path)
                exists = orig.exists()
                return (not exists), "Item deletion verified." if not exists else "Item still exists after deletion attempt."

            elif intent == IntentType.RENAME_FOLDER or intent == IntentType.RENAME_FILE:
                new_p = self.workspace.root / outcome.get("new_path", "")
                exists = new_p.exists()
                return exists, "Renamed item verified." if exists else "Renamed item not found on disk."

            elif intent == IntentType.MOVE_ITEM:
                dst_p = self.workspace.root / outcome.get("destination", "")
                exists = dst_p.exists()
                return exists, "Moved item verified at destination." if exists else "Item not found at move destination."

            elif intent in [IntentType.READ_FILE, IntentType.LIST_FOLDER, IntentType.SEARCH_FILES,
                            IntentType.FIND_BY_EXTENSION, IntentType.SEARCH_TEXT, IntentType.FIND_DUPLICATES,
                            IntentType.FIND_TEMP, IntentType.SUMMARIZE_FILE, IntentType.NAVIGATE_FOLDER,
                            IntentType.EXECUTE_SCRIPT, IntentType.OPEN_ITEM, IntentType.ORGANIZE_FILES,
                            IntentType.UNDO]:
                return True, "Operation completed."

            return True, "Verified."
        except Exception as e:
            return False, f"Verification exception: {e}"

    def _update_context_for_task(self, task: TaskItem, actual_path: str) -> None:
        if task.intent == IntentType.CREATE_FOLDER:
            self.context.update_context(folder=actual_path, success=True)
        elif task.intent == IntentType.CREATE_FILE:
            self.context.update_context(file=actual_path, success=True)
        elif task.intent == IntentType.RENAME_FOLDER:
            new_p = task.result.get("new_path", actual_path) if task.result else actual_path
            self.context.update_context(folder=new_p, success=True)

    def _build_natural_response(self, result: ExecutionResult) -> str:
        if result.total == 0:
            return "I couldn't identify any operations to perform."

        if result.overall_success:
            if result.total == 1:
                t = result.succeeded[0]
                msg = t.result.get("message") if t.result else ""
                if t.intent == IntentType.READ_FILE and t.result:
                    return f"Contents of '{t.target_path}':\n\n{t.result.get('content')}"
                if t.intent == IntentType.LIST_FOLDER and t.result:
                    items = [f"{i['name']} ({i['type']})" for i in t.result.get("items", [])]
                    items_str = ", ".join(items) if items else "folder is empty"
                    return f"Inside '{t.result.get('path') or t.target_path}': {items_str}."
                if t.intent == IntentType.UNDO and t.result:
                    return t.result.get("message", "Undo completed successfully.")
                if t.intent == IntentType.ORGANIZE_FILES and t.result:
                    return t.result.get("message", "Workspace organized successfully.")
                return msg or f"Successfully completed: {t.description}."
            else:
                steps = [t.description for t in result.succeeded]
                return f"Successfully executed all {result.total} operations: {'; '.join(steps)}."
        else:
            parts = []
            if result.succeeded:
                parts.append(f"Completed ({len(result.succeeded)}): {', '.join(t.description for t in result.succeeded)}.")
            if result.failed:
                fail_details = [f"{t.description} ({t.error_message})" for t in result.failed]
                parts.append(f"Failed ({len(result.failed)}): {'; '.join(fail_details)}.")
            if result.skipped:
                parts.append(f"Skipped ({len(result.skipped)}): {', '.join(t.description for t in result.skipped)}.")

            return " ".join(parts)
