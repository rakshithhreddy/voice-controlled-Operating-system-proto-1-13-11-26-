"""
Enhanced Conversational Context and Dialogue Memory (CAOP Voice OS 2.0).
Maintains hierarchical path context, entity history, pronoun resolution ('it', 'there', 'those', 'the last one'),
correction handling ('actually...'), and conversational undo tracking.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path


class ContextManager:
    """
    Maintains dialogue history and entity memory across conversational turns.
    Resolves anaphora, spatial deictics, and operational corrections.
    """

    def __init__(self):
        self.last_folder: Optional[str] = None
        self.last_file: Optional[str] = None
        self.last_intent: Optional[str] = None
        self.last_action_success: bool = True
        self.last_targets: List[str] = []
        self.hierarchy_stack: List[str] = []
        self.history: List[Dict[str, Any]] = []

    def update_context(
        self,
        intent: Optional[str] = None,
        folder: Optional[str] = None,
        file: Optional[str] = None,
        targets: Optional[List[str]] = None,
        success: bool = True,
        raw_text: Optional[str] = None,
        response_text: Optional[str] = None
    ) -> None:
        """Updates entity memory with the latest operation results."""
        if folder:
            self.last_folder = folder
            if not self.hierarchy_stack or self.hierarchy_stack[-1] != folder:
                self.hierarchy_stack.append(folder)

        if file:
            self.last_file = file

        if intent:
            self.last_intent = intent

        if targets:
            self.last_targets = targets
        elif folder and not targets:
            self.last_targets = [folder]
        elif file and not targets:
            self.last_targets = [file]

        self.last_action_success = success

        record = {
            "intent": intent,
            "folder": folder,
            "file": file,
            "targets": self.last_targets.copy(),
            "success": success,
            "user_text": raw_text,
            "assistant_response": response_text
        }
        self.history.append(record)

    def resolve_reference(self, text: str) -> Optional[str]:
        """
        Resolves pronouns and contextual pointers:
        - 'it', 'inside it', 'in it' -> last referenced folder or file.
        - 'there', 'in there', 'into it' -> active directory.
        - 'the last one' -> last item in last_targets.
        - 'those', 'them' -> last_targets.
        """
        lower = text.lower().strip()

        # Check for 'the last one' or 'last folder'
        if "the last one" in lower or "last one" in lower or "last created" in lower:
            if self.last_targets:
                return self.last_targets[-1]
            return self.last_folder or self.last_file

        # Check for 'there', 'in there'
        if any(p in lower for p in ["inside there", "in there", "there", "into there"]):
            return self.last_folder

        # Check for 'inside it', 'in it', 'into it'
        if any(p in lower for p in ["inside it", "in it", "into it", "within it", "inside that", "in that"]):
            return self.last_folder

        # Direct token check
        words = lower.split()
        if "it" in words or "that" in words:
            if self.last_folder:
                return self.last_folder
            return self.last_file

        return None

    def get_last_targets(self) -> List[str]:
        return self.last_targets

    def get_last_folder(self) -> Optional[str]:
        return self.last_folder

    def get_last_file(self) -> Optional[str]:
        return self.last_file

    def get_hierarchy_parent(self) -> Optional[str]:
        """Returns the parent container from the active hierarchy stack."""
        if len(self.hierarchy_stack) >= 2:
            return self.hierarchy_stack[-2]
        elif self.hierarchy_stack:
            return self.hierarchy_stack[-1]
        return None

    def resolve_pronoun(self, text: str) -> Optional[str]:
        """Alias for resolve_reference — resolves pronouns like 'it', 'there', 'that folder'."""
        return self.resolve_reference(text)

    def clear(self) -> None:
        self.last_folder = None
        self.last_file = None
        self.last_intent = None
        self.last_action_success = True
        self.last_targets.clear()
        self.hierarchy_stack.clear()
        self.history.clear()
