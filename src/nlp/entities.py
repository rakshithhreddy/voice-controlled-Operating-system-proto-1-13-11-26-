"""
Enhanced Entity Extractor (CAOP Voice OS 2.0).
Extracts targets, parent destinations, topics/prompts for content generation,
multiple folder lists, rename parameters, and relative location phrases.
"""

import re
from typing import Dict, Any, List, Optional, Tuple


class EntityExtractor:
    """
    Extracts semantic parameters and entities required for OS task execution.
    """

    def __init__(self):
        self.ext_map = {
            "python": ".py",
            "py": ".py",
            "text": ".txt",
            "txt": ".txt",
            "markdown": ".md",
            "md": ".md",
            "json": ".json",
            "csv": ".csv",
            "html": ".html",
            "css": ".css",
            "javascript": ".js",
            "js": ".js",
            "log": ".log"
        }

    def extract_all(self, text: str) -> Dict[str, Any]:
        """Runs all entity extraction strategies on the input text."""
        content, topic = self.extract_content_and_topic(text)

        # When extracting names, strip out content phrases to prevent misidentification
        text_for_names = text
        if content:
            text_for_names = re.sub(r"\b(?:with\s+content|containing|saying|text)\s+['\"][^'\"]+['\"]", "", text_for_names, flags=re.I)
            text_for_names = re.sub(r"\b(?:with\s+content|containing|saying)\s+[^\n]+$", "", text_for_names, flags=re.I)
        if topic:
            text_for_names = re.sub(r"\b(?:explaining|about|demonstrating)\s+[^\n]+$", "", text_for_names, flags=re.I)

        rename_source, rename_dest = self.extract_rename_pair(text)

        result: Dict[str, Any] = {
            "raw_text": text,
            "names": self.extract_names(text_for_names),
            "destination": self.extract_destination(text_for_names),
            "content": content,
            "topic_prompt": topic,
            "extension": self.extract_extension(text),
            "query": self.extract_search_query(text_for_names),
            "rename_source": rename_source,
            "rename_dest": rename_dest
        }
        return result

    def extract_names(self, text: str) -> List[str]:
        """Extracts file or folder names."""
        names: List[str] = []

        # 1. Direct filename or filepath pattern
        file_matches = re.findall(r"(?:^|[\s\"'])((?:(?:\.\.|\.)[/\\])*[A-Za-z0-9_\-./\\]+\.[a-zA-Z0-9]{1,5})(?:$|[\s\"'])", text)
        if file_matches:
            for fm in file_matches:
                clean_fm = fm.strip()
                if clean_fm not in names:
                    names.append(clean_fm)
            return names

        # 2. 'readme'
        if re.search(r"\breadme(\s+file)?\b", text, re.I):
            names.append("README.md")
            return names

        # 3. Quoted names
        quotes = re.findall(r"['\"]([^'\"]+)['\"]", text)
        if quotes:
            for q in quotes:
                clean_q = q.strip()
                if clean_q and clean_q.lower() not in ["it", "that", "this"]:
                    names.append(clean_q)
            if names:
                return names

        # 4. 'called / named / titled X, Y, and Z'
        list_match = re.search(
            r"\b(?:called|named|titled)\s+([A-Za-z0-9_.\-\s,]+?)(?:\s+(?:inside|in|into|with|then|and\s+create|and\s+make|containing|explaining)|$)",
            text,
            re.I
        )
        if list_match:
            raw_list = list_match.group(1).strip()
            tokens = re.split(r",\s*|\s+and\s+", raw_list)
            for tok in tokens:
                clean_tok = tok.strip()
                clean_tok = re.sub(r"^(?:and|or|\&)\s+", "", clean_tok, flags=re.I).strip()
                if clean_tok and clean_tok.lower() not in ["it", "that", "another", "a", "an", "the"]:
                    names.append(clean_tok)
            if names:
                return names

        # 5. 'the last one'
        if re.search(r"\bthe\s+last\s+one\b", text, re.I):
            names.append("the last one")
            return names

        # 6. 'folder/directory/file [name]'
        single_match = re.search(
            r"\b(?:folder|directory|file|script)\s+([A-Za-z0-9_\-]+)\b",
            text,
            re.I
        )
        if single_match:
            cand = single_match.group(1).strip()
            if cand.lower() not in ["called", "named", "inside", "in", "it", "that", "here"]:
                names.append(cand)

        return names

    def extract_destination(self, text: str) -> Optional[str]:
        """Extracts destination folder or parent container."""
        # Deictics: 'it', 'there', 'that'
        if re.search(r"\b(inside|in|into|under)\s+(it|there|that\s+folder|that\s+directory)\b", text, re.I):
            return "it"
        if re.search(r"\b(there|in\s+there|into\s+there)\b", text, re.I):
            return "it"

        # 'into / in / inside <folder>'
        match = re.search(
            r"\b(?:into|inside|in)\s+(?:the\s+)?([A-Za-z0-9_\-\s]+?)(?:\s+(?:folder|directory)|$|\s+create|\s+then|\s+and|\s+explaining|\s+containing)",
            text,
            re.I
        )
        if match:
            dest = match.group(1).strip()
            dest = re.sub(r"^(the|a|an)\s+", "", dest, flags=re.I).strip()
            if dest and dest.lower() not in ["it", "there", "here", "this"]:
                return dest

        return None

    def extract_content_and_topic(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts literal content or educational topic prompts:
        e.g., 'explaining social network analysis', 'containing a working calculator program'
        """
        content = None
        topic = None

        # Quoted literal content
        quoted = re.search(r"\b(?:with\s+content|containing|saying|text)\s+['\"]([^'\"]+)['\"]", text, re.I)
        if quoted:
            content = quoted.group(1)

        # Unquoted topic prompt: 'explaining X' or 'containing X'
        topic_match = re.search(r"\b(?:explaining|about|containing|demonstrating)\s+(?:the\s+)?(.+)$", text, re.I)
        if topic_match:
            topic = topic_match.group(1).strip()

        return content, topic

    def extract_rename_pair(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extracts source and target names for rename instructions."""
        match = re.search(r"\brename\s+(?:the\s+)?(?:folder\s+|file\s+)?(['\"A-Za-z0-9_\-.\s]+?)\s+to\s+(['\"A-Za-z0-9_\-.\s]+)", text, re.I)
        if match:
            src = match.group(1).strip().strip("'\"")
            dst = match.group(2).strip().strip("'\"")
            return src, dst
        return None, None

    def extract_extension(self, text: str) -> Optional[str]:
        ext_match = re.search(r"\b(\.[a-zA-Z0-9]+)\b", text)
        if ext_match:
            return ext_match.group(1).lower()

        for word, ext in self.ext_map.items():
            if re.search(rf"\b{word}\s+(files?|scripts?|documents?)\b", text, re.I):
                return ext

        return None

    def extract_search_query(self, text: str) -> Optional[str]:
        quoted = re.search(r"\b(?:for|named|called|containing)\s+['\"]([^'\"]+)['\"]", text, re.I)
        if quoted:
            return quoted.group(1).strip()

        match = re.search(r"\b(?:search\s+for|look\s+for|find|related\s+to)\s+([A-Za-z0-9_.\-*]+)\b", text, re.I)
        if match:
            cand = match.group(1).strip()
            if cand.lower() not in ["file", "files", "folder", "folders", "all"]:
                return cand

        return None
