import os
import re
import logging
from typing import Set, List
from app.core.protected_files import PROTECTED_FILES
from app.core.skills import Skill, parse_skill_md

logger = logging.getLogger(__name__)

class ResourceLoader:
    def __init__(self, cwd: str):
        self.cwd = os.path.realpath(cwd)

    def discover_agents_md_files(self) -> List[str]:
        """
        Discovers all AGENTS.md file paths starting from self.cwd up to the filesystem root.
        Returns paths ordered from root down to self.cwd (farthest to closest).
        """
        discovered = []
        curr = self.cwd
        while True:
            agents_md_path = os.path.join(curr, "AGENTS.md")
            if os.path.isfile(agents_md_path):
                discovered.append(agents_md_path)
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent

        # Reverse so root-level files come first, and closest cwd-level files come last (taking precedence)
        discovered.reverse()
        return discovered

    def discover_agents_md(self) -> str:
        """
        Discovers all AGENTS.md files from root down to self.cwd.
        Fault-tolerant: handles unreadable or malformed files by logging a warning and continuing.
        Returns concatenated content of all valid AGENTS.md files with closest file taking precedence (listed last).
        """
        contents = []
        file_paths = self.discover_agents_md_files()

        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                    if text.strip():
                        contents.append(text.strip())
            except Exception as e:
                logger.warning("Error reading AGENTS.md at %s: %s", path, e)
                continue

        return "\n\n".join(contents)

    def get_effective_protected_files(self) -> Set[str]:
        """
        Combines default PROTECTED_FILES with any listed in AGENTS.md.
        Expects a format like '- Protected: path/to/file' or similar in AGENTS.md.
        """
        effective = PROTECTED_FILES.copy()
        content = self.discover_agents_md()
        if content:
            matches = re.findall(r"- `([^`]+)`.*protected", content, re.IGNORECASE)
            for m in matches:
                effective.add(m)
        return effective

    def discover_skill_md_files(self) -> List[str]:
        """
        Discovers all SKILL.md file paths starting from self.cwd up to filesystem root,
        as well as within any subdirectories under self.cwd (AUD-016 & AUD-022 pattern).
        Returns paths ordered from root down to self.cwd and subdirectories.
        """
        discovered = []
        # 1. Walk up to filesystem root
        curr = self.cwd
        while True:
            skill_md_path = os.path.join(curr, "SKILL.md")
            if os.path.isfile(skill_md_path) and skill_md_path not in discovered:
                discovered.append(skill_md_path)
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent

        discovered.reverse()

        # 2. Walk down into subdirectories of self.cwd
        for root, _dirs, files in os.walk(self.cwd):
            if "SKILL.md" in files:
                full_path = os.path.join(root, "SKILL.md")
                if full_path not in discovered:
                    discovered.append(full_path)

        return discovered

    def discover_skills(self) -> List[Skill]:
        """
        Discovers and parses all SKILL.md files accessible to self.cwd.
        Fault-tolerant: handles unreadable or malformed files cleanly.
        """
        skills = []
        file_paths = self.discover_skill_md_files()
        for path in file_paths:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        skill = parse_skill_md(content, filepath=path)
                        if skill and (skill.name or skill.instructions):
                            skills.append(skill)
            except Exception as e:
                logger.warning("Error reading SKILL.md at %s: %s", path, e)
                continue
        return skills
