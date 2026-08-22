from pathlib import Path
from typing import Iterable, Sequence, Set, Union
import pathspec

try:
    from app.core.protected_files import PROTECTED_FILES
except ImportError:
    PROTECTED_FILES = set()

GENERIC_ACCESS_ERROR = "Archivo o directorio no encontrado o no accesible"

DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".git/**",
    ".env",
    ".env.*",
    "*.env",
    "node_modules",
    "node_modules/**",
    "__pycache__",
    "__pycache__/**",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
]


class FSObservationPolicy:
    """
    Proactive Observation Policy inspired by DeepSeek Harness.
    Prevents the LLM agent from even seeing protected or ignored files
    when using read or listing tools.
    """

    def __init__(
        self,
        cwd: Union[Path, str],
        protected_files: Union[Set[str], Sequence[str], None] = None,
        additional_patterns: Union[Sequence[str], None] = None,
    ) -> None:
        self.cwd = Path(cwd).resolve()

        # Combine protected files
        self.protected_files: set[str] = set()
        if PROTECTED_FILES:
            self.protected_files.update(PROTECTED_FILES)
        if protected_files:
            self.protected_files.update(protected_files)

        # Build patterns list
        patterns = list(DEFAULT_IGNORE_PATTERNS)

        # Add protected files as patterns
        for pf in self.protected_files:
            pf_str = str(pf).strip()
            if pf_str:
                patterns.append(pf_str)
                patterns.append(f"/{pf_str.lstrip('/')}")

        if additional_patterns:
            patterns.extend(additional_patterns)

        # Read .gitignore from cwd if present
        gitignore_path = self.cwd / ".gitignore"
        if gitignore_path.is_file():
            try:
                with gitignore_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str and not line_str.startswith("#"):
                            patterns.append(line_str)
            except Exception:
                pass

        self.spec = pathspec.PathSpec.from_lines("gitignore", patterns)

    def is_path_safe(self, target: Union[Path, str]) -> bool:
        """
        Verifies that target is inside cwd after resolving symlinks and relative references.
        """
        try:
            target_path = Path(target)
            if not target_path.is_absolute():
                target_path = self.cwd / target_path
            target_resolved = target_path.resolve()

            return target_resolved.is_relative_to(self.cwd)
        except Exception:
            return False

    def is_path_ignored(self, target: Union[Path, str]) -> bool:
        """
        Determines whether target path should be hidden/ignored.
        Returns True if the path is outside cwd or matches any exclusion rule.
        """
        if not self.is_path_safe(target):
            return True

        target_path = Path(target)
        if not target_path.is_absolute():
            target_path = self.cwd / target_path
        resolved_target = target_path.resolve()

        # Compute relative path string with forward slashes for pathspec
        try:
            rel_path = resolved_target.relative_to(self.cwd)
        except ValueError:
            return True

        if rel_path == Path("."):
            return False

        rel_str = rel_path.as_posix()

        # Check protected files explicitly (both relative posix str and normalized)
        if rel_str in self.protected_files:
            return True

        # Check if any parent component matches protected files or hidden folders
        for part in rel_path.parts:
            if part in {".git", "node_modules", "__pycache__", ".env"}:
                return True

        # If it's a directory, check with trailing slash too for directory-only patterns
        if resolved_target.is_dir():
            if self.spec.match_file(rel_str + "/"):
                return True

        return self.spec.match_file(rel_str)

    def filter_paths(self, paths: Iterable[Union[Path, str]]) -> list[Path]:
        """
        Filters out ignored or inaccessible paths from a list of paths.
        """
        allowed: list[Path] = []
        for p in paths:
            if not self.is_path_ignored(p):
                allowed.append(Path(p))
        return allowed

    @staticmethod
    def get_generic_error_message() -> str:
        return GENERIC_ACCESS_ERROR
