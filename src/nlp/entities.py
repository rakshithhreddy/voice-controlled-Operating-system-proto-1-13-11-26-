"""
Entity Extraction Module.
Extracts named entities such as filenames, foldernames, extensions,
target locations, and file content from natural language text.
"""

import re
from typing import Dict, Any, List, Optional


class EntityExtractor:
    """
    Extracts semantic parameters and entities required for OS execution.
    """

    def __init__(self):
        # Known common extensions
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
        content = self.extract_content(text)
        
        # When extracting names, strip out the content phrase so quoted content is not confused with filenames
        text_for_names = text
        if content:
            text_for_names = re.sub(r"\b(?:with\s+content|containing|saying|text)\s+['\"][^'\"]+['\"]", "", text_for_names, flags=re.I)
            text_for_names = re.sub(r"\b(?:with\s+content|containing|saying)\s+[^\n]+$", "", text_for_names, flags=re.I)

        result: Dict[str, Any] = {
            "raw_text": text,
            "names": self.extract_names(text_for_names),
            "destination": self.extract_destination(text_for_names),
            "content": content,
            "extension": self.extract_extension(text),
            "query": self.extract_search_query(text_for_names)
        }
        return result

    def extract_names(self, text: str) -> List[str]:
        """
        Extracts one or more file/folder names specified in the instruction.
        Handles:
        - Direct filename patterns: test.txt, calculator.py, README.md
        - Quoted strings: 'College Projects', "calculator.py"
        - 'called X, Y, and Z' or 'named X, Y, and Z'
        - 'folder called X'
        - 'file named X'
        """
        names: List[str] = []

        # 1. Direct filename or filepath patterns (e.g., calculator.py, test.txt, ../../secret.txt)
        file_matches = re.findall(r"(?:^|[\s\"'])((?:(?:\.\.|\.)[/\\])*[A-Za-z0-9_\-./\\]+\.[a-zA-Z0-9]{1,5})(?:$|[\s\"'])", text)
        if file_matches:
            for fm in file_matches:
                clean_fm = fm.strip()
                if clean_fm not in names:
                    names.append(clean_fm)
            return names

        # 2. 'readme' special case
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
            r"\b(?:called|named|titled)\s+([A-Za-z0-9_.\-\s,]+?)(?:\s+(?:inside|in|into|with|then|and\s+create|and\s+make)|$)",
            text,
            re.I
        )
        if list_match:
            raw_list = list_match.group(1).strip()
            # If it has commas or 'and', split into multiple names
            # e.g., 'SNA, AI, and Projects'
            tokens = re.split(r",\s*|\s+and\s+", raw_list)
            for tok in tokens:
                clean_tok = tok.strip()
                # Remove leading 'and ' if any left over
                clean_tok = re.sub(r"^(?:and|or|\&)\s+", "", clean_tok, flags=re.I).strip()
                # Exclude noise words
                if clean_tok and clean_tok.lower() not in ["it", "that", "another", "a", "an", "the"]:
                    names.append(clean_tok)
            if names:
                return names

        # 5. Fallback pattern: 'folder/directory/file [name]'
        single_match = re.search(
            r"\b(?:folder|directory|file|script)\s+([A-Za-z0-9_\-]+)\b",
            text,
            re.I
        )
        if single_match:
            cand = single_match.group(1).strip()
            if cand.lower() not in ["called", "named", "inside", "in", "it", "that"]:
                names.append(cand)

        return names

    def extract_destination(self, text: str) -> Optional[str]:
        """
        Extracts destination path or parent folder container.
        Matches:
        - 'inside <folder>'
        - 'in <folder>'
        - 'to <folder>'
        - 'under <folder>'
        - 'inside it' / 'in it' (returns 'it')
        """
        # Inside it / in it
        if re.search(r"\b(inside|in|into|under)\s+(it|there|that\s+folder|that\s+directory)\b", text, re.I):
            return "it"

        # Quoted destination
        quoted = re.search(r"\b(?:inside|in|into|under|to)\s+['\"]([^'\"]+)['\"]", text, re.I)
        if quoted:
            return quoted.group(1).strip()

        # Named destination: 'inside folder called X' or 'inside the X folder' or 'inside X'
        match = re.search(
            r"\b(?:inside|into|under)\s+(?:the\s+)?(?:folder\s+(?:called|named)\s+)?([A-Za-z0-9_\-\s]+?)(?:\s+(?:folder|directory)|$|\s+then|\s+and)",
            text,
            re.I
        )
        if match:
            dest = match.group(1).strip()
            dest = re.sub(r"^(the|a|an)\s+", "", dest, flags=re.I).strip()
            if dest and dest.lower() not in ["it", "there"]:
                return dest

        # 'in <folder> folder'
        match_in = re.search(r"\bin\s+(?:the\s+)?([A-Za-z0-9_\-]+)\s+(?:folder|directory)\b", text, re.I)
        if match_in:
            return match_in.group(1).strip()

        return None

    def extract_content(self, text: str) -> Optional[str]:
        """
        Extracts content to be written or appended to a file.
        e.g., 'with content "Hello World"', 'containing print(1)', 'saying Hello'
        """
        quoted = re.search(r"\b(?:with\s+content|containing|saying|text)\s+['\"]([^'\"]+)['\"]", text, re.I)
        if quoted:
            return quoted.group(1)

        match = re.search(r"\b(?:with\s+content|containing|saying)\s+([^\n]+)$", text, re.I)
        if match:
            return match.group(1).strip()

        return None

    def extract_extension(self, text: str) -> Optional[str]:
        """
        Extracts file extension or file category.
        e.g., 'python files', 'txt files', '.md'
        """
        ext_match = re.search(r"\b(\.[a-zA-Z0-9]+)\b", text)
        if ext_match:
            return ext_match.group(1).lower()

        for word, ext in self.ext_map.items():
            if re.search(rf"\b{word}\s+(files?|scripts?|documents?)\b", text, re.I):
                return ext

        return None

    def extract_search_query(self, text: str) -> Optional[str]:
        """
        Extracts search term for file searching or text grep.
        """
        # Quoted query
        quoted = re.search(r"\b(?:for|search\s+for|named|called|containing)\s+['\"]([^'\"]+)['\"]", text, re.I)
        if quoted:
            return quoted.group(1).strip()

        match = re.search(r"\b(?:search\s+for|look\s+for|find)\s+([A-Za-z0-9_.\-*]+)\b", text, re.I)
        if match:
            cand = match.group(1).strip()
            if cand.lower() not in ["file", "files", "folder", "folders", "all", "duplicate"]:
                return cand

        return None
