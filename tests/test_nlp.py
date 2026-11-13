"""
Unit tests for NLP Classifier, Entity Extractor, Parser, and Context Memory.
"""

import pytest
from src.nlp.intents import IntentClassifier, IntentType
from src.nlp.entities import EntityExtractor
from src.nlp.context import ContextManager
from src.nlp.parser import InstructionParser


def test_intent_synonym_variations():
    classifier = IntentClassifier()

    # Different expressions of the same intent: CREATE_FOLDER
    phrases = [
        "Make a new folder called Games",
        "Create a Games directory",
        "I need a folder named Games",
        "Set up a new directory called Games",
        "Build a folder titled Games",
        "mkdir Games"
    ]
    for p in phrases:
        assert classifier.classify(p) == IntentType.CREATE_FOLDER, f"Failed for phrase: '{p}'"


def test_intent_classification_types():
    classifier = IntentClassifier()
    assert classifier.classify("Create a file called notes.txt") == IntentType.CREATE_FILE
    assert classifier.classify("Delete the file test.py") == IntentType.DELETE_FILE
    assert classifier.classify("Delete the folder OldStuff") == IntentType.DELETE_FOLDER
    assert classifier.classify("Read the contents of report.txt") == IntentType.READ_FILE
    assert classifier.classify("List all files in this directory") == IntentType.LIST_FOLDER
    assert classifier.classify("Run the python script calculator.py") == IntentType.EXECUTE_SCRIPT
    assert classifier.classify("Organize the files in my workspace") == IntentType.ORGANIZE_FILES
    assert classifier.classify("Find duplicate files") == IntentType.FIND_DUPLICATES
    assert classifier.classify("Summarize the file readme.md") == IntentType.SUMMARIZE_FILE


def test_entity_extraction():
    extractor = EntityExtractor()

    # Single folder
    e1 = extractor.extract_all("Make a folder called College Projects")
    assert "College Projects" in e1["names"]

    # Multiple folders
    e2 = extractor.extract_all("create three folders inside it called SNA, AI, and Projects")
    assert "SNA" in e2["names"]
    assert "AI" in e2["names"]
    assert "Projects" in e2["names"]
    assert e2["destination"] == "it"

    # File with content
    e3 = extractor.extract_all("Create a file called info.txt with content 'Secret Data'")
    assert "info.txt" in e3["names"]
    assert e3["content"] == "Secret Data"

    # Search query
    e4 = extractor.extract_all("Search for 'quarterly report'")
    assert e4["query"] == "quarterly report"


def test_compound_instruction_splitting():
    parser = InstructionParser()
    s = "Create a folder called College Projects, create another folder inside it called Python, and create a Python file called calculator.py."
    clauses = parser.split_compound_instruction(s)
    assert len(clauses) == 3


def test_context_anaphora_resolution():
    cm = ContextManager()
    cm.update_context(folder="College Projects", success=True)
    assert cm.resolve_pronoun("inside it") == "College Projects"
    assert cm.resolve_pronoun("in that folder") == "College Projects"
    assert cm.resolve_pronoun("there") == "College Projects"
