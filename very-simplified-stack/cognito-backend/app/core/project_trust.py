import json
import os
from pathlib import Path
from typing import Dict

class ProjectTrustStore:
    def __init__(self, store_path: Path | None = None):
        self.store_path = store_path or (Path.home() / ".cognito" / "trust.json")
        self._ensure_dir()

    def _ensure_dir(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> Dict[str, bool]:
        if not self.store_path.exists():
            return {}
        try:
            with open(self.store_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save(self, data: Dict[str, bool]):
        with open(self.store_path, "w") as f:
            json.dump(data, f, indent=2)

    def is_trusted(self, repo_path: str) -> bool:
        path = os.path.realpath(repo_path)
        data = self._load()
        return data.get(path, False)

    def set_trusted(self, repo_path: str, trusted: bool) -> None:
        path = os.path.realpath(repo_path)
        data = self._load()
        data[path] = trusted
        self._save(data)
