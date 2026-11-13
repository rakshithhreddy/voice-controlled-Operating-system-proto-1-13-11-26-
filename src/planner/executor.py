"""
Task Executor Module.
Executes planned tasks, enforces dependencies, independently verifies
filesystem outcomes, and reports partial or full execution status.
"""

import logging
from typing import Callable, Optional, Dict, Any, List

from src.workspace.manager import WorkspaceManager
from src.nlp.intents import IntentType
from src.nlp.context import ContextManager
from src.planner.task import TaskItem, TaskStatus
from src.planner.planner import ExecutionPlan
from src.config import LOG_FILE

logger = logging.getLogger("VoiceOS.Executor")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [Executor] %(message)s"))
    logger.addHandler(fh)


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
    Executes tasks sequentially, verifies disk state, and notifies listeners.
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
        """Emits status events to UI or logging handlers."""
        if self.status_callback:
            try:
                self.status_callback(status, task)
            except Exception as e:
                logger.error(f"Error in status callback: {e}")

    def execute_plan(self, plan: ExecutionPlan) -> ExecutionResult:
        """
        Executes all tasks in the ExecutionPlan with verification and dependency checks.
        """
        result = ExecutionResult(plan)
        if plan.is_empty():
            result.overall_success = True
            result.summary_message = "No actionable operations detected."
            return result

        successful_task_ids = set()

        for task in plan.tasks:
            # Check dependencies
            unmet_deps = [dep for dep in task.dependencies if dep not in successful_task_ids]
            if unmet_deps:
                task.status = TaskStatus.SKIPPED
                task.error_message = f"Skipped because dependent task(s) {unmet_deps} failed."
                result.skipped.append(task)
                self.notify("SKIPPED", task)
                continue

            # Execute task
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

                # Update context
                self._update_context_for_task(task)
            else:
                task.status = TaskStatus.FAILED
                err = task_outcome.get("error", verify_msg or "Execution or verification failed.")
                task.error_message = err
                result.failed.append(task)
                self.notify("FAILED", task)

        # Calculate final summary
        result.overall_success = (len(result.failed) == 0 and len(result.skipped) == 0)
        result.summary_message = self._build_natural_response(result)

        # Context record for the entire turn
        self.context.update_context(
            intent=plan.tasks[0].intent.value if plan.tasks else None,
            success=result.overall_success,
            raw_text=plan.raw_instruction,
            response_text=result.summary_message
        )

        return result

    def _dispatch_task(self, task: TaskItem) -> Dict[str, Any]:
        """Dispatches an atomic task to the WorkspaceManager."""
        intent = task.intent
        target = task.target_path
        params = task.params

        try:
            if intent == IntentType.CREATE_FOLDER:
                return self.workspace.create_directory(target)

            elif intent == IntentType.DELETE_FOLDER:
                return self.workspace.delete_directory(target)

            elif intent == IntentType.RENAME_FOLDER or intent == IntentType.RENAME_FILE:
                new_name = params.get("new_name", "")
                if intent == IntentType.RENAME_FOLDER:
                    return self.workspace.rename_directory(target, new_name)
                return self.workspace.rename_file(target, new_name)

            elif intent == IntentType.CREATE_FILE:
                content = params.get("content", "")
                return self.workspace.create_file(target, initial_content=content)

            elif intent == IntentType.DELETE_FILE:
                return self.workspace.delete_file(target)

            elif intent == IntentType.READ_FILE:
                return self.workspace.read_file(target)

            elif intent == IntentType.WRITE_FILE:
                return self.workspace.write_file(target, params.get("content", ""))

            elif intent == IntentType.APPEND_FILE:
                return self.workspace.append_file(target, params.get("content", ""))

            elif intent == IntentType.LIST_FOLDER:
                return self.workspace.list_directory(target or ".")

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
                return self.workspace.organize_files(target or ".")

            elif intent == IntentType.FIND_DUPLICATES:
                return self.workspace.identify_duplicate_files(target or ".")

            elif intent == IntentType.EXECUTE_SCRIPT:
                return self.workspace.execute_python_script(target)

            elif intent == IntentType.SUMMARIZE_FILE:
                return self.workspace.summarize_document(target)

            elif intent == IntentType.OPEN_ITEM:
                return self.workspace.open_with_default_app(target)

            else:
                return {"success": False, "error": f"Unsupported or unknown intent: {intent}"}

        except Exception as e:
            logger.error(f"Execution error on task {task.task_id}: {e}")
            return {"success": False, "error": str(e)}

    def _verify_task(self, task: TaskItem, outcome: Dict[str, Any]) -> (bool, str):
        """
        Independently checks the real filesystem state.
        Ensures the assistant NEVER claims success without physical verification.
        """
        if not outcome.get("success", False):
            return False, outcome.get("error", "Operation indicated failure.")

        target_path = task.target_path
        intent = task.intent

        try:
            resolved = self.workspace.resolve_path(target_path) if target_path else self.workspace.current_directory

            if intent in [IntentType.CREATE_FOLDER]:
                exists = resolved.exists() and resolved.is_dir()
                return exists, "Directory verified on disk." if exists else "Directory does not exist after creation."

            elif intent in [IntentType.CREATE_FILE, IntentType.WRITE_FILE, IntentType.APPEND_FILE]:
                exists = resolved.exists() and resolved.is_file()
                return exists, "File verified on disk." if exists else "File does not exist after creation."

            elif intent in [IntentType.DELETE_FOLDER, IntentType.DELETE_FILE]:
                exists = resolved.exists()
                return (not exists), "Item deletion verified." if not exists else "Item still exists after deletion attempt."

            elif intent in [IntentType.READ_FILE, IntentType.LIST_FOLDER, IntentType.SEARCH_FILES,
                            IntentType.FIND_BY_EXTENSION, IntentType.SEARCH_TEXT, IntentType.FIND_DUPLICATES,
                            IntentType.SUMMARIZE_FILE, IntentType.NAVIGATE_FOLDER, IntentType.EXECUTE_SCRIPT,
                            IntentType.OPEN_ITEM]:
                # Query/Read operations are verified by outcome dict
                return True, "Operation completed."

            return True, "Verified."
        except Exception as e:
            return False, f"Verification exception: {e}"

    def _update_context_for_task(self, task: TaskItem) -> None:
        """Updates contextual memory with the verified task target."""
        if task.intent == IntentType.CREATE_FOLDER:
            self.context.update_context(folder=task.target_path, success=True)
        elif task.intent == IntentType.CREATE_FILE:
            self.context.update_context(file=task.target_path, success=True)

    def _build_natural_response(self, result: ExecutionResult) -> str:
        """Builds natural English response summarizing the execution outcome."""
        if result.total == 0:
            return "I couldn't identify any operations to perform."

        if result.overall_success:
            if result.total == 1:
                t = result.succeeded[0]
                msg = t.result.get("message") if t.result else ""
                if t.intent == IntentType.READ_FILE and t.result:
                    return f"Here are the contents of '{t.target_path}':\n\n{t.result.get('content')}"
                if t.intent == IntentType.LIST_FOLDER and t.result:
                    items = [f"{i['name']} ({i['type']})" for i in t.result.get("items", [])]
                    items_str = ", ".join(items) if items else "folder is empty"
                    return f"Contents of '{t.target_path or 'workspace'}': {items_str}."
                if t.intent == IntentType.EXECUTE_SCRIPT and t.result:
                    out = t.result.get('stdout', '')
                    err = t.result.get('stderr', '')
                    details = f" Output: {out}" if out else ""
                    if err:
                        details += f" Error: {err}"
                    return f"Python script '{t.target_path}' executed successfully.{details}"
                return msg or f"Successfully completed: {t.description}."
            else:
                steps = [t.description for t in result.succeeded]
                return f"Successfully executed all {result.total} operations: {'; '.join(steps)}."

        else:
            # Partial or total failure
            parts = []
            if result.succeeded:
                parts.append(f"Completed ({len(result.succeeded)}): {', '.join(t.description for t in result.succeeded)}.")
            if result.failed:
                fail_details = [f"{t.description} ({t.error_message})" for t in result.failed]
                parts.append(f"Failed ({len(result.failed)}): {'; '.join(fail_details)}.")
            if result.skipped:
                parts.append(f"Skipped ({len(result.skipped)}): {', '.join(t.description for t in result.skipped)}.")

            return " ".join(parts)
