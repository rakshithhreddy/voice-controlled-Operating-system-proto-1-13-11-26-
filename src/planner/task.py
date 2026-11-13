"""
Task Data Model for Task Planning and Execution.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from src.nlp.intents import IntentType


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    ROLLED_BACK = "ROLLED_BACK"


class TaskItem:
    """
    Represents an atomic operation to be executed within the workspace.
    """

    def __init__(
        self,
        task_id: int,
        intent: IntentType,
        description: str,
        target_path: str,
        source_path: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[int]] = None
    ):
        self.task_id = task_id
        self.intent = intent
        self.description = description
        self.target_path = target_path
        self.source_path = source_path
        self.params = params or {}
        self.dependencies: List[int] = dependencies or []

        self.status = TaskStatus.PENDING
        self.result: Optional[Dict[str, Any]] = None
        self.verified: bool = False
        self.error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "intent": self.intent.value,
            "description": self.description,
            "target_path": self.target_path,
            "source_path": self.source_path,
            "params": self.params,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "verified": self.verified,
            "error_message": self.error_message,
            "result": self.result
        }

    def __repr__(self) -> str:
        return f"<TaskItem #{self.task_id} [{self.status.value}] {self.description}>"
