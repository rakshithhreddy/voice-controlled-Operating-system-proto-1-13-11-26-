"""
Conversational Context and Memory Module.
Maintains history of interactions, tracks active entities (folders, files),
and resolves anaphoric references such as 'it', 'there', 'that folder'.
"""

from typing import Optional, List, Dict, Any
from pathlib import Path


class ContextManager:
    """
    Maintains dialogue history and entity memory across conversational turns.
    """

    def __init__(self):
        self.last_folder: Optional[str] = None
        self.last_file: Optional[str] = None
        self.last_intent: Optional[str] = None
        self.last_action_success: bool = True
        self.history: List[Dict[str, Any]] = []

    def update_context(
        self,
        intent: Optional[str] = None,
        folder: Optional[str] = None,
        file: Optional[str] = None,
        success: bool = True,
        raw_text: Optional[str] = None,
        response_text: Optional[str] = None
    ) -> None:
        """Updates entity memory with the latest operation results."""
        if folder:
            self.last_folder = folder
        if file:
            self.last_file = file
        if intent:
            self.last_intent = intent
        self.last_action_success = success

        record = {
            "intent": intent,
            "folder": folder,
            "file": file,
            "success": success,
            "user_text": raw_text,
            "assistant_response": response_text
        }
        self.history.append(record)

    def resolve_pronoun(self, text: str) -> Optional[str]:
        """
        Resolves pronouns such as 'it', 'that', 'there', 'inside it', 'in that folder'
        to the most recently referenced folder or file.
        """
        text_lower = text.lower().strip()
        pronoun_phrases = [
            "inside it", "in it", "into it", "within it",
            "inside that", "in that", "into that",
            "inside there", "in there", "there",
            "inside that folder", "in that folder",
            "inside that directory", "in that directory",
            "inside the folder", "in the folder"
        ]

        for phrase in pronoun_phrases:
            if phrase in text_lower:
                return self.last_folder

        # Direct token checks
        words = text_lower.split()
        if "it" in words or "that" in words:
            # If context indicates a folder was recently created or focused on
            if self.last_folder:
                return self.last_folder
            elif self.last_file:
                return self.last_file

        return None

    def get_last_folder(self) -> Optional[str]:
        """Returns the last active folder in context."""
        return self.last_folder

    def get_last_file(self) -> Optional[str]:
        """Returns the last active file in context."""
        return self.last_file

    def clear(self) -> None:
        """Resets the conversational memory."""
        self.last_folder = None
        self.last_file = None
        self.last_intent = None
        self.last_action_success = True
        self.history.clear()
