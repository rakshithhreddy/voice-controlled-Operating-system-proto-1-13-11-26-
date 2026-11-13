"""
Intent Definitions and Semantic Classifier.
Maps natural English phrases and variations to standardized OS intents.
"""

from enum import Enum
from typing import List, Dict, Tuple, Optional
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
    
    # Development & System
    EXECUTE_SCRIPT = "EXECUTE_SCRIPT"
    SUMMARIZE_FILE = "SUMMARIZE_FILE"
    OPEN_ITEM = "OPEN_ITEM"
    
    # System / Ambiguous
    UNKNOWN = "UNKNOWN"


class IntentClassifier:
    """
    Classifies user natural language requests into structured intents.
    Uses layered semantic patterns and syntactic cues.
    """

    def __init__(self):
        # Patterns ordered by specificity
        self.rules: List[Tuple[IntentType, List[re.Pattern]]] = [
            # 1. Execute Script
            (IntentType.EXECUTE_SCRIPT, [
                re.compile(r"\b(run|execute|launch|start)\s+(the\s+)?(python\s+script|script|code|program|test)\b", re.I),
                re.compile(r"\b(run|execute)\s+[\w\-./\\]+\.py\b", re.I)
            ]),

            # 2. Summarize Document
            (IntentType.SUMMARIZE_FILE, [
                re.compile(r"\b(summarize|give\s+a\s+summary\s+of|summary\s+for|brief)\s+(the\s+)?(file|document|text)?\b", re.I),
                re.compile(r"\b(what\s+is\s+in|explain\s+contents\s+of)\s+(the\s+)?(file|document)\b", re.I)
            ]),

            # 3. Find Duplicates
            (IntentType.FIND_DUPLICATES, [
                re.compile(r"\b(find|detect|check\s+for|list|show)\s+(duplicate|repeated)\s+files\b", re.I),
                re.compile(r"\bduplicate\s+files\b", re.I)
            ]),

            # 4. Organize Files
            (IntentType.ORGANIZE_FILES, [
                re.compile(r"\b(organize|sort|clean\s+up|categorize|structure)\s+(the\s+)?(files|workspace|folder|directory)\b", re.I)
            ]),

            # 5. Search Text in Files
            (IntentType.SEARCH_TEXT, [
                re.compile(r"\b(search\s+for\s+text|find\s+text|grep|look\s+for\s+text|search\s+inside)\b", re.I),
                re.compile(r"\bwhich\s+files\s+contain\b", re.I)
            ]),

            # 6. Find by Extension
            (IntentType.FIND_BY_EXTENSION, [
                re.compile(r"\b(find|list|show|search)\s+(all\s+)?(?!all\b|my\b|the\b|these\b|those\b)([a-z0-9_-]+)\s+files\b", re.I),
                re.compile(r"\b(find|list|show)\s+(all\s+)?files\s+ending\s+with\b", re.I),
                re.compile(r"\b(find|list|show)\s+(all\s+)?files\s+with\s+(extension|\.[\w]+)\b", re.I)
            ]),

            # 7. Search Files / Directories
            (IntentType.SEARCH_FILES, [
                re.compile(r"\b(search\s+for|look\s+for|where\s+is|find\s+file|find\s+folder|find\s+directory)\b", re.I)
            ]),

            # 8. Append to File
            (IntentType.APPEND_FILE, [
                re.compile(r"\b(append|add)\s+.+\s+(to|into)\s+(the\s+)?file\b", re.I),
                re.compile(r"\bappend\s+to\b", re.I)
            ]),

            # 9. Write to File
            (IntentType.WRITE_FILE, [
                re.compile(r"\b(write|put|insert)\s+.+\s+(in|into|to)\s+(the\s+)?file\b", re.I),
                re.compile(r"\boverwrite\b", re.I)
            ]),

            # 10. Read File
            (IntentType.READ_FILE, [
                re.compile(r"\b(read|cat|display|view|show|print)\s+(the\s+)?contents\s+of\b", re.I),
                re.compile(r"\b(read|cat|display|view|show|print)\s+(the\s+)?(contents\s+of\s+)?(file|document)\b", re.I),
                re.compile(r"\b(show|read)\s+[\w\-./\\]+\.(txt|py|md|json|log|csv)\b", re.I)
            ]),

            # 11. Copy
            (IntentType.COPY_ITEM, [
                re.compile(r"\b(copy|duplicate)\s+(the\s+)?(file|folder|directory)?\b", re.I)
            ]),

            # 12. Move
            (IntentType.MOVE_ITEM, [
                re.compile(r"\b(move|relocate|transfer)\s+(the\s+)?(file|folder|directory)?\b", re.I)
            ]),

            # 13. Rename File / Folder
            (IntentType.RENAME_FILE, [
                re.compile(r"\brename\s+(the\s+)?file\b", re.I),
                re.compile(r"\bchange\s+the\s+name\s+of\s+(the\s+)?file\b", re.I)
            ]),
            (IntentType.RENAME_FOLDER, [
                re.compile(r"\brename\s+(the\s+)?(folder|directory)\b", re.I),
                re.compile(r"\bchange\s+the\s+name\s+of\s+(the\s+)?(folder|directory)\b", re.I)
            ]),

            # 14. Delete File
            (IntentType.DELETE_FILE, [
                re.compile(r"\b(delete|remove|erase|destroy|drop)\s+(the\s+)?file\b", re.I),
                re.compile(r"\b(delete|remove)\s+[\w\-./\\]+\.(txt|py|md|json|log|csv)\b", re.I)
            ]),

            # 15. Delete Folder
            (IntentType.DELETE_FOLDER, [
                re.compile(r"\b(delete|remove|erase|destroy|rmdir)\s+(the\s+)?(folder|directory)\b", re.I)
            ]),

            # 16. Open Item
            (IntentType.OPEN_ITEM, [
                re.compile(r"\b(open|launch)\s+(the\s+)?(file|folder|directory|document|application)\b", re.I)
            ]),

            # 17. Navigate / Change Directory
            (IntentType.NAVIGATE_FOLDER, [
                re.compile(r"\b(navigate\s+to|go\s+to|cd\s+to|enter|switch\s+to|change\s+directory\s+to)\b", re.I),
                re.compile(r"\bgo\s+up(\s+one\s+level|\s+to\s+parent)?\b", re.I)
            ]),

            # 18. List Folder
            (IntentType.LIST_FOLDER, [
                re.compile(r"\b(list|show|display|what\s+is\s+in|dir|ls)\s*(all\s+)?(contents|files|folders|items|in\s+the\s+workspace|in\s+this\s+folder)?\b", re.I),
                re.compile(r"\bwhat\s+(files|folders)\s+(are\s+)?here\b", re.I)
            ]),

            # 19. Create File
            (IntentType.CREATE_FILE, [
                re.compile(r"\b(create|make|generate|build|touch|new|set\s+up|write|add)\s+(a\s+|an\s+)?([a-z0-9_-]+\s+)?file\b", re.I),
                re.compile(r"\b(create|make)\s+(a\s+)?readme\b", re.I),
                re.compile(r"\b(create|make|generate)\s+[\w\-./\\]+\.(py|txt|md|json|csv|log|html|css|js)\b", re.I)
            ]),

            # 20. Create Folder
            (IntentType.CREATE_FOLDER, [
                re.compile(r"\b(create|make|generate|set\s+up|build|mkdir|add|initialize)\s+(a\s+|an\s+|the\s+)?(new\s+)?(folder|directory|dir)\b", re.I),
                re.compile(r"\bmkdir\s+[A-Za-z0-9_\-]+", re.I),
                re.compile(r"\b(create|make)\s+\w+\s+(folders?|directories)\b", re.I),
                re.compile(r"\bi\s+need\s+(a\s+)?(folder|directory)\b", re.I)
            ])
        ]

    def classify(self, text: str) -> IntentType:
        """Determines the primary IntentType for a given single clause."""
        cleaned = text.strip()
        for intent, patterns in self.rules:
            for pattern in patterns:
                if pattern.search(cleaned):
                    return intent

        # Fallback heuristic: check if file or folder creation is implied
        lower = cleaned.lower()
        if any(w in lower for w in ["folder", "directory", "dir"]) and any(w in lower for w in ["create", "make", "setup", "need", "new"]):
            return IntentType.CREATE_FOLDER
        if any(w in lower for w in ["file", "script", "document"]) and any(w in lower for w in ["create", "make", "new", "touch"]):
            return IntentType.CREATE_FILE
        if any(w in lower for w in ["list", "show", "see"]) and any(w in lower for w in ["files", "folders", "contents"]):
            return IntentType.LIST_FOLDER
        if any(w in lower for w in ["delete", "remove", "destroy"]) and any(w in lower for w in ["folder", "directory"]):
            return IntentType.DELETE_FOLDER
        if any(w in lower for w in ["delete", "remove", "erase"]) and any(w in lower for w in ["file", "document"]):
            return IntentType.DELETE_FILE

        return IntentType.UNKNOWN
