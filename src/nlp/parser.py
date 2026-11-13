"""
Advanced Natural Language Instruction Parser (CAOP Voice OS 2.0).
Parses compound, multi-sentence spoken instructions, resolves contextual references,
anaphora ('it', 'there', 'the last one'), and produces dependency-aware task specifications.
"""

import re
from typing import List, Dict, Any, Optional

from src.nlp.intents import IntentClassifier, IntentType
from src.nlp.entities import EntityExtractor
from src.nlp.context import ContextManager


class ParsedInstruction:
    """Represents an atomic parsed sub-operation."""

    def __init__(
        self,
        step_id: int,
        intent: IntentType,
        raw_clause: str,
        target_name: Optional[str] = None,
        destination: Optional[str] = None,
        content: Optional[str] = None,
        topic_prompt: Optional[str] = None,
        extension: Optional[str] = None,
        query: Optional[str] = None,
        new_name: Optional[str] = None,
        depends_on: Optional[int] = None
    ):
        self.step_id = step_id
        self.intent = intent
        self.raw_clause = raw_clause
        self.target_name = target_name
        self.destination = destination
        self.content = content
        self.topic_prompt = topic_prompt
        self.extension = extension
        self.query = query
        self.new_name = new_name
        self.depends_on = depends_on

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "intent": self.intent.value,
            "raw_clause": self.raw_clause,
            "target_name": self.target_name,
            "destination": self.destination,
            "content": self.content,
            "topic_prompt": self.topic_prompt,
            "extension": self.extension,
            "query": self.query,
            "new_name": self.new_name,
            "depends_on": self.depends_on
        }

    def __repr__(self) -> str:
        return f"<ParsedInstruction #{self.step_id} {self.intent.value} target={self.target_name} dest={self.destination}>"


class InstructionParser:
    """
    Parses conversational utterances, multi-sentence paragraphs, and compound instructions.
    """

    def __init__(self, context_manager: Optional[ContextManager] = None):
        self.classifier = IntentClassifier()
        self.extractor = EntityExtractor()
        self.context = context_manager or ContextManager()

    def split_compound_instruction(self, utterance: str) -> List[str]:
        """
        Splits multi-sentence and compound instructions into discrete actionable clauses.
        Supports periods, semicolons, 'then', 'after that', 'and create', etc.
        """
        cleaned = utterance.strip()

        # Remove trailing reporting polite phrases like "and tell me exactly what you created"
        cleaned = re.sub(r"(?:,\s*)?(?:and\s+)?tell\s+me\s+(?:exactly\s+)?(?:what\s+you\s+(?:have\s+)?created|what\s+you\s+did)\.?$", "", cleaned, flags=re.I).strip()

        # 1. Normalize periods followed by capital letters or conversational markers
        sentences = re.split(r"\.\s+(?=[A-Z0-9\"'a-z])", cleaned)

        clauses = []
        for sent in sentences:
            s_clean = sent.strip().rstrip(".")
            if not s_clean:
                continue

            # Handle discourse markers at start of sentence: "Actually, move it back" -> "move it back"
            s_clean = re.sub(r"^(?:actually|wait|hold\s+on|no|please|hey\s+assistant),?\s+", "", s_clean, flags=re.I).strip()

            # Do not split if the sentence starts with a preposition phrase like "Inside it, create..."
            if re.match(r"^(inside|in|into|under)\s+(?:it|that|the\s+[\w\s]+),\s+", s_clean, re.I):
                s_clean = re.sub(r"^(inside|in|into|under\s+(?:it|that|the\s+[\w\s]+)),\s+", r"\1 ", s_clean, flags=re.I)

            # Split on markers: ', then ', '; ', 'after that, ', 'and create...'
            pattern = r"(?:,\s*(?:and\s+)?then\s+|(?:and\s+)?then\s+|;\s*|,\s*after\s+that,?\s*|after\s+that,?\s*|,\s*and\s+(?=(?:create|make|generate|build|delete|remove|open|read|write|organize|move))|\s+and\s+(?=(?:create|make|generate|build|delete|remove|open|read|write|organize|move)))"

            raw_parts = re.split(pattern, s_clean, flags=re.I)
            for p in raw_parts:
                p_strip = p.strip().strip(",")
                if not p_strip:
                    continue

                # Strip discourse prefixes inside clauses too
                p_strip = re.sub(r"^(?:actually|wait|no|please),?\s+", "", p_strip, flags=re.I).strip()

                # Check if there is an internal comma separating distinct action verbs
                sub_parts = re.split(r",\s+(?=(?:create|make|generate|build|delete|remove|read|write|append|open|move|organize)\b)", p_strip, flags=re.I)

                buffer = ""
                for sp in sub_parts:
                    sp_clean = sp.strip().strip(",")
                    if not sp_clean:
                        continue
                    if re.match(r"^(inside|in|into|under)\s+(it|that|there|\w+)", sp_clean, re.I) and not any(v in sp_clean.lower() for v in ["create", "make", "delete", "read", "write", "open", "move", "organize"]):
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
        Parses utterance into an ordered list of ParsedInstructions.
        Maintains step-wise context and resolves pronouns and relative locations.
        """
        # Handle special conversational correction:
        # "Actually, don't delete those. Move them into a Backup folder instead."
        if re.search(r"\b(?:don't|do\s+not)\s+(?:delete|remove)\s+(?:those|them)\b", utterance, re.I):
            dest_match = re.search(r"\binto\s+(?:a\s+)?([A-Za-z0-9_\-]+)\s+(?:folder)?", utterance, re.I)
            dest_name = dest_match.group(1).strip() if dest_match else "Backup"
            targets = self.context.get_last_targets()
            return [
                ParsedInstruction(
                    step_id=1,
                    intent=IntentType.CREATE_FOLDER,
                    raw_clause=f"Create folder {dest_name}",
                    target_name=dest_name
                ),
                ParsedInstruction(
                    step_id=2,
                    intent=IntentType.MOVE_ITEM,
                    raw_clause=utterance,
                    target_name="those",
                    destination=dest_name,
                    depends_on=1
                )
            ]

        clauses = self.split_compound_instruction(utterance)
        instructions: List[ParsedInstruction] = []

        step_id = 1
        current_focus_folder = self.context.get_last_folder()
        last_step_folder: Optional[str] = None
        turn_created_folders: List[str] = []

        for clause in clauses:
            intent = self.classifier.classify(clause)
            entities = self.extractor.extract_all(clause)

            names = entities["names"]
            destination = entities["destination"]
            content = entities["content"]
            topic = entities["topic_prompt"]
            extension = entities["extension"]
            query = entities["query"]
            rename_src = entities["rename_source"]
            rename_dst = entities["rename_dest"]

            # Handle destination resolution ('inside it', 'in it', 'there')
            if destination == "it":
                if last_step_folder:
                    destination = last_step_folder
                elif current_focus_folder:
                    destination = current_focus_folder
                else:
                    destination = self.context.get_last_folder()

            # Handle 'the last one'
            if names and names[0] == "the last one":
                ref = self.context.resolve_reference("the last one")
                if ref:
                    names = [ref]
                elif turn_created_folders:
                    names = [turn_created_folders[-1]]

            # Handle rename pair extraction
            new_name = rename_dst
            if rename_src:
                names = [rename_src]

            # Handle organize target extraction: "organize the College folder properly" -> target="College"
            if intent == IntentType.ORGANIZE_FILES:
                org_match = re.search(r"\borganize\s+(?:the\s+)?([A-Za-z0-9_\-]+)\s+(?:folder|directory)?", clause, re.I)
                if org_match:
                    cand = org_match.group(1).strip()
                    if cand.lower() not in ["properly", "cleanly", "files", "workspace"]:
                        names = [cand]

            # Handle multiple targets in single clause (e.g. "create three folders inside it called AI, SNA and Projects")
            if len(names) > 1 and intent in [IntentType.CREATE_FOLDER, IntentType.CREATE_FILE]:
                for single_name in names:
                    clean_name = self._ensure_proper_extension(single_name, intent, extension)
                    dep = (step_id - 1) if destination and (destination == last_step_folder) else None

                    inst = ParsedInstruction(
                        step_id=step_id,
                        intent=intent,
                        raw_clause=clause,
                        target_name=clean_name,
                        destination=destination,
                        content=content,
                        topic_prompt=topic,
                        extension=extension,
                        query=query,
                        new_name=new_name,
                        depends_on=dep
                    )
                    instructions.append(inst)
                    if intent == IntentType.CREATE_FOLDER:
                        last_step_folder = clean_name
                        turn_created_folders.append(clean_name)
                    step_id += 1
                continue

            target_name = names[0] if names else None
            if target_name:
                target_name = self._ensure_proper_extension(target_name, intent, extension)

            # Dependency linking
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
                topic_prompt=topic,
                extension=extension,
                query=query,
                new_name=new_name,
                depends_on=dep
            )
            instructions.append(inst)

            if intent == IntentType.CREATE_FOLDER and target_name:
                last_step_folder = target_name
                turn_created_folders.append(target_name)
                if not current_focus_folder:
                    current_focus_folder = target_name

            step_id += 1

        return instructions

    def _ensure_proper_extension(self, name: str, intent: IntentType, extension: Optional[str]) -> str:
        if intent == IntentType.CREATE_FILE:
            if "." not in name:
                if extension:
                    return f"{name}{extension}"
                elif "python" in name.lower() or "script" in name.lower():
                    return f"{name}.py"
                else:
                    return f"{name}.txt"
        return name
