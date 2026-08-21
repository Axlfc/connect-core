from pathlib import Path
from typing import Iterable, List, Optional, Set, Union
import fnmatch

try:
    import pathspec
    HAS_PATHSPEC = True
except ImportError:
    HAS_PATHSPEC = False

from app.core.protected_files import PROTECTED_FILES

DEFAULT_EXCLUDE_PATTERNS = [
    ".git",
    ".git/*",
    ".git/**",
    ".env",
    ".env.*",
    "node_modules",
    "node_modules/*",
    "node_modules/**",
    "*.pyc",
    "__pycache__",
    "__pycache__/*",
    "__pycache__/**",
]

class FSObservationPolicy:
    """
    Proactive Observation Policy for File System tools.
    Filters out hidden, protected, or ignored files/directories before LLM tools observe or access them.
    """

    def __init__(
        self,
        cwd: Union[str, Path],
        protected_files: Optional[Union[Set[str], List[str]]] = None,
        custom_patterns: Optional[List[str]] = None,
    ):
        self.cwd = Path(cwd).resolve()

        # Merge protected files from module defaults + parameter
        self.protected_files: Set[str] = set(PROTECTED_FILES)
        if protected_files:
            self.protected_files.update(protected_files)

        # Collect pattern rules
        patterns: List[str] = list(DEFAULT_EXCLUDE_PATTERNS)
        if custom_patterns:
            patterns.extend(custom_patterns)

        # Read .gitignore if present in cwd
        gitignore_path = self.cwd / ".gitignore"
        if gitignore_path.exists() and gitignore_path.is_file():
            try:
                with gitignore_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str and not line_str.startswith("#"):
                            patterns.append(line_str)
            except Exception:
                pass

        self.patterns = patterns

        if HAS_PATHSPEC:
            self.spec = pathspec.PathSpec.from_lines("gitignore", self.patterns)
        else:
            self.spec = None

    def is_hidden(self, target: Union[str, Path]) -> bool:
        """
        Determines whether a file or directory should be hidden/masked from observation.
        Guards against Path Traversal by requiring target to be contained within self.cwd.
        """
        try:
            target_path = Path(target)
            if not target_path.is_absolute():
                resolved_target = (self.cwd / target_path).resolve()
            else:
                resolved_target = target_path.resolve()
        except Exception:
            return True

        # Check path traversal / boundary
        try:
            rel_target = resolved_target.relative_to(self.cwd)
        except ValueError:
            # Target escapes workspace cwd
            return True

        # Check if target is cwd itself
        if rel_target == Path("."):
            return False

        rel_target_str = rel_target.as_posix()

        # Check protected files
        for pf in self.protected_files:
            pf_norm = Path(pf).as_posix()
            if rel_target_str == pf_norm or rel_target_str.startswith(pf_norm.rstrip("/") + "/"):
                return True

        # Check exclusion patterns using pathspec or fnmatch fallback
        if self.spec:
            # Check rel_target_str and directory forms
            if self.spec.match_file(rel_target_str):
                return True
            if resolved_target.is_dir() and self.spec.match_file(f"{rel_target_str}/"):
                return True
            # Also check if any parent component matches
            for parent in rel_target.parents:
                if parent != Path("."):
                    parent_str = parent.as_posix()
                    if self.spec.match_file(parent_str) or self.spec.match_file(f"{parent_str}/"):
                        return True
        else:
            # Fallback fnmatch check on all parent components and current path
            parts = rel_target.parts
            accumulated = ""
            for part in parts:
                accumulated = f"{accumulated}/{part}" if accumulated else part
                for pat in self.patterns:
                    clean_pat = pat.rstrip("/")
                    if fnmatch.fnmatch(part, clean_pat) or fnmatch.fnmatch(accumulated, clean_pat):
                        return True

        return False

    def filter_paths(self, paths: Iterable[Union[str, Path]]) -> List[Path]:
        """
        Filters an iterable of paths, returning only those that are visible (not hidden).
        """
        visible: List[Path] = []
        for p in paths:
            if not self.is_hidden(p):
                visible.append(Path(p))
        return visible
