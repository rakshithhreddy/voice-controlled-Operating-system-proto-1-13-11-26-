"""
Intent Definitions and Semantic Classifier (CAOP Voice OS 2.0).
Maps natural conversational utterances to standardized OS operational intents.
Includes Undo, Reversal, Search, Recovery, and Multi-turn corrections.
"""

from enum import Enum
from typing import List, Tuple, Optional
import re


class IntentType(str, Enum):
    # Folder operations
    CREATE_FOLDER = "CREATE_FOLDER"
    DELETE_FOLDER = "DELETE_FOLDER"
    RENAME_FOLDER = "RENAME_FOLDER"
    LIST_FOLDER = "LIST_FOLDER"
    NAVIGATE_FOLDER = "NAVIGATE_FOLDER"

    # File operations
    CREATE_FILE = "CREATE_FILE"
    DELETE_FILE = "DELETE_FILE"
    RENAME_FILE = "RENAME_FILE"
    READ_FILE = "READ_FILE"
    WRITE_FILE = "WRITE_FILE"
    APPEND_FILE = "APPEND_FILE"
    COPY_ITEM = "COPY_ITEM"
    MOVE_ITEM = "MOVE_ITEM"

    # Search & Organization
    SEARCH_FILES = "SEARCH_FILES"
    FIND_BY_EXTENSION = "FIND_BY_EXTENSION"
    SEARCH_TEXT = "SEARCH_TEXT"
    ORGANIZE_FILES = "ORGANIZE_FILES"
    FIND_DUPLICATES = "FIND_DUPLICATES"
    FIND_TEMP = "FIND_TEMP"

    # Development & System
    EXECUTE_SCRIPT = "EXECUTE_SCRIPT"
    SUMMARIZE_FILE = "SUMMARIZE_FILE"
    OPEN_ITEM = "OPEN_ITEM"

    # Reversal & Conversational Control
    UNDO = "UNDO"
    CORRECTION = "CORRECTION"

    # System / Ambiguous
    UNKNOWN = "UNKNOWN"


class IntentClassifier:
    """
    Classifies natural English requests into structured intents using layered
    semantic patterns, contextual cues, and action verb analysis.
    """

    def __init__(self):
        self.rules: List[Tuple[IntentType, List[re.Pattern]]] = [
            # 1. Undo / Reversal
            (IntentType.UNDO, [
                re.compile(r"\b(undo|undo\s+that|revert|revert\s+that|rollback|roll\s+back|take\s+that\s+back)\b", re.I),
                re.compile(r"\bundo\s+(the\s+)?(last\s+)?(operation|action|step|change)\b", re.I),
                re.compile(r"\b(actually,?\s+)?(move|put)\s+it\s+back\b", re.I)
            ]),

            # 2. Correction / Override
            (IntentType.CORRECTION, [
                re.compile(r"\bactually,?\s+(don't|do\s+not)\s+(delete|remove)\b", re.I),
                re.compile(r"\bactually,?\s+(change|rename)\b", re.I),
                re.compile(r"\bno,?\s+(put|move|place)\s+it\b", re.I)
            ]),

            # 3. Organize Files & Workspace
            (IntentType.ORGANIZE_FILES, [
                re.compile(r"\b(organize|clean\s+up|sort|structure|tidy\s+up|categorize)\s+(the\s+)?(files|folder|directory|workspace|college\s+folder)?\b", re.I),
                re.compile(r"\b(organize|sort)\s+.+\s+based\s+on\s+file\s+type\b", re.I),
                re.compile(r"\b(separate|group)\s+(images|videos|documents|python\s+files)\b", re.I)
            ]),

            # 4. Find Duplicates
            (IntentType.FIND_DUPLICATES, [
                re.compile(r"\b(find|detect|check\s+for|list|show)\s+(duplicate|repeated)\s+files\b", re.I),
                re.compile(r"\bduplicate\s+files\b", re.I)
            ]),

            # 5. Find / Delete Temporary Files
            (IntentType.FIND_TEMP, [
                re.compile(r"\b(find|detect|list|show)\s+(temporary|temp|backup)\s+files\b", re.I),
                re.compile(r"\b(delete|remove|clean)\s+(the\s+)?(temporary|temp)\s+files\b", re.I)
            ]),

            # 6. Execute Python Script
            (IntentType.EXECUTE_SCRIPT, [
                re.compile(r"\b(run|execute|launch|start)\s+(the\s+)?(python\s+script|script|code|program|test)\b", re.I),
                re.compile(r"\b(run|execute)\s+[\w\-./\\]+\.py\b", re.I)
            ]),

            # 7. Summarize Document
            (IntentType.SUMMARIZE_FILE, [
                re.compile(r"\b(summarize|give\s+a\s+summary\s+of|summary\s+for|brief)\s+(the\s+)?(file|document|text)?\b", re.I),
                re.compile(r"\b(what\s+is\s+in|explain\s+contents\s+of)\s+(the\s+)?(file|document)\b", re.I)
            ]),

            # 8. Search Text in Files (Grep)
            (IntentType.SEARCH_TEXT, [
                re.compile(r"\b(search\s+for\s+text|find\s+text|grep|look\s+for\s+text|search\s+inside)\b", re.I),
                re.compile(r"\bwhich\s+files\s+contain\b", re.I)
            ]),

            # 9. Find by Extension
            (IntentType.FIND_BY_EXTENSION, [
                re.compile(r"\b(find|list|show|search)\s+(all\s+)?(?!all\b|my\b|the\b|these\b|those\b)([a-z0-9_-]+)\s+files\b", re.I),
                re.compile(r"\b(find|list|show)\s+(all\s+)?files\s+ending\s+with\b", re.I),
                re.compile(r"\b(find|list|show)\s+(all\s+)?files\s+with\s+(extension|\.[\w]+)\b", re.I)
            ]),

            # 10. Search Files / Folders
            (IntentType.SEARCH_FILES, [
                re.compile(r"\b(search\s+for|look\s+for|where\s+is|find\s+file|find\s+folder|find\s+directory)\b", re.I),
                re.compile(r"\bfind\s+(the\s+)?files\s+related\s+to\b", re.I)
            ]),

            # 11. Append to File
            (IntentType.APPEND_FILE, [
                re.compile(r"\b(append|add)\s+.+\s+(to|into)\s+(the\s+)?file\b", re.I),
                re.compile(r"\bappend\s+to\b", re.I)
            ]),

            # 12. Write to File
            (IntentType.WRITE_FILE, [
                re.compile(r"\b(write|put|insert)\s+.+\s+(in|into|to)\s+(the\s+)?file\b", re.I),
                re.compile(r"\boverwrite\b", re.I)
            ]),

            # 13. Read File
            (IntentType.READ_FILE, [
                re.compile(r"\b(read|cat|display|view|show|print)\s+(the\s+)?contents\s+of\b", re.I),
                re.compile(r"\b(read|cat|display|view|show|print)\s+(the\s+)?(contents\s+of\s+)?(file|document)\b", re.I),
                re.compile(r"\b(show|read)\s+[\w\-./\\]+\.(txt|py|md|json|log|csv)\b", re.I)
            ]),

            # 14. Move Item
            (IntentType.MOVE_ITEM, [
                re.compile(r"\b(move|relocate|transfer)\s+(all\s+)?(the\s+)?(python\s+files|files|file|folder|directory)?\b", re.I),
                re.compile(r"\bmove\s+[\w\-./\\]+\s+(in|into|to)\b", re.I)
            ]),

            # 15. Copy Item
            (IntentType.COPY_ITEM, [
                re.compile(r"\b(copy|duplicate)\s+(the\s+)?(file|folder|directory)?\b", re.I)
            ]),

            # 16. Rename File / Folder
            (IntentType.RENAME_FILE, [
                re.compile(r"\brename\s+(the\s+)?file\b", re.I),
                re.compile(r"\bchange\s+the\s+name\s+of\s+(the\s+)?file\b", re.I),
                re.compile(r"\brename\s+[\w\-./\\]+\.[a-zA-Z0-9]+\s+to\b", re.I)
            ]),
            (IntentType.RENAME_FOLDER, [
                re.compile(r"\brename\s+(the\s+)?(folder|directory)\b", re.I),
                re.compile(r"\bchange\s+the\s+name\s+of\s+(the\s+)?(folder|directory)\b", re.I),
                re.compile(r"\brename\s+(the\s+)?(last\s+one|folder\s+\w+)\s+to\b", re.I)
            ]),

            # 17. Delete File
            (IntentType.DELETE_FILE, [
                re.compile(r"\b(delete|remove|erase|destroy|drop)\s+(the\s+)?file\b", re.I),
                re.compile(r"\b(delete|remove)\s+[\w\-./\\]+\.(txt|py|md|json|log|csv)\b", re.I)
            ]),

            # 18. Delete Folder
            (IntentType.DELETE_FOLDER, [
                re.compile(r"\b(delete|remove|erase|destroy|rmdir)\s+(the\s+)?(folder|directory)\b", re.I)
            ]),

            # 19. Open Item
            (IntentType.OPEN_ITEM, [
                re.compile(r"\b(open|launch)\s+(the\s+)?(file|folder|directory|document|application)\b", re.I)
            ]),

            # 20. Navigate / Change Directory
            (IntentType.NAVIGATE_FOLDER, [
                re.compile(r"\b(navigate\s+to|go\s+to|cd\s+to|enter|switch\s+to|change\s+directory\s+to)\b", re.I),
                re.compile(r"\bgo\s+up(\s+one\s+level|\s+to\s+parent)?\b", re.I)
            ]),

            # 21. List Folder
            (IntentType.LIST_FOLDER, [
                re.compile(r"\b(list|show|display|what\s+is\s+in|dir|ls)\s*(all\s+)?(contents|files|folders|items|in\s+the\s+workspace|in\s+this\s+folder)?\b", re.I),
                re.compile(r"\bshow\s+me\s+what\s+is\s+inside\b", re.I),
                re.compile(r"\bwhat\s+(files|folders)\s+(are\s+)?here\b", re.I)
            ]),

            # 22. Create File
            (IntentType.CREATE_FILE, [
                re.compile(r"\b(create|make|generate|build|touch|new|set\s+up|write|add)\s+(a\s+|an\s+)?([a-z0-9_-]+\s+)?file\b", re.I),
                re.compile(r"\b(in|inside)\s+(the\s+)?[\w\s]+\s+(create|make)\s+(a\s+|an\s+)?(text\s+|python\s+)?file\b", re.I),
                re.compile(r"\b(create|make)\s+(a\s+)?readme\b", re.I),
                re.compile(r"\b(create|make|generate)\s+[\w\-./\\]+\.(py|txt|md|json|csv|log|html|css|js)\b", re.I)
            ]),

            # 23. Create Folder
            (IntentType.CREATE_FOLDER, [
                re.compile(r"\b(create|make|generate|set\s+up|build|mkdir|add|initialize)\s+(a\s+|an\s+|the\s+)?(new\s+)?(folder|directory|dir)\b", re.I),
                re.compile(r"\bmkdir\s+[A-Za-z0-9_\-]+", re.I),
                re.compile(r"\b(create|make)\s+\w+\s+(folders?|directories)\b", re.I),
                re.compile(r"\bi\s+need\s+(a\s+)?(folder|directory)\b", re.I),
                re.compile(r"\bi\s+want\s+you\s+to\s+create\s+a\s+folder\b", re.I),
                re.compile(r"\b(inside|in)\s+[\w\s]+,\s*create\s+(a\s+)?folder\b", re.I)
            ])
        ]

    def classify(self, text: str) -> IntentType:
        """Determines the primary IntentType for a given single clause."""
        cleaned = text.strip()
        for intent, patterns in self.rules:
            for pattern in patterns:
                if pattern.search(cleaned):
                    return intent

        # Fallback heuristic analysis
        lower = cleaned.lower()
        if any(w in lower for w in ["undo", "revert"]):
            return IntentType.UNDO
        if any(w in lower for w in ["organize", "clean up", "sort"]):
            return IntentType.ORGANIZE_FILES
        if any(w in lower for w in ["folder", "directory", "dir"]) and any(w in lower for w in ["create", "make", "setup", "need", "new"]):
            return IntentType.CREATE_FOLDER
        if any(w in lower for w in ["file", "script", "document"]) and any(w in lower for w in ["create", "make", "new", "touch"]):
            return IntentType.CREATE_FILE
        if any(w in lower for w in ["move", "transfer", "relocate"]):
            return IntentType.MOVE_ITEM
        if any(w in lower for w in ["rename", "change name"]):
            return IntentType.RENAME_FOLDER if "folder" in lower else IntentType.RENAME_FILE
        if any(w in lower for w in ["list", "show", "see"]) and any(w in lower for w in ["files", "folders", "contents", "inside"]):
            return IntentType.LIST_FOLDER
        if any(w in lower for w in ["delete", "remove", "destroy"]):
            return IntentType.DELETE_FOLDER if "folder" in lower else IntentType.DELETE_FILE

        return IntentType.UNKNOWN
