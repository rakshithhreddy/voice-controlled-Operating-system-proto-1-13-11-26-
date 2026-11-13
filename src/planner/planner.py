"""
Intelligent Task Planner Module (CAOP Voice OS 2.0).
Constructs sequenced, dependency-aware execution plans, resolving hierarchical
directory paths, contextual references, and multi-clause relationships.
"""

from typing import List, Dict, Any, Optional
from src.nlp.parser import ParsedInstruction
from src.nlp.intents import IntentType
from src.planner.task import TaskItem, TaskStatus


class ExecutionPlan:
    """Represents a sequenced plan of tasks with dependencies."""

    def __init__(self, raw_instruction: str, tasks: List[TaskItem]):
        self.raw_instruction = raw_instruction
        self.tasks = tasks

    def is_empty(self) -> bool:
        return len(self.tasks) == 0

    def total_tasks(self) -> int:
        return len(self.tasks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instruction": self.raw_instruction,
            "total_tasks": len(self.tasks),
            "tasks": [t.to_dict() for t in self.tasks]
        }


class TaskPlanner:
    """
    Sequences tasks, maps dependencies, and resolves hierarchical folder paths.
    """

    def __init__(self):
        pass

    def create_plan(
        self,
        raw_instruction: str,
        parsed_instructions: List[ParsedInstruction],
        current_workspace_cwd: str = "."
    ) -> ExecutionPlan:
        """
        Creates an ExecutionPlan from ParsedInstructions with hierarchical path resolution.
        """
        tasks: List[TaskItem] = []
        planned_folder_paths: Dict[str, str] = {}
        folder_creator_tasks: Dict[str, int] = {}

        for inst in parsed_instructions:
            intent = inst.intent
            target = inst.target_name or ""
            dest = inst.destination
            deps: List[int] = []

            # Resolve destination hierarchy
            parent_dir = ""
            if dest:
                if dest in planned_folder_paths:
                    parent_dir = planned_folder_paths[dest]
                    if dest in folder_creator_tasks:
                        deps.append(folder_creator_tasks[dest])
                else:
                    matched = False
                    for p_name, p_path in planned_folder_paths.items():
                        if p_name.lower() == dest.lower() or p_path.lower().endswith(dest.lower()):
                            parent_dir = p_path
                            matched = True
                            if p_name in folder_creator_tasks:
                                deps.append(folder_creator_tasks[p_name])
                            break
                    if not matched:
                        parent_dir = dest
            elif current_workspace_cwd != ".":
                parent_dir = current_workspace_cwd

            # Determine final target path
            if intent in [IntentType.MOVE_ITEM, IntentType.COPY_ITEM, IntentType.RENAME_FILE, IntentType.RENAME_FOLDER]:
                full_target = target
            elif parent_dir and parent_dir != "." and target:
                full_target = f"{parent_dir}/{target}"
            elif target:
                if target in planned_folder_paths:
                    full_target = planned_folder_paths[target]
                else:
                    full_target = target
            else:
                full_target = parent_dir or "."

            desc = self._generate_description(intent, target or full_target, parent_dir, inst)

            task = TaskItem(
                task_id=inst.step_id,
                intent=intent,
                description=desc,
                target_path=full_target,
                source_path=None,
                params={
                    "content": inst.content or "",
                    "topic_prompt": inst.topic_prompt or "",
                    "extension": inst.extension,
                    "query": inst.query,
                    "new_name": inst.new_name,
                    "destination": parent_dir or dest
                },
                dependencies=deps
            )

            tasks.append(task)

            # Record created folders for downstream relative path resolution
            if intent == IntentType.CREATE_FOLDER and target:
                planned_folder_paths[target] = full_target
                folder_creator_tasks[target] = task.task_id

        ordered_tasks = self._order_tasks_by_dependencies(tasks)
        return ExecutionPlan(raw_instruction, ordered_tasks)

    def _generate_description(
        self,
        intent: IntentType,
        target: str,
        parent_dir: str,
        inst: ParsedInstruction
    ) -> str:
        loc = f" inside '{parent_dir}'" if parent_dir and parent_dir != "." else ""
        if intent == IntentType.CREATE_FOLDER:
            return f"Create folder '{target}'{loc}"
        elif intent == IntentType.CREATE_FILE:
            topic_str = f" with content about '{inst.topic_prompt}'" if inst.topic_prompt else ""
            return f"Create file '{target}'{loc}{topic_str}"
        elif intent == IntentType.DELETE_FOLDER:
            return f"Delete folder '{target}'"
        elif intent == IntentType.DELETE_FILE:
            return f"Delete file '{target}'"
        elif intent == IntentType.RENAME_FOLDER or intent == IntentType.RENAME_FILE:
            return f"Rename '{target}' to '{inst.new_name or 'new name'}'"
        elif intent == IntentType.MOVE_ITEM:
            return f"Move '{target}' to '{parent_dir or inst.destination}'"
        elif intent == IntentType.READ_FILE:
            return f"Read content of '{target}'"
        elif intent == IntentType.WRITE_FILE:
            return f"Write content to '{target}'"
        elif intent == IntentType.APPEND_FILE:
            return f"Append content to '{target}'"
        elif intent == IntentType.LIST_FOLDER:
            return f"List contents of '{target or 'workspace'}'"
        elif intent == IntentType.SEARCH_FILES:
            return f"Search for '{inst.query or target}'"
        elif intent == IntentType.FIND_BY_EXTENSION:
            return f"Find files with extension '{inst.extension or target}'"
        elif intent == IntentType.EXECUTE_SCRIPT:
            return f"Execute Python script '{target}'"
        elif intent == IntentType.SUMMARIZE_FILE:
            return f"Summarize document '{target}'"
        elif intent == IntentType.ORGANIZE_FILES:
            return f"Organize directory '{target or 'workspace'}'"
        elif intent == IntentType.FIND_DUPLICATES:
            return f"Identify duplicate files"
        elif intent == IntentType.UNDO:
            return "Undo previous operation"
        return f"Execute {intent.value} on '{target}'"

    def _order_tasks_by_dependencies(self, tasks: List[TaskItem]) -> List[TaskItem]:
        task_map = {t.task_id: t for t in tasks}
        visited = set()
        ordered = []

        def visit(task_id: int):
            if task_id in visited or task_id not in task_map:
                return
            t = task_map[task_id]
            for dep in t.dependencies:
                visit(dep)
            visited.add(task_id)
            ordered.append(t)

        for t in tasks:
            visit(t.task_id)

        return ordered
