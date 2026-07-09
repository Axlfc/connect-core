import os
import re
from typing import Set
from app.core.protected_files import PROTECTED_FILES

class ResourceLoader:
    def __init__(self, cwd: str):
        self.cwd = os.path.realpath(cwd)

    def discover_agents_md(self) -> str:
        """
        Looks for AGENTS.md in the root of cwd.
        If it exists, returns its content.
        """
        agents_md_path = os.path.join(self.cwd, "AGENTS.md")
        if os.path.exists(agents_md_path):
            try:
                with open(agents_md_path, "r") as f:
                    return f.read()
            except Exception:
                return ""
        return ""

    def get_effective_protected_files(self) -> Set[str]:
        """
        Combines default PROTECTED_FILES with any listed in AGENTS.md.
        Expects a format like '- Protected: path/to/file' or similar in AGENTS.md,
        but for Phase 1 we will just look for lines that look like paths
        in a specific section or just use the defaults if not easily parsable.
        Actually, the requirement says "if ResourceLoader finds a different list in AGENTS.md...
        it has priority... but never reduce".
        Let's implement a simple parser for AGENTS.md for protected files.
        """
        effective = PROTECTED_FILES.copy()
        content = self.discover_agents_md()
        if content:
            # Simple heuristic: look for lines starting with - and containing a path
            # or specifically in a "Protected Files" section
            # For now, let's look for: - `path/to/file` (protected)
            # or just any line with 'protected' and a backticked path
            matches = re.findall(r"- `([^`]+)`.*protected", content, re.IGNORECASE)
            for m in matches:
                effective.add(m)
        return effective
