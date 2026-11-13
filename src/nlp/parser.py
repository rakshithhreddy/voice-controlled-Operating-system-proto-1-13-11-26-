"""
NLP Parser Module.
Decomposes compound spoken commands into discrete operational steps,
resolves dependencies and context, and creates structured execution specs.
"""

import re
from typing import List, Dict, Any, Optional

from src.nlp.intents import IntentClassifier, IntentType
from src.nlp.entities import EntityExtractor
from src.nlp.context import ContextManager


class ParsedInstruction:
    """Represents a single parsed sub-operation."""

    def __init__(
        self,
        step_id: int,
        intent: IntentType,
        raw_clause: str,
        target_name: Optional[str] = None,
        destination: Optional[str] = None,
        content: Optional[str] = None,
        extension: Optional[str] = None,
        query: Optional[str] = None,
        depends_on: Optional[int] = None
    ):
        self.step_id = step_id
        self.intent = intent
        self.raw_clause = raw_clause
        self.target_name = target_name
        self.destination = destination
        self.content = content
        self.extension = extension
        self.query = query
        self.depends_on = depends_on

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "intent": self.intent.value,
            "raw_clause": self.raw_clause,
            "target_name": self.target_name,
            "destination": self.destination,
            "content": self.content,
            "extension": self.extension,
            "query": self.query,
            "depends_on": self.depends_on
        }

    def __repr__(self) -> str:
        return f"<ParsedInstruction step={self.step_id} intent={self.intent.value} target={self.target_name} dest={self.destination}>"


class InstructionParser:
    """
    Parses natural English utterances, splits multi-intent sentences,
    and maps them to sequential instructions with contextual grounding.
    """

    def __init__(self, context_manager: Optional[ContextManager] = None):
        self.classifier = IntentClassifier()
        self.extractor = EntityExtractor()
        self.context = context_manager or ContextManager()

    def split_compound_instruction(self, utterance: str) -> List[str]:
        """
        Splits a compound sentence into separate actionable clauses.
        Examples:
        - "Create folder A, then create folder B inside it, and make file C"
        - "Create folder A and make folder B"
        - "Inside it, create a folder called College" (keeps together)
        """
        cleaned = utterance.strip().rstrip(".")

        # Do not split if the sentence starts with a preposition like "Inside it, create..."
        if re.match(r"^(inside|in|into|under)\s+(?:it|that|the\s+[\w\s]+),\s+", cleaned, re.I):
            cleaned = re.sub(r"^(inside|in|into|under\s+(?:it|that|the\s+[\w\s]+)),\s+", r"\1 ", cleaned, flags=re.I)

        # Split on sequencing markers:
        # ', and then ', ', then ', ' and then ', ' then ', '; ', ', and create ', ', and make '
        pattern = r"(?:,\s*(?:and\s+)?then\s+|(?:and\s+)?then\s+|;\s*|,\s*and\s+(?=(?:create|make|generate|build|delete|remove|open|read|write))|\s+and\s+(?=(?:create|make|generate|build|delete|remove|open|read|write)))"

        raw_parts = re.split(pattern, cleaned, flags=re.I)
        clauses = []
        for p in raw_parts:
            p_strip = p.strip().strip(",")
            if not p_strip:
                continue

            # Check if there is an internal comma separating distinct action verbs
            sub_parts = re.split(r",\s+(?=(?:create|make|generate|build|delete|remove|read|write|append|open)\b)", p_strip, flags=re.I)
            
            # Recombine any dangling preposition phrases (e.g. "Inside it") with following clause
            buffer = ""
            for sp in sub_parts:
                sp_clean = sp.strip().strip(",")
                if not sp_clean:
                    continue
                if re.match(r"^(inside|in|into|under)\s+(it|that|there|\w+)", sp_clean, re.I) and not any(v in sp_clean.lower() for v in ["create", "make", "delete", "read", "write", "open"]):
                    buffer = sp_clean + " "
                else:
                    clauses.append((buffer + sp_clean).strip())
                    buffer = ""
            if buffer:
                if clauses:
                    clauses[-1] = (clauses[-1] + " " + buffer).strip()
                else:
                    clauses.append(buffer.strip())

        return clauses if clauses else [utterance]

    def parse(self, utterance: str) -> List[ParsedInstruction]:
        """
        Processes a full user utterance and returns an ordered list of ParsedInstructions.
        Maintains an internal context for resolving references within the same instruction
        as well as from previous turns.
        """
        clauses = self.split_compound_instruction(utterance)
        instructions: List[ParsedInstruction] = []

        step_id = 1
        current_focus_folder = self.context.get_last_folder()
        last_step_folder: Optional[str] = None

        for clause in clauses:
            intent = self.classifier.classify(clause)
            entities = self.extractor.extract_all(clause)

            names = entities["names"]
            destination = entities["destination"]
            content = entities["content"]
            extension = entities["extension"]
            query = entities["query"]

            # Handle destination resolution ('inside it', 'in it', 'into it')
            if destination == "it":
                # First check if the immediately preceding step created a folder
                if last_step_folder:
                    destination = last_step_folder
                elif current_focus_folder:
                    destination = current_focus_folder
                else:
                    destination = self.context.get_last_folder()
            elif not destination and last_step_folder and intent == IntentType.CREATE_FILE:
                # If a file is created right after a folder in the same compound sentence,
                # place it into the created folder by default
                destination = last_step_folder

            # Handle multi-item folder or file creation in a single clause
            # e.g., "create three folders inside it called SNA, AI, and Projects"
            if len(names) > 1 and intent in [IntentType.CREATE_FOLDER, IntentType.CREATE_FILE]:
                for single_name in names:
                    # Clean single name
                    clean_name = self._ensure_proper_extension(single_name, intent, extension)
                    dep = (step_id - 1) if destination and (destination == last_step_folder) else None

                    inst = ParsedInstruction(
                        step_id=step_id,
                        intent=intent,
                        raw_clause=clause,
                        target_name=clean_name,
                        destination=destination,
                        content=content,
                        extension=extension,
                        query=query,
                        depends_on=dep
                    )
                    instructions.append(inst)
                    if intent == IntentType.CREATE_FOLDER:
                        last_step_folder = clean_name
                    step_id += 1
                continue

            target_name = names[0] if names else None
            if target_name:
                target_name = self._ensure_proper_extension(target_name, intent, extension)

            # Check dependency on previous step
            dep = None
            if destination and destination == last_step_folder:
                dep = step_id - 1

            inst = ParsedInstruction(
                step_id=step_id,
                intent=intent,
                raw_clause=clause,
                target_name=target_name,
                destination=destination,
                content=content,
                extension=extension,
                query=query,
                depends_on=dep
            )
            instructions.append(inst)

            if intent == IntentType.CREATE_FOLDER and target_name:
                last_step_folder = target_name
                if not current_focus_folder:
                    current_focus_folder = target_name

            step_id += 1

        return instructions

    def _ensure_proper_extension(self, name: str, intent: IntentType, extension: Optional[str]) -> str:
        """Appends appropriate extension if file creation specifies an extension."""
        if intent == IntentType.CREATE_FILE:
            if "." not in name:
                if extension:
                    return f"{name}{extension}"
                elif "python" in name.lower() or "script" in name.lower():
                    return f"{name}.py"
                else:
                    return f"{name}.txt"
        return name
